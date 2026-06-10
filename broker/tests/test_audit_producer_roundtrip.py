"""Producer-roundtrip contract for audit artifact consumers.

Consumers of audit artifacts are tested against REAL writer output
(producer-roundtrip), never hand-built fixtures -- the 2026-06-10 readiness
key-mismatch P0 shipped because the fixture used the consumer's keys.
"""
from __future__ import annotations

import json
from pathlib import Path

from broker.components.analytics.audit import AuditConfig, GenericAuditWriter
from broker.components.analytics.terminal_taxonomy import classify_terminal
from broker.components.validation.readiness_profile import load_readiness_profile
from broker.governance.rule_types import GovernanceRule
from broker.interfaces.skill_types import ValidationResult
from broker.tools.readiness_report import _firing, compute_readiness_report
from broker.validators.governance.physical_validator import PhysicalValidator


ERROR_RULE_ID = "roundtrip_physical_error"
WARNING_RULE_ID = "roundtrip_physical_warning"
BUILTIN_RULE_ID = "roundtrip_pool_insolvent"
NEVER_RULE_ID = "roundtrip_never_emitted"


def _rules() -> list[GovernanceRule]:
    return [
        GovernanceRule(
            id=ERROR_RULE_ID,
            category="physical",
            subcategory="state",
            precondition="blocked_state",
            blocked_skills=["approve_payout"],
            level="ERROR",
            message="approve_payout is blocked by state",
        ),
        GovernanceRule(
            id=WARNING_RULE_ID,
            category="physical",
            subcategory="state",
            precondition="warn_state",
            blocked_skills=["approve_payout"],
            level="WARNING",
            message="approve_payout should warn on state",
        ),
    ]


def _cat_model_style_check(skill_name, rules, context):
    if skill_name != "approve_payout" or not context.get("pool_insolvent"):
        return []
    return [
        ValidationResult(
            valid=False,
            validator_name="insurer_payout_solvency_check",
            errors=["approve_payout would overdraw the pool"],
            metadata={
                "category": "physical",
                "rule_id": BUILTIN_RULE_ID,
                "deterministic": True,
            },
        )
    ]


def _trace(agent_id: str, year: int, status: str) -> dict:
    return {
        "step_id": year,
        "year": year,
        "agent_id": agent_id,
        "agent_type": "insurer",
        "skill_proposal": {
            "skill_name": "approve_payout",
            "agent_id": agent_id,
            "agent_type": "insurer",
            "reasoning": {},
            "parsing_warnings": [],
        },
        "approved_skill": {
            "skill_name": "approve_payout",
            "status": status,
        },
        "retry_count": 0,
        "format_retries": 0,
        "memory_audit": {},
        "social_audit": {},
        "cognitive_audit": {},
        "rule_breakdown": {},
    }


def _jsonl_records(results_dir: Path) -> list[dict]:
    raw_path = results_dir / "raw" / "insurer_traces.jsonl"
    records = []
    with raw_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            if "_metadata" not in obj:
                records.append(obj)
    return records


def test_audit_artifact_consumers_use_real_writer_validator_health(tmp_path):
    writer = GenericAuditWriter(
        AuditConfig(output_dir=str(tmp_path), experiment_name="roundtrip")
    )
    validator = PhysicalValidator(builtin_checks=[_cat_model_style_check])
    rules = _rules()

    error_results = validator.validate(
        "approve_payout",
        rules,
        {"state": {"blocked_state": True, "warn_state": False}},
    )
    warning_results = validator.validate(
        "approve_payout",
        rules,
        {"state": {"blocked_state": False, "warn_state": True}},
    )
    builtin_results = validator.validate(
        "approve_payout",
        [],
        {"pool_insolvent": True},
    )

    assert any(
        not r.valid and r.metadata.get("rule_id") == ERROR_RULE_ID
        for r in error_results
    )
    assert any(
        r.valid and r.warnings and r.metadata.get("rule_id") == WARNING_RULE_ID
        for r in warning_results
    )
    assert any(
        not r.valid and r.metadata.get("rule_id") == BUILTIN_RULE_ID
        for r in builtin_results
    )

    writer.write_trace(
        "insurer",
        _trace("A-error", 1, "REJECTED"),
        validation_results=error_results,
    )
    writer.write_trace(
        "insurer",
        _trace("A-warning", 2, "APPROVED"),
        validation_results=warning_results,
    )
    writer.write_trace(
        "insurer",
        _trace("A-builtin", 3, "REJECTED"),
        validation_results=builtin_results,
    )
    writer.finalize()

    with (tmp_path / "audit_summary.json").open("r", encoding="utf-8") as f:
        summary = json.load(f)
    health = summary["validator_health"]

    assert health[ERROR_RULE_ID]["fire_count"] >= 1
    assert _firing(health[ERROR_RULE_ID]) is True

    report = compute_readiness_report(tmp_path, load_readiness_profile("functional"))
    assert ERROR_RULE_ID not in report.metrics.dead_validators
    assert report.metrics.validator_firing_diversity >= 3

    records = _jsonl_records(tmp_path)
    # Review S1: valid-with-warnings results must stay in the WARNINGS channel —
    # the F2 + classify_terminal pipeline depends on validation_issues carrying
    # only blocking results.
    warning_trace = next(t for t in records if t["agent_id"] == "A-warning")
    assert all(
        i.get("rule_id") != WARNING_RULE_ID
        for i in warning_trace.get("validation_issues", [])
    ), "WARNING rules must not appear in validation_issues (warnings channel only)"
    assert any(
        w.get("rule_id") == WARNING_RULE_ID
        for w in warning_trace.get("validation_warnings_list", [])
    )
    error_trace = next(t for t in records if t["agent_id"] == "A-error")
    error_issue = next(
        i for i in error_trace["validation_issues"]
        if i["rule_id"] == ERROR_RULE_ID
    )
    assert error_issue["metadata"]["expected_terminal"] is True
    assert classify_terminal(
        {
            "status": "REJECTED",
            "retry_count": 0,
            "format_retries": 0,
            "validation_issues": [error_issue],
        }
    ) == "expected_hard_block"

    assert NEVER_RULE_ID not in health
