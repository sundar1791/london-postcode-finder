import pytest
import pytest_asyncio

from tools.postcode import get_postcode_coordinates


@pytest.mark.asyncio
async def test_e1_returns_london_coordinates():
    result = await get_postcode_coordinates("E1")
    assert result["outcode"] == "E1"
    assert 51.0 < result["lat"] < 52.0
    assert isinstance(result["lng"], float)


@pytest.mark.asyncio
async def test_invalid_postcode_raises_value_error():
    with pytest.raises(ValueError, match="ZZ99"):
        await get_postcode_coordinates("ZZ99")
