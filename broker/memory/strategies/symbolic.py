"""
Symbolic Surprise Strategy - Frequency-based novelty detection.

Extracted and refactored from v4 SymbolicContextMonitor.

Uses multi-variate sensor quantization and signature hashing
for discrete state representation and novelty-first surprise.

Reference: Task-040 Memory Module Optimization
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
import hashlib


@dataclass
class Sensor:
    """
    Quantizes a continuous value into a discrete bin label.

    This is a core primitive that transforms continuous sensor readings
    into symbolic representations for pattern matching.

    Attributes:
        path: Path to value in world state (e.g., "flood_depth", "agent.savings")
        name: Sensor name for symbolic output (e.g., "FLOOD", "SAVINGS")
        bins: Quantization bins: [{"label": str, "max": float}, ...]

    Example:
        >>> sensor = Sensor(
        ...     path="flood_depth",
        ...     name="FLOOD",
        ...     bins=[
        ...         {"label": "SAFE", "max": 0.3},
        ...         {"label": "MINOR", "max": 1.0},
        ...         {"label": "MODERATE", "max": 2.0},
        ...         {"label": "SEVERE", "max": 99.0}
        ...     ]
        ... )
        >>> sensor.quantize(1.5)
        'FLOOD:MODERATE'
    """
    path: str
    name: str
    bins: List[Dict]

    def quantize(self, value: float) -> str:
        """Convert continuous value to symbolic label."""
        for bin_def in self.bins:
            if value <= bin_def["max"]:
                return f"{self.name}:{bin_def['label']}"
        return f"{self.name}:UNKNOWN"


class SignatureEngine:
    """
    Fuses multiple sensor outputs into a unique state signature (hash).

    Creates a compact, comparable representation of multi-dimensional
    symbolic state for efficient novelty detection.

    Args:
        sensors: List of Sensor objects defining state dimensions
    """

    def __init__(self, sensors: List[Sensor]):
        self.sensors = sensors

    def _extract_value(self, data: Dict[str, Any], path: str) -> float:
        """Extract value from nested dict using dot notation."""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, 0.0)
            else:
                break
        return float(current) if current else 0.0

    def compute_signature(self, world_state: Dict[str, Any]) -> str:
        """Compute unique hash signature from current world state."""
        symbols = []
        for sensor in self.sensors:
            value = self._extract_value(world_state, sensor.path)
            symbols.append(sensor.quantize(value))
        symbol_str = "|".join(sorted(symbols))
        return hashlib.sha256(symbol_str.encode()).hexdigest()[:16]

    def get_quantized_state(self, world_state: Dict[str, Any]) -> Dict[str, str]:
        """Get quantized symbols for all sensors (for explainability)."""
        result = {}
        for sensor in self.sensors:
            value = self._extract_value(world_state, sensor.path)
            result[sensor.name] = sensor.quantize(value)
        return result


class SymbolicSurpriseStrategy:
    """
    Frequency-based symbolic surprise strategy (from v4).

    Uses multi-variate sensor quantization and signature hashing for
    discrete state novelty detection. Implements novelty-first logic:
    - First occurrence of any state signature = 100% surprise
    - Repeated signatures have lower surprise based on frequency

    Features:
    - Multi-dimensional state tracking
    - Discrete, interpretable state symbols
    - Zero surprise for familiar states, max for novel
    - Full trace capture for XAI

    Args:
        sensors: List of Sensor configs or dicts
        default_sensor_key: If no sensors provided, use this key with default bins

    Example:
        >>> sensors = [
        ...     Sensor(path="flood_depth", name="FLOOD", bins=[...]),
        ...     Sensor(path="panic_level", name="PANIC", bins=[...])
        ... ]
        >>> strategy = SymbolicSurpriseStrategy(sensors=sensors)
        >>> surprise = strategy.update({"flood_depth": 3.0, "panic_level": 0.8})
    """

    # Default bins for common variables
    DEFAULT_BINS = {
        "flood_depth": [
            {"label": "NONE", "max": 0.0},
            {"label": "MINOR", "max": 0.5},
            {"label": "MODERATE", "max": 1.5},
            {"label": "SEVERE", "max": 3.0},
            {"label": "EXTREME", "max": 999.0},
        ],
        "panic_level": [
            {"label": "CALM", "max": 0.2},
            {"label": "CONCERNED", "max": 0.5},
            {"label": "ANXIOUS", "max": 0.8},
            {"label": "PANICKED", "max": 1.0},
        ],
    }

    def __init__(
        self,
        sensors: Optional[List[Sensor]] = None,
        default_sensor_key: str = "flood_depth",
    ):
        # Build sensors from config or use default
        if sensors:
            self._sensors = [
                s if isinstance(s, Sensor) else Sensor(**s)
                for s in sensors
            ]
        else:
            # Create default sensor
            default_bins = self.DEFAULT_BINS.get(
                default_sensor_key,
                self.DEFAULT_BINS["flood_depth"]
            )
            self._sensors = [
                Sensor(
                    path=default_sensor_key,
                    name=default_sensor_key.upper().replace("_", ""),
                    bins=default_bins
                )
            ]

        self._signature_engine = SignatureEngine(self._sensors)
        self._frequency_map: Dict[str, int] = {}
        self._total_events: int = 0
        self._last_trace: Optional[Dict[str, Any]] = None

    def update(self, observation: Dict[str, Any]) -> float:
        """
        Update frequency map and return surprise.

        Implements novelty-first logic: first occurrence = max surprise.

        Args:
            observation: World state dict with sensor values

        Returns:
            Surprise value [0-1] where 1.0 = completely novel
        """
        # Quantize sensors
        quantized = self._signature_engine.get_quantized_state(observation)

        # Compute signature
        sig = self._signature_engine.compute_signature(observation)

        # Novelty-first check (BEFORE counting)
        is_novel = sig not in self._frequency_map
        prior_count = self._frequency_map.get(sig, 0)
        prior_frequency = prior_count / self._total_events if self._total_events > 0 else None

        if is_novel:
            surprise = 1.0
            self._frequency_map[sig] = 1
        else:
            frequency = prior_count / self._total_events if self._total_events > 0 else 0.0
            surprise = 1.0 - frequency
            self._frequency_map[sig] += 1

        self._total_events += 1

        # Capture trace
        self._last_trace = {
            "strategy": "Symbolic",
            "quantized_sensors": quantized,
            "signature": sig,
            "is_novel": is_novel,
            "prior_frequency": prior_frequency,
            "surprise": surprise,
            "frequency_map_size": len(self._frequency_map),
            "total_events": self._total_events,
        }

        return surprise

    def get_surprise(self, observation: Dict[str, Any]) -> float:
        """
        Calculate surprise WITHOUT updating frequency map.

        Args:
            observation: World state dict

        Returns:
            Surprise value [0-1]
        """
        sig = self._signature_engine.compute_signature(observation)
        is_novel = sig not in self._frequency_map

        if is_novel:
            return 1.0

        prior_count = self._frequency_map.get(sig, 0)
        frequency = prior_count / self._total_events if self._total_events > 0 else 0.0
        return 1.0 - frequency

    def get_arousal(self) -> float:
        """Get last computed surprise (arousal level)."""
        if self._last_trace:
            return self._last_trace.get("surprise", 0.0)
        return 0.0

    def get_trace(self) -> Optional[Dict[str, Any]]:
        """Get trace data for explainability."""
        return self._last_trace

    def explain_last(self) -> str:
        """Human-readable explanation of last observation."""
        if not self._last_trace:
            return "No observations yet."

        t = self._last_trace
        lines = [
            f"Sensors: {t['quantized_sensors']}",
            f"Signature: {t['signature'][:8]}...",
        ]

        if t['is_novel']:
            lines.append("NOVEL STATE -> Surprise = 100%")
        else:
            freq_str = f"{t['prior_frequency']:.1%}" if t['prior_frequency'] is not None else "N/A"
            lines.append(f"Seen {freq_str} of the time -> Surprise = {t['surprise']:.1%}")

        return " | ".join(lines)

    def reset(self) -> None:
        """Reset strategy state for new simulation."""
        self._frequency_map.clear()
        self._total_events = 0
        self._last_trace = None
