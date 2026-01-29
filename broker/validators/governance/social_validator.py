"""
Social Validator - Neighbor influence and Community norms.

IMPORTANT: Social rules are WARNING only, never blocking.
They log social context but do not reject decisions.

Validates:
- Neighbor adaptation pressure (herd behavior observation)
- Community norm deviations (outlier detection)
"""
from typing import List, Dict, Any
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import BaseValidator


class SocialValidator(BaseValidator):
    """
    Validates social context: neighbor influence and community norms.

    IMPORTANT: This validator only produces WARNINGs, never ERRORs.
    Social pressure is logged for audit but does not block decisions.

    Examples:
    - Most neighbors elevated -> log pressure to adapt
    - Agent choosing do_nothing while community adapts -> log deviation
    """

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

        Args:
            skill_name: Proposed skill name
            rules: List of governance rules
            context: Must include 'social_context' with neighbor data

        Returns:
            List of ValidationResult objects (all valid=True for warnings)
        """
        results = []
        social_context = context.get("social_context", {})

        # Filter social rules
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
                        "social_pressure": self._calculate_pressure(social_context)
                    }
                ))

        # Built-in: Log if deviating from majority
        elevated_pct = social_context.get("elevated_neighbor_pct", 0)
        if elevated_pct > 0.5 and skill_name == "do_nothing":
            results.append(ValidationResult(
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
            ))

        return results

    def _calculate_pressure(self, social_context: Dict[str, Any]) -> float:
        """Calculate social pressure score (0-1) based on neighbor actions."""
        elevated = social_context.get("elevated_neighbors", 0)
        relocated = social_context.get("relocated_neighbors", 0)
        total = social_context.get("neighbor_count", 1)

        if total == 0:
            return 0.0

        # Weighted: relocation counts more than elevation
        return min(1.0, (elevated + relocated * 1.5) / total)
