"""
Symbolic Context Memory Layer for SDK.

Provides O(1) state signature lookup and novelty-first surprise detection.
Core primitives are defined in symbolic_core.py (domain-agnostic).

Task-037: Fixed SDK -> broker dependency violation
"""

from typing import Dict, List, Optional, Tuple, Any

# Import from SDK core (NOT from broker - maintains clean dependency)
from .symbolic_core import (
    Sensor,
    SignatureEngine,
    SymbolicContextMonitor,
)

__all__ = [
    "Sensor",
    "SignatureEngine",
    "SymbolicContextMonitor",
    "SymbolicMemory",
]


class SymbolicMemory:
    """
    SDK-friendly wrapper for SymbolicContextMonitor.

    Provides O(1) state signature lookup and novelty-first surprise detection.
    This is the main interface for SDK users who want symbolic memory capabilities.

    Example:
        >>> sensors = [
        ...     {"path": "flood", "name": "FLOOD", "bins": [
        ...         {"label": "SAFE", "max": 0.5},
        ...         {"label": "DANGER", "max": 99.0}
        ...     ]}
        ... ]
        >>> memory = SymbolicMemory(sensors, arousal_threshold=0.5)
        >>> sig, surprise = memory.observe({"flood": 2.0})
        >>> print(f"Surprise: {surprise:.0%}")  # 100% for novel state
    """

    def __init__(
        self,
        sensors: List[Dict[str, Any]],
        arousal_threshold: float = 0.5
    ):
        """
        Initialize symbolic memory.

        Args:
            sensors: List of Sensor configs. Each dict should have:
                - path: str - Path to value in world state (e.g., "flood_depth")
                - name: str - Name for the sensor (e.g., "FLOOD")
                - bins: List[Dict] - Quantization bins with "label" and "max" keys
            arousal_threshold: Threshold for System 1/2 switching (default 0.5)
        """
        # Convert dicts to Sensor objects if needed
        sensor_objs = []
        for s in sensors:
            if isinstance(s, dict):
                sensor_objs.append(Sensor(**s))
            elif isinstance(s, Sensor):
                sensor_objs.append(s)
            else:
                raise TypeError(f"Expected dict or Sensor, got {type(s)}")

        self._monitor = SymbolicContextMonitor(sensor_objs, arousal_threshold)
        self._arousal_threshold = arousal_threshold

    def observe(self, world_state: Dict[str, Any]) -> Tuple[str, float]:
        """
        Observe world state and compute surprise.

        Novelty-First Logic:
        - First occurrence of any signature = 100% surprise (System 2)
        - Repeated signatures have lower surprise based on frequency

        Args:
            world_state: Current world state dict (e.g., {"flood": 1.5, "panic": 0.8})

        Returns:
            (signature, surprise): State hash (16 chars) and surprise score (0.0-1.0)
        """
        return self._monitor.observe(world_state)

    def get_trace(self) -> Optional[Dict[str, Any]]:
        """
        Get the last observation trace for XAI/debugging.

        Returns:
            Dict with keys: quantized_sensors, signature, is_novel,
            prior_frequency, surprise, frequency_map_size, total_events
        """
        return self._monitor.get_last_trace()

    def get_trace_history(self) -> List[Dict[str, Any]]:
        """
        Get full trace history for analysis.

        Returns:
            List of all observation traces
        """
        return self._monitor.get_trace_history()

    def explain(self) -> str:
        """
        Human-readable explanation of last observation.

        Returns:
            String like "Sensors: {...} | Signature: abc123... | NOVEL STATE -> Surprise = 100%"
        """
        return self._monitor.explain_last()

    def determine_system(self, surprise: float) -> str:
        """
        Determine cognitive system based on surprise level.

        Args:
            surprise: Surprise value from observe()

        Returns:
            "SYSTEM_1" for routine (low surprise) or "SYSTEM_2" for crisis (high surprise)
        """
        return self._monitor.determine_system(surprise)

    @property
    def frequency_map(self) -> Dict[str, int]:
        """Access the internal frequency map (signature -> count)."""
        return self._monitor.frequency_map

    @property
    def total_events(self) -> int:
        """Total number of observations made."""
        return self._monitor.total_events

    @property
    def arousal_threshold(self) -> float:
        """Current arousal threshold for System 1/2 switching."""
        return self._arousal_threshold

    def reset(self) -> None:
        """Reset the memory (clear frequency map and history)."""
        self._monitor.frequency_map.clear()
        self._monitor.total_events = 0
        self._monitor._trace_history.clear()
        self._monitor._last_trace = None
