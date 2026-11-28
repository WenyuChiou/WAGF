"""The flood memory filter omits generic executed-action lines. The flood
threshold changes only when the corresponding action actually executes.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from broker.components.memory.engine import WindowMemoryEngine
from broker.interfaces.skill_types import (
    ApprovedSkill, ExecutionResult, SkillBrokerResult, SkillOutcome, SkillProposal,
)
from examples.single_agent.run_flood import DecisionFilteredMemoryEngine, FinalParityHook


class _Ag:
    id = "A1"


def test_filter_drops_runner_fallback_and_decision_lines():
    inner = WindowMemoryEngine(window_size=5)
    eng = DecisionFilteredMemoryEngine(inner)
    eng.add_memory("A1", "Year 1: Action carried out: Buy insurance.")
    eng.add_memory_for_agent(_Ag(), "Year 2: Action carried out: Do nothing.")
    eng.add_memory("A1", "Year 2: The river rose.")
    kept = inner.retrieve(_Ag(), top_k=10)
    assert [m["content"] if isinstance(m, dict) else str(m) for m in kept] == [
        "Year 2: The river rose."
    ]


@dataclass
class _FakeSim:
    current_year: int = 1


@dataclass
class _FakeAgent:
    id: str = "A1"
    flood_threshold: float = 0.5


def _result(outcome, executed, success=True):
    return SkillBrokerResult(
        outcome=outcome,
        skill_proposal=SkillProposal(skill_name="elevate_house", agent_id="A1",
                                     reasoning={}),
        approved_skill=ApprovedSkill(skill_name="elevate_house", agent_id="A1",
                                     approval_status=outcome.value),
        execution_result=ExecutionResult(success=success, state_changes={}),
        executed_skill=executed,
        executed_via_fallback=(executed == "do_nothing"),
    )


def test_rejected_default_fallback_keeps_threshold():
    agent = _FakeAgent()
    FinalParityHook(sim=_FakeSim(), runner=None).post_step(
        agent, _result(SkillOutcome.REJECTED, "do_nothing"))
    assert agent.flood_threshold == 0.5


def test_keep_proposal_executed_elevation_lowers_threshold():
    agent = _FakeAgent()
    FinalParityHook(sim=_FakeSim(), runner=None).post_step(
        agent, _result(SkillOutcome.REJECTED, "elevate_house"))
    assert agent.flood_threshold == pytest.approx(0.1)


def test_keep_proposal_failed_execution_keeps_threshold():
    agent = _FakeAgent()
    FinalParityHook(sim=_FakeSim(), runner=None).post_step(
        agent, _result(SkillOutcome.REJECTED, "elevate_house", success=False))
    assert agent.flood_threshold == 0.5
