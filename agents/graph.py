import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from agents.state import LondonSearchState, make_initial_state


async def knowledge_loader_node(state: LondonSearchState) -> dict:
    print("knowledge_loader_node")
    return {}


async def orchestrator_node(state: LondonSearchState) -> dict:
    print("orchestrator_node")
    return {}


async def crime_scorer_node(state: LondonSearchState) -> dict:
    print("crime_scorer_node")
    return {}


async def green_scorer_node(state: LondonSearchState) -> dict:
    print("green_scorer_node")
    return {}


async def nightlife_scorer_node(state: LondonSearchState) -> dict:
    print("nightlife_scorer_node")
    return {}


async def transport_scorer_node(state: LondonSearchState) -> dict:
    print("transport_scorer_node")
    return {}


async def rent_scorer_node(state: LondonSearchState) -> dict:
    print("rent_scorer_node")
    return {}


async def synthesiser_pass1_node(state: LondonSearchState) -> dict:
    print("synthesiser_pass1_node")
    return {}


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
