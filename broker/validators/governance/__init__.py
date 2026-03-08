"""
Governance Validators - Rule evaluation by category.

Validators:
- PersonalValidator: Financial + Cognitive constraints
- SocialValidator: Neighbor influence + Community norms (WARNING only)
- ThinkingValidator: construct-action coherence
- PhysicalValidator: State preconditions + Immutability
- SemanticGroundingValidator: Reasoning grounding + Factual consistency
- TypeValidator: Per-agent-type validation (skill eligibility, type rules)

Domain-specific builtin checks are injected by domain adapters. The generic
governance entrypoint should not import example packages directly.
"""
import os
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from broker.interfaces.skill_types import ValidationResult
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck
from broker.validators.governance.personal_validator import PersonalValidator
from broker.validators.governance.social_validator import SocialValidator
from broker.validators.governance.thinking_validator import ThinkingValidator
from broker.validators.governance.physical_validator import PhysicalValidator
from broker.validators.governance.semantic_validator import SemanticGroundingValidator
from broker.governance.type_validator import TypeValidator
from broker.domains.water.validator_bundles import build_domain_validators

if TYPE_CHECKING:
    from broker.governance.rule_types import GovernanceRule

__all__ = [
    "BaseValidator",
    "BuiltinCheck",
    "PersonalValidator",
    "SocialValidator",
    "ThinkingValidator",
    "PhysicalValidator",
    "SemanticGroundingValidator",
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
    domain: Optional[str] = None,
) -> List[ValidationResult]:
    """
    Run all validators against a skill proposal.

    Args:
        skill_name: Proposed skill name
        rules: List of all governance rules
        context: Dictionary with reasoning, state, social_context
        agent_type: Optional agent type ID for per-type validation.
        registry: Optional AgentTypeRegistry instance for type validation.
        domain: Domain identifier controlling built-in checks.

    Returns:
        Combined list of ValidationResult from all validators
    """
    from broker.governance.rule_types import GovernanceRule as _GovernanceRule

    if rules and not isinstance(rules[0], _GovernanceRule):
        raise TypeError("rules must be GovernanceRule instances")

    resolved_domain = (domain or "").strip().lower() or (
        str(context.get("domain", "")).strip().lower()
        or str(context.get("env_state", {}).get("domain", "")).strip().lower()
        or str(context.get("agent_state", {}).get("env_state", {}).get("domain", "")).strip().lower()
        or str(os.environ.get("GOVERNANCE_DOMAIN", "")).strip().lower()
        or None
    )

    validators = build_domain_validators(resolved_domain)

    all_results = []
    for validator in validators:
        results = validator.validate(skill_name, rules, context)
        all_results.extend(results)

    if agent_type:
        type_validator = TypeValidator(registry)
        type_results = type_validator.validate(skill_name, agent_type, context)
        all_results.extend(type_results)

    return all_results


def get_rule_breakdown(results: List[ValidationResult]) -> Dict[str, int]:
    """Get rule hit counts by category for audit logging."""
    breakdown = {
        "personal": 0,
        "social": 0,
        "thinking": 0,
        "physical": 0,
        "semantic": 0,
    }

    for result in results:
        category = result.metadata.get("category", "")
        if category in breakdown:
            breakdown[category] += 1

    return breakdown
