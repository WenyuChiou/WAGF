"""
Base Validator - Abstract base class for governance validators.

All category validators inherit from this class.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule


class BaseValidator(ABC):
    """
    Abstract base class for governance validators.

    Each validator is responsible for evaluating rules in a specific category.
    """

    @property
    @abstractmethod
    def category(self) -> str:
        """Return the category this validator handles."""
        pass

    def validate(
        self,
        skill_name: str,
        rules: List[GovernanceRule],
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate a skill proposal against rules.

        Args:
            skill_name: Proposed skill name
            rules: List of governance rules to check
            context: Dictionary with reasoning, state, social_context

        Returns:
            List of ValidationResult objects
        """
        results = []

        # Filter rules for this category
        category_rules = [r for r in rules if r.category == self.category]

        for rule in category_rules:
            if rule.evaluate(skill_name, context):
                # Rule triggered - create result based on level
                is_error = rule.level == "ERROR"
                result = ValidationResult(
                    valid=not is_error,
                    validator_name=self.__class__.__name__,
                    errors=[rule.message] if is_error else [],
                    warnings=[rule.message] if not is_error else [],
                    metadata={
                        "rule_id": rule.id,
                        "category": rule.category,
                        "subcategory": rule.subcategory,
                        "blocked_skill": skill_name,
                        "level": rule.level
                    }
                )
                results.append(result)

        return results

    def _format_intervention_message(self, rule: GovernanceRule, context: Dict[str, Any]) -> str:
        """Format a human-readable intervention message."""
        base_msg = rule.get_intervention_message()

        # Add context details if available
        if rule.construct:
            reasoning = context.get("reasoning", {})
            actual_value = reasoning.get(rule.construct, "unknown")
            return f"{base_msg} (Actual {rule.construct}: {actual_value})"

        return base_msg
