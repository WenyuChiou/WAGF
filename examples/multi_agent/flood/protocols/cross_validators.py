"""
Flood-domain validation rules for CrossAgentValidator.

These are pluggable domain rules injected via the ``domain_rules``
parameter of ``CrossAgentValidator.__init__()``.

Each rule is a callable:
    (artifacts: Dict, prev_artifacts: Optional[Dict]) -> Optional[ValidationResult]

Usage:
    from examples.multi_agent.flood.ma_cross_validators import FLOOD_VALIDATION_RULES
    validator = CrossAgentValidator(domain_rules=FLOOD_VALIDATION_RULES)

Reference: Task-058B (Cross-Agent Validation & Arbitration)
"""
from typing import Dict, Optional

from broker.validators.governance.cross_agent_validator import (
    CrossValidationResult,
    ValidationLevel,
)


def flood_perverse_incentive_check(
    artifacts: Dict, prev_artifacts: Optional[Dict],
) -> Optional[CrossValidationResult]:
    """Check if government and insurance actions cancel each other out.

    WARN conditions:
    - Govt increases subsidy AND insurance increases premium (cancellation)
    - Govt decreases subsidy while loss_ratio > 0.7 (abandoning vulnerable)
    """
    policy = artifacts.get("policy")
    market = artifacts.get("market")
    if policy is None or market is None:
        return None

    if prev_artifacts is None:
        return None
    prev_policy = prev_artifacts.get("policy")
    prev_market = prev_artifacts.get("market")
    if prev_policy is None or prev_market is None:
        return None

    # Condition 1: subsidy up AND premium up
    if (policy.subsidy_rate > prev_policy.subsidy_rate
            and market.premium_rate > prev_market.premium_rate):
        return CrossValidationResult(
            is_valid=False,
            level=ValidationLevel.WARNING,
            rule_id="PERVERSE_INCENTIVE_CANCELLATION",
            message=f"Policy cancellation: subsidy increased to {policy.subsidy_rate:.2f} "
                    f"while premium increased to {market.premium_rate:.2f}.",
        )

    # Condition 2: subsidy down while loss_ratio > 0.7
    if (policy.subsidy_rate < prev_policy.subsidy_rate
            and market.loss_ratio > 0.7):
        return CrossValidationResult(
            is_valid=False,
            level=ValidationLevel.WARNING,
            rule_id="PERVERSE_INCENTIVE_ABANDONMENT",
            message=f"Abandonment risk: subsidy decreased to {policy.subsidy_rate:.2f} "
                    f"while loss ratio is high ({market.loss_ratio:.2f}).",
        )

    return None


def flood_budget_coherence_check(
    artifacts: Dict, prev_artifacts: Optional[Dict],
    avg_subsidy_cost: float = 5000.0,
) -> Optional[CrossValidationResult]:
    """Check if government budget can cover expected subsidy demand.

    ERROR if budget_remaining < household_count * subsidy_rate * avg_cost
    """
    policy = artifacts.get("policy")
    intentions = artifacts.get("intentions", [])
    if policy is None:
        return None
    if policy.budget_remaining is None:
        return None

    household_count = len(intentions)
    expected_demand = household_count * policy.subsidy_rate * avg_subsidy_cost

    if policy.budget_remaining < expected_demand:
        return CrossValidationResult(
            is_valid=False,
            level=ValidationLevel.ERROR,
            rule_id="BUDGET_SHORTFALL",
            message=f"Budget shortfall: remaining {policy.budget_remaining:.2f} "
                    f"< expected demand {expected_demand:.2f} "
                    f"({household_count} households, "
                    f"{policy.subsidy_rate:.0%} rate, avg ${avg_subsidy_cost:.0f}).",
        )

    return None


# Convenience list for injection into CrossAgentValidator
FLOOD_VALIDATION_RULES = [
    flood_perverse_incentive_check,
    flood_budget_coherence_check,
]
