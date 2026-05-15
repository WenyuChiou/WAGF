"""Unit tests for broker.tools.recover_csv_from_jsonl (Phase 6G crash recovery).

Validates:
1. Recovery produces CSV with identical column schema to live-finalized CSV
2. Truncated final JSONL line is tolerated (mid-write crash recovery)
3. Empty directory raises clean error
4. Multiple agent types -> separate CSV per agent type
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from broker.tools.recover_csv_from_jsonl import recover_csv, _read_jsonl_safely
from broker.components.analytics.audit import (
    GenericAuditWriter,
    AuditConfig,
    trace_to_csv_row,
    compute_csv_fieldnames,
)


def _make_trace(step_id: int, year: int, status: str = "APPROVED",
                wsa: str = "M", aca: str = "M",
                fallback: bool = False) -> dict:
    return {
        "step_id": step_id,
        "agent_id": f"agent_{step_id % 3}",
        "year": year,
        "timestamp": "2026-05-15T00:00:00",
        "retry_count": 0,
        "fallback_activated": fallback,
        "skill_proposal": {
            "skill_name": "maintain_demand",
            "raw_output": "{}",
            "parse_layer": "json",
            "parse_confidence": 1.0,
            "reasoning": {
                "WSA_LABEL": wsa,
                "ACA_LABEL": aca,
                "wsa_reason": "moderate scarcity",
            },
        },
        "approved_skill": {
            "skill_name": "maintain_demand",
            "status": status,
        },
    }


def test_recover_csv_basic(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    jsonl_path = raw_dir / "test_agent_traces.jsonl"
    traces = [_make_trace(i, year=i // 3 + 1) for i in range(10)]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")

    summary = recover_csv(tmp_path)
    assert "test_agent" in summary
    info = summary["test_agent"]
    assert info["rows_recovered"] == 10
    assert info["lines_skipped"] == 0

    csv_path = tmp_path / "test_agent_governance_audit.csv"
    assert csv_path.exists()
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 10
    assert "construct_WSA_LABEL" in rows[0]
    assert rows[0]["construct_WSA_LABEL"] == "M"


def test_recover_handles_truncated_last_line(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    jsonl_path = raw_dir / "agent_traces.jsonl"
    traces = [_make_trace(i, year=1) for i in range(5)]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")
        f.write('{"step_id": 99, "year": 2, "incomplete')

    parsed, skipped = _read_jsonl_safely(jsonl_path)
    assert len(parsed) == 5
    assert skipped == 1

    summary = recover_csv(tmp_path)
    assert summary["agent"]["rows_recovered"] == 5
    assert summary["agent"]["lines_skipped"] == 1


def test_recover_no_jsonl_raises(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        recover_csv(tmp_path)


def test_recover_missing_raw_dir(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        recover_csv(tmp_path)


def test_recovered_csv_matches_live_finalize_schema(tmp_path: Path):
    """Critical invariant: recovery CSV column order == live finalize CSV order."""
    output_dir = tmp_path / "live"
    config = AuditConfig(output_dir=str(output_dir),
                         experiment_name="schema_test",
                         clear_existing_traces=False)
    writer = GenericAuditWriter(config)
    for i in range(5):
        writer.write_trace("schema_agent", _make_trace(i, year=1))
    writer.finalize()

    live_csv = output_dir / "schema_agent_governance_audit.csv"
    assert live_csv.exists()
    with open(live_csv, "r", encoding="utf-8-sig") as f:
        live_cols = next(csv.reader(f))

    recovery_dir = tmp_path / "recovered"
    recovery_dir.mkdir()
    (recovery_dir / "raw").mkdir()
    shutil.copy(output_dir / "raw" / "schema_agent_traces.jsonl",
                recovery_dir / "raw" / "schema_agent_traces.jsonl")
    recover_csv(recovery_dir)

    rec_csv = recovery_dir / "schema_agent_governance_audit.csv"
    with open(rec_csv, "r", encoding="utf-8-sig") as f:
        rec_cols = next(csv.reader(f))

    assert live_cols == rec_cols, (
        f"Column order drift between live and recovered CSV.\n"
        f"Live: {live_cols}\nRecovered: {rec_cols}"
    )


def test_fallback_activated_reflects_trace_field(tmp_path: Path):
    """fallback_activated column must reflect trace's top-level field
    (Phase 6G schema bug fix: previously inferred only from status string)."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    jsonl_path = raw_dir / "agent_traces.jsonl"
    traces = [
        _make_trace(1, year=1, status="APPROVED", fallback=False),
        _make_trace(2, year=1, status="REJECTED", fallback=True),
        _make_trace(3, year=1, status="REJECTED_FALLBACK", fallback=True),
    ]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")

    recover_csv(tmp_path)
    with open(tmp_path / "agent_governance_audit.csv", "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["fallback_activated"] == "False"
    assert rows[1]["fallback_activated"] == "True"
    assert rows[2]["fallback_activated"] == "True"
