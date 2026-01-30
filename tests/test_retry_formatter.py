"""
Unit tests for RetryMessageFormatter.

Tests the template engine functionality for governance retry messages.
"""

import pytest

from broker.utils.retry_formatter import (
    RetryMessageFormatter,
    format_retry_message,
)


class TestRetryMessageFormatter:
    """Test suite for RetryMessageFormatter class."""

    def test_simple_interpolation(self):
        """Test basic variable interpolation."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Your TP={context.TP_LABEL}",
            {"context": {"TP_LABEL": "VL"}}
        )
        assert result == "Your TP=VL"

    def test_multiple_variables(self):
        """Test multiple variables in one template."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "TP={context.TP_LABEL}, CP={context.CP_LABEL}",
            {"context": {"TP_LABEL": "VL", "CP_LABEL": "M"}}
        )
        assert result == "TP=VL, CP=M"

    def test_nested_path(self):
        """Test dot-notation nested path resolution."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Rule {rule.id} blocked {context.decision}",
            {"rule": {"id": "test_rule"}, "context": {"decision": "elevate"}}
        )
        assert result == "Rule test_rule blocked elevate"

    def test_deeply_nested_path(self):
        """Test deeply nested paths."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Value: {a.b.c.d}",
            {"a": {"b": {"c": {"d": "deep_value"}}}}
        )
        assert result == "Value: deep_value"

    def test_missing_var_lenient(self):
        """Test missing variable with lenient mode (default)."""
        formatter = RetryMessageFormatter(strict_mode=False)
        result = formatter.format(
            "Value is {missing.var}",
            {}
        )
        assert result == "Value is {missing.var}"

    def test_missing_var_strict(self):
        """Test missing variable with strict mode raises KeyError."""
        formatter = RetryMessageFormatter(strict_mode=True)
        with pytest.raises(KeyError) as exc_info:
            formatter.format("Value is {missing.var}", {})
        assert "missing.var" in str(exc_info.value)

    def test_partial_path_missing_lenient(self):
        """Test partial path resolution in lenient mode."""
        formatter = RetryMessageFormatter(strict_mode=False)
        result = formatter.format(
            "Value: {context.missing}",
            {"context": {"other": "value"}}
        )
        assert result == "Value: {context.missing}"

    def test_empty_template(self):
        """Test empty template returns empty string."""
        formatter = RetryMessageFormatter()
        result = formatter.format("", {"context": {"TP_LABEL": "VL"}})
        assert result == ""

    def test_none_template(self):
        """Test None template returns None."""
        formatter = RetryMessageFormatter()
        result = formatter.format(None, {"context": {"TP_LABEL": "VL"}})
        assert result is None

    def test_no_placeholders(self):
        """Test template with no placeholders returns unchanged."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Static message without variables",
            {"context": {"TP_LABEL": "VL"}}
        )
        assert result == "Static message without variables"

    def test_list_value(self):
        """Test list values are formatted as comma-separated."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Blocked: {rule.blocked_skills}",
            {"rule": {"blocked_skills": ["elevate_house", "relocate"]}}
        )
        assert result == "Blocked: elevate_house, relocate"

    def test_integer_value(self):
        """Test integer values are converted to string."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Year: {context.year}",
            {"context": {"year": 5}}
        )
        assert result == "Year: 5"

    def test_float_value(self):
        """Test float values are converted to string."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Score: {context.score}",
            {"context": {"score": 0.75}}
        )
        assert result == "Score: 0.75"

    def test_boolean_value(self):
        """Test boolean values are converted to string."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Active: {context.active}",
            {"context": {"active": True}}
        )
        assert result == "Active: True"

    def test_governance_rule_scenario(self):
        """Test realistic governance rule scenario."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Elevation blocked: Your threat appraisal ({context.TP_LABEL}) is too low. "
            "Consider scenarios with threat >= M. Current decision: {context.decision}",
            {
                "context": {
                    "TP_LABEL": "VL",
                    "CP_LABEL": "M",
                    "decision": "elevate_house",
                    "agent_id": "Agent_42"
                },
                "rule": {
                    "id": "elevation_threat_low",
                    "blocked_skills": ["elevate_house"],
                    "level": "ERROR"
                }
            }
        )
        assert "VL" in result
        assert "elevate_house" in result
        assert "threat >= M" in result


class TestFormatWithDefaults:
    """Test format_with_defaults method."""

    def test_defaults_used_when_missing(self):
        """Test default values are used for missing variables."""
        formatter = RetryMessageFormatter()
        result = formatter.format_with_defaults(
            "TP={context.TP_LABEL}",
            {"context": {}},
            {"context": {"TP_LABEL": "N/A"}}
        )
        assert result == "TP=N/A"

    def test_context_overrides_defaults(self):
        """Test context values override defaults."""
        formatter = RetryMessageFormatter()
        result = formatter.format_with_defaults(
            "TP={context.TP_LABEL}",
            {"context": {"TP_LABEL": "VL"}},
            {"context": {"TP_LABEL": "N/A"}}
        )
        assert result == "TP=VL"

    def test_deep_merge(self):
        """Test deep merge of nested dictionaries."""
        formatter = RetryMessageFormatter()
        result = formatter.format_with_defaults(
            "TP={context.TP_LABEL}, CP={context.CP_LABEL}",
            {"context": {"TP_LABEL": "VL"}},
            {"context": {"TP_LABEL": "default", "CP_LABEL": "N/A"}}
        )
        assert result == "TP=VL, CP=N/A"


class TestConvenienceFunction:
    """Test the convenience format_retry_message function."""

    def test_format_retry_message(self):
        """Test the convenience function works correctly."""
        result = format_retry_message(
            "TP={context.TP_LABEL}",
            {"context": {"TP_LABEL": "VL"}}
        )
        assert result == "TP=VL"

    def test_format_retry_message_missing_var(self):
        """Test convenience function uses lenient mode."""
        result = format_retry_message(
            "Value: {missing.var}",
            {}
        )
        assert result == "Value: {missing.var}"


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_curly_braces_not_placeholder(self):
        """Test that non-matching patterns are preserved."""
        formatter = RetryMessageFormatter()
        # JSON-like content should be preserved
        result = formatter.format(
            "Data: {not a valid var}",
            {}
        )
        # Pattern doesn't match (space in var name), so preserved
        assert result == "Data: {not a valid var}"

    def test_empty_context(self):
        """Test with empty context dictionary."""
        formatter = RetryMessageFormatter(strict_mode=False)
        result = formatter.format(
            "TP={context.TP_LABEL}",
            {}
        )
        assert result == "TP={context.TP_LABEL}"

    def test_single_level_var(self):
        """Test single-level variable without dot notation."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Value: {simple}",
            {"simple": "test_value"}
        )
        assert result == "Value: test_value"

    def test_special_characters_in_value(self):
        """Test values with special characters."""
        formatter = RetryMessageFormatter()
        result = formatter.format(
            "Message: {context.message}",
            {"context": {"message": "Test with {braces} and $pecial chars!"}}
        )
        assert result == "Message: Test with {braces} and $pecial chars!"
