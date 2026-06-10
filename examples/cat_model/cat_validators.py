"""Catastrophe-model world-mutation governance checks (Phase 6V).

THE NOVELTY HOOK, made concrete: governance enforced on a WORLD-MUTATING action
(an insurer payout that debits the shared pool / hits the financial model)
*before* it commits. Implemented as a ``BuiltinCheck`` physical-slot check —
signature ``(skill_name, rules, context) -> List[ValidationResult]`` — so it runs
INSIDE the existing governance retry loop (a ``valid=False`` result re-prompts
the agent; verified at broker/core/_retry_loop.py). It is NOT placed in the
adapter's ``execute_skill`` (which runs after the retry loop has closed APPROVED,
where a veto would silently drop the action with no re-prompt).

Registered with ``ValidatorRegistry`` (slot ``physical``) in this package's
``__init__.py`` — no edit to broker/ source code.

The governed quantity (the payout decision) is a DISCRETE choice
(approve_payout vs deny_payout) known at proposal time, so it satisfies the
proposal-time-governability constraint (avoids the execution-time-sampling risk
R-1 of a continuously-sampled magnitude).
"""
from __future__ import annotations

from typing import Any, Dict, List

from broker.governance.rule_types import GovernanceRule
from broker.interfaces.skill_types import ValidationResult


def _env_get(context: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Read a world-state field from the validation context. The broker exposes
    world state both as ``context["env_state"]`` and flattened at top level;
    read defensively, preferring the explicit env_state."""
    env = context.get("env_state")
    if isinstance(env, dict) and env.get(key) is not None:
        return env[key]
    if context.get(key) is not None:
        return context[key]
    return default


def insurer_payout_solvency_check(
    skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
) -> List[ValidationResult]:
    """Block ``approve_payout`` when it would be physically/financially invalid:
      * the policy was not in force before the event (can't pay a lapsed claim), or
      * the owed amount would overdraw the shared pool (mass-balance violation).
    On ERROR the broker re-prompts; the insurer can re-decide (e.g. deny_payout)."""
    if skill_name != "approve_payout":
        return []

    # FAIL-SAFE on missing world state. A governance check must NEVER approve a
    # world-mutating payout on ABSENT data: silent-zeroing a missing field would
    # either block every valid payout (pool->0) or pass an insolvent one
    # (owed->0). Missing required fields therefore BLOCK (ERROR -> re-prompt),
    # surfacing the coupling-pipeline wiring bug in the audit trace rather than
    # corrupting the loss aggregate silently.
    missing: List[str] = []

    def _req(key: str) -> Any:
        val = _env_get(context, key, None)
        if val is None:
            missing.append(key)
        return val

    in_force = _req("policy_in_force_before_event")
    ground_up = _req("agent_ground_up_loss")
    deductible = _req("policy_deductible")
    pool = _req("pool_budget_remaining")
    limit = _env_get(context, "policy_limit", float("inf"))  # unbounded default is safe

    if missing:
        return [
            ValidationResult(
                valid=False,
                validator_name="insurer_payout_solvency_check",
                errors=[
                    "approve_payout: required world-state field(s) absent from the "
                    f"validation context: {missing}. Cannot verify claim eligibility "
                    "or pool solvency — check the coupling pipeline wiring."
                ],
                metadata={"category": "physical", "rule_id": "missing_world_state",
                          "deterministic": True, "missing": list(missing)},
            )
        ]

    if not bool(in_force):
        return [
            ValidationResult(
                valid=False,
                validator_name="insurer_payout_solvency_check",
                errors=[
                    "approve_payout is invalid: the policy was not in force before "
                    "the event. Deny the claim or correct the policy state."
                ],
                metadata={"category": "physical", "rule_id": "policy_not_in_force",
                          "deterministic": True},
            )
        ]

    owed = min(max(0.0, float(ground_up) - float(deductible)), float(limit))
    pool_f = float(pool)
    if owed > pool_f:
        return [
            ValidationResult(
                valid=False,
                validator_name="insurer_payout_solvency_check",
                errors=[
                    f"approve_payout owes {owed:.0f} but the pool has only "
                    f"{pool_f:.0f} remaining — paying it would overdraw the pool. "
                    f"Deny the claim or settle pro-rata via the backstop."
                ],
                metadata={
                    "category": "physical",
                    "rule_id": "pool_insolvent",
                    "deterministic": True,
                    "owed": owed,
                    "pool": pool_f,
                },
            )
        ]
    return []


# Registry tuple consumed by ValidatorRegistry (see __init__.py)
CAT_MODEL_PHYSICAL_CHECKS = (insurer_payout_solvency_check,)

__all__ = ["insurer_payout_solvency_check", "CAT_MODEL_PHYSICAL_CHECKS"]
