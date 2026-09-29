"""Maps LangGraph stream chunks to the typed SSE events the frontend renders."""
from typing import Optional

_DIMENSION_FIELDS = {
    "crime": "crime_scores",
    "green": "green_scores",
    "nightlife": "nightlife_scores",
    "transport": "transport_scores",
    "rent": "rent_scores",
}
_SCORER_NODES = {f"{dim}_scorer": dim for dim in _DIMENSION_FIELDS}


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(float(value), 4)


class EventMapper:
    """Accumulates graph state from `updates` chunks and emits UI events."""

    def __init__(self, token_allocation: dict, context_text: str):
        self.state: dict = {"token_allocation": token_allocation, "context_text": context_text}

    def dimension_scores(self, district: str) -> dict:
        return {
            dim: _round((self.state.get(field) or {}).get(district))
            for dim, field in _DIMENSION_FIELDS.items()
        }

    def handle_custom(self, payload: dict) -> list:
        event = payload.get("event")
        if event not in ("research_started", "research_complete"):
            return []
        data = {k: v for k, v in payload.items() if k != "event"}
        return [(event, data)]

    def handle_update(self, node: str, update: Optional[dict]) -> list:
        update = update or {}
        for key, value in update.items():
            if key == "qualitative_insights":
                merged = dict(self.state.get(key) or {})
                merged.update(value or {})
                self.state[key] = merged
            elif key == "new_learnings":
                self.state[key] = list(self.state.get(key) or []) + list(value or [])
            else:
                self.state[key] = value

        handler = getattr(self, f"_on_{node}", None)
        if handler:
            return handler(update)
        if node in _SCORER_NODES:
            dim = _SCORER_NODES[node]
            scores = update.get(_DIMENSION_FIELDS[dim]) or {}
            return [("scorer_complete", {"dimension": dim, "districts": len(scores)})]
        return []

    def _on_knowledge_loader(self, update: dict) -> list:
        kb = update.get("knowledge_base") or ""
        return [("knowledge_loaded", {
            "chars": len(kb),
            "cold_start": (not kb) or kb.startswith("No accumulated knowledge yet"),
        })]

    def _on_orchestrator(self, update: dict) -> list:
        analysis = update.get("context_analysis") or {}
        spawn = analysis.get("spawn")
        events = [("orchestrator", {
            "type": analysis.get("type", "ignore"),
            "reasoning": analysis.get("reasoning", ""),
            "original_allocation": self.state.get("token_allocation"),
            "adjusted_allocation": update.get("adjusted_allocation"),
            "synthesiser_instruction": update.get("synthesiser_instruction", ""),
            "spawn": spawn,
        })]
        if spawn:
            events.append(("spawn_started", {
                "intent": spawn.get("intent"),
                "overpass_query": spawn.get("overpass_query"),
                "web_search_fallback": bool(spawn.get("web_search_fallback")),
            }))
        return events

    def _on_context_sub_agent(self, update: dict) -> list:
        spawn = (self.state.get("context_analysis") or {}).get("spawn")
        if not spawn:
            return []
        scores = update.get("spawn_scores") or {}
        meta = update.get("spawn_meta") or {}
        return [("spawn_complete", {
            "intent": spawn.get("intent"),
            "districts_matched": sum(1 for v in scores.values() if v > 0),
            "districts_total": len(scores),
            "from_cache": bool(meta.get("from_cache")),
            "timed_out": bool(meta.get("timed_out")),
            "failed": not scores,
        })]

    def _on_synthesiser_pass1(self, update: dict) -> list:
        weighted = update.get("weighted_scores") or {}
        top_10 = update.get("top_10_districts") or []
        top_5 = update.get("top_5_districts") or []
        spawn_scores = self.state.get("spawn_scores") or {}
        removed = []
        if spawn_scores:
            # Districts that out-scored the shortlist on weights alone but had
            # nothing matching the spawned criterion nearby.
            cutoff = weighted.get(top_5[-1], 0) if top_5 else 0
            removed = [
                {"district": d, "weighted_score": _round(weighted.get(d)), "spawn_score": _round(spawn_scores.get(d, 0))}
                for d in top_10
                if spawn_scores.get(d, 0) <= 0 and weighted.get(d, 0) >= cutoff
            ]
        return [
            ("scoring_complete", {
                "top_10": [
                    {"district": d, "weighted_score": _round(weighted.get(d)), "scores": self.dimension_scores(d)}
                    for d in top_10
                ],
                "districts_scored": len(weighted),
            }),
            ("shortlist", {
                "top_5": [{"district": d, "weighted_score": _round(weighted.get(d))} for d in top_5],
                "removed_by_spawn_filter": removed,
                "spawn_filter_applied": bool(spawn_scores),
            }),
        ]

    def _on_synthesiser_pass2(self, update: dict) -> list:
        weighted = self.state.get("weighted_scores") or {}
        spawn_scores = self.state.get("spawn_scores") or {}
        recs = []
        for rec in update.get("top_5") or []:
            district = rec.get("district", "")
            recs.append({
                **rec,
                "weighted_score": _round(weighted.get(district)),
                "scores": self.dimension_scores(district),
                "spawn_score": _round(spawn_scores.get(district)) if spawn_scores else None,
                "insights": (self.state.get("qualitative_insights") or {}).get(district, []),
            })
        self.state["recommendations"] = recs
        return [("synthesis_complete", {"recommendations": recs})]

    def _on_knowledge_writer(self, update: dict) -> list:
        result = update.get("knowledge_result") or {}
        return [("learning_saved", {
            "count": result.get("learnings_written", 0),
            "query_count": result.get("query_count"),
            "distillation_due": bool(result.get("distillation_triggered")),
            "learnings": self.state.get("new_learnings") or [],
        })]

    def result_summary(self) -> dict:
        return {
            "context_analysis": self.state.get("context_analysis"),
            "adjusted_allocation": self.state.get("adjusted_allocation"),
            "synthesiser_instruction": self.state.get("synthesiser_instruction"),
            "top_10_districts": self.state.get("top_10_districts"),
            "top_5_districts": self.state.get("top_5_districts"),
            "weighted_scores": self.state.get("weighted_scores"),
            "spawn_scores": self.state.get("spawn_scores"),
            "qualitative_insights": self.state.get("qualitative_insights"),
            "recommendations": self.state.get("recommendations"),
            "new_learnings": self.state.get("new_learnings"),
            "knowledge_base": self.state.get("knowledge_base"),
        }
