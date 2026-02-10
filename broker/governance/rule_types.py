"""
Governance Rule Types - Core type definitions for extensible rule system.

This module defines the fundamental types for the governance rule system:
- RuleCategory: personal, social, thinking, physical, semantic
- RuleLevel: ERROR (blocking) or WARNING (logging only)
- RuleCondition: Single condition to check
- GovernanceRule: Complete rule definition

Domain-agnostic: all domain-specific behavior (construct names, skill IDs,
state fields) is injected via YAML configuration.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Literal
from enum import Enum


class RuleCategory(str, Enum):
    """Categories of governance rules."""
    PERSONAL = "personal"    # Financial + Cognitive constraints
    SOCIAL = "social"        # Neighbor influence + Community norms
    THINKING = "thinking"    # Behavioral constructs + Reasoning coherence
    PHYSICAL = "physical"    # State preconditions + Immutability
    SEMANTIC = "semantic"    # Reasoning grounding + Factual consistency


class RuleLevel(str, Enum):
    """Rule enforcement level."""
    ERROR = "ERROR"      # Blocks decision, requires retry
    WARNING = "WARNING"  # Logs but allows decision


class ConditionType(str, Enum):
    """Types of conditions that can be evaluated."""
    CONSTRUCT = "construct"      # Behavioral construct label comparison (e.g., THREAT_LABEL, CAPACITY_LABEL)
    PRECONDITION = "precondition"  # Boolean state check (e.g., at_capacity, adopted_technology)
    EXPRESSION = "expression"    # Mathematical expression (e.g., budget > threshold)
    SOCIAL = "social"            # Social context check (e.g., adoption_rate > 0.5)


@dataclass
class RuleCondition:
    """
    Single condition to evaluate for a rule.

    Examples (domain-agnostic):
    - construct: {type: "construct", field: "THREAT_LABEL", operator: "in", values: ["H", "VH"]}
    - precondition: {type: "precondition", field: "at_capacity", operator: "==", values: [True]}
    - expression: {type: "expression", field: "budget", operator: ">=", values: [50000]}
    - social: {type: "social", field: "adoption_rate", operator: ">", values: [0.6]}
    """
    type: str  # construct, precondition, expression, social
    field: str  # Field name to check (configured per domain in agent_types.yaml)
    operator: str = "in"  # in, ==, !=, >, <, >=, <=
    values: List[Any] = field(default_factory=list)

    def evaluate(self, context: dict) -> bool:
        """
        Evaluate condition against context.

        Args:
            context: Dictionary with fields to check (reasoning, state, social_context)

        Returns:
            True if condition is satisfied (rule should trigger)
        """
        # Get the actual value from context
        actual_value = self._get_value_from_context(context)
        if actual_value is None:
            return False  # Can't evaluate if field not found

        # Apply operator
        if self.operator == "in":
            return actual_value in self.values
        elif self.operator == "==":
            return actual_value == self.values[0] if self.values else False
        elif self.operator == "!=":
            return actual_value != self.values[0] if self.values else True
        elif self.operator == ">":
            return actual_value > self.values[0] if self.values else False
        elif self.operator == "<":
            return actual_value < self.values[0] if self.values else False
        elif self.operator == ">=":
            return actual_value >= self.values[0] if self.values else False
        elif self.operator == "<=":
            return actual_value <= self.values[0] if self.values else False
        else:
            return False

    def _get_value_from_context(self, context: dict) -> Any:
        """Extract value from nested context based on condition type."""
        if self.type == "construct":
            # Look in reasoning dict
            reasoning = context.get("reasoning", {})
            return reasoning.get(self.field)
        elif self.type == "precondition":
            # Look in state dict
            state = context.get("state", {})
            return state.get(self.field)
        elif self.type == "expression":
            # Look in state dict for numeric values
            state = context.get("state", {})
            return state.get(self.field)
        elif self.type == "social":
            # Look in social_context dict
            social = context.get("social_context", {})
            return social.get(self.field)
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "field": self.field,
            "operator": self.operator,
            "values": self.values
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RuleCondition":
        """Create from dictionary."""
        return cls(
            type=data.get("type", "construct"),
            field=data.get("field", ""),
            operator=data.get("operator", "in"),
            values=data.get("values", [])
        )


@dataclass
class GovernanceRule:
    """
    Complete governance rule definition.

    Examples (domain-agnostic):
    - Thinking rule: Block inaction skill when threat construct is Very High
    - Physical rule: Block skill when irreversible state precondition is True
    - Social rule: Warn if majority of peers have adapted but agent hasn't
    """
    id: str                                    # Unique identifier
    category: str                              # personal, social, thinking, physical
    subcategory: str = ""                      # financial, cognitive, neighbor, pmt, state
    conditions: List[RuleCondition] = field(default_factory=list)
    blocked_skills: List[str] = field(default_factory=list)
    level: str = "ERROR"                       # ERROR or WARNING
    message: str = ""                          # Human-readable explanation

    # Legacy support for single-construct rules
    construct: Optional[str] = None            # e.g., "TP_LABEL"
    when_above: Optional[List[str]] = None     # e.g., ["VH"]
    precondition: Optional[str] = None         # e.g., "elevated"

    def evaluate(self, skill_name: str, context: dict) -> bool:
        """
        Evaluate if this rule should block the skill.

        Args:
            skill_name: Proposed skill name
            context: Dictionary with reasoning, state, social_context

        Returns:
            True if rule should trigger (skill should be blocked)
        """
        # Check if skill is in blocked list
        if skill_name not in self.blocked_skills:
            return False

        # If using modern conditions
        if self.conditions:
            # All conditions must be satisfied for rule to trigger
            return all(cond.evaluate(context) for cond in self.conditions)

        # Legacy support: single construct with when_above
        if self.construct and self.when_above:
            reasoning = context.get("reasoning", {})
            actual_label = reasoning.get(self.construct)
            if actual_label:
                # Normalize label (handle variations like "VERY HIGH" -> "VH")
                normalized = self._normalize_label(actual_label)
                return normalized in self.when_above
            return False

        # Legacy support: precondition check
        if self.precondition:
            state = context.get("state", {})
            return state.get(self.precondition, False) is True

        return False

    def _normalize_label(self, label: str) -> str:
        """Normalize construct labels to standard format (VL/L/M/H/VH)."""
        if not label:
            return ""
        label = str(label).upper().strip()
        # Map variations to standard labels
        mappings = {
            "VERY LOW": "VL", "VERYLOW": "VL", "VERY_LOW": "VL",
            "LOW": "L",
            "MEDIUM": "M", "MED": "M", "MODERATE": "M",
            "HIGH": "H",
            "VERY HIGH": "VH", "VERYHIGH": "VH", "VERY_HIGH": "VH"
        }
        return mappings.get(label, label)

    def get_intervention_message(self) -> str:
        """Get message for intervention report."""
        if self.message:
            return self.message
        return f"Rule {self.id} blocked action"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "id": self.id,
            "category": self.category,
            "subcategory": self.subcategory,
            "blocked_skills": self.blocked_skills,
            "level": self.level,
            "message": self.message
        }
        if self.conditions:
            result["conditions"] = [c.to_dict() for c in self.conditions]
        if self.construct:
            result["construct"] = self.construct
        if self.when_above:
            result["when_above"] = self.when_above
        if self.precondition:
            result["precondition"] = self.precondition
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "GovernanceRule":
        """Create from dictionary (YAML config)."""
        conditions = []
        if "conditions" in data:
            conditions = [RuleCondition.from_dict(c) for c in data["conditions"]]

        return cls(
            id=data.get("id", "unknown"),
            category=data.get("category", data.get("type", "thinking")),
            subcategory=data.get("subcategory", ""),
            conditions=conditions,
            blocked_skills=data.get("blocked_skills", []),
            level=data.get("level", "ERROR"),
            message=data.get("message", ""),
            construct=data.get("construct"),
            when_above=data.get("when_above"),
            precondition=data.get("precondition")
        )


_DEFAULT_THINKING_CONSTRUCTS = frozenset({
    "TP_LABEL", "CP_LABEL", "WSA_LABEL", "ACA_LABEL",
    "BUDGET_UTIL", "EQUITY_GAP", "RISK_APPETITE", "SOLVENCY_IMPACT",
})
_DEFAULT_PERSONAL_FIELDS = frozenset({
    "savings", "income", "cost", "budget", "water_right",
})


def categorize_rule(
    rule: GovernanceRule,
    construct_hints: Optional[Dict[str, str]] = None,
    thinking_constructs: Optional[set] = None,
    personal_fields: Optional[set] = None,
) -> str:
    """
    Categorize a rule for audit breakdown.

    Args:
        rule: The governance rule to categorize.
        construct_hints: Optional mapping from field names to categories.
            Allows domain-specific construct-to-category resolution without
            hardcoding field names.  Example::

                {"WSA_LABEL": "thinking", "ACA_LABEL": "thinking",
                 "budget": "personal", "adoption_rate": "social"}
        thinking_constructs: Optional set of construct names classified as
            "thinking".  Falls back to ``_DEFAULT_THINKING_CONSTRUCTS``.
        personal_fields: Optional set of field names classified as
            "personal".  Falls back to ``_DEFAULT_PERSONAL_FIELDS``.

    Returns:
        One of: personal, social, thinking, physical, semantic
    """
    if rule.category:
        return rule.category

    # Infer from rule structure
    if rule.precondition:
        return "physical"

    # Check domain-specific construct hints first
    if construct_hints:
        if rule.construct and rule.construct in construct_hints:
            return construct_hints[rule.construct]
        for cond in rule.conditions:
            if cond.field in construct_hints:
                return construct_hints[cond.field]

    # Configurable heuristic sets (with sensible defaults)
    tc = thinking_constructs if thinking_constructs is not None else _DEFAULT_THINKING_CONSTRUCTS
    pf = personal_fields if personal_fields is not None else _DEFAULT_PERSONAL_FIELDS
    if rule.construct in tc:
        return "thinking"
    if any(c.type == "social" for c in rule.conditions):
        return "social"
    if any(c.field in pf for c in rule.conditions):
        return "personal"

    return "thinking"  # Default
