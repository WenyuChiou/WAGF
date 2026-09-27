"""Generic opt-out for the runner's own decision/fallback memory line.

``ExperimentRunner._apply_state_changes`` writes a generic "legacy immediate
memory" line every period ("Year N: Decided to: X" on approved rows, "Year N:
default action applied: X" / the neutral rejection line on fallback rows).
Irrigation's ``pre_year`` hook (``build_action_outcome_feedback``,
``examples/irrigation_abm/run_experiment.py``) already writes its own domain
outcome line describing the executed action and the rule, so the generic line
doubled every year up in the composed 5-recent-memory retrieval window,
covering ~2.5 years of history instead of 5 (2026-09-26 finding).

Flood already solves the same duplication problem with a DIFFERENT mechanism
(``DecisionFilteredMemoryEngine``, ``examples/single_agent/run_flood.py``),
which filters these lines back OUT after they are written. This test file
covers a second, generic mechanism: ``agent.memory_config["runner_decision_line"]``
(from the agent type's YAML ``memory:`` block), which skips writing the line
at all. Default True: every existing run (including flood, which never sets
this key) is byte-identical to before this opt-out existed.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from broker.agents import AgentConfig, BaseAgent
from broker.components.governance.registry import SkillRegistry
from broker.core.experiment_runner import ExperimentConfig, ExperimentRunner
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import (
    ExecutionResult, SkillDefinition, SkillProposal, ValidationResult,
)
from broker.utils.model_adapter import UnifiedAdapter

PROPOSED = "take_action"
DEFAULT_SKILL = "default_action"


class _Ctx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "PROMPT"


class _Sim:
    """The default skill resets `holds_policy` to False (a per-period
    lapse); the proposed skill sets it True."""

    def __init__(self):
        self.executed = []

    def execute_skill(self, approved_skill):
        self.executed.append(approved_skill.skill_name)
        if approved_skill.skill_name == PROPOSED:
            return ExecutionResult(success=True, state_changes={"holds_policy": True})
        return ExecutionResult(success=True, state_changes={"holds_policy": False})


class _Writer:
    def __init__(self):
        self.traces = []

    def write_trace(self, agent_type, trace, history):
        self.traces.append(trace)


def _engine(*, blocked: bool):
    registry = SkillRegistry()
    for sid in (PROPOSED, DEFAULT_SKILL):
        registry.register(SkillDefinition(
            skill_id=sid, description=sid, eligible_agent_types=["*"],
            preconditions=[], institutional_constraints={},
            allowed_state_changes=[], implementation_mapping=sid,
        ))
    registry.set_default_skill(DEFAULT_SKILL)

    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    adapter.parse_output = lambda *_a, **_k: SkillProposal(
        skill_name=PROPOSED, agent_id="A1", reasoning={}, parse_layer="mock",
    )

    validator = MagicMock()
    validator.validate.side_effect = lambda *_a, **_k: ValidationResult(
        valid=not blocked, validator_name="AgentValidator:thinking_error",
        errors=["blocked"] if blocked else [],
        metadata={"rules_hit": ["r1"], "level": "ERROR"} if blocked else {})

    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_governance_retries.return_value = 2
    config.get_governance_max_reports.return_value = 3
    config.get_multi_skill_config.return_value = {}
    config.get_audit_executed_columns.return_value = True
    config.get_governance_on_retry_exhausted.return_value = "default"
    config.get_parsing_config.return_value = {}

    sim = _Sim()
    eng = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[validator],
        simulation_engine=sim, context_builder=_Ctx(), config=config,
    )
    writer = _Writer()
    eng.audit_writer = writer
    return eng, sim, writer


def _agent(holds_policy=True, memory_config=None):
    agent = BaseAgent(AgentConfig(
        name="A1", agent_type="agent", state_params=[], objectives=[],
        constraints=[], skills=[],
    ))
    agent.holds_policy = holds_policy
    if memory_config is not None:
        agent.memory_config = memory_config
    return agent


class _World:
    def advance_year(self):
        return {}


def _run_one_period(tmp_path, agent, result):
    runner = ExperimentRunner(
        broker=MagicMock(log_prompt=False),
        sim_engine=_World(),
        agents={agent.id: agent},
        config=ExperimentConfig(output_dir=tmp_path, num_years=1),
    )
    runner._resolve_declared_deciders = lambda: None
    runner._run_agents_sequential = lambda agents, run_id, llm, env: [(agent, result)]
    runner._finalize_step = lambda step: None
    runner._finalize_experiment = lambda n: None
    runner.run()
    return runner


def _broker_result(*, blocked):
    eng, sim, writer = _engine(blocked=blocked)
    result = eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                              llm_invoke=lambda p: "raw", agent_type="agent")
    return result, sim, writer


def _memories(runner, agent):
    return [m.get("content") if isinstance(m, dict) else str(m)
            for m in runner.memory_engine.retrieve(agent, top_k=10)]


# Default (no memory_config, and memory_config without the key) --------------

def test_default_writes_approved_decision_line(tmp_path):
    result, sim, _ = _broker_result(blocked=False)
    assert sim.executed == [PROPOSED]
    agent = _agent(holds_policy=False)
    runner = _run_one_period(tmp_path, agent, result)
    assert agent.holds_policy is True
    assert agent._last_action_context == {"skill_name": PROPOSED, "year": 1}
    assert any("Decided to: Take action" in m for m in _memories(runner, agent))


def test_default_writes_fallback_line(tmp_path):
    result, sim, _ = _broker_result(blocked=True)
    assert sim.executed == [DEFAULT_SKILL]
    agent = _agent(holds_policy=True)
    runner = _run_one_period(tmp_path, agent, result)
    assert agent.holds_policy is False
    mems = _memories(runner, agent)
    assert any("default action applied: Default action" in m for m in mems), mems


def test_memory_config_without_key_still_defaults_true(tmp_path):
    """An agent type with SOME memory config, just not this key, keeps the
    line (e.g. flood's rejection_line_style block never sets this key)."""
    result, _, _ = _broker_result(blocked=False)
    agent = _agent(holds_policy=False, memory_config={"rejection_line_style": "neutral"})
    runner = _run_one_period(tmp_path, agent, result)
    assert any("Decided to:" in m for m in _memories(runner, agent))


# Opt-out (memory.runner_decision_line: false) --------------------------------

def test_optout_writes_no_line_on_approved_row_but_still_applies_state(tmp_path):
    result, sim, _ = _broker_result(blocked=False)
    assert sim.executed == [PROPOSED]
    agent = _agent(holds_policy=False, memory_config={"runner_decision_line": False})
    runner = _run_one_period(tmp_path, agent, result)

    # State and action context are unaffected by the opt-out.
    assert agent.holds_policy is True
    assert agent._last_action_context == {"skill_name": PROPOSED, "year": 1}
    # No generic memory line at all.
    assert _memories(runner, agent) == []


def test_optout_writes_no_line_on_fallback_row_but_still_applies_state(tmp_path):
    result, sim, _ = _broker_result(blocked=True)
    assert sim.executed == [DEFAULT_SKILL]
    agent = _agent(holds_policy=True, memory_config={"runner_decision_line": False})
    runner = _run_one_period(tmp_path, agent, result)

    assert agent.holds_policy is False
    ctx = agent._last_action_context
    assert ctx["skill_name"] == DEFAULT_SKILL
    assert ctx["was_fallback"] is True
    assert ctx["proposed_skill"] == PROPOSED
    assert _memories(runner, agent) == []


def test_optout_false_suppresses_both_decided_and_fallback_markers(tmp_path):
    """Belt-and-suspenders: neither marker substring ever appears, on either
    row shape, when the opt-out is set."""
    for blocked in (False, True):
        result, _, _ = _broker_result(blocked=blocked)
        agent = _agent(holds_policy=True, memory_config={"runner_decision_line": False})
        runner = _run_one_period(tmp_path, agent, result)
        mems = _memories(runner, agent)
        assert not any("Decided to:" in m for m in mems), mems
        assert not any("default action applied:" in m for m in mems), mems


def test_non_bool_runner_decision_line_raises_instead_of_silently_truthy(tmp_path):
    """A quoted YAML string like "false" is a non-empty Python str -- truthy
    if merely `if not runner_decision_line` were checked without a type
    guard, which would silently KEEP writing the generic line despite the
    author's evident intent. Fail loud instead, matching the sibling
    rejection_line_style guard a few lines up in the same function."""
    import pytest

    result, _, _ = _broker_result(blocked=False)
    agent = _agent(holds_policy=False, memory_config={"runner_decision_line": "false"})
    with pytest.raises(ValueError, match="runner_decision_line"):
        _run_one_period(tmp_path, agent, result)
