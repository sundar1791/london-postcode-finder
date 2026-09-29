"""Record one rich search as a replayable event sequence for the demo fallback.

Runs a Family-preset search with "I need a nursery nearby for my daughter" and
saves every SSE event with its timestamp to api/demo/recorded_run.json (served
by GET /api/demo/recorded) and frontend/public/recorded_run.json (used when the
backend itself is unreachable).

Usage:
    python tools/record_demo_run.py                     # in-process, uses .env
    python tools/record_demo_run.py --api https://...   # record against a deployed backend
                                                        # (send ADMIN_TOKEN to skip rate limits)
Costs one search (~$0.20).
"""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS = [
    os.path.join(ROOT, "api", "demo", "recorded_run.json"),
    os.path.join(ROOT, "frontend", "public", "recorded_run.json"),
]
REQUEST = {
    "token_allocation": {"crime": 35, "green": 30, "nightlife": 0, "transport": 15, "rent": 20},
    "context_text": "I need a nursery nearby for my daughter",
    "session_id": "recorded-demo",
}


def _parse(block: str):
    event, data = None, None
    for line in block.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data = json.loads(line[5:].strip())
    return (event, data) if event else None


async def _chunks_in_process():
    from api.main import SearchRequest, _stream
    async for chunk in _stream(SearchRequest(**REQUEST)):
        yield chunk


async def _chunks_remote(api: str, admin_token: str):
    headers = {"X-Admin-Token": admin_token} if admin_token else {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        async with client.stream("POST", f"{api.rstrip('/')}/api/search", json=REQUEST, headers=headers) as res:
            res.raise_for_status()
            buffer = ""
            async for text in res.aiter_text():
                buffer += text
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    yield block + "\n\n"


async def record(api: str, admin_token: str) -> dict:
    start = time.monotonic()
    events = []
    source = _chunks_remote(api, admin_token) if api else _chunks_in_process()
    async for chunk in source:
        for block in chunk.split("\n\n"):
            parsed = _parse(block)
            if not parsed:
                continue
            event, data = parsed
            t_ms = int((time.monotonic() - start) * 1000)
            events.append({"event": event, "data": data, "t_ms": t_ms})
            print(f"{t_ms / 1000:6.1f}s  {event}")
    return {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "request": {k: REQUEST[k] for k in ("token_allocation", "context_text")},
        "events": events,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="", help="Base URL of a deployed backend (default: run in-process)")
    args = parser.parse_args()

    run = asyncio.run(record(args.api, os.getenv("ADMIN_TOKEN", "")))
    names = [e["event"] for e in run["events"]]
    if "done" not in names or "synthesis_complete" not in names:
        print(f"\nRun did not complete ({names[-1] if names else 'no events'}) — nothing saved.")
        sys.exit(1)

    for path in OUTPUTS:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(run, f, indent=1)
        print(f"Saved {len(run['events'])} events to {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
