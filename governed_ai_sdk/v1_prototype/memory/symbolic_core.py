"""
Symbolic Context Core - Multi-variate frequency-based surprise detection.

Core primitives for symbolic memory:
- Sensor: Quantizes continuous values into discrete symbols
- SignatureEngine: Fuses sensor outputs into unique state hashes
- SymbolicContextMonitor: Frequency-based novelty/surprise detection

These are domain-agnostic primitives that can be used across any domain
(flood, finance, education, health, etc.).

Reference: Task-037 SDK Architecture Refactor
"""
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any
import hashlib


@dataclass
class Sensor:
    """
    Quantizes a continuous value into a discrete bin label.

    This is a core primitive that transforms continuous sensor readings
    into symbolic representations for pattern matching.

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
    path: str          # Path to value in world state (e.g., "flood_depth", "agent.savings")
    name: str          # Sensor name for symbolic output (e.g., "FLOOD", "SAVINGS")
    bins: List[Dict]   # Quantization bins: [{"label": str, "max": float}, ...]

    def quantize(self, value: float) -> str:
        """
        Convert continuous value to symbolic label.

        Args:
            value: Continuous value to quantize

        Returns:
            String in format "NAME:LABEL" (e.g., "FLOOD:SEVERE")
        """
        for bin_def in self.bins:
            if value <= bin_def["max"]:
                return f"{self.name}:{bin_def['label']}"
        return f"{self.name}:UNKNOWN"


class SignatureEngine:
    """
    Fuses multiple sensor outputs into a unique state signature (hash).

    Creates a compact, comparable representation of multi-dimensional
    symbolic state for efficient novelty detection.

    Example:
        >>> sensors = [flood_sensor, panic_sensor]
        >>> engine = SignatureEngine(sensors)
        >>> sig = engine.compute_signature({"flood_depth": 2.0, "panic_level": 0.8})
        >>> print(sig)  # "a1b2c3d4e5f6..."
    """

    def __init__(self, sensors: List[Sensor]):
        """
        Initialize with list of sensors.

        Args:
            sensors: List of Sensor objects that define state dimensions
        """
        self.sensors = sensors

    def _extract_value(self, data: Dict[str, Any], path: str) -> float:
        """
        Extract value from nested dict using dot notation.

        Args:
            data: Source dictionary (e.g., world_state)
            path: Dot-separated path (e.g., "agent.finances.savings")

        Returns:
            Extracted float value, or 0.0 if not found
        """
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, 0.0)
            else:
                break
        return float(current) if current else 0.0

    def compute_signature(self, world_state: Dict[str, Any]) -> str:
        """
        Compute unique hash signature from current world state.

        Args:
            world_state: Dictionary containing sensor values

        Returns:
            16-character hex hash representing the symbolic state
        """
        symbols = []
        for sensor in self.sensors:
            value = self._extract_value(world_state, sensor.path)
            symbols.append(sensor.quantize(value))
        symbol_str = "|".join(sorted(symbols))
        return hashlib.sha256(symbol_str.encode()).hexdigest()[:16]

    def get_quantized_state(self, world_state: Dict[str, Any]) -> Dict[str, str]:
        """
        Get quantized symbols for all sensors (for explainability).

        Args:
            world_state: Dictionary containing sensor values

        Returns:
            Dict mapping sensor names to their quantized labels
        """
        result = {}
        for sensor in self.sensors:
            value = self._extract_value(world_state, sensor.path)
            result[sensor.name] = sensor.quantize(value)
        return result


class SymbolicContextMonitor:
    """
    Frequency-based surprise/novelty detection with full trace capture.

    Implements novelty-first logic:
    - First occurrence of any state signature = 100% surprise (System 2)
    - Repeated signatures have lower surprise based on frequency

    Designed for XAI-ABM integration with full observability.

    Example:
        >>> monitor = SymbolicContextMonitor(sensors, arousal_threshold=0.5)
        >>> sig, surprise = monitor.observe({"flood_depth": 3.0})
        >>> print(f"Surprise: {surprise:.0%}")  # "Surprise: 100%" for novel state
        >>> system = monitor.determine_system(surprise)  # "SYSTEM_2"
    """

    def __init__(self, sensors: List[Sensor], arousal_threshold: float = 0.5):
        """
        Initialize monitor with sensors and cognitive threshold.

        Args:
            sensors: List of Sensor objects defining observed dimensions
            arousal_threshold: Surprise level that triggers System 2 (default: 0.5)
        """
        self.signature_engine = SignatureEngine(sensors)
        self.frequency_map: Dict[str, int] = {}
        self.total_events: int = 0
        self.arousal_threshold = arousal_threshold

        # Trace history for explainability
        self._trace_history: List[Dict] = []
        self._last_trace: Optional[Dict] = None

    def observe(self, world_state: Dict[str, Any]) -> Tuple[str, float]:
        """
        Observe world state and compute surprise.

        Implements novelty-first logic: first occurrence = MAX surprise (1.0).

        Args:
            world_state: Current world state dictionary

        Returns:
            Tuple of (signature, surprise) where:
            - signature: 16-char hex hash of symbolic state
            - surprise: 0.0-1.0 surprise score (1.0 = completely novel)
        """
        # Step 1: Quantize sensors (capture for trace)
        quantized = self.signature_engine.get_quantized_state(world_state)

        # Step 2: Compute signature
        sig = self.signature_engine.compute_signature(world_state)

        # Step 3: Novelty-first check (BEFORE counting)
        is_novel = sig not in self.frequency_map
        prior_count = self.frequency_map.get(sig, 0)
        prior_frequency = prior_count / self.total_events if self.total_events > 0 else None

        if is_novel:
            surprise = 1.0
            self.frequency_map[sig] = 1
        else:
            frequency = prior_count / self.total_events if self.total_events > 0 else 0.0
            surprise = 1.0 - frequency
            self.frequency_map[sig] += 1

        self.total_events += 1

        # Step 4: Capture trace for explainability
        self._last_trace = {
            "quantized_sensors": quantized,
            "signature": sig,
            "is_novel": is_novel,
            "prior_frequency": prior_frequency,
            "surprise": surprise,
            "frequency_map_size": len(self.frequency_map),
            "total_events": self.total_events
        }
        self._trace_history.append(self._last_trace.copy())

        return sig, surprise

    def determine_system(self, surprise: float) -> str:
        """
        Determine cognitive system based on surprise level.

        Args:
            surprise: Surprise value from observe()

        Returns:
            "SYSTEM_1" for routine (low surprise) or
            "SYSTEM_2" for crisis (high surprise)
        """
        return "SYSTEM_2" if surprise > self.arousal_threshold else "SYSTEM_1"

    def get_last_trace(self) -> Optional[Dict]:
        """Return the last observation trace for logging/analysis."""
        return self._last_trace

    def get_trace_history(self) -> List[Dict]:
        """Return full trace history for post-hoc analysis."""
        return self._trace_history.copy()

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
        """Reset frequency map and trace history (for new simulation runs)."""
        self.frequency_map.clear()
        self.total_events = 0
        self._trace_history.clear()
        self._last_trace = None


# Type aliases for convenience
SensorConfig = Sensor  # Alias for backward compatibility
