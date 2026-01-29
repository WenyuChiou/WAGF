"""
Personal Validator - Financial and Cognitive constraints.

Validates:
- Financial affordability (savings vs costs, income limits)
- Cognitive capability (extreme states blocking options)
"""
from typing import List, Dict, Any
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import BaseValidator


class PersonalValidator(BaseValidator):
    """
    Validates personal constraints: financial affordability and cognitive capability.

    Examples:
    - Cannot elevate if savings < elevation_cost * (1 - subsidy_rate)
    - Low coping capacity blocks complex actions
    """

    @property
    def category(self) -> str:
        return "personal"

    def validate(
        self,
        skill_name: str,
        rules: List[GovernanceRule],
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate personal rules with enhanced financial checks.

        Args:
            skill_name: Proposed skill name
            rules: List of governance rules
            context: Must include 'state' with financial fields

        Returns:
            List of ValidationResult objects
        """
        results = super().validate(skill_name, rules, context)

        # Additional built-in financial checks (if no explicit rules cover them)
        state = context.get("state", {})

        # Check elevation affordability
        if skill_name == "elevate_house" and not self._has_rule_for(rules, "elevation_affordability"):
            savings = state.get("savings", 0)
            elevation_cost = state.get("elevation_cost", 50000)
            subsidy_rate = state.get("subsidy_rate", 0.0)
            effective_cost = elevation_cost * (1 - subsidy_rate)

            if savings < effective_cost:
                results.append(ValidationResult(
                    valid=False,
                    validator_name="PersonalValidator",
                    errors=[f"Insufficient funds: savings ${savings:.0f} < cost ${effective_cost:.0f}"],
                    warnings=[],
                    metadata={
                        "rule_id": "builtin_elevation_affordability",
                        "category": "personal",
                        "subcategory": "financial",
                        "savings": savings,
                        "effective_cost": effective_cost
                    }
                ))

        return results

    def _has_rule_for(self, rules: List[GovernanceRule], rule_id_prefix: str) -> bool:
        """Check if a rule covering this constraint already exists."""
        return any(r.id.startswith(rule_id_prefix) for r in rules if r.category == "personal")
