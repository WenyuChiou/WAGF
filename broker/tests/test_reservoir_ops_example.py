"""Regression tests for the reservoir continuous-control worked example."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import examples.reservoir_control  # noqa: F401 - registers reservoir_control
from broker.components.governance.validator_registry import ValidatorRegistry
from broker.coupling import CouplingViolation, EnvironmentCouplingAdapter
from broker.domains.registry import DomainPackRegistry
from broker.interfaces.skill_types import ApprovedSkill
from examples.cat_model.cat_validators import insurer_payout_solvency_check
from examples.cat_model.ma_validators import policyholder_claim_check
from examples.reservoir_control import run_reservoir_ops
from examples.reservoir_control.ops_modules import (
    INFLOW_PATTERN_MONTHLY,
    ReservoirOpsBundle,
    ToyMassBalanceReservoir,
)
from examples.reservoir_control.ops_validators import (
    dead_pool_violation,
    flood_control_overflow,
)


def _approved(skill_name: str = "set_release", **params) -> ApprovedSkill:
    return ApprovedSkill(
        skill_name=skill_name,
        agent_id="OPERATOR",
        approval_status="APPROVED",
        parameters=dict(params),
    )


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _jsonl_records(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            record = json.loads(line)
            if "_metadata" not in record:
                records.append(record)
    return records


def _manual_year(storage: float, factor: float, release_target: float) -> dict[str, float]:
    spill_sum = 0.0
    shortfall_sum = 0.0
    release_sum = 0.0
    for inflow in INFLOW_PATTERN_MONTHLY:
        available = max(0.0, storage + inflow * factor)
        release_applied = min(release_target, available)
        shortfall = max(0.0, ToyMassBalanceReservoir.DEMAND_M - release_applied)
        next_storage = storage + inflow * factor - release_applied - (
            ToyMassBalanceReservoir.EVAP_RATE * storage
        )
        spill = max(0.0, next_storage - ToyMassBalanceReservoir.CAPACITY)
        storage = min(ToyMassBalanceReservoir.CAPACITY, max(0.0, next_storage))
        spill_sum += spill
        shortfall_sum += shortfall
        release_sum += release_applied
    return {
        "storage": storage,
        "spill": spill_sum,
        "shortfall": shortfall_sum,
        "release_actual": release_sum / 12.0,
    }


def test_e2e_mock_run_rows_equal_years(tmp_path: Path):
    out = tmp_path / "ops_results"

    rc = run_reservoir_ops.main(
        ["--model", "mock", "--years", "4", "--output", str(out)]
    )

    assert rc == 0
    rows = _csv_rows(out / "operator_governance_audit.csv")
    assert len(rows) == 4

    # T5 menu regression net (the e4b "[N/A]" blind-menu class): the rendered
    # prompt must carry the real numbered menu injected via dynamic_state.
    records = _jsonl_records(out / "raw" / "operator_traces.jsonl")
    prompt = records[0]["input"]
    assert "[N/A]" not in prompt
    assert "1. set_release" in prompt
    assert "2. maintain_release" in prompt
    assert prompt.index("1. set_release") < prompt.index("2. maintain_release")


def test_drought_year_wall_retry_resolves_and_audits_failed_rule(tmp_path: Path):
    """The insurer-pattern narrative (review C2): at the year-3 decision the
    coming-year forecast continues the drought, 100% projects 1.838 maf
    (< 6.0 dead pool) -> WALL; the scripted 50% retry projects 6.338 maf ->
    APPROVED. Wall evidence AND resolution evidence both asserted."""
    out = tmp_path / "ops_results"

    run_reservoir_ops.main(["--model", "mock", "--years", "4", "--output", str(out)])

    rows = _csv_rows(out / "operator_governance_audit.csv")
    year3 = next(row for row in rows if row["year"] == "3")
    # wall evidence
    assert int(year3["retry_count"]) >= 1
    assert "dead_pool_violation" in year3.get("failed_rules", "")
    # resolution evidence: the retry PASSED — not the REJECTED fallback
    assert year3["final_skill"] == "set_release"
    assert year3["status"] == "APPROVED"
    # other decision years never hit the wall
    for yr in ("1", "2", "4"):
        row = next(r for r in rows if r["year"] == yr)
        assert int(row["retry_count"]) == 0, f"unexpected retry in year {yr}"
        assert row["status"] == "APPROVED"


def test_reduce_semantics_match_hand_computed_solver_year():
    solver = ToyMassBalanceReservoir()
    bundle = ReservoirOpsBundle(contract=run_reservoir_ops._build_contract(), solver=solver)

    env = bundle.run_pipeline({"current_year": 1}, [], (), "constant")
    expected = _manual_year(18.0, 1.0, 0.75)

    assert env["storage"] == pytest.approx(expected["storage"])
    assert env["spill"] == pytest.approx(expected["spill"])
    assert env["shortfall"] == pytest.approx(expected["shortfall"])
    assert env["release_actual"] == pytest.approx(expected["release_actual"])
    assert env["_substeps_run"] == 12


def test_magnitude_setpoint_mapping_and_absent_magnitude_repeats_last():
    solver = ToyMassBalanceReservoir()
    bundle = ReservoirOpsBundle(contract=run_reservoir_ops._build_contract(), solver=solver)

    first = bundle.commit_world_delta(_approved(magnitude_pct=80))
    assert first.world_changes["release_target"] == pytest.approx(0.6)
    assert solver.release_target == pytest.approx(0.6)

    second = bundle.commit_world_delta(_approved("maintain_release"))
    assert second.world_changes["release_target"] == pytest.approx(0.6)
    assert solver.release_target == pytest.approx(0.6)


def test_solver_floor_storage_and_spill_invariants_over_36_months():
    solver = ToyMassBalanceReservoir()
    solver.set_value("release_target", [1.125])

    for _ in range(36):
        solver.update()
        available = solver.last_available
        release = solver.get_value("release_actual")[0]
        storage = solver.get_value("storage")[0]
        spill = solver.get_value("spill")[0]
        assert release <= available + 1e-12
        assert storage >= 0.0
        assert storage <= ToyMassBalanceReservoir.CAPACITY
        if spill > 0.0:
            assert storage == pytest.approx(ToyMassBalanceReservoir.CAPACITY)


def test_model_swap_linear_evap_run_completes(tmp_path: Path):
    """THE model-agnostic-slot test: the SAME contract + bundle accepts a
    differently-implemented BMI solver unchanged. Also asserts the swap
    actually happened (review W2): the two evap laws must produce different
    year-1 storages — a regression in the solver dispatch would leave both
    runs on the same model and this assert red."""
    from examples.reservoir_control.ops_modules import ToyLinearEvapReservoir

    out = tmp_path / "linear_results"

    rc = run_reservoir_ops.main(
        ["--model", "mock-linear-evap", "--years", "2", "--output", str(out)]
    )

    assert rc == 0
    rows = _csv_rows(out / "operator_governance_audit.csv")
    assert len(rows) == 2

    # the swapped solver is genuinely different physics
    mass, linear = ToyMassBalanceReservoir(), ToyLinearEvapReservoir()
    for _ in range(12):
        mass.update()
        linear.update()
    s_mass = mass.get_value("storage")[0]
    s_linear = linear.get_value("storage")[0]
    assert abs(s_mass - s_linear) > 0.1, (
        "evap laws should diverge measurably over one year "
        f"(mass={s_mass:.3f}, linear={s_linear:.3f})"
    )


def test_out_of_range_derived_setpoint_blocked_by_bundle_guard():
    """The block fires in ReservoirOpsBundle.commit_world_delta's DERIVED
    range guard (review S1): the adapter's generic PRE check iterates the
    proposal's raw params (magnitude_pct) against input_specs (release_target)
    and passes silently — the bundle re-checks the DERIVED release_target
    against the same VarSpec range BEFORE super() reaches the sink, so the
    solver is still protected pre-mutation."""
    solver = ToyMassBalanceReservoir()
    bundle = ReservoirOpsBundle(contract=run_reservoir_ops._build_contract(), solver=solver)
    adapter = EnvironmentCouplingAdapter(
        real_engine=None,
        contract=bundle.contract,
        sources=bundle,
    )

    with pytest.raises(CouplingViolation, match="release_target"):
        adapter.execute_skill(_approved(magnitude_pct=200))

    assert solver.release_target == pytest.approx(0.75)


def test_registration_isolation():
    reservoir_checks = ValidatorRegistry.get_checks("reservoir_control", "physical")
    cat_single_checks = ValidatorRegistry.get_checks("cat_model", "physical")
    cat_checks = ValidatorRegistry.get_checks("cat_model_ma", "physical")

    assert dead_pool_violation in reservoir_checks
    assert flood_control_overflow in reservoir_checks
    assert insurer_payout_solvency_check in cat_single_checks
    assert policyholder_claim_check in cat_checks
    assert policyholder_claim_check not in reservoir_checks
    assert insurer_payout_solvency_check not in reservoir_checks
    assert dead_pool_violation not in cat_checks
    assert dead_pool_violation not in cat_single_checks
    assert DomainPackRegistry.get("reservoir_control") is not None
