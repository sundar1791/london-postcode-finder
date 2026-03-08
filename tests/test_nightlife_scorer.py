import pytest

from agents.nightlife_scorer import score_all_postcodes, score_single_postcode


@pytest.mark.asyncio
async def test_score_all_postcodes_returns_40_dicts():
    results = await score_all_postcodes()
    assert len(results) == 40


@pytest.mark.asyncio
async def test_all_scores_between_0_and_1():
    results = await score_all_postcodes()
    for entry in results:
        assert 0.0 <= entry["score"] <= 1.0, (
            f"Score out of range for {entry['district']}: {entry['score']}"
        )


@pytest.mark.asyncio
async def test_score_single_postcode_e1_shape():
    result = await score_single_postcode("E1")
    assert isinstance(result, dict)
    assert set(result.keys()) == {"district", "raw_count", "score"}
    assert result["district"] == "E1"
    assert isinstance(result["raw_count"], int)
    assert isinstance(result["score"], float)
