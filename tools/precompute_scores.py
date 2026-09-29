import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional, cast

import httpx

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

DISTRICTS = [
    "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10",
    "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8",
    "NW1", "NW2", "NW3", "NW4", "NW5", "NW6",
    "SE1", "SE5", "SE10", "SE15", "SE22",
    "SW1A", "SW3", "SW6", "SW11", "SW15",
    "W1", "W2", "W6", "W11", "W14", "WC1",
]

# Maps dimension name -> key in scorer result dict that holds the raw value
_RAW_KEY = {
    "crime": "raw_count",
    "green": "raw_count",
    "nightlife": "raw_count",
    "transport": "raw_score",
    "rent": "median_rent",
}

# Higher raw value means LOWER score for these dimensions (inverted normalisation)
_INVERTED_DIMENSIONS = {"crime", "rent"}


def _get_supabase():
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


def _upsert_results(supabase, dimension: str, results: list) -> tuple:
    raw_key = _RAW_KEY[dimension]
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for r in results:
        score = r["score"]
        raw_value = r.get(raw_key, 0)
        # Transport scorer has internal retry logic and score=0 is genuine for
        # outer London districts with no TfL stops (EN1, SM1, UB1, NW9, etc.)
        if dimension == "transport":
            needs_retry = False
        else:
            needs_retry = score == 0
        rows.append({
            "district": r["district"],
            "dimension": dimension,
            "raw_value": raw_value,
            "score": score,
            "needs_retry": needs_retry,
            "last_updated": now,
        })

    try:
        supabase.table("cached_scores").upsert(rows, on_conflict="district,dimension").execute()
    except Exception as exc:
        import supabase as _supabase_pkg
        print(f"[{dimension}] Upsert ERROR: {exc}")
        print(f"  supabase-py version: {_supabase_pkg.__version__}")
        raise

    success_count = sum(1 for r in rows if not r["needs_retry"])
    retry_count = sum(1 for r in rows if r["needs_retry"])
    return success_count, retry_count


async def _run_scorer(dimension: str) -> Optional[list]:
    print(f"[{dimension}] Running scorer...")
    try:
        if dimension == "crime":
            from scorers.crime_scorer import score_all_postcodes
            results = await score_all_postcodes()
        elif dimension == "green":
            from scorers.green_scorer import score_all_postcodes
            results = await score_all_postcodes()
        elif dimension == "nightlife":
            from scorers.nightlife_scorer import score_all_postcodes
            results = await score_all_postcodes()
        elif dimension == "transport":
            try:
                from scorers.transport_scorer import score_all_postcodes
            except ValueError as exc:
                print(f"[transport] Skipping: {exc}")
                return None
            results = await score_all_postcodes()
        elif dimension == "rent":
            from scorers.rent_scorer import score_all_postcodes
            results = score_all_postcodes()
        else:
            raise ValueError(f"Unknown dimension: {dimension}")
    except Exception as exc:
        print(f"[{dimension}] ERROR: {exc}")
        return None

    print(f"[{dimension}] Completed: {len(results)} districts scored.")
    return results


def _normalise_single(raw_value: float, existing_raw_values: list, dimension: str) -> float:
    """Compute a normalised score for raw_value using the range from existing_raw_values."""
    all_values = existing_raw_values + [raw_value]
    min_val = min(all_values)
    max_val = max(all_values)
    if max_val == min_val:
        return 0.5
    ratio = (raw_value - min_val) / (max_val - min_val)
    if dimension in _INVERTED_DIMENSIONS:
        return round(1.0 - ratio, 6)
    return round(ratio, 6)


async def _retry_single(dimension: str, district: str, supabase) -> Optional[dict]:
    """Fetch real API data for one district using the scorer's internal fetch function.

    Normalises the returned raw_value against the min/max of already-cached raw_values
    for the same dimension so the score is positioned correctly relative to other districts.

    Returns {"raw_value": <n>, "score": <normalised>} when the API returned data,
    or {"raw_value": 0, "score": 0.0} when the API returned nothing — so callers can
    use score > 0 to detect a genuine result.
    """
    from tools.postcode import get_postcode_coordinates

    try:
        coord = await get_postcode_coordinates(district)
        lat, lng = coord["lat"], coord["lng"]

        async with httpx.AsyncClient() as client:
            if dimension == "crime":
                from scorers.crime_scorer import _fetch_crime_count, _default_date
                result = await _fetch_crime_count(client, district, lat, lng, _default_date())
                raw_value = result["raw_count"]

            elif dimension == "green":
                from scorers.green_scorer import _fetch_green_count
                result = await _fetch_green_count(client, district, lat, lng)
                raw_value = result["raw_count"]

            elif dimension == "nightlife":
                from scorers.nightlife_scorer import _fetch_nightlife_count
                result = await _fetch_nightlife_count(client, district, lat, lng)
                raw_value = result["raw_count"]

            elif dimension == "transport":
                try:
                    from scorers.transport_scorer import _fetch_transport_score
                except ValueError as exc:
                    print(f"[transport] Skipping retry: {exc}")
                    return None
                result = await _fetch_transport_score(client, district, lat, lng)
                raw_value = result["raw_score"]

            elif dimension == "rent":
                from scorers.rent_scorer import score_single_postcode
                result = score_single_postcode(district)
                raw_value = result["median_rent"]

            else:
                raise ValueError(f"Unknown dimension: {dimension}")

    except Exception as exc:
        print(f"[{dimension}/{district}] Retry ERROR: {exc}")
        return None

    if raw_value == 0:
        return {"raw_value": 0, "score": 0.0}

    # Fetch existing raw_values for this dimension (excluding the district being retried)
    # to compute a normalised score that slots in correctly alongside the rest.
    existing_resp = (
        supabase.table("cached_scores")
        .select("raw_value")
        .eq("dimension", dimension)
        .neq("district", district)
        .execute()
    )
    existing_raw_values = [
        r["raw_value"] for r in (existing_resp.data or []) if r["raw_value"] is not None
    ]

    score = _normalise_single(raw_value, existing_raw_values, dimension)
    return {"raw_value": raw_value, "score": score}


def apply_manual_overrides(supabase) -> None:
    """
    Apply deterministic fallback scores for districts with known permanent data gaps.

    Runs after the retry pass. Each override derives its score from existing scored
    rows in cached_scores so the values are anchored to the real distribution.
    """
    now = datetime.now(timezone.utc).isoformat()
    overrides_applied = 0

    # --- rent: W1A, W2, EC1A, SW1A have raw_value=3181 but score=0 ---
    # Compute the normalised score using the min/max of all other rent raw_values.
    RENT_FALLBACK_RAW = 3181.0
    RENT_FALLBACK_DISTRICTS = ["W1A", "W2", "EC1A", "SW1A"]

    print("\n[overrides] Computing rent correction for fallback districts...")
    rent_resp = (
        supabase.table("cached_scores")
        .select("raw_value")
        .eq("dimension", "rent")
        .gt("score", 0)
        .execute()
    )
    rent_raw_values = [
        r["raw_value"] for r in (rent_resp.data or []) if r["raw_value"] is not None
    ]

    if rent_raw_values:
        min_rent = min(rent_raw_values)
        max_rent = max(rent_raw_values)
        if max_rent > min_rent:
            rent_score = round(max(0.0, min(1.0, 1 - (RENT_FALLBACK_RAW - min_rent) / (max_rent - min_rent))), 6)
        else:
            rent_score = 0.5
        for district in RENT_FALLBACK_DISTRICTS:
            supabase.table("cached_scores").update({
                "score": rent_score,
                "needs_retry": False,
                "last_updated": now,
            }).eq("district", district).eq("dimension", "rent").execute()
            print(
                f"[override] rent/{district} — score={rent_score} "
                f"(raw={RENT_FALLBACK_RAW}, min={min_rent}, max={max_rent})"
            )
            overrides_applied += 1
    else:
        print("[override] rent — no existing scored rows found, skipping rent overrides.")

    # --- crime/SW1A — mean score of SW* districts already scored ---
    print("\n[overrides] Computing crime/SW1A from neighbouring SW districts...")
    sw_crime_resp = (
        supabase.table("cached_scores")
        .select("district,score")
        .eq("dimension", "crime")
        .like("district", "SW%")
        .gt("score", 0)
        .execute()
    )
    sw_crime_rows = sw_crime_resp.data or []
    sw_scores = [r["score"] for r in sw_crime_rows]

    if sw_scores:
        sw_mean = round(sum(sw_scores) / len(sw_scores), 6)
        neighbours = [r["district"] for r in sw_crime_rows]
        supabase.table("cached_scores").update({
            "score": sw_mean,
            "needs_retry": False,
            "last_updated": now,
        }).eq("district", "SW1A").eq("dimension", "crime").execute()
        print(
            f"[override] crime/SW1A — score={sw_mean} "
            f"(mean of {neighbours})"
        )
        overrides_applied += 1
    else:
        print("[override] crime/SW1A — no scored SW* crime rows found, skipping.")

    # --- green/CR0 — mean score of all scored green districts ---
    print("\n[overrides] Computing green/CR0 from overall green distribution...")
    green_resp = (
        supabase.table("cached_scores")
        .select("score")
        .eq("dimension", "green")
        .gt("score", 0)
        .execute()
    )
    green_scores = [r["score"] for r in (green_resp.data or [])]

    if green_scores:
        green_mean = round(sum(green_scores) / len(green_scores), 6)
        supabase.table("cached_scores").update({
            "score": green_mean,
            "needs_retry": False,
            "last_updated": now,
        }).eq("district", "CR0").eq("dimension", "green").execute()
        print(
            f"[override] green/CR0 — score={green_mean} "
            f"(mean of {len(green_scores)} scored districts)"
        )
        overrides_applied += 1
    else:
        print("[override] green/CR0 — no scored green rows found, skipping.")

    print(f"\nManual overrides complete: {overrides_applied} applied.")


async def main():
    supabase = _get_supabase()
    dimensions = ["crime", "green", "nightlife", "transport", "rent"]

    total_success = 0
    total_retry = 0

    for dimension in dimensions:
        results = await _run_scorer(dimension)
        if results is None:
            print(f"[{dimension}] Skipped — scorer unavailable or failed.")
            continue

        if dimension == "rent" and len(results) == 0:
            print(
                "[rent] WARNING: rent_data table appears empty — is local Supabase running? "
                "Skipping upsert."
            )
            continue

        success, retry = _upsert_results(supabase, dimension, results)
        total_success += success
        total_retry += retry
        print(f"[{dimension}] Upserted {len(results)} rows — {success} ok, {retry} flagged for retry.")

    print(f"\nMain pass complete: {total_success} succeeded, {total_retry} flagged for retry.\n")

    if total_retry == 0:
        print("No retries needed.")
    else:
        print("Querying cached_scores for rows with needs_retry=true...")
        response = (
            supabase.table("cached_scores")
            .select("district,dimension")
            .eq("needs_retry", True)
            .execute()
        )
        retry_rows = cast(list[dict[str, Any]], response.data or [])
        print(f"Found {len(retry_rows)} rows to retry.\n")

        retry_success = 0
        retry_failed = 0

        for i, row in enumerate(retry_rows):
            district: str = row["district"]
            dimension: str = row["dimension"]
            print(f"Retrying [{i + 1}/{len(retry_rows)}] {dimension}/{district}...")

            result = await _retry_single(dimension, district, supabase)

            if result is None:
                print(f"  -> Failed (no result returned).")
                retry_failed += 1
            elif result["score"] > 0:
                supabase.table("cached_scores").update({
                    "raw_value": result["raw_value"],
                    "score": result["score"],
                    "needs_retry": False,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }).eq("district", district).eq("dimension", dimension).execute()
                print(f"  -> Success: score={result['score']}, raw_value={result['raw_value']}.")
                retry_success += 1
            else:
                print(f"  -> Still score=0 after retry.")
                retry_failed += 1

            if i < len(retry_rows) - 1:
                print(f"  Waiting 60s before next retry...")
                await asyncio.sleep(60)

        print(f"\nRetry pass complete: {retry_success} resolved, {retry_failed} still failing.")

    print("\nApplying manual overrides for known permanent failures...")
    apply_manual_overrides(supabase)


if __name__ == "__main__":
    asyncio.run(main())
