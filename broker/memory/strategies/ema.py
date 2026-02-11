"""
EMA Surprise Strategy - Exponential Moving Average based surprise detection.

Extracted and refactored from v3 UniversalCognitiveEngine.

Formula: E_t = (alpha * R_t) + ((1 - alpha) * E_{t-1})
Surprise = |Reality - Expectation|

Reference: Task-040 Memory Module Optimization
"""

from typing import Dict, Any, Optional


class EMAPredictor:
    """
    Exponential Moving Average predictor for environmental state tracking.

    Tracks expectations for a single variable and computes prediction error
    (surprise) when observations deviate from expectations.

    Formula:
        E_t = (alpha * R_t) + ((1 - alpha) * E_{t-1})

    Where:
    - E_t = Current expectation
    - R_t = Current reality (observed value)
    - alpha = Smoothing factor (higher = faster adaptation)

    Args:
        alpha: Smoothing factor [0-1]. Higher values = faster adaptation.
               0.1 = High inertia (slow adaptation)
               0.5 = Balanced
               0.9 = Fast adaptation
        initial_value: Starting expectation value
    """

    def __init__(self, alpha: float = 0.3, initial_value: float = 0.0):
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        self.alpha = alpha
        self.expectation = initial_value
        self._initialized = False

    def update(self, reality: float) -> float:
        """
        Update expectation based on observed reality.

        Args:
            reality: The observed value from the environment

        Returns:
            The updated expectation value
        """
        if not self._initialized:
            self.expectation = reality * self.alpha
            self._initialized = True
        else:
            self.expectation = (self.alpha * reality) + ((1 - self.alpha) * self.expectation)
        return self.expectation

    def predict(self) -> float:
        """Return current expectation (prediction for next observation)."""
        return self.expectation

    def surprise(self, reality: float) -> float:
        """
        Calculate surprise (prediction error) given an observation.

        Surprise = |Reality - Expectation|

        Args:
            reality: The observed value

        Returns:
            Absolute prediction error (non-negative)
        """
        return abs(reality - self.expectation)

    def reset(self, initial_value: float = 0.0) -> None:
        """Reset predictor state."""
        self.expectation = initial_value
        self._initialized = False


class EMASurpriseStrategy:
    """
    EMA-based surprise strategy (from v3 Universal Cognitive Engine).

    Tracks a single environmental variable using EMA and computes
    surprise as the prediction error between reality and expectation.

    This is the "scalar mode" surprise calculation that provides
    continuous surprise values based on how much reality deviates
    from learned expectations.

    Features:
    - Gradual adaptation to repeated stimuli ("boiling frog" normalization)
    - Configurable responsiveness via alpha parameter
    - Simple, interpretable surprise calculation

    Args:
        stimulus_key: Key to extract from world_state dict (e.g., "flood_depth")
        alpha: EMA smoothing factor [0-1]
        initial_expectation: Starting expectation value
        normalize_range: Optional (min, max) to normalize surprise to [0, 1]

    Example:
        >>> strategy = EMASurpriseStrategy(
        ...     stimulus_key="flood_depth",
        ...     alpha=0.3
        ... )
        >>> surprise = strategy.update({"flood_depth": 2.5})
        >>> print(f"Surprise: {surprise:.2f}")
    """

    def __init__(
        self,
        stimulus_key: str = "flood_depth",
        alpha: float = 0.3,
        initial_expectation: float = 0.0,
        normalize_range: Optional[tuple] = None,
    ):
        self.stimulus_key = stimulus_key
        self.alpha = alpha
        self.normalize_range = normalize_range

        self._predictor = EMAPredictor(alpha=alpha, initial_value=initial_expectation)
        self._last_reality: Optional[float] = None
        self._last_expectation: Optional[float] = None
        self._last_surprise: float = 0.0

    def _extract_value(self, observation: Dict[str, Any]) -> float:
        """Extract stimulus value from observation dict."""
        value = observation.get(self.stimulus_key, 0.0)
        return float(value) if value is not None else 0.0

    def _normalize_surprise(self, raw_surprise: float) -> float:
        """Normalize surprise to [0, 1] range if normalize_range is set."""
        if self.normalize_range is None:
            # Default: assume max reasonable surprise is 10.0
            return min(1.0, raw_surprise / 10.0)

        min_val, max_val = self.normalize_range
        range_size = max_val - min_val
        if range_size <= 0:
            return 0.0
        normalized = raw_surprise / range_size
        return min(1.0, max(0.0, normalized))

    def update(self, observation: Dict[str, Any]) -> float:
        """
        Update internal state and return surprise.

        Args:
            observation: Dict containing stimulus key-value

        Returns:
            Normalized surprise value [0-1]
        """
        reality = self._extract_value(observation)

        # Capture current expectation BEFORE update
        self._last_expectation = self._predictor.predict()

        # Calculate surprise
        raw_surprise = self._predictor.surprise(reality)

        # Update expectation
        self._predictor.update(reality)

        # Store for trace
        self._last_reality = reality
        self._last_surprise = self._normalize_surprise(raw_surprise)

        return self._last_surprise

    def get_surprise(self, observation: Dict[str, Any]) -> float:
        """
        Calculate surprise WITHOUT updating internal state.

        Args:
            observation: Dict containing stimulus key-value

        Returns:
            Normalized surprise value [0-1]
        """
        reality = self._extract_value(observation)
        raw_surprise = self._predictor.surprise(reality)
        return self._normalize_surprise(raw_surprise)

    def get_arousal(self) -> float:
        """Get last computed surprise (arousal level)."""
        return self._last_surprise

    def get_trace(self) -> Optional[Dict[str, Any]]:
        """
        Get trace data for explainability.

        Returns:
            Dict with:
            - stimulus_key: The tracked variable name
            - reality: Last observed value
            - expectation: Expectation before observation
            - surprise: Normalized surprise value
            - alpha: EMA smoothing factor
        """
        if self._last_reality is None:
            return None

        return {
            "strategy": "EMA",
            "stimulus_key": self.stimulus_key,
            "reality": self._last_reality,
            "expectation": self._last_expectation,
            "surprise": self._last_surprise,
            "alpha": self.alpha,
        }

    def reset(self) -> None:
        """Reset strategy state for new simulation."""
        self._predictor.reset()
        self._last_reality = None
        self._last_expectation = None
        self._last_surprise = 0.0
