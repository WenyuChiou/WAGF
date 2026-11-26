"""Tests for context-budget truncation provenance in run_integrity.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from broker.core.run_integrity import record_run_integrity, scan_context_budget
from broker.tools.check_run_integrity import main as check_run_integrity_main


def _write_traces(output_dir: Path, rows: list[dict]) -> None:
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    trace_file = raw_dir / "operator_traces.jsonl"
    lines = [json.dumps({"_metadata": {"audit_schema_version": "2"}})]
    lines.extend(json.dumps(row) for row in rows)
    trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_clean_and_zero_ctx_runs_omit_context_budget_keys(tmp_path):
    _write_traces(
        tmp_path,
        [
            {"step_id": 1, "llm_stats": {"prompt_tokens": 400, "num_ctx": 4096}},
            {"step_id": 2, "llm_stats": {"prompt_tokens": 500, "num_ctx": 0}},
        ],
    )
    assert scan_context_budget(tmp_path) == {}
    audit = record_run_integrity(tmp_path, verbose=False)
    for key in (
        "context_budget_near_limit_rows",
        "context_budget_truncated_rows",
        "max_context_utilization",
    ):
        assert key not in audit


def test_near_limit_peak_recorded_without_false_truncation(tmp_path):
    _write_traces(
        tmp_path,
        [
            {
                "step_id": 1,
                "llm_stats": {
                    "prompt_tokens": 300,
                    "num_ctx": 4096,
                    "prompt_tokens_peak": 3800,
                    "num_ctx_peak": 4096,
                },
            }
        ],
    )
    audit = record_run_integrity(tmp_path, verbose=False)
    assert audit["context_budget_near_limit_rows"] == 1
    assert audit["context_budget_truncated_rows"] == 0
    assert audit["max_context_utilization"] == round(3800 / 4096, 4)


def test_truncated_run_logs_warning_and_surfaces_in_cli(tmp_path, caplog, capsys):
    _write_traces(
        tmp_path,
        [
            {"step_id": 1, "llm_stats": {"prompt_tokens": 4200, "num_ctx": 4096}},
        ],
    )
    with caplog.at_level(logging.WARNING):
        audit = record_run_integrity(tmp_path, verbose=False)
    assert audit["context_budget_near_limit_rows"] == 1
    assert audit["context_budget_truncated_rows"] == 1
    assert any("[Integrity]" in rec.message and "num_ctx" in rec.message for rec in caplog.records)

    try:
        check_run_integrity_main([str(tmp_path)])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "ctx_truncated=1" in out


def test_invalid_utf8_trace_line_is_skipped_without_dropping_integrity(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    trace_file = raw_dir / "operator_traces.jsonl"
    trace_file.write_bytes(
        b'{"_metadata": {"audit_schema_version": "2"}}\n'
        b"\xff\xfecorrupt\n"
        b'{"step_id": 1, "llm_stats": {"prompt_tokens": 4200, "num_ctx": 4096}}\n'
    )
    audit = record_run_integrity(tmp_path, verbose=False)
    assert (tmp_path / "run_integrity.json").is_file()
    assert audit["context_budget_truncated_rows"] == 1

