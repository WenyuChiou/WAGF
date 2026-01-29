"""
Physical Validator - State preconditions and action immutability.

Validates:
- State preconditions (already elevated, already relocated)
- Renter restrictions (cannot modify property)
- Action immutability (irreversible decisions)
"""
from typing import List, Dict, Any
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import BaseValidator


class PhysicalValidator(BaseValidator):
    """
    Validates physical state: preconditions and immutable states.

    Examples:
    - Cannot elevate if already elevated
    - Cannot relocate if already relocated
    - Renters cannot modify property (elevate, buyout)
    """

    @property
    def category(self) -> str:
        return "physical"

    def validate(
        self,
        skill_name: str,
        rules: List[GovernanceRule],
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate physical rules with state precondition checks.

        Args:
            skill_name: Proposed skill name
            rules: List of governance rules
            context: Must include 'state' with boolean flags

        Returns:
            List of ValidationResult objects
        """
        results = super().validate(skill_name, rules, context)
        state = context.get("state", {})

        # Built-in: Cannot elevate if already elevated
        if skill_name == "elevate_house" and state.get("elevated", False):
            results.append(ValidationResult(
                valid=False,
                validator_name="PhysicalValidator",
                errors=["House is already elevated - cannot elevate again"],
                warnings=[],
                metadata={
                    "rule_id": "builtin_already_elevated",
                    "category": "physical",
                    "subcategory": "state",
                    "current_state": "elevated"
                }
            ))

        # Built-in: Cannot do anything meaningful after relocation
        if state.get("relocated", False):
            restricted_after_relocation = {
                "relocate", "elevate_house", "buy_insurance", "buyout"
            }
            if skill_name in restricted_after_relocation:
                results.append(ValidationResult(
                    valid=False,
                    validator_name="PhysicalValidator",
                    errors=[f"Household has relocated - '{skill_name}' is no longer applicable"],
                    warnings=[],
                    metadata={
                        "rule_id": "builtin_already_relocated",
                        "category": "physical",
                        "subcategory": "state",
                        "current_state": "relocated"
                    }
                ))

        # Built-in: Renter restrictions
        is_renter = state.get("tenure", "Owner").lower() == "renter"
        if is_renter:
            owner_only_actions = {"elevate_house", "buyout"}
            if skill_name in owner_only_actions:
                results.append(ValidationResult(
                    valid=False,
                    validator_name="PhysicalValidator",
                    errors=[f"Renters cannot perform '{skill_name}' - property modification requires ownership"],
                    warnings=[],
                    metadata={
                        "rule_id": "builtin_renter_restriction",
                        "category": "physical",
                        "subcategory": "state",
                        "tenure": "renter",
                        "restricted_action": skill_name
                    }
                ))

        return results
