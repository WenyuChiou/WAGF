"""Tests for continuous quantitative-control coupling (Phase 6V increment 3).

Covers the execution path for what the contract previously only declared
(review P0-1/P0-2) plus the runtime contract guards (check #3 + the
execution-sampling guard, review item 3/4) and the provenance package
(review P0-3) and the world-delta CSV plane (review P1-9).

The toy reservoir below is the first CONTINUOUS consumer: storage integrates
inflow minus an agent-set release each sub-step — a real (if tiny) control
problem, exercised through the standard BMI verb set. No LLM/GPU.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from broker.coupling import (
    BmiControlSink,
    ContinuousBundle,
    CouplingContract,
    CouplingViolation,
    EnvironmentCouplingAdapter,
    VarSpec,
    WorldDelta,
    reduce_series,
)
from broker.interfaces.skill_types import ApprovedSkill


# --------------------------------------------------------------------------
# Toy BMI reservoir: S[t+1] = max(0, S + inflow - release)
# --------------------------------------------------------------------------
class ToyBmiReservoir:
    """BMI-conformant linear reservoir with a settable release control."""

    def __init__(self, inflow_per_step: float = 10.0, initial_storage: float = 0.0):
        self._inflow = float(inflow_per_step)
        self._storage = float(initial_storage)
        self._release = 0.0
        self._t = 0.0

    # -- BMI verbs ----------------------------------------------------------
    def get_component_name(self) -> str:
        return "toy-linear-reservoir"

    def update(self) -> None:
        self._storage = max(0.0, self._storage + self._inflow - self._release)
        self._t += 1.0

    def get_value(self, name: str) -> List[float]:
        if name == "storage":
            return [self._storage]
        if name == "release":
            return [self._release]
        raise KeyError(name)

    def set_value(self, name: str, value) -> None:
        if name != "release":
            raise KeyError(f"{name!r} is not a settable input")
        self._release = float(list(value)[0] if hasattr(value, "__len__") else value)

    def get_var_units(self, name: str) -> str:
        return "af"  # acre-feet, toy

    def get_current_time(self) -> float:
        return self._t


def _contract(reduce: str = "min", value_source: str = "proposal") -> CouplingContract:
    return CouplingContract(
        observations=(
            VarSpec("storage", float, "af", lo=0.0, hi=1e9,
                    cadence="per_solver_step", observation_reduce=reduce),
        ),
        inputs=(
            VarSpec("release", float, "af_per_step", lo=0.0, hi=100.0,
                    direction="agent_to_world", value_source=value_source),
        ),
        decision_cadence="annual",
        solver_cadence="sub_step",
        substeps_per_decision=4,
    )


def _bundle(reduce: str = "min", **kw) -> ContinuousBundle:
    return ContinuousBundle(contract=_contract(reduce, **kw), solver=ToyBmiReservoir())


def _approved(**params) -> ApprovedSkill:
    return ApprovedSkill(skill_name="set_release", agent_id="OP",
                         approval_status="APPROVED", parameters=dict(params))


# --------------------------------------------------------------------------
# reduce_series — the check-#2 executor
# --------------------------------------------------------------------------
def test_reduce_series_all_modes():
    vals = [10.0, 20.0, 30.0, 40.0]
    assert reduce_series(vals, "mean") == pytest.approx(25.0)
    assert reduce_series(vals, "max") == 40.0
    assert reduce_series(vals, "min") == 10.0
    assert reduce_series(vals, "sum") == 100.0
    assert reduce_series(vals, "last") == 40.0


def test_reduce_series_empty_and_unknown_fail_loud():
    with pytest.raises(ValueError, match="empty"):
        reduce_series([], "mean")
    with pytest.raises(ValueError, match="unknown"):
        reduce_series([1.0], "median")


# --------------------------------------------------------------------------
# ContinuousBundle — K sub-steps + declared reduction
# --------------------------------------------------------------------------
def test_run_pipeline_advances_k_substeps_and_reduces():
    # no release: storage series 10,20,30,40 -> min=10
    bundle = _bundle(reduce="min")
    env = bundle.run_pipeline({"current_year": 1}, [], (), "constant")
    assert env["storage"] == pytest.approx(10.0)
    assert env["_substeps_run"] == 4
    # mean over a fresh bundle: (10+20+30+40)/4 = 25
    env2 = _bundle(reduce="mean").run_pipeline({}, [], (), "constant")
    assert env2["storage"] == pytest.approx(25.0)


def test_committed_release_holds_constant_across_substeps():
    """control_hold_policy='constant': the setpoint persists in the solver, so
    the next period's K sub-steps all see it. inflow 10, release 4 ->
    storage 6,12,18,24 -> min=6."""
    bundle = _bundle(reduce="min")
    delta = bundle.commit_world_delta(_approved(release=4.0))
    assert delta.world_changes == {"release": 4.0}
    env = bundle.run_pipeline({}, [], (), "constant")
    assert env["storage"] == pytest.approx(6.0)


def test_non_constant_hold_policy_raises():
    bundle = _bundle()
    with pytest.raises(NotImplementedError, match="ramp"):
        bundle.run_pipeline({}, [], (), "ramp")


def test_bundle_requires_substeps_declaration():
    contract = CouplingContract(
        observations=(VarSpec("storage", float, "af", cadence="per_solver_step",
                              observation_reduce="min"),),
        solver_cadence="sub_step",
    )  # substeps_per_decision omitted
    with pytest.raises(ValueError, match="substeps_per_decision"):
        ContinuousBundle(contract=contract, solver=ToyBmiReservoir())


def test_setpoint_without_sink_fails_loud():
    """A solver without set_value -> no sink; an agent-authored setpoint must
    NOT be silently dropped."""
    class ReadOnlySolver(ToyBmiReservoir):
        set_value = None  # shadow with non-callable -> no sink derived

    bundle = ContinuousBundle(contract=_contract(), solver=ReadOnlySolver())
    assert bundle.sink is None
    with pytest.raises(ValueError, match="ControlSink"):
        bundle.commit_world_delta(_approved(release=4.0))


def test_commit_without_setpoint_params_is_inert():
    bundle = _bundle()
    delta = bundle.commit_world_delta(_approved())
    assert delta.world_changes == {}


def test_bmi_control_sink_requires_set_value():
    class NoWrite:
        pass

    with pytest.raises(TypeError, match="set_value"):
        BmiControlSink(NoWrite())


# --------------------------------------------------------------------------
# 6W-B5 — multi-field bridge consumption + R1 mixed-bag (magnitude_fallback) skip
# --------------------------------------------------------------------------
def _contract_two_inputs() -> CouplingContract:
    """A contract whose inputs include a real setpoint AND a (mis-named)
    'magnitude_fallback' input — the R1 footgun the B5 hardening must defuse."""
    return CouplingContract(
        observations=(
            VarSpec("storage", float, "af", lo=0.0, hi=1e9,
                    cadence="per_solver_step", observation_reduce="min"),
        ),
        inputs=(
            VarSpec("release", float, "af_per_step", lo=0.0, hi=100.0,
                    direction="agent_to_world", value_source="proposal"),
            VarSpec("magnitude_fallback", float, "x", lo=0.0, hi=1.0,
                    direction="agent_to_world", value_source="proposal"),
        ),
        decision_cadence="annual", solver_cadence="sub_step", substeps_per_decision=4,
    )


def test_commit_applies_declared_setpoint_from_bridged_params():
    """The world side consumes the bridged multi-field ApprovedSkill.parameters."""
    bundle = ContinuousBundle(contract=_contract_two_inputs(), solver=ToyBmiReservoir())
    delta = bundle.commit_world_delta(_approved(release=4.0))
    assert delta.world_changes["release"] == 4.0


def test_commit_skips_magnitude_fallback_even_if_declared_input():
    """6W-B5 (R1): magnitude_fallback (the audit-only bool the bridge co-locates
    with setpoints) is NEVER coerced through float()/applied as a setpoint — even
    when a contract mis-declares it as an input."""
    bundle = ContinuousBundle(contract=_contract_two_inputs(), solver=ToyBmiReservoir())
    delta = bundle.commit_world_delta(_approved(release=4.0, magnitude_fallback=True))
    assert delta.world_changes["release"] == 4.0
    assert "magnitude_fallback" not in delta.world_changes  # skipped, not float(True)=1.0


# --------------------------------------------------------------------------
# Adapter e2e — continuous bundle behind the standard adapter
# --------------------------------------------------------------------------
def _adapter(bundle=None):
    bundle = bundle or _bundle()
    return EnvironmentCouplingAdapter(real_engine=None, contract=bundle.contract,
                                      sources=bundle), bundle


def test_adapter_advance_step_with_no_event_source():
    adapter, _ = _adapter()
    env = adapter.advance_step()
    assert env["current_year"] == 1
    assert env["storage"] == pytest.approx(10.0)  # min of 10,20,30,40


def test_adapter_full_decide_commit_cycle():
    """Period 1 observe -> commit release=4 -> period 2 reflects the control."""
    adapter, _ = _adapter()
    adapter.advance_step()  # storage now 40 internally
    result = adapter.execute_skill(_approved(release=4.0))
    assert result.success
    assert result.action_context["world_delta"]["world_changes"] == {"release": 4.0}
    env2 = adapter.advance_step()  # 46,52,58,64 -> min=46
    assert env2["storage"] == pytest.approx(46.0)


@pytest.mark.parametrize("exceptions", [[], ["TR1"]])
def test_adapter_preserves_domain_audit_context(exceptions):
    """Domain audit keys survive coupling; contract evidence remains authoritative."""
    class ContextBundle(ContinuousBundle):
        def commit_world_delta(self, approved_skill):
            delta = super().commit_world_delta(approved_skill)
            return WorldDelta(
                agent_state_changes=delta.agent_state_changes,
                world_changes=delta.world_changes,
                contention_rule=delta.contention_rule,
                action_context={
                    "rule_exceptions_used": exceptions,
                    "world_delta": "cannot replace contract evidence",
                    "contention_rule": "cannot replace contract evidence",
                },
            )

    bundle = ContextBundle(contract=_contract(), solver=ToyBmiReservoir())
    adapter, _ = _adapter(bundle)
    result = adapter.execute_skill(_approved(release=4.0))
    assert result.action_context == {
        "rule_exceptions_used": exceptions,
        "world_delta": {"world_changes": {"release": 4.0}, "contention_rule": "none"},
        "contention_rule": "none",
    }


def test_adapter_default_audit_context_is_unchanged():
    adapter, _ = _adapter()
    result = adapter.execute_skill(_approved(release=4.0))
    assert result.action_context == {
        "world_delta": {"world_changes": {"release": 4.0}, "contention_rule": "none"},
        "contention_rule": "none",
    }


# --------------------------------------------------------------------------
# Runtime contract guards in execute_skill (checks #1/#3 + sampling guard)
# --------------------------------------------------------------------------
def test_out_of_range_setpoint_blocked_pre_commit():
    adapter, bundle = _adapter()
    with pytest.raises(CouplingViolation, match="above hi"):
        adapter.execute_skill(_approved(release=500.0))  # hi=100
    # and the solver was never touched (pre-commit guard)
    assert bundle.solver._release == 0.0


def test_agent_write_to_observation_key_blocked_direction_check():
    adapter, _ = _adapter()
    with pytest.raises(CouplingViolation, match="direction check #3"):
        adapter.execute_skill(_approved(storage=123.0))  # storage is world-owned


def test_sampling_guard_blocks_world_side_divergence():
    """A bundle that commits a value diverging from the approved proposal's
    parameter must be caught — the execution-sampling bug class."""
    class DivergingBundle(ContinuousBundle):
        def commit_world_delta(self, approved_skill):
            delta = super().commit_world_delta(approved_skill)
            wc = dict(delta.world_changes)
            if "release" in wc:
                wc["release"] = wc["release"] + 1.0  # world-side re-sample
            return WorldDelta(agent_state_changes={}, world_changes=wc,
                              contention_rule="none")

    bundle = DivergingBundle(contract=_contract(value_source="proposal"),
                             solver=ToyBmiReservoir())
    adapter = EnvironmentCouplingAdapter(real_engine=None, contract=bundle.contract,
                                         sources=bundle)
    with pytest.raises(CouplingViolation, match="diverges"):
        adapter.execute_skill(_approved(release=5.0))


def test_sampling_guard_blocks_synthesized_proposal_input():
    """Committing a proposal-sourced input the agent never proposed is the
    other half of the sampling guard."""
    class SynthesizingBundle(ContinuousBundle):
        def commit_world_delta(self, approved_skill):
            self.sink.apply_control("release", 7.0)
            return WorldDelta(agent_state_changes={},
                              world_changes={"release": 7.0}, contention_rule="none")

    bundle = SynthesizingBundle(contract=_contract(value_source="proposal"),
                                solver=ToyBmiReservoir())
    adapter = EnvironmentCouplingAdapter(real_engine=None, contract=bundle.contract,
                                         sources=bundle)
    with pytest.raises(CouplingViolation, match="absent from the"):
        adapter.execute_skill(_approved())  # no release param proposed


def test_world_deterministic_input_has_no_sampling_guard():
    """value_source='world_deterministic' (the cat-model shape) commits world-
    computed values freely — guard only binds proposal-sourced inputs."""
    class WorldComputedBundle(ContinuousBundle):
        def commit_world_delta(self, approved_skill):
            self.sink.apply_control("release", 3.0)
            return WorldDelta(agent_state_changes={},
                              world_changes={"release": 3.0}, contention_rule="none")

    bundle = WorldComputedBundle(contract=_contract(value_source="world_deterministic"),
                                 solver=ToyBmiReservoir())
    adapter = EnvironmentCouplingAdapter(real_engine=None, contract=bundle.contract,
                                         sources=bundle)
    result = adapter.execute_skill(_approved())  # no params — fine
    assert result.success


# --------------------------------------------------------------------------
# Provenance (review P0-3)
# --------------------------------------------------------------------------
def test_adapter_provenance_pins_contract_and_solver_identity():
    adapter, bundle = _adapter()
    prov = adapter.get_provenance()
    assert prov["adapter_class"] == "EnvironmentCouplingAdapter"
    assert len(prov["contract_sha256"]) == 16
    assert prov["bundle_class"] == "ContinuousBundle"
    assert prov["bundle_provenance"]["solver_component_name"] == "toy-linear-reservoir"
    assert prov["bundle_provenance"]["substeps_per_decision"] == 4
    # deterministic: same contract -> same sha
    adapter2, _ = _adapter()
    assert adapter2.get_provenance()["contract_sha256"] == prov["contract_sha256"]


def test_bmi_event_source_provenance_reads_component_name():
    from broker.coupling import BmiEventSource
    from examples.cat_model.bmi_flood_model import ToyBmiFloodModel

    src = BmiEventSource(ToyBmiFloodModel(rainfall=[1.0]), value_var="depth")
    prov = src.get_provenance()
    assert prov["component_name"] == "toy-linear-reservoir-flood-stage"
    assert prov["value_var"] == "depth"
    assert prov["unit"] == "ft"


# --------------------------------------------------------------------------
# World-delta CSV plane (review P1-9) — key-gated flattening
# --------------------------------------------------------------------------
def _base_trace(**extra) -> Dict[str, Any]:
    t = {
        "step_id": 1, "year": 1, "agent_id": "OP",
        "skill_proposal": {"skill_name": "set_release"},
        "approved_skill": {"skill_name": "set_release", "status": "APPROVED"},
    }
    t.update(extra)
    return t


def test_world_delta_flattens_into_csv_row():
    from broker.components.analytics.audit import trace_to_csv_row

    t = _base_trace(execution_result={
        "success": True, "state_changes": {},
        "action_context": {
            "world_delta": {"world_changes": {"release": 4.0, "spill": 0.0},
                            "contention_rule": "none"},
            "contention_rule": "none",
        },
    })
    row = trace_to_csv_row(t)
    assert row["world_release"] == 4.0
    assert row["world_spill"] == 0.0
    assert row["world_contention_rule"] == "none"


def test_frozen_shaped_trace_gains_no_world_columns():
    """The byte-identity gate: a trace WITHOUT the coupled execution_result
    key (every frozen-domain trace) must produce a row with ZERO world_*
    keys — fieldnames derive from row keys, so frozen CSVs are unchanged."""
    from broker.components.analytics.audit import compute_csv_fieldnames, trace_to_csv_row

    row = trace_to_csv_row(_base_trace())
    world_keys = [k for k in row if k.startswith("world_")]
    assert world_keys == [], world_keys
    assert "world_contention_rule" not in compute_csv_fieldnames([row])


def test_float_substeps_coerced_to_int_at_construction():
    """Review W1: a float K must coerce to int IN THE CONTRACT so the
    provenance sha and the executed K can never diverge."""
    c = _contract()
    c2 = CouplingContract(
        observations=c.observations, inputs=c.inputs,
        decision_cadence="annual", solver_cadence="sub_step",
        substeps_per_decision=4.7,
    )
    assert c2.substeps_per_decision == 4
    assert isinstance(c2.substeps_per_decision, int)
    # identical effective contract -> identical sha
    import hashlib
    sha = lambda x: hashlib.sha256(repr(x).encode()).hexdigest()
    assert sha(c2) == sha(CouplingContract(
        observations=c.observations, inputs=c.inputs,
        decision_cadence="annual", solver_cadence="sub_step",
        substeps_per_decision=4,
    ))


def test_non_numeric_committed_value_raises_coupling_violation_not_valueerror():
    """Review W2: a broken bundle committing a non-numeric value for a declared
    input must surface as CouplingViolation (classified), never a raw
    ValueError from float().

    (PR-9 review P0 changed only the MESSAGE, not the outcome: a str in a
    numeric slot is now named as a dtype violation instead of a coercion
    failure, because ``float("55")`` succeeds and the old wording could never
    have described it. The assertion below still pins the same property this
    test was written for -- CouplingViolation, not ValueError.)"""
    class BrokenBundle(ContinuousBundle):
        def commit_world_delta(self, approved_skill):
            return WorldDelta(agent_state_changes={},
                              world_changes={"release": "error_token"},
                              contention_rule="none")

    bundle = BrokenBundle(contract=_contract(), solver=ToyBmiReservoir())
    adapter = EnvironmentCouplingAdapter(real_engine=None, contract=bundle.contract,
                                         sources=bundle)
    with pytest.raises(CouplingViolation, match="is a str, not a float"):
        adapter.execute_skill(_approved(release=5.0))
