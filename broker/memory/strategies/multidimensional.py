"""
Multi-dimensional Surprise Strategy - Track multiple variables simultaneously.

Extends EMA-based surprise detection to monitor multiple environmental
variables with configurable weights and aggregation strategies.

Reference:
- Task-050C: Multi-dimensional Surprise Tracking
- A-MEM (2025): Multi-factor surprise for memory consolidation
- Generative Agents (Park et al., 2023): Multi-factor importance

Example:
    >>> strategy = MultiDimensionalSurpriseStrategy(
    ...     variables={"flood_depth": 0.5, "neighbor_panic": 0.3, "policy_change": 0.2},
    ...     aggregation="max"
    ... )
    >>> surprise = strategy.update({"flood_depth": 2.5, "neighbor_panic": 0.8})
    >>> print(f"Aggregate surprise: {surprise:.2f}")
"""

from typing import Dict, Any, Optional, List, Literal
from .ema import EMAPredictor


class MultiDimensionalSurpriseStrategy:
    """
    Multi-dimensional surprise strategy tracking multiple variables.

    Monitors multiple environmental variables simultaneously and computes
    aggregate surprise using configurable strategies. This enables richer
    anomaly detection for System 1/2 cognitive switching.

    Features:
    - Track arbitrary number of variables
    - Per-variable weight configuration
    - Multiple aggregation strategies (max, mean, weighted_sum)
    - Detailed per-variable trace for explainability
    - Compliant with SurpriseStrategy protocol

    Args:
        variables: Dict mapping variable names to weights (must sum to 1.0)
        alpha: EMA smoothing factor for all predictors [0-1]
        aggregation: Aggregation strategy ("max", "mean", "weighted_sum")
        normalize_range: Optional (min, max) range for normalizing raw surprise

    Example:
        >>> strategy = MultiDimensionalSurpriseStrategy(
        ...     variables={
        ...         "flood_depth": 0.4,
        ...         "neighbor_panic": 0.3,
        ...         "policy_change": 0.3
        ...     },
        ...     aggregation="max"
        ... )
        >>> # Any variable spiking triggers high surprise
        >>> surprise = strategy.update({"flood_depth": 0.1, "neighbor_panic": 0.9})
    """

    def __init__(
        self,
        variables: Dict[str, float],
        alpha: float = 0.3,
        aggregation: Literal["max", "mean", "weighted_sum"] = "max",
        normalize_range: Optional[tuple] = None,
    ):
        if not variables:
            raise ValueError("At least one variable must be specified")

        if not 0.0 <= alpha <= 1.0:
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")

        self.variables = variables
        self.alpha = alpha
        self.aggregation = aggregation
        self.normalize_range = normalize_range

        # Create EMA predictor for each variable
        self._predictors: Dict[str, EMAPredictor] = {
            name: EMAPredictor(alpha=alpha, initial_value=0.0)
            for name in variables
        }

        # Normalize weights to sum to 1.0
        total_weight = sum(variables.values())
        if total_weight > 0:
            self._normalized_weights = {
                k: v / total_weight for k, v in variables.items()
            }
        else:
            self._normalized_weights = {k: 1.0 / len(variables) for k in variables}

        # Trace data
        self._last_values: Dict[str, float] = {}
        self._last_surprises: Dict[str, float] = {}
        self._last_aggregate: float = 0.0

    def _extract_value(self, observation: Dict[str, Any], key: str) -> float:
        """Extract and convert value from observation."""
        value = observation.get(key, 0.0)
        return float(value) if value is not None else 0.0

    def _normalize_surprise(self, raw_surprise: float) -> float:
        """Normalize surprise to [0, 1] range."""
        if self.normalize_range is None:
            return min(1.0, raw_surprise / 10.0)

        min_val, max_val = self.normalize_range
        range_size = max_val - min_val
        if range_size <= 0:
            return 0.0
        return min(1.0, max(0.0, raw_surprise / range_size))

    def _aggregate(self, surprises: Dict[str, float]) -> float:
        """Aggregate individual surprises into single value."""
        if not surprises:
            return 0.0

        values = list(surprises.values())

        if self.aggregation == "max":
            # Maximum surprise triggers System 2
            return max(values)

        elif self.aggregation == "mean":
            # Average surprise across all dimensions
            return sum(values) / len(values)

        elif self.aggregation == "weighted_sum":
            # Weighted sum using variable weights
            total = 0.0
            for name, surprise in surprises.items():
                weight = self._normalized_weights.get(name, 0.0)
                total += weight * surprise
            return total

        else:
            raise ValueError(f"Unknown aggregation: {self.aggregation}")

    def update(self, observation: Dict[str, Any]) -> float:
        """
        Update internal state and return aggregate surprise.

        Args:
            observation: Dict containing observed values for tracked variables

        Returns:
            Aggregate surprise value [0-1]
        """
        self._last_values = {}
        self._last_surprises = {}

        for name, predictor in self._predictors.items():
            reality = self._extract_value(observation, name)
            self._last_values[name] = reality

            # Calculate raw surprise
            raw_surprise = predictor.surprise(reality)
            self._last_surprises[name] = self._normalize_surprise(raw_surprise)

            # Update expectation
            predictor.update(reality)

        # Aggregate surprises
        self._last_aggregate = self._aggregate(self._last_surprises)

        return self._last_aggregate

    def get_surprise(self, observation: Dict[str, Any]) -> float:
        """
        Calculate surprise WITHOUT updating internal state.

        Args:
            observation: Dict containing observed values

        Returns:
            Aggregate surprise value [0-1]
        """
        surprises = {}
        for name, predictor in self._predictors.items():
            reality = self._extract_value(observation, name)
            raw_surprise = predictor.surprise(reality)
            surprises[name] = self._normalize_surprise(raw_surprise)

        return self._aggregate(surprises)

    def get_arousal(self) -> float:
        """Get last computed aggregate surprise (arousal level)."""
        return self._last_aggregate

    def get_per_variable_surprise(self) -> Dict[str, float]:
        """Get last surprise values for each variable."""
        return self._last_surprises.copy()

    def get_dominant_variable(self) -> Optional[str]:
        """Get the variable with highest surprise in last update."""
        if not self._last_surprises:
            return None
        return max(self._last_surprises, key=self._last_surprises.get)

    def get_trace(self) -> Optional[Dict[str, Any]]:
        """
        Get detailed trace data for explainability.

        Returns:
            Dict with per-variable and aggregate trace information
        """
        if not self._last_values:
            return None

        return {
            "strategy": "MultiDimensional",
            "aggregation": self.aggregation,
            "aggregate_surprise": self._last_aggregate,
            "dominant_variable": self.get_dominant_variable(),
            "per_variable": {
                name: {
                    "value": self._last_values.get(name),
                    "surprise": self._last_surprises.get(name),
                    "weight": self._normalized_weights.get(name),
                    "expectation": self._predictors[name].predict(),
                }
                for name in self.variables
            },
            "alpha": self.alpha,
        }

    def reset(self) -> None:
        """Reset all predictor states."""
        for predictor in self._predictors.values():
            predictor.reset()
        self._last_values = {}
        self._last_surprises = {}
        self._last_aggregate = 0.0

    def add_variable(self, name: str, weight: float = 1.0) -> None:
        """
        Add a new variable to track.

        Args:
            name: Variable name
            weight: Weight for aggregation
        """
        self.variables[name] = weight
        self._predictors[name] = EMAPredictor(alpha=self.alpha, initial_value=0.0)

        # Recalculate normalized weights
        total_weight = sum(self.variables.values())
        self._normalized_weights = {
            k: v / total_weight for k, v in self.variables.items()
        }

    def remove_variable(self, name: str) -> bool:
        """
        Remove a variable from tracking.

        Args:
            name: Variable name to remove

        Returns:
            True if removed, False if not found
        """
        if name not in self.variables:
            return False

        del self.variables[name]
        del self._predictors[name]
        self._normalized_weights.pop(name, None)

        # Recalculate normalized weights
        if self.variables:
            total_weight = sum(self.variables.values())
            self._normalized_weights = {
                k: v / total_weight for k, v in self.variables.items()
            }

        return True


# Convenience factory function
def create_flood_surprise_strategy(
    include_social: bool = True,
    include_policy: bool = True,
    alpha: float = 0.3,
) -> MultiDimensionalSurpriseStrategy:
    """
    Create a pre-configured multi-dimensional surprise strategy for flood domain.

    Args:
        include_social: Include neighbor panic tracking
        include_policy: Include policy change tracking
        alpha: EMA smoothing factor

    Returns:
        Configured MultiDimensionalSurpriseStrategy
    """
    variables = {
        "flood_depth": 0.4,
    }

    if include_social:
        variables["neighbor_panic"] = 0.3
        variables["elevated_pct"] = 0.15

    if include_policy:
        variables["subsidy_rate"] = 0.15

    return MultiDimensionalSurpriseStrategy(
        variables=variables,
        alpha=alpha,
        aggregation="max",  # Any spike triggers System 2
    )
