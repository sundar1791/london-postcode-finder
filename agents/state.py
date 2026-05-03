import operator
from typing import Annotated
from typing_extensions import TypedDict


class LondonSearchState(TypedDict):
    # Input fields
    token_allocation: dict
    context_text: str
    session_id: str

    # Knowledge base
    knowledge_base: str

    # Orchestrator output
    adjusted_allocation: dict
    context_analysis: dict

    # Scorer output (Pass 1) — separate fields to avoid parallel write conflicts
    crime_scores: dict
    green_scores: dict
    nightlife_scores: dict
    transport_scores: dict
    rent_scores: dict
    weighted_scores: dict
    top_5_districts: list

    # Research agent output (Pass 2) — Annotated for parallel writes
    qualitative_insights: Annotated[dict, operator.or_]

    # Synthesiser output
    top_5: list

    # Knowledge writer input — Annotated for parallel writes
    new_learnings: Annotated[list, operator.add]


def make_initial_state(
    token_allocation: dict,
    context_text: str,
    session_id: str,
) -> LondonSearchState:
    return LondonSearchState(
        token_allocation=token_allocation,
        context_text=context_text,
        session_id=session_id,
        knowledge_base="",
        adjusted_allocation={},
        context_analysis={},
        crime_scores={},
        green_scores={},
        nightlife_scores={},
        transport_scores={},
        rent_scores={},
        weighted_scores={},
        top_5_districts=[],
        qualitative_insights={},
        top_5=[],
        new_learnings=[],
    )
