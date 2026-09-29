import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import api.main as main
from api.rate_limit import RateLimiter
from tests.fakes import FakeSupabase

BALANCED = {"crime": 20, "green": 20, "nightlife": 20, "transport": 20, "rent": 20}
TOP_5 = ["KT1", "TW1", "SW19", "BR3", "SM1"]


class FakePipeline:
    def __init__(self, spawn=False, delay=0.0, fail=False, raises=None):
        self.spawn = spawn
        self.delay = delay
        self.fail = fail
        self.raises = raises

    async def astream(self, initial, stream_mode=None):
        spawn = {"intent": "nursery", "overpass_query": "amenity=kindergarten", "web_search_fallback": False}
        yield "updates", {"knowledge_loader": {"knowledge_base": "## Distilled Knowledge\nx"}}
        if self.raises:
            raise self.raises
        yield "updates", {"orchestrator": {
            "adjusted_allocation": initial["token_allocation"],
            "context_analysis": {"type": "spawn" if self.spawn else "ignore", "reasoning": "r", "spawn": spawn if self.spawn else None},
            "synthesiser_instruction": "",
        }}
        yield "updates", {"context_sub_agent": {
            "spawn_scores": {d: 1.0 for d in TOP_5} if self.spawn else {},
            "spawn_meta": {"from_cache": True},
        }}
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("boom")
        for dim in ("crime", "green", "nightlife", "transport", "rent"):
            yield "updates", {f"{dim}_scorer": {f"{dim}_scores": {d: 0.5 for d in TOP_5}}}
        yield "updates", {"synthesiser_pass1": {
            "weighted_scores": {d: 0.9 - i * 0.1 for i, d in enumerate(TOP_5)},
            "top_10_districts": TOP_5,
            "top_5_districts": TOP_5,
        }}
        for d in TOP_5:
            yield "custom", {"event": "research_started", "district": d}
            yield "custom", {"event": "research_complete", "district": d, "insights": ["a"]}
        yield "updates", {"research_agents": {"qualitative_insights": {d: ["a"] for d in TOP_5}}}
        yield "updates", {"synthesiser_pass2": {
            "top_5": [{"rank": i + 1, "district": d, "verdict": "v", "rationale": "r", "tradeoff": "t", "tip": "p"}
                      for i, d in enumerate(TOP_5)],
            "new_learnings": [{"category": "token_pattern", "content": "c"}],
        }}
        yield "updates", {"knowledge_writer": {"knowledge_result": {
            "learnings_written": 1, "query_count": 7, "distillation_triggered": False,
        }}}


@pytest.fixture
def db():
    return FakeSupabase({
        "agent_config": [{"id": 1, "distilled_brain": "## Brain", "last_distilled": None, "query_count": 7}],
        "learnings": [{"category": "token_pattern", "outcome_summary": "L", "created_at": "2026-09-01"}],
        "distillation_history": [],
        "searches": [],
    })


@pytest.fixture
def client(monkeypatch, db):
    monkeypatch.setattr(main, "get_db", lambda: db)
    monkeypatch.setattr(main, "get_pipeline", lambda: FakePipeline())
    monkeypatch.setattr(main, "limiter", RateLimiter(per_hour=5, daily_cap=100))
    with TestClient(main.app) as c:
        yield c


def _events(body: str) -> list:
    events = []
    for block in body.split("\n\n"):
        lines = [l for l in block.splitlines() if not l.startswith(":")]
        if not lines:
            continue
        name = lines[0].removeprefix("event: ")
        data = json.loads(lines[1].removeprefix("data: "))
        events.append((name, data))
    return events


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["db"] == "ok"


@pytest.mark.parametrize("body,msg", [
    ({"token_allocation": {**BALANCED, "rent": 25}}, "sum to 100"),
    ({"token_allocation": {**BALANCED, "crime": -10, "rent": 50}}, "between 0 and 100"),
    ({"token_allocation": {"crime": 100}}, "exactly these keys"),
    ({"token_allocation": BALANCED, "context_text": "x" * 501}, "500 characters"),
])
def test_search_validation(client, body, msg):
    r = client.post("/api/search", json=body)
    assert r.status_code == 422
    assert msg in json.dumps(r.json())


def test_search_streams_typed_events_and_saves(client, db):
    r = client.post("/api/search", json={"token_allocation": BALANCED, "session_id": "s1"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    names = [n for n, _ in _events(r.text)]
    for expected in ("started", "knowledge_loaded", "orchestrator", "scoring_complete", "shortlist",
                     "research_started", "research_complete", "synthesis_complete", "learning_saved", "done"):
        assert expected in names, expected
    assert "spawn_started" not in names
    events = dict(_events(r.text))
    recs = events["synthesis_complete"]["recommendations"]
    assert len(recs) == 5 and recs[0]["scores"]["crime"] == 0.5
    assert events["learning_saved"]["query_count"] == 7
    saved = db.tables["searches"][0]
    assert saved["session_id"] == "s1" and saved["token_safety"] == 20 and saved["status"] == "complete"
    assert len(saved["top_5"]) == 5


def test_spawn_events(client, monkeypatch):
    monkeypatch.setattr(main, "get_pipeline", lambda: FakePipeline(spawn=True))
    r = client.post("/api/search", json={"token_allocation": BALANCED, "context_text": "nursery"})
    events = dict(_events(r.text))
    assert events["spawn_started"]["intent"] == "nursery"
    assert events["spawn_complete"]["from_cache"] is True
    assert events["spawn_complete"]["districts_matched"] == 5
    assert events["shortlist"]["spawn_filter_applied"] is True


def test_pipeline_error_emits_error_event(client, db, monkeypatch):
    monkeypatch.setattr(main, "get_pipeline", lambda: FakePipeline(fail=True))
    r = client.post("/api/search", json={"token_allocation": BALANCED})
    names = [n for n, _ in _events(r.text)]
    assert names[-1] == "error"
    assert db.tables["searches"][0]["status"] == "error"


def test_model_unavailable_emits_clear_error(client, db, monkeypatch):
    from agents.graph import ModelUnavailableError
    monkeypatch.setattr(main, "get_pipeline", lambda: FakePipeline(raises=ModelUnavailableError("usage limits")))
    r = client.post("/api/search", json={"token_allocation": BALANCED})
    name, data = _events(r.text)[-1]
    assert name == "error" and data["code"] == "model_unavailable"
    assert db.tables["searches"][0]["status"] == "error"


def test_pipeline_timeout_emits_error_event(client, monkeypatch):
    monkeypatch.setattr(main.cfg, "PIPELINE_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(main, "get_pipeline", lambda: FakePipeline(delay=5))
    r = client.post("/api/search", json={"token_allocation": BALANCED})
    events = _events(r.text)
    assert events[-1][0] == "error" and events[-1][1]["code"] == "timeout"


def test_rate_limit_per_ip(client, monkeypatch):
    monkeypatch.setattr(main, "limiter", RateLimiter(per_hour=2, daily_cap=100))
    headers = {"X-Forwarded-For": "1.2.3.4"}
    for _ in range(2):
        assert client.post("/api/search", json={"token_allocation": BALANCED}, headers=headers).status_code == 200
    r = client.post("/api/search", json={"token_allocation": BALANCED}, headers=headers)
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"
    other = client.post("/api/search", json={"token_allocation": BALANCED}, headers={"X-Forwarded-For": "5.6.7.8"})
    assert other.status_code == 200


def test_daily_cap(client, monkeypatch):
    monkeypatch.setattr(main, "limiter", RateLimiter(per_hour=50, daily_cap=3, seed_daily_count=lambda: 2))
    assert client.post("/api/search", json={"token_allocation": BALANCED}).status_code == 200
    r = client.post("/api/search", json={"token_allocation": BALANCED}, headers={"X-Forwarded-For": "9.9.9.9"})
    assert r.status_code == 429
    assert r.json()["error"] == "daily_cap"


def test_invalid_requests_do_not_consume_quota(client, monkeypatch):
    monkeypatch.setattr(main, "limiter", RateLimiter(per_hour=1, daily_cap=100))
    client.post("/api/search", json={"token_allocation": {**BALANCED, "rent": 0}})
    assert client.post("/api/search", json={"token_allocation": BALANCED}).status_code == 200


def test_admin_token_bypasses_rate_limit(client, monkeypatch):
    monkeypatch.setattr(main.cfg, "ADMIN_TOKEN", "secret")
    monkeypatch.setattr(main, "limiter", RateLimiter(per_hour=0, daily_cap=0))
    r = client.post("/api/search", json={"token_allocation": BALANCED}, headers={"X-Admin-Token": "secret"})
    assert r.status_code == 200


def test_spoofed_forwarded_for_prefix_does_not_bypass_limit(client, monkeypatch):
    monkeypatch.setattr(main, "limiter", RateLimiter(per_hour=1, daily_cap=100))
    assert client.post("/api/search", json={"token_allocation": BALANCED},
                       headers={"X-Forwarded-For": "1.1.1.1, 7.7.7.7"}).status_code == 200
    r = client.post("/api/search", json={"token_allocation": BALANCED},
                    headers={"X-Forwarded-For": "2.2.2.2, 7.7.7.7"})
    assert r.status_code == 429


def test_rate_limiter_zero_limit_blocks_cleanly():
    assert RateLimiter(per_hour=0, daily_cap=100).check_and_record("ip")["error"] == "rate_limited"


def test_rate_limiter_window_expires():
    now = [1_000_000.0]
    limiter = RateLimiter(per_hour=1, daily_cap=100, clock=lambda: now[0])
    assert limiter.check_and_record("ip") is None
    assert limiter.check_and_record("ip")["error"] == "rate_limited"
    now[0] += 3601
    assert limiter.check_and_record("ip") is None


def test_knowledge(client):
    r = client.get("/api/knowledge")
    assert r.status_code == 200
    body = r.json()
    assert body["distilled_brain"] == "## Brain"
    assert body["query_count"] == 7
    assert body["queries_until_next_distillation"] == main.cfg.DISTILL_EVERY_N - 7 % main.cfg.DISTILL_EVERY_N
    assert len(body["recent_learnings"]) == 1


def test_admin_distill_requires_token(client, monkeypatch):
    monkeypatch.setattr(main.cfg, "ADMIN_TOKEN", "secret")
    monkeypatch.setattr(main, "run_distillation", lambda: {"status": "ok"})
    assert client.post("/api/admin/distill").status_code == 401
    assert client.post("/api/admin/distill", headers={"X-Admin-Token": "wrong"}).status_code == 401
    r = client.post("/api/admin/distill", headers={"X-Admin-Token": "secret"})
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_cron_requires_secret(client, monkeypatch):
    monkeypatch.setattr(main.cfg, "CRON_SECRET", "cron")
    ran = []
    monkeypatch.setattr(main, "_run_precompute", lambda: ran.append(1))
    assert client.get("/api/cron/refresh-scores").status_code == 401
    r = client.get("/api/cron/refresh-scores", headers={"Authorization": "Bearer cron"})
    assert r.status_code == 202
    assert ran == [1]


def test_demo_recorded_missing(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DEMO_PATH", str(tmp_path / "none.json"))
    assert client.get("/api/demo/recorded").status_code == 404
