"""Subprocess e2e coverage for the generated-domain on-ramp."""
from __future__ import annotations

import csv
import json
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

    # Round 3 (2026-09) regression lock: the scaffolded prompt renders
    # {options_text} (broker/tools/scaffold_domain.py:gen_prompt), but the
    # generated run_experiment.py used to rely on ExperimentBuilder's
    # DEFAULT context builder (create_context_builder() with no hub ->
    # plain BaseAgentContextBuilder), which does NOT fill {options_text}
    # at all -- it falls through to SafeFormatter's "[N/A]" placeholder,
    # so the LLM saw a completely empty menu despite validate_prompt and
    # the options-text-parity guard both reporting clean (neither one
    # checks RUNTIME rendering, only template-time and order-safety).
    # gen_run_experiment() now pins an explicit TieredContextBuilder
    # (hub=None), matching examples/vaccination_demo /
    # examples/irrigation_abm's established fix for the exact same gap.
    raw_trace = output_dir / "raw" / "agent_traces.jsonl"
    assert raw_trace.exists(), f"missing raw trace: {raw_trace}"
    trace_lines = raw_trace.read_text(encoding="utf-8").splitlines()
    # Line 0 is the `_metadata` header row (see broker/core/experiment_runner.py
    # audit-schema-2 raw writer); the first real decision trace is line 1.
    first_decision = json.loads(trace_lines[1])
    rendered_prompt = first_decision.get("input", "")
    assert "Available actions" in rendered_prompt
    # Scope the check to the options section specifically (not the whole
    # prompt): {narrative_persona} is a separate, pre-existing,
    # out-of-scope gap in the scaffolded agent's context (it isn't wired
    # to set a persona string) and legitimately renders "[N/A]" -- that
    # is not what this regression lock is about.
    options_section = rendered_prompt.split("Available actions", 1)[1]
    assert "[N/A]" not in options_section.split("\n\n", 1)[0], (
        "the scaffolded prompt's {options_text} placeholder rendered as "
        "SafeFormatter's unfilled default -- the generated runner is not "
        "wired to a context builder that actually fills it. Full options "
        f"section: {options_section[:300]!r}"
    )
    assert "1. " in options_section and "2. " in options_section, (
        "expected a live numbered options list (from {options_text}), got: "
        f"{options_section[:400]!r}"
    )
