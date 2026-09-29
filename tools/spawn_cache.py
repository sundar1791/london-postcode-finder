import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import SPAWN_CACHE_MAX_AGE_DAYS
from tools.db import get_client


def cache_key(spawn: dict) -> str:
    if spawn.get("web_search_fallback") or not spawn.get("overpass_query"):
        return "web_search:" + (spawn.get("intent") or "").strip().lower()
    return spawn["overpass_query"].strip().lower()


def get_cached_scores(key: str, supabase=None) -> Optional[dict]:
    try:
        supabase = supabase or get_client()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=SPAWN_CACHE_MAX_AGE_DAYS)).isoformat()
        rows = (
            supabase.table("spawn_cache")
            .select("scores,created_at")
            .eq("overpass_query", key)
            .gte("created_at", cutoff)
            .execute()
        ).data
    except Exception as exc:
        logging.warning("spawn_cache: read failed for %s — %s", key, exc)
        return None
    if not rows:
        return None
    return {k: float(v) for k, v in rows[0]["scores"].items()}


def put_cached_scores(key: str, scores: dict, supabase=None) -> None:
    try:
        supabase = supabase or get_client()
        supabase.table("spawn_cache").upsert({
            "overpass_query": key,
            "scores": scores,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as exc:
        logging.warning("spawn_cache: write failed for %s — %s", key, exc)
