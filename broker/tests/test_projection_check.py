"""R1 slice 2: the projection check (contract.feasibility)."""
from __future__ import annotations

import copy
import csv
import dataclasses
import hashlib
import random
from pathlib import Path

import numpy as np
import pytest

import broker.run
from broker.coupling import (
    BmiControlSink,
    ContinuousBundle,
    CouplingContract,
    CouplingViolation,
    EnvironmentCouplingAdapter,
    FeasibilityBound,
    Relation,
    VarSpec,
)
from broker.coupling.projection_check import (
    ProjectionCheck,
    ProjectionCheckError,
    ProjectionSideEffect,
)
from broker.utils.agent_config import AgentTypeConfig
from examples.reservoir_control import ops_case
from examples.reservoir_control.ops_modules import (
    ReservoirOpsBundle,
    ToyLinearEvapReservoir,
    ToyMassBalanceReservoir,
)

FORECAST_DROUGHT = 4.2
FORECAST_WET = 10.5


def _ctx(forecast=FORECAST_DROUGHT):
    return {"env_state": {"inflow_forecast_year": forecast}}


_ORIGINAL_CONTRACT = ops_case.build_contract


def _contract(bounds):
    return dataclasses.replace(_ORIGINAL_CONTRACT(), feasibility=tuple(bounds))


def _reservoir(solver=None, bounds=None, years_at_100=3):
    solver = solver or ToyMassBalanceReservoir()
    contract = _ORIGINAL_CONTRACT() if bounds is None else _contract(bounds)
    bundle = ReservoirOpsBundle(contract=contract, solver=solver)
    adapter = EnvironmentCouplingAdapter(real_engine=None, contract=contract, sources=bundle)
    for _ in range(years_at_100):
        bundle.run_pipeline({"current_year": 0}, [], ())
    check = ProjectionCheck(adapter)
    adapter.projection_check = check
    return solver, bundle, adapter, check


def _bound(must_hold, name="b", skills=("set_release",)):
    return FeasibilityBound(name=name, must_hold=must_hold, skills=skills)


# ---------------------------------------------------------------- contract ----
def test_bound_build_errors_name_the_bound():
    with pytest.raises(ValueError, match="name"):
        FeasibilityBound(name="", must_hold="x > 1")
    with pytest.raises(ValueError, match="bad_expr"):
        FeasibilityBound(name="bad_expr", must_hold="x +")
    with pytest.raises(ValueError, match="no_cmp"):
        FeasibilityBound(name="no_cmp", must_hold="x + 1")
    with pytest.raises(ValueError, match="bad_skills"):
        FeasibilityBound(name="bad_skills", must_hold="x > 1", skills=(1,))
    with pytest.raises(ValueError, match="bad_skills2"):
        FeasibilityBound(name="bad_skills2", must_hold="x > 1", skills="set_release")


def test_bound_from_dict_and_contract_accepts_dicts():
    with pytest.raises(ValueError, match="unknown key"):
        FeasibilityBound.from_dict({"name": "a", "must_hold": "x > 1", "extra": 1})
    c = _contract([{"name": "a", "must_hold": "x > 1", "skills": ["s"]}])
    assert c.feasibility == (FeasibilityBound("a", "x > 1", ("s",)),)
    with pytest.raises(ValueError, match="duplicate feasibility"):
        _contract([_bound("x > 1", "a"), _bound("x > 2", "a")])


def test_no_feasibility_leaves_repr_hash_and_provenance_alone():
    contract = ops_case.build_contract()
    contract = dataclasses.replace(contract, feasibility=())
    assert "feasibility" not in repr(contract)
    bundle = ReservoirOpsBundle(contract=contract, solver=ToyMassBalanceReservoir())
    adapter = EnvironmentCouplingAdapter(None, contract, bundle)
    prov = adapter.get_provenance()
    expected = hashlib.sha256((repr(contract) + repr(contract.relations)).encode()).hexdigest()[:16]
    assert prov["contract_sha256"] == expected
    assert "feasibility" not in prov
    assert adapter.projection_check is None
    # declaring one changes the identity and adds a provenance block
    with_bound = dataclasses.replace(contract, feasibility=(_bound("storage_unclamped >= 6"),))
    adapter2 = EnvironmentCouplingAdapter(None, with_bound, bundle)
    prov2 = adapter2.get_provenance()
    assert prov2["contract_sha256"] != prov["contract_sha256"]
    assert prov2["feasibility"]["declared"][0]["name"] == "b"


# ----------------------------------------------------- 1. copy path, reservoir ----
def test_copy_path_refuses_100_passes_50_and_leaves_live_state_alone():
    solver, bundle, adapter, check = _reservoir()
    assert check.source == "copy"
    before = copy.deepcopy(solver.__dict__)
    env = {"env_state": {"inflow_forecast_year": 4.2}, "storage_now": 7.54}
    env_before = copy.deepcopy(env)
    proposal100 = type("P", (), {"skill_name": "set_release", "agent_id": "OPERATOR",
                                 "magnitude_pct": 100.0, "magnitude_fallback": False,
                                 "parameters": {}})()
    res = check(proposal100, env)
    assert len(res) == 1 and not res[0].valid
    assert res[0].validator_name == "dead_pool_violation"
    meta = res[0].metadata
    assert meta["rule_id"] == "dead_pool_violation" and meta["grounding"] == "world"
    assert meta["category"] == "physical" and meta["source"] == "copy"
    assert meta["projected"]["storage_unclamped"] < 6.0
    assert solver.__dict__ == before and env == env_before
    proposal50 = type("P", (), {"skill_name": "set_release", "agent_id": "OPERATOR",
                                "magnitude_pct": 50.0, "magnitude_fallback": False,
                                "parameters": {}})()
    assert check(proposal50, env) == []
    assert solver.__dict__ == before
    # a skill the bound does not name is not projected at all
    other = type("P", (), {"skill_name": "maintain_release", "agent_id": "O",
                           "magnitude_pct": None, "magnitude_fallback": False, "parameters": {}})()
    n = check.projections_run
    assert check(other, env) == [] and check.projections_run == n


# ------------------------------------------------- 2. linear evaporation model ----
def test_linear_evap_model_is_judged_by_the_real_model_not_a_formula():
    solver, _b, _a, check = _reservoir(ToyLinearEvapReservoir())
    assert solver.get_value("storage")[0] == pytest.approx(11.25)
    ctx = _ctx()
    # the deleted linear formula said ~5.55 at 95% (refuse); the model ends near 6.30
    assert check.check_skill("set_release", {"magnitude_pct": 95}, ctx) == []
    breaches = check.check_skill("set_release", {"magnitude_pct": 100}, ctx)
    assert len(breaches) == 1
    assert breaches[0].projected["storage_unclamped"] == pytest.approx(5.85, abs=1e-6)


# ------------------------------------------------------------- 3. clamping ----
def test_bound_is_judged_before_the_clamp_and_on_the_request():
    contract_bounds = [
        _bound("storage_unclamped >= 0", "unclamped"),
        _bound("storage >= 0", "clamped"),
        _bound("requested_release_target <= 1.0", "request"),
        _bound("release_actual <= 1.0", "actual"),
    ]
    solver = ToyMassBalanceReservoir(storage0=0.2)
    _s, _b, _a, check = _reservoir(solver, contract_bounds, years_at_100=0)
    ctx = _ctx(0.0)
    breaches = check.check_skill("set_release", {"magnitude_pct": 140}, ctx, stop_at_first=False)
    names = {b.bound for b in breaches}
    # storage is clamped to 0.0 (so the clamped bound holds) but the request drove it below
    assert "unclamped" in names and "clamped" not in names
    # release_actual is clamped by what is available; the request (1.05) is what is judged
    assert "request" in names and "actual" not in names
    unclamped = next(b for b in breaches if b.bound == "unclamped")
    assert unclamped.projected["storage_unclamped"] < 0


# --------------------------------------------------- 4. forecast, not truth ----
def test_projection_uses_the_forecast_the_agent_saw():
    solver, _b, _a, check = _reservoir()
    solver._year_factors = (1.0, 0.7, 0.4, 1.0)  # year 4 is truly wet; same first 3 years
    assert check.check_skill("set_release", {"magnitude_pct": 100}, _ctx(FORECAST_DROUGHT))
    solver2, _b2, _a2, check2 = _reservoir()  # year 4 is truly a drought
    assert check2.check_skill("set_release", {"magnitude_pct": 100}, _ctx(FORECAST_WET)) == []


def test_missing_forecast_stops_the_run():
    _s, _b, _a, check = _reservoir()
    with pytest.raises(CouplingViolation, match="inflow_forecast_year"):
        check.check_skill("set_release", {"magnitude_pct": 100}, {"env_state": {}})


# --------------------------------------------------------- tiny BMI solvers ----
class _Base:
    def __init__(self):
        self.x = 10.0
        self.u = 1.0
        self.t = 0

    def update(self):
        self.x -= self.u
        self.t += 1

    def get_value(self, name):
        if name != "x":
            raise KeyError(name)
        return [self.x]

    def set_value(self, name, value):
        self.u = float(value[0])

    def get_var_units(self, name):
        return "m"

    def get_current_time(self):
        return float(self.t)


def _simple_contract(bounds, k=3):
    return CouplingContract(
        observations=(VarSpec("x", float, "m"),),
        inputs=(VarSpec("u", float, "m", direction="agent_to_world"),),
        substeps_per_decision=k,
        feasibility=tuple(bounds),
    )


def _simple_check(solver, bundle_cls=ContinuousBundle, bounds=None):
    contract = _simple_contract(bounds or [_bound("x >= 4", "floor", ())])
    bundle = bundle_cls(contract=contract, solver=solver)
    adapter = EnvironmentCouplingAdapter(None, contract, bundle)
    return ProjectionCheck(adapter)


class _NoForcing(ContinuousBundle):
    projection_has_no_forcing = True


# ------------------------------------------------------------ 5. project() ----
class _Projecting(_Base):
    def __deepcopy__(self, memo):
        raise RuntimeError("must not be copied")

    def project(self, inputs, context, substeps):
        return {"x": [10.0 - inputs["u"] * (k + 1) for k in range(substeps)]}


class _BadProjecting(_Projecting):
    def project(self, inputs, context, substeps):
        return {"y": [1.0]}


def test_project_method_is_used_and_nothing_is_copied():
    check = _simple_check(_Projecting())
    assert check.source == "project"
    assert check.check_skill("s", {"u": 1.0}, {}) == []
    breach = check.check_skill("s", {"u": 3.0}, {})
    assert breach and breach[0].source == "project" and breach[0].substep == 3


def test_project_result_missing_a_name_stops_the_run():
    check = _simple_check(_BadProjecting())
    with pytest.raises(CouplingViolation, match="did not return"):
        check.check_skill("s", {"u": 1.0}, {})


class _EndOnlyProjecting(_Projecting):
    def project(self, inputs, context, substeps):
        return {"x": [10.0 - inputs["u"] * substeps]}  # only the end value


def test_project_result_without_one_value_per_substep_stops_the_run():
    # 10 - 2*3 = 4 passes at the end, so judging only that value would pass.
    check = _simple_check(_EndOnlyProjecting())
    with pytest.raises(ProjectionCheckError, match=r"one value per sub-step \(3\)"):
        check.check_skill("s", {"u": 2.0}, {})


class _PlainBundle:
    def __init__(self, solver):
        self.solver = solver


def test_bundle_without_inputs_for_skill_is_a_build_error():
    contract = _simple_contract([_bound("x >= 4", "floor", ())])
    adapter = EnvironmentCouplingAdapter(None, contract, ContinuousBundle(contract=contract, solver=_Base()))
    adapter.sources = _PlainBundle(_Projecting())
    with pytest.raises(ValueError, match="no inputs_for_skill"):
        ProjectionCheck(adapter)


# ----------------------------------------------------------- 6. build errors ----
class _NoCopy(_Base):
    def __deepcopy__(self, memo):
        raise TypeError("holds a handle")


def test_non_copyable_model_without_project_is_a_build_error():
    with pytest.raises(ValueError, match="cannot be deep-copied") as exc:
        _simple_check(_NoCopy())
    assert "give it project()" in str(exc.value) and "holds a handle" in str(exc.value)


def test_bundle_without_apply_forecast_is_a_build_error_unless_no_forcing():
    with pytest.raises(ValueError, match="apply_forecast"):
        _simple_check(_Base())
    assert _simple_check(_Base(), _NoForcing).source == "copy"


def test_bound_naming_an_unknown_name_is_a_build_error():
    with pytest.raises(ValueError, match="does not answer 'nope'"):
        _simple_check(_Base(), _NoForcing, [_bound("nope >= 1", "bad", ())])
    with pytest.raises(ValueError, match="no declared input"):
        _simple_check(_Base(), _NoForcing, [_bound("requested_zzz >= 1", "bad", ())])


def test_builder_build_fails_for_a_non_copyable_model(tmp_path, monkeypatch):
    def refuse(self, memo):
        raise TypeError("holds a handle")

    monkeypatch.setattr(ToyMassBalanceReservoir, "__deepcopy__", refuse, raising=False)
    AgentTypeConfig.clear_cache()
    with pytest.raises(ValueError, match="cannot be deep-copied"):
        broker.run.prepare([
            str(ops_case.CONFIG_PATH), "--model", "mock", "--years", "1",
            "--output", str(tmp_path / "o"), "--seed", "1",
        ])
    AgentTypeConfig.clear_cache()


# --------------------------------------------------- 7. files written on a copy ----
class _Logging(_Base):
    def __init__(self, path):
        super().__init__()
        self.log_path = str(path)

    def update(self):
        super().update()
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write("step\n")


class _LoggingBundle(ContinuousBundle):
    def apply_forecast(self, model_copy, context):
        if context.get("silence"):
            model_copy.log_path = None


def test_copy_that_writes_a_file_stops_the_run_and_leaves_the_file_alone(tmp_path):
    log = tmp_path / "model.log"
    log.write_bytes(b"live\n")
    mtime = log.stat().st_mtime_ns
    check = _simple_check(_Logging(log), _LoggingBundle)
    with pytest.raises(ProjectionSideEffect) as exc:
        check.check_skill("s", {"u": 1.0}, {})
    assert "model.log" in str(exc.value) and "project()" in str(exc.value)
    assert isinstance(exc.value, CouplingViolation)
    assert log.read_bytes() == b"live\n" and log.stat().st_mtime_ns == mtime
    # the guard is off again afterwards
    with open(log, "ab") as fh:
        fh.write(b"x")
    # switching the copy's output off in apply_forecast projects fine
    assert check.check_skill("s", {"u": 1.0}, {"silence": True}) == []
    assert log.read_bytes() == b"live\nx"  # only the test's own write


class _SwallowingLogging(_Logging):
    def update(self):
        try:
            super().update()
        except Exception:  # the model's own code hides the failed write
            pass


def test_copy_whose_code_catches_the_blocked_write_still_stops_the_run(tmp_path):
    log = tmp_path / "model.log"
    log.write_bytes(b"live\n")
    check = _simple_check(_SwallowingLogging(log), _NoForcing)
    with pytest.raises(ProjectionSideEffect, match="model.log"):
        check.check_skill("s", {"u": 1.0}, {})
    assert log.read_bytes() == b"live\n"
    from broker.coupling import projection_check as pc

    assert getattr(pc._state, "blocked", None) is None  # the next projection starts clean
    assert getattr(pc._state, "projecting", False) is False


def test_first_import_inside_a_copy_does_not_trip_the_guard(tmp_path, monkeypatch):
    # With bytecode writing on, a first-time import makes __pycache__ and a
    # temporary .pyc file; the guard turns bytecode writing off instead of
    # blaming the copy.
    import sys as _sys
    import uuid

    name = f"_r1s2_fresh_{uuid.uuid4().hex}"
    (tmp_path / f"{name}.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(_sys, "dont_write_bytecode", False)

    class _Importing(_Base):
        def update(self):
            super().update()
            __import__(name)

    check = _simple_check(_Importing(), _NoForcing)
    assert check.check_skill("s", {"u": 1.0}, {}) == []
    assert not (tmp_path / "__pycache__").exists()
    assert _sys.dont_write_bytecode is False  # restored afterwards
    _sys.modules.pop(name, None)


class _Spawning(_Base):
    def update(self):
        super().update()
        import subprocess
        import sys as _sys

        subprocess.Popen([_sys.executable, "-c", "pass"]).wait()


def test_copy_that_starts_a_process_stops_the_run():
    check = _simple_check(_Spawning(), _NoForcing)
    with pytest.raises(ProjectionSideEffect, match="subprocess.Popen"):
        check.check_skill("s", {"u": 1.0}, {})


@pytest.mark.skipif(not __import__("sys").platform.startswith("win"), reason="Windows only")
def test_copy_that_calls_createprocess_directly_stops_the_run():
    import _winapi
    import sys as _sys

    class _WinSpawning(_Base):
        def update(self):
            super().update()
            _winapi.CreateProcess(
                None, f'"{_sys.executable}" -c pass', None, None, False, 0, None, None, None
            )

    check = _simple_check(_WinSpawning(), _NoForcing)
    with pytest.raises(ProjectionSideEffect, match="_winapi.CreateProcess"):
        check.check_skill("s", {"u": 1.0}, {})


class _SwallowThenFail(_Logging):
    def update(self):
        try:
            super().update()
        except Exception:
            raise ValueError("boom")  # the model hides the real cause


def test_side_effect_is_reported_when_the_model_then_fails_another_way(tmp_path):
    log = tmp_path / "model.log"
    log.write_bytes(b"live\n")
    check = _simple_check(_SwallowThenFail(log), _NoForcing)
    with pytest.raises(ProjectionSideEffect, match="model.log"):
        check.check_skill("s", {"u": 1.0}, {})
    assert log.read_bytes() == b"live\n"


class _RenamingSink:
    def __init__(self, bmi):
        self._bmi = bmi

    def apply_control(self, name, value):
        self._bmi.set_value("internal_" + name, [float(value)])


def test_copy_projection_with_a_custom_sink_is_a_build_error():
    contract = _simple_contract([_bound("x >= 4", "floor", ())])
    solver = _Base()
    bundle = _NoForcing(contract=contract, solver=solver, sink=_RenamingSink(solver))
    with pytest.raises(ValueError, match="sink is _RenamingSink"):
        ProjectionCheck(EnvironmentCouplingAdapter(None, contract, bundle))


class _DoublingSink(BmiControlSink):
    def apply_control(self, name, value):
        super().apply_control(name, 2 * float(value))


def test_copy_projection_with_a_bmi_sink_subclass_is_a_build_error():
    # PR #113 review: the copy is driven by a plain BmiControlSink, so a
    # subclass that changes the controls would be judged on other values
    # than the live model gets.
    contract = _simple_contract([_bound("x >= 4", "floor", ())])
    solver = _Base()
    bundle = _NoForcing(contract=contract, solver=solver, sink=_DoublingSink(solver))
    with pytest.raises(ValueError, match="sink is _DoublingSink"):
        ProjectionCheck(EnvironmentCouplingAdapter(None, contract, bundle))


def test_feasibility_with_workers_above_1_is_a_build_error(tmp_path):
    AgentTypeConfig.clear_cache()
    try:
        with pytest.raises(ValueError, match="workers=2 .* feasibility bounds"):
            broker.run.prepare([
                str(ops_case.CONFIG_PATH), "--model", "mock", "--years", "1",
                "--output", str(tmp_path / "o"), "--seed", "1", "--workers", "2",
            ])
    finally:
        AgentTypeConfig.clear_cache()


# ------------------------------------------------------------ 8. global RNG ----
class _Random(_Base):
    def update(self):
        super().update()
        random.random()
        np.random.rand()


def test_global_rng_states_are_restored_after_a_projection():
    check = _simple_check(_Random(), _NoForcing)
    random.seed(7)
    np.random.seed(7)
    py_before, np_before = random.getstate(), np.random.get_state()
    check.check_skill("s", {"u": 1.0}, {})
    assert random.getstate() == py_before
    after = np.random.get_state()
    assert after[0] == np_before[0] and (after[1] == np_before[1]).all() and after[2:] == np_before[2:]


# ---------------------------------------------- 9. default after retries (e2e) ----
def _always_100(prompt):
    return ops_case.decision_payload("set_release", magnitude=100)


def _run(monkeypatch, tmp_path, bounds, years=2, always_100=True):
    contract = _contract(bounds)
    monkeypatch.setattr(ops_case, "build_contract", lambda: contract)
    out = tmp_path / "out"
    AgentTypeConfig.clear_cache()
    try:
        runner = broker.run.prepare([
            str(ops_case.CONFIG_PATH), "--model", "mock", "--years", str(years),
            "--output", str(out), "--seed", "42",
        ]).runner
        if always_100:
            runner._llm_cache["operator"] = _always_100
        runner.run()
    finally:
        AgentTypeConfig.clear_cache()
    with (out / "operator_governance_audit.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return runner, rows


def test_default_after_retries_runs_even_if_it_breaches_and_is_marked(monkeypatch, tmp_path):
    bounds = [
        _bound("requested_release_target <= 0.5", "too_much", ("set_release",)),
        _bound("storage_unclamped >= 100", "never_fine", ("maintain_release",)),
    ]
    runner, rows = _run(monkeypatch, tmp_path, bounds)
    assert [r["status"] for r in rows] == ["REJECTED", "REJECTED"]
    assert [r["projection_default_breach"] for r in rows] == ["never_fine", "never_fine"]
    # the default still ran: the committed target is the (unchanged) 0.75
    assert runner.sim_engine.sources.solver.release_target == pytest.approx(0.75)


def test_default_that_passes_gets_an_empty_mark(monkeypatch, tmp_path):
    bounds = [
        _bound("requested_release_target <= 0.5", "too_much", ("set_release",)),
        _bound("storage_unclamped >= 1", "fine", ("maintain_release",)),
    ]
    _runner, rows = _run(monkeypatch, tmp_path, bounds)
    assert "projection_default_breach" in rows[0]
    assert [r["projection_default_breach"] for r in rows] == ["", ""]


def test_error_projecting_the_default_stops_the_run_without_a_row(monkeypatch, tmp_path):
    bounds = [
        _bound("requested_release_target <= 0.5", "too_much", ("set_release",)),
        _bound("1 / (storage_unclamped - storage_unclamped) > 0", "zero_div_default",
               ("maintain_release",)),
    ]
    with pytest.raises(ProjectionCheckError, match="zero_div_default"):
        _run(monkeypatch, tmp_path, bounds, years=1)
    audit = tmp_path / "out" / "operator_governance_audit.csv"
    if audit.exists():
        with audit.open(encoding="utf-8-sig", newline="") as fh:
            assert list(csv.DictReader(fh)) == []


def test_reservoir_bundle_passes_other_declared_inputs_through():
    contract = dataclasses.replace(
        _ORIGINAL_CONTRACT(),
        inputs=_ORIGINAL_CONTRACT().inputs
        + (VarSpec("gate", float, "maf_per_month", direction="agent_to_world"),),
    )
    bundle = ReservoirOpsBundle(contract=contract, solver=ToyMassBalanceReservoir())
    from broker.interfaces.skill_types import ApprovedSkill

    skill = ApprovedSkill(skill_name="set_release", agent_id="op", approval_status="APPROVED",
                          parameters={"magnitude_pct": 50, "gate": 0.1})
    assert bundle.inputs_for_skill(skill) == {"release_target": pytest.approx(0.375), "gate": 0.1}


def test_run_without_feasibility_has_no_projection_column(monkeypatch, tmp_path):
    runner, rows = _run(monkeypatch, tmp_path, [], always_100=False)
    assert "projection_default_breach" not in rows[0]
    assert runner.sim_engine.projection_check is None
    assert runner.broker.custom_validators == []


# ---------------------------------------------------------- 11. end to end ----
def test_reservoir_main_blocks_year_3_and_approves_the_retry(tmp_path):
    out = tmp_path / "out"
    assert broker.run.main([
        str(ops_case.CONFIG_PATH), "--model", "mock", "--years", "4", "--output", str(out),
    ]) == 0
    with (out / "operator_governance_audit.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = {r["year"]: r for r in csv.DictReader(fh)}
    assert rows["3"]["retry_count"] == "1" and rows["3"]["failed_rules"] == "dead_pool_violation"
    assert rows["3"]["status"] == "APPROVED"
    assert rows["3"]["rules_world_grounded"] == "dead_pool_violation"
    for y in ("1", "2", "4"):
        assert rows[y]["retry_count"] == "0"
    assert "projection_default_breach" not in rows["1"]


ZERO_DIV = _bound("1 / (storage_unclamped - storage_unclamped) > 0", "zero_div", ("set_release",))


def test_zero_divisor_in_a_projection_stops_the_run(monkeypatch, tmp_path):
    monkeypatch.setattr(ops_case, "build_contract", lambda: _contract([ZERO_DIV]))
    AgentTypeConfig.clear_cache()
    try:
        with pytest.raises(CouplingViolation, match="zero_div"):
            broker.run.main([
                str(ops_case.CONFIG_PATH), "--years", "2", "--output", str(tmp_path / "out"),
            ])
    finally:
        AgentTypeConfig.clear_cache()


def test_zero_divisor_stops_a_parallel_run(monkeypatch, tmp_path):
    # The builder refuses workers>1 with feasibility bounds; the parallel step
    # handler still re-raises (defence in depth), so drive it directly.
    from broker.core.experiment_runner import ExperimentRunner

    monkeypatch.setattr(ops_case, "build_contract", lambda: _contract([ZERO_DIV]))
    calls = []
    orig_parallel = ExperimentRunner._run_agents_parallel

    def spy(self, *a, **k):
        calls.append(self.config.workers)
        return orig_parallel(self, *a, **k)

    monkeypatch.setattr(ExperimentRunner, "_run_agents_parallel", spy)
    AgentTypeConfig.clear_cache()
    try:
        runner = broker.run.prepare([
            str(ops_case.CONFIG_PATH), "--model", "mock", "--years", "2",
            "--output", str(tmp_path / "out"), "--seed", "42",
        ]).runner
        runner.config.workers = 2
        with pytest.raises(ProjectionCheckError, match="zero_div"):
            runner.run()
    finally:
        AgentTypeConfig.clear_cache()
    assert calls and set(calls) == {2}, "the parallel step handler was not used"


# ----------------------------------------------------------------- 12. mixed ----
def test_relations_are_still_checked_after_execution_alongside_feasibility(tmp_path):
    out = tmp_path / "out"
    runner = broker.run.prepare([
        str(ops_case.CONFIG_PATH), "--model", "mock", "--years", "3",
        "--output", str(out), "--seed", "42",
    ]).runner
    runner.run()
    prov = runner.sim_engine.get_provenance()
    assert prov["relations"]["declared"][0]["name"] == "storage_balance"
    assert prov["relations"]["checks_run"] > 0
    assert prov["feasibility"]["source"] == "copy"
    assert prov["feasibility"]["projections_run"] >= 3
    assert "ProjectionCheck" in [type(v).__name__ for v in runner.broker.custom_validators]
