"""
Social Validator - Neighbor influence and Community norms.

IMPORTANT: Social rules are WARNING only, never blocking.
They log social context but do not reject decisions.

Validates:
- Neighbor adaptation pressure (herd behavior observation)
- Community norm deviations (outlier detection)

Domain-specific built-in checks (e.g. flood neighbor elevation %) are
injected via ``builtin_checks``.  When *None*, flood-domain defaults are
used for backward compatibility.
"""
from typing import List, Dict, Any, Optional
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck


# ---------------------------------------------------------------------------
# Flood-domain built-in checks
# ---------------------------------------------------------------------------

def flood_majority_deviation(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Warn if agent deviates from majority neighbor adaptation (flood domain).

    Fires when > 50% neighbors have elevated but agent chooses do_nothing.
    Always WARNING (valid=True).
    """
    if skill_name != "do_nothing":
        return []
    social_context = context.get("social_context", {})
    elevated_pct = social_context.get("elevated_neighbor_pct", 0)
    if elevated_pct <= 0.5:
        return []
    return [ValidationResult(
        valid=True,
        validator_name="SocialValidator",
        errors=[],
        warnings=[f"Social observation: {elevated_pct*100:.0f}% of neighbors have elevated"],
        metadata={
            "rule_id": "builtin_majority_deviation",
            "category": "social",
            "subcategory": "neighbor",
            "elevated_neighbor_pct": elevated_pct,
            "level": "WARNING"
        }
    )]


# Registry of flood-domain checks for this category
FLOOD_SOCIAL_CHECKS: List[BuiltinCheck] = [flood_majority_deviation]


# ---------------------------------------------------------------------------
# Shared utility
# ---------------------------------------------------------------------------

def calculate_social_pressure(social_context: Dict[str, Any]) -> float:
    """Calculate social pressure score (0-1) based on neighbor actions.

    This helper is domain-agnostic: callers supply the relevant keys.
    For flood domain, uses ``elevated_neighbors`` and ``relocated_neighbors``.
    """
    elevated = social_context.get("elevated_neighbors", 0)
    relocated = social_context.get("relocated_neighbors", 0)
    total = social_context.get("neighbor_count", 1)

    if total == 0:
        return 0.0

    # Weighted: relocation counts more than elevation
    return min(1.0, (elevated + relocated * 1.5) / total)


# ---------------------------------------------------------------------------
# Validator class
# ---------------------------------------------------------------------------

class SocialValidator(BaseValidator):
    """
    Validates social context: neighbor influence and community norms.

    IMPORTANT: This validator only produces WARNINGs, never ERRORs.
    Social pressure is logged for audit but does not block decisions.

    Built-in checks default to flood domain (majority deviation).
    Pass ``builtin_checks=[]`` to disable, or supply domain-specific checks.
    """

    def __init__(self, builtin_checks: Optional[List[BuiltinCheck]] = None):
        super().__init__(builtin_checks=builtin_checks)

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Flood-domain defaults for backward compatibility."""
        return list(FLOOD_SOCIAL_CHECKS)

    @property
    def category(self) -> str:
        return "social"

    def validate(
        self,
        skill_name: str,
        rules: List[GovernanceRule],
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate social rules (WARNING only).

        Social YAML rules are always force-downgraded to WARNING.
        Then domain-specific built-in checks run via the base class.

        Args:
            skill_name: Proposed skill name
            rules: List of governance rules
            context: Must include 'social_context' with neighbor data

        Returns:
            List of ValidationResult objects (all valid=True for warnings)
        """
        results = []
        social_context = context.get("social_context", {})

        # --- YAML-driven social rules (always WARNING) ---
        social_rules = [r for r in rules if r.category == "social"]

        for rule in social_rules:
            if rule.evaluate(skill_name, context):
                # Social rules always produce warnings, never errors
                results.append(ValidationResult(
                    valid=True,  # Always valid - just logging
                    validator_name="SocialValidator",
                    errors=[],
                    warnings=[rule.message],
                    metadata={
                        "rule_id": rule.id,
                        "category": "social",
                        "subcategory": rule.subcategory,
                        "skill_proposed": skill_name,
                        "level": "WARNING",  # Force WARNING level
                        "social_pressure": calculate_social_pressure(social_context)
                    }
                ))

        # --- Domain-specific built-in checks ---
        for check in self._builtin_checks:
            results.extend(check(skill_name, rules, context))

        return results
