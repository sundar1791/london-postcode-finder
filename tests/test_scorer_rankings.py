import os

import pytest
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(override=True)

RANKING_PAIRS = {
    "crime": [
        ("N21", "WC1A"),
        ("BR3", "SE1"),
        ("TW1", "E1"),
    ],
    "green": [
        ("N4", "EC1A"),
        ("N4", "WC1A"),
        ("E11", "EN1"),
    ],
    "nightlife": [
        ("SW1A", "NW9"),
        ("WC1A", "CR0"),
        ("EC1A", "EN1"),
    ],
    "transport": [
        ("W6", "EN1"),
        ("SE1", "UB1"),
        ("E1", "NW9"),
    ],
    "rent": [
        ("DA1", "W1A"),
        ("CR0", "SW1A"),
        ("SM1", "EC1A"),
    ],
}


def get_score(supabase, district: str, dimension: str) -> float:
    response = (
        supabase.table("cached_scores")
        .select("score")
        .eq("district", district)
        .eq("dimension", dimension)
        .execute()
    )
    if not response.data:
        raise AssertionError(
            f"No cached_scores row for district={district}, dimension={dimension} "
            "— is the cache populated?"
        )
    return response.data[0]["score"]


@pytest.fixture(scope="session")
def supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url:
        raise ValueError("SUPABASE_URL environment variable is not set")
    if not key:
        raise ValueError("SUPABASE_KEY environment variable is not set")
    return create_client(url, key)


def _ranking_pair_cases():
    cases = []
    for dimension, pairs in RANKING_PAIRS.items():
        for higher, lower in pairs:
            cases.append(
                pytest.param(
                    dimension,
                    higher,
                    lower,
                    id=f"{dimension}-{higher}-vs-{lower}",
                )
            )
    return cases


@pytest.mark.parametrize("dimension,higher,lower", _ranking_pair_cases())
def test_ranking_pair(supabase_client, dimension: str, higher: str, lower: str):
    score_a = get_score(supabase_client, higher, dimension)
    score_b = get_score(supabase_client, lower, dimension)
    assert score_a > score_b, (
        f"Expected {higher} > {lower} on {dimension}, "
        f"got {higher}={score_a}, {lower}={score_b}"
    )
