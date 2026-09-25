"""Regression pin: the published paper config
(``examples/irrigation_abm/config/agent_types.yaml``) ships with
``global_config.coupling.context_contract: true`` (PR-9 F1 guard on
``IrrigationEnvironment.get_agent_context()``).

Byte-identity between the flag OFF and ON was verified with 4 mock runs
(3 years, seed 42, workers 1, strict AND disabled governance) before the
paper config was flipped: identical ``irrigation_farmer_governance_audit.csv``
(``broker.tools.compare_audit_csv``), identical ``simulation_log.csv``, and
an identical year-2 rendered prompt for one agent read from
``raw/irrigation_farmer_traces.jsonl``. See CHANGELOG ``[Unreleased]`` and
``AgentTypeConfig.get_coupling_context_contract`` for what the flag does and
does not change on the happy path: it is a fail-loud presence/range guard,
never a value or prompt-text mutation.

This module has two responsibilities:

1. Pin that the SHIPPED config resolves the flag True (a silent revert of
   the one-line ``coupling: { context_contract: true }`` would otherwise
   pass every other test in this directory unnoticed).
2. Pin that an actual mock run against that config reports
   ``coupling_contract_active: true`` with ``coupling_guard_calls > 0`` in
   ``run_integrity.json`` (flag-true-with-zero-calls is a run the guard
   never touched; see ``IrrigationEnvironment.get_coupling_retrofit_metadata``).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from broker.utils.agent_config import AgentTypeConfig

PAPER_CONFIG = PROJECT_ROOT / "examples" / "irrigation_abm" / "config" / "agent_types.yaml"
RUN_EXPERIMENT = PROJECT_ROOT / "examples" / "irrigation_abm" / "run_experiment.py"


def test_paper_config_resolves_context_contract_true():
    cfg = AgentTypeConfig.load(str(PAPER_CONFIG))
    assert cfg.get_coupling_context_contract() is True, (
        f"{PAPER_CONFIG} must resolve global_config.coupling.context_contract "
        "to True: this pins the paper config's default-on state added "
        "alongside this test; a silent revert of that one line would "
        "otherwise not be caught by anything else in this directory."
    )


def test_paper_config_two_year_mock_run_reports_contract_active(tmp_path):
    import subprocess

    output_dir = tmp_path / "ctxc_default_on_2yr"
    args = [
        sys.executable, str(RUN_EXPERIMENT),
        "--model", "mock", "--agents", "5", "--years", "2", "--seed", "42",
        "--governance-mode", "strict", "--workers", "1",
        "--output", str(output_dir),
    ]
    result = subprocess.run(
        args, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, (
        f"paper-config mock run failed:\nSTDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    assert "[coupling] context_contract=True" in result.stdout

    integrity = json.loads((output_dir / "run_integrity.json").read_text(encoding="utf-8"))
    assert integrity.get("coupling_contract_active") is True
    assert integrity.get("coupling_guard_calls", 0) > 0, (
        "flag true with zero guard calls is a run the guard never touched"
    )
