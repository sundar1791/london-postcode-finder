"""
tests/test_rent_data.py
-----------------------
Unit tests for the rent data loading logic.

These tests work entirely offline — no Supabase connection required.
They exercise load_borough_rents() and build_rows() directly.
"""

import sys
from pathlib import Path

import pytest

# Make sure the project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.load_rent_data import BOROUGH_TO_DISTRICTS, build_rows, load_borough_rents

XLSX_PATH = Path(__file__).parent.parent / "data" / "ons_rent.xlsx"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def borough_rents():
    """Load borough → rent mapping once for the whole module."""
    if not XLSX_PATH.exists():
        pytest.skip(f"XLSX not found at {XLSX_PATH}; skipping data-dependent tests.")
    return load_borough_rents(XLSX_PATH)


@pytest.fixture(scope="module")
def rows(borough_rents):
    return build_rows(borough_rents)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_at_least_30_district_rows(rows):
    """Expanding boroughs → districts should produce at least 30 rows."""
    assert len(rows) >= 30, (
        f"Expected ≥30 district rows, got {len(rows)}. "
        "Check that the XLSX Area Name values match BOROUGH_TO_DISTRICTS keys."
    )


def test_tower_hamlets_districts(rows):
    """Tower Hamlets must map to exactly E1 and E14."""
    th_districts = {r["district"] for r in rows if r["borough"] == "Tower Hamlets"}
    assert "E1" in th_districts, "E1 missing from Tower Hamlets rows"
    assert "E14" in th_districts, "E14 missing from Tower Hamlets rows"


def test_all_median_rents_above_500(rows):
    """Every median_rent value must be a positive number above £500."""
    for row in rows:
        rent = row["median_rent"]
        assert isinstance(rent, (int, float)), (
            f"median_rent for {row['district']} is not numeric: {rent!r}"
        )
        assert rent > 500, (
            f"median_rent for {row['district']} ({rent}) is not above £500. "
            "Check the Rental price column in the XLSX."
        )
