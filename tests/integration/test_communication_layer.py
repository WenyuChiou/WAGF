"""Integration test for the full Communication Layer.

Tests MessagePool + ConflictResolver + GameMaster + PhaseOrchestrator
working together in a simulated multi-agent step.

Reference: Task-054 Communication Layer
"""
import pytest
from unittest.mock import MagicMock

from broker.interfaces.coordination import (
    ExecutionPhase,
    PhaseConfig,
    ActionProposal,
)
from broker.components.message_pool import MessagePool
from broker.components.message_provider import MessagePoolProvider
from broker.components.conflict_resolver import (
    ConflictDetector,
    ConflictResolver,
    PriorityResolution,
)
from broker.components.coordinator import (
    GameMaster,
    ConflictAwareStrategy,
    create_game_master,
)
from broker.components.phase_orchestrator import PhaseOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_agent(agent_type, region_id="region_A"):
    agent = MagicMock()
    agent.agent_type = agent_type
    agent.region_id = region_id
    return agent


def make_proposal(agent_id, agent_type, skill, requirements=None):
    return ActionProposal(
        agent_id=agent_id,
        agent_type=agent_type,
        skill_name=skill,
        resource_requirements=requirements or {},
    )


# ---------------------------------------------------------------------------
# Full Pipeline Integration
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """Simulate a single simulation step through all 4 modules."""

    def test_full_step_lifecycle(self):
        """
        Scenario:
        - 1 government, 1 insurance, 3 households
        - Government budget limit: 200,000
        - Two households compete for subsidies (150k each)
        - Phase orchestrator orders execution
        - Game Master resolves conflicts
        - Message pool distributes outcomes
        """
        # --- Setup agents ---
        agents = {
            "gov_1": make_agent("government"),
            "ins_1": make_agent("insurance"),
            "hh_1": make_agent("household_owner"),
            "hh_2": make_agent("household_mg_owner"),
            "hh_3": make_agent("household_owner"),
        }

        # --- 1. Phase Orchestrator: determine execution order ---
        orchestrator = PhaseOrchestrator()
        plan = orchestrator.get_execution_plan(agents)
        assert len(plan) == 4

        # Verify institutional phase has gov + ins
        inst_phase, inst_ids = plan[0]
        assert inst_phase == ExecutionPhase.INSTITUTIONAL
        assert set(inst_ids) == {"gov_1", "ins_1"}

        # Verify household phase has all households
        hh_phase, hh_ids = plan[1]
        assert hh_phase == ExecutionPhase.HOUSEHOLD
        assert set(hh_ids) == {"hh_1", "hh_2", "hh_3"}

        # --- 2. Message Pool: government broadcasts policy ---
        pool = MessagePool()
        pool.register_agents(agents)

        pool.broadcast(
            "gov_1", "government",
            "Subsidy rate increased to 75% for elevated homes",
            message_type="policy_announcement",
            timestamp=1, priority=10,
        )
        pool.broadcast(
            "ins_1", "insurance",
            "Premium rates updated for 2024",
            message_type="market_update",
            timestamp=1, priority=5,
        )

        # Verify households received both messages
        hh1_msgs = pool.get_messages("hh_1")
        assert len(hh1_msgs) == 2
        assert hh1_msgs[0].priority == 10  # Policy first (higher priority)

        # --- 3. Game Master: resolve household actions ---
        gm = create_game_master(
            resource_limits={"govt_budget": 200_000},
            message_pool=pool,
            strategy_type="conflict_aware",
        )

        # Households submit competing proposals
        gm.submit_proposals([
            make_proposal("hh_1", "household_owner", "apply_for_subsidy",
                          {"govt_budget": 150_000}),
            make_proposal("hh_2", "household_mg_owner", "apply_for_subsidy",
                          {"govt_budget": 150_000}),
            make_proposal("hh_3", "household_owner", "do_nothing", {}),
        ])

        resolutions = gm.resolve_phase(shared_state={"year": 2024})

        # hh_3 (no conflict) auto-approved
        hh3_res = next(r for r in resolutions if r.agent_id == "hh_3")
        assert hh3_res.approved is True

        # Budget conflict: 150k + 150k = 300k > 200k
        # MG household (priority 50) beats NMG (priority 10)
        hh2_res = next(r for r in resolutions if r.agent_id == "hh_2")
        hh1_res = next(r for r in resolutions if r.agent_id == "hh_1")
        assert hh2_res.approved is True  # MG household wins
        assert hh1_res.approved is False  # NMG household denied

        # --- 4. Verify resolution messages in pool ---
        # GameMaster broadcasts resolutions to affected agents
        hh1_all_msgs = pool.get_messages("hh_1")
        resolution_msgs = [m for m in hh1_all_msgs if m.message_type == "resolution"]
        assert len(resolution_msgs) >= 1

        # --- 5. Summary statistics ---
        gm_summary = gm.summary()
        assert gm_summary["total_resolutions"] == 3
        assert gm_summary["approved"] == 2
        assert gm_summary["denied"] == 1

    def test_message_provider_context_injection(self):
        """Test MessagePoolProvider injects messages into agent context."""
        pool = MessagePool()
        pool.register_agent("hh_1")
        pool.register_agent("gov_1")

        pool.broadcast("gov_1", "government", "Important policy update",
                       message_type="policy_announcement", priority=10)

        provider = MessagePoolProvider(pool, max_messages=3)
        context = {}
        provider.provide("hh_1", {}, context)

        assert "messages" in context
        assert len(context["messages"]) == 1
        assert context["messages"][0]["from"] == "government"
        assert context["messages"][0]["type"] == "policy_announcement"

    def test_ttl_lifecycle_across_steps(self):
        """Test message expiration across simulation steps."""
        pool = MessagePool()
        pool.register_agent("hh_1")
        pool.register_agent("gov_1")

        # TTL=2 message at step 0
        pool.broadcast("gov_1", "government", "Step 0 policy",
                       timestamp=0)  # Default TTL=1

        assert pool.peek_count("hh_1") == 1

        # Advance to step 1: TTL=1, (1-0)=1 >= 1 → expires
        pool.advance_step(1)
        assert pool.peek_count("hh_1") == 0

    def test_phase_orchestrator_with_custom_yaml(self, tmp_path):
        """Test custom phase configuration from YAML."""
        yaml_content = """\
phases:
  - phase: institutional
    agent_types: [government]
    ordering: sequential
  - phase: household
    agent_types: [household_owner, household_mg_owner]
    ordering: random
  - phase: resolution
    agent_types: []
    depends_on: [institutional, household]
  - phase: observation
    agent_types: []
    depends_on: [resolution]
"""
        yaml_file = tmp_path / "custom_phases.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        agents = {
            "gov_1": make_agent("government"),
            "hh_1": make_agent("household_owner"),
            "hh_2": make_agent("household_mg_owner"),
        }

        orch = PhaseOrchestrator.from_yaml(str(yaml_file), seed=42)
        plan = orch.get_execution_plan(agents)

        assert len(plan) == 4
        # Institutional phase should only have government
        inst_ids = next(ids for ph, ids in plan if ph == ExecutionPhase.INSTITUTIONAL)
        assert inst_ids == ["gov_1"]

    def test_coordinator_reset_between_steps(self):
        """Test that GameMaster properly resets between simulation steps."""
        gm = create_game_master()

        # Step 1
        gm.submit_proposal(
            make_proposal("hh_1", "household_owner", "elevate")
        )
        res1 = gm.resolve_phase()
        assert len(res1) == 1

        # Step 2: proposals should be cleared
        res2 = gm.resolve_phase()
        assert len(res2) == 0

        # History should accumulate
        assert len(gm.resolution_history) == 1


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_agents(self):
        orch = PhaseOrchestrator()
        plan = orch.get_execution_plan({})
        # All phases should have empty agent lists
        for phase, ids in plan:
            assert ids == []

    def test_no_proposals(self):
        gm = GameMaster()
        resolutions = gm.resolve_phase()
        assert resolutions == []

    def test_single_agent_no_conflict(self):
        gm = create_game_master(
            resource_limits={"budget": 100_000},
            strategy_type="conflict_aware",
        )
        gm.submit_proposal(
            make_proposal("hh_1", "household_owner", "subsidy",
                          {"budget": 50_000})
        )
        resolutions = gm.resolve_phase()
        assert len(resolutions) == 1
        assert resolutions[0].approved is True
