"""
Governance Validators - Rule evaluation by category.

STATUS: this five-category stack (reached through ``validate_all`` /
``build_domain_validators`` below) is available architecture, not the
production default. As of v0.6.0 it has no non-test production call
sites: production experiment construction
(``broker/core/experiment_builder.py``) wires a single
``AgentValidator`` instance (``broker/validators/agent/agent_validator.py``),
whose own ``validate_thinking`` / ``_validate_internal`` methods run the
YAML rule engine (``identity_rules`` / ``thinking_rules`` / ...) directly —
they never call into ``PersonalValidator`` / ``SocialValidator`` /
``PhysicalValidator`` / ``SemanticGroundingValidator`` /
``ThinkingValidator`` below. The one exception is the opt-in, default-OFF
``domain_physical_dispatch`` path in ``skill_broker_engine.py``, which
calls ``PhysicalValidator`` directly (not through ``validate_all``) and
only when a run explicitly sets
``global_config.governance.dispatch_domain_physical``.

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

# Phase 6T-F prep (2026-05-27): auto-register the generic-framework
# metadata (utility / financial / narrative_diffusion) at module
# import time. Closes a Phase-6P-A-class leak — previously utility +
# financial lived in broker/domains/water/thinking_checks.py even
# though their construct vocabulary is genuinely cross-domain. Now
# they're available to ANY domain pack without needing to import
# from the water namespace.
from . import frameworks  # noqa: F401

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

    Not on the default production path — see the module STATUS note above.
    Production runs validate through ``AgentValidator`` instead.

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

    # Phase 6P-A (2026-05-25): runtime cross-namespace coupling closed.
    # The dispatcher now lives at a generic address —
    # `broker.components.governance.domain_validator_dispatch` — and its
    # body has been registry-driven since Phase 6C-v2. The function-local
    # import is preserved to keep `validate_all`'s module-load surface
    # narrow (no eager import of all validator subclasses).
    from broker.components.governance.domain_validator_dispatch import (
        build_domain_validators,
    )

    # Phase 6T-B (2026-05-27): plumb agent_type to the dispatcher so
    # GovernancePack.framework_for_agent_type can route household
    # decisions to PMT, government to utility, insurance to financial.
    # Pre-6T-B the agent_type was accepted by validate_all but dropped
    # before the dispatcher call — closing engineering-audit Y6.
    validators = build_domain_validators(resolved_domain, agent_type=agent_type)

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
