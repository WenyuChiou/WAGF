"""
Hybrid Surprise Strategy - Combines EMA and Symbolic approaches.

Provides a weighted combination of continuous EMA-based surprise
and discrete symbolic novelty detection for robust arousal computation.

Reference: Task-040 Memory Module Optimization
"""

from typing import Dict, Any, Optional, List

from .ema import EMASurpriseStrategy
from .symbolic import SymbolicSurpriseStrategy, Sensor


class HybridSurpriseStrategy:
    """
    Hybrid surprise strategy combining EMA and Symbolic approaches.

    Computes weighted surprise from both:
    - EMA: Continuous tracking of primary stimulus
    - Symbolic: Discrete multi-variate novelty detection

    This provides robustness by capturing both:
    - Gradual deviations (EMA captures "something feels off")
    - Novel state combinations (Symbolic captures "never seen this before")

    Args:
        ema_weight: Weight for EMA surprise [0-1]
        symbolic_weight: Weight for Symbolic surprise [0-1]
        ema_stimulus_key: Key for EMA tracking
        ema_alpha: EMA smoothing factor
        sensors: Sensors for Symbolic strategy

    Note:
        Weights are normalized to sum to 1.0 internally.

    Example:
        >>> strategy = HybridSurpriseStrategy(
        ...     ema_weight=0.6,
        ...     symbolic_weight=0.4,
        ...     ema_stimulus_key="flood_depth",
        ...     sensors=[flood_sensor, panic_sensor]
        ... )
        >>> surprise = strategy.update(world_state)
    """

    def __init__(
        self,
        ema_weight: float = 0.6,
        symbolic_weight: float = 0.4,
        ema_stimulus_key: str = "flood_depth",
        ema_alpha: float = 0.3,
        sensors: Optional[List[Sensor]] = None,
    ):
        # Normalize weights
        total = ema_weight + symbolic_weight
        self.ema_weight = ema_weight / total
        self.symbolic_weight = symbolic_weight / total

        # Initialize sub-strategies
        self._ema = EMASurpriseStrategy(
            stimulus_key=ema_stimulus_key,
            alpha=ema_alpha
        )
        self._symbolic = SymbolicSurpriseStrategy(
            sensors=sensors,
            default_sensor_key=ema_stimulus_key
        )

        self._last_ema_surprise: float = 0.0
        self._last_symbolic_surprise: float = 0.0
        self._last_combined_surprise: float = 0.0

    def update(self, observation: Dict[str, Any]) -> float:
        """
        Update both strategies and return weighted surprise.

        Args:
            observation: World state dict

        Returns:
            Weighted combined surprise [0-1]
        """
        self._last_ema_surprise = self._ema.update(observation)
        self._last_symbolic_surprise = self._symbolic.update(observation)

        self._last_combined_surprise = (
            self.ema_weight * self._last_ema_surprise +
            self.symbolic_weight * self._last_symbolic_surprise
        )

        return self._last_combined_surprise

    def get_surprise(self, observation: Dict[str, Any]) -> float:
        """Calculate surprise WITHOUT updating internal state."""
        ema_surprise = self._ema.get_surprise(observation)
        symbolic_surprise = self._symbolic.get_surprise(observation)

        return (
            self.ema_weight * ema_surprise +
            self.symbolic_weight * symbolic_surprise
        )

    def get_arousal(self) -> float:
        """Get last combined arousal level."""
        return self._last_combined_surprise

    def get_trace(self) -> Optional[Dict[str, Any]]:
        """Get combined trace from both strategies."""
        ema_trace = self._ema.get_trace()
        symbolic_trace = self._symbolic.get_trace()

        if not ema_trace and not symbolic_trace:
            return None

        return {
            "strategy": "Hybrid",
            "ema_weight": self.ema_weight,
            "symbolic_weight": self.symbolic_weight,
            "ema_surprise": self._last_ema_surprise,
            "symbolic_surprise": self._last_symbolic_surprise,
            "combined_surprise": self._last_combined_surprise,
            "ema_trace": ema_trace,
            "symbolic_trace": symbolic_trace,
        }

    def reset(self) -> None:
        """Reset both sub-strategies."""
        self._ema.reset()
        self._symbolic.reset()
        self._last_ema_surprise = 0.0
        self._last_symbolic_surprise = 0.0
        self._last_combined_surprise = 0.0
