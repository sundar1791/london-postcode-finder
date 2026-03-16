import os

from supabase import create_client
from dotenv import load_dotenv
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


def score_all_postcodes() -> list[dict]:
    client = _get_client()
    try:
        response = client.table("rent_data").select("district,median_rent").execute()
    except Exception as exc:
        raise RuntimeError(f"Could not reach Supabase database: {exc}") from exc

    rows = response.data
    if not rows:
        return []

    rents = [r["median_rent"] for r in rows]
    min_rent = min(rents)
    max_rent = max(rents)

    if max_rent == min_rent:
        return [
            {"district": r["district"], "median_rent": r["median_rent"], "score": 0.5}
            for r in rows
        ]

    return [
        {
            "district": r["district"],
            "median_rent": r["median_rent"],
            "score": round(1 - (r["median_rent"] - min_rent) / (max_rent - min_rent), 6),
        }
        for r in rows
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
    if not rows:
        raise ValueError(f"District '{district}' not found in rent_data table")

    row = rows[0]
    return {"district": row["district"], "median_rent": row["median_rent"], "score": 0.5}
