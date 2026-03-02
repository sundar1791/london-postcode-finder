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
    "Barking and Dagenham": ["RM8", "RM9", "RM10"],
    "Barnet": ["EN5", "N12", "NW7"],
    "Bexley": ["DA5", "DA6", "DA7"],
    "Brent": ["HA9", "NW10"],
    "Bromley": ["BR1", "BR2"],
    "Camden": ["NW1", "NW3"],
    "City of Westminster": ["SW1", "W1"],
    "Croydon": ["CR0", "CR2"],
    "Ealing": ["UB1", "W13"],
    "Enfield": ["EN1", "EN3"],
    "Greenwich": ["SE9", "SE18"],
    "Hackney": ["E8", "N16"],
    "Hammersmith and Fulham": ["W6", "W12"],
    "Haringey": ["N8", "N15"],
    "Harrow": ["HA1", "HA3"],
    "Havering": ["RM1", "RM11"],
    "Hillingdon": ["UB4", "UB8"],
    "Hounslow": ["TW3", "TW4"],
    "Islington": ["N1", "N7"],
    "Kensington and Chelsea": ["SW3", "W8"],
    "Kingston upon Thames": ["KT1", "KT2"],
    "Lambeth": ["SE24", "SW4"],
    "Lewisham": ["SE13", "SE23"],
    "Merton": ["SM4", "SW19"],
    "Newham": ["E6", "E13"],
    "Redbridge": ["IG1", "IG4"],
    "Richmond upon Thames": ["TW9", "TW10"],
    "Southwark": ["SE1", "SE15"],
    "Sutton": ["SM1", "SM2"],
    "Tower Hamlets": ["E1", "E14"],
    "Waltham Forest": ["E17", "E10"],
    "Wandsworth": ["SW11", "SW18"],
    "City of London": ["EC1", "EC2"],
    "Hackney (Inner)": ["E2", "E5"],
    "Haringey (North)": ["N13", "N22"],
    "Lewisham (South)": ["SE21", "SE22"],
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

    df = df[[c for c in [time_col, area_col, rent_col] if c]].copy()
    df[area_col] = df[area_col].astype(str).str.strip()
    df[rent_col] = pd.to_numeric(df[rent_col], errors="coerce")
    df = df.dropna(subset=[area_col, rent_col])

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
