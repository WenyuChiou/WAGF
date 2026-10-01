"""feat/v3-parallel-determinism: with the mock LLM, an irrigation v3 run at
--workers N (N = 1, 4, 8) must produce the same outputs regardless of
thread-completion order. The two ordering fixes (in
ExperimentRunner._run_agents_parallel and GenericAuditWriter._export_csv)
are documented no-ops at workers=1, so --workers 1 is the reference point
every other worker count is compared against below.

The byte-identity tests use
examples/irrigation_abm/tests/_hash_scripted_llm_harness.py (a subprocess,
not pytest's monkeypatch fixture, so each run gets a fresh process and
GovernanceAuditor's class-level singleton never leaks between the
workers=1/4/8 comparisons) instead of the stock ``--model mock`` invoke:
the stock mock always answers ``{"decision": 1}`` and states no WSA/ACA
label, so it never exercises strict's TR1/TR3 thinking rules, the
appraisal freeze, or more than one format-retry shape. The harness answers
every prompt from a hash of the prompt text itself (so completion order can
never change what one prompt resolves to) plus a per-prompt 0 to 20 ms
sleep (also derived from the hash) to scramble which thread finishes first.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from broker.tools.compare_audit_csv import compare  # noqa: E402

HARNESS = Path(__file__).resolve().parent / "_hash_scripted_llm_harness.py"
AUDIT_CSV_NAME = "irrigation_farmer_governance_audit.csv"


def _run(script: Path, output_dir: Path, governance_mode: str, workers: int,
         timeout: int = 180) -> subprocess.CompletedProcess:
    args = [
        sys.executable, str(script),
        "--model", "mock", "--real", "--years", "3", "--seed", "42",
        "--governance-mode", governance_mode, "--workers", str(workers),
        "--output", str(output_dir),
    ]
    result = subprocess.run(
        args, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, (
        f"{script.name} failed (governance_mode={governance_mode}, "
        f"workers={workers}):\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    return result


def _assert_runs_match(base_dir: Path, other_dir: Path, label: str) -> None:
    sim_rc = compare(base_dir / "simulation_log.csv", other_dir / "simulation_log.csv")
    assert sim_rc == 0, f"simulation_log.csv differs {label}"

    audit_rc = compare(base_dir / AUDIT_CSV_NAME, other_dir / AUDIT_CSV_NAME)
    assert audit_rc == 0, f"{AUDIT_CSV_NAME} (row order or content) differs {label}"

    base_summary = json.loads((base_dir / "governance_summary.json").read_text(encoding="utf-8"))
    other_summary = json.loads((other_dir / "governance_summary.json").read_text(encoding="utf-8"))
    assert base_summary == other_summary, f"governance_summary.json differs {label}"

    base_integrity = json.loads((base_dir / "run_integrity.json").read_text(encoding="utf-8"))
    other_integrity = json.loads((other_dir / "run_integrity.json").read_text(encoding="utf-8"))
    assert base_integrity == other_integrity, f"run_integrity.json differs {label}"


@pytest.mark.parametrize("governance_mode", ["strict", "feasibility_only"])
def test_workers_1_4_8_byte_identical(tmp_path: Path, governance_mode: str):
    base_dir = tmp_path / "w1"
    _run(HARNESS, base_dir, governance_mode, workers=1)

    base_summary = json.loads((base_dir / "governance_summary.json").read_text(encoding="utf-8"))
    if governance_mode == "strict":
        # Sanity: the hash-scripted mock must actually exercise governance
        # (TR1/TR3, retries, the appraisal freeze) or this test proves
        # nothing beyond the trivial all-approved path the stock mock
        # already covers.
        assert base_summary["total_interventions"] > 0, (
            "hash-scripted mock triggered no governance intervention in "
            "strict mode; this run exercises nothing beyond the trivial "
            "all-approved path"
        )

    for workers in (4, 8):
        other_dir = tmp_path / f"w{workers}"
        _run(HARNESS, other_dir, governance_mode, workers=workers)
        _assert_runs_match(
            base_dir, other_dir,
            f"between workers=1 and workers={workers} ({governance_mode})",
        )
