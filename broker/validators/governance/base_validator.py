"""
Base Validator - Abstract base class for governance validators.

All category validators inherit from this class.
Supports dynamic template interpolation in rule messages via RetryMessageFormatter.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from broker.utils.retry_formatter import RetryMessageFormatter


class BaseValidator(ABC):
    """
    Abstract base class for governance validators.

    Each validator is responsible for evaluating rules in a specific category.
    Supports dynamic template interpolation in rule messages using {var.path} syntax.

    Example YAML rule with template:
        - id: elevation_threat_low
          message: "Elevation blocked: Your TP={context.TP_LABEL} is too low."
    """

    # Shared formatter instance (lenient mode - keeps placeholders if missing)
    _message_formatter = RetryMessageFormatter(strict_mode=False)

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

                # Format message with template interpolation
                formatted_message = self._format_rule_message(rule, skill_name, context)

                result = ValidationResult(
                    valid=not is_error,
                    validator_name=self.__class__.__name__,
                    errors=[formatted_message] if is_error else [],
                    warnings=[formatted_message] if not is_error else [],
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

    def _format_rule_message(
        self,
        rule: GovernanceRule,
        skill_name: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Format rule message with dynamic variable interpolation.

        Supports {var.path} syntax for template variables:
            - {context.TP_LABEL}: Current threat appraisal
            - {context.CP_LABEL}: Current coping appraisal
            - {context.decision}: Proposed decision
            - {rule.id}: Rule identifier
            - {rule.blocked_skills}: List of blocked skills

        Args:
            rule: The governance rule that triggered
            skill_name: The skill that was proposed
            context: Full context dictionary

        Returns:
            Formatted message string
        """
        if not rule.message:
            return f"[Rule: {rule.id}] Validation failed for skill: {skill_name}"

        # Build template context for interpolation
        reasoning = context.get("reasoning", {})
        template_context = {
            "context": {
                "TP_LABEL": reasoning.get("TP_LABEL", reasoning.get("threat_appraisal", "N/A")),
                "CP_LABEL": reasoning.get("CP_LABEL", reasoning.get("coping_appraisal", "N/A")),
                "decision": skill_name,
                "agent_id": context.get("agent_id", "unknown"),
                **reasoning  # Include all reasoning fields
            },
            "rule": {
                "id": rule.id,
                "blocked_skills": rule.blocked_skills or [],
                "level": rule.level,
                "category": rule.category,
                "subcategory": getattr(rule, "subcategory", None),
            }
        }

        return self._message_formatter.format(rule.message, template_context)

    def _format_intervention_message(self, rule: GovernanceRule, context: Dict[str, Any]) -> str:
        """
        Format a human-readable intervention message.

        This method also supports template interpolation for backwards compatibility.
        """
        base_msg = rule.get_intervention_message()

        # Try template interpolation first
        reasoning = context.get("reasoning", {})
        template_context = {
            "context": {
                "TP_LABEL": reasoning.get("TP_LABEL", reasoning.get("threat_appraisal", "N/A")),
                "CP_LABEL": reasoning.get("CP_LABEL", reasoning.get("coping_appraisal", "N/A")),
                **reasoning
            },
            "rule": {"id": rule.id}
        }
        formatted_msg = self._message_formatter.format(base_msg, template_context)

        # Add context details if available (legacy behavior)
        if rule.construct and "{" not in base_msg:  # Only append if not using templates
            actual_value = reasoning.get(rule.construct, "unknown")
            return f"{formatted_msg} (Actual {rule.construct}: {actual_value})"

        return formatted_msg
