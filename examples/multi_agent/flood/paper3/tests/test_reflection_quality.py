"""Tests for reflection quality (Bug 1: Memory Consolidation).

Verifies that year-end reflections are personalized, not static stubs,
and that importance/retrieval allocation are properly calibrated.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch


# --- Helpers to build mock agents ---

def _make_mock_agent(agent_id, dynamic_state):
    """Create a mock agent with given dynamic_state dict."""
    agent = MagicMock()
    agent.dynamic_state = dynamic_state
    return agent


def _make_mock_memory_engine():
    """Create a mock memory engine that records add_memory calls."""
    engine = MagicMock()
    engine.retrieve_stratified.return_value = [
        "Year 1: Purchased insurance after flood warning.",
        "Neighbor elevated their home last year.",
    ]
    engine.added_memories = []

    def _capture_add(agent_id, text, metadata=None):
        engine.added_memories.append({
            "agent_id": agent_id,
            "text": text,
            "metadata": metadata or {},
        })

    engine.add_memory.side_effect = _capture_add
    return engine


def _build_hooks():
    """Build a MultiAgentHooks instance with minimal config for testing."""
    from examples.multi_agent.flood.orchestration.lifecycle_hooks import MultiAgentHooks

    hooks = MultiAgentHooks.__new__(MultiAgentHooks)
    hooks.env = {}
    hooks.agent_flood_depths = {}
    hooks.drift_detector = MagicMock()
    return hooks


class TestReflectionNoStaticString:
    """Verify the old hardcoded stub is gone."""

    def test_reflection_no_static_string(self):
        hooks = _build_hooks()
        engine = _make_mock_memory_engine()

        agent = _make_mock_agent("A1", {
            "flooded_this_year": True,
            "flood_damage_pct": 0.15,
            "last_decision": "purchase_insurance",
            "has_insurance": True,
            "elevated": False,
        })
        hooks.agent_flood_depths["A1"] = 0.45

        hooks._run_ma_reflection(
            agent_id="A1",
            year=5,
            agents={"A1": agent},
            memory_engine=engine,
            flood_occurred=True,
        )

        assert len(engine.added_memories) == 1
        text = engine.added_memories[0]["text"]
        assert "Learned valuable lessons" not in text, (
            f"Reflection still contains hardcoded stub: {text}"
        )
        assert "Importance of preparedness highlighted" not in text, (
            f"Reflection still contains hardcoded stub: {text}"
        )


class TestReflectionUniqueness:
    """Two agents with different states should produce different reflections."""

    def test_reflection_uniqueness(self):
        hooks = _build_hooks()

        # Agent A: flooded, insured
        engine_a = _make_mock_memory_engine()
        agent_a = _make_mock_agent("A1", {
            "flooded_this_year": True,
            "flood_damage_pct": 0.30,
            "last_decision": "purchase_insurance",
            "has_insurance": True,
            "elevated": False,
        })
        hooks.agent_flood_depths["A1"] = 0.80

        hooks._run_ma_reflection("A1", 3, {"A1": agent_a}, engine_a, True)

        # Agent B: not flooded, elevated
        engine_b = _make_mock_memory_engine()
        agent_b = _make_mock_agent("B1", {
            "flooded_this_year": False,
            "last_decision": "do_nothing",
            "has_insurance": False,
            "elevated": True,
        })

        hooks._run_ma_reflection("B1", 3, {"B1": agent_b}, engine_b, False)

        text_a = engine_a.added_memories[0]["text"]
        text_b = engine_b.added_memories[0]["text"]
        assert text_a != text_b, (
            f"Two different agents produced identical reflections:\n"
            f"  A: {text_a}\n  B: {text_b}"
        )


class TestReflectionContainsState:
    """A flooded agent's reflection should mention flooding."""

    def test_reflection_contains_flood_info(self):
        hooks = _build_hooks()
        engine = _make_mock_memory_engine()

        agent = _make_mock_agent("A1", {
            "flooded_this_year": True,
            "flood_damage_pct": 0.25,
            "last_decision": "elevate_home",
            "has_insurance": False,
            "elevated": False,
        })
        hooks.agent_flood_depths["A1"] = 0.60

        hooks._run_ma_reflection("A1", 7, {"A1": agent}, engine, True)

        text = engine.added_memories[0]["text"]
        assert "flood" in text.lower(), (
            f"Flooded agent reflection should mention flooding: {text}"
        )
        assert "elevat" in text.lower(), (
            f"Agent who chose elevation should mention it: {text}"
        )


class TestReflectionImportanceBelowFlood:
    """Reflection importance should be below flood memory importance (0.80)."""

    def test_reflection_importance_below_flood(self):
        hooks = _build_hooks()
        engine = _make_mock_memory_engine()

        agent = _make_mock_agent("A1", {
            "flooded_this_year": False,
            "last_decision": "do_nothing",
            "has_insurance": False,
            "elevated": False,
        })

        hooks._run_ma_reflection("A1", 2, {"A1": agent}, engine, False)

        metadata = engine.added_memories[0]["metadata"]
        importance = metadata.get("importance", 1.0)
        assert importance < 0.80, (
            f"Reflection importance {importance} should be < 0.80 (flood memory level)"
        )
        assert importance <= 0.50, (
            f"Reflection importance {importance} should be <= 0.50 (below decision level)"
        )


class TestRetrievalAllocationBalanced:
    """Personal slots should be >= reflection slots."""

    def test_retrieval_allocation_balanced(self):
        """Verify retrieve_stratified is called with personal >= reflection allocation."""
        hooks = _build_hooks()
        engine = _make_mock_memory_engine()

        agent = _make_mock_agent("A1", {
            "flooded_this_year": False,
            "last_decision": "do_nothing",
            "has_insurance": False,
            "elevated": False,
        })

        hooks._run_ma_reflection("A1", 1, {"A1": agent}, engine, False)

        # Check what allocation was passed to retrieve_stratified
        call_args = engine.retrieve_stratified.call_args
        # retrieve_stratified(agent_id, allocation=..., total_k=..., ...)
        allocation = call_args.kwargs.get("allocation")
        if allocation is None and call_args.args and len(call_args.args) > 1:
            allocation = call_args.args[1]

        assert allocation is not None, "Could not extract allocation from retrieve_stratified call"
        assert allocation.get("personal", 0) >= allocation.get("reflection", 0), (
            f"Personal slots ({allocation.get('personal')}) should be >= "
            f"reflection slots ({allocation.get('reflection')})"
        )
