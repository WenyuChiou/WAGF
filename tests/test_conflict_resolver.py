"""Tests for broker.components.conflict_resolver — Conflict Detection & Resolution.

Reference: Task-054 Communication Layer
"""
import pytest

from broker.interfaces.coordination import ActionProposal, ActionResolution, ResourceConflict
from broker.components.conflict_resolver import (
    ConflictDetector,
    PriorityResolution,
    ProportionalResolution,
    ConflictResolver,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_proposal(agent_id, agent_type, skill, requirements=None, priority=0):
    """Helper to create ActionProposal."""
    return ActionProposal(
        agent_id=agent_id,
        agent_type=agent_type,
        skill_name=skill,
        resource_requirements=requirements or {},
        priority=priority,
    )


@pytest.fixture
def detector():
    """Detector with 500k budget and 10 elevation slots."""
    return ConflictDetector({"govt_budget": 500_000, "elevation_slots": 10})


@pytest.fixture
def resolver(detector):
    """Default ConflictResolver with PriorityResolution."""
    return ConflictResolver(detector, PriorityResolution())


# ---------------------------------------------------------------------------
# Conflict Detection
# ---------------------------------------------------------------------------

class TestConflictDetector:
    def test_no_conflict_when_under_limit(self, detector):
        proposals = [
            make_proposal("hh_1", "household_owner", "apply_for_subsidy",
                          {"govt_budget": 100_000}),
            make_proposal("hh_2", "household_owner", "apply_for_subsidy",
                          {"govt_budget": 200_000}),
        ]
        conflicts = detector.detect(proposals)
        assert len(conflicts) == 0  # 300k < 500k

    def test_over_allocation_detected(self, detector):
        proposals = [
            make_proposal("hh_1", "household_owner", "apply_for_subsidy",
                          {"govt_budget": 300_000}),
            make_proposal("hh_2", "household_owner", "apply_for_subsidy",
                          {"govt_budget": 300_000}),
        ]
        conflicts = detector.detect(proposals)
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c.resource_key == "govt_budget"
        assert c.total_requested == 600_000
        assert c.available == 500_000
        assert set(c.competing_agents) == {"hh_1", "hh_2"}

    def test_deficit_property(self):
        c = ResourceConflict(
            resource_key="budget", total_requested=800, available=500,
            competing_agents=["a", "b"],
        )
        assert c.deficit == 300

    def test_no_deficit_when_under(self):
        c = ResourceConflict(
            resource_key="budget", total_requested=300, available=500,
            competing_agents=["a"],
        )
        assert c.deficit == 0

    def test_multiple_resource_conflicts(self, detector):
        proposals = [
            make_proposal("hh_1", "household_owner", "elevate_and_subsidy",
                          {"govt_budget": 400_000, "elevation_slots": 8}),
            make_proposal("hh_2", "household_owner", "elevate_and_subsidy",
                          {"govt_budget": 200_000, "elevation_slots": 5}),
        ]
        conflicts = detector.detect(proposals)
        assert len(conflicts) == 2  # Both budget and elevation over limit
        keys = {c.resource_key for c in conflicts}
        assert "govt_budget" in keys
        assert "elevation_slots" in keys

    def test_unknown_resource_ignored(self, detector):
        proposals = [
            make_proposal("hh_1", "household_owner", "relocate",
                          {"relocation_fund": 999_999}),
        ]
        conflicts = detector.detect(proposals)
        assert len(conflicts) == 0  # No limit set for relocation_fund

    def test_update_limit(self, detector):
        detector.update_limit("govt_budget", 1_000_000)
        proposals = [
            make_proposal("hh_1", "household_owner", "sub",
                          {"govt_budget": 600_000}),
            make_proposal("hh_2", "household_owner", "sub",
                          {"govt_budget": 300_000}),
        ]
        conflicts = detector.detect(proposals)
        assert len(conflicts) == 0  # 900k < 1M


# ---------------------------------------------------------------------------
# Priority Resolution
# ---------------------------------------------------------------------------

class TestPriorityResolution:
    def test_higher_priority_approved_first(self):
        strategy = PriorityResolution()
        conflict = ResourceConflict(
            resource_key="govt_budget", total_requested=600_000,
            available=500_000, competing_agents=["gov_1", "hh_1"],
        )
        proposals = [
            make_proposal("hh_1", "household_owner", "apply_for_subsidy",
                          {"govt_budget": 300_000}),
            make_proposal("gov_1", "government", "allocate_budget",
                          {"govt_budget": 300_000}),
        ]
        resolutions = strategy.resolve(conflict, proposals)
        # Government (priority 100) should be approved, household (priority 10) approved too
        # Total: 300k + 300k = 600k, available 500k
        # Gov gets 300k first (remaining: 200k), household needs 300k → denied
        gov_res = next(r for r in resolutions if r.agent_id == "gov_1")
        hh_res = next(r for r in resolutions if r.agent_id == "hh_1")
        assert gov_res.approved is True
        assert hh_res.approved is False
        assert "Insufficient" in hh_res.denial_reason

    def test_equal_priority_fcfs(self):
        strategy = PriorityResolution()
        conflict = ResourceConflict(
            resource_key="govt_budget", total_requested=800_000,
            available=500_000,
            competing_agents=["hh_1", "hh_2", "hh_3"],
        )
        proposals = [
            make_proposal("hh_1", "household_owner", "subsidy",
                          {"govt_budget": 200_000}),
            make_proposal("hh_2", "household_owner", "subsidy",
                          {"govt_budget": 200_000}),
            make_proposal("hh_3", "household_owner", "subsidy",
                          {"govt_budget": 400_000}),
        ]
        resolutions = strategy.resolve(conflict, proposals)
        approved = [r for r in resolutions if r.approved]
        denied = [r for r in resolutions if not r.approved]
        # 200k + 200k = 400k ≤ 500k, but 400k more → 800k > 500k
        # First two get approved, third denied
        assert len(approved) == 2
        assert len(denied) == 1


# ---------------------------------------------------------------------------
# Proportional Resolution
# ---------------------------------------------------------------------------

class TestProportionalResolution:
    def test_proportional_split(self):
        strategy = ProportionalResolution()
        conflict = ResourceConflict(
            resource_key="govt_budget", total_requested=1_000_000,
            available=500_000,
            competing_agents=["hh_1", "hh_2"],
        )
        proposals = [
            make_proposal("hh_1", "household_owner", "subsidy",
                          {"govt_budget": 750_000}),
            make_proposal("hh_2", "household_owner", "subsidy",
                          {"govt_budget": 250_000}),
        ]
        resolutions = strategy.resolve(conflict, proposals)
        assert len(resolutions) == 2
        # All approved with reduced allocation
        assert all(r.approved for r in resolutions)
        hh1_res = next(r for r in resolutions if r.agent_id == "hh_1")
        hh2_res = next(r for r in resolutions if r.agent_id == "hh_2")
        # hh_1 gets 75% of 500k = 375k
        assert hh1_res.state_changes["govt_budget_allocated"] == pytest.approx(375_000)
        # hh_2 gets 25% of 500k = 125k
        assert hh2_res.state_changes["govt_budget_allocated"] == pytest.approx(125_000)


# ---------------------------------------------------------------------------
# ConflictResolver (Orchestrator)
# ---------------------------------------------------------------------------

class TestConflictResolver:
    def test_no_conflict_passthrough(self, resolver):
        proposals = [
            make_proposal("hh_1", "household_owner", "do_nothing", {}),
        ]
        resolutions, conflicts = resolver.resolve_all(proposals)
        assert len(conflicts) == 0
        assert len(resolutions) == 0  # No conflicts → no resolutions

    def test_conflict_resolved(self, resolver):
        proposals = [
            make_proposal("hh_1", "household_owner", "subsidy",
                          {"govt_budget": 400_000}),
            make_proposal("hh_2", "household_owner", "subsidy",
                          {"govt_budget": 400_000}),
        ]
        resolutions, conflicts = resolver.resolve_all(proposals)
        assert len(conflicts) == 1
        assert len(resolutions) == 2

    def test_conflict_history_accumulated(self, resolver):
        proposals = [
            make_proposal("hh_1", "household_owner", "sub",
                          {"govt_budget": 400_000}),
            make_proposal("hh_2", "household_owner", "sub",
                          {"govt_budget": 400_000}),
        ]
        resolver.resolve_all(proposals)
        resolver.resolve_all(proposals)
        assert len(resolver.conflict_history) == 2

    def test_summary(self, resolver):
        s = resolver.summary()
        assert s["strategy"] == "PriorityResolution"
        assert "resource_limits" in s
        assert s["total_conflicts"] == 0

    def test_to_dict_methods(self):
        proposal = make_proposal("a1", "gov", "skill1",
                                 {"budget": 100}, priority=5)
        d = proposal.to_dict()
        assert d["agent_id"] == "a1"
        assert d["priority"] == 5

        resolution = ActionResolution(
            agent_id="a1", original_proposal=proposal,
            approved=True, event_statement="OK",
        )
        d2 = resolution.to_dict()
        assert d2["approved"] is True
        assert d2["original_skill"] == "skill1"

        conflict = ResourceConflict(
            resource_key="budget", total_requested=200,
            available=100, competing_agents=["a1", "a2"],
        )
        d3 = conflict.to_dict()
        assert d3["deficit"] == 100
