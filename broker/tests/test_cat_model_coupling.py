"""Tests for the catastrophe-model coupling example (Phase 6V).

Covers the world-mutation governance check (the novelty hook), the cat-model
coupling modules (hazard source + financial ledger + bundle), and the
package-import registration side effects. The full broker retry-loop e2e (an
over-pool approve_payout re-prompting via the real engine, retry_count>0) is
exercised by the real-LLM smoke run of run_cat.py; here we lock the validator
logic + the bundle mechanics deterministically (no LLM, no GPU).
"""
from __future__ import annotations

import importlib

import pytest

from examples.cat_model.cat_validators import insurer_payout_solvency_check
from examples.cat_model.coupling_modules import (
    CatBundle,
    FloodFootprintSource,
    PortfolioLedger,
    depth_damage_ratio,
)
from broker.coupling import EnvironmentCouplingAdapter
from broker.interfaces.skill_types import ApprovedSkill


# --------------------------------------------------------------------------
# The world-mutation governance check (the novelty hook)
# --------------------------------------------------------------------------
def _ctx(**env):
    return {"env_state": dict(env), "agent_type": "insurer"}


def test_payout_blocked_when_pool_insolvent():
    ctx = _ctx(
        policy_in_force_before_event=True,
        agent_ground_up_loss=100_000.0,
        policy_deductible=5_000.0,
        policy_limit=50_000.0,
        pool_budget_remaining=10_000.0,  # owed=50k > pool=10k
    )
    out = insurer_payout_solvency_check("approve_payout", [], ctx)
    assert len(out) == 1 and out[0].valid is False
    assert out[0].metadata["rule_id"] == "pool_insolvent"


def test_payout_blocked_when_policy_not_in_force():
    ctx = _ctx(policy_in_force_before_event=False, agent_ground_up_loss=10.0,
               policy_deductible=0.0, policy_limit=1e9, pool_budget_remaining=1e9)
    out = insurer_payout_solvency_check("approve_payout", [], ctx)
    assert len(out) == 1 and out[0].valid is False
    assert out[0].metadata["rule_id"] == "policy_not_in_force"


def test_payout_valid_when_solvent_and_in_force():
    ctx = _ctx(
        policy_in_force_before_event=True,
        agent_ground_up_loss=20_000.0,
        policy_deductible=5_000.0,
        policy_limit=50_000.0,
        pool_budget_remaining=100_000.0,  # owed=15k <= pool
    )
    assert insurer_payout_solvency_check("approve_payout", [], ctx) == []


def test_check_ignores_non_payout_skill():
    assert insurer_payout_solvency_check("deny_payout", [], _ctx()) == []


def test_payout_blocked_when_world_state_missing():
    """A governance check must NEVER approve a world-mutating payout on ABSENT
    data — missing required fields BLOCK (not silent-zero/silent-approve)."""
    out = insurer_payout_solvency_check("approve_payout", [], {"env_state": {}, "agent_type": "insurer"})
    assert len(out) == 1 and out[0].valid is False
    assert out[0].metadata["rule_id"] == "missing_world_state"
    assert set(out[0].metadata["missing"]) >= {
        "policy_in_force_before_event", "agent_ground_up_loss",
        "policy_deductible", "pool_budget_remaining",
    }


# --------------------------------------------------------------------------
# Coupling modules
# --------------------------------------------------------------------------
def test_depth_damage_monotone_capped():
    assert depth_damage_ratio(0.0) == 0.0
    assert 0.0 < depth_damage_ratio(2.0) < depth_damage_ratio(6.0) <= 1.0
    assert depth_damage_ratio(1000.0) == 1.0


def test_footprint_source_emits_event_only_when_depth():
    src = FloodFootprintSource({1: 0.0, 2: 4.0})
    assert src.draw_events(1) == []
    ev = src.draw_events(2)
    assert len(ev) == 1 and ev[0].payload["depth"] == 4.0
    assert src.units() == "ft"


def test_ledger_terms_and_settlement():
    led = PortfolioLedger(pool_budget=10_000.0)
    # ground-up 100k, deductible 5k, limit 50k -> gross 50k
    assert led.ground_up_to_gross(100_000.0, {"deductible": 5_000.0, "limit": 50_000.0}) == 50_000.0
    # settle two claims exceeding the pool -> pro-rata, pool exhausted
    s = led.settle({"a": 6_000.0, "b": 6_000.0})
    assert s.rule == "pro_rata"
    assert abs(s.total - 10_000.0) < 1e-6
    assert s.pool_remaining == 0.0


def test_bundle_pipeline_projects_observations_and_commit_debits_once():
    # Pool sized so the owed amount is solvent (the governed path: payout_valid
    # only lets approve_payout through when owed <= pool, so commit pays in full).
    led = PortfolioLedger(pool_budget=200_000.0)
    bundle = CatBundle(
        FloodFootprintSource({1: 6.0}), led,
        exposure_value=250_000.0, deductible=5_000.0, limit=200_000.0,
    )
    env = bundle.run_pipeline({"current_year": 1}, bundle.event_src.draw_events(1), ())
    assert env["flood_depth_ft"] == 6.0
    assert env["agent_ground_up_loss"] > 0.0
    assert env["policy_in_force_before_event"] is True
    owed = env["owed_payout"]
    assert owed <= led.pool_budget  # solvent fixture
    # commit an approved payout -> pool debited exactly once by the owed amount
    approved = ApprovedSkill(skill_name="approve_payout", agent_id="INS", approval_status="APPROVED")
    delta = bundle.commit_world_delta(approved)
    assert abs(delta.world_changes["payout"] - owed) < 1e-6
    assert abs(led.pool_budget - (200_000.0 - owed)) < 1e-6
    # a non-payout commit is inert
    deny = ApprovedSkill(skill_name="deny_payout", agent_id="INS", approval_status="APPROVED")
    d2 = bundle.commit_world_delta(deny)
    assert d2.world_changes["payout"] == 0.0


def test_commit_before_run_pipeline_raises():
    """Committing a payout without a same-period run_pipeline (no owed amount
    established) is a hard error, not a silent zero-debit."""
    from broker.coupling import CouplingViolation

    bundle = CatBundle(FloodFootprintSource({1: 4.0}), PortfolioLedger(100_000.0))
    approved = ApprovedSkill(skill_name="approve_payout", agent_id="INS", approval_status="APPROVED")
    with pytest.raises(CouplingViolation):
        bundle.commit_world_delta(approved)


def test_double_commit_is_idempotent_no_double_debit():
    """E2: a second commit of the same approved payout must NOT debit the pool
    again — it raises (the owed amount was consumed by the first commit)."""
    from broker.coupling import CouplingViolation

    led = PortfolioLedger(200_000.0)
    bundle = CatBundle(FloodFootprintSource({1: 4.0}), led)
    bundle.run_pipeline({"current_year": 1}, bundle.event_src.draw_events(1), ())
    approved = ApprovedSkill(skill_name="approve_payout", agent_id="INS", approval_status="APPROVED")
    pool_before = led.pool_budget
    paid = bundle.commit_world_delta(approved).world_changes["payout"]
    assert abs(led.pool_budget - (pool_before - paid)) < 1e-6
    with pytest.raises(CouplingViolation):
        bundle.commit_world_delta(approved)
    assert abs(led.pool_budget - (pool_before - paid)) < 1e-6  # unchanged, no double-debit


def test_adapter_with_cat_bundle_end_to_end_world_to_agent():
    led = PortfolioLedger(pool_budget=100_000.0)
    bundle = CatBundle(FloodFootprintSource({1: 4.0}), led)
    from broker.coupling import CouplingContract, VarSpec

    contract = CouplingContract(
        observations=(
            VarSpec("flood_depth_ft", float, "ft", lo=0.0, hi=100.0),
            VarSpec("agent_ground_up_loss", float, "USD_2020", lo=0.0),
            VarSpec("pool_budget_remaining", float, "USD_2020", lo=0.0),
        ),
        inputs=(VarSpec("owed_payout", float, "USD_2020", direction="agent_to_world", consumer_of_record=False),),
    )
    adapter = EnvironmentCouplingAdapter(real_engine=None, contract=contract, sources=bundle)
    env = adapter.advance_step()
    assert env["current_year"] == 1
    assert env["flood_depth_ft"] == 4.0
    assert env["agent_ground_up_loss"] > 0.0


# --------------------------------------------------------------------------
# Package-import registration side effects
# --------------------------------------------------------------------------
def test_import_registers_validators_and_pack():
    importlib.import_module("examples.cat_model")
    from broker.components.governance.validator_registry import ValidatorRegistry
    from broker.domains.registry import DomainPackRegistry

    checks = ValidatorRegistry.get_checks("cat_model", "physical")
    assert checks, "cat_model physical checks must register on import"
    assert DomainPackRegistry.get("cat_model") is not None
    # the pack defaults coupling OFF
    assert DomainPackRegistry.get("cat_model").coupling_enabled_default() is False
