from config import LONDON_POSTCODE_DISTRICTS


def test_postcode_district_count():
    assert len(LONDON_POSTCODE_DISTRICTS) >= 30
