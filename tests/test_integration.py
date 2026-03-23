import asyncio
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from agents.crime_scorer import score_all_postcodes as crime_scores
from agents.green_scorer import score_all_postcodes as green_scores
from agents.nightlife_scorer import score_all_postcodes as nightlife_scores
from agents.transport_scorer import score_all_postcodes as transport_scores
from agents.rent_scorer import score_all_postcodes as rent_scores

TEST_POSTCODES = ["E1", "SW1A", "SE22", "N1", "BR1"]


def _build_combined() -> dict:
    crime = {r["district"]: r["score"] for r in asyncio.run(crime_scores())}
    green = {r["district"]: r["score"] for r in asyncio.run(green_scores())}
    nightlife = {r["district"]: r["score"] for r in asyncio.run(nightlife_scores())}
    transport = {r["district"]: r["score"] for r in asyncio.run(transport_scores())}
    rent = {r["district"]: r["score"] for r in rent_scores()}

    return {
        pc: {
            "crime": crime[pc],
            "green": green[pc],
            "nightlife": nightlife[pc],
            "transport": transport[pc],
            "rent": rent[pc],
        }
        for pc in TEST_POSTCODES
    }


def _print_table(combined: dict) -> None:
    dims = ["crime", "green", "nightlife", "transport", "rent"]
    header = f"{'District':<10}" + "".join(f"{d:>12}" for d in dims)
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))
    for pc, scores in combined.items():
        row = f"{pc:<10}" + "".join(f"{scores[d]:>12.3f}" for d in dims)
        print(row)
    print("=" * len(header) + "\n")


@pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason=(
        "Hits live APIs (Overpass, TfL, Police, etc.) and can flake. "
        "Set RUN_INTEGRATION_TESTS=1 to run."
    ),
)
def test_integration_all_scorers():
    combined = _build_combined()
    _print_table(combined)

    # 1. All 5 postcodes present across all dimensions
    for pc in TEST_POSTCODES:
        assert pc in combined, f"{pc} missing from combined results"
        assert set(combined[pc].keys()) == {"crime", "green", "nightlife", "transport", "rent"}, (
            f"Missing dimensions for {pc}"
        )

    # 2. All scores in [0, 1]
    for pc, scores in combined.items():
        for dim, val in scores.items():
            assert 0.0 <= val <= 1.0, f"{pc} {dim} score out of range: {val}"

    # 3. E1 scores higher on nightlife than SE22
    assert combined["E1"]["nightlife"] > combined["SE22"]["nightlife"], (
        f"Expected E1 nightlife ({combined['E1']['nightlife']:.3f}) > "
        f"SE22 nightlife ({combined['SE22']['nightlife']:.3f})"
    )

    # 4. SE22 scores higher on green space than E1
    assert combined["SE22"]["green"] > combined["E1"]["green"], (
        f"Expected SE22 green ({combined['SE22']['green']:.3f}) > "
        f"E1 green ({combined['E1']['green']:.3f})"
    )

    # 5. SW1A scores lower on rent affordability than BR1 (SW1A is expensive)
    assert combined["SW1A"]["rent"] < combined["BR1"]["rent"], (
        f"Expected SW1A rent ({combined['SW1A']['rent']:.3f}) < "
        f"BR1 rent ({combined['BR1']['rent']:.3f})"
    )

    # 6. SW1A scores higher on transport than BR1
    assert combined["SW1A"]["transport"] > combined["BR1"]["transport"], (
        f"Expected SW1A transport ({combined['SW1A']['transport']:.3f}) > "
        f"BR1 transport ({combined['BR1']['transport']:.3f})"
    )

    # 7. No postcode has all 5 dimensions at 0.0 simultaneously
    for pc, scores in combined.items():
        assert not all(v == 0.0 for v in scores.values()), (
            f"{pc} has all scores at 0.0 — possible data pipeline failure"
        )
