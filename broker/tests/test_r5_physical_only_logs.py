"""R5 walk finding 10: two warnings a physical-only case (psychological_framework:
none) got on every run although nothing was wrong."""
import logging

from broker.components.analytics.audit import AuditConfig, GenericAuditWriter
from broker.core.run_integrity import record_run_integrity
from broker.validators.governance import note_uncategorised_rules, reset_uncategorised_rules


def _trace():
    return {
        "step_id": 1, "agent_id": "agent_1", "year": 1,
        "memory_audit": {}, "social_audit": {}, "rule_breakdown": {},
        "skill_proposal": {"skill_name": "wait", "reasoning": {}},
        "approved_skill": {"skill_name": "wait", "status": "APPROVED"},
    }


def _invariant_lines(caplog):
    return [r for r in caplog.records if "[AuditInvariant]" in r.getMessage()]


def test_no_appraisal_type_gets_no_cognitive_audit_warning(tmp_path, caplog):
    writer = GenericAuditWriter(AuditConfig(output_dir=str(tmp_path)))
    writer.no_appraisal_agent_types = {"agent"}
    with caplog.at_level(logging.WARNING):
        writer.write_trace("agent", _trace())
    assert _invariant_lines(caplog) == []


def test_other_types_still_get_the_warning(tmp_path, caplog):
    writer = GenericAuditWriter(AuditConfig(output_dir=str(tmp_path)))
    with caplog.at_level(logging.WARNING):
        writer.write_trace("agent", _trace())
    [line] = _invariant_lines(caplog)
    assert "cognitive_audit" in line.getMessage()


def test_no_appraisal_type_still_warns_for_another_missing_dict(tmp_path, caplog):
    writer = GenericAuditWriter(AuditConfig(output_dir=str(tmp_path)))
    writer.no_appraisal_agent_types = {"agent"}
    trace = _trace()
    del trace["memory_audit"]
    with caplog.at_level(logging.WARNING):
        writer.write_trace("agent", trace)
    [line] = _invariant_lines(caplog)
    assert "memory_audit" in line.getMessage() and "cognitive_audit" not in line.getMessage()


def _bucket_warnings(caplog):
    return [r for r in caplog.records
            if r.levelno >= logging.WARNING and "reached no rules_*_hit" in r.getMessage()]


def test_bucket_line_is_quiet_for_a_no_appraisal_run(tmp_path, caplog):
    reset_uncategorised_rules()
    note_uncategorised_rules(2, ["aquifer_floor"])
    try:
        with caplog.at_level(logging.DEBUG):
            audit = record_run_integrity(tmp_path, corrected_status_columns=True,
                                         no_appraisal=True)
        assert _bucket_warnings(caplog) == []
        assert audit["rules_uncategorised_total"] == 2  # still recorded
    finally:
        reset_uncategorised_rules()


def test_bucket_line_still_warns_otherwise(tmp_path, caplog):
    reset_uncategorised_rules()
    note_uncategorised_rules(2, ["aquifer_floor"])
    try:
        with caplog.at_level(logging.WARNING):
            record_run_integrity(tmp_path, corrected_status_columns=True)
        assert len(_bucket_warnings(caplog)) == 1
    finally:
        reset_uncategorised_rules()
