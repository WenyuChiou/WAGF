"""Subprocess e2e coverage for the generated-domain on-ramp."""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.slow


REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_with_repo_pythonpath() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(REPO_ROOT) if not existing else str(REPO_ROOT) + os.pathsep + existing
    )
    return env


def _run(cmd: list[str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=_env_with_repo_pythonpath(),
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )


def _assert_ok(result: subprocess.CompletedProcess[str], label: str) -> None:
    tail = "\n".join((result.stderr or result.stdout).splitlines()[-40:])
    assert result.returncode == 0, f"{label} failed with {result.returncode}\n{tail}"


def test_scaffolded_generic_domain_validates_and_runs_with_mock(tmp_path):
    """Ship tmp_path scaffolding.

    The emitted runner inserts the generated package's parent into sys.path,
    and each subprocess also receives PYTHONPATH={repo root}, so the scaffold
    does not need to live under examples/. Keeping it in tmp_path avoids
    repository cleanup while still exercising the CLI surface that regressed.
    """
    domain = "scaffold_e2e_probe"
    scaffold_dir = tmp_path / domain
    output_dir = tmp_path / "smoke_output"

    scaffold = _run(
        [
            sys.executable,
            "-m",
            "broker.tools.scaffold_domain",
            domain,
            "--output",
            str(scaffold_dir),
            "--framework",
            "generic",
        ]
    )
    _assert_ok(scaffold, "scaffold_domain")

    validate = _run(
        [
            sys.executable,
            "-m",
            "broker.tools.validate_prompt",
            str(scaffold_dir / "config" / "agent_types.yaml"),
        ]
    )
    _assert_ok(validate, "validate_prompt")

    run = _run(
        [
            sys.executable,
            str(scaffold_dir / "run_experiment.py"),
            "--model",
            "mock",
            "--years",
            "1",
            "--output",
            str(output_dir),
        ]
    )
    _assert_ok(run, "generated runner")

    audit_csv = output_dir / "agent_governance_audit.csv"
    assert audit_csv.exists(), f"missing audit CSV: {audit_csv}"

    with audit_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    # 5 == scaffold_domain's argparse default for --agents (see
    # broker/tools/scaffold_domain.py); 1 == the --years we passed.
    assert len(rows) == 5 * 1
