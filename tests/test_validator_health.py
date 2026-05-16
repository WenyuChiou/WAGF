from __future__ import annotations

import csv
import json
from pathlib import Path

from broker.components.analytics.audit import AuditConfig, GenericAuditWriter
from broker.interfaces.skill_types import ValidationResult


def _make_trace(step_id: int) -> dict:
    return {
        "step_id": step_id,
        "agent_id": f"agent_{step_id}",
        "year": 2026,
        "timestamp": "2026-05-16T00:00:00",
        "retry_count": 0,
        "fallback_activated": False,
        "skill_proposal": {
            "skill_name": "maintain_demand",
            "raw_output": "{}",
            "parse_layer": "json",
            "parse_confidence": 1.0,
            "reasoning": {"WSA_LABEL": "M"},
        },
        "approved_skill": {
            "skill_name": "maintain_demand",
            "status": "APPROVED",
        },
    }


def _make_writer(output_dir: Path) -> GenericAuditWriter:
    config = AuditConfig(
        output_dir=str(output_dir),
        experiment_name="validator_health",
        clear_existing_traces=True,
    )
    return GenericAuditWriter(config)


def _result(rule_id: str, valid: bool = True, warnings: list[str] | None = None) -> ValidationResult:
    return ValidationResult(
        valid=valid,
        validator_name=f"{rule_id}_validator",
        errors=[] if valid else ["blocked"],
        warnings=warnings or [],
        metadata={"rule_id": rule_id},
    )


def _health_rows(path: Path) -> dict[str, dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        return {row["rule_id"]: row for row in csv.DictReader(f)}


def test_validator_health_records_firing_rule_counts_and_rate(tmp_path: Path):
    writer = _make_writer(tmp_path)
    n = 3

    for step_id in range(n):
        writer.write_trace(
            "schema_agent",
            _make_trace(step_id),
            validation_results=[_result("rule_A", valid=False)],
        )
    writer.finalize()

    health_path = tmp_path / "validator_health.csv"
    assert health_path.exists()
    row = _health_rows(health_path)["rule_A"]
    assert row["seen_count"] == str(n)
    assert row["fire_count"] == str(n)
    assert row["fire_rate"] == "1.0"


def test_validator_health_records_seen_but_never_firing_rule(tmp_path: Path):
    writer = _make_writer(tmp_path)
    n = 4

    for step_id in range(n):
        writer.write_trace(
            "schema_agent",
            _make_trace(step_id),
            validation_results=[_result("rule_B", valid=True)],
        )
    writer.finalize()

    row = _health_rows(tmp_path / "validator_health.csv")["rule_B"]
    assert row["seen_count"] == str(n)
    assert row["fire_count"] == "0"
    assert row["fire_rate"] == "0.0"


def test_validator_health_records_warning_only_rule_without_fire(tmp_path: Path):
    writer = _make_writer(tmp_path)

    writer.write_trace(
        "schema_agent",
        _make_trace(1),
        validation_results=[_result("rule_C", valid=True, warnings=["w"])],
    )
    writer.finalize()

    row = _health_rows(tmp_path / "validator_health.csv")["rule_C"]
    assert int(row["warn_count"]) >= 1
    assert row["fire_count"] == "0"


def test_audit_summary_retains_existing_keys_and_adds_validator_health(tmp_path: Path):
    writer = _make_writer(tmp_path)
    writer.write_trace(
        "schema_agent",
        _make_trace(1),
        validation_results=[_result("rule_A", valid=False)],
    )
    summary = writer.finalize()

    summary_path = tmp_path / "audit_summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        persisted = json.load(f)

    expected_existing = {
        "experiment_name",
        "framework_version",
        "audit_schema_version",
        "git_commit_short",
        "agent_types",
        "total_traces",
        "validation_errors",
        "validation_warnings",
        "structural_faults_fixed",
        "total_format_retries",
    }
    assert expected_existing.issubset(summary.keys())
    assert expected_existing.issubset(persisted.keys())
    assert isinstance(summary["validator_health"], dict)
    assert isinstance(persisted["validator_health"], dict)


def test_validator_health_keeps_distinct_rules_independent(tmp_path: Path):
    """Mixed batch in one writer: rule_A fires 2/5, rule_B 0/5.

    Guards against setdefault key aliasing — distinct rule_ids must keep
    independent counters (code-review W3 gap).
    """
    writer = _make_writer(tmp_path)
    n = 5
    for step_id in range(n):
        a_fires = step_id < 2  # rule_A blocking on the first 2 of 5
        writer.write_trace(
            "schema_agent",
            _make_trace(step_id),
            validation_results=[
                _result("rule_A", valid=not a_fires),
                _result("rule_B", valid=True),
            ],
        )
    writer.finalize()

    rows = _health_rows(tmp_path / "validator_health.csv")
    a, b = rows["rule_A"], rows["rule_B"]
    assert a["seen_count"] == str(n) and b["seen_count"] == str(n)
    assert a["fire_count"] == "2" and b["fire_count"] == "0"
    assert float(a["fire_rate"]) == 0.4  # 2/5, robust to str formatting
    assert float(b["fire_rate"]) == 0.0
