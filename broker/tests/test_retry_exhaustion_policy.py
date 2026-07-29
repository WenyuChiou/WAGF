"""What executes when governance retries are exhausted — a model-builder choice.

Historically the engine hardcoded "run the registry default skill" for every domain.
That is right for irrigation (an enforced-allocation domain that would not converge
if agents could keep taking water they were denied) and wrong for flood, whose study
treats a persistent rule-violating choice as the observable it exists to measure —
overwriting it with `do_nothing` destroys the datum.

`global_config.governance.on_retry_exhausted` makes it configurable. Default
`"default"` reproduces the historical behaviour bit-for-bit.

The subtle rules these tests exist to pin:
  * UNCERTAIN (parser produced nothing usable) always uses the default — there is no
    agent choice to preserve.
  * an unregistered proposal name falls back to the default.
  * a MagicMock config must NOT enable the new behaviour (a Mock compares unequal to
    every string, so a `!= "default"` branch would switch it on everywhere).
  * it is refused outright under an enabled coupling layer (INVARIANTS AR-2).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from broker.components.governance.registry import SkillRegistry
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import (
    SkillDefinition, SkillProposal, ValidationResult,
)
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.model_adapter import UnifiedAdapter


# ---------------------------------------------------------------------------
# Config getter
# ---------------------------------------------------------------------------

def _cfg(global_config=None) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": global_config or {}}
    return cfg


def test_getter_defaults_to_default():
    assert _cfg().get_governance_on_retry_exhausted() == "default"
    assert _cfg({"governance": {}}).get_governance_on_retry_exhausted() == "default"
    # A malformed scalar block must read as the default, never raise.
    assert _cfg({"governance": "yes"}).get_governance_on_retry_exhausted() == "default"


def test_getter_accepts_keep_proposal():
    assert _cfg({"governance": {"on_retry_exhausted": "keep_proposal"}}
                ).get_governance_on_retry_exhausted() == "keep_proposal"


def test_getter_rejects_unknown_value():
    """A misspelled policy must fail loudly, not silently pick a behaviour."""
    with pytest.raises(ValueError, match="on_retry_exhausted"):
        _cfg({"governance": {"on_retry_exhausted": "keep"}}
             ).get_governance_on_retry_exhausted()


def test_keep_proposal_refused_when_coupling_enabled():
    """INVARIANTS AR-2: a rejected proposal must never reach a physical model's
    ControlSink ungoverned."""
    cfg = _cfg({"governance": {"on_retry_exhausted": "keep_proposal"},
                "coupling": {"enable": True}})
    with pytest.raises(ValueError, match="AR-2|coupling"):
        cfg.get_governance_on_retry_exhausted()


def test_default_policy_allowed_with_coupling():
    cfg = _cfg({"governance": {"on_retry_exhausted": "default"},
                "coupling": {"enable": True}})
    assert cfg.get_governance_on_retry_exhausted() == "default"


# ---------------------------------------------------------------------------
# End-to-end through a real process_step
# ---------------------------------------------------------------------------

VALID = ("increase_large", "maintain_demand")
DEFAULT_SKILL = "maintain_demand"


class _Ctx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "PROMPT"


class _Sim:
    """Records exactly what reached the simulation engine.

    tests/conftest.py has an equivalent recorder that nothing asserts on, so there
    was no end-to-end guard that the right skill object is handed to execute_skill
    on a rejection. These tests close that gap.
    """

    def __init__(self):
        self.executed = []

    def execute_skill(self, approved_skill):
        from broker.interfaces.skill_types import ExecutionResult
        self.executed.append(approved_skill.skill_name)
        return ExecutionResult(success=True, state_changes={})


class _Writer:
    def __init__(self):
        self.traces = []

    def write_trace(self, agent_type, trace, history):
        self.traces.append(trace)


def _engine(policy, *, proposal_name="increase_large", parse_layer="mock",
            register=VALID):
    registry = SkillRegistry()
    for sid in register:
        registry.register(SkillDefinition(
            skill_id=sid, description=sid, eligible_agent_types=["*"],
            preconditions=[], institutional_constraints={},
            allowed_state_changes=[], implementation_mapping=sid,
        ))
    registry.set_default_skill(DEFAULT_SKILL)

    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    if proposal_name is None:
        adapter.parse_output = lambda *_a, **_k: None
    else:
        adapter.parse_output = lambda *_a, **_k: SkillProposal(
            skill_name=proposal_name, agent_id="A1",
            reasoning={"WSA_LABEL": "H"}, parse_layer=parse_layer,
        )

    # Always blocks, so every decision exhausts its retries.
    validator = MagicMock()
    validator.validate.side_effect = lambda *_a, **_k: ValidationResult(
        valid=False, validator_name="AgentValidator:thinking_error",
        errors=["blocked"], metadata={"rules_hit": ["r1"], "level": "ERROR"})

    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_governance_retries.return_value = 3
    config.get_governance_max_reports.return_value = 3
    config.get_multi_skill_config.return_value = {}
    config.get_audit_executed_columns.return_value = True
    config.get_governance_on_retry_exhausted.return_value = policy
    config.get_parsing_config.return_value = {}

    sim = _Sim()
    eng = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[validator],
        simulation_engine=sim, context_builder=_Ctx(), config=config,
    )
    writer = _Writer()
    eng.audit_writer = writer
    return eng, sim, writer


def _run(eng):
    eng.process_step(agent_id="A1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda p: "raw", agent_type="farmer")


def test_default_policy_executes_registry_default():
    eng, sim, writer = _engine("default")
    _run(eng)
    assert sim.executed == [DEFAULT_SKILL], "the registry default must execute"
    t = writer.traces[0]
    assert t["executed_skill"] == DEFAULT_SKILL
    assert t["executed_via_fallback"] is True


def test_keep_proposal_executes_the_agents_final_choice():
    eng, sim, writer = _engine("keep_proposal")
    _run(eng)
    assert sim.executed == ["increase_large"], "the agent's own choice must execute"
    t = writer.traces[0]
    assert t["executed_skill"] == "increase_large"
    assert t["executed_via_fallback"] is False, "nothing fell back"
    # The decision is still recorded as rejected — only what EXECUTES changes, so
    # the terminal taxonomy and every status-derived metric are unaffected.
    assert t["approved_skill"]["status"] == "REJECTED"


def test_total_parse_failure_executes_nothing_at_all():
    """A wholly unparsable response aborts before the execution block
    (skill_broker_engine.py:255-261), so the policy is never consulted and nothing
    reaches the simulation engine under either setting."""
    for policy in ("default", "keep_proposal"):
        eng, sim, _ = _engine(policy, proposal_name=None)
        _run(eng)
        assert sim.executed == [], f"{policy}: nothing may execute on an aborted step"


def test_keep_proposal_does_not_apply_to_generic_parse_default():
    """UNCERTAIN: parse_layer == 'default' means the PARSER supplied the skill, not
    the agent. There is no agent choice to preserve, so the registry default runs
    even under keep_proposal."""
    eng, sim, writer = _engine("keep_proposal", parse_layer="default")
    _run(eng)
    assert sim.executed == [DEFAULT_SKILL]
    assert writer.traces[0]["executed_via_fallback"] is True


def test_keep_proposal_falls_back_when_skill_unregistered():
    """Membership validation can fail and still leave a bogus name on the proposal."""
    eng, sim, writer = _engine("keep_proposal", proposal_name="teleport_house")
    _run(eng)
    assert sim.executed == [DEFAULT_SKILL], "must not execute an unregistered skill"
    assert writer.traces[0]["executed_via_fallback"] is True


@pytest.mark.parametrize("meta,label", [
    ({"rules_hit": ["elevated_already"], "constraint_type": "hard"}, "identity/hard"),
    ({"rules_hit": ["r1"], "expected_terminal": True}, "expected_terminal"),
    ({"rules_hit": ["affordability"], "deterministic": True}, "affordability"),
    ({"rules_hit": ["precondition_violation"]}, "registry precondition"),
])
def test_hard_constraint_blocker_declines_keep_proposal(meta, label):
    """INVARIANTS AR-1a, enforced in code rather than prose.

    keep_proposal exists to preserve behaviourally INCOHERENT choices. It must never
    resurrect a WORLD-INFEASIBLE one — re-doing an irreversible action, exceeding an
    allocation cap, or buying something unaffordable would put the world in a state
    it cannot occupy, and some domain executors double-charge rather than refuse.
    """
    eng, sim, writer = _engine("keep_proposal")
    eng.validators[0].validate.side_effect = lambda *_a, **_k: ValidationResult(
        valid=False, validator_name="AgentValidator:identity_error",
        errors=["blocked"], metadata=meta)
    _run(eng)
    assert sim.executed == [DEFAULT_SKILL], f"{label} must fall back to the default"
    assert writer.traces[0]["executed_via_fallback"] is True


def test_soft_blocker_still_keeps_the_proposal():
    """Control for the test above: a plain theory-rule block is exactly the case
    keep_proposal is for, so it must NOT be caught by the hard-constraint guard."""
    eng, sim, _ = _engine("keep_proposal")
    eng.validators[0].validate.side_effect = lambda *_a, **_k: ValidationResult(
        valid=False, validator_name="AgentValidator:thinking_error",
        errors=["blocked"],
        metadata={"rules_hit": ["r1"], "constraint_type": "soft",
                  "expected_terminal": False})
    _run(eng)
    assert sim.executed == ["increase_large"]


def test_standalone_mode_executes_nothing_under_either_policy():
    """Flood's multi-agent runner wires no simulation engine, so the broker's
    execution branch is never reached. Pin that both policies are then
    indistinguishable, so nobody reads a keep_proposal config as proof that the
    proposal executed in such a domain."""
    for policy in ("default", "keep_proposal"):
        eng, _, writer = _engine(policy)
        eng.simulation_engine = None
        _run(eng)
        t = writer.traces[0]
        assert t["executed_skill"] is None, f"{policy}: nothing executes"
        assert t["executed_via_fallback"] is False


def test_mock_config_leaves_advise_and_counters_off():
    """Same Mock footgun as the policy flag, on the adjacent P0-1c fields:
    `_spec["mode"]` on a Mock yields a Mock, and `bool(MagicMock())` is True."""
    registry = SkillRegistry()
    eng = SkillBrokerEngine(
        skill_registry=registry, model_adapter=MagicMock(), validators=[MagicMock()],
        simulation_engine=None, context_builder=_Ctx(), config=MagicMock(),
    )
    assert eng._advise_mode == "off"
    assert eng._advise_spec is None
    assert eng._count_llm_calls is False
    assert eng._intervention_framing == "legacy"


def test_mock_config_does_not_enable_keep_proposal():
    """Regression guard. A MagicMock config returns a Mock from every getter, and a
    Mock compares unequal to any string — so a `!= "default"` branch would silently
    switch the new behaviour on for every test in the suite."""
    registry = SkillRegistry()
    registry.register(SkillDefinition(
        skill_id="x", description="x", eligible_agent_types=["*"],
        preconditions=[], institutional_constraints={},
        allowed_state_changes=[], implementation_mapping="x",
    ))
    eng = SkillBrokerEngine(
        skill_registry=registry, model_adapter=MagicMock(), validators=[MagicMock()],
        simulation_engine=None, context_builder=_Ctx(), config=MagicMock(),
    )
    assert eng._on_retry_exhausted == "default"


def test_engine_without_the_getter_defaults_safely():
    """A config object predating this flag must not raise."""
    from types import SimpleNamespace
    registry = SkillRegistry()
    cfg = SimpleNamespace(
        get_governance_retries=lambda d=3: 3,
        get_governance_max_reports=lambda: 3,
        get_global_skills=lambda t: [],
        get_full_disclosure_agent_types=lambda: [],
        get_retrieval_config=lambda: {},
    )
    eng = SkillBrokerEngine(
        skill_registry=registry, model_adapter=MagicMock(), validators=[MagicMock()],
        simulation_engine=None, context_builder=_Ctx(), config=cfg,
    )
    assert eng._on_retry_exhausted == "default"
