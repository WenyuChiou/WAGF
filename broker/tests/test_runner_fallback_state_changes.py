"""Rejected rows whose fallback skill EXECUTED must have that execution applied.

Audit finding F06 + F20 (2026-09-25). On REJECTED / UNCERTAIN results
`SkillBrokerEngine.process_step` runs the registry default skill as a fallback
(on_retry_exhausted = default), but `ExperimentRunner.run` used to `continue`
straight past `_apply_state_changes` for those rows. Two effects:

  (a) the fallback's `state_changes` were thrown away, so a per-period reset
      the default skill performs (e.g. a lapse of a held policy) never happened;
  (b) `agent._last_action_context` kept an OLDER approved action, so a domain
      memory line next period said "You chose to <stale action>".

Design (runner owns state application): on every row where a skill actually
executed the runner applies `execution_result.state_changes` once and sets
`_last_action_context` from the EXECUTED skill, flagged `was_fallback`. Audit
rows keep the blocked proposal (`final_skill` semantics, docs/AUDIT_SCHEMA.md).

These tests drive a real `SkillBrokerEngine.process_step` into the real
`ExperimentRunner.run` result loop, so they fail on the pre-fix runner.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from broker.agents import AgentConfig, BaseAgent
from broker.components.governance.registry import SkillRegistry
from broker.core.experiment_runner import ExperimentConfig, ExperimentRunner
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import (
    ExecutionResult, SkillDefinition, SkillOutcome, SkillProposal,
    ValidationResult,
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
    """Simulation engine: the default skill resets `holds_policy` to False
    (the per-period lapse), the proposed skill sets it True."""

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


def _engine(*, blocked: bool, policy: str = "default", parse_layer: str = "mock",
            sim=None, with_engine: bool = True):
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
        skill_name=PROPOSED, agent_id="A1", reasoning={}, parse_layer=parse_layer,
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
    config.get_governance_on_retry_exhausted.return_value = policy
    config.get_parsing_config.return_value = {}

    sim = sim if sim is not None else _Sim()
    eng = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[validator],
        simulation_engine=sim if with_engine else None, context_builder=_Ctx(),
        config=config,
    )
    writer = _Writer()
    eng.audit_writer = writer
    return eng, sim, writer


def _agent(holds_policy=True):
    agent = BaseAgent(AgentConfig(
        name="A1", agent_type="agent", state_params=[], objectives=[],
        constraints=[], skills=[],
    ))
    agent.holds_policy = holds_policy
    return agent


class _World:
    def advance_year(self):
        return {}


def _run_one_period(tmp_path, agent, result, hooks=None):
    """Drive ExperimentRunner.run's real result loop for one period, with the
    agent loop replaced by a precomputed broker result."""
    runner = ExperimentRunner(
        broker=MagicMock(log_prompt=False),
        sim_engine=_World(),
        agents={agent.id: agent},
        config=ExperimentConfig(output_dir=tmp_path, num_years=1),
        hooks=hooks,
    )
    runner._resolve_declared_deciders = lambda: None
    runner._run_agents_sequential = lambda agents, run_id, llm, env: [(agent, result)]
    runner._finalize_step = lambda step: None
    runner._finalize_experiment = lambda n: None
    runner.run()
    return runner


def _broker_result(*, blocked, policy="default", **kw):
    eng, sim, writer = _engine(blocked=blocked, policy=policy, **kw)
    result = eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                              llm_invoke=lambda p: "raw", agent_type="agent")
    return result, sim, writer


def _memories(runner, agent):
    return [m.get("content") if isinstance(m, dict) else str(m)
            for m in runner.memory_engine.retrieve(agent, top_k=10)]


# (a) ---------------------------------------------------------------------

def test_rejected_row_applies_fallback_state_changes(tmp_path):
    result, sim, _ = _broker_result(blocked=True)
    assert result.outcome is SkillOutcome.REJECTED
    assert sim.executed == [DEFAULT_SKILL], "precondition: the fallback executed"

    agent = _agent(holds_policy=True)
    _run_one_period(tmp_path, agent, result)

    assert agent.holds_policy is False, (
        "the fallback skill's state change (the per-period lapse) was discarded "
        "on a REJECTED row"
    )


# (b) ---------------------------------------------------------------------

def test_rejected_row_action_context_names_executed_fallback(tmp_path):
    result, _, _ = _broker_result(blocked=True)
    agent = _agent()
    agent._last_action_context = {"skill_name": "older_approved_action", "year": 0}

    runner = _run_one_period(tmp_path, agent, result)

    ctx = agent._last_action_context
    assert ctx["skill_name"] == DEFAULT_SKILL, "context must name what EXECUTED"
    assert ctx["was_fallback"] is True
    assert ctx["proposed_skill"] == PROPOSED
    assert ctx["year"] == 1
    mems = _memories(runner, agent)
    assert any(
        "Proposal to take action was rejected; default action applied: Default action"
        in m for m in mems
    ), mems
    assert not any("Decided to" in m for m in mems), mems


def test_keep_proposal_rejected_row_is_not_marked_fallback(tmp_path):
    """Under keep_proposal the agent's own proposal executed: not a fallback."""
    result, sim, _ = _broker_result(blocked=True, policy="keep_proposal")
    assert sim.executed == [PROPOSED]
    agent = _agent(holds_policy=False)
    _run_one_period(tmp_path, agent, result)
    assert agent.holds_policy is True
    assert agent._last_action_context["skill_name"] == PROPOSED
    assert agent._last_action_context["was_fallback"] is False


def test_rejected_row_without_execution_changes_nothing(tmp_path):
    """Standalone mode (no engine): nothing executed, so no state, no context,
    no memory. This is the path multi-type hooks that patch rejected rows
    themselves rely on, so the generic path must not add a second application."""
    result, _, _ = _broker_result(blocked=True)
    result.executed_skill = None
    result.executed_via_fallback = False
    result.execution_result = ExecutionResult(success=False, state_changes={})
    agent = _agent(holds_policy=True)
    runner = _run_one_period(tmp_path, agent, result)
    assert agent.holds_policy is True
    assert getattr(agent, "_last_action_context", None) is None
    assert _memories(runner, agent) == []


# (c) ---------------------------------------------------------------------

def test_approved_row_applied_exactly_once_with_unchanged_context(tmp_path):
    result, sim, _ = _broker_result(blocked=False)
    assert result.outcome is SkillOutcome.APPROVED
    assert sim.executed == [PROPOSED]

    calls = []
    agent = _agent(holds_policy=False)
    original = agent.apply_delta
    agent.apply_delta = lambda delta: (calls.append(dict(delta)), original(delta))

    runner = _run_one_period(tmp_path, agent, result)

    assert calls == [{"holds_policy": True}], "approved state applied once, not twice"
    assert agent.holds_policy is True
    # Approved-row context keeps exactly its historical keys.
    assert agent._last_action_context == {"skill_name": PROPOSED, "year": 1}
    assert any("Decided to: Take action" in m for m in _memories(runner, agent))


# (d) ---------------------------------------------------------------------

def test_audit_row_still_carries_the_blocked_proposal(tmp_path):
    result, _, writer = _broker_result(blocked=True)
    trace = writer.traces[0]
    # final_skill semantics: the blocked proposal, not the executed fallback.
    assert trace["approved_skill"]["skill_name"] == PROPOSED
    assert trace["approved_skill"]["status"] == "REJECTED"
    assert trace["executed_skill"] == DEFAULT_SKILL
    assert result.approved_skill.skill_name == PROPOSED

    agent = _agent()
    _run_one_period(tmp_path, agent, result)
    # The runner must not rewrite the result the audit / hooks see.
    assert result.approved_skill.skill_name == PROPOSED
    assert result.approved_skill.approval_status == "REJECTED"


def test_post_step_hook_still_fires_once_on_rejected_row(tmp_path):
    result, _, _ = _broker_result(blocked=True)
    seen = []
    agent = _agent()
    _run_one_period(tmp_path, agent, result,
                    hooks={"post_step": lambda a, r: seen.append(r.outcome)})
    assert seen == [SkillOutcome.REJECTED]


def test_to_dict_does_not_serialise_executed_fields():
    """to_dict feeds the (approved-only) efficiency cache; keep its keys stable."""
    result, _, _ = _broker_result(blocked=True)
    d = result.to_dict()
    assert "executed_skill" not in d and "executed_via_fallback" not in d


# UNCERTAIN / failure / standalone paths -------------------------------------

def test_uncertain_row_applies_fallback_without_proposal(tmp_path):
    """UNCERTAIN: the parser supplied the skill, so there is no proposal to name."""
    result, sim, _ = _broker_result(blocked=True, parse_layer="default")
    assert result.outcome is SkillOutcome.UNCERTAIN
    assert sim.executed == [DEFAULT_SKILL]
    agent = _agent(holds_policy=True)
    runner = _run_one_period(tmp_path, agent, result)
    assert agent.holds_policy is False
    ctx = agent._last_action_context
    assert ctx["skill_name"] == DEFAULT_SKILL
    assert ctx["was_fallback"] is True
    assert ctx["proposed_skill"] is None
    assert any("No valid proposal; default action applied: Default action" in m
               for m in _memories(runner, agent))


class _FailingSim(_Sim):
    def execute_skill(self, approved_skill):
        self.executed.append(approved_skill.skill_name)
        return ExecutionResult(success=False, state_changes={"holds_policy": False},
                               error="refused")


def test_failed_fallback_execution_changes_nothing(tmp_path):
    result, sim, _ = _broker_result(blocked=True, sim=_FailingSim())
    assert sim.executed == [DEFAULT_SKILL]
    assert result.executed_skill == DEFAULT_SKILL
    agent = _agent(holds_policy=True)
    agent._last_action_context = {"skill_name": "earlier", "year": 0}
    runner = _run_one_period(tmp_path, agent, result)
    assert agent.holds_policy is True
    assert agent._last_action_context == {"skill_name": "earlier", "year": 0}
    assert _memories(runner, agent) == []


def test_standalone_engine_rejected_row_changes_nothing(tmp_path):
    """A real engine built with no simulation engine (the multi-type setup):
    nothing executes, so the runner applies nothing."""
    result, _, _ = _broker_result(blocked=True, with_engine=False)
    assert result.outcome is SkillOutcome.REJECTED
    assert result.executed_skill is None
    agent = _agent(holds_policy=True)
    runner = _run_one_period(tmp_path, agent, result)
    assert agent.holds_policy is True
    assert getattr(agent, "_last_action_context", None) is None
    assert _memories(runner, agent) == []


def test_mock_result_with_non_string_executed_skill_is_ignored():
    result = MagicMock()
    result.outcome = SkillOutcome.REJECTED
    assert ExperimentRunner._executed_on_rejected_row(result) is False


# Audit tie-break -------------------------------------------------------------

_TIE_CODE = (
    "from broker.components.analytics.audit import trace_to_csv_row\n"
    "t = {'memory_audit': {'memories': ["
    "{'emotion': 'beta', 'source': 's2'}, {'emotion': 'alpha', 'source': 's1'},"
    "{'emotion': 'alpha', 'source': 's1'}, {'emotion': 'beta', 'source': 's2'}]}}\n"
    "r = trace_to_csv_row(t)\n"
    "print('RESULT', r['mem_top_emotion'], r['mem_top_source'])\n"
)


def test_mem_top_emotion_tie_is_first_retrieved_across_hash_seeds():
    """max(set(...)) broke ties by string-hash order, which varies per process."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = str(Path(__file__).resolve().parents[2])
    seen = set()
    for seed in ("0", "1", "2", "3", "4", "5"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        out = subprocess.run([sys.executable, "-c", _TIE_CODE], capture_output=True,
                             text=True, env=env, timeout=120, check=True, cwd=root)
        line = [ln for ln in out.stdout.splitlines() if ln.startswith("RESULT")][-1]
        seen.add(line)
    assert seen == {"RESULT beta s2"}, seen
