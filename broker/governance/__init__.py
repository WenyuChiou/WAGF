"""
Governance Module - Extensible rule-based validation system.

Categories:
- Personal Rules: Financial constraints, cognitive constraints
- Social Rules: Neighbor influence, community norms (WARNING only)
- Thinking Rules: PMT construct validation, reasoning coherence
- Physical Rules: State preconditions, action immutability
- Type Rules: Per-agent-type skill eligibility and validation

Usage:
    from broker.governance import validate_all, get_rule_breakdown, GovernanceRule

    rules = [GovernanceRule.from_dict(r) for r in yaml_rules]
    results = validate_all(skill_name, rules, context)
    breakdown = get_rule_breakdown(results)

    # With agent type validation:
    from broker.governance import validate_all, TypeValidator
    results = validate_all(
        skill_name, rules, context,
        agent_type="household_owner",
        registry=my_registry
    )
"""
from .rule_types import (
    GovernanceRule,
    RuleCondition,
    RuleCategory,
    RuleLevel,
    ConditionType,
    categorize_rule,
)
from .type_validator import TypeValidator

__all__ = [
    # Rule Types
    "GovernanceRule",
    "RuleCondition",
    "RuleCategory",
    "RuleLevel",
    "ConditionType",
    "categorize_rule",
    # Validators
    "BaseValidator",
    "PersonalValidator",
    "SocialValidator",
    "ThinkingValidator",
    "PhysicalValidator",
    "TypeValidator",
    # Convenience functions (lazy imports)
    "validate_all",
    "get_rule_breakdown",
]


def validate_all(*args, **kwargs):
    from broker.validators.governance import validate_all as _validate_all
    return _validate_all(*args, **kwargs)


def get_rule_breakdown(*args, **kwargs):
    from broker.validators.governance import get_rule_breakdown as _get_rule_breakdown
    return _get_rule_breakdown(*args, **kwargs)


_VALIDATOR_EXPORTS = {
    "BaseValidator",
    "PersonalValidator",
    "SocialValidator",
    "ThinkingValidator",
    "PhysicalValidator",
}


def __getattr__(name):
    if name in _VALIDATOR_EXPORTS:
        from broker.validators import governance as _gov
        return getattr(_gov, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
