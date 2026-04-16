import asyncio
from datetime import date
from typing import Optional

import httpx

from tools.postcode import get_all_postcode_coordinates

POLICE_API_BASE = "https://data.police.uk/api/crimes-street/all-crime"


def _default_date() -> str:
    """Return the most recent full month as YYYY-MM (current month minus 4)."""
    today = date.today()
    month = today.month - 4
    year = today.year
    if month <= 0:
        month += 12
        year -= 1
    return f"{year}-{month:02d}"


async def _fetch_crime_count(
    client: httpx.AsyncClient, district: str, lat: float, lng: float, date_str: str
) -> dict:
    url = POLICE_API_BASE
    params = {"lat": lat, "lng": lng, "date": date_str}
    retry_delays = [10, 20, 30]

    for attempt, delay in enumerate(retry_delays):
        try:
            response = await client.get(url, params=params, timeout=30.0)
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Could not reach UK Police API: {exc}"
            ) from exc

        if response.status_code == 404 or response.text.strip() in ("", "[]"):
            return {"district": district, "raw_count": 0}

        if response.status_code in (429, 504):
            if attempt < len(retry_delays) - 1:
                await asyncio.sleep(delay)
                continue
            print(f"Warning: Police API unavailable for {district} after 3 retries. Using count 0.")
            return {"district": district, "raw_count": 0}

        response.raise_for_status()
        data = response.json()
        return {"district": district, "raw_count": len(data) if data else 0}

    print(f"Warning: Police API unavailable for {district} after 3 retries. Using count 0.")
    return {"district": district, "raw_count": 0}


def _normalise(results: list[dict]) -> list[dict]:
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
            "score": round(1 - (r["raw_count"] - min_count) / (max_count - min_count), 6),
        }
        for r in results
    ]


async def score_all_postcodes(date: Optional[str] = None) -> list[dict]:
    """Fetch crime counts for all London postcode districts and return normalised safety scores.

    Args:
        date: Month to query in YYYY-MM format. Defaults to the most recent full month
              (current month minus 2, to ensure data availability).

    Returns:
        List of dicts with keys: district, raw_count, score.
        score is normalised 0-1 where 1 = safest (lowest crime count).

    Raises:
        RuntimeError: If the UK Police API is unreachable.
    """
    if date is None:
        date = _default_date()

    coordinates = await get_all_postcode_coordinates()

    raw_results = []
    async with httpx.AsyncClient() as client:
        for i in range(0, len(coordinates), 5):
            batch = coordinates[i : i + 5]
            batch_results = await asyncio.gather(
                *[
                    _fetch_crime_count(client, coord["outcode"], coord["lat"], coord["lng"], date)
                    for coord in batch
                ]
            )
            raw_results.extend(batch_results)
            if i + 5 < len(coordinates):
                await asyncio.sleep(1)

    return _normalise(raw_results)


async def score_single_postcode(district: str, date: Optional[str] = None) -> dict:
    """Fetch the crime score for a single postcode district.

    The score is computed relative to only this district (always 0.5 since there is
    one data point), but raw_count reflects the true API value. Useful for testing
    connectivity and response shape.

    Args:
        district: A postcode district string, e.g. "E1".
        date: Month to query in YYYY-MM format. Defaults to the most recent full month.

    Returns:
        A dict with keys: district, raw_count, score.

    Raises:
        RuntimeError: If the UK Police API is unreachable.
    """
    if date is None:
        date = _default_date()

    from tools.postcode import get_postcode_coordinates

    coord = await get_postcode_coordinates(district)

    async with httpx.AsyncClient() as client:
        result = await _fetch_crime_count(
            client, district, coord["lat"], coord["lng"], date
        )

    return {"district": result["district"], "raw_count": result["raw_count"], "score": 0.5}
