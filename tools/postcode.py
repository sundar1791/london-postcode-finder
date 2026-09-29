import asyncio
import httpx

from config import LONDON_POSTCODE_DISTRICTS

POSTCODES_IO_BASE = "https://api.postcodes.io"


async def get_postcode_coordinates(district: str) -> dict:
    """Validate a postcode district and return its centroid coordinates.

    Args:
        district: A postcode district string, e.g. "E1", "SW4", "NW3".

    Returns:
        A dict with keys: outcode, lat, lng.

    Raises:
        ValueError: If the postcode district is invalid or not found.
        RuntimeError: If the postcodes.io API is unreachable.
    """
    url = f"{POSTCODES_IO_BASE}/outcodes/{district}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not reach postcodes.io API: {exc}"
        ) from exc

    if response.status_code == 404:
        raise ValueError(
            f"Postcode district '{district}' is not valid or was not found."
        )

    response.raise_for_status()

    data = response.json().get("result", {})
    return {
        "outcode": district,
        "lat": data["latitude"],
        "lng": data["longitude"],
    }


async def get_all_postcode_coordinates() -> list[dict]:
    """Fetch centroid coordinates for all London postcode districts concurrently.

    Returns:
        A list of dicts, each with keys: outcode, lat, lng.
    """
    results = await asyncio.gather(
        *[get_postcode_coordinates(district) for district in LONDON_POSTCODE_DISTRICTS]
    )
    return list(results)
