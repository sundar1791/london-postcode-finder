import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv
from supabase import create_client

from tools.postcode import get_all_postcode_coordinates, get_postcode_coordinates

load_dotenv()


def _get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url:
        raise ValueError("SUPABASE_URL environment variable is not set")
    if not key:
        raise ValueError("SUPABASE_KEY environment variable is not set")
    try:
        return create_client(url, key)
    except Exception as exc:
        raise RuntimeError(f"Could not connect to Supabase: {exc}") from exc


def score_all_from_cache(supabase=None) -> dict[str, float]:
    if supabase is None:
        supabase = _get_client()
    try:
        response = (
            supabase.table("cached_scores")
            .select("district,score,needs_retry")
            .eq("dimension", "nightlife")
            .execute()
        )
    except Exception as exc:
        raise RuntimeError(f"Could not read cached_scores for dimension 'nightlife': {exc}") from exc

    rows = response.data
    if not rows:
        raise RuntimeError("cached_scores returned 0 rows for dimension 'nightlife' — cache may not be populated")

    result = {}
    for row in rows:
        if row.get("needs_retry"):
            logging.warning("[nightlife] District %s has needs_retry=True — score is a placeholder", row["district"])
        result[row["district"]] = row["score"]
    return result

OVERPASS_API = "https://overpass-api.de/api/interpreter"

_OVERPASS_QUERY_TEMPLATE = """
[out:json];
(
  node["amenity"="bar"](around:800,{lat},{lng});
  way["amenity"="bar"](around:800,{lat},{lng});
  relation["amenity"="bar"](around:800,{lat},{lng});
  node["amenity"="pub"](around:800,{lat},{lng});
  way["amenity"="pub"](around:800,{lat},{lng});
  relation["amenity"="pub"](around:800,{lat},{lng});
  node["amenity"="nightclub"](around:800,{lat},{lng});
  way["amenity"="nightclub"](around:800,{lat},{lng});
  relation["amenity"="nightclub"](around:800,{lat},{lng});
  node["amenity"="restaurant"](around:800,{lat},{lng});
  way["amenity"="restaurant"](around:800,{lat},{lng});
  relation["amenity"="restaurant"](around:800,{lat},{lng});
);
out count;
"""

_RETRY_STATUSES = {429, 504}
_MAX_RETRIES = 3
_RETRY_DELAYS = [10, 20, 30]


async def _fetch_nightlife_count(
    client: httpx.AsyncClient, district: str, lat: float, lng: float
) -> dict:
    query = _OVERPASS_QUERY_TEMPLATE.format(lat=lat, lng=lng)

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await client.post(
                OVERPASS_API, data={"data": query}, timeout=30.0
            )
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Could not reach Overpass API: {exc}"
            ) from exc

        if response.status_code in _RETRY_STATUSES:
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAYS[attempt])
                continue
            print(f"Warning: Overpass unavailable for {district} after {_MAX_RETRIES} retries. Using count 0.")
            return {"district": district, "raw_count": 0}

        response.raise_for_status()

        data = response.json()
        elements = data.get("elements", [])
        if not elements:
            return {"district": district, "raw_count": 0}

        count_element = elements[0]
        total = int(count_element.get("tags", {}).get("total", 0))
        return {"district": district, "raw_count": total}

    raise RuntimeError(f"Overpass API failed for district {district} after {_MAX_RETRIES} retries.")


def _normalise(results: list) -> list:
    counts = [r["raw_count"] for r in results]
    min_count = min(counts)
    max_count = max(counts)

    if max_count == min_count:
        return [
            {"district": r["district"], "raw_count": r["raw_count"], "score": 0.5}
            for r in results
        ]

    return [
        {
            "district": r["district"],
            "raw_count": r["raw_count"],
            "score": round((r["raw_count"] - min_count) / (max_count - min_count), 6),
        }
        for r in results
    ]


async def score_all_postcodes() -> list:
    """Fetch nightlife venue counts for all London postcode districts and return normalised scores.

    Returns:
        List of dicts with keys: district, raw_count, score.
        score is normalised 0-1 where 1 = most nightlife.

    Raises:
        RuntimeError: If the Overpass API is unreachable.
    """
    coordinates = await get_all_postcode_coordinates()

    raw_results = []
    async with httpx.AsyncClient() as client:
        for i in range(0, len(coordinates), 2):
            batch = coordinates[i : i + 2]
            batch_results = await asyncio.gather(
                *[
                    _fetch_nightlife_count(client, coord["outcode"], coord["lat"], coord["lng"])
                    for coord in batch
                ]
            )
            raw_results.extend(batch_results)
            if i + 2 < len(coordinates):
                await asyncio.sleep(5)

    return _normalise(raw_results)


async def score_single_postcode(district: str) -> dict:
    """Fetch the nightlife score for a single postcode district.

    The score is a placeholder of 0.5 since normalisation requires all districts.

    Args:
        district: A postcode district string, e.g. "E1".

    Returns:
        A dict with keys: district, raw_count, score.

    Raises:
        RuntimeError: If the Overpass API is unreachable.
    """
    coord = await get_postcode_coordinates(district)

    async with httpx.AsyncClient() as client:
        result = await _fetch_nightlife_count(
            client, district, coord["lat"], coord["lng"]
        )

    return {"district": result["district"], "raw_count": result["raw_count"], "score": 0.5}
