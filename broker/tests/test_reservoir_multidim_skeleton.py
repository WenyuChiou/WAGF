"""Phase 6W-B7 — reservoir_control_multidim worked-example skeleton.

Proves the multi-dimensional-action chain end-to-end (mock, no LLM): a domain declares
3 bounded numeric setpoints (param_specs) -> the generic ParameterBoundsValidator
bounds-checks each -> approved setpoints commit to the hosted solver via the plain
ContinuousBundle (B5 applies each named setpoint; no derive/override needed). The full
gemma4:e4b worked run + baseline are a separate ollama task. See
.research/wagf_coupling_IMPLEMENTATION_PLAN_2026-06-12.md (B7).
"""
import pytest

from broker.coupling import ContinuousBundle, CouplingContract, VarSpec
from broker.coupling.param_validator import make_parameter_bounds_validator
from broker.interfaces.skill_types import ApprovedSkill
from examples.reservoir_control_multidim.ops_modules_multidim import ToyMultiReservoir
from examples.reservoir_control_multidim.reservoir_multidim_pack import (
    ReservoirMultidimDomainPack,
)


def _contract():
    return CouplingContract(
        observations=(
            # per_decision delivers ONE storage value/period -> "last" is accepted by
            # check_cadence (matches reservoir_control's storage; the adapter rejects
            # per_solver_step + implicit "last" under sub_step/annual).
            VarSpec("storage", float, "maf", lo=0.0, hi=1e9,
                    cadence="per_decision", observation_reduce="last"),
        ),
        inputs=(
            VarSpec("release_rate_cms", float, "cms", lo=0.0, hi=850.0,
                    direction="agent_to_world", value_source="proposal"),
            VarSpec("hydropower_target_mw", float, "MW", lo=0.0, hi=2000.0,
                    direction="agent_to_world", value_source="proposal"),
            VarSpec("flood_pool_pct", float, "pct", lo=0.0, hi=100.0,
                    direction="agent_to_world", value_source="proposal"),
        ),
        decision_cadence="annual", solver_cadence="sub_step", substeps_per_decision=12,
    )


def _approved(**params):
    return ApprovedSkill(skill_name="set_release_multi", agent_id="OP",
                         approval_status="APPROVED", parameters=dict(params))


def test_param_specs_declares_three_setpoints():
    specs = ReservoirMultidimDomainPack().param_specs()
    assert set(specs) == {"set_release_multi"}
    assert [v.name for v in specs["set_release_multi"]] == [
        "release_rate_cms", "hydropower_target_mw", "flood_pool_pct"
    ]


def test_validator_blocks_out_of_bounds_setpoint():
    v = make_parameter_bounds_validator(ReservoirMultidimDomainPack().param_specs())
    ctx = {"proposed_parameters": {"release_rate_cms": 900.0,  # > hi=850
                                   "hydropower_target_mw": 800.0, "flood_pool_pct": 10.0}}
    res = v("set_release_multi", [], ctx)
    assert any(r.metadata["rule_id"] == "param_bounds_release_rate_cms" and not r.valid for r in res)


def test_validator_passes_in_bounds():
    v = make_parameter_bounds_validator(ReservoirMultidimDomainPack().param_specs())
    ctx = {"proposed_parameters": {"release_rate_cms": 400.0,
                                   "hydropower_target_mw": 800.0, "flood_pool_pct": 10.0}}
    assert v("set_release_multi", [], ctx) == []


def test_commit_applies_all_three_setpoints_to_solver():
    solver = ToyMultiReservoir()
    bundle = ContinuousBundle(contract=_contract(), solver=solver)
    delta = bundle.commit_world_delta(
        _approved(release_rate_cms=300.0, hydropower_target_mw=1200.0, flood_pool_pct=25.0)
    )
    assert delta.world_changes == {
        "release_rate_cms": 300.0, "hydropower_target_mw": 1200.0, "flood_pool_pct": 25.0
    }
    assert solver.get_value("release_rate_cms") == [300.0]
    assert solver.get_value("flood_pool_pct") == [25.0]


def test_package_import_registers_without_error():
    import examples.reservoir_control_multidim as pkg  # registration side effect

    assert pkg.ReservoirMultidimDomainPack().param_specs()["set_release_multi"]
