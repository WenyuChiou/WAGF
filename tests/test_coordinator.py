"""Tests for broker.components.coordinator — Game Master / Coordinator.

Reference: Task-054 Communication Layer
"""
import pytest

from broker.interfaces.coordination import ActionProposal, ActionResolution
from broker.components.coordinator import (
    PassthroughStrategy,
    ConflictAwareStrategy,
    CustomStrategy,
    GameMaster,
    create_game_master,
)
from broker.components.conflict_resolver import (
    ConflictDetector,
    ConflictResolver,
    PriorityResolution,
)
from broker.components.message_pool import MessagePool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_proposal(agent_id, agent_type, skill, requirements=None, priority=0):
    return ActionProposal(
        agent_id=agent_id,
        agent_type=agent_type,
        skill_name=skill,
        resource_requirements=requirements or {},
        priority=priority,
    )


# ---------------------------------------------------------------------------
# Passthrough Strategy
# ---------------------------------------------------------------------------

class TestPassthroughStrategy:
    def test_approves_all(self):
        strategy = PassthroughStrategy()
        proposals = [
            make_proposal("hh_1", "household_owner", "elevate"),
            make_proposal("hh_2", "household_owner", "insure"),
        ]
        resolutions = strategy.resolve(proposals, {})
        assert len(resolutions) == 2
        assert all(r.approved for r in resolutions)

    def test_generates_event_statements(self):
        strategy = PassthroughStrategy()
        proposals = [make_proposal("gov_1", "government", "announce_policy")]
        resolutions = strategy.resolve(proposals, {})
        assert "gov_1" in resolutions[0].event_statement
        assert "announce_policy" in resolutions[0].event_statement


# ---------------------------------------------------------------------------
# ConflictAware Strategy
# ---------------------------------------------------------------------------

class TestConflictAwareStrategy:
    def test_auto_approves_non_conflicting(self):
        detector = ConflictDetector({"budget": 1_000_000})
        resolver = ConflictResolver(detector, PriorityResolution())
        strategy = ConflictAwareStrategy(resolver)

        proposals = [
            make_proposal("hh_1", "household_owner", "insure", {}),
            make_proposal("hh_2", "household_owner", "elevate", {}),
        ]
        resolutions = strategy.resolve(proposals, {})
        assert len(resolutions) == 2
        assert all(r.approved for r in resolutions)

    def test_conflict_resolved_with_denials(self):
        detector = ConflictDetector({"budget": 100_000})
        resolver = ConflictResolver(detector, PriorityResolution())
        strategy = ConflictAwareStrategy(resolver)

        proposals = [
            make_proposal("gov_1", "government", "allocate",
                          {"budget": 80_000}),
            make_proposal("hh_1", "household_owner", "subsidy",
                          {"budget": 80_000}),
        ]
        resolutions = strategy.resolve(proposals, {})
        # gov gets approved (priority 100), household denied (priority 10)
        gov_res = next(r for r in resolutions if r.agent_id == "gov_1")
        hh_res = next(r for r in resolutions if r.agent_id == "hh_1")
        assert gov_res.approved is True
        assert hh_res.approved is False

    def test_mixed_conflict_and_non_conflict(self):
        detector = ConflictDetector({"budget": 100_000})
        resolver = ConflictResolver(detector, PriorityResolution())
        strategy = ConflictAwareStrategy(resolver)

        proposals = [
            make_proposal("hh_1", "household_owner", "subsidy",
                          {"budget": 80_000}),
            make_proposal("hh_2", "household_owner", "subsidy",
                          {"budget": 80_000}),
            make_proposal("hh_3", "household_owner", "do_nothing", {}),
        ]
        resolutions = strategy.resolve(proposals, {})
        # hh_3 has no resource requirements → auto-approved
        hh3_res = next(r for r in resolutions if r.agent_id == "hh_3")
        assert hh3_res.approved is True
        # One of hh_1/hh_2 denied
        conflict_res = [r for r in resolutions if r.agent_id in ("hh_1", "hh_2")]
        denied = [r for r in conflict_res if not r.approved]
        assert len(denied) == 1


# ---------------------------------------------------------------------------
# Custom Strategy
# ---------------------------------------------------------------------------

class TestCustomStrategy:
    def test_delegates_to_callable(self):
        def my_resolve(proposals, state):
            return [
                ActionResolution(
                    agent_id=p.agent_id,
                    original_proposal=p,
                    approved=(p.agent_type == "government"),
                    event_statement=f"Custom: {p.agent_id}",
                )
                for p in proposals
            ]

        strategy = CustomStrategy(my_resolve)
        proposals = [
            make_proposal("gov_1", "government", "policy"),
            make_proposal("hh_1", "household_owner", "elevate"),
        ]
        resolutions = strategy.resolve(proposals, {})
        assert resolutions[0].approved is True  # gov
        assert resolutions[1].approved is False  # household


# ---------------------------------------------------------------------------
# Game Master
# ---------------------------------------------------------------------------

class TestGameMaster:
    def test_submit_and_resolve(self):
        gm = GameMaster()
        gm.submit_proposal(make_proposal("hh_1", "household_owner", "elevate"))
        gm.submit_proposal(make_proposal("hh_2", "household_owner", "insure"))
        resolutions = gm.resolve_phase()
        assert len(resolutions) == 2
        assert all(r.approved for r in resolutions)

    def test_resolve_with_explicit_proposals(self):
        gm = GameMaster()
        proposals = [make_proposal("hh_1", "household_owner", "elevate")]
        resolutions = gm.resolve_phase(proposals=proposals)
        assert len(resolutions) == 1

    def test_empty_proposals_returns_empty(self):
        gm = GameMaster()
        resolutions = gm.resolve_phase()
        assert len(resolutions) == 0

    def test_resolution_history(self):
        gm = GameMaster()
        gm.submit_proposal(make_proposal("hh_1", "household_owner", "elevate"))
        gm.resolve_phase()
        gm.submit_proposal(make_proposal("hh_2", "household_owner", "insure"))
        gm.resolve_phase()
        assert len(gm.resolution_history) == 2

    def test_get_resolution(self):
        gm = GameMaster()
        gm.submit_proposal(make_proposal("hh_1", "household_owner", "elevate"))
        gm.resolve_phase()
        res = gm.get_resolution("hh_1")
        assert res is not None
        assert res.agent_id == "hh_1"
        assert gm.get_resolution("unknown") is None

    def test_custom_event_statement_fn(self):
        def my_statement(resolution):
            return f"CUSTOM: {resolution.agent_id} did {resolution.original_proposal.skill_name}"

        gm = GameMaster(event_statement_fn=my_statement)
        # Use proposals that produce empty event_statement to trigger fn
        proposals = [make_proposal("hh_1", "household_owner", "elevate")]

        def no_statement_strategy(proposals, state):
            return [
                ActionResolution(
                    agent_id=p.agent_id,
                    original_proposal=p,
                    approved=True,
                    event_statement="",  # Empty → triggers custom fn
                )
                for p in proposals
            ]

        gm.strategy = CustomStrategy(no_statement_strategy)
        resolutions = gm.resolve_phase(proposals=proposals)
        assert "CUSTOM" in resolutions[0].event_statement

    def test_reset_phase_clears_proposals(self):
        gm = GameMaster()
        gm.submit_proposal(make_proposal("hh_1", "household_owner", "elevate"))
        gm.reset_phase()
        resolutions = gm.resolve_phase()
        assert len(resolutions) == 0

    def test_full_reset(self):
        gm = GameMaster()
        gm.submit_proposal(make_proposal("hh_1", "household_owner", "elevate"))
        gm.resolve_phase()
        gm.reset()
        assert len(gm.resolution_history) == 0

    def test_summary(self):
        gm = GameMaster()
        gm.submit_proposal(make_proposal("hh_1", "household_owner", "elevate"))
        gm.resolve_phase()
        s = gm.summary()
        assert s["total_resolutions"] == 1
        assert s["approved"] == 1
        assert s["denied"] == 0
        assert s["strategy"] == "PassthroughStrategy"


# ---------------------------------------------------------------------------
# MessagePool Integration
# ---------------------------------------------------------------------------

class TestGameMasterMessagePool:
    def test_broadcasts_resolutions_to_pool(self):
        pool = MessagePool()
        pool.register_agent("hh_1")
        pool.register_agent("game_master")
        gm = GameMaster(message_pool=pool)
        gm.submit_proposal(make_proposal("hh_1", "household_owner", "elevate"))
        gm.resolve_phase()
        # Resolution message should be in hh_1's mailbox
        msgs = pool.get_messages("hh_1")
        assert len(msgs) == 1
        assert msgs[0].sender_id == "game_master"
        assert msgs[0].message_type == "resolution"


# ---------------------------------------------------------------------------
# Factory Function
# ---------------------------------------------------------------------------

class TestFactory:
    def test_create_passthrough(self):
        gm = create_game_master()
        assert isinstance(gm.strategy, PassthroughStrategy)

    def test_create_conflict_aware(self):
        gm = create_game_master(
            resource_limits={"budget": 500_000},
            strategy_type="conflict_aware",
        )
        assert isinstance(gm.strategy, ConflictAwareStrategy)

    def test_create_with_message_pool(self):
        pool = MessagePool()
        gm = create_game_master(message_pool=pool)
        assert gm.message_pool is pool

    def test_create_priority_alias(self):
        gm = create_game_master(
            resource_limits={"budget": 100},
            strategy_type="priority",
        )
        assert isinstance(gm.strategy, ConflictAwareStrategy)
