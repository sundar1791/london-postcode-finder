import logging
import os
import sys
from typing import Optional

from supabase import create_client
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url:
        raise ValueError("SUPABASE_URL environment variable is not set")
    if not key:
        raise ValueError("SUPABASE_KEY environment variable is not set")
    try:
        return create_client(url, key)
    except Exception as exc:
        raise RuntimeError(f"Could not connect to Supabase: {exc}") from exc


def _trigger_distillation(query_count: int) -> None:
    # TODO US-039/040: replace with the real distillation engine (Milestone 7)
    logging.info(
        "Distillation would trigger here at query_count=%d (Milestone 7 — not yet implemented)",
        query_count,
    )


def write_knowledge(new_learnings: list, supabase=None) -> dict:
    if supabase is None:
        supabase = _get_client()

    learnings_written = 0
    if new_learnings:
        rows = [
            {
                "category": entry.get("category"),
                "context_intent": None,
                "methodology": None,
                "token_pattern": None,
                "outcome_summary": entry.get("content"),
            }
            for entry in new_learnings
        ]
        try:
            supabase.table("learnings").insert(rows).execute()
        except Exception as exc:
            raise RuntimeError(f"Could not write learnings: {exc}") from exc
        learnings_written = len(rows)

    try:
        config_response = (
            supabase.table("agent_config")
            .select("query_count")
            .eq("id", 1)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError(f"Could not read agent_config: {exc}") from exc

    config_rows = config_response.data
    current_count: Optional[int] = config_rows[0].get("query_count") if config_rows else None
    new_count = (current_count or 0) + 1

    try:
        (
            supabase.table("agent_config")
            .update({"query_count": new_count})
            .eq("id", 1)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError(f"Could not update agent_config: {exc}") from exc

    distillation_triggered = new_count > 0 and new_count % 50 == 0
    if distillation_triggered:
        _trigger_distillation(new_count)

    return {
        "learnings_written": learnings_written,
        "query_count": new_count,
        "distillation_triggered": distillation_triggered,
    }
