"""Declared relations (water balance) on the coupling contract (R1 slice 1)."""
from __future__ import annotations

import dataclasses
import hashlib
import math
from typing import Any, Dict, List

import pytest

import examples.reservoir_control  # noqa: F401 - registers reservoir_control
from broker.coupling import (
    CouplingContract,
    CouplingViolation,
    EnvironmentCouplingAdapter,
    Relation,
    VarSpec,
)
from broker.coupling.interfaces import InterfaceBundle
from examples.reservoir_control import run_reservoir_ops
from examples.reservoir_control.ops_modules import (
    ReservoirOpsBundle,
    ToyMassBalanceReservoir,
)

BALANCE = (
    "storage - (prev_storage + inflow - release_actual - evaporation - spill)"
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _reservoir_adapter(solver=None, contract=None) -> EnvironmentCouplingAdapter:
    contract = contract or run_reservoir_ops._build_contract()
    solver = solver or ToyMassBalanceReservoir()
    bundle = ReservoirOpsBundle(contract=contract, solver=solver)
    return EnvironmentCouplingAdapter(None, contract, bundle)


def _vs(name: str) -> VarSpec:
    return VarSpec(name, float, "maf", cadence="per_decision")


class _PeriodBundle(InterfaceBundle):
    """A bundle with one value per period and no sub-step series."""

    def __init__(self, rows: List[Dict[str, Any]]):
        super().__init__()
        self._rows = list(rows)
        self.touched = 0

    def run_pipeline(self, base_env, events, operation_order, control_hold_policy="constant"):
        env = dict(base_env)
        env.update(self._rows.pop(0))
        return env


def _period_contract(*relations) -> CouplingContract:
    return CouplingContract(
        observations=(_vs("level"), _vs("gain"), _vs("loss")),
        relations=tuple(relations),
    )


LEVEL_REL = Relation("level_balance", "level - (prev_level + gain - loss)", 1e-9)


class _LeakyReservoir(ToyMassBalanceReservoir):
    """Loses 0.001 maf a month that no published variable accounts for."""

    def update(self) -> None:
        super().update()
        self._storage -= 0.001


# --------------------------------------------------------------------------
# 1 / 2: leak is caught, the real toy solver is clean
# --------------------------------------------------------------------------
def test_leaky_solver_stops_with_named_relation_value_and_substep():
    adapter = _reservoir_adapter(_LeakyReservoir())
    with pytest.raises(CouplingViolation) as err:
        adapter.advance_step()
    msg = str(err.value)
    assert "storage_balance" in msg
    assert "sub-step 1" in msg  # sub-step 0 has no previous value: skipped
    assert "period 1" in msg
    assert "residual=-0.00099999" in msg or "residual=-0.001" in msg
    assert "prev_storage=" in msg and "inflow=" in msg


def test_real_toy_solver_passes_four_years_on_48_substeps():
    adapter = _reservoir_adapter()
    for _ in range(4):
        adapter.advance_step()
    rel = adapter.get_provenance()["relations"]
    assert rel["checks_run"] == 47  # 48 sub-steps, the first has no previous value
    assert rel["skipped_no_previous_value"] == [
        {"relation": "storage_balance", "period": 1, "substep": 0}
    ]


# --------------------------------------------------------------------------
# 3: first step
# --------------------------------------------------------------------------
def test_first_step_prev_relation_skipped_and_plain_relation_checked():
    plain = Relation("storage_nonneg_gap", "storage - storage", 0.0)
    contract = dataclasses.replace(
        run_reservoir_ops._build_contract(),
        relations=(Relation("storage_balance", BALANCE, 1e-9), plain),
    )
    adapter = _reservoir_adapter(contract=contract)
    adapter.advance_step()
    rel = adapter.get_provenance()["relations"]
    assert rel["skipped_no_previous_value"] == [
        {"relation": "storage_balance", "period": 1, "substep": 0}
    ]
    # 12 sub-steps of `plain` + 11 of the balance
    assert rel["checks_run"] == 12 + 11


# --------------------------------------------------------------------------
# 4: per-period path
# --------------------------------------------------------------------------
def test_per_period_path_first_period_skipped_breach_on_period_two():
    rows = [
        {"level": 10.0, "gain": 1.0, "loss": 0.0},
        {"level": 11.0, "gain": 1.0, "loss": 0.0},   # balances
        {"level": 12.5, "gain": 1.0, "loss": 0.0},   # leaks 0.5
    ]
    contract = _period_contract(LEVEL_REL)
    adapter = EnvironmentCouplingAdapter(None, contract, _PeriodBundle(rows))
    adapter.advance_step()
    assert adapter.get_provenance()["relations"]["skipped_no_previous_value"] == [
        {"relation": "level_balance", "period": 1, "substep": None}
    ]
    adapter.advance_step()
    assert adapter.get_provenance()["relations"]["checks_run"] == 1
    with pytest.raises(CouplingViolation) as err:
        adapter.advance_step()
    assert "level_balance" in str(err.value) and "period 3" in str(err.value)


def test_per_period_breach_on_period_two_raises():
    rows = [
        {"level": 10.0, "gain": 1.0, "loss": 0.0},
        {"level": 12.0, "gain": 1.0, "loss": 0.0},
    ]
    adapter = EnvironmentCouplingAdapter(None, _period_contract(LEVEL_REL), _PeriodBundle(rows))
    adapter.advance_step()
    with pytest.raises(CouplingViolation, match="level_balance"):
        adapter.advance_step()


# --------------------------------------------------------------------------
# 5: zero divisor, NaN input, NaN residual
# --------------------------------------------------------------------------
class _PartialSeriesBundle(_PeriodBundle):
    """Publishes a sub-step series that lacks one observation."""

    def run_pipeline(self, base_env, events, operation_order, control_hold_policy="constant"):
        env = super().run_pipeline(base_env, events, operation_order, control_hold_policy)
        self.last_substep_series = {"level": [env["level"]], "gain": [env["gain"]]}
        return env


def test_incomplete_substep_series_stops_instead_of_checking_reductions():
    rows = [{"level": 1.0, "gain": 0.0, "loss": 0.0}]
    adapter = EnvironmentCouplingAdapter(
        None, _period_contract(LEVEL_REL), _PartialSeriesBundle(rows))
    with pytest.raises(CouplingViolation, match="last_substep_series"):
        adapter.advance_step()


def test_zero_divisor_raises():
    rel = Relation("ratio", "gain / loss", 1.0)
    rows = [{"level": 1.0, "gain": 1.0, "loss": 0.0}]
    adapter = EnvironmentCouplingAdapter(None, _period_contract(rel), _PeriodBundle(rows))
    with pytest.raises(CouplingViolation, match="division by zero in relation"):
        adapter.advance_step()


def test_nan_input_value_raises_not_skipped():
    rows = [{"level": 1.0, "gain": float("nan"), "loss": 0.0}]
    adapter = EnvironmentCouplingAdapter(None, _period_contract(
        Relation("g", "gain - loss", 1.0)), _PeriodBundle(rows))
    # the observation range check runs first and also refuses a NaN; either way it stops
    with pytest.raises(CouplingViolation):
        adapter.advance_step()


def test_relation_input_check_directly_refuses_non_finite_and_missing():
    adapter = EnvironmentCouplingAdapter(None, _period_contract(LEVEL_REL), _PeriodBundle([]))
    adapter._period = 1
    for bad in (float("nan"), float("inf"), None, "x", True):
        with pytest.raises(CouplingViolation, match="relation cannot be checked"):
            adapter._relation_number("gain", bad, None)


def test_nan_residual_raises():
    # inf - inf cannot reach the evaluator as inputs (inputs must be finite), so a
    # huge product that overflows to inf gives a non-finite residual.
    rel = Relation("big", "gain * gain * gain - loss", 1.0)
    rows = [{"level": 1.0, "gain": 1e200, "loss": 0.0}]
    adapter = EnvironmentCouplingAdapter(None, _period_contract(rel), _PeriodBundle(rows))
    with pytest.raises(CouplingViolation, match="not finite|overflow"):
        adapter.advance_step()


# --------------------------------------------------------------------------
# 6: build time
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "residual",
    [
        "level - mystery",                 # unknown name (checked in the contract below)
        "level > 0",                       # comparison
        "level and gain",                  # and/or
        "level - 'x'",                     # string constant
        "level - True",                    # bool constant
        "abs(level)",                      # call
        "level ** 2",                      # power
        "_level - 1",                      # underscore name
        "1 + 2",                           # no name
        "level - nan_value",               # fine here, unknown in the contract
        "",                                # empty
    ],
)
def test_bad_residuals_rejected_at_build(residual):
    try:
        rel = Relation("r", residual, 1e-9)
    except ValueError as exc:
        assert "Relation[r]" in str(exc) or "Relation:" in str(exc)
        return
    # compiled fine as an expression: it must then fail the contract's name check
    with pytest.raises(ValueError, match="unknown name"):
        CouplingContract(observations=(_vs("level"),), relations=(rel,))


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), True, "1e-9", None])
def test_bad_tolerance_rejected(bad):
    with pytest.raises(ValueError, match="Relation\\[r\\]"):
        Relation("r", "level - 1", bad)


def test_empty_name_rejected():
    with pytest.raises(ValueError):
        Relation("", "level - 1", 0.0)


def test_unknown_input_and_prev_names_rejected_in_contract():
    obs = (_vs("level"),)
    inp = (VarSpec("setpoint", float, "maf", direction="agent_to_world"),)
    with pytest.raises(ValueError, match="setpoint"):
        CouplingContract(observations=obs, inputs=inp,
                         relations=(Relation("r", "level - setpoint", 0.0),))
    with pytest.raises(ValueError, match="prev_nothing"):
        CouplingContract(observations=obs,
                         relations=(Relation("r", "level - prev_nothing", 0.0),))
    with pytest.raises(ValueError, match="unknown name"):
        CouplingContract(observations=obs, relations=(Relation("r", "level - ghost", 0.0),))


def test_duplicate_relation_names_rejected():
    obs = (_vs("level"),)
    with pytest.raises(ValueError, match="duplicate relation name"):
        CouplingContract(observations=obs, relations=(
            Relation("r", "level - 1", 0.0), Relation("r", "level - 2", 0.0)))


def test_unknown_dict_key_rejected():
    with pytest.raises(ValueError, match="unknown key"):
        Relation.from_dict({"name": "r", "residual": "level - 1", "tolerance": 0.0, "tol": 1})
    with pytest.raises(ValueError, match="unknown key"):
        CouplingContract(observations=(_vs("level"),), relations=(
            {"name": "r", "residual": "level - 1", "tolerance": 0.0, "extra": 1},))


def test_relation_names_property():
    assert Relation("r", BALANCE, 0.0).names == (
        "storage", "prev_storage", "inflow", "release_actual", "evaporation", "spill",
    )


# --------------------------------------------------------------------------
# 7: coverage report
# --------------------------------------------------------------------------
def test_mixed_declared_undeclared_reports_observations_in_no_relation():
    contract = _period_contract(Relation("only_level", "level - 1", 0.0))
    assert contract.relation_coverage() == {
        "declared": ["only_level"],
        "observations_in_no_relation": ["gain", "loss"],
    }
    rows = [{"level": 1.0, "gain": 0.0, "loss": 0.0}]
    adapter = EnvironmentCouplingAdapter(None, contract, _PeriodBundle(rows))
    adapter.advance_step()
    assert adapter.get_provenance()["relations"]["observations_in_no_relation"] == ["gain", "loss"]


def test_reservoir_contract_reports_shortfall_in_no_relation():
    cov = run_reservoir_ops._build_contract().relation_coverage()
    assert cov["declared"] == ["storage_balance"]
    assert cov["observations_in_no_relation"] == ["shortfall"]


# --------------------------------------------------------------------------
# 8: no relations -> nothing changes
# --------------------------------------------------------------------------
def test_no_relations_provenance_and_repr_unchanged_and_bundle_untouched():
    obs = (_vs("level"), _vs("gain"))
    plain = CouplingContract(observations=obs)
    explicit_empty = CouplingContract(observations=obs, relations=())
    assert repr(plain) == repr(explicit_empty)
    assert "relations" not in repr(plain)

    class Spy(InterfaceBundle):
        def __getattribute__(self, name):
            if name == "last_substep_series":
                raise AssertionError("bundle touched by _check_relations")
            return super().__getattribute__(name)

    adapter = EnvironmentCouplingAdapter(None, plain, Spy())
    adapter._check_relations({"level": 1.0})  # must not touch the bundle
    prov = adapter.get_provenance()
    assert "relations" not in prov
    expected = hashlib.sha256(repr(plain).encode("utf-8")).hexdigest()[:16]
    assert prov["contract_sha256"] == expected


def test_declared_relations_change_the_contract_hash():
    obs = (_vs("level"),)
    a = EnvironmentCouplingAdapter(None, CouplingContract(observations=obs), InterfaceBundle())
    b = EnvironmentCouplingAdapter(
        None,
        CouplingContract(observations=obs, relations=(Relation("r", "level - 1", 0.0),)),
        InterfaceBundle(),
    )
    assert a.get_provenance()["contract_sha256"] != b.get_provenance()["contract_sha256"]


# --------------------------------------------------------------------------
# 9: dict form == dataclass form
# --------------------------------------------------------------------------
def test_dict_form_equals_dataclass_form():
    as_dict = {"name": "storage_balance", "residual": BALANCE, "tolerance": 1e-9}
    base = run_reservoir_ops._build_contract()
    from_dict = dataclasses.replace(base, relations=(as_dict,))
    assert from_dict.relations == base.relations
    assert from_dict.relations[0] == Relation(**as_dict)

    leaky = _reservoir_adapter(_LeakyReservoir(), contract=from_dict)
    with pytest.raises(CouplingViolation, match="storage_balance"):
        leaky.advance_step()


# --------------------------------------------------------------------------
# 2b: a breach stops the run (does not become an ABORTED row)
# --------------------------------------------------------------------------
def test_reservoir_main_with_leaking_solver_raises_coupling_violation(tmp_path, monkeypatch):
    monkeypatch.setattr(run_reservoir_ops, "_make_solver", lambda model: _LeakyReservoir())
    with pytest.raises(CouplingViolation, match="storage_balance"):
        run_reservoir_ops.main(
            ["--model", "mock", "--years", "2", "--output", str(tmp_path / "leak")]
        )


def test_reservoir_manifest_carries_final_relation_counts(tmp_path):
    import json

    out = tmp_path / "ok"
    assert run_reservoir_ops.main(["--model", "mock", "--years", "4", "--output", str(out)]) == 0
    manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    rel = manifest["coupling_provenance"]["relations"]
    assert rel["checks_run"] == 47
    assert rel["observations_in_no_relation"] == ["shortfall"]
    assert math.isclose(rel["declared"][0]["tolerance"], 1e-9)
