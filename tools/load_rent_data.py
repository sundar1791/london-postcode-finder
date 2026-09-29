"""
load_rent_data.py
-----------------
Reads the ONS Price Index of Private Rents XLSX (Table 1), maps borough names
to London postcode districts, and upserts the results into the Supabase
rent_data table.

Usage:
    python tools/load_rent_data.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# ---------------------------------------------------------------------------
# Borough → district mapping
# ---------------------------------------------------------------------------

BOROUGH_TO_DISTRICTS: dict[str, list[str]] = {
    "Bromley": ["BR1", "BR3"],
    "Croydon": ["CR0"],
    "Bexley": ["DA1"],
    "Tower Hamlets": ["E1", "E2"],
    "Waltham Forest": ["E11", "E17"],
    "Westminster": ["SW1A", "W1A", "W2", "EC1A"],
    "Enfield": ["EN1", "N13", "N21"],
    "Harrow": ["HA1"],
    "Redbridge": ["IG1"],
    "Kingston upon Thames": ["KT1"],
    "Islington": ["N1"],
    "Haringey": ["N4"],
    "Camden": ["NW1", "NW3", "NW6", "WC1A"],
    "Brent": ["NW9"],
    "Havering": ["RM1"],
    "Southwark": ["SE1", "SE5"],
    "Greenwich": ["SE18", "SE9"],
    "Sutton": ["SM1"],
    "Lambeth": ["SW16", "SW4", "SW8"],
    "Merton": ["SW19"],
    "Richmond upon Thames": ["TW1"],
    "Ealing": ["UB1", "W13", "W5"],
    "Hammersmith and Fulham": ["W6"],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

XLSX_PATH = Path(__file__).parent.parent / "data" / "ons_rent.xlsx"


def load_borough_rents(xlsx_path: Path = XLSX_PATH) -> dict[str, float]:
    """Return {borough_name: median_rent} for all rows in Table 1."""
    df = pd.read_excel(xlsx_path, sheet_name="Table 1", engine="openpyxl")

    # Normalise column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]

    # Normalise to a canonical set regardless of title-case variations
    col_map = {c.lower(): c for c in df.columns}
    area_col = col_map.get("area name")
    rent_col = col_map.get("rental price")
    time_col = col_map.get("time period")

    missing = [label for label, col in [("Area name", area_col), ("Rental price", rent_col)] if col is None]
    if missing:
        raise ValueError(f"Expected columns not found in XLSX: {missing}. Got: {list(df.columns)}")

    assert area_col is not None
    assert rent_col is not None

    df = df[[c for c in [time_col, area_col, rent_col] if c]].copy()
    df[area_col] = df[area_col].astype(str).str.strip()  # pyright: ignore[reportAttributeAccessIssue]
    df[rent_col] = pd.to_numeric(df[rent_col], errors="coerce")
    df = df.dropna(subset=[area_col, rent_col])  # pyright: ignore[reportCallIssue]

    # The XLSX is a monthly time-series; take the most recent row per area
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        df = df.sort_values(time_col)

    latest = df.groupby(area_col)[rent_col].last()
    return latest.to_dict()


def build_rows(borough_rents: dict[str, float]) -> list[dict]:
    """Expand borough → districts into one row per district."""
    rows = []
    for borough, districts in BOROUGH_TO_DISTRICTS.items():
        if borough not in borough_rents:
            continue
        rent = float(borough_rents[borough])
        for district in districts:
            rows.append({"borough": borough, "district": district, "median_rent": rent})
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        sys.exit("Error: SUPABASE_URL and SUPABASE_KEY must be set in the environment or .env file.")

    print(f"Reading {XLSX_PATH} …")
    borough_rents = load_borough_rents()

    rows = build_rows(borough_rents)
    matched_boroughs = len({r["borough"] for r in rows})

    if not rows:
        sys.exit("No matching boroughs found in the XLSX. Check the Area Name column.")

    print(f"Matched {matched_boroughs} borough(s) → {len(rows)} district row(s).")

    client = create_client(url, key)
    client.table("rent_data").delete().neq("id", 0).execute()
    result = (
        client.table("rent_data")
        .upsert(rows, on_conflict="district")
        .execute()
    )

    inserted = len(result.data) if result.data else 0
    print(f"Upserted {inserted} row(s) into rent_data.")
    print("Done.")


if __name__ == "__main__":
    main()
