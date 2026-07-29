from __future__ import annotations

from broker.core._retry_loop import RetryMixin
from broker.interfaces.skill_types import SkillProposal, ValidationResult


class _NoopAuditor:
    def log_parse_error(self):
        raise AssertionError("direct SkillProposal retry should not be parsed")


class _Adapter:
    def format_retry_prompt(self, prompt, errors, max_reports=3):
        return f"{prompt}\nretry"

    def parse_output(self, raw_output, context):
        raise TypeError(f"expected string or bytes-like object, got {type(raw_output).__name__}")


class _Host(RetryMixin):
    max_retries = 1
    max_reports = 3

    def __init__(self):
        self.auditor = _NoopAuditor()
        self.model_adapter = _Adapter()

    def _run_validators(self, proposal, context):
        return [ValidationResult(valid=True, validator_name="ok")]


def test_governance_retry_accepts_direct_skill_proposal_outputs():
    host = _Host()
    initial = SkillProposal(
        skill_name="buy_contents_insurance",
        agent_id="H0013",
        agent_type="household_renter",
        reasoning={},
    )
    retry = SkillProposal(
        skill_name="do_nothing",
        agent_id="H0013",
        agent_type="household_renter",
        reasoning={"TP_LABEL": "H", "CP_LABEL": "M"},
        parse_layer="parametric",
    )
    rejected = [
        ValidationResult(
            valid=False,
            validator_name="reject",
            errors=["blocked"],
            metadata={"rules_hit": ["test_rule"], "deterministic": False},
        )
    ]

    result = host._governance_retry_loop(
        all_valid=False,
        skill_proposal=initial,
        validation_results=rejected,
        all_validation_history=list(rejected),
        validation_context={},
        prompt="prompt",
        llm_invoke=lambda _prompt: retry,
        context={},
        agent_id="H0013",
        agent_type="household_renter",
        env_context={"current_year": 1},
        raw_output=initial,
        total_llm_stats={"llm_retries": 0, "llm_success": False},
    )

    skill_proposal, raw_output, validation_results, _, all_valid, retry_count = result
    assert skill_proposal is retry
    assert raw_output is retry
    assert all_valid is True
    assert retry_count == 1
    assert all(v.valid for v in validation_results)
