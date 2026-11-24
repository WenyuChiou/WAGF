"""The first-run demo (reservoir mock): one block, one repair, one change in the toy model."""
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESERVOIR_CONFIG = "examples/reservoir_control/config/reservoir_agent_types.yaml"


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    out = tmp_path_factory.mktemp("first_run") / "run"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "broker.run", RESERVOIR_CONFIG, "--model", "mock", "--years", "4", "--output", str(out)],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out, result.stdout


def _records(out):
    lines = (out / "raw" / "operator_traces.jsonl").read_text(encoding="utf-8").splitlines()
    return [r for r in map(json.loads, lines) if "step_id" in r]


def test_audit_has_one_blocked_then_approved_decision(demo):
    out, _ = demo
    with (out / "operator_governance_audit.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 4
    repaired = [r for r in rows if int(r["retry_count"]) > 0]
    assert len(repaired) == 1
    row = repaired[0]
    assert (row["agent_id"], row["year"], row["status"]) == ("OPERATOR", "3", "APPROVED")
    assert row["failed_rules"] == "dead_pool_violation"
    assert int(row["retry_count"]) == 1
    assert all(r["status"] == "APPROVED" for r in rows)


def test_trace_keeps_the_block_reason_for_the_same_step(demo):
    out, _ = demo
    step = [r for r in _records(out) if r["retry_count"]][0]
    assert step["outcome"] == "RETRY_SUCCESS"
    assert step["approved_skill"]["status"] == "APPROVED"
    errors = [e for v in step["validation_issues"] for e in v["errors"]]
    assert any("dead_pool_violation" in e and "storage_unclamped" in e for e in errors)
    assert step["skill_proposal"]["reasoning"]["magnitude"] == 50


def test_executed_change_reaches_the_toy_reservoir(demo):
    out, _ = demo
    records = {r["year"]: r for r in _records(out)}
    delta = records[3]["execution_result"]["action_context"]["world_delta"]["world_changes"]
    assert delta["release_target"] == pytest.approx(0.375)
    # The release the solver then ran is half of the year-3 one, and storage stays above dead pool.
    assert records[4]["environment_context"]["release_actual"] == pytest.approx(0.375)
    assert records[4]["environment_context"]["storage"] > records[4]["environment_context"]["dead_pool"]
    assert records[4]["environment_context"]["storage"] < records[3]["environment_context"]["storage"]


def test_console_summary_shows_block_reason_repair_and_effect(demo):
    _, stdout = demo
    summary = stdout.split("Block and repair in this run:")[1]
    assert "BLOCKED: set_release (requested release_target=0.75)" in summary
    assert "breaks dead_pool_violation" in summary
    assert "APPROVED: set_release at 50% of demand" in summary
    assert "0.750 -> 0.375 maf/month" in summary
    assert "storage 7.543 maf at year 3, 6.362 maf at year 4" in summary


def _summarize():
    sys.path.insert(0, str(ROOT))
    from examples.reservoir_control.ops_case import summarize_block_and_repair
    return summarize_block_and_repair


def _write_trace(out, records):
    (out / "raw").mkdir(parents=True)
    (out / "raw" / "operator_traces.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _record(step_id, retry_count):
    return {
        "step_id": step_id, "year": step_id, "agent_id": "OPERATOR", "retry_count": retry_count,
        "validation_issues": [{"errors": ["below dead pool."]}] if retry_count else [],
        "environment_context": {"storage": 7.0, "release_actual": 0.75, "dead_pool": 6.0},
        "skill_proposal": {"reasoning": {"magnitude": 40}},
        "approved_skill": {"status": "APPROVED", "skill_name": "set_release"},
        "execution_result": {"action_context": {"world_delta": {"world_changes": {"release_target": 0.3}}}},
    }


def test_summary_without_trace_file_says_so(tmp_path):
    lines = _summarize()(tmp_path)
    assert len(lines) == 1 and "no trace file" in lines[0]


def test_summary_is_empty_when_nothing_was_blocked(tmp_path):
    _write_trace(tmp_path, [_record(1, 0), _record(2, 0)])
    assert _summarize()(tmp_path) == []


def test_summary_counts_attempts_when_blocked_twice(tmp_path):
    _write_trace(tmp_path, [_record(1, 2)])
    lines = _summarize()(tmp_path)
    assert lines[1].startswith("  attempts 1-2 BLOCKED: below dead pool.")
    assert lines[2].startswith("  attempt 3  APPROVED: set_release at 40% of demand")


def test_summary_handles_a_retry_that_ends_without_a_proposal(tmp_path):
    rec = _record(1, 3)
    rec.update(skill_proposal=None, approved_skill=None, execution_result=None)
    _write_trace(tmp_path, [rec])
    lines = _summarize()(tmp_path)
    assert lines[1].startswith("  attempts 1-3 BLOCKED: below dead pool.")
    assert lines[2] == ("  attempt 4  NO DECISION: no parsable proposal after the retries; "
                        "see the trace for the fallback")
    assert len(lines) == 3
