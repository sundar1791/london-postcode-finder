import logging
import os
import sys
from typing import Optional

from supabase import create_client
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.distiller import should_distil


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

    # The distillation itself runs after the user's response is complete — see
    # agents.graph.run_pipeline and the API's background task.
    distillation_triggered = should_distil(new_count)
    if distillation_triggered:
        logging.info("knowledge_writer: query_count=%d — distillation due", new_count)

    return {
        "learnings_written": learnings_written,
        "query_count": new_count,
        "distillation_triggered": distillation_triggered,
    }
