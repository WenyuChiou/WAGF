"""
Flood-domain saga transaction definitions.

Defines multi-step workflows with compensatory rollback:
- SUBSIDY_APPLICATION_SAGA: Household applies for government subsidy
- INSURANCE_CLAIM_SAGA: Household files insurance claim after flood damage
- ELEVATION_GRANT_SAGA: Government approves and funds house elevation

Usage:
    from examples.multi_agent.ma_saga_definitions import FLOOD_SAGA_DEFINITIONS
    for defn in FLOOD_SAGA_DEFINITIONS:
        coordinator.register_saga(defn)

Reference: Task-058D (Saga Transaction Coordinator)
Literature: SagaLLM (Chang & Geng, 2025) — transaction guarantees
"""
from typing import Any, Dict

from broker.components.saga_coordinator import SagaStep, SagaDefinition


# ---------------------------------------------------------------------------
# Subsidy Application Saga
# ---------------------------------------------------------------------------

def _household_applies_subsidy(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Step 1: Household submits subsidy application."""
    ctx["application_submitted"] = True
    ctx["application_agent"] = ctx.get("household_id", "unknown")
    return ctx


def _cancel_subsidy_application(ctx: Dict[str, Any]) -> None:
    """Compensate: Cancel subsidy application."""
    ctx["application_submitted"] = False
    ctx.pop("application_agent", None)


def _government_reviews_subsidy(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Step 2: Government reviews and approves/denies."""
    budget = ctx.get("budget_remaining", 0)
    cost = ctx.get("subsidy_cost", 5000)
    if budget < cost:
        raise ValueError(f"Insufficient budget: {budget} < {cost}")
    ctx["subsidy_approved"] = True
    ctx["budget_remaining"] = budget - cost
    return ctx


def _restore_budget(ctx: Dict[str, Any]) -> None:
    """Compensate: Restore budget after failed subsidy."""
    cost = ctx.get("subsidy_cost", 5000)
    ctx["budget_remaining"] = ctx.get("budget_remaining", 0) + cost
    ctx["subsidy_approved"] = False


def _household_receives_subsidy(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Step 3: Household receives subsidy funds."""
    ctx["subsidy_received"] = True
    return ctx


def _revoke_subsidy(ctx: Dict[str, Any]) -> None:
    """Compensate: Revoke subsidy from household."""
    ctx["subsidy_received"] = False


SUBSIDY_APPLICATION_SAGA = SagaDefinition(
    name="subsidy_application",
    steps=[
        SagaStep("household_applies", _household_applies_subsidy, _cancel_subsidy_application),
        SagaStep("government_reviews", _government_reviews_subsidy, _restore_budget),
        SagaStep("household_receives", _household_receives_subsidy, _revoke_subsidy),
    ],
    timeout_steps=3,
)


# ---------------------------------------------------------------------------
# Insurance Claim Saga
# ---------------------------------------------------------------------------

def _household_files_claim(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Step 1: Household files insurance claim."""
    ctx["claim_filed"] = True
    ctx["claim_agent"] = ctx.get("household_id", "unknown")
    return ctx


def _cancel_claim(ctx: Dict[str, Any]) -> None:
    """Compensate: Cancel insurance claim."""
    ctx["claim_filed"] = False


def _insurance_evaluates_claim(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Step 2: Insurance evaluates damage and approves."""
    damage = ctx.get("damage_amount", 0)
    deductible = ctx.get("deductible", 1000)
    if damage <= deductible:
        raise ValueError(f"Damage {damage} below deductible {deductible}")
    ctx["claim_approved"] = True
    ctx["payout_amount"] = damage - deductible
    return ctx


def _deny_claim(ctx: Dict[str, Any]) -> None:
    """Compensate: Deny claim (revert approval)."""
    ctx["claim_approved"] = False
    ctx.pop("payout_amount", None)


def _household_receives_payout(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Step 3: Household receives insurance payout."""
    ctx["payout_received"] = True
    return ctx


def _revoke_payout(ctx: Dict[str, Any]) -> None:
    """Compensate: Revoke payout."""
    ctx["payout_received"] = False


INSURANCE_CLAIM_SAGA = SagaDefinition(
    name="insurance_claim",
    steps=[
        SagaStep("household_files", _household_files_claim, _cancel_claim),
        SagaStep("insurance_evaluates", _insurance_evaluates_claim, _deny_claim),
        SagaStep("household_receives", _household_receives_payout, _revoke_payout),
    ],
    timeout_steps=3,
)


# ---------------------------------------------------------------------------
# Elevation Grant Saga
# ---------------------------------------------------------------------------

def _household_requests_elevation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Step 1: Household requests elevation grant."""
    ctx["elevation_requested"] = True
    return ctx


def _cancel_elevation_request(ctx: Dict[str, Any]) -> None:
    """Compensate: Cancel elevation request."""
    ctx["elevation_requested"] = False


def _government_approves_elevation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Step 2: Government approves and allocates funds."""
    budget = ctx.get("budget_remaining", 0)
    elevation_cost = ctx.get("elevation_cost", 10000)
    if budget < elevation_cost:
        raise ValueError(f"Insufficient budget for elevation: {budget} < {elevation_cost}")
    ctx["elevation_approved"] = True
    ctx["budget_remaining"] = budget - elevation_cost
    return ctx


def _restore_elevation_budget(ctx: Dict[str, Any]) -> None:
    """Compensate: Restore budget after failed elevation."""
    cost = ctx.get("elevation_cost", 10000)
    ctx["budget_remaining"] = ctx.get("budget_remaining", 0) + cost
    ctx["elevation_approved"] = False


def _contractor_elevates_house(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Step 3: Contractor elevates the house."""
    ctx["house_elevated"] = True
    return ctx


def _undo_elevation(ctx: Dict[str, Any]) -> None:
    """Compensate: Mark elevation as not completed."""
    ctx["house_elevated"] = False


ELEVATION_GRANT_SAGA = SagaDefinition(
    name="elevation_grant",
    steps=[
        SagaStep("household_requests", _household_requests_elevation, _cancel_elevation_request),
        SagaStep("government_approves", _government_approves_elevation, _restore_elevation_budget),
        SagaStep("contractor_elevates", _contractor_elevates_house, _undo_elevation),
    ],
    timeout_steps=5,
)


# ---------------------------------------------------------------------------
# Convenience list
# ---------------------------------------------------------------------------

FLOOD_SAGA_DEFINITIONS = [
    SUBSIDY_APPLICATION_SAGA,
    INSURANCE_CLAIM_SAGA,
    ELEVATION_GRANT_SAGA,
]
