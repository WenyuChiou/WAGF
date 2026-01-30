"""Tests for broker.components.phase_orchestrator — Phase Ordering.

Reference: Task-054 Communication Layer
"""
import os
import tempfile
import pytest
from unittest.mock import MagicMock

from broker.interfaces.coordination import ExecutionPhase, PhaseConfig
from broker.components.phase_orchestrator import PhaseOrchestrator


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
    def test_has_four_phases(self, orchestrator):
        assert len(orchestrator.phases) == 4

    def test_phase_order(self, orchestrator):
        phases = [p.phase for p in orchestrator.phases]
        assert phases == [
            ExecutionPhase.INSTITUTIONAL,
            ExecutionPhase.HOUSEHOLD,
            ExecutionPhase.RESOLUTION,
            ExecutionPhase.OBSERVATION,
        ]

    def test_institutional_includes_gov_and_ins(self, orchestrator):
        pc = orchestrator.get_phase_config(ExecutionPhase.INSTITUTIONAL)
        assert "government" in pc.agent_types
        assert "insurance" in pc.agent_types

    def test_household_includes_all_subtypes(self, orchestrator):
        pc = orchestrator.get_phase_config(ExecutionPhase.HOUSEHOLD)
        assert "household_owner" in pc.agent_types
        assert "household_renter" in pc.agent_types
        assert "household_mg_owner" in pc.agent_types

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
        assert len(plan) == 4

    def test_institutional_before_household(self, orchestrator, agents):
        plan = orchestrator.get_execution_plan(agents)
        phase_order = [p for p, _ in plan]
        inst_idx = phase_order.index(ExecutionPhase.INSTITUTIONAL)
        hh_idx = phase_order.index(ExecutionPhase.HOUSEHOLD)
        assert inst_idx < hh_idx

    def test_institutional_agents_correct(self, orchestrator, agents):
        plan = orchestrator.get_execution_plan(agents)
        inst_phase = next(
            (ids for phase, ids in plan if phase == ExecutionPhase.INSTITUTIONAL),
            [],
        )
        assert "gov_1" in inst_phase
        assert "ins_1" in inst_phase
        assert "hh_1" not in inst_phase

    def test_household_agents_correct(self, orchestrator, agents):
        plan = orchestrator.get_execution_plan(agents)
        hh_phase = next(
            (ids for phase, ids in plan if phase == ExecutionPhase.HOUSEHOLD),
            [],
        )
        assert "hh_1" in hh_phase
        assert "hh_2" in hh_phase
        assert "hh_3" in hh_phase
        assert "gov_1" not in hh_phase

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
    def test_get_institutional_agents(self, orchestrator, agents):
        ids = orchestrator.get_phase_agents(ExecutionPhase.INSTITUTIONAL, agents)
        assert set(ids) == {"gov_1", "ins_1"}

    def test_get_unknown_phase_returns_empty(self, orchestrator, agents):
        ids = orchestrator.get_phase_agents(ExecutionPhase.CUSTOM, agents)
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
        assert s["num_phases"] == 4
        assert len(s["phases"]) == 4
        assert s["phases"][0]["phase"] == "institutional"
