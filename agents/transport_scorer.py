import asyncio
import os
from typing import Optional

import httpx

from tools.postcode import get_all_postcode_coordinates, get_postcode_coordinates

TFL_APP_KEY: Optional[str] = os.environ.get("TFL_APP_KEY")
if not TFL_APP_KEY:
    raise ValueError(
        "TFL_APP_KEY environment variable is not set. "
        "Register at api.tfl.gov.uk to obtain a key."
    )

TFL_STOPPOINT_URL = "https://api.tfl.gov.uk/StopPoint"
_STOP_TYPES = "NaptanMetroStation,NaptanRailStation,NaptanBusCoachStation"

_MAX_RETRIES = 3
_RETRY_DELAYS = [5, 10, 15]
_RETRY_STATUSES = {429, 500, 502, 503, 504}


async def _fetch_transport_score(
    client: httpx.AsyncClient, district: str, lat: float, lng: float
) -> dict:
    params = {
        "lat": lat,
        "lon": lng,
        "stopTypes": _STOP_TYPES,
        "radius": 800,
        "app_key": TFL_APP_KEY,
    }

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await client.get(TFL_STOPPOINT_URL, params=params, timeout=15.0)
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Could not reach TfL API: {exc}"
            ) from exc

        if response.status_code in _RETRY_STATUSES:
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAYS[attempt])
                continue
            print(
                f"Warning: TfL API unavailable for {district} after {_MAX_RETRIES} retries "
                f"(HTTP {response.status_code}). "
                "Using raw_score 0."
            )
            return {"district": district, "raw_score": 0.0}

        if response.status_code == 400:
            # Invalid query params / temporary API-side validation issues.
            print(
                f"Warning: TfL API returned 400 for {district}. "
                "Using raw_score 0."
            )
            return {"district": district, "raw_score": 0.0}

        response.raise_for_status()

        data = response.json()
        stops = data.get("stopPoints", [])

        if not stops:
            print(f"Warning: No stops found for district {district}. Using raw_score 0.")
            return {"district": district, "raw_score": 0.0}

        stop_count = len(stops)
        lines: set = set()
        for stop in stops:
            for line in stop.get("lines", []):
                line_id = line.get("id")
                if line_id:
                    lines.add(line_id)

        raw_score = round((stop_count * 0.4) + (len(lines) * 0.6), 6)
        return {"district": district, "raw_score": raw_score}

    # Unreachable — loop always returns or raises — but satisfies type checkers
    return {"district": district, "raw_score": 0.0}


def _normalise(results: list) -> list:
    scores = [r["raw_score"] for r in results]
    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        return [
            {"district": r["district"], "raw_score": r["raw_score"], "score": 0.5}
            for r in results
        ]

    return [
        {
            "district": r["district"],
            "raw_score": r["raw_score"],
            "score": round((r["raw_score"] - min_score) / (max_score - min_score), 6),
        }
        for r in results
    ]


async def score_all_postcodes() -> list:
    """Fetch transport connectivity scores for all London postcode districts.

    Connectivity is measured as (stop_count * 0.4) + (distinct_lines * 0.6),
    weighting line diversity more heavily than raw stop count.

    Returns:
        List of dicts with keys: district, raw_score, score.
        score is normalised 0-1 where 1 = most connected.

    Raises:
        RuntimeError: If the TfL API is unreachable.
    """
    coordinates = await get_all_postcode_coordinates()

    raw_results = []
    async with httpx.AsyncClient() as client:
        for i in range(0, len(coordinates), 5):
            batch = coordinates[i : i + 5]
            batch_results = await asyncio.gather(
                *[
                    _fetch_transport_score(client, coord["outcode"], coord["lat"], coord["lng"])
                    for coord in batch
                ]
            )
            raw_results.extend(batch_results)
            if i + 5 < len(coordinates):
                await asyncio.sleep(2)

    return _normalise(raw_results)


async def score_single_postcode(district: str) -> dict:
    """Fetch the transport connectivity score for a single postcode district.

    The score is a placeholder of 0.5 since normalisation requires all districts.

    Args:
        district: A postcode district string, e.g. "E1".

    Returns:
        A dict with keys: district, raw_score, score.

    Raises:
        RuntimeError: If the TfL API is unreachable.
    """
    coord = await get_postcode_coordinates(district)

    async with httpx.AsyncClient() as client:
        result = await _fetch_transport_score(
            client, district, coord["lat"], coord["lng"]
        )

    return {"district": result["district"], "raw_score": result["raw_score"], "score": 0.5}
