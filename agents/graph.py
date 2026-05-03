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
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        block = response.content[0]
        return block.text if isinstance(block, TextBlock) else ""

    try:
        raw = await asyncio.get_event_loop().run_in_executor(None, _call_claude)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        parsed = json.loads(cleaned)

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
    top_5 = ranked[:5]

    logging.info("synthesiser_pass1_node: top 5 districts:")
    for i, d in enumerate(top_5, 1):
        logging.info("  %d. %s — %.4f", i, d, weighted_scores[d])

    return {
        "weighted_scores": weighted_scores,
        "top_5_districts": top_5,
    }


async def research_agent_node(state: LondonSearchState, district: str) -> dict:
    print(f"research_agent_node: {district}")
    return {}


async def synthesiser_pass2_node(state: LondonSearchState) -> dict:
    print("synthesiser_pass2_node")
    return {}


async def knowledge_writer_node(state: LondonSearchState) -> dict:
    print("knowledge_writer_node")
    return {}


# TODO US-046: replace with true parallel fan-out once top_5_districts is known at graph-build time
async def research_agents_sequential_node(state: LondonSearchState) -> dict:
    for district in state.get("top_5_districts", []):
        await research_agent_node(state, district)
    return {}


def build_graph() -> CompiledStateGraph:
    graph = StateGraph(LondonSearchState)

    graph.add_node("knowledge_loader", knowledge_loader_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("crime_scorer", crime_scorer_node)
    graph.add_node("green_scorer", green_scorer_node)
    graph.add_node("nightlife_scorer", nightlife_scorer_node)
    graph.add_node("transport_scorer", transport_scorer_node)
    graph.add_node("rent_scorer", rent_scorer_node)
    graph.add_node("synthesiser_pass1", synthesiser_pass1_node)
    graph.add_node("research_agents", research_agents_sequential_node)
    graph.add_node("synthesiser_pass2", synthesiser_pass2_node)
    graph.add_node("knowledge_writer", knowledge_writer_node)

    graph.set_entry_point("knowledge_loader")
    graph.add_edge("knowledge_loader", "orchestrator")

    for scorer in ("crime_scorer", "green_scorer", "nightlife_scorer", "transport_scorer", "rent_scorer"):
        graph.add_edge("orchestrator", scorer)
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
