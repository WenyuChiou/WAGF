"""governance_summary.json counted a YAML rule once per attempt plus once more.

R5 walk finding 4: ``AgentValidator`` calls ``log_intervention(..., is_final=False)``
each time a YAML rule blocks an attempt, and the engine counts the same rule
again when the decision ends. ``retry_success`` counted rule ids, not decisions.
A mock run showed ``low_storage_cap`` 6 in the summary against 3 rows.

Fix: ``global_config.governance.summary_counts_per_decision`` (default OFF, so
the frozen paper configs write the same summary; ``scaffold_domain`` turns it
on). With it on, each rule that blocked any attempt of a decision counts once
for that decision, and each decision that a rule blocked counts once as
``retry_success`` or ``retry_exhausted``.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from broker.components.governance.registry import SkillRegistry
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import SkillDefinition, SkillProposal, ValidationResult
from broker.tools.validate_prompt import KNOWN_GOVERNANCE_KEYS
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.governance_auditor import GovernanceAuditor
from broker.utils.parsing.unified_adapter import UnifiedAdapter


def _fresh_auditor():
    aud = object.__new__(GovernanceAuditor)
    aud._initialized = False
    aud.__init__()
    return aud


class _Ctx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "PROMPT"


def _config(flag):
    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_base_type.side_effect = lambda a: a
    config.get_parsing_config.return_value = {}
    config.get_governance_retries.return_value = 2
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
    config.get_governance_summary_counts_python_checks.return_value = False
    config.get_governance_summary_counts_per_decision.return_value = flag
    return config


def _run(flag, skills, blocks):
    """One decision through ``process_step``. The model proposes ``skills`` in
    order; ``blocks`` maps a skill to the YAML rules that block it. The
    validator logs each block the way ``AgentValidator`` does."""
    registry = SkillRegistry()
    for sid in ("wait", "pump", "drill"):
        registry.register(SkillDefinition(
            skill_id=sid, description=sid, eligible_agent_types=["*"],
            preconditions=[], institutional_constraints={},
            allowed_state_changes=[], implementation_mapping=sid,
        ))
    registry.set_default_skill("wait")
    proposals = iter([
        SkillProposal(skill_name=s, agent_id="agent_1", agent_type="agent", reasoning={})
        for s in skills
    ])
    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    adapter.parse_output = lambda _raw, _ctx: next(proposals)
    holder = {}

    def validate(proposal, _ctx, _reg=None):
        results = []
        for rule in blocks.get(proposal.skill_name, []):
            holder["auditor"].log_intervention(rule, success=False, is_final=False)
            results.append(ValidationResult(
                valid=False, validator_name="AgentValidator:thinking",
                errors=[f"{rule} blocks {proposal.skill_name}"],
                metadata={"rule_id": rule, "rules_hit": [rule]},
            ))
        return results

    validator = MagicMock()
    validator.validate.side_effect = validate
    eng = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[validator],
        simulation_engine=None, context_builder=_Ctx(), config=_config(flag),
    )
    eng.auditor = holder["auditor"] = _fresh_auditor()
    eng.process_step(agent_id="agent_1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda _p: "raw", agent_type="agent")
    return eng.auditor


def _counts(aud):
    return (dict(aud.rule_hits), aud.total_interventions,
            aud.retry_success_count, aud.retry_failure_count)


@pytest.mark.parametrize("flag, expected", [
    (True, ({"cap": 1}, 1, 1, 0)),
    (False, ({"cap": 3}, 3, 1, 0)),  # 2 blocked attempts + 1 at the end, as shipped
])
def test_fixed_after_two_retries(flag, expected):
    assert _counts(_run(flag, ["pump", "pump", "wait"], {"pump": ["cap"]})) == expected


@pytest.mark.parametrize("flag, expected", [
    (True, ({"cap": 1}, 1, 0, 1)),
    (False, ({"cap": 4}, 4, 0, 1)),  # 3 blocked attempts + 1 at the end
])
def test_blocked_on_every_attempt(flag, expected):
    assert _counts(_run(flag, ["pump"] * 3, {"pump": ["cap"]})) == expected


@pytest.mark.parametrize("flag, expected", [
    # Each rule once; one repaired decision. A rule that blocked only the
    # retry ("floor") counts too.
    (True, ({"cap": 1, "floor": 1, "dry": 1}, 3, 1, 0)),
    # Shipped: per attempt, plus the FIRST attempt's rules again, and
    # retry_success once per first-attempt rule id.
    (False, ({"cap": 2, "dry": 2, "floor": 1}, 5, 2, 0)),
])
def test_two_rules_then_a_third_then_fixed(flag, expected):
    blocks = {"pump": ["cap", "dry"], "drill": ["floor"]}
    assert _counts(_run(flag, ["pump", "drill", "wait"], blocks)) == expected


def test_an_approved_decision_counts_nothing():
    assert _counts(_run(True, ["wait"], {"pump": ["cap"]})) == ({}, 0, 0, 0)


def test_switch_drops_only_per_attempt_blocks():
    aud = _fresh_auditor()
    with GovernanceAuditor.per_decision():
        aud.log_intervention("cap", success=False, is_final=False)
        aud.log_warning("note")
    aud.log_intervention("cap", success=False, is_final=False)
    assert dict(aud.rule_hits) == {"cap": 1}
    assert dict(aud.warning_hits) == {"note": 1}


def _cfg(tmp_path, gov):
    import yaml
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "at.yaml"
    p.write_text(yaml.safe_dump({
        "global_config": {"governance": gov}, "shared": {}, "agent": {"parsing": {}},
    }), encoding="utf-8")
    return AgentTypeConfig.load(str(p))


def test_config_getter_default_off_and_strict_bool(tmp_path):
    assert _cfg(tmp_path / "a", {}).get_governance_summary_counts_per_decision() is False
    on = _cfg(tmp_path / "b", {"summary_counts_per_decision": True})
    assert on.get_governance_summary_counts_per_decision() is True
    with pytest.raises(ValueError, match="summary_counts_per_decision"):
        _cfg(tmp_path / "c", {"summary_counts_per_decision": "yes"}) \
            .get_governance_summary_counts_per_decision()


def test_validate_prompt_knows_the_key():
    assert "summary_counts_per_decision" in KNOWN_GOVERNANCE_KEYS
