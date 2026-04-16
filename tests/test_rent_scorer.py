from scorers.rent_scorer import score_all_postcodes, score_single_postcode


def test_score_all_postcodes_returns_at_least_30_dicts():
    results = score_all_postcodes()
    assert len(results) >= 30


def test_all_scores_between_0_and_1():
    results = score_all_postcodes()
    for entry in results:
        assert 0.0 <= entry["score"] <= 1.0, (
            f"Score out of range for {entry['district']}: {entry['score']}"
        )


def test_score_single_postcode_e1_shape():
    result = score_single_postcode("E1")
    assert isinstance(result, dict)
    assert set(result.keys()) == {"district", "median_rent", "score"}
    assert result["district"] == "E1"
    assert isinstance(result["median_rent"], float)
    assert result["score"] == 0.5


def test_higher_rent_districts_score_lower():
    results = score_all_postcodes()
    by_district = {r["district"]: r for r in results}

    expensive = ["SW1A", "W1A"]
    affordable = ["E17", "RM1"]

    present_expensive = [d for d in expensive if d in by_district]
    present_affordable = [d for d in affordable if d in by_district]

    if not present_expensive or not present_affordable:
        return

    avg_expensive = sum(by_district[d]["score"] for d in present_expensive) / len(present_expensive)
    avg_affordable = sum(by_district[d]["score"] for d in present_affordable) / len(present_affordable)

    assert avg_expensive < avg_affordable, (
        f"Expected expensive districts to score lower: "
        f"{present_expensive} avg={avg_expensive:.3f} vs "
        f"{present_affordable} avg={avg_affordable:.3f}"
    )
