"""Physical governance checks for the multi-agent catastrophe model.

The runner writes policyholder per-agent values into ``BaseAgent.dynamic_state``
in ``pre_year``. ``skill_broker_engine`` then flattens ``context["state"]`` into
the validation context, so ``policyholder_claim_check`` reads
``policy_in_force_self`` and ``own_ground_up_loss`` as top-level keys while also
accepting the explicit ``env_state`` location used by world aggregates.
"""
from __future__ import annotations

from typing import Any, Dict, List

from broker.governance.rule_types import GovernanceRule
from broker.interfaces.skill_types import ValidationResult


def _ctx_get(context: Dict[str, Any], key: str, default: Any = None) -> Any:
    env = context.get("env_state")
    if isinstance(env, dict) and env.get(key) is not None:
        return env[key]
    if context.get(key) is not None:
        return context[key]
    return default


def _missing_result(validator: str, skill_name: str, missing: List[str]) -> List[ValidationResult]:
    return [
        ValidationResult(
            valid=False,
            validator_name=validator,
            errors=[
                f"{skill_name}: required world-state field(s) absent from the "
                f"validation context: {missing}. Cannot verify the physical "
                "constraint; check the runner dynamic_state/env wiring."
            ],
            metadata={
                "category": "physical",
                "rule_id": "missing_world_state",
                "deterministic": True,
                "missing": list(missing),
            },
        )
    ]


def policyholder_claim_check(
    skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
) -> List[ValidationResult]:
    """Block ``file_claim`` unless the flattened agent state says the policy is
    in force and the policyholder has positive own ground-up loss.

    Reads ``policy_in_force_self`` and ``own_ground_up_loss`` from the
    validation context. Those keys originate in ``BaseAgent.dynamic_state`` and
    are flattened by ``skill_broker_engine`` before registry checks run.
    """
    if skill_name != "file_claim":
        return []

    missing: List[str] = []

    def req(key: str) -> Any:
        value = _ctx_get(context, key, None)
        if value is None:
            missing.append(key)
        return value

    in_force = req("policy_in_force_self")
    own_loss = req("own_ground_up_loss")
    if missing:
        return _missing_result("policyholder_claim_check", skill_name, missing)

    if not bool(in_force):
        return [
            ValidationResult(
                valid=False,
                validator_name="policyholder_claim_check",
                errors=["file_claim is invalid: this policy is not in force."],
                metadata={
                    "category": "physical",
                    "rule_id": "policy_not_in_force",
                    "deterministic": True,
                },
            )
        ]
    if float(own_loss) <= 0.0:
        return [
            ValidationResult(
                valid=False,
                validator_name="policyholder_claim_check",
                errors=["file_claim is invalid: this policyholder has no loss."],
                metadata={
                    "category": "physical",
                    "rule_id": "no_loss_to_claim",
                    "deterministic": True,
                },
            )
        ]
    return []


def insurer_settlement_check(
    skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
) -> List[ValidationResult]:
    """Block ``settle_full`` when aggregate owed claims exceed the pool.

    DEPENDENCY (review W3): ``total_claims_owed`` is populated live by the
    runner's ``on_post_step`` hook as policyholders file; this check is only
    meaningful when the insurer phase runs AFTER the policyholder phase
    (``with_phase_order``). With no claims filed yet, ``settle_full`` passes
    trivially — phase ordering, not this validator, is the protection
    against premature settlement.
    """
    if skill_name != "settle_full":
        return []

    missing: List[str] = []

    def req(key: str) -> Any:
        value = _ctx_get(context, key, None)
        if value is None:
            missing.append(key)
        return value

    total_owed = req("total_claims_owed")
    pool = req("pool_budget_remaining")
    if missing:
        return _missing_result("insurer_settlement_check", skill_name, missing)

    if float(total_owed) > float(pool):
        return [
            ValidationResult(
                valid=False,
                validator_name="insurer_settlement_check",
                errors=[
                    f"settle_full is invalid: claims owe {float(total_owed):.2f} "
                    f"but the pool has {float(pool):.2f}."
                ],
                metadata={
                    "category": "physical",
                    "rule_id": "pool_insolvent_aggregate",
                    "deterministic": True,
                },
            )
        ]
    return []


def government_relief_check(
    skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
) -> List[ValidationResult]:
    """Block relief funding after the government budget is exhausted."""
    if skill_name != "fund_shortfall_relief":
        return []

    budget = _ctx_get(context, "gov_budget_remaining", None)
    if budget is None:
        return _missing_result("government_relief_check", skill_name, ["gov_budget_remaining"])

    if float(budget) <= 0.0:
        return [
            ValidationResult(
                valid=False,
                validator_name="government_relief_check",
                errors=["fund_shortfall_relief is invalid: government budget is exhausted."],
                metadata={
                    "category": "physical",
                    "rule_id": "gov_budget_exhausted",
                    "deterministic": True,
                },
            )
        ]
    return []


MA_CAT_PHYSICAL_CHECKS = (
    policyholder_claim_check,
    insurer_settlement_check,
    government_relief_check,
)

# Registration lives in examples/cat_model/__init__.py (review C2: one
# registration site for both the single-agent and MA domains; importing
# this module triggers the package __init__, so the registration still
# happens for any consumer).


__all__ = [
    "policyholder_claim_check",
    "insurer_settlement_check",
    "government_relief_check",
    "MA_CAT_PHYSICAL_CHECKS",
]
