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


def _format_learning(learning: dict) -> str:
    context_intent = (learning.get("context_intent") or "").strip()
    methodology = (learning.get("methodology") or "").strip()
    outcome_summary = (learning.get("outcome_summary") or "").strip()
    parts = [p for p in (context_intent, methodology, outcome_summary) if p]
    return " — ".join(parts)


def load_knowledge(supabase=None) -> str:
    if supabase is None:
        supabase = _get_client()

    try:
        config_response = (
            supabase.table("agent_config")
            .select("distilled_brain")
            .eq("id", 1)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError(f"Could not read agent_config: {exc}") from exc

    config_rows = config_response.data
    distilled_brain: Optional[str] = config_rows[0].get("distilled_brain") if config_rows else None
    distilled_brain = (distilled_brain or "").strip()

    try:
        learnings_response = (
            supabase.table("learnings")
            .select("context_intent,methodology,outcome_summary,created_at")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
    except Exception as exc:
        raise RuntimeError(f"Could not read learnings: {exc}") from exc

    learnings = learnings_response.data or []

    if not distilled_brain and not learnings:
        return "No accumulated knowledge yet — this is an early query."

    brain_section = distilled_brain if distilled_brain else "No distilled knowledge yet."

    if learnings:
        learnings_section = "\n".join(f"- {_format_learning(l)}" for l in learnings)
    else:
        learnings_section = "No recent learnings yet."

    return (
        "## Distilled Knowledge\n"
        f"{brain_section}\n\n"
        "## Recent Learnings\n"
        f"{learnings_section}"
    )
