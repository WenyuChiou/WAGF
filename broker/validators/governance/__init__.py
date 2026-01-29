"""
Governance Validators - Rule evaluation by category.

Validators:
- PersonalValidator: Financial + Cognitive constraints
- SocialValidator: Neighbor influence + Community norms (WARNING only)
- ThinkingValidator: PMT constructs + Reasoning coherence
- PhysicalValidator: State preconditions + Immutability
- TypeValidator: Per-agent-type validation (skill eligibility, type rules)
"""
from typing import List, Dict, Any, Optional
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule

from broker.validators.governance.base_validator import BaseValidator
from broker.validators.governance.personal_validator import PersonalValidator
from broker.validators.governance.social_validator import SocialValidator
from broker.validators.governance.thinking_validator import ThinkingValidator
from broker.validators.governance.physical_validator import PhysicalValidator
from broker.governance.type_validator import TypeValidator

__all__ = [
    "BaseValidator",
    "PersonalValidator",
    "SocialValidator",
    "ThinkingValidator",
    "PhysicalValidator",
    "TypeValidator",
    "validate_all",
    "get_rule_breakdown",
]


def validate_all(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
    agent_type: Optional[str] = None,
    registry: Optional["AgentTypeRegistry"] = None,
) -> List[ValidationResult]:
    """
    Run all validators against a skill proposal.

    Args:
        skill_name: Proposed skill name
        rules: List of all governance rules
        context: Dictionary with reasoning, state, social_context
        agent_type: Optional agent type ID for per-type validation.
            If provided, TypeValidator will check skill eligibility
            and per-type rules. Defaults to None (no type validation).
        registry: Optional AgentTypeRegistry instance for type validation.
            If agent_type is provided but registry is None, uses the
            default registry.

    Returns:
        Combined list of ValidationResult from all validators
    """
    validators = [
        PersonalValidator(),
        PhysicalValidator(),
        ThinkingValidator(),
        SocialValidator(),
    ]

    all_results = []
    for validator in validators:
        results = validator.validate(skill_name, rules, context)
        all_results.extend(results)

    # Add type-specific validation if agent_type is provided
    if agent_type:
        type_validator = TypeValidator(registry)
        type_results = type_validator.validate(skill_name, agent_type, context)
        all_results.extend(type_results)

    return all_results


def get_rule_breakdown(results: List[ValidationResult]) -> Dict[str, int]:
    """
    Get rule hit counts by category for audit logging.

    Args:
        results: List of validation results

    Returns:
        Dict with counts per category: {personal, social, thinking, physical}
    """
    breakdown = {
        "personal": 0,
        "social": 0,
        "thinking": 0,
        "physical": 0
    }

    for r in results:
        category = r.metadata.get("category", "")
        if category in breakdown:
            breakdown[category] += 1

    return breakdown
