import asyncio
import json
import logging
import sys
import os
import re

import anthropic
from anthropic.types import TextBlock
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from agents.state import LondonSearchState, make_initial_state


async def knowledge_loader_node(state: LondonSearchState) -> dict:
    print("knowledge_loader_node")
    return {}


_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


async def orchestrator_node(state: LondonSearchState) -> dict:
    with open(os.path.join(_PROMPTS_DIR, "orchestrator.md"), "r") as f:
        system_prompt = f.read()

    user_message = (
        f"Token allocation: {json.dumps(state['token_allocation'])}\n"
        f"Context: {state['context_text']}"
    )

    def _call_claude() -> str:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        )

    try:
        raw = ""
        for _attempt in range(1, 4):
            try:
                raw = await asyncio.get_event_loop().run_in_executor(None, _call_claude)
                break
            except anthropic.RateLimitError:
                if _attempt == 3:
                    raise
                logging.warning("orchestrator_node: rate limit hit — waiting 15s before retry %d/3", _attempt)
                await asyncio.sleep(15)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        parsed = json.loads(cleaned, strict=False)

        if not parsed.get("valid", True):
            raise ValueError(parsed.get("error", "Orchestrator returned invalid=false"))

        has_spawn = bool(parsed.get("spawn"))
        allocation_changed = parsed.get("adjusted_allocation") != state["token_allocation"]
        if has_spawn and allocation_changed:
            classification = "combination"
        elif has_spawn:
            classification = "spawn"
        elif allocation_changed:
            classification = "adjust"
        else:
            classification = "ignore"

        print(f"orchestrator_node: type={classification} reasoning={parsed.get('reasoning', '')}")

        return {
            "adjusted_allocation": parsed["adjusted_allocation"],
            "context_analysis": {
                "spawn": parsed.get("spawn"),
                "reasoning": parsed.get("reasoning", ""),
                "type": classification,
            },
            "synthesiser_instruction": parsed.get("synthesiser_instruction", ""),
        }

    except ValueError:
        raise
    except Exception as exc:
        logging.error("orchestrator_node: Claude call failed — %s", exc)
        return {
            "adjusted_allocation": state["token_allocation"],
            "context_analysis": {},
            "synthesiser_instruction": "",
        }


async def context_sub_agent_node(state: LondonSearchState) -> dict:
    from agents.context_sub_agent import run_context_sub_agent
    spawn = (state.get("context_analysis") or {}).get("spawn")
    if not spawn:
        logging.info("context_sub_agent_node: no spawn detected — skipping")
        return {"spawn_scores": {}}
    logging.info("context_sub_agent_node: spawn detected — running context sub-agent")
    try:
        result = await run_context_sub_agent(spawn)
        logging.info("context_sub_agent_node: completed — %d districts scored", len(result))
        return {"spawn_scores": result}
    except Exception as exc:
        logging.error("context_sub_agent_node: failed — %s", exc)
        return {"spawn_scores": {}}


async def crime_scorer_node(state: LondonSearchState) -> dict:
    from scorers.crime_scorer import score_all_from_cache
    logging.info("crime_scorer_node: loading scores from cache")
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, score_all_from_cache)
        logging.info("crime_scorer_node: loaded %d districts", len(result))
        return {"crime_scores": result}
    except Exception as exc:
        logging.error("crime_scorer_node: cache read failed — %s", exc)
        return {"crime_scores": {}}


async def green_scorer_node(state: LondonSearchState) -> dict:
    from scorers.green_scorer import score_all_from_cache
    logging.info("green_scorer_node: loading scores from cache")
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, score_all_from_cache)
        logging.info("green_scorer_node: loaded %d districts", len(result))
        return {"green_scores": result}
    except Exception as exc:
        logging.error("green_scorer_node: cache read failed — %s", exc)
        return {"green_scores": {}}


async def nightlife_scorer_node(state: LondonSearchState) -> dict:
    from scorers.nightlife_scorer import score_all_from_cache
    logging.info("nightlife_scorer_node: loading scores from cache")
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, score_all_from_cache)
        logging.info("nightlife_scorer_node: loaded %d districts", len(result))
        return {"nightlife_scores": result}
    except Exception as exc:
        logging.error("nightlife_scorer_node: cache read failed — %s", exc)
        return {"nightlife_scores": {}}


async def transport_scorer_node(state: LondonSearchState) -> dict:
    from scorers.transport_scorer import score_all_from_cache
    logging.info("transport_scorer_node: loading scores from cache")
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, score_all_from_cache)
        logging.info("transport_scorer_node: loaded %d districts", len(result))
        return {"transport_scores": result}
    except Exception as exc:
        logging.error("transport_scorer_node: cache read failed — %s", exc)
        return {"transport_scores": {}}


async def rent_scorer_node(state: LondonSearchState) -> dict:
    from scorers.rent_scorer import score_all_from_cache
    logging.info("rent_scorer_node: loading scores from cache")
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, score_all_from_cache)
        logging.info("rent_scorer_node: loaded %d districts", len(result))
        return {"rent_scores": result}
    except Exception as exc:
        logging.error("rent_scorer_node: cache read failed — %s", exc)
        return {"rent_scores": {}}


async def synthesiser_pass1_node(state: LondonSearchState) -> dict:
    crime_scores = state.get("crime_scores", {})
    green_scores = state.get("green_scores", {})
    nightlife_scores = state.get("nightlife_scores", {})
    transport_scores = state.get("transport_scores", {})
    rent_scores = state.get("rent_scores", {})
    allocation = state.get("adjusted_allocation") or state.get("token_allocation", {})

    crime_w = allocation.get("crime", 0) / 100
    green_w = allocation.get("green", 0) / 100
    nightlife_w = allocation.get("nightlife", 0) / 100
    transport_w = allocation.get("transport", 0) / 100
    rent_w = allocation.get("rent", 0) / 100

    logging.info(
        "synthesiser_pass1_node: weights crime=%.2f green=%.2f nightlife=%.2f transport=%.2f rent=%.2f",
        crime_w, green_w, nightlife_w, transport_w, rent_w,
    )

    all_districts = (
        set(crime_scores)
        | set(green_scores)
        | set(nightlife_scores)
        | set(transport_scores)
        | set(rent_scores)
    )

    weighted_scores: dict = {}
    for district in all_districts:
        missing = []
        def _get(scores: dict, dim: str) -> float:
            val = scores.get(district)
            if val is None:
                missing.append(dim)
                return 0.0
            return val

        c = _get(crime_scores, "crime")
        g = _get(green_scores, "green")
        n = _get(nightlife_scores, "nightlife")
        t = _get(transport_scores, "transport")
        r = _get(rent_scores, "rent")

        if missing:
            logging.warning("synthesiser_pass1_node: %s missing dimensions %s — using 0.0", district, missing)

        weighted_scores[district] = (
            c * crime_w + g * green_w + n * nightlife_w + t * transport_w + r * rent_w
        )

    ranked = sorted(weighted_scores, key=lambda d: weighted_scores[d], reverse=True)
    top_10 = ranked[:10]

    spawn_scores = state.get("spawn_scores") or {}
    if spawn_scores:
        filtered = [d for d in top_10 if spawn_scores.get(d, 0) > 0]
        logging.info(
            "synthesiser_pass1_node: spawn filter applied — %d of %d districts passed",
            len(filtered), len(top_10),
        )
        top_5 = filtered[:5]
    else:
        top_5 = top_10[:5]

    logging.info("synthesiser_pass1_node: top 5 districts:")
    for i, d in enumerate(top_5, 1):
        logging.info("  %d. %s — %.4f", i, d, weighted_scores[d])

    return {
        "weighted_scores": weighted_scores,
        "top_10_districts": top_10,
        "top_5_districts": top_5,
    }


_RESEARCH_SYSTEM_PROMPT = (
    "You are a London neighbourhood research agent. Your job is to find specific, "
    "recent, actionable insights about a London postcode district that data alone "
    "cannot capture. Focus on: recent news, Reddit/forum discussions, transport "
    "developments, crime trends, green space quality, nightlife reputation, and "
    "rent trajectory. Be specific — name actual streets, stations, developments. "
    "Avoid generic descriptions that could apply to any London neighbourhood. "
    "Perform a maximum of 2 web searches. Be selective — choose searches that will "
    "yield the most specific and recent information about this district."
)


async def research_agent_node(state: LondonSearchState, district: str) -> dict:
    logging.info("research_agent_node: starting research for %s", district)

    def _call_claude() -> list:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=_RESEARCH_SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": (
                    f"Research the London postcode district {district}. Find 3-5 specific, recent "
                    "insights that would help someone decide whether to live there. Focus on anything "
                    "that has changed recently or that local residents commonly mention."
                ),
            }],
        )
        text = "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        )
        raw_lines = text.splitlines()
        insights = [
            re.sub(r"^[\s\-\*\d\.\)]+", "", line).strip()
            for line in raw_lines
        ]
        return [s for s in insights if s]

    try:
        insights: list = []
        for _attempt in range(1, 4):
            try:
                insights = await asyncio.get_event_loop().run_in_executor(None, _call_claude)
                break
            except anthropic.RateLimitError:
                if _attempt == 3:
                    raise
                logging.warning("research_agent_node: rate limit hit — waiting 15s before retry %d/3", _attempt)
                await asyncio.sleep(15)
        logging.info("research_agent_node: completed %s — %d insights", district, len(insights))
        return {"qualitative_insights": {district: insights}}
    except Exception as exc:
        logging.error("research_agent_node: failed for %s — %s", district, exc)
        return {"qualitative_insights": {district: ["Research unavailable for this district."]}}


async def synthesiser_pass2_node(state: LondonSearchState) -> dict:
    with open(os.path.join(_PROMPTS_DIR, "synthesiser_pass2.md"), "r") as f:
        system_prompt = f.read()

    top_5_districts = state.get("top_5_districts", [])
    weighted_scores = state.get("weighted_scores", {})
    qualitative_insights = state.get("qualitative_insights", {})

    top_5_with_scores = "\n".join(
        f"{i}. {d} — {weighted_scores.get(d, 0.0):.4f}"
        for i, d in enumerate(top_5_districts, 1)
    )

    insights_sections = []
    for d in top_5_districts:
        insights = qualitative_insights.get(d, [])
        bullet_lines = "\n".join(f"  - {line}" for line in insights)
        insights_sections.append(f"{d}:\n{bullet_lines}" if bullet_lines else f"{d}:\n  - No research available.")
    qualitative_insights_text = "\n\n".join(insights_sections)

    user_message = (
        system_prompt
        .replace("{token_allocation}", json.dumps(state.get("token_allocation", {})))
        .replace("{adjusted_allocation}", json.dumps(state.get("adjusted_allocation", {})))
        .replace("{synthesiser_instruction}", state.get("synthesiser_instruction", ""))
        .replace("{top_5_with_scores}", top_5_with_scores)
        .replace("{qualitative_insights}", qualitative_insights_text)
        .replace("{knowledge_base}", state.get("knowledge_base", ""))
    )

    def _call_claude() -> dict:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        return json.loads(cleaned, strict=False)

    try:
        parsed: dict = {}
        for _attempt in range(1, 4):
            try:
                parsed = await asyncio.get_event_loop().run_in_executor(None, _call_claude)
                break
            except anthropic.RateLimitError:
                if _attempt == 3:
                    raise
                logging.warning("synthesiser_pass2_node: rate limit hit — waiting 15s before retry %d/3", _attempt)
                await asyncio.sleep(15)
        recommendations = parsed.get("recommendations", [])
        for rec in recommendations:
            logging.info(
                "synthesiser_pass2_node: #%d %s — %s",
                rec.get("rank", "?"), rec.get("district", "?"), rec.get("verdict", ""),
            )
        return {
            "top_5": recommendations,
            "new_learnings": parsed.get("new_learnings", []),
        }
    except Exception as exc:
        logging.error("synthesiser_pass2_node: Claude call failed — %s", exc)
        return {"top_5": [], "new_learnings": []}


async def knowledge_writer_node(state: LondonSearchState) -> dict:
    print("knowledge_writer_node")
    return {}


async def research_agents_parallel_node(state: LondonSearchState) -> dict:
    districts = state.get("top_5_districts", [])
    logging.info("research_agents_parallel_node: starting parallel research for %s", districts)
    results = await asyncio.gather(*[research_agent_node(state, d) for d in districts])
    merged: dict = {}
    for r in results:
        merged.update(r.get("qualitative_insights", {}))
    logging.info("research_agents_parallel_node: all %d districts complete", len(merged))
    return {"qualitative_insights": merged}


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(LondonSearchState)

    graph.add_node("knowledge_loader", knowledge_loader_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("context_sub_agent", context_sub_agent_node)
    graph.add_node("crime_scorer", crime_scorer_node)
    graph.add_node("green_scorer", green_scorer_node)
    graph.add_node("nightlife_scorer", nightlife_scorer_node)
    graph.add_node("transport_scorer", transport_scorer_node)
    graph.add_node("rent_scorer", rent_scorer_node)
    graph.add_node("synthesiser_pass1", synthesiser_pass1_node)
    graph.add_node("research_agents", research_agents_parallel_node)
    graph.add_node("synthesiser_pass2", synthesiser_pass2_node)
    graph.add_node("knowledge_writer", knowledge_writer_node)

    graph.set_entry_point("knowledge_loader")
    graph.add_edge("knowledge_loader", "orchestrator")
    graph.add_edge("orchestrator", "context_sub_agent")

    for scorer in ("crime_scorer", "green_scorer", "nightlife_scorer", "transport_scorer", "rent_scorer"):
        graph.add_edge("context_sub_agent", scorer)
        graph.add_edge(scorer, "synthesiser_pass1")

    graph.add_edge("synthesiser_pass1", "research_agents")
    graph.add_edge("research_agents", "synthesiser_pass2")
    graph.add_edge("synthesiser_pass2", "knowledge_writer")
    graph.add_edge("knowledge_writer", END)

    return graph.compile()


pipeline = build_graph()


async def run_pipeline(
    token_allocation: dict,
    context_text: str,
    session_id: str,
) -> LondonSearchState:
    initial_state = make_initial_state(token_allocation, context_text, session_id)
    result = await pipeline.ainvoke(initial_state)
    return result
