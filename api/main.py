import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

import config as cfg
from api.events import EventMapper
from api.rate_limit import RateLimiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")

DIMENSIONS = ("crime", "green", "nightlife", "transport", "rent")
DEMO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo", "recorded_run.json")
HEARTBEAT_SECONDS = 15


def get_db():
    from tools.db import get_client
    return get_client()


def get_pipeline():
    from agents.graph import pipeline
    return pipeline


def run_distillation() -> dict:
    from agents.distiller import distil
    return distil()


def _count_searches_today() -> int:
    midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = get_db().table("searches").select("id").gte("created_at", midnight.isoformat()).execute().data
    return len(rows or [])


app = FastAPI(title="London Postcode Finder API", version="1.0.0")

_origins = [o.strip() for o in cfg.FRONTEND_ORIGIN.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins + ["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=os.getenv("FRONTEND_ORIGIN_REGEX") or None,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

limiter = RateLimiter(cfg.RATE_LIMIT_PER_HOUR, cfg.DAILY_SEARCH_CAP, seed_daily_count=_count_searches_today)
_distill_lock = asyncio.Lock()
_background: set = set()


class SearchRequest(BaseModel):
    token_allocation: Dict[str, int]
    context_text: str = ""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), max_length=100)

    @field_validator("token_allocation")
    @classmethod
    def _check_tokens(cls, v: Dict[str, int]) -> Dict[str, int]:
        if set(v) != set(DIMENSIONS):
            raise ValueError(f"token_allocation must have exactly these keys: {', '.join(DIMENSIONS)}")
        for key, value in v.items():
            if not 0 <= value <= 100:
                raise ValueError(f"{key} must be between 0 and 100 (got {value})")
        total = sum(v.values())
        if total != 100:
            raise ValueError(f"Tokens must sum to 100 (got {total})")
        return {k: v[k] for k in DIMENSIONS}

    @field_validator("context_text")
    @classmethod
    def _check_context(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) > 500:
            raise ValueError(f"Context must be 500 characters or fewer (got {len(v)})")
        return v


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_admin(token: Optional[str]) -> bool:
    return bool(cfg.ADMIN_TOKEN) and token == cfg.ADMIN_TOKEN


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _save_search(req: SearchRequest, mapper: EventMapper, status: str, duration_ms: int) -> Optional[str]:
    alloc = req.token_allocation
    row = {
        "session_id": req.session_id,
        "token_safety": alloc["crime"],
        "token_green": alloc["green"],
        "token_nightlife": alloc["nightlife"],
        "token_transport": alloc["transport"],
        "token_rent": alloc["rent"],
        "context_text": req.context_text or None,
        "results": mapper.result_summary(),
        "adjusted_allocation": mapper.state.get("adjusted_allocation"),
        "top_5": mapper.state.get("recommendations"),
        "duration_ms": duration_ms,
        "status": status,
    }
    try:
        data = get_db().table("searches").insert(row).execute().data
        return data[0].get("id") if data else None
    except Exception as exc:
        log.error("could not save search: %s", exc)
        return None


async def _distil_in_background() -> None:
    if _distill_lock.locked():
        log.info("distillation already running — skipping duplicate trigger")
        return
    async with _distill_lock:
        result = await asyncio.get_event_loop().run_in_executor(None, run_distillation)
        log.info("background distillation finished: %s", result)


def _spawn_background(coro) -> None:
    task = asyncio.ensure_future(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _produce(req: SearchRequest, queue: asyncio.Queue) -> None:
    from agents.state import make_initial_state

    mapper = EventMapper(req.token_allocation, req.context_text)
    start = time.monotonic()
    loop = asyncio.get_event_loop()
    status = "complete"
    try:
        initial = make_initial_state(req.token_allocation, req.context_text, req.session_id)
        async for mode, chunk in get_pipeline().astream(initial, stream_mode=["updates", "custom"]):
            if mode == "custom":
                events = mapper.handle_custom(chunk)
            else:
                events = [e for node, update in chunk.items() for e in mapper.handle_update(node, update)]
            for event in events:
                await queue.put(event)

        if not mapper.state.get("recommendations"):
            raise RuntimeError("The synthesiser did not return recommendations.")

        duration_ms = int((time.monotonic() - start) * 1000)
        search_id = await loop.run_in_executor(None, _save_search, req, mapper, status, duration_ms)
        await queue.put(("done", {"search_id": search_id, "duration_ms": duration_ms}))

        if (mapper.state.get("knowledge_result") or {}).get("distillation_triggered"):
            _spawn_background(_distil_in_background())
    except asyncio.CancelledError:
        _save_search(req, mapper, "timeout", int((time.monotonic() - start) * 1000))
        raise
    except Exception as exc:
        log.exception("pipeline failed")
        status = "error"
        duration_ms = int((time.monotonic() - start) * 1000)
        await loop.run_in_executor(None, _save_search, req, mapper, status, duration_ms)
        await queue.put(("error", {"code": "pipeline_failed", "message": str(exc) or "The pipeline failed."}))
    finally:
        await queue.put(None)


async def _stream(req: SearchRequest) -> AsyncIterator[str]:
    queue: asyncio.Queue = asyncio.Queue()
    producer = asyncio.ensure_future(_produce(req, queue))
    _background.add(producer)
    producer.add_done_callback(_background.discard)

    loop = asyncio.get_event_loop()
    deadline = loop.time() + cfg.PIPELINE_TIMEOUT_SECONDS
    yield _sse("started", {"session_id": req.session_id, "timeout_seconds": cfg.PIPELINE_TIMEOUT_SECONDS})
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            producer.cancel()
            yield _sse("error", {
                "code": "timeout",
                "message": f"The pipeline took longer than {cfg.PIPELINE_TIMEOUT_SECONDS} seconds and was stopped.",
            })
            return
        try:
            item = await asyncio.wait_for(queue.get(), timeout=min(HEARTBEAT_SECONDS, remaining))
        except asyncio.TimeoutError:
            yield ": keep-alive\n\n"
            continue
        if item is None:
            return
        event, data = item
        yield _sse(event, data)


@app.get("/api/health")
async def health():
    db_status = "ok"
    try:
        await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, lambda: get_db().table("agent_config").select("id").eq("id", 1).execute()
            ),
            timeout=5,
        )
    except Exception as exc:
        db_status = f"error: {type(exc).__name__}"
    return {"status": "ok", "db": db_status, "version": app.version}


@app.post("/api/search")
async def search(req: SearchRequest, request: Request, x_admin_token: Optional[str] = Header(None)):
    if not _is_admin(x_admin_token):
        blocked = limiter.check_and_record(_client_ip(request))
        if blocked:
            return JSONResponse(blocked, status_code=429, headers={"Retry-After": str(blocked["retry_after"])})
    return StreamingResponse(
        _stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


def _read_knowledge() -> dict:
    db = get_db()
    config_rows = db.table("agent_config").select("*").eq("id", 1).execute().data or [{}]
    config = config_rows[0]
    learnings = (
        db.table("learnings").select("*").order("created_at", desc=True).limit(10).execute().data or []
    )
    history = (
        db.table("distillation_history").select("*").order("created_at", desc=True).limit(20).execute().data or []
    )
    query_count = config.get("query_count") or 0
    every_n = cfg.DISTILL_EVERY_N
    return {
        "distilled_brain": config.get("distilled_brain"),
        "last_distilled": config.get("last_distilled"),
        "query_count": query_count,
        "distill_every_n": every_n,
        "queries_until_next_distillation": (every_n - query_count % every_n) if every_n > 0 else None,
        "recent_learnings": learnings,
        "distillation_history": history,
    }


@app.get("/api/knowledge")
async def knowledge():
    try:
        return await asyncio.get_event_loop().run_in_executor(None, _read_knowledge)
    except Exception as exc:
        log.exception("knowledge read failed")
        raise HTTPException(status_code=503, detail=f"Could not read knowledge base: {exc}")


@app.get("/api/knowledge/export", response_class=PlainTextResponse)
async def knowledge_export():
    data = await asyncio.get_event_loop().run_in_executor(None, _read_knowledge)
    learnings = "\n".join(
        f"- [{l.get('category')}] {l.get('outcome_summary') or ''}" for l in data["recent_learnings"]
    )
    body = (
        "# London Postcode Finder — Knowledge\n\n"
        f"_Exported {datetime.now(timezone.utc).isoformat()} · {data['query_count']} queries · "
        f"last distilled {data['last_distilled'] or 'never'}_\n\n"
        f"{data['distilled_brain'] or 'No distilled knowledge yet.'}\n\n"
        f"## Recent learnings\n{learnings or 'None yet.'}\n"
    )
    return PlainTextResponse(body, media_type="text/markdown", headers={
        "Content-Disposition": 'attachment; filename="knowledge.md"',
    })


@app.post("/api/admin/distill")
async def admin_distill(x_admin_token: Optional[str] = Header(None)):
    if not cfg.ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured")
    if not _is_admin(x_admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    if _distill_lock.locked():
        raise HTTPException(status_code=409, detail="A distillation is already running")
    async with _distill_lock:
        return await asyncio.get_event_loop().run_in_executor(None, run_distillation)


def _run_precompute() -> None:
    from tools.precompute_scores import main as precompute_main
    asyncio.run(precompute_main())


@app.get("/api/cron/refresh-scores", status_code=202)
async def cron_refresh_scores(
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    x_cron_secret: Optional[str] = Header(None),
):
    if not cfg.CRON_SECRET:
        raise HTTPException(status_code=503, detail="CRON_SECRET is not configured")
    supplied = x_cron_secret or (authorization or "").replace("Bearer ", "", 1)
    if supplied != cfg.CRON_SECRET:
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    background_tasks.add_task(_run_precompute)
    return {"status": "accepted", "message": "Score refresh started in the background."}


@app.get("/api/demo/recorded")
async def demo_recorded():
    if not os.path.exists(DEMO_PATH):
        raise HTTPException(status_code=404, detail="No recorded run available")
    with open(DEMO_PATH, "r") as f:
        return json.load(f)
