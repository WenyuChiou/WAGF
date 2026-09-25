"""
Regression test for the FinalParityHook.post_step flood_threshold defect.

Defect: post_step used to lower agent.flood_threshold whenever
result.approved_skill.skill_name resolved to "elevate_house", regardless of
whether the proposal was actually approved. On a REJECTED row,
approved_skill still carries the agent's blocked proposal (see
SkillBrokerEngine._build_approved_skill in
broker/core/skill_broker_engine.py), so a rejected elevate_house proposal
would still lower the household's flood threshold even though the registry
default skill (do_nothing) is what actually executed.

The fix gates the threshold update on the same canonical "was this actually
approved and executed" predicate already used elsewhere in the codebase for
the identical purpose (see examples/multi_agent/flood/orchestration/
lifecycle_hooks.py FloodLifecycleHooks.post_step and
broker/core/skill_broker_engine.py's own execution guard):

    result.outcome in (SkillOutcome.APPROVED, SkillOutcome.RETRY_SUCCESS)

This test builds a minimal agent + hook and asserts:
  - a REJECTED elevate_house proposal leaves flood_threshold unchanged.
  - an UNCERTAIN elevate_house proposal leaves flood_threshold unchanged.
  - an APPROVED elevate_house proposal still drops flood_threshold by 0.2x
    (the pre-existing, intended behaviour).
  - a RETRY_SUCCESS elevate_house proposal also drops it by 0.2x (same as
    APPROVED: it is a real, executed approval).

Lives in broker/tests/ (not examples/single_agent/tests/) so it runs under
CI's `pytest tests/ broker/` the same way the sibling
test_single_agent_run_flood.py does.
"""
import pytest

from examples.single_agent.run_flood import FinalParityHook

from broker.interfaces.skill_types import (
    ApprovedSkill,
    ExecutionResult,
    SkillBrokerResult,
    SkillOutcome,
    SkillProposal,
)


class _FakeSim:
    """Stand-in for ResearchSimulation: post_step only reads current_year."""

    def __init__(self, current_year: int = 1):
        self.current_year = current_year


class _FakeAgent:
    """Minimal agent stand-in: post_step only touches id + flood_threshold."""

    def __init__(self, agent_id: str = "agent_1", flood_threshold: float = 0.5):
        self.id = agent_id
        self.flood_threshold = flood_threshold


def _make_hook(year: int = 1) -> FinalParityHook:
    return FinalParityHook(sim=_FakeSim(current_year=year), runner=None)


def _elevate_house_result(outcome: SkillOutcome, agent_id: str) -> SkillBrokerResult:
    proposal = SkillProposal(
        skill_name="elevate_house",
        agent_id=agent_id,
        reasoning={"threat_appraisal": "high", "coping_appraisal": "high"},
    )
    approved = ApprovedSkill(
        skill_name="elevate_house",
        agent_id=agent_id,
        approval_status=outcome.value,
    )
    # REJECTED rows never reach a successful execution_result on the real
    # pipeline; APPROVED rows do.
    execution_result = ExecutionResult(
        success=(outcome in (SkillOutcome.APPROVED, SkillOutcome.RETRY_SUCCESS)),
        state_changes={},
    )
    return SkillBrokerResult(
        outcome=outcome,
        skill_proposal=proposal,
        approved_skill=approved,
        execution_result=execution_result,
    )


def test_rejected_elevate_house_does_not_lower_threshold():
    """A REJECTED elevate_house proposal must NOT touch flood_threshold.

    Pre-fix, this failed: post_step string-matched approved_skill.skill_name
    without checking result.outcome, so the blocked proposal alone was
    enough to slash the threshold even though the registry default
    (do_nothing) is what actually ran.
    """
    agent = _FakeAgent(agent_id="agent_1", flood_threshold=0.5)
    hook = _make_hook()
    result = _elevate_house_result(SkillOutcome.REJECTED, agent.id)

    hook.post_step(agent, result)

    assert agent.flood_threshold == 0.5, (
        "flood_threshold changed on a REJECTED elevate_house proposal; "
        "only the registry default (do_nothing) actually executed"
    )


def test_approved_elevate_house_lowers_threshold_by_point_two_x():
    """An APPROVED elevate_house proposal keeps the intended 0.2x drop."""
    agent = _FakeAgent(agent_id="agent_2", flood_threshold=0.5)
    hook = _make_hook()
    result = _elevate_house_result(SkillOutcome.APPROVED, agent.id)

    hook.post_step(agent, result)

    assert agent.flood_threshold == pytest.approx(0.1)  # 0.5 * 0.2


def test_retry_success_elevate_house_lowers_threshold_by_point_two_x():
    """RETRY_SUCCESS is also a real, executed approval: same 0.2x drop."""
    agent = _FakeAgent(agent_id="agent_3", flood_threshold=0.5)
    hook = _make_hook()
    result = _elevate_house_result(SkillOutcome.RETRY_SUCCESS, agent.id)

    hook.post_step(agent, result)

    assert agent.flood_threshold == pytest.approx(0.1)


def test_uncertain_elevate_house_does_not_lower_threshold():
    """UNCERTAIN (parser never produced a usable choice) also must not fire."""
    agent = _FakeAgent(agent_id="agent_4", flood_threshold=0.5)
    hook = _make_hook()
    result = _elevate_house_result(SkillOutcome.UNCERTAIN, agent.id)

    hook.post_step(agent, result)

    assert agent.flood_threshold == 0.5
