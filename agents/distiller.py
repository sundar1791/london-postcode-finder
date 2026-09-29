import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DISTILL_EVERY_N, DISTILLER_EFFORT, DISTILLER_MAX_TOKENS, SONNET_MODEL
from tools.db import get_client

_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts", "distiller.md"
)


def should_distil(query_count: int, every_n: Optional[int] = None) -> bool:
    n = every_n if every_n is not None else DISTILL_EVERY_N
    return n > 0 and query_count > 0 and query_count % n == 0


def _format_learning(row: dict) -> str:
    parts = [
        (row.get(k) or "").strip()
        for k in ("context_intent", "methodology", "token_pattern", "outcome_summary")
    ]
    text = " ".join(p for p in parts if p)
    return f"- [{row.get('category', 'unknown')}] {text}"


def _build_user_message(brain: str, learnings: list, query_count: int) -> str:
    learnings_text = "\n".join(_format_learning(r) for r in learnings)
    return (
        f"Total queries processed: {query_count}\n\n"
        "## Current distilled brain\n"
        f"{brain or '(empty — this is the first distillation)'}\n\n"
        f"## New raw learnings ({len(learnings)})\n"
        f"{learnings_text}"
    )


def _call_claude(client, user_message: str) -> dict:
    with open(_PROMPT_PATH, "r") as f:
        system_prompt = f.read()
    response = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=DISTILLER_MAX_TOKENS,
        output_config={"effort": DISTILLER_EFFORT},
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    if response.stop_reason == "max_tokens":
        raise ValueError(f"distiller hit max_tokens={DISTILLER_MAX_TOKENS} before finishing")
    raw = "".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    )
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    return json.loads(cleaned, strict=False)


def distil(supabase=None, client=None, force: bool = False) -> dict:
    """Rewrite agent_config.distilled_brain from the learnings recorded since the
    last distillation. Never raises: on any failure the old brain is kept."""
    try:
        if supabase is None:
            supabase = get_client()

        config_rows = (
            supabase.table("agent_config")
            .select("distilled_brain,last_distilled,query_count")
            .eq("id", 1)
            .execute()
        ).data
        config = config_rows[0] if config_rows else {}
        previous_brain = (config.get("distilled_brain") or "").strip()
        last_distilled = config.get("last_distilled")
        query_count = config.get("query_count") or 0

        query = supabase.table("learnings").select("*").order("created_at")
        if last_distilled:
            query = query.gt("created_at", last_distilled)
        learnings = query.execute().data or []

        if not learnings and not force:
            logging.info("distiller: no new learnings since %s — skipping", last_distilled)
            return {"status": "skipped", "reason": "no new learnings", "query_count": query_count}

        if client is None:
            client = anthropic.Anthropic()
        parsed = _call_claude(client, _build_user_message(previous_brain, learnings, query_count))

        new_brain = (parsed.get("distilled_brain") or "").strip()
        change_summary = (parsed.get("change_summary") or "").strip()
        if not new_brain:
            raise ValueError("distiller returned an empty brain")

        # Watermark at the newest consumed learning so rows written mid-run are
        # picked up next time rather than skipped.
        watermark = learnings[-1]["created_at"] if learnings else datetime.now(timezone.utc).isoformat()
        supabase.table("agent_config").update(
            {"distilled_brain": new_brain, "last_distilled": watermark}
        ).eq("id", 1).execute()
        supabase.table("distillation_history").insert({
            "query_count": query_count,
            "learnings_consumed": len(learnings),
            "previous_brain": previous_brain or None,
            "new_brain": new_brain,
            "change_summary": change_summary,
        }).execute()

        logging.info(
            "distiller: brain rewritten from %d learnings at query_count=%d — %s",
            len(learnings), query_count, change_summary,
        )
        return {
            "status": "ok",
            "query_count": query_count,
            "learnings_consumed": len(learnings),
            "change_summary": change_summary,
        }
    except Exception as exc:
        logging.error("distiller: failed, keeping previous brain — %s", exc)
        return {"status": "failed", "error": str(exc)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(distil(force="--force" in sys.argv), indent=2))
