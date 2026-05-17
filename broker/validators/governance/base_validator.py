"""
Base Validator - Abstract base class for governance validators.

All category validators inherit from this class.
Supports dynamic template interpolation in rule messages via RetryMessageFormatter.

Built-in domain-specific checks are injected via ``builtin_checks`` constructor
parameter.  Each check is a callable:
    (skill_name: str, rules: List[GovernanceRule], context: Dict) -> List[ValidationResult]

When ``builtin_checks`` is *None* (default), subclasses provide their own
domain defaults via ``_default_builtin_checks()``.
Pass an empty list ``[]`` to disable all built-in checks and rely on YAML rules only.
"""
import copy
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule
from broker.utils.retry_formatter import RetryMessageFormatter

# Type alias for domain-specific built-in check functions.
# Each function receives (skill_name, rules, context) and returns
# a list of ValidationResult for any violations found.
BuiltinCheck = Callable[
    [str, List[GovernanceRule], Dict[str, Any]],
    List[ValidationResult],
]


def scoped_to(*agent_types: str):
    """Mark a builtin check as applicable only to these agent types
    (or their base types). A check WITHOUT this marker applies to ALL
    agent types (backward compatible)."""
    norm = frozenset(t.strip().lower() for t in agent_types if t)

    def _wrap(fn):
        fn._wagf_agent_types = norm
        return fn

    return _wrap


class BaseValidator(ABC):
    """
    Abstract base class for governance validators.

    Each validator is responsible for evaluating rules in a specific category.
    Supports dynamic template interpolation in rule messages using {var.path} syntax.

    Domain-specific built-in checks are injected via *builtin_checks*.
    Subclasses that need domain defaults override ``_default_builtin_checks()``.

    Example YAML rule with template:
        - id: high_threat_no_maintain
          message: "Action blocked: Your THREAT={context.THREAT_LABEL} requires action."
    """

    # Shared formatter instance (lenient mode - keeps placeholders if missing)
    _message_formatter = RetryMessageFormatter(strict_mode=False)

    _valid_modes = {"active", "shadow"}

    def __init__(
        self,
        builtin_checks: Optional[List[BuiltinCheck]] = None,
        mode: str = "active",
    ):
        self.set_mode(mode)
        if builtin_checks is not None:
            self._builtin_checks = builtin_checks
        else:
            self._builtin_checks = self._default_builtin_checks()

    def set_mode(self, mode: str) -> None:
        """Set validator enforcement mode."""
        if mode not in self._valid_modes:
            raise ValueError(f"mode must be one of {sorted(self._valid_modes)}, got {mode!r}")
        self.mode = mode

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Return default domain-specific checks.

        Subclasses override this to provide flood / irrigation / etc. defaults.
        The base implementation returns an empty list (no built-in checks).
        """
        return []

    def _to_shadow(self, result: ValidationResult) -> ValidationResult:
        """Convert a blocking built-in result to shadow-mode shape."""
        metadata = copy.deepcopy(result.metadata or {})
        rid = metadata.get("rule_id") or f"{result.validator_name or self.__class__.__name__}:builtin"
        metadata.update({
            "shadow_blocked": [rid],
            "would_block_level": "ERROR",
        })
        shadow_result = ValidationResult(
            valid=True,
            validator_name=result.validator_name,
            errors=[],
            warnings=list(result.warnings or []) + list(result.errors or []),
            metadata=metadata,
        )
        if hasattr(result, "rule_violations"):
            shadow_result.rule_violations = result.rule_violations
        return shadow_result

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

        Evaluation order:
        1. YAML-driven rules filtered by ``self.category``
        2. Injected ``_builtin_checks`` (domain-specific hardcoded logic)

        Args:
            skill_name: Proposed skill name
            rules: List of governance rules to check
            context: Dictionary with reasoning, state, social_context

        Returns:
            List of ValidationResult objects
        """
        results = []

        # --- 1. YAML-driven rules (domain-agnostic) ---
        category_rules = [r for r in rules if r.category == self.category]

        for rule in category_rules:
            if rule.evaluate(skill_name, context):
                # Rule triggered - create result based on level
                is_error = rule.level == "ERROR"
                shadow_blocked = self.mode == "shadow" and is_error

                # Format message with template interpolation
                formatted_message = self._format_rule_message(rule, skill_name, context)
                metadata = {
                    "rule_id": rule.id,
                    "rules_hit": [rule.id],
                    "category": rule.category,
                    "subcategory": rule.subcategory,
                    "blocked_skill": skill_name,
                    "level": rule.level
                }
                if shadow_blocked:
                    metadata.update({
                        "shadow_blocked": [rule.id],
                        "would_block_level": rule.level,
                    })

                result = ValidationResult(
                    valid=True if shadow_blocked else not is_error,
                    validator_name=self.__class__.__name__,
                    errors=[] if shadow_blocked else ([formatted_message] if is_error else []),
                    warnings=[formatted_message] if (shadow_blocked or not is_error) else [],
                    metadata=metadata
                )
                results.append(result)

        # --- 2. Domain-specific built-in checks ---
        agent_type = context.get("agent_type")
        base_type = context.get("base_type")
        scope_types = {
            t.strip().lower()
            for t in (agent_type, base_type)
            if t is not None
        }
        for check in self._builtin_checks:
            declared = getattr(check, "_wagf_agent_types", None)
            if declared and scope_types and not scope_types.intersection(declared):
                continue
            for r in check(skill_name, rules, context):
                if self.mode == "shadow" and not r.valid and r.errors:
                    results.append(self._to_shadow(r))
                else:
                    results.append(r)

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
            - {context.<CONSTRUCT>}: Any construct label (e.g., TP_LABEL, WSA_LABEL)
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

        # Build template context for interpolation — domain-agnostic.
        # All construct keys (e.g., TP_LABEL, CP_LABEL, WSA_LABEL) are
        # populated from reasoning dict directly; no hardcoded fallbacks.
        reasoning = context.get("reasoning", {})
        template_context = {
            "context": {
                "decision": skill_name,
                "agent_id": context.get("agent_id", "unknown"),
                **reasoning  # Include all reasoning fields (construct labels, etc.)
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

        # Try template interpolation first — domain-agnostic
        reasoning = context.get("reasoning", {})
        template_context = {
            "context": {
                **reasoning  # All construct labels available via {context.KEY}
            },
            "rule": {"id": rule.id}
        }
        formatted_msg = self._message_formatter.format(base_msg, template_context)

        # Add context details if available (legacy behavior)
        if rule.construct and "{" not in base_msg:  # Only append if not using templates
            actual_value = reasoning.get(rule.construct, "unknown")
            return f"{formatted_msg} (Actual {rule.construct}: {actual_value})"

        return formatted_msg
