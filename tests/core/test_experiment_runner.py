"""
Tests for broker.core.experiment — ExperimentRunner and ExperimentConfig.

Covers: single-year execution, hook ordering, phase partitioning,
parallel workers, memory persistence, and error handling.

These tests use mocked SkillBrokerEngine to isolate orchestration logic
from LLM/parsing/governance concerns.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call, PropertyMock
from dataclasses import dataclass
from typing import Dict, Any, List

from broker.core.experiment import ExperimentRunner, ExperimentConfig
from broker.interfaces.skill_types import (
    SkillProposal, ApprovedSkill, SkillBrokerResult,
    SkillOutcome, ExecutionResult,
)
from broker.components.memory_engine import WindowMemoryEngine
from cognitive_governance.agents import BaseAgent, AgentConfig, StateParam


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(agent_id: str, agent_type: str = "household") -> BaseAgent:
    config = AgentConfig(
        name=agent_id,
        agent_type=agent_type,
        state_params=[
            StateParam(name="savings", raw_range=(0, 100000), initial_raw=50000),
        ],
        objectives=[], constraints=[], skills=[],
    )
    return BaseAgent(config)


def _make_approved_result(agent_id: str, skill_name: str = "do_nothing",
                          state_changes: Dict = None) -> SkillBrokerResult:
    """Create a minimal APPROVED SkillBrokerResult."""
    return SkillBrokerResult(
        outcome=SkillOutcome.APPROVED,
        skill_proposal=SkillProposal(
            skill_name=skill_name, agent_id=agent_id, reasoning={}
        ),
        approved_skill=ApprovedSkill(
            skill_name=skill_name, agent_id=agent_id,
            approval_status="APPROVED", execution_mapping="sim.noop",
        ),
        execution_result=ExecutionResult(
            success=True, state_changes=state_changes or {}
        ),
        validation_errors=[], retry_count=0,
    )


def _make_rejected_result(agent_id: str) -> SkillBrokerResult:
    """Create a minimal REJECTED SkillBrokerResult."""
    return SkillBrokerResult(
        outcome=SkillOutcome.REJECTED,
        skill_proposal=SkillProposal(
            skill_name="do_nothing", agent_id=agent_id, reasoning={}
        ),
        approved_skill=ApprovedSkill(
            skill_name="do_nothing", agent_id=agent_id,
            approval_status="REJECTED", execution_mapping="sim.noop",
        ),
        execution_result=None,
        validation_errors=["blocked"], retry_count=3,
    )


def _make_mock_broker(return_results=None):
    """Create a mocked SkillBrokerEngine.

    Args:
        return_results: dict mapping agent_id → SkillBrokerResult.
                        If None, returns APPROVED do_nothing for any agent.
    """
    broker = MagicMock()
    broker.log_prompt = False

    # Mock the audit writer
    broker.audit_writer = MagicMock()
    broker.auditor = MagicMock()

    # Mock model_adapter for schema validation
    broker.model_adapter = MagicMock()
    broker.model_adapter.agent_config = None  # skip schema validation

    # Mock context builder — return unique context per agent to prevent cache collisions
    ctx_builder = MagicMock()
    call_counter = {"n": 0}
    def _build_context(agent_id, **kwargs):
        call_counter["n"] += 1
        return {"state": {"_call": call_counter["n"]}, "agent_id": agent_id}
    ctx_builder.build.side_effect = _build_context
    broker.context_builder = ctx_builder

    # Mock config
    broker.config = MagicMock()
    broker.config.get_llm_params.return_value = {}

    def process_step_side_effect(agent_id, **kwargs):
        if return_results and agent_id in return_results:
            return return_results[agent_id]
        return _make_approved_result(agent_id)

    broker.process_step.side_effect = process_step_side_effect
    return broker


# ---------------------------------------------------------------------------
# ExperimentConfig
# ---------------------------------------------------------------------------

class TestExperimentConfig:
    """Tests for ExperimentConfig dataclass."""

    def test_defaults(self):
        cfg = ExperimentConfig()
        assert cfg.num_years == 1
        assert cfg.workers == 1
        assert cfg.seed == 42
        assert cfg.phase_order is None

    def test_custom_values(self):
        cfg = ExperimentConfig(
            model="gemma3:4b", num_years=5, workers=4,
            seed=123, phase_order=[["type_a"], ["type_b"]],
        )
        assert cfg.model == "gemma3:4b"
        assert cfg.num_years == 5
        assert cfg.workers == 4
        assert cfg.phase_order == [["type_a"], ["type_b"]]


# ---------------------------------------------------------------------------
# Single-year execution
# ---------------------------------------------------------------------------

class TestSingleYearExecution:
    """Tests for basic 1-year experiment completion."""

    def test_single_year_completes(self, tmp_path):
        agents = {"a1": _make_agent("a1")}
        broker = _make_mock_broker()
        config = ExperimentConfig(num_years=1, output_dir=tmp_path)
        runner = ExperimentRunner(
            broker=broker, sim_engine=MagicMock(advance_year=lambda: {"current_year": 1}),
            agents=agents, config=config,
        )
        # Patch llm_invoke to avoid real LLM creation
        mock_invoke = MagicMock(return_value='{"decision": "do_nothing"}')
        runner.run(llm_invoke=mock_invoke)

        assert broker.process_step.call_count == 1

    def test_multi_year_processes_all_agents(self, tmp_path):
        agents = {f"a{i}": _make_agent(f"a{i}") for i in range(3)}
        broker = _make_mock_broker()
        config = ExperimentConfig(num_years=2, output_dir=tmp_path)
        sim = MagicMock()
        sim.advance_year.return_value = {"current_year": 1}
        runner = ExperimentRunner(
            broker=broker, sim_engine=sim,
            agents=agents, config=config,
        )
        runner.run(llm_invoke=MagicMock())

        # 3 agents × 2 years = 6 calls
        assert broker.process_step.call_count == 6


# ---------------------------------------------------------------------------
# Hook execution ordering
# ---------------------------------------------------------------------------

class TestHookOrdering:
    """Tests for lifecycle hook execution sequence."""

    def test_pre_and_post_year_hooks_called(self, tmp_path):
        hook_log = []
        agents = {"a1": _make_agent("a1")}
        broker = _make_mock_broker()
        config = ExperimentConfig(num_years=2, output_dir=tmp_path)

        runner = ExperimentRunner(
            broker=broker,
            sim_engine=MagicMock(advance_year=lambda: {}),
            agents=agents, config=config,
            hooks={
                "pre_year": lambda yr, env, ags: hook_log.append(("pre", yr)),
                "post_year": lambda yr, ags: hook_log.append(("post", yr)),
            }
        )
        runner.run(llm_invoke=MagicMock())

        assert hook_log == [("pre", 1), ("post", 1), ("pre", 2), ("post", 2)]

    def test_post_step_hook_called_per_agent(self, tmp_path):
        step_agents = []
        agents = {"a1": _make_agent("a1"), "a2": _make_agent("a2")}
        broker = _make_mock_broker()
        config = ExperimentConfig(num_years=1, output_dir=tmp_path)

        runner = ExperimentRunner(
            broker=broker,
            sim_engine=MagicMock(advance_year=lambda: {}),
            agents=agents, config=config,
            hooks={
                "post_step": lambda agent, result: step_agents.append(agent.id),
            }
        )
        runner.run(llm_invoke=MagicMock())

        assert len(step_agents) == 2
        assert set(step_agents) == {"a1", "a2"}

    def test_rejected_result_still_triggers_post_step(self, tmp_path):
        """REJECTED outcomes must still trigger post_step for audit tracking."""
        post_step_called = []
        agents = {"a1": _make_agent("a1")}
        broker = _make_mock_broker({"a1": _make_rejected_result("a1")})
        config = ExperimentConfig(num_years=1, output_dir=tmp_path)

        runner = ExperimentRunner(
            broker=broker,
            sim_engine=MagicMock(advance_year=lambda: {}),
            agents=agents, config=config,
            hooks={
                "post_step": lambda agent, result: post_step_called.append(
                    (agent.id, result.outcome)
                ),
            }
        )
        runner.run(llm_invoke=MagicMock())

        assert len(post_step_called) == 1
        assert post_step_called[0] == ("a1", SkillOutcome.REJECTED)


# ---------------------------------------------------------------------------
# Phase partitioning
# ---------------------------------------------------------------------------

class TestPhasePartitioning:
    """Tests for _partition_by_phase."""

    def test_single_phase_default(self, tmp_path):
        """Without phase_order, all agents run in one phase."""
        agents = [_make_agent("a1", "alpha"), _make_agent("a2", "beta")]
        broker = _make_mock_broker()
        config = ExperimentConfig(output_dir=tmp_path)  # No phase_order
        runner = ExperimentRunner(
            broker=broker,
            sim_engine=MagicMock(advance_year=lambda: {}),
            agents={"a1": agents[0], "a2": agents[1]}, config=config,
        )
        phases = runner._partition_by_phase(agents)
        assert len(phases) == 1  # Single phase
        assert len(phases[0]) == 2

    def test_two_phases_correct_ordering(self, tmp_path):
        agents = [
            _make_agent("a1", "government"),
            _make_agent("a2", "household"),
            _make_agent("a3", "household"),
        ]
        broker = _make_mock_broker()
        config = ExperimentConfig(
            output_dir=tmp_path,
            phase_order=[["government"], ["household"]],
        )
        runner = ExperimentRunner(
            broker=broker,
            sim_engine=MagicMock(advance_year=lambda: {}),
            agents={a.id: a for a in agents}, config=config,
        )
        phases = runner._partition_by_phase(agents)
        assert len(phases) == 2
        assert [a.agent_type for a in phases[0]] == ["government"]
        assert len(phases[1]) == 2
        assert all(a.agent_type == "household" for a in phases[1])

    def test_unmatched_agents_appended(self, tmp_path):
        agents = [
            _make_agent("a1", "government"),
            _make_agent("a2", "unknown_type"),
        ]
        broker = _make_mock_broker()
        config = ExperimentConfig(
            output_dir=tmp_path,
            phase_order=[["government"]],
        )
        runner = ExperimentRunner(
            broker=broker,
            sim_engine=MagicMock(advance_year=lambda: {}),
            agents={a.id: a for a in agents}, config=config,
        )
        phases = runner._partition_by_phase(agents)
        # 1 configured phase + 1 unmatched phase
        assert len(phases) == 2
        assert phases[1][0].agent_type == "unknown_type"


# ---------------------------------------------------------------------------
# Phase execution ordering (integration within run)
# ---------------------------------------------------------------------------

class TestPhaseExecution:
    """Verify phases execute sequentially during run()."""

    def test_phases_execute_in_order(self, tmp_path):
        execution_order = []
        a_gov = _make_agent("gov1", "government")
        a_hh = _make_agent("hh1", "household")

        def track_process_step(agent_id, **kwargs):
            execution_order.append(agent_id)
            return _make_approved_result(agent_id)

        broker = _make_mock_broker()
        broker.process_step.side_effect = track_process_step

        config = ExperimentConfig(
            num_years=1, output_dir=tmp_path,
            phase_order=[["government"], ["household"]],
        )
        runner = ExperimentRunner(
            broker=broker,
            sim_engine=MagicMock(advance_year=lambda: {}),
            agents={"gov1": a_gov, "hh1": a_hh}, config=config,
        )
        runner.run(llm_invoke=MagicMock())

        assert execution_order == ["gov1", "hh1"]


# ---------------------------------------------------------------------------
# State changes
# ---------------------------------------------------------------------------

class TestStateChanges:
    """Tests for _apply_state_changes."""

    def test_approved_result_applies_state(self, tmp_path):
        agent = _make_agent("a1")
        result = _make_approved_result("a1", state_changes={"elevated": True})

        broker = _make_mock_broker({"a1": result})
        config = ExperimentConfig(num_years=1, output_dir=tmp_path)
        runner = ExperimentRunner(
            broker=broker,
            sim_engine=MagicMock(advance_year=lambda: {}),
            agents={"a1": agent}, config=config,
        )
        runner.run(llm_invoke=MagicMock())

        assert agent.dynamic_state.get("elevated") is True

    def test_rejected_result_no_state_change(self, tmp_path):
        agent = _make_agent("a1")
        original_state = dict(agent.dynamic_state)
        result = _make_rejected_result("a1")

        broker = _make_mock_broker({"a1": result})
        config = ExperimentConfig(num_years=1, output_dir=tmp_path)
        runner = ExperimentRunner(
            broker=broker,
            sim_engine=MagicMock(advance_year=lambda: {}),
            agents={"a1": agent}, config=config,
        )
        runner.run(llm_invoke=MagicMock())

        assert agent.dynamic_state == original_state


# ---------------------------------------------------------------------------
# Inactive agents
# ---------------------------------------------------------------------------

class TestInactiveAgents:
    """Tests for agent filtering."""

    def test_inactive_agents_skipped(self, tmp_path):
        a1 = _make_agent("a1")
        a2 = _make_agent("a2")
        a2.is_active = False  # Mark inactive

        broker = _make_mock_broker()
        config = ExperimentConfig(num_years=1, output_dir=tmp_path)
        runner = ExperimentRunner(
            broker=broker,
            sim_engine=MagicMock(advance_year=lambda: {}),
            agents={"a1": a1, "a2": a2}, config=config,
        )
        runner.run(llm_invoke=MagicMock())

        # Only a1 should be processed
        assert broker.process_step.call_count == 1
        assert broker.process_step.call_args[1]["agent_id"] == "a1"
