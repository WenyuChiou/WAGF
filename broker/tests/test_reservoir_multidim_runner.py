"""Phase 6W-B7 — reservoir_control_multidim RUNNER end-to-end mock smoke.

The skeleton test (test_reservoir_multidim_skeleton.py) proves the pieces in
isolation (validator, commit). This drives the FULL runnable path — parse ->
strict governance (output_schema + ParameterBoundsValidator) -> approve ->
commit -> audit — through run_reservoir_multidim.main() with --model mock.

It is the regression guard for two things that only show up end-to-end:
  1. broker/core/skill_broker_engine.py surfaces proposal.parameters into the
     output_schema's `output_fields` (without it the 3 setpoints read as
     "missing required field" -> REJECTED, not APPROVED).
  2. the audit CSV emits proposed_param_<name> columns (audit.param_columns ON).

The real gemma4:e4b worked run + baseline are a separate ollama task.
"""
from __future__ import annotations

import csv

from examples.reservoir_control_multidim.run_reservoir_multidim import main


def test_runner_mock_smoke_approves_and_emits_param_columns(tmp_path):
    out = tmp_path / "results_multidim"
    rc = main(["--model", "mock", "--years", "2", "--output", str(out)])
    assert rc == 0

    csv_path = out / "operator_governance_audit.csv"
    assert csv_path.exists(), f"no audit CSV at {csv_path}"
    with csv_path.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2, "expected exactly one row per year (2 years, 1 agent)"

    r = rows[0]
    # the multi-dim setpoint skill is APPROVED end-to-end (NOT rejected-fallback):
    # proves the engine surfaced proposal.parameters to the output_schema check.
    assert r["proposed_skill"] == "set_release_multi"
    assert r["final_skill"] == "set_release_multi"
    assert r["status"] == "APPROVED"

    # ...and the proposed_param_<name> columns carry the three setpoints.
    for col, expected in (
        ("proposed_param_release_rate_cms", 400.0),
        ("proposed_param_hydropower_target_mw", 900.0),
        ("proposed_param_flood_pool_pct", 20.0),
    ):
        assert col in r, f"missing audit column {col}"
        assert float(r[col]) == expected

    # all THREE committed world_<name> setpoints mirror the proposal (no derive
    # layer) — assert each so a silent drop of any one is caught.
    assert float(r["world_release_rate_cms"]) == 400.0
    assert float(r["world_hydropower_target_mw"]) == 900.0
    assert float(r["world_flood_pool_pct"]) == 20.0
