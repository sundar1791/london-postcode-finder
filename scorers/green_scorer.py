import asyncio

import httpx

from tools.postcode import get_all_postcode_coordinates, get_postcode_coordinates

# Public Overpass instances often return 504 under load; try several mirrors.
_OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
)

# Deprecated single URL (kept for any external imports); prefer _OVERPASS_ENDPOINTS.
OVERPASS_API = _OVERPASS_ENDPOINTS[0]

_OVERPASS_QUERY_TEMPLATE = """
[out:json];
(
  node["leisure"="park"](around:800,{lat},{lng});
  way["leisure"="park"](around:800,{lat},{lng});
  relation["leisure"="park"](around:800,{lat},{lng});
  node["leisure"="nature_reserve"](around:800,{lat},{lng});
  way["leisure"="nature_reserve"](around:800,{lat},{lng});
  relation["leisure"="nature_reserve"](around:800,{lat},{lng});
  node["landuse"="grass"](around:800,{lat},{lng});
  way["landuse"="grass"](around:800,{lat},{lng});
  relation["landuse"="grass"](around:800,{lat},{lng});
  node["landuse"="forest"](around:800,{lat},{lng});
  way["landuse"="forest"](around:800,{lat},{lng});
  relation["landuse"="forest"](around:800,{lat},{lng});
);
out count;
"""


# 502/503: bad gateway / overloaded; 429/504: rate limit / timeout
_RETRY_STATUSES = {429, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_DELAYS = [10, 20, 30]
# Overpass can take a long time when busy; short timeouts cause false failures.
_OVERPASS_TIMEOUT = 120.0


async def _fetch_green_count(
    client: httpx.AsyncClient, district: str, lat: float, lng: float
) -> dict:
    query = _OVERPASS_QUERY_TEMPLATE.format(lat=lat, lng=lng)
    endpoint_errors: list[str] = []

    for endpoint in _OVERPASS_ENDPOINTS:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await client.post(
                    endpoint, data={"data": query}, timeout=_OVERPASS_TIMEOUT
                )
            except httpx.RequestError as exc:
                endpoint_errors.append(f"{endpoint} attempt {attempt}: {exc}")
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_DELAYS[attempt])
                    continue
                break  # try next mirror

            if response.status_code in _RETRY_STATUSES:
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_DELAYS[attempt])
                    continue
                endpoint_errors.append(
                    f"{endpoint}: HTTP {response.status_code} after {_MAX_RETRIES} retries"
                )
                break  # try next mirror

            response.raise_for_status()

            # Overpass sometimes returns HTTP 200 with an HTML/XML error page
            # (e.g. Dispatcher_Client::protocol_error) instead of JSON.
            try:
                data = response.json()
            except ValueError as exc:
                snippet = (response.text or "")[:240].replace("\n", " ")
                endpoint_errors.append(
                    f"{endpoint}: not valid JSON ({exc!s}); body starts: {snippet!r}"
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_DELAYS[attempt])
                    continue
                break  # try next mirror

            elements = data.get("elements", [])
            if not elements:
                return {"district": district, "raw_count": 0}

            count_element = elements[0]
            total = int(count_element.get("tags", {}).get("total", 0))
            return {"district": district, "raw_count": total}

    raise RuntimeError(
        f"Overpass API unavailable for district {district} after trying "
        f"{len(_OVERPASS_ENDPOINTS)} endpoint(s). Details: {'; '.join(endpoint_errors)}"
    )


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
    """Fetch green space counts for all London postcode districts and return normalised scores.

    Returns:
        List of dicts with keys: district, raw_count, score.
        score is normalised 0-1 where 1 = most green space.

    Raises:
        RuntimeError: If the Overpass API is unreachable.
    """
    coordinates = await get_all_postcode_coordinates()

    raw_results = []
    async with httpx.AsyncClient() as client:
        # Small batches + pause between batches reduce 429/504 from public Overpass.
        for i in range(0, len(coordinates), 2):
            batch = coordinates[i : i + 2]
            batch_results = await asyncio.gather(
                *[
                    _fetch_green_count(
                        client, coord["outcode"], coord["lat"], coord["lng"]
                    )
                    for coord in batch
                ]
            )
            raw_results.extend(batch_results)
            if i + 2 < len(coordinates):
                await asyncio.sleep(5)

    return _normalise(raw_results)


async def score_single_postcode(district: str) -> dict:
    """Fetch the green space count for a single postcode district.

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
        result = await _fetch_green_count(
            client, district, coord["lat"], coord["lng"]
        )

    return {"district": result["district"], "raw_count": result["raw_count"], "score": 0.5}
