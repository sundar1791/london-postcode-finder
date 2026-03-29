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


def _included_test_postcodes(
    crime: dict,
    green: dict,
    nightlife: dict,
    transport: dict,
    rent: dict,
) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """Return postcodes from TEST_POSTCODES that exist in every scorer map, plus skip reasons."""
    maps = {
        "crime": crime,
        "green": green,
        "nightlife": nightlife,
        "transport": transport,
        "rent": rent,
    }
    included: list[str] = []
    missing_report: list[tuple[str, list[str]]] = []
    for pc in TEST_POSTCODES:
        missing_dims = [name for name, m in maps.items() if pc not in m]
        if not missing_dims:
            included.append(pc)
        else:
            missing_report.append((pc, missing_dims))
    return included, missing_report


def _build_combined() -> tuple[dict, list[str], list[tuple[str, list[str]]]]:
    crime = {r["district"]: r["score"] for r in asyncio.run(crime_scores())}
    green = {r["district"]: r["score"] for r in asyncio.run(green_scores())}
    nightlife = {r["district"]: r["score"] for r in asyncio.run(nightlife_scores())}
    transport = {r["district"]: r["score"] for r in asyncio.run(transport_scores())}
    rent = {r["district"]: r["score"] for r in rent_scores()}

    included, missing_report = _included_test_postcodes(
        crime, green, nightlife, transport, rent
    )

    combined = {
        pc: {
            "crime": crime[pc],
            "green": green[pc],
            "nightlife": nightlife[pc],
            "transport": transport[pc],
            "rent": rent[pc],
        }
        for pc in included
    }
    return combined, included, missing_report


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
    combined, included, missing_report = _build_combined()

    for pc, dims in missing_report:
        print(
            f"Warning: skipping {pc} — not in all scorer outputs "
            f"(missing: {', '.join(dims)})"
        )

    assert included, (
        "No TEST_POSTCODES appear in every scorer; cannot run integration checks. "
        f"Missing breakdown: {missing_report}"
    )

    _print_table(combined)

    # 1. Included postcodes have all five dimensions
    for pc in included:
        assert pc in combined, f"{pc} missing from combined results"
        assert set(combined[pc].keys()) == {"crime", "green", "nightlife", "transport", "rent"}, (
            f"Missing dimensions for {pc}"
        )

    # 2. All scores in [0, 1]
    for pc, scores in combined.items():
        for dim, val in scores.items():
            assert 0.0 <= val <= 1.0, f"{pc} {dim} score out of range: {val}"

    # 3. E1 scores higher on nightlife than SE22 (needs both in DB + APIs)
    if "E1" in included and "SE22" in included:
        assert combined["E1"]["nightlife"] > combined["SE22"]["nightlife"], (
            f"Expected E1 nightlife ({combined['E1']['nightlife']:.3f}) > "
            f"SE22 nightlife ({combined['SE22']['nightlife']:.3f})"
        )
    else:
        print("Skipping E1 vs SE22 nightlife check — one or both not in combined set.")

    # 4. SE22 scores higher on green space than E1
    if "E1" in included and "SE22" in included:
        assert combined["SE22"]["green"] > combined["E1"]["green"], (
            f"Expected SE22 green ({combined['SE22']['green']:.3f}) > "
            f"E1 green ({combined['E1']['green']:.3f})"
        )
    else:
        print("Skipping SE22 vs E1 green check — one or both not in combined set.")

    # 5. SW1A scores lower on rent affordability than BR1 (SW1A is expensive)
    if "SW1A" in included and "BR1" in included:
        assert combined["SW1A"]["rent"] < combined["BR1"]["rent"], (
            f"Expected SW1A rent ({combined['SW1A']['rent']:.3f}) < "
            f"BR1 rent ({combined['BR1']['rent']:.3f})"
        )
    else:
        print("Skipping SW1A vs BR1 rent check — one or both not in combined set.")

    # 6. SW1A scores higher on transport than BR1
    if "SW1A" in included and "BR1" in included:
        assert combined["SW1A"]["transport"] > combined["BR1"]["transport"], (
            f"Expected SW1A transport ({combined['SW1A']['transport']:.3f}) > "
            f"BR1 transport ({combined['BR1']['transport']:.3f})"
        )
    else:
        print("Skipping SW1A vs BR1 transport check — one or both not in combined set.")

    # 7. No postcode has all 5 dimensions at 0.0 simultaneously
    for pc, scores in combined.items():
        assert not all(v == 0.0 for v in scores.values()), (
            f"{pc} has all scores at 0.0 — possible data pipeline failure"
        )
