"""Tests for the generic environment-coupling contract + adapter
(broker/coupling/, Phase 6V).

Covers the four numerical-correctness checks and the adapter's world->agent /
agent->world paths with stub interfaces (no domain code needed). The
double-count NEGATIVE CONTROL (test_double_count_*) is the load-bearing proof
that the E2 guard catches a mass-balance double-count, not just documents it.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any, Dict, List

import pytest

from broker.coupling import (
    CouplingContract,
    EnvironmentCouplingAdapter,
    Event,
    InterfaceBundle,
    VarSpec,
    WorldDelta,
)
from broker.coupling.adapter import CouplingViolation
from broker.interfaces.skill_types import ApprovedSkill


# --------------------------------------------------------------------------
# VarSpec validation
# --------------------------------------------------------------------------
def test_varspec_rejects_bad_enums():
    with pytest.raises(ValueError):
        VarSpec("x", float, "m", cadence="bogus")
    with pytest.raises(ValueError):
        VarSpec("x", float, "m", direction="sideways")
    with pytest.raises(ValueError):
        VarSpec("x", float, "m", observation_reduce="median")


def test_varspec_numeric_requires_unit():
    with pytest.raises(ValueError):
        VarSpec("loss", float, "")  # numeric must declare a unit


def test_varspec_range_violation():
    vs = VarSpec("ratio", float, "ratio_decimal", lo=0.0, hi=1.0)
    assert vs.range_violation(0.5) is None
    assert vs.range_violation(1.5) is not None
    assert vs.range_violation(-0.1) is not None
    assert vs.range_violation(None) is None  # missing handled elsewhere


# --------------------------------------------------------------------------
# Contract directionality + checks
# --------------------------------------------------------------------------
def test_contract_enforces_direction_on_lists():
    bad_obs = VarSpec("x", float, "m", direction="agent_to_world")
    with pytest.raises(ValueError):
        CouplingContract(observations=(bad_obs,))


def test_check_cadence_requires_explicit_reduce_when_cadences_differ():
    obs = VarSpec("storage", float, "m3", cadence="per_solver_step")  # default reduce='last'
    c = CouplingContract(observations=(obs,), decision_cadence="annual", solver_cadence="sub_step")
    problems = c.check_cadence()
    assert any("storage" in p for p in problems), problems
    # declaring an explicit reduction clears it
    obs2 = VarSpec("storage", float, "m3", cadence="per_solver_step", observation_reduce="mean")
    c2 = CouplingContract(observations=(obs2,), decision_cadence="annual", solver_cadence="sub_step")
    assert c2.check_cadence() == []


def test_check_direction_lookup():
    c = CouplingContract(
        observations=(VarSpec("loss", float, "USD_2020"),),
        inputs=(VarSpec("payout", float, "USD_2020", direction="agent_to_world"),),
    )
    assert c.check_direction("loss") == "world"
    assert c.check_direction("payout") == "agent"
    assert c.check_direction("absent") is None


# --------------------------------------------------------------------------
# DOUBLE-COUNT NEGATIVE CONTROL (E2) — the load-bearing guard
# --------------------------------------------------------------------------
def test_double_count_construction_raises():
    """Declaring the SAME ledger quantity with two consumer_of_record=True
    VarSpecs is the classic mass-balance double-count bug. The contract MUST
    reject it at construction (fail-fast), not silently sum twice."""
    dup_a = VarSpec("pool_loss", float, "USD_2020", consumer_of_record=True)
    dup_b = VarSpec("pool_loss", float, "USD_2020", direction="agent_to_world", consumer_of_record=True)
    with pytest.raises(ValueError, match="double-count"):
        CouplingContract(observations=(dup_a,), inputs=(dup_b,))


def test_double_count_fixed_by_marking_one_diagnostic():
    """Marking all-but-one duplicate as consumer_of_record=False is the fix;
    then the contract constructs and reports exactly one consumer."""
    of_record = VarSpec("pool_loss", float, "USD_2020", consumer_of_record=True)
    diagnostic = VarSpec(
        "pool_loss", float, "USD_2020", direction="agent_to_world", consumer_of_record=False
    )
    c = CouplingContract(observations=(of_record,), inputs=(diagnostic,))
    assert c.ledger_consumers() == {"pool_loss": 1}


# --------------------------------------------------------------------------
# Adapter world->agent + agent->world (stub interfaces)
# --------------------------------------------------------------------------
class _StubEventSource:
    def __init__(self, intensity: float = 0.4):
        self._intensity = intensity

    def draw_events(self, period: int) -> List[Event]:
        return [Event(event_id=f"e{period}", period=period, payload={"intensity": self._intensity})]

    def intensity_at(self, agent_id: str, event: Event) -> float:
        return self._intensity

    def units(self) -> str:
        return "ratio_decimal"


class _StubBundle(InterfaceBundle):
    """Projects a contracted observation + a commit delta for testing."""

    def run_pipeline(self, base_env, events, operation_order, control_hold_policy="constant"):
        env = dict(base_env)
        env["hazard_intensity"] = events[0].payload["intensity"] if events else 0.0
        return env

    def commit_world_delta(self, approved_skill) -> WorldDelta:
        return WorldDelta(
            agent_state_changes={"committed": approved_skill.skill_name},
            world_changes={"applied": True},
            contention_rule="full",
        )


def _adapter():
    contract = CouplingContract(
        observations=(VarSpec("hazard_intensity", float, "ratio_decimal", lo=0.0, hi=1.0),),
        inputs=(VarSpec("payout", float, "USD_2020", direction="agent_to_world"),),
    )
    bundle = _StubBundle(event_src=_StubEventSource())
    return EnvironmentCouplingAdapter(real_engine=None, contract=contract, sources=bundle)


def test_adapter_advance_step_projects_and_validates():
    a = _adapter()
    env = a.advance_step()
    assert env["current_year"] == 1
    assert env["hazard_intensity"] == 0.4


def test_adapter_advance_step_fails_loud_on_out_of_range():
    contract = CouplingContract(
        observations=(VarSpec("hazard_intensity", float, "ratio_decimal", lo=0.0, hi=1.0),),
    )
    bundle = _StubBundle(event_src=_StubEventSource(intensity=9.0))  # out of [0,1]
    a = EnvironmentCouplingAdapter(real_engine=None, contract=contract, sources=bundle)
    with pytest.raises(CouplingViolation, match="hazard_intensity"):
        a.advance_step()


def test_adapter_execute_skill_is_commit_only():
    a = _adapter()
    approved = ApprovedSkill(skill_name="payout", agent_id="INS", approval_status="APPROVED")
    result = a.execute_skill(approved)
    assert result.success is True
    assert result.state_changes == {"committed": "payout"}
    assert result.action_context["contention_rule"] == "full"
    assert result.action_context["world_delta"]["world_changes"] == {"applied": True}


# --------------------------------------------------------------------------
# Import-inert lock: broker.coupling must register NOTHING at import
# --------------------------------------------------------------------------
def test_importing_broker_coupling_is_registration_inert():
    """Importing ``broker.coupling`` must have NO registration side effects
    (no validators, no domain packs) — domain registration lives only in
    ``examples/<domain>``. Subprocess so the assertion isn't polluted by other
    tests in this session importing examples.cat_model into the shared registry."""
    code = (
        "import broker.coupling\n"
        "from broker.components.governance.validator_registry import ValidatorRegistry\n"
        "assert not ValidatorRegistry.has_domain('cat_model'), "
        "'broker.coupling import must NOT register the cat_model domain'\n"
        "print('INERT_OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "INERT_OK" in r.stdout, (
        f"import-inert check failed:\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
    )
