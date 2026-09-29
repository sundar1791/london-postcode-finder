# Integration tests for the full two-pass LangGraph pipeline.
# These tests make real API calls (Anthropic, Police, Overpass, TfL, etc.).
# Do NOT run in CI without rate limit consideration — use RUN_E2E_TESTS=1 to enable.

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(override=True)

import asyncio

import pytest
import pytest_asyncio
from agents.graph import run_pipeline


@pytest_asyncio.fixture(autouse=True)
async def rate_limit_buffer():
    await asyncio.sleep(30)
    yield


@pytest.mark.asyncio
@pytest.mark.timeout(300)
@pytest.mark.skipif(
    os.getenv("RUN_E2E_TESTS") != "1",
    reason="Makes real API calls. Set RUN_E2E_TESTS=1 to run.",
)
async def test_baseline_pipeline():
    result = await run_pipeline(
        token_allocation={"crime": 20, "green": 20, "nightlife": 20, "transport": 20, "rent": 20},
        context_text="",
        session_id="test-baseline",
    )

    assert len(result["top_5_districts"]) == 5
    assert len(result["top_5"]) == 5

    for rec in result["top_5"]:
        assert rec.get("verdict"), f"Missing verdict in recommendation: {rec}"
        assert rec.get("rationale"), f"Missing rationale in recommendation: {rec}"
        assert rec.get("tradeoff"), f"Missing tradeoff in recommendation: {rec}"
        assert rec.get("tip"), f"Missing tip in recommendation: {rec}"

    assert len(result["weighted_scores"]) == 40
    assert isinstance(result["new_learnings"], list) and len(result["new_learnings"]) > 0


@pytest.mark.asyncio
@pytest.mark.timeout(300)
@pytest.mark.skipif(
    os.getenv("RUN_E2E_TESTS") != "1",
    reason="Makes real API calls. Set RUN_E2E_TESTS=1 to run.",
)
async def test_weight_adjustment():
    result = await run_pipeline(
        token_allocation={"crime": 40, "green": 20, "nightlife": 15, "transport": 15, "rent": 10},
        context_text="I am terrified of crime",
        session_id="test-weight-adjustment",
    )

    assert result["context_analysis"]["type"] == "adjust"
    assert result["adjusted_allocation"]["crime"] > 40
    assert sum(result["adjusted_allocation"].values()) == 100
    assert len(result["top_5_districts"]) == 5
    assert len(result["top_5"]) == 5


@pytest.mark.asyncio
@pytest.mark.timeout(300)
@pytest.mark.skipif(
    os.getenv("RUN_E2E_TESTS") != "1",
    reason="Makes real API calls. Set RUN_E2E_TESTS=1 to run.",
)
async def test_spawn_detection():
    result = await run_pipeline(
        token_allocation={"crime": 20, "green": 20, "nightlife": 20, "transport": 20, "rent": 20},
        context_text="I need a nursery nearby for my daughter",
        session_id="test-spawn-detection",
    )

    assert result["context_analysis"]["type"] in ("spawn", "combination")
    assert result["context_analysis"]["spawn"] is not None
    assert result["context_analysis"]["spawn"]["overpass_query"] is not None
