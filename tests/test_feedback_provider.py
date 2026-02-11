"""
Tests for broker.components.feedback_provider module.

Covers:
- AgentMetricsTracker: record, get_history, compute_trends
- SafeExpressionEvaluator: safety checking and evaluation
- FeedbackDashboardProvider: full dashboard rendering + assertion evaluation
"""

import pytest

from broker.components.analytics.feedback import (
    AgentMetricsTracker,
    FeedbackDashboardProvider,
    SafeExpressionEvaluator,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def metric_names():
    return ["request", "supply"]


@pytest.fixture
def tracker(metric_names):
    return AgentMetricsTracker(metric_names, window=5)


@pytest.fixture
def feedback_config():
    """Minimal feedback config matching irrigation agent_types.yaml."""
    return {
        "trend_window": 5,
        "dashboard_format": "table",
        "tracked_metrics": [
            {"name": "request", "source": "current_request", "unit": "AF", "format": ",.0f"},
            {"name": "supply", "source": "current_diversion", "unit": "AF", "format": ",.0f"},
        ],
        "assertions": [
            {
                "when": "supply / request < 0.95",
                "severity": "warning",
                "message": (
                    "You requested {request_fmt} AF but only received {supply_fmt} AF "
                    "({unmet_pct:.0f}% unmet)."
                ),
            }
        ],
    }


# =========================================================================
# AgentMetricsTracker Tests
# =========================================================================

class TestAgentMetricsTracker:

    def test_record_and_get_history(self, tracker):
        tracker.record("A1", 2020, {"request": 100, "supply": 90})
        tracker.record("A1", 2021, {"request": 110, "supply": 85})

        history = tracker.get_history("A1")
        assert len(history) == 2
        assert history[0]["year"] == 2020
        assert history[0]["request"] == 100
        assert history[1]["supply"] == 85

    def test_get_history_respects_window(self, tracker):
        for y in range(2015, 2025):
            tracker.record("A1", y, {"request": y, "supply": y - 10})

        history = tracker.get_history("A1")
        assert len(history) == 5  # window=5
        assert history[0]["year"] == 2020

    def test_get_history_custom_window(self, tracker):
        for y in range(2015, 2025):
            tracker.record("A1", y, {"request": y, "supply": y - 10})

        history = tracker.get_history("A1", window=3)
        assert len(history) == 3
        assert history[0]["year"] == 2022

    def test_get_history_empty_agent(self, tracker):
        assert tracker.get_history("nonexistent") == []

    def test_record_missing_metric_defaults_zero(self, tracker):
        tracker.record("A1", 2020, {"request": 100})
        history = tracker.get_history("A1")
        assert history[0]["supply"] == 0.0

    def test_separate_agents(self, tracker):
        tracker.record("A1", 2020, {"request": 100, "supply": 90})
        tracker.record("A2", 2020, {"request": 200, "supply": 180})

        assert tracker.get_history("A1")[0]["request"] == 100
        assert tracker.get_history("A2")[0]["request"] == 200

    # -- Trend Tests --

    def test_trends_rising(self, tracker):
        tracker.record("A1", 2020, {"request": 100, "supply": 80})
        tracker.record("A1", 2021, {"request": 110, "supply": 85})
        tracker.record("A1", 2022, {"request": 130, "supply": 100})
        tracker.record("A1", 2023, {"request": 150, "supply": 120})

        trends = tracker.compute_trends("A1")
        assert trends["request"] == "rising"
        assert trends["supply"] == "rising"

    def test_trends_falling(self, tracker):
        tracker.record("A1", 2020, {"request": 200, "supply": 180})
        tracker.record("A1", 2021, {"request": 180, "supply": 160})
        tracker.record("A1", 2022, {"request": 120, "supply": 100})
        tracker.record("A1", 2023, {"request": 100, "supply": 80})

        trends = tracker.compute_trends("A1")
        assert trends["request"] == "falling"
        assert trends["supply"] == "falling"

    def test_trends_stable(self, tracker):
        tracker.record("A1", 2020, {"request": 100, "supply": 95})
        tracker.record("A1", 2021, {"request": 101, "supply": 96})
        tracker.record("A1", 2022, {"request": 100, "supply": 95})
        tracker.record("A1", 2023, {"request": 102, "supply": 97})

        trends = tracker.compute_trends("A1")
        assert trends["request"] == "stable"
        assert trends["supply"] == "stable"

    def test_trends_insufficient_data(self, tracker):
        tracker.record("A1", 2020, {"request": 100, "supply": 90})
        trends = tracker.compute_trends("A1")
        assert trends["request"] == "insufficient_data"
        assert trends["supply"] == "insufficient_data"

    def test_trends_no_data(self, tracker):
        trends = tracker.compute_trends("nonexistent")
        assert trends["request"] == "insufficient_data"

    def test_trends_zero_to_positive(self, tracker):
        """First-half average is 0, second half is positive → rising."""
        tracker.record("A1", 2020, {"request": 0, "supply": 0})
        tracker.record("A1", 2021, {"request": 0, "supply": 0})
        tracker.record("A1", 2022, {"request": 100, "supply": 80})
        tracker.record("A1", 2023, {"request": 120, "supply": 90})

        trends = tracker.compute_trends("A1")
        assert trends["request"] == "rising"

    def test_trends_all_zero(self, tracker):
        tracker.record("A1", 2020, {"request": 0, "supply": 0})
        tracker.record("A1", 2021, {"request": 0, "supply": 0})
        trends = tracker.compute_trends("A1")
        assert trends["request"] == "stable"


# =========================================================================
# SafeExpressionEvaluator Tests
# =========================================================================

class TestSafeExpressionEvaluator:

    # -- Safety --

    def test_safe_simple_comparison(self):
        assert SafeExpressionEvaluator.is_safe("supply / request < 0.95")

    def test_safe_arithmetic(self):
        assert SafeExpressionEvaluator.is_safe("a + b * 2 - c / 3")

    def test_safe_boolean(self):
        assert SafeExpressionEvaluator.is_safe("a > 1 and b < 2")

    def test_unsafe_import(self):
        assert not SafeExpressionEvaluator.is_safe("__import__('os').system('rm -rf /')")

    def test_unsafe_function_call(self):
        assert not SafeExpressionEvaluator.is_safe("print('hello')")

    def test_unsafe_attribute_access(self):
        assert not SafeExpressionEvaluator.is_safe("x.__class__")

    def test_unsafe_subscript(self):
        assert not SafeExpressionEvaluator.is_safe("x[0]")

    def test_unsafe_lambda(self):
        assert not SafeExpressionEvaluator.is_safe("lambda: 1")

    def test_unsafe_syntax_error(self):
        assert not SafeExpressionEvaluator.is_safe("if True:")

    # -- Evaluation --

    def test_evaluate_comparison_true(self):
        result = SafeExpressionEvaluator.evaluate(
            "supply / request < 0.95", {"supply": 80, "request": 100}
        )
        assert result is True

    def test_evaluate_comparison_false(self):
        result = SafeExpressionEvaluator.evaluate(
            "supply / request < 0.95", {"supply": 98, "request": 100}
        )
        assert result is False

    def test_evaluate_arithmetic(self):
        result = SafeExpressionEvaluator.evaluate("a + b", {"a": 3, "b": 7})
        assert result == 10

    def test_evaluate_division_by_zero_guarded(self):
        """Zero-valued variables are replaced with epsilon to prevent ZeroDivisionError."""
        result = SafeExpressionEvaluator.evaluate(
            "supply / request < 0.95", {"supply": 0, "request": 0}
        )
        # 1e-10 / 1e-10 = 1.0, which is NOT < 0.95
        assert result is False

    def test_evaluate_rejects_unsafe(self):
        with pytest.raises(ValueError, match="Unsafe"):
            SafeExpressionEvaluator.evaluate("print('x')", {})


# =========================================================================
# FeedbackDashboardProvider Tests
# =========================================================================

class TestFeedbackDashboardProvider:

    def _make_provider(self, tracker, config):
        return FeedbackDashboardProvider(tracker, config)

    def test_provide_empty_history(self, tracker, feedback_config):
        """Year 1: no history yet, just assertions."""
        provider = self._make_provider(tracker, feedback_config)
        context = {}
        provider.provide(
            "A1", {}, context,
            env_context={"current_request": 100_000, "current_diversion": 70_000},
        )
        dashboard = context["feedback_dashboard"]
        # Should contain assertion alert (70000/100000 = 0.70 < 0.95)
        assert "WARNING" in dashboard
        assert "70,000" in dashboard

    def test_provide_no_alert_when_fulfilled(self, tracker, feedback_config):
        """Assertion should NOT fire when supply/request >= 0.95."""
        provider = self._make_provider(tracker, feedback_config)
        context = {}
        provider.provide(
            "A1", {}, context,
            env_context={"current_request": 100_000, "current_diversion": 98_000},
        )
        dashboard = context["feedback_dashboard"]
        assert "WARNING" not in dashboard

    def test_provide_with_history_table(self, tracker, feedback_config):
        """Dashboard should render a history table after recording."""
        tracker.record("A1", 2020, {"request": 100_000, "supply": 90_000})
        tracker.record("A1", 2021, {"request": 110_000, "supply": 80_000})

        provider = self._make_provider(tracker, feedback_config)
        context = {}
        provider.provide(
            "A1", {}, context,
            env_context={"current_request": 110_000, "current_diversion": 80_000},
        )
        dashboard = context["feedback_dashboard"]
        assert "PERFORMANCE HISTORY" in dashboard
        assert "2020" in dashboard
        assert "2021" in dashboard

    def test_provide_trends_displayed(self, tracker, feedback_config):
        """Trends should appear after sufficient history."""
        tracker.record("A1", 2020, {"request": 100, "supply": 90})
        tracker.record("A1", 2021, {"request": 120, "supply": 80})
        tracker.record("A1", 2022, {"request": 140, "supply": 70})

        provider = self._make_provider(tracker, feedback_config)
        context = {}
        provider.provide(
            "A1", {}, context,
            env_context={"current_request": 140, "current_diversion": 70},
        )
        dashboard = context["feedback_dashboard"]
        assert "TREND:" in dashboard
        assert "RISING" in dashboard or "FALLING" in dashboard

    def test_provide_no_feedback_when_format_none(self, tracker, feedback_config):
        """dashboard_format=none should suppress the history table."""
        feedback_config["dashboard_format"] = "none"
        tracker.record("A1", 2020, {"request": 100, "supply": 90})

        provider = self._make_provider(tracker, feedback_config)
        context = {}
        provider.provide(
            "A1", {}, context,
            env_context={"current_request": 100, "current_diversion": 95},
        )
        dashboard = context["feedback_dashboard"]
        # No table, no assertion (95/100 = 0.95 not < 0.95), maybe trend
        assert "PERFORMANCE HISTORY" not in dashboard

    def test_provide_empty_context_key(self, tracker):
        """No feedback config → empty dashboard string."""
        provider = self._make_provider(tracker, {})
        context = {}
        provider.provide("A1", {}, context, env_context={})
        assert context["feedback_dashboard"] == ""

    def test_assertion_format_with_unmet_pct(self, tracker, feedback_config):
        """Check that {unmet_pct:.0f} is properly formatted."""
        provider = self._make_provider(tracker, feedback_config)
        context = {}
        provider.provide(
            "A1", {}, context,
            env_context={"current_request": 200_000, "current_diversion": 100_000},
        )
        dashboard = context["feedback_dashboard"]
        assert "50% unmet" in dashboard

    def test_assertion_safe_expression_rejected(self, tracker):
        """Unsafe assertion expressions should be silently skipped."""
        config = {
            "tracked_metrics": [
                {"name": "x", "source": "x", "unit": "", "format": ""},
            ],
            "assertions": [
                {"when": "__import__('os')", "severity": "warning", "message": "bad"},
            ],
        }
        provider = self._make_provider(tracker, config)
        context = {}
        provider.provide("A1", {}, context, env_context={"x": 1})
        # Should not crash, and should not produce alert
        assert "WARNING" not in context.get("feedback_dashboard", "")

    def test_multiple_assertions(self, tracker):
        """Multiple assertions: only triggered ones appear."""
        config = {
            "tracked_metrics": [
                {"name": "a", "source": "a", "unit": "", "format": ""},
                {"name": "b", "source": "b", "unit": "", "format": ""},
            ],
            "assertions": [
                {"when": "a > 10", "severity": "warning", "message": "A is high"},
                {"when": "b < 5", "severity": "error", "message": "B is low"},
            ],
        }
        provider = self._make_provider(tracker, config)
        context = {}
        provider.provide("A1", {}, context, env_context={"a": 20, "b": 10})
        dashboard = context["feedback_dashboard"]
        assert "A is high" in dashboard
        assert "B is low" not in dashboard

    def test_provide_missing_env_context_defaults_zero(self, tracker, feedback_config):
        """Missing env_context keys default to 0."""
        provider = self._make_provider(tracker, feedback_config)
        context = {}
        # No current_request or current_diversion in env_context
        provider.provide("A1", {}, context, env_context={})
        # Should not crash (division by near-zero epsilon, assertion evaluates false)
        assert "feedback_dashboard" in context
