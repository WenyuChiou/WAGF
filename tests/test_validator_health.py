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


# --- per-agent-type validator_health (Gate-3 item 4) ---

def _pt_rows(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        return {(r["agent_type"], r["rule_id"]): r for r in csv.DictReader(f)}


def test_validator_health_per_type_splits_by_agent_type_and_global_is_sum(tmp_path: Path):
    """Same rule fired under two agent_types -> 2 per-type rows; the
    UNCHANGED global validator_health.csv counts == sum across types."""
    writer = _make_writer(tmp_path)
    for step_id in range(2):
        writer.write_trace("owner", _make_trace(step_id),
                            validation_results=[_result("rule_X", valid=False)])
    for step_id in range(3):
        writer.write_trace("renter", _make_trace(10 + step_id),
                            validation_results=[_result("rule_X", valid=False)])
    writer.finalize()

    pt = _pt_rows(tmp_path / "validator_health_by_agent_type.csv")
    assert ("owner", "rule_X") in pt and ("renter", "rule_X") in pt
    assert pt[("owner", "rule_X")]["fire_count"] == "2"
    assert pt[("renter", "rule_X")]["fire_count"] == "3"
    # global unchanged: equals the sum of the per-type buckets
    g = _health_rows(tmp_path / "validator_health.csv")["rule_X"]
    assert g["seen_count"] == "5" and g["fire_count"] == "5"


def test_validator_health_per_type_dead_for_all_false_when_fires_somewhere(tmp_path: Path):
    """rule fires for agent_a, only seen (no fire) for agent_b ->
    agent_b bucket fire_count 0; rule's dead_for_all == False."""
    writer = _make_writer(tmp_path)
    writer.write_trace("agent_a", _make_trace(1),
                       validation_results=[_result("rule_Y", valid=False)])
    writer.write_trace("agent_b", _make_trace(2),
                       validation_results=[_result("rule_Y", valid=True)])
    writer.finalize()

    pt = _pt_rows(tmp_path / "validator_health_by_agent_type.csv")
    assert pt[("agent_b", "rule_Y")]["fire_count"] == "0"
    assert pt[("agent_a", "rule_Y")]["dead_for_all"] == "False"
    assert pt[("agent_b", "rule_Y")]["dead_for_all"] == "False"


def test_validator_health_dead_for_all_true_and_warns(tmp_path: Path, caplog):
    """rule seen>0 fire==0 for ALL agent_types -> dead_for_all True AND
    a loud DEAD VALIDATOR warning naming the rule."""
    writer = _make_writer(tmp_path)
    writer.write_trace("owner", _make_trace(1),
                       validation_results=[_result("rule_dead", valid=True)])
    writer.write_trace("renter", _make_trace(2),
                       validation_results=[_result("rule_dead", valid=True)])
    with caplog.at_level("WARNING"):
        writer.finalize()

    pt = _pt_rows(tmp_path / "validator_health_by_agent_type.csv")
    assert pt[("owner", "rule_dead")]["dead_for_all"] == "True"
    assert pt[("renter", "rule_dead")]["dead_for_all"] == "True"
    assert "DEAD VALIDATOR" in caplog.text and "rule_dead" in caplog.text


def test_validator_health_no_dead_warning_when_fires_everywhere(tmp_path: Path, caplog):
    """rule fires for every agent_type that saw it -> NO DEAD VALIDATOR
    warning (no false positive)."""
    writer = _make_writer(tmp_path)
    writer.write_trace("owner", _make_trace(1),
                       validation_results=[_result("rule_live", valid=False)])
    writer.write_trace("renter", _make_trace(2),
                       validation_results=[_result("rule_live", valid=False)])
    with caplog.at_level("WARNING"):
        writer.finalize()

    pt = _pt_rows(tmp_path / "validator_health_by_agent_type.csv")
    assert pt[("owner", "rule_live")]["dead_for_all"] == "False"
    assert "DEAD VALIDATOR" not in caplog.text
