import httpx
import pytest

from agents.context_sub_agent import _build_combined_query, _fetch_all_counts_combined
from tools.spawn_cache import cache_key, get_cached_scores, put_cached_scores
from tests.fakes import FakeSupabase

COORDS = [
    {"outcode": "E1", "lat": 51.51, "lng": -0.06},
    {"outcode": "KT1", "lat": 51.40, "lng": -0.30},
]


def test_combined_query_has_one_count_per_district():
    q = _build_combined_query("amenity", "kindergarten", COORDS)
    assert q.count("out count;") == 2
    assert "around:500,51.51,-0.06" in q


@pytest.mark.asyncio
async def test_combined_counts_map_to_districts_in_order():
    def handler(request):
        assert request.headers["user-agent"].startswith("london-postcode-finder")
        return httpx.Response(200, json={"elements": [
            {"type": "count", "tags": {"total": "7"}},
            {"type": "count", "tags": {"total": "0"}},
        ]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await _fetch_all_counts_combined(client, COORDS, "amenity", "kindergarten")
    assert result == [{"district": "E1", "raw_count": 7}, {"district": "KT1", "raw_count": 0}]


@pytest.mark.asyncio
async def test_combined_count_mismatch_returns_none():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"elements": [{"tags": {"total": "1"}}]}))
    async with httpx.AsyncClient(transport=transport) as client:
        assert await _fetch_all_counts_combined(client, COORDS, "amenity", "kindergarten") is None


def test_cache_key():
    assert cache_key({"overpass_query": "Amenity=Kindergarten "}) == "amenity=kindergarten"
    assert cache_key({"intent": "Tamil community", "web_search_fallback": True}) == "web_search:tamil community"


def test_spawn_cache_round_trip():
    db = FakeSupabase({"spawn_cache": []})
    assert get_cached_scores("amenity=school", supabase=db) is None
    put_cached_scores("amenity=school", {"E1": 1.0, "KT1": 0.0}, supabase=db)
    assert get_cached_scores("amenity=school", supabase=db) == {"E1": 1.0, "KT1": 0.0}


def test_spawn_cache_ignores_stale_entries():
    db = FakeSupabase({"spawn_cache": [
        {"overpass_query": "amenity=school", "scores": {"E1": 1.0}, "created_at": "2020-01-01T00:00:00+00:00"},
    ]})
    assert get_cached_scores("amenity=school", supabase=db) is None
