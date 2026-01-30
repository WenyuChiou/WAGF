"""
Governance Validators - Rule evaluation by category.

Validators:
- PersonalValidator: Financial + Cognitive constraints
- SocialValidator: Neighbor influence + Community norms (WARNING only)
- ThinkingValidator: PMT constructs + Reasoning coherence
- PhysicalValidator: State preconditions + Immutability
- TypeValidator: Per-agent-type validation (skill eligibility, type rules)

Domain-specific built-in checks are injected via ``builtin_checks``
constructor parameter on each validator.  When ``builtin_checks=None``
(default), flood-domain checks are used for backward compatibility.
Pass ``builtin_checks=[]`` to disable all built-in checks.

Use ``validate_all(domain=...)`` to select domain:
- ``"flood"`` (default): Flood-domain built-in checks (backward compat)
- ``"irrigation"``: Irrigation-domain checks (water rights, curtailment, drought)
- ``None``: YAML rules only — no hardcoded built-in checks
"""
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from broker.interfaces.skill_types import ValidationResult

if TYPE_CHECKING:
    from broker.governance.rule_types import GovernanceRule

from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck
from broker.validators.governance.personal_validator import PersonalValidator
from broker.validators.governance.social_validator import SocialValidator
from broker.validators.governance.thinking_validator import ThinkingValidator
from broker.validators.governance.physical_validator import PhysicalValidator
from broker.governance.type_validator import TypeValidator

__all__ = [
    "BaseValidator",
    "BuiltinCheck",
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
    rules: List["GovernanceRule"],
    context: Dict[str, Any],
    agent_type: Optional[str] = None,
    registry: Optional["AgentTypeRegistry"] = None,
    domain: Optional[str] = "flood",
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
        domain: Domain identifier controlling built-in checks.
            - ``"flood"`` (default): Flood-domain built-in checks (backward compat)
            - ``"irrigation"``: Irrigation-domain checks (water rights, drought, compact)
            - ``None``: YAML rules only — no hardcoded built-in checks

    Returns:
        Combined list of ValidationResult from all validators
    """
    from broker.governance.rule_types import GovernanceRule as _GovernanceRule
    if rules and not isinstance(rules[0], _GovernanceRule):
        raise TypeError("rules must be GovernanceRule instances")

    # Domain-specific builtin check injection:
    # - "flood" (default): None → each validator uses _default_builtin_checks()
    # - "irrigation": inject irrigation checks into physical/social, empty for others
    # - None: empty list → YAML rules only
    if domain == "irrigation":
        from broker.validators.governance.irrigation_validators import (
            IRRIGATION_PHYSICAL_CHECKS,
            IRRIGATION_SOCIAL_CHECKS,
        )
        validators = [
            PersonalValidator(builtin_checks=[]),       # No financial/cognitive checks
            PhysicalValidator(builtin_checks=list(IRRIGATION_PHYSICAL_CHECKS)),
            ThinkingValidator(builtin_checks=[]),       # No PMT checks
            SocialValidator(builtin_checks=list(IRRIGATION_SOCIAL_CHECKS)),
        ]
    elif domain is None:
        no_builtins: List[BuiltinCheck] = []
        validators = [
            PersonalValidator(builtin_checks=no_builtins),
            PhysicalValidator(builtin_checks=no_builtins),
            ThinkingValidator(builtin_checks=no_builtins),
            SocialValidator(builtin_checks=no_builtins),
        ]
    else:
        # "flood" or any unrecognized domain → default (flood backward compat)
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
