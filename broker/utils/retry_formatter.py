"""
Retry Message Formatter with Template Engine support.

Part of the Cognitive Governance Framework.
Provides dynamic variable interpolation for governance retry messages,
allowing rules to include context-aware error messages.

Usage:
    from broker.utils.retry_formatter import RetryMessageFormatter

    formatter = RetryMessageFormatter()
    result = formatter.format(
        "Your TP={context.TP_LABEL} is too low",
        {"context": {"TP_LABEL": "VL"}}
    )
    # result: "Your TP=VL is too low"

Supported Variables:
    - {context.TP_LABEL}: Current threat appraisal value
    - {context.CP_LABEL}: Current coping appraisal value
    - {context.decision}: Proposed decision/skill
    - {context.agent_id}: Agent identifier
    - {rule.id}: Rule identifier that triggered
    - {rule.blocked_skills}: List of blocked skills
    - {rule.level}: Rule severity level (ERROR/WARNING)
"""

import re
from typing import Any, Dict, List, Optional


class RetryMessageFormatter:
    """
    Format retry messages with context variable interpolation.

    This class provides a simple template engine for governance retry messages,
    allowing rules to include dynamic context values in their error messages.

    Attributes:
        strict_mode: If True, raises KeyError on missing variables.
                    If False, keeps original placeholder text.

    Example:
        >>> formatter = RetryMessageFormatter()
        >>> formatter.format(
        ...     "Elevation blocked: TP={context.TP_LABEL}",
        ...     {"context": {"TP_LABEL": "VL"}}
        ... )
        'Elevation blocked: TP=VL'
    """

    # Pattern matches {var} or {var.path} or {var.path.nested}
    VARIABLE_PATTERN = re.compile(r'\{(\w+(?:\.\w+)*)\}')

    def __init__(self, strict_mode: bool = False):
        """
        Initialize the formatter.

        Args:
            strict_mode: If True, raise KeyError when a variable is not found.
                        If False (default), keep the original placeholder.
        """
        self.strict_mode = strict_mode

    def format(self, template: str, context: Dict[str, Any]) -> str:
        """
        Format template string with context variables.

        Args:
            template: Message template with {var.path} placeholders.
                     Example: "Your TP={context.TP_LABEL} is too low."
            context: Dictionary containing variable values.
                    Nested access is supported via dot notation.

        Returns:
            Formatted message string with placeholders replaced.

        Raises:
            KeyError: If strict_mode=True and a variable is not found.

        Example:
            >>> formatter = RetryMessageFormatter()
            >>> formatter.format(
            ...     "Rule {rule.id} blocked {context.decision}",
            ...     {"rule": {"id": "test_rule"}, "context": {"decision": "elevate"}}
            ... )
            'Rule test_rule blocked elevate'
        """
        if not template:
            return template

        def replace_var(match: re.Match) -> str:
            var_path = match.group(1)
            value = self._resolve_path(var_path, context)
            if value is None:
                if self.strict_mode:
                    raise KeyError(f"Missing variable: {var_path}")
                return match.group(0)  # Keep original placeholder
            return self._format_value(value)

        return self.VARIABLE_PATTERN.sub(replace_var, template)

    def _resolve_path(self, path: str, data: Dict[str, Any]) -> Optional[Any]:
        """
        Resolve dot-notation path in nested dictionary.

        Args:
            path: Dot-separated path like 'context.TP_LABEL'
            data: Dictionary to resolve from

        Returns:
            Resolved value or None if not found
        """
        parts = path.split('.')
        current: Any = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
        return current

    def _format_value(self, value: Any) -> str:
        """
        Format a value for insertion into the message.

        Args:
            value: Value to format

        Returns:
            String representation of the value
        """
        if isinstance(value, list):
            return ', '.join(str(v) for v in value)
        return str(value)

    def format_with_defaults(
        self,
        template: str,
        context: Dict[str, Any],
        defaults: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format template with context variables and fallback defaults.

        Args:
            template: Message template with {var.path} placeholders
            context: Primary dictionary containing variable values
            defaults: Fallback dictionary for missing values

        Returns:
            Formatted message string

        Example:
            >>> formatter = RetryMessageFormatter()
            >>> formatter.format_with_defaults(
            ...     "TP={context.TP_LABEL}",
            ...     {"context": {}},
            ...     {"context": {"TP_LABEL": "N/A"}}
            ... )
            'TP=N/A'
        """
        # Merge defaults with context (context takes priority)
        merged = self._deep_merge(defaults or {}, context)
        return self.format(template, merged)

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries, with override taking priority."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


# Singleton instance for convenience
_default_formatter = RetryMessageFormatter(strict_mode=False)


def format_retry_message(template: str, context: Dict[str, Any]) -> str:
    """
    Convenience function to format a retry message.

    Uses the default formatter with strict_mode=False.

    Args:
        template: Message template with {var.path} placeholders
        context: Dictionary containing variable values

    Returns:
        Formatted message string
    """
    return _default_formatter.format(template, context)
