"""Warm up a fresh deployment: run ~12 varied searches so learnings accumulate
and the distiller fires at least once.

Covers every orchestrator path — ignore, adjust, spawn (Overpass and web
search) and adjust+spawn — so the spawn cache is also pre-filled for the demo
queries.

Usage:
    python tools/seed_demo.py --yes                   # in-process, uses .env (local or hosted Supabase)
    python tools/seed_demo.py --yes --api https://…   # through a deployed backend; set ADMIN_TOKEN
                                                      # in your env to bypass rate limits
Costs roughly $2–3 in Anthropic API calls.
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BALANCED = {"crime": 20, "green": 20, "nightlife": 20, "transport": 20, "rent": 20}
YOUNG_PRO = {"crime": 10, "green": 10, "nightlife": 35, "transport": 35, "rent": 10}
FAMILY = {"crime": 35, "green": 30, "nightlife": 0, "transport": 15, "rent": 20}
BUDGET = {"crime": 15, "green": 10, "nightlife": 5, "transport": 20, "rent": 50}
SAFETY = {"crime": 40, "green": 20, "nightlife": 15, "transport": 15, "rent": 10}
GREEN = {"crime": 15, "green": 45, "nightlife": 5, "transport": 20, "rent": 15}

QUERIES = [
    ("baseline", BALANCED, ""),
    ("ignore", YOUNG_PRO, "I like pizza"),
    ("adjust", SAFETY, "I'm terrified of crime"),
    ("spawn", FAMILY, "I need a nursery nearby for my daughter"),
    ("adjust", BALANCED, "I love parks and quiet streets"),
    ("adjust", BUDGET, "I'm on a very tight budget, every pound counts"),
    ("spawn", YOUNG_PRO, "I want to be near a mosque"),
    ("combination", FAMILY, "I need good schools and I'm really worried about crime"),
    ("adjust", YOUNG_PRO, "I go out most nights and hate long night bus journeys home"),
    ("spawn (web)", BALANCED, "I want a strong Tamil community nearby"),
    ("adjust", GREEN, "I run every morning and want a big park on my doorstep"),
    ("combination", BUDGET, "I need a gym nearby and rent has to be cheap"),
]


def _parse_events(text: str) -> list:
    events = []
    for block in text.split("\n\n"):
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if name:
            events.append((name, data))
    return events


async def _run_in_process(allocation: dict, context: str, session_id: str) -> list:
    from api.main import SearchRequest, _stream
    chunks = []
    async for chunk in _stream(SearchRequest(token_allocation=allocation, context_text=context, session_id=session_id)):
        chunks.append(chunk)
    return _parse_events("".join(chunks))


async def _run_remote(api: str, allocation: dict, context: str, session_id: str) -> list:
    headers = {"X-Admin-Token": os.getenv("ADMIN_TOKEN", "")} if os.getenv("ADMIN_TOKEN") else {}
    body = {"token_allocation": allocation, "context_text": context, "session_id": session_id}
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        res = await client.post(f"{api.rstrip('/')}/api/search", json=body, headers=headers)
        if res.status_code != 200:
            return [("error", {"code": res.status_code, "message": res.text[:200]})]
        return _parse_events(res.text)


async def _wait_for_background_distillation() -> None:
    import api.main as main
    if main._background:
        print("\nWaiting for background distillation to finish…")
        await asyncio.gather(*list(main._background), return_exceptions=True)


async def seed(api: str) -> None:
    rows = []
    for i, (label, allocation, context) in enumerate(QUERIES, 1):
        started = time.monotonic()
        print(f"[{i:2}/{len(QUERIES)}] {label:12} {context or '(no context)'}", flush=True)
        if api:
            events = await _run_remote(api, allocation, context, f"seed-demo-{i}")
        else:
            events = await _run_in_process(allocation, context, f"seed-demo-{i}")
        by_name = dict(events)
        orch = by_name.get("orchestrator") or {}
        spawn = by_name.get("spawn_complete") or {}
        recs = (by_name.get("synthesis_complete") or {}).get("recommendations") or []
        learning = by_name.get("learning_saved") or {}
        rows.append({
            "label": label,
            "type": orch.get("type", "?"),
            "spawn": (f"{spawn.get('districts_matched')}/{spawn.get('districts_total')}"
                      + (" cached" if spawn.get("from_cache") else "")) if spawn else "",
            "top3": ", ".join(r["district"] for r in recs[:3]),
            "query_count": learning.get("query_count"),
            "distil": "yes" if learning.get("distillation_due") else "",
            "secs": round(time.monotonic() - started),
            "error": (by_name.get("error") or {}).get("message", ""),
        })
        print(f"      -> {rows[-1]['type']:11} top: {rows[-1]['top3'] or '-'} ({rows[-1]['secs']}s)"
              + (f"  ERROR: {rows[-1]['error']}" if rows[-1]["error"] else ""), flush=True)

    if not api:
        await _wait_for_background_distillation()

    print("\n  #  expected      got          spawn         top 3              count  distil  secs")
    for i, r in enumerate(rows, 1):
        print(f"{i:3}  {r['label']:12}  {r['type']:11}  {r['spawn']:12}  {r['top3']:17}  "
              f"{str(r['query_count'] or '-'):>5}  {r['distil']:6}  {r['secs']:4}")
    failures = [r for r in rows if r["error"]]
    print(f"\n{len(rows) - len(failures)} of {len(rows)} searches completed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="Confirm you want to spend ~$2–3 on API calls")
    parser.add_argument("--api", default="", help="Base URL of a deployed backend (default: run in-process)")
    args = parser.parse_args()
    if not args.yes:
        print(__doc__)
        print("Refusing to run without --yes (this spends real money on the Anthropic API).")
        sys.exit(2)
    asyncio.run(seed(args.api))


if __name__ == "__main__":
    main()
