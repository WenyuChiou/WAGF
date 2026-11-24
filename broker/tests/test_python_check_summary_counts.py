"""A Python check that blocks a decision must reach governance_summary.json.

Walk record p2-walk-2026-11-23: a scaffolded reservoir case whose only rule is a
Python physical check (registered through ValidatorRegistry, run by
``dispatch_domain_physical``). The audit CSV showed 2 REJECTED rows with
``failed_rules`` = ``release_exceeds_storage``; governance_summary.json showed
``total_interventions: 0``, an empty ``rule_frequency`` and ``retry_exhausted: 0``.

Cause: the engine logs final outcomes to the GovernanceAuditor from
``metadata["rules_hit"]`` only. YAML rules set ``rules_hit``; a Python check
names its rule by ``rule_id`` only (the irrigation checks do too), so its
blocks never reached the summary, while the CSV's ``failed_rules`` reads
``rule_id``.

Fix: ``global_config.governance.summary_counts_python_checks`` (default OFF,
so the frozen paper configs, which leave it unset, write the same summary as
before; ``scaffold_domain`` turns it on). These tests lock both settings.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from broker.components.governance.registry import SkillRegistry
from broker.components.governance.validator_registry import ValidatorRegistry
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import SkillDefinition, SkillProposal, ValidationResult
from broker.tools.validate_prompt import KNOWN_GOVERNANCE_KEYS
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.governance_auditor import GovernanceAuditor
from broker.utils.parsing.unified_adapter import UnifiedAdapter

DOMAIN = "test_py_physical_summary"
RULE_ID = "release_exceeds_storage"


def _python_check_block():
    """Shaped like a Python check's result: rule_id, no rules_hit."""
    return ValidationResult(
        valid=False, validator_name=RULE_ID, errors=["releases more than storage"],
        metadata={"category": "physical", "rule_id": RULE_ID, "deterministic": False},
    )


def _release_check(skill_name, rules, context):
    return [_python_check_block()] if skill_name == "release_large" else []


def _fresh_auditor():
    """A private GovernanceAuditor, so the process-wide singleton is untouched."""
    aud = object.__new__(GovernanceAuditor)
    aud._initialized = False
    aud.__init__()
    return aud


class _Ctx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "PROMPT"


def _config(flag, max_retries=2):
    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_base_type.side_effect = lambda a: a
    config.get_parsing_config.return_value = {}
    config.get_governance_retries.return_value = max_retries
    config.get_governance_max_reports.return_value = 3
    config.get_multi_skill_config.return_value = {}
    config.get_audit_initial_proposal_columns.return_value = False
    config.get_audit_executed_columns.return_value = False
    config.get_audit_advise_columns.return_value = False
    config.get_governance_advise.return_value = None
    config.get_governance_advise_mode.return_value = "off"
    config.get_governance_intervention_framing.return_value = "legacy"
    config.get_governance_on_retry_exhausted.return_value = "default"
    config.get_governance_retry_feedback_mode.return_value = "full"
    config.get_governance_summary_counts_python_checks.return_value = flag
    return config


def _process_engine(flag, skills):
    """A real engine driven through ``process_step``: the LLM proposes
    ``skills`` in order; one Python-check-shaped validator blocks
    ``release_large``."""
    registry = SkillRegistry()
    for sid in ("release_none", "release_large"):
        registry.register(SkillDefinition(
            skill_id=sid, description=sid, eligible_agent_types=["*"],
            preconditions=[], institutional_constraints={},
            allowed_state_changes=[], implementation_mapping=sid,
        ))
    registry.set_default_skill("release_none")

    proposals = iter([
        SkillProposal(skill_name=s, agent_id="agent_1", agent_type="agent", reasoning={})
        for s in skills
    ])
    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    adapter.parse_output = lambda _raw, _ctx: next(proposals)

    validator = MagicMock()
    validator.validate.side_effect = (
        lambda proposal, _ctx, _reg=None: _release_check(proposal.skill_name, [], {})
    )

    eng = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[validator],
        simulation_engine=None, context_builder=_Ctx(), config=_config(flag),
    )
    eng.auditor = _fresh_auditor()
    eng.process_step(agent_id="agent_1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda _p: "raw", agent_type="agent")
    return eng


# ---------------------------------------------------------------------------
# The walk's shape: one Python physical check through dispatch_domain_physical
# ---------------------------------------------------------------------------

def _dispatch_engine(flag):
    eng = SkillBrokerEngine(
        skill_registry=SkillRegistry(), model_adapter=MagicMock(), validators=[],
        simulation_engine=MagicMock(), context_builder=MagicMock(),
        config=_config(flag), domain_physical_dispatch=DOMAIN,
    )
    eng.auditor = _fresh_auditor()
    return eng


@pytest.mark.parametrize("flag, expected", [
    (True, {RULE_ID: 1}),
    (False, {}),   # shipped behaviour, kept for configs that leave the flag unset
])
def test_dispatched_python_check_rejection_reaches_summary(monkeypatch, flag, expected):
    monkeypatch.setitem(ValidatorRegistry._registry, DOMAIN, {"physical": [_release_check]})
    eng = _dispatch_engine(flag)
    proposal = SkillProposal(skill_name="release_large", agent_id="agent_1",
                             reasoning={}, agent_type="agent", parse_layer="test")
    results = eng._run_validators(proposal, {"agent_type": "agent", "env_state": {}})
    assert any(not r.valid and r.metadata.get("rule_id") == RULE_ID for r in results)

    approved, _ = eng._build_approved_skill(
        all_valid=False, skill_proposal=proposal, agent_id="agent_1",
        agent_type="agent", retry_count=1, validation_results=results,
        initial_rule_ids=set(),
    )
    assert approved.approval_status == "REJECTED"
    assert dict(eng.auditor.rule_hits) == expected
    assert eng.auditor.total_interventions == len(expected)
    assert eng.auditor.retry_failure_count == len(expected)


# ---------------------------------------------------------------------------
# Full decisions through process_step
# ---------------------------------------------------------------------------

def test_rejected_decision_counts_once_with_flag_on():
    """Blocked on every attempt -> one rejected decision -> one count."""
    aud = _process_engine(True, ["release_large"] * 5).auditor
    assert dict(aud.rule_hits) == {RULE_ID: 1}
    assert aud.total_interventions == 1
    assert aud.retry_failure_count == 1
    assert aud.retry_success_count == 0


def test_decision_fixed_on_retry_counts_once_as_success_with_flag_on():
    """Blocked first, passes on the retry -> one retry_success."""
    aud = _process_engine(True, ["release_large", "release_none"]).auditor
    assert dict(aud.rule_hits) == {RULE_ID: 1}
    assert aud.total_interventions == 1
    assert aud.retry_success_count == 1
    assert aud.retry_failure_count == 0


@pytest.mark.parametrize("skills", [
    ["release_large"] * 5,
    ["release_large", "release_none"],
])
def test_flag_off_keeps_shipped_summary(skills):
    """Flag OFF (every frozen paper config): Python-check blocks stay out of
    the summary exactly as before."""
    aud = _process_engine(False, skills).auditor
    assert dict(aud.rule_hits) == {}
    assert aud.total_interventions == 0
    assert aud.retry_success_count == 0
    assert aud.retry_failure_count == 0


# ---------------------------------------------------------------------------
# Which results fall back to rule_id
# ---------------------------------------------------------------------------

def test_summary_rule_ids_falls_back_only_for_blocking_results_without_rules_hit():
    on = _dispatch_engine(True)
    off = _dispatch_engine(False)

    def res(valid, **meta):
        return ValidationResult(valid=valid, validator_name="v", errors=[], metadata=meta)

    # rules_hit present: used as is, with or without the flag
    yaml_like = res(False, rule_id="a", rules_hit=["b"])
    assert on._summary_rule_ids(yaml_like) == ["b"]
    assert off._summary_rule_ids(yaml_like) == ["b"]
    # blocking, rule_id only: counted only with the flag
    assert on._summary_rule_ids(res(False, rule_id=RULE_ID)) == [RULE_ID]
    assert off._summary_rule_ids(res(False, rule_id=RULE_ID)) == []
    # non-blocking (warning, shadow, rule exception): never falls back
    assert on._summary_rule_ids(res(True, rule_id=RULE_ID)) == []
    # no usable rule_id: nothing to count
    assert on._summary_rule_ids(res(False)) == []
    assert on._summary_rule_ids(res(False, rule_id="  ")) == []


# ---------------------------------------------------------------------------
# Config surface
# ---------------------------------------------------------------------------

def _cfg(tmp_path, gov):
    import yaml
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "at.yaml"
    p.write_text(yaml.safe_dump({
        "global_config": {"governance": gov}, "shared": {}, "agent": {"parsing": {}},
    }), encoding="utf-8")
    return AgentTypeConfig.load(str(p))


def test_config_getter_default_off_and_strict_bool(tmp_path):
    assert _cfg(tmp_path / "a", {}).get_governance_summary_counts_python_checks() is False
    on = _cfg(tmp_path / "b", {"summary_counts_python_checks": True})
    assert on.get_governance_summary_counts_python_checks() is True
    with pytest.raises(ValueError, match="summary_counts_python_checks"):
        _cfg(tmp_path / "c", {"summary_counts_python_checks": "false"}) \
            .get_governance_summary_counts_python_checks()


def test_validate_prompt_knows_the_key():
    assert "summary_counts_python_checks" in KNOWN_GOVERNANCE_KEYS
