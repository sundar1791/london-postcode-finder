import asyncio
import json
import logging
import os
import sys

import anthropic
from anthropic.types import TextBlock
import httpx
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(override=True)

from tools.postcode import get_all_postcode_coordinates

_OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

_OVERPASS_HEADERS = {"User-Agent": "london-postcode-finder/1.0 (portfolio project)"}
_RETRY_STATUSES = {406, 429, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_DELAYS = [10, 20, 30]
_OVERPASS_TIMEOUT = 30.0


def _build_overpass_query(key: str, value: str, lat: float, lng: float) -> str:
    return (
        f'[out:json][timeout:30];\n'
        f'(\n'
        f'  node["{key}"="{value}"](around:500,{lat},{lng});\n'
        f'  way["{key}"="{value}"](around:500,{lat},{lng});\n'
        f');\n'
        f'out count;\n'
    )


async def _fetch_count(
    client: httpx.AsyncClient,
    district: str,
    lat: float,
    lng: float,
    key: str,
    value: str,
) -> dict:
    query = _build_overpass_query(key, value, lat, lng)

    for endpoint in _OVERPASS_ENDPOINTS:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await client.post(
                    endpoint, data={"data": query}, headers=_OVERPASS_HEADERS, timeout=_OVERPASS_TIMEOUT
                )
            except httpx.RequestError as exc:
                logging.warning(
                    "context_sub_agent: %s attempt %d request error for %s: %s",
                    endpoint, attempt, district, exc,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_DELAYS[attempt])
                    continue
                break

            if response.status_code in _RETRY_STATUSES:
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_DELAYS[attempt])
                    continue
                break

            if response.status_code >= 400:
                logging.warning(
                    "context_sub_agent: %s returned HTTP %d for %s — rotating endpoint",
                    endpoint, response.status_code, district,
                )
                break

            try:
                data = response.json()
            except ValueError as exc:
                snippet = (response.text or "")[:240].replace("\n", " ")
                logging.warning(
                    "context_sub_agent: %s not valid JSON for %s (%s); body: %r",
                    endpoint, district, exc, snippet,
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_DELAYS[attempt])
                    continue
                break

            elements = data.get("elements", [])
            if not elements:
                return {"district": district, "raw_count": 0}

            total = int(elements[0].get("tags", {}).get("total", 0))
            return {"district": district, "raw_count": total}

    logging.warning(
        "context_sub_agent: all endpoints exhausted for %s — using count 0", district
    )
    return {"district": district, "raw_count": 0}


def _normalise_counts(results: list) -> dict:
    counts = [r["raw_count"] for r in results]

    if all(c == 0 for c in counts):
        return {r["district"]: 0.0 for r in results}

    min_count = min(counts)
    max_count = max(counts)

    if max_count == min_count:
        return {r["district"]: 0.5 for r in results}

    return {
        r["district"]: round(
            (r["raw_count"] - min_count) / (max_count - min_count), 6
        )
        for r in results
    }


async def _run_overpass_path(spawn: dict) -> dict:
    overpass_query: str = spawn.get("overpass_query", "")
    if "=" not in overpass_query:
        logging.error(
            "context_sub_agent: cannot parse overpass_query '%s' — expected key=value",
            overpass_query,
        )
        return {}

    key, value = overpass_query.split("=", 1)
    logging.info(
        "context_sub_agent: Overpass path — tag %s=%s, radius 500m", key, value
    )

    coordinates = await get_all_postcode_coordinates()

    raw_results: list = []
    async with httpx.AsyncClient() as client:
        for i in range(0, len(coordinates), 2):
            batch = coordinates[i : i + 2]
            batch_results = await asyncio.gather(
                *[
                    _fetch_count(
                        client, coord["outcode"], coord["lat"], coord["lng"], key, value
                    )
                    for coord in batch
                ]
            )
            raw_results.extend(batch_results)
            if i + 2 < len(coordinates):
                await asyncio.sleep(5)

    logging.info(
        "context_sub_agent: Overpass complete — %d districts fetched", len(raw_results)
    )
    return _normalise_counts(raw_results)


async def _run_web_search_path(spawn: dict) -> dict:
    from config import LONDON_POSTCODE_DISTRICTS

    intent: str = spawn.get("intent", "")
    district_list = ", ".join(LONDON_POSTCODE_DISTRICTS)

    prompt = (
        f"For each of these 40 London postcode districts, score from 0-1 how well it "
        f"matches this criterion: {intent}. Districts: {district_list}. Return only a "
        f"JSON object mapping district to score, no other text."
    )

    def _call_claude() -> dict:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        )
        return json.loads(text.strip())

    try:
        result = await asyncio.get_event_loop().run_in_executor(None, _call_claude)
        logging.info("context_sub_agent: web search path complete — %d districts scored", len(result))
        return {k: float(v) for k, v in result.items()}
    except Exception as exc:
        logging.error("context_sub_agent: web search path failed — %s; returning 0.5 for all", exc)
        from config import LONDON_POSTCODE_DISTRICTS
        return {d: 0.5 for d in LONDON_POSTCODE_DISTRICTS}


async def run_context_sub_agent(spawn: dict) -> dict:
    try:
        if spawn.get("web_search_fallback"):
            logging.info(
                "context_sub_agent: web_search_fallback=True — using Claude web search path for intent: %s",
                spawn.get("intent"),
            )
            return await _run_web_search_path(spawn)

        logging.info(
            "context_sub_agent: web_search_fallback=False — using Overpass path for query: %s",
            spawn.get("overpass_query"),
        )
        return await _run_overpass_path(spawn)
    except Exception as exc:
        logging.error("context_sub_agent: unexpected error — %s; spawn filter will not be applied", exc)
        return {}
