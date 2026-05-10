import logging
import os
import re
import statistics
from typing import Optional

from supabase import create_client
from dotenv import load_dotenv
load_dotenv(override=True)


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


def _letter_prefix(district: str) -> str:
    """Return the leading letters of a district code, e.g. 'SW11' → 'SW', 'E1' → 'E'."""
    m = re.match(r'^([A-Z]+)', district)
    return m.group(1) if m else district


def _find_fallback(district: str, rent_by_district: dict) -> Optional[tuple]:
    """
    Find a fallback median_rent for a district absent from rent_data.

    Strategy:
    1. Find all rent_data districts sharing the same letter prefix (e.g. 'SW'); use
       the one with the lowest median_rent as a conservative estimate.
    2. If no prefix match exists, use the overall median rent across all ONS districts.

    Returns (median_rent, description) or None if rent_by_district is empty.
    """
    if not rent_by_district:
        return None

    prefix = _letter_prefix(district)
    prefix_matches = {d: v for d, v in rent_by_district.items() if d.startswith(prefix)}
    if prefix_matches:
        best = min(prefix_matches, key=lambda d: prefix_matches[d])
        return prefix_matches[best], f"{best} (lowest {prefix}* rent)"

    overall_median = round(statistics.median(rent_by_district.values()))
    return overall_median, "overall ONS median rent"


def score_all_postcodes() -> list[dict]:
    from config import LONDON_POSTCODE_DISTRICTS

    client = _get_client()
    try:
        response = client.table("rent_data").select("district,median_rent").execute()
    except Exception as exc:
        raise RuntimeError(f"Could not reach Supabase database: {exc}") from exc

    rows = response.data
    if not rows:
        return []

    rent_by_district = {r["district"]: r["median_rent"] for r in rows}
    print(
        f"[rent] rent_data contains {len(rent_by_district)} districts: "
        f"{sorted(rent_by_district.keys())}"
    )

    full_rows = []
    for district in LONDON_POSTCODE_DISTRICTS:
        if district in rent_by_district:
            full_rows.append({"district": district, "median_rent": rent_by_district[district]})
        else:
            fallback = _find_fallback(district, rent_by_district)
            if fallback:
                median_rent, description = fallback
                print(f"[rent] {district} not in rent_data — using {description} (£{median_rent})")
                full_rows.append({"district": district, "median_rent": median_rent})
            else:
                print(f"[rent] WARNING: {district} not in rent_data and no fallback found — skipping.")

    if not full_rows:
        return []

    rents = [r["median_rent"] for r in full_rows]
    min_rent = min(rents)
    max_rent = max(rents)

    if max_rent == min_rent:
        return [
            {"district": r["district"], "median_rent": r["median_rent"], "score": 0.5}
            for r in full_rows
        ]

    return [
        {
            "district": r["district"],
            "median_rent": r["median_rent"],
            "score": round(1 - (r["median_rent"] - min_rent) / (max_rent - min_rent), 6),
        }
        for r in full_rows
    ]


def score_single_postcode(district: str) -> dict:
    client = _get_client()
    try:
        response = (
            client.table("rent_data")
            .select("district,median_rent")
            .eq("district", district)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError(f"Could not reach Supabase database: {exc}") from exc

    rows = response.data
    if rows:
        row = rows[0]
        return {"district": row["district"], "median_rent": row["median_rent"], "score": 0.5}

    # District not in rent_data — query the full table and try a prefix fallback.
    try:
        all_response = client.table("rent_data").select("district,median_rent").execute()
    except Exception as exc:
        raise RuntimeError(f"Could not reach Supabase database: {exc}") from exc

    rent_by_district = {r["district"]: r["median_rent"] for r in (all_response.data or [])}
    fallback = _find_fallback(district, rent_by_district)
    if fallback:
        median_rent, description = fallback
        print(f"[rent] {district} not in rent_data — using {description} (£{median_rent})")
        return {"district": district, "median_rent": median_rent, "score": 0.5}

    raise ValueError(f"District '{district}' not found in rent_data and no fallback available")


def score_all_from_cache(supabase=None) -> dict[str, float]:
    if supabase is None:
        supabase = _get_client()
    try:
        response = (
            supabase.table("cached_scores")
            .select("district,score,needs_retry")
            .eq("dimension", "rent")
            .execute()
        )
    except Exception as exc:
        raise RuntimeError(f"Could not read cached_scores for dimension 'rent': {exc}") from exc

    rows = response.data
    if not rows:
        raise RuntimeError("cached_scores returned 0 rows for dimension 'rent' — cache may not be populated")

    result = {}
    for row in rows:
        if row.get("needs_retry"):
            logging.warning("[rent] District %s has needs_retry=True — score is a placeholder", row["district"])
        result[row["district"]] = row["score"]
    return result
