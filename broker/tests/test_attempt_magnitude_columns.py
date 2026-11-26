"""global_config.audit.attempt_magnitude_columns (R5 walk finding 6): the
number each attempt proposed. The broker.run end-to-end case is in
test_broker_run.py; these cover an unparsed attempt and the refusal."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from broker.components.governance.registry import SkillRegistry
from broker.core._audit_helpers import _magnitude_text
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import SkillDefinition, SkillProposal, ValidationResult
from broker.utils.parsing.unified_adapter import UnifiedAdapter


class _Ctx:
    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": {}}

    def format_prompt(self, context):
        return "PROMPT"


def _config(advise_mode="off"):
    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_base_type.side_effect = lambda a: a
    config.get_parsing_config.return_value = {}
    config.get_governance_retries.return_value = 3
    config.get_governance_max_reports.return_value = 3
    config.get_multi_skill_config.return_value = {}
    config.get_audit_initial_proposal_columns.return_value = True
    config.get_audit_executed_columns.return_value = False
    config.get_audit_advise_columns.return_value = False
    config.get_governance_advise.return_value = None
    config.get_governance_advise_mode.return_value = advise_mode
    config.get_governance_intervention_framing.return_value = "legacy"
    config.get_governance_on_retry_exhausted.return_value = "default"
    config.get_governance_retry_feedback_mode.return_value = "full"
    config.get_audit_attempt_magnitude_columns.return_value = True
    return config


def _registry():
    registry = SkillRegistry()
    for sid in ("wait", "pump"):
        registry.register(SkillDefinition(
            skill_id=sid, description=sid, eligible_agent_types=["*"],
            preconditions=[], institutional_constraints={},
            allowed_state_changes=[], implementation_mapping=sid,
        ))
    registry.set_default_skill("wait")
    return registry


def test_number_text():
    assert _magnitude_text(None) == ""
    assert _magnitude_text(0.3) == "0.3"
    assert _magnitude_text(1) == "1.0"


def test_an_unparsed_attempt_is_an_empty_entry():
    """pump 0.9 is blocked, the next reply does not parse, pump 0.3 passes."""
    replies = iter([
        SkillProposal(skill_name="pump", agent_id="agent_1", agent_type="agent",
                      reasoning={}, magnitude_pct=0.9),
        None,
        SkillProposal(skill_name="pump", agent_id="agent_1", agent_type="agent",
                      reasoning={}, magnitude_pct=0.3),
    ])
    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    adapter.parse_output = lambda _raw, _ctx: next(replies)

    def cap(proposal, _ctx, _reg=None):
        ok = (proposal.magnitude_pct or 0) <= 0.5
        return ValidationResult(valid=ok, validator_name="cap",
                                errors=[] if ok else ["above 0.5"], metadata={"rule_id": "cap"})

    validator = MagicMock()
    validator.validate.side_effect = cap
    writer = MagicMock()
    eng = SkillBrokerEngine(
        skill_registry=_registry(), model_adapter=adapter, validators=[validator],
        simulation_engine=None, context_builder=_Ctx(), config=_config(),
        audit_writer=writer,
    )
    eng.process_step(agent_id="agent_1", step_id=1, run_id="r", seed=42,
                     llm_invoke=lambda _p: "raw", agent_type="agent")
    trace = writer.write_trace.call_args.args[1]
    assert trace["attempt_skills"] == "pump||pump"
    assert trace["initial_magnitude"] == "0.9"
    assert trace["attempt_magnitudes"] == "0.9||0.3"


def test_refused_with_an_advisory_channel():
    with pytest.raises(ValueError, match="attempt_magnitude_columns"):
        SkillBrokerEngine(
            skill_registry=_registry(), model_adapter=MagicMock(), validators=[],
            simulation_engine=None, context_builder=_Ctx(), config=_config("record"),
        )
