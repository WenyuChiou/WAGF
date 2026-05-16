from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from broker.components.analytics.audit import (
    AuditConfig,
    GenericAuditWriter,
    audit_run_metadata,
)
from broker.tools.recover_csv_from_jsonl import main, recover_csv


def _make_trace(step_id: int, year: int = 2026) -> dict:
    return {
        "step_id": step_id,
        "agent_id": f"agent_{step_id}",
        "year": year,
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


def _write_audit_run(output_dir: Path, agent_type: str = "schema_agent", count: int = 3):
    config = AuditConfig(
        output_dir=str(output_dir),
        experiment_name="schema_versioning",
        clear_existing_traces=True,
    )
    writer = GenericAuditWriter(config)
    for step_id in range(count):
        writer.write_trace(agent_type, _make_trace(step_id))
    summary = writer.finalize()
    return summary


def _csv_header(path: Path) -> list[str]:
    with open(path, "r", encoding="utf-8-sig") as f:
        return next(csv.reader(f))


def test_audit_run_metadata_returns_non_empty_strings():
    metadata = audit_run_metadata()

    assert set(metadata) == {
        "framework_version",
        "audit_schema_version",
        "git_commit_short",
    }
    for value in metadata.values():
        assert isinstance(value, str)
        assert value


def test_audit_summary_contains_run_metadata(tmp_path: Path):
    expected = audit_run_metadata()

    summary = _write_audit_run(tmp_path, count=2)
    summary_path = tmp_path / "audit_summary.json"
    with open(summary_path, "r", encoding="utf-8") as f:
        persisted = json.load(f)

    for key, value in expected.items():
        assert summary[key] == value
        assert persisted[key] == value


def test_jsonl_first_line_is_metadata_and_second_line_is_trace(tmp_path: Path):
    _write_audit_run(tmp_path, agent_type="household", count=2)

    jsonl_path = tmp_path / "raw" / "household_traces.jsonl"
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3

    first = json.loads(lines[0])
    assert first["agent_type"] == "household"
    assert set(first["_metadata"]) == {
        "framework_version",
        "audit_schema_version",
        "git_commit_short",
    }

    second = json.loads(lines[1])
    assert second["step_id"] == 0
    assert "_metadata" not in second


def test_recovery_skips_metadata_row_and_matches_live_schema(tmp_path: Path):
    live_dir = tmp_path / "live"
    _write_audit_run(live_dir, count=4)
    live_csv = live_dir / "schema_agent_governance_audit.csv"

    recovery_dir = tmp_path / "recovered"
    (recovery_dir / "raw").mkdir(parents=True)
    shutil.copy(
        live_dir / "raw" / "schema_agent_traces.jsonl",
        recovery_dir / "raw" / "schema_agent_traces.jsonl",
    )

    summary = recover_csv(recovery_dir)

    assert summary["schema_agent"]["rows_recovered"] == 4
    recovered_csv = recovery_dir / "schema_agent_governance_audit.csv"
    with open(recovered_csv, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4
    assert _csv_header(recovered_csv) == _csv_header(live_csv)


def test_recovery_cli_reports_metadata_schema(tmp_path: Path, capsys):
    _write_audit_run(tmp_path, count=1)
    jsonl_path = tmp_path / "raw" / "schema_agent_traces.jsonl"
    metadata = json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[0])["_metadata"]

    exit_code = main([str(tmp_path)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert (
        f"schema: framework={metadata['framework_version']} "
        f"audit_schema={metadata['audit_schema_version']} "
        f"git={metadata['git_commit_short']}"
    ) in captured.out
