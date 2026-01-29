"""
Type Validator - Per-agent-type validation.

Validates skills based on agent type eligibility and per-type validation rules.
This validator checks:
1. Is the skill eligible for this agent type?
2. Are the per-type validation rules satisfied?

Part of Task-040: SA/MA Unified Architecture (Part 14, P3)
"""
from typing import List, Dict, Any, Optional

from broker.interfaces.skill_types import ValidationResult
from broker.config.agent_types import (
    AgentTypeRegistry,
    AgentTypeDefinition,
    ValidationConfig,
    ValidationRuleRef,
    get_default_registry,
)


class TypeValidator:
    """
    Validates skills based on agent type eligibility.

    This validator checks:
    1. Is the skill eligible for this agent type?
    2. Are the per-type validation rules satisfied?

    Usage:
        validator = TypeValidator(registry)
        results = validator.validate("elevate_house", "household_renter", context)

        # Or with validate_all (integrated):
        results = validate_all(
            skill_name, rules, context,
            agent_type="household_owner",
            registry=registry
        )
    """

    def __init__(self, registry: Optional[AgentTypeRegistry] = None):
        """
        Initialize TypeValidator.

        Args:
            registry: AgentTypeRegistry instance. If None, uses default registry.
        """
        self.registry = registry or get_default_registry()

    def validate(
        self,
        skill_name: str,
        agent_type: str,
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate skill against agent type rules.

        Args:
            skill_name: Proposed skill name
            agent_type: Agent's type ID (e.g., "household", "household_owner")
            context: Full context with state, reasoning, etc.

        Returns:
            List of ValidationResult (empty if valid)
        """
        results = []

        # Get type definition
        defn = self.registry.get(agent_type)
        if not defn:
            return results  # Unknown type, skip validation

        # Check skill eligibility
        if not defn.is_skill_eligible(skill_name):
            results.append(ValidationResult(
                valid=False,
                validator_name="TypeValidator",
                errors=[f"Skill '{skill_name}' not eligible for agent type '{agent_type}'"],
                warnings=[],
                metadata={
                    "rule_id": "type_skill_eligibility",
                    "category": "type",
                    "agent_type": agent_type,
                    "blocked_skill": skill_name,
                    "eligible_skills": defn.eligible_skills,
                }
            ))

        # Apply per-type validation rules
        if defn.validation:
            results.extend(self._apply_type_rules(skill_name, defn, context))

        return results

    def _apply_type_rules(
        self,
        skill_name: str,
        defn: AgentTypeDefinition,
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Apply per-agent-type validation rules from ValidationConfig.

        Args:
            skill_name: Proposed skill name
            defn: AgentTypeDefinition containing validation rules
            context: Full context with state, reasoning, etc.

        Returns:
            List of ValidationResult for triggered rules
        """
        results = []
        validation = defn.validation

        if not validation:
            return results

        # Apply identity rules (state preconditions)
        for rule_ref in validation.identity_rules:
            result = self._evaluate_identity_rule(skill_name, rule_ref, context, defn.type_id)
            if result:
                results.append(result)

        # Apply thinking rules (construct-based)
        for rule_ref in validation.thinking_rules:
            result = self._evaluate_thinking_rule(skill_name, rule_ref, context, defn.type_id)
            if result:
                results.append(result)

        # Apply social rules (warning only)
        for rule_ref in validation.social_rules:
            result = self._evaluate_social_rule(skill_name, rule_ref, context, defn.type_id)
            if result:
                results.append(result)

        # Apply financial rules
        for rule_ref in validation.financial_rules:
            result = self._evaluate_financial_rule(skill_name, rule_ref, context, defn.type_id)
            if result:
                results.append(result)

        return results

    def _evaluate_identity_rule(
        self,
        skill_name: str,
        rule_ref: ValidationRuleRef,
        context: Dict[str, Any],
        agent_type: str
    ) -> Optional[ValidationResult]:
        """
        Evaluate an identity (state precondition) rule.

        Args:
            skill_name: Proposed skill name
            rule_ref: ValidationRuleRef defining the rule
            context: Context with state
            agent_type: Agent type ID for metadata

        Returns:
            ValidationResult if rule triggers, None otherwise
        """
        # Check if this rule applies to the proposed skill
        if skill_name not in rule_ref.blocked_skills:
            return None

        state = context.get("state", {})

        # Check precondition
        if rule_ref.precondition:
            precondition_value = state.get(rule_ref.precondition, False)
            if precondition_value:
                # Precondition met and skill is blocked
                is_error = rule_ref.level == "ERROR"
                message = rule_ref.message or f"Precondition '{rule_ref.precondition}' blocks '{skill_name}'"

                return ValidationResult(
                    valid=not is_error,
                    validator_name="TypeValidator",
                    errors=[message] if is_error else [],
                    warnings=[message] if not is_error else [],
                    metadata={
                        "rule_id": rule_ref.rule_id,
                        "category": "type",
                        "subcategory": "identity",
                        "agent_type": agent_type,
                        "precondition": rule_ref.precondition,
                        "blocked_skill": skill_name,
                        "level": rule_ref.level,
                    }
                )

        return None

    def _evaluate_thinking_rule(
        self,
        skill_name: str,
        rule_ref: ValidationRuleRef,
        context: Dict[str, Any],
        agent_type: str
    ) -> Optional[ValidationResult]:
        """
        Evaluate a thinking (construct-based) rule.

        Args:
            skill_name: Proposed skill name
            rule_ref: ValidationRuleRef defining the rule
            context: Context with reasoning
            agent_type: Agent type ID for metadata

        Returns:
            ValidationResult if rule triggers, None otherwise
        """
        # Check if this rule applies to the proposed skill
        if skill_name not in rule_ref.blocked_skills:
            return None

        reasoning = context.get("reasoning", {})

        # Check construct value
        if rule_ref.construct and rule_ref.when_above:
            construct_value = self._normalize_label(reasoning.get(rule_ref.construct, ""))

            # Check if construct value is in when_above list
            normalized_when_above = [self._normalize_label(v) for v in rule_ref.when_above]

            if construct_value in normalized_when_above:
                # Construct matches and skill is blocked
                is_error = rule_ref.level == "ERROR"
                message = rule_ref.message or f"Construct '{rule_ref.construct}' value '{construct_value}' blocks '{skill_name}'"

                return ValidationResult(
                    valid=not is_error,
                    validator_name="TypeValidator",
                    errors=[message] if is_error else [],
                    warnings=[message] if not is_error else [],
                    metadata={
                        "rule_id": rule_ref.rule_id,
                        "category": "type",
                        "subcategory": "thinking",
                        "agent_type": agent_type,
                        "construct": rule_ref.construct,
                        "construct_value": construct_value,
                        "when_above": rule_ref.when_above,
                        "blocked_skill": skill_name,
                        "level": rule_ref.level,
                    }
                )

        return None

    def _evaluate_social_rule(
        self,
        skill_name: str,
        rule_ref: ValidationRuleRef,
        context: Dict[str, Any],
        agent_type: str
    ) -> Optional[ValidationResult]:
        """
        Evaluate a social rule (WARNING only).

        Social rules produce warnings but do not block actions.

        Args:
            skill_name: Proposed skill name
            rule_ref: ValidationRuleRef defining the rule
            context: Context with social_context
            agent_type: Agent type ID for metadata

        Returns:
            ValidationResult (warning) if rule triggers, None otherwise
        """
        # Check if this rule applies to the proposed skill
        if rule_ref.blocked_skills and skill_name not in rule_ref.blocked_skills:
            return None

        social_context = context.get("social_context", {})

        # Social rules always produce warnings (never errors)
        # Check if any social condition is met
        if rule_ref.precondition:
            # Use precondition field for social metric check
            social_value = social_context.get(rule_ref.precondition, 0)

            # If value is truthy, trigger the warning
            if social_value:
                message = rule_ref.message or f"Social rule triggered for '{skill_name}'"

                return ValidationResult(
                    valid=True,  # Social rules are warnings only
                    validator_name="TypeValidator",
                    errors=[],
                    warnings=[message],
                    metadata={
                        "rule_id": rule_ref.rule_id,
                        "category": "type",
                        "subcategory": "social",
                        "agent_type": agent_type,
                        "level": "WARNING",
                    }
                )

        return None

    def _evaluate_financial_rule(
        self,
        skill_name: str,
        rule_ref: ValidationRuleRef,
        context: Dict[str, Any],
        agent_type: str
    ) -> Optional[ValidationResult]:
        """
        Evaluate a financial rule.

        Args:
            skill_name: Proposed skill name
            rule_ref: ValidationRuleRef defining the rule
            context: Context with state (financial info)
            agent_type: Agent type ID for metadata

        Returns:
            ValidationResult if rule triggers, None otherwise
        """
        # Check if this rule applies to the proposed skill
        if skill_name not in rule_ref.blocked_skills:
            return None

        state = context.get("state", {})

        # Check precondition (financial state)
        if rule_ref.precondition:
            precondition_value = state.get(rule_ref.precondition, False)
            if precondition_value:
                is_error = rule_ref.level == "ERROR"
                message = rule_ref.message or f"Financial constraint '{rule_ref.precondition}' blocks '{skill_name}'"

                return ValidationResult(
                    valid=not is_error,
                    validator_name="TypeValidator",
                    errors=[message] if is_error else [],
                    warnings=[message] if not is_error else [],
                    metadata={
                        "rule_id": rule_ref.rule_id,
                        "category": "type",
                        "subcategory": "financial",
                        "agent_type": agent_type,
                        "precondition": rule_ref.precondition,
                        "blocked_skill": skill_name,
                        "level": rule_ref.level,
                    }
                )

        return None

    def _normalize_label(self, label: Optional[str]) -> str:
        """Normalize PMT label to standard format."""
        if not label:
            return ""
        label = str(label).upper().strip()
        mappings = {
            "VERY LOW": "VL", "VERYLOW": "VL", "VERY_LOW": "VL",
            "LOW": "L",
            "MEDIUM": "M", "MED": "M", "MODERATE": "M",
            "HIGH": "H",
            "VERY HIGH": "VH", "VERYHIGH": "VH", "VERY_HIGH": "VH"
        }
        return mappings.get(label, label)
