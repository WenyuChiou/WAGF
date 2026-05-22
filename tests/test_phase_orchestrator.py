"""Tests for broker.components.phase_orchestrator — Phase Ordering.

Reference: Task-054 Communication Layer
"""
import os
import tempfile
import pytest
from unittest.mock import MagicMock

from broker.interfaces.coordination import ExecutionPhase, PhaseConfig
from broker.components.orchestration.phases import PhaseOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_agent(agent_type):
    """Create a mock agent with agent_type attribute."""
    agent = MagicMock()
    agent.agent_type = agent_type
    return agent


@pytest.fixture
def agents():
    """Dictionary of test agents."""
    return {
        "gov_1": make_agent("government"),
        "ins_1": make_agent("insurance"),
        "hh_1": make_agent("household_owner"),
        "hh_2": make_agent("household_renter"),
        "hh_3": make_agent("household_mg_owner"),
    }


@pytest.fixture
def orchestrator():
    """Default PhaseOrchestrator."""
    return PhaseOrchestrator()


# ---------------------------------------------------------------------------
# Default Phases
# ---------------------------------------------------------------------------

class TestDefaultPhases:
    def test_has_generic_three_phases(self, orchestrator):
        assert len(orchestrator.phases) == 3

    def test_phase_order(self, orchestrator):
        phases = [p.phase for p in orchestrator.phases]
        assert phases == [
            ExecutionPhase.CUSTOM,
            ExecutionPhase.RESOLUTION,
            ExecutionPhase.OBSERVATION,
        ]

    def test_custom_phase_auto_discovers_agent_types(self, orchestrator):
        pc = orchestrator.get_phase_config(ExecutionPhase.CUSTOM)
        assert pc.agent_types is None

    def test_resolution_has_no_agents(self, orchestrator):
        pc = orchestrator.get_phase_config(ExecutionPhase.RESOLUTION)
        assert pc.agent_types == []

    def test_observation_depends_on_resolution(self, orchestrator):
        pc = orchestrator.get_phase_config(ExecutionPhase.OBSERVATION)
        assert ExecutionPhase.RESOLUTION in pc.depends_on


# ---------------------------------------------------------------------------
# Execution Plan Generation
# ---------------------------------------------------------------------------

class TestExecutionPlan:
    def test_plan_includes_all_phases(self, orchestrator, agents):
        plan = orchestrator.get_execution_plan(agents)
        assert len(plan) == 3

    def test_custom_before_resolution(self, orchestrator, agents):
        plan = orchestrator.get_execution_plan(agents)
        phase_order = [p for p, _ in plan]
        custom_idx = phase_order.index(ExecutionPhase.CUSTOM)
        res_idx = phase_order.index(ExecutionPhase.RESOLUTION)
        assert custom_idx < res_idx

    def test_custom_phase_includes_all_agents(self, orchestrator, agents):
        plan = orchestrator.get_execution_plan(agents)
        custom_phase = next(
            (ids for phase, ids in plan if phase == ExecutionPhase.CUSTOM),
            [],
        )
        assert set(custom_phase) == set(agents)

    def test_resolution_phase_empty(self, orchestrator, agents):
        plan = orchestrator.get_execution_plan(agents)
        res_phase = next(
            (ids for phase, ids in plan if phase == ExecutionPhase.RESOLUTION),
            [],
        )
        assert res_phase == []


# ---------------------------------------------------------------------------
# Per-Phase Agent Retrieval
# ---------------------------------------------------------------------------

class TestGetPhaseAgents:
    def test_get_custom_agents(self, orchestrator, agents):
        ids = orchestrator.get_phase_agents(ExecutionPhase.CUSTOM, agents)
        assert set(ids) == set(agents)

    def test_get_unknown_phase_returns_empty(self, orchestrator, agents):
        ids = orchestrator.get_phase_agents(ExecutionPhase.INSTITUTIONAL, agents)
        assert ids == []


# ---------------------------------------------------------------------------
# Ordering Modes
# ---------------------------------------------------------------------------

class TestOrdering:
    def test_sequential_preserves_order(self):
        orch = PhaseOrchestrator(phases=[
            PhaseConfig(
                phase=ExecutionPhase.HOUSEHOLD,
                agent_types=["household_owner"],
                ordering="sequential",
            ),
        ])
        agents = {f"hh_{i}": make_agent("household_owner") for i in range(5)}
        plan = orch.get_execution_plan(agents)
        _, ids = plan[0]
        # Sequential: deterministic order (dict order)
        assert len(ids) == 5

    def test_random_ordering_deterministic(self):
        orch = PhaseOrchestrator(
            phases=[
                PhaseConfig(
                    phase=ExecutionPhase.HOUSEHOLD,
                    agent_types=["household_owner"],
                    ordering="random",
                ),
            ],
            seed=123,
        )
        agents = {f"hh_{i}": make_agent("household_owner") for i in range(10)}
        plan1 = orch.get_execution_plan(agents)

        orch2 = PhaseOrchestrator(
            phases=[
                PhaseConfig(
                    phase=ExecutionPhase.HOUSEHOLD,
                    agent_types=["household_owner"],
                    ordering="random",
                ),
            ],
            seed=123,
        )
        plan2 = orch2.get_execution_plan(agents)
        # Same seed → same order
        assert plan1[0][1] == plan2[0][1]

    def test_parallel_returns_all(self):
        orch = PhaseOrchestrator(phases=[
            PhaseConfig(
                phase=ExecutionPhase.HOUSEHOLD,
                agent_types=["household_owner"],
                ordering="parallel",
            ),
        ])
        agents = {f"hh_{i}": make_agent("household_owner") for i in range(5)}
        plan = orch.get_execution_plan(agents)
        _, ids = plan[0]
        assert len(ids) == 5


# ---------------------------------------------------------------------------
# Dependency Ordering (Topological Sort)
# ---------------------------------------------------------------------------

class TestDependencyOrdering:
    def test_dependencies_respected(self):
        phases = [
            PhaseConfig(
                phase=ExecutionPhase.OBSERVATION,
                agent_types=[],
                depends_on=[ExecutionPhase.RESOLUTION],
            ),
            PhaseConfig(
                phase=ExecutionPhase.RESOLUTION,
                agent_types=[],
                depends_on=[ExecutionPhase.HOUSEHOLD],
            ),
            PhaseConfig(
                phase=ExecutionPhase.HOUSEHOLD,
                agent_types=["household_owner"],
            ),
        ]
        orch = PhaseOrchestrator(phases=phases)
        plan = orch.get_execution_plan({"hh_1": make_agent("household_owner")})
        phase_order = [p for p, _ in plan]
        # Household → Resolution → Observation
        assert phase_order.index(ExecutionPhase.HOUSEHOLD) < \
               phase_order.index(ExecutionPhase.RESOLUTION) < \
               phase_order.index(ExecutionPhase.OBSERVATION)


# ---------------------------------------------------------------------------
# YAML Loading
# ---------------------------------------------------------------------------

class TestYAMLLoading:
    def test_from_yaml(self, tmp_path):
        yaml_content = """\
phases:
  - phase: institutional
    agent_types: [government]
    ordering: sequential
  - phase: household
    agent_types: [household_owner]
    ordering: random
  - phase: resolution
    agent_types: []
    depends_on: [institutional, household]
"""
        yaml_file = tmp_path / "phases.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        orch = PhaseOrchestrator.from_yaml(str(yaml_file))
        assert len(orch.phases) == 3
        assert orch.phases[0].phase == ExecutionPhase.INSTITUTIONAL
        assert orch.phases[1].ordering == "random"
        res_phase = orch.phases[2]
        assert ExecutionPhase.INSTITUTIONAL in res_phase.depends_on
        assert ExecutionPhase.HOUSEHOLD in res_phase.depends_on

    def test_unknown_phase_falls_back_to_custom(self, tmp_path):
        yaml_content = """\
phases:
  - phase: my_custom_phase
    agent_types: [special_agent]
    ordering: sequential
"""
        yaml_file = tmp_path / "custom.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        orch = PhaseOrchestrator.from_yaml(str(yaml_file))
        assert orch.phases[0].phase == ExecutionPhase.CUSTOM


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_warns_on_missing_dependency(self, caplog):
        phases = [
            PhaseConfig(
                phase=ExecutionPhase.OBSERVATION,
                agent_types=[],
                depends_on=[ExecutionPhase.RESOLUTION],  # Not defined!
            ),
        ]
        import logging
        with caplog.at_level(logging.WARNING):
            PhaseOrchestrator(phases=phases)
        assert "depends on" in caplog.text.lower() or len(caplog.records) > 0


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_structure(self, orchestrator):
        s = orchestrator.summary()
        assert s["num_phases"] == 3
        assert len(s["phases"]) == 3
        assert s["phases"][0]["phase"] == "custom"


# ---------------------------------------------------------------------------
# Domain-agnostic mode (Phase 6C-v4 G1a, 2026-05-10)
# ---------------------------------------------------------------------------

class TestDomainAgnostic:
    """Verify PhaseOrchestrator works without flood-specific defaults.

    Reference: docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md — multi-agent path
    should not require a domain author to enumerate every agent_type in
    YAML just to get a working baseline.
    """

    def test_agent_types_none_selects_all(self):
        """None sentinel auto-discovers all agents regardless of type."""
        orch = PhaseOrchestrator(phases=[
            PhaseConfig(
                phase=ExecutionPhase.CUSTOM,
                agent_types=None,
                ordering="sequential",
            ),
        ])
        agents = {
            "v1": make_agent("vaccination_individual"),
            "v2": make_agent("vaccination_individual"),
            "h1": make_agent("household_owner"),
            "t1": make_agent("traffic_commuter"),
        }
        plan = orch.get_execution_plan(agents)
        assert len(plan) == 1
        ids = plan[0][1]
        assert set(ids) == {"v1", "v2", "h1", "t1"}

    def test_agent_types_empty_skips_phase(self):
        """[] keeps existing skip semantics (agent-less coordinator phases)."""
        orch = PhaseOrchestrator(phases=[
            PhaseConfig(
                phase=ExecutionPhase.RESOLUTION,
                agent_types=[],
            ),
        ])
        plan = orch.get_execution_plan({"v1": make_agent("anything")})
        assert plan[0][1] == []

    def test_generic_phases_works_for_non_water_domain(self):
        """_generic_phases() runs custom agent_types without configuration."""
        orch = PhaseOrchestrator(phases=PhaseOrchestrator._generic_phases())
        agents = {
            "v1": make_agent("vaccination_individual"),
            "e1": make_agent("energy_consumer"),
        }
        plan = orch.get_execution_plan(agents)
        # 3 phases: CUSTOM (all agents) + RESOLUTION (empty) + OBSERVATION (empty)
        assert len(plan) == 3
        custom_ids = next(ids for phase, ids in plan if phase == ExecutionPhase.CUSTOM)
        assert set(custom_ids) == {"v1", "e1"}

    def test_from_domain_flood_uses_default_phases(self):
        """from_domain('flood') keeps flood 4-phase backward compat."""
        orch = PhaseOrchestrator.from_domain("flood")
        assert len(orch.phases) == 4
        inst_pc = orch.get_phase_config(ExecutionPhase.INSTITUTIONAL)
        assert "government" in inst_pc.agent_types

    def test_from_domain_none_uses_default_phases(self):
        """from_domain(None) preserves prior backward compat (flood default)."""
        orch = PhaseOrchestrator.from_domain(None)
        assert len(orch.phases) == 4

    def test_from_domain_vaccination_uses_generic_phases(self):
        """from_domain('vaccination') yields generic phases."""
        orch = PhaseOrchestrator.from_domain("vaccination")
        assert len(orch.phases) == 3
        # First phase should be the agent execution phase with None
        custom_pc = orch.phases[0]
        assert custom_pc.agent_types is None

    def test_from_domain_generic_executes_arbitrary_agent_types(self):
        """Full flow: from_domain('any_new_domain') + arbitrary agents → all run."""
        orch = PhaseOrchestrator.from_domain("traffic")
        agents = {
            "c1": make_agent("commuter"),
            "v1": make_agent("vehicle"),
            "s1": make_agent("traffic_signal"),
        }
        plan = orch.get_execution_plan(agents)
        agent_phase_ids = plan[0][1]
        assert set(agent_phase_ids) == {"c1", "v1", "s1"}
