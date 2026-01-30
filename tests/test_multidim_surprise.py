"""
Tests for Multi-dimensional Surprise Strategy (Task-050C).

Verifies multi-variable surprise tracking and aggregation.
"""

import pytest
from cognitive_governance.memory.strategies.multidimensional import (
    MultiDimensionalSurpriseStrategy,
    create_flood_surprise_strategy,
)


class TestMultiDimensionalSurpriseStrategy:
    """Tests for MultiDimensionalSurpriseStrategy."""

    def test_init_basic(self):
        """Test basic initialization."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"flood_depth": 0.5, "panic_level": 0.5},
            alpha=0.3,
            aggregation="max"
        )

        assert len(strategy.variables) == 2
        assert strategy.alpha == 0.3
        assert strategy.aggregation == "max"

    def test_init_empty_variables_raises(self):
        """Test that empty variables dict raises error."""
        with pytest.raises(ValueError):
            MultiDimensionalSurpriseStrategy(variables={})

    def test_init_invalid_alpha_raises(self):
        """Test that invalid alpha raises error."""
        with pytest.raises(ValueError):
            MultiDimensionalSurpriseStrategy(
                variables={"x": 1.0},
                alpha=1.5
            )

    def test_update_single_variable(self):
        """Test update with single variable."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"flood_depth": 1.0},
            alpha=0.3
        )

        # First update establishes baseline
        surprise1 = strategy.update({"flood_depth": 1.0})

        # Same value = low surprise (after EMA adjusts)
        surprise2 = strategy.update({"flood_depth": 1.0})

        # Different value = higher surprise
        surprise3 = strategy.update({"flood_depth": 5.0})

        assert surprise3 > surprise2  # Spike causes higher surprise

    def test_update_multiple_variables(self):
        """Test update with multiple variables."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"flood_depth": 0.5, "panic_level": 0.5},
            alpha=0.3,
            aggregation="max"
        )

        # Initialize both
        strategy.update({"flood_depth": 1.0, "panic_level": 0.2})

        # Spike one variable
        surprise = strategy.update({"flood_depth": 1.0, "panic_level": 0.9})

        assert surprise > 0  # Should detect the panic spike

    def test_aggregation_max(self):
        """Test max aggregation strategy."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"a": 0.5, "b": 0.5},
            aggregation="max"
        )

        # Initialize
        strategy.update({"a": 0.0, "b": 0.0})

        # Spike 'a', keep 'b' stable
        surprise = strategy.update({"a": 10.0, "b": 0.0})

        # Max should pick up the spike in 'a'
        per_var = strategy.get_per_variable_surprise()
        assert per_var["a"] > per_var["b"]
        assert surprise == max(per_var.values())

    def test_aggregation_mean(self):
        """Test mean aggregation strategy."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"a": 0.5, "b": 0.5},
            aggregation="mean"
        )

        strategy.update({"a": 0.0, "b": 0.0})
        surprise = strategy.update({"a": 10.0, "b": 0.0})

        per_var = strategy.get_per_variable_surprise()
        expected_mean = sum(per_var.values()) / 2
        assert abs(surprise - expected_mean) < 0.01

    def test_aggregation_weighted_sum(self):
        """Test weighted_sum aggregation strategy."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"a": 0.8, "b": 0.2},  # 'a' has higher weight
            aggregation="weighted_sum"
        )

        strategy.update({"a": 0.0, "b": 0.0})

        # Same spike on both, but 'a' should dominate
        surprise = strategy.update({"a": 5.0, "b": 5.0})

        per_var = strategy.get_per_variable_surprise()
        # Weighted sum should favor 'a'
        assert surprise > 0

    def test_get_dominant_variable(self):
        """Test getting the dominant variable."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"flood": 0.5, "panic": 0.5},
            aggregation="max"
        )

        strategy.update({"flood": 0.0, "panic": 0.0})
        strategy.update({"flood": 10.0, "panic": 0.1})  # Flood spikes

        dominant = strategy.get_dominant_variable()
        assert dominant == "flood"

    def test_get_surprise_read_only(self):
        """Test that get_surprise doesn't update state."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"x": 1.0},
            alpha=0.3
        )

        strategy.update({"x": 1.0})
        expectation_before = strategy._predictors["x"].predict()

        # Read-only query
        strategy.get_surprise({"x": 5.0})

        expectation_after = strategy._predictors["x"].predict()
        assert expectation_before == expectation_after

    def test_get_trace(self):
        """Test trace data retrieval."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"flood": 0.6, "panic": 0.4},
            aggregation="max"
        )

        strategy.update({"flood": 2.0, "panic": 0.5})

        trace = strategy.get_trace()

        assert trace is not None
        assert trace["strategy"] == "MultiDimensional"
        assert trace["aggregation"] == "max"
        assert "aggregate_surprise" in trace
        assert "dominant_variable" in trace
        assert "per_variable" in trace
        assert "flood" in trace["per_variable"]
        assert "panic" in trace["per_variable"]

    def test_reset(self):
        """Test reset clears state."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"x": 1.0}
        )

        strategy.update({"x": 5.0})
        assert strategy.get_arousal() > 0

        strategy.reset()

        assert strategy.get_arousal() == 0.0
        assert strategy.get_trace() is None

    def test_add_variable(self):
        """Test dynamically adding a variable."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"x": 1.0}
        )

        assert len(strategy.variables) == 1

        strategy.add_variable("y", weight=0.5)

        assert len(strategy.variables) == 2
        assert "y" in strategy._predictors

    def test_remove_variable(self):
        """Test dynamically removing a variable."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"x": 0.5, "y": 0.5}
        )

        result = strategy.remove_variable("y")

        assert result is True
        assert len(strategy.variables) == 1
        assert "y" not in strategy._predictors

        # Removing non-existent returns False
        result = strategy.remove_variable("z")
        assert result is False

    def test_missing_observation_value(self):
        """Test handling of missing values in observation."""
        strategy = MultiDimensionalSurpriseStrategy(
            variables={"x": 0.5, "y": 0.5}
        )

        # Only provide 'x', 'y' should default to 0
        surprise = strategy.update({"x": 1.0})

        assert strategy._last_values.get("y") == 0.0


class TestCreateFloodSurpriseStrategy:
    """Tests for the flood domain factory function."""

    def test_default_config(self):
        """Test default flood surprise strategy."""
        strategy = create_flood_surprise_strategy()

        assert "flood_depth" in strategy.variables
        assert "neighbor_panic" in strategy.variables
        assert "elevated_pct" in strategy.variables
        assert "subsidy_rate" in strategy.variables
        assert strategy.aggregation == "max"

    def test_without_social(self):
        """Test without social variables."""
        strategy = create_flood_surprise_strategy(include_social=False)

        assert "flood_depth" in strategy.variables
        assert "neighbor_panic" not in strategy.variables
        assert "elevated_pct" not in strategy.variables

    def test_without_policy(self):
        """Test without policy variables."""
        strategy = create_flood_surprise_strategy(include_policy=False)

        assert "flood_depth" in strategy.variables
        assert "subsidy_rate" not in strategy.variables

    def test_custom_alpha(self):
        """Test custom alpha parameter."""
        strategy = create_flood_surprise_strategy(alpha=0.5)

        assert strategy.alpha == 0.5


class TestProtocolCompliance:
    """Test that strategy complies with SurpriseStrategy protocol."""

    def test_has_required_methods(self):
        """Test that all protocol methods exist."""
        strategy = MultiDimensionalSurpriseStrategy(variables={"x": 1.0})

        assert hasattr(strategy, "update")
        assert hasattr(strategy, "get_surprise")
        assert hasattr(strategy, "get_arousal")
        assert hasattr(strategy, "get_trace")
        assert hasattr(strategy, "reset")

        assert callable(strategy.update)
        assert callable(strategy.get_surprise)
        assert callable(strategy.get_arousal)
        assert callable(strategy.get_trace)
        assert callable(strategy.reset)
