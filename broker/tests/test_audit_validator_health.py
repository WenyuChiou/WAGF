"""Audit writer validator-health regression tests."""
from broker.components.analytics.audit import AuditConfig, GenericAuditWriter
from broker.interfaces.skill_types import ValidationResult


def test_validator_health_ignores_clean_pass_without_rule_id(tmp_path):
    """Clean pass-through validation results should not create Unknown rules."""
    writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="test")
    )
    trace = {
        "agent_id": "A1",
        "agent_type": "simple_agent",
        "approved_skill": {"skill_name": "do_nothing"},
        "memory_audit": {},
        "social_audit": {},
        "cognitive_audit": {},
        "rule_breakdown": {},
    }

    writer.write_trace(
        "simple_agent",
        trace,
        validation_results=[
            ValidationResult(valid=True, validator_name="SkillRegistry.eligibility")
        ],
    )

    assert writer.summary["validator_health"] == {}
