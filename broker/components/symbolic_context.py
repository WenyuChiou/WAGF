"""
Symbolic Context Engine v4.0 - Multi-variate frequency-based surprise detection.

Replaces scalar EMA-based surprise with signature-based novelty detection.
Includes full tracing for XAI-ABM integration (Task-031C).
"""
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import hashlib


@dataclass
class Sensor:
    """Quantizes a continuous value into a discrete bin label."""

    path: str
    name: str
    bins: List[Dict]

    def quantize(self, value: float) -> str:
        for bin_def in self.bins:
            if value <= bin_def["max"]:
                return f"{self.name}:{bin_def['label']}"
        return f"{self.name}:UNKNOWN"


class SignatureEngine:
    """Fuses sensor outputs into a unique state hash."""

    def __init__(self, sensors: List[Sensor]):
        self.sensors = sensors

    def _extract_value(self, data: Dict, path: str) -> float:
        """Extract value from nested dict using dot notation."""
        keys = path.split(".")
        for key in keys:
            data = data.get(key, 0.0)
            if not isinstance(data, dict):
                break
        return float(data) if data else 0.0

    def compute_signature(self, world_state: Dict) -> str:
        symbols = []
        for sensor in self.sensors:
            value = self._extract_value(world_state, sensor.path)
            symbols.append(sensor.quantize(value))
        symbol_str = "|".join(sorted(symbols))
        return hashlib.sha256(symbol_str.encode()).hexdigest()[:16]


class SymbolicContextMonitor:
    """Frequency-based surprise detection with full trace capture (XAI-ABM)."""

    def __init__(self, sensors: List[Sensor], arousal_threshold: float = 0.5):
        self.signature_engine = SignatureEngine(sensors)
        self.frequency_map: Dict[str, int] = {}
        self.total_events: int = 0
        self.arousal_threshold = arousal_threshold

        # Trace history for explainability (Task-031C)
        self._trace_history: List[Dict] = []
        self._last_trace: Optional[Dict] = None

    def observe(self, world_state: Dict) -> Tuple[str, float]:
        """
        Returns (signature, surprise) with full trace capture.

        Implements Novelty-First logic: first occurrence = MAX surprise (1.0).
        """
        # Step 1: Quantize sensors (capture for trace)
        quantized = {}
        for sensor in self.signature_engine.sensors:
            value = self.signature_engine._extract_value(world_state, sensor.path)
            quantized[sensor.name] = sensor.quantize(value)

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
        """Returns SYSTEM_1 (routine) or SYSTEM_2 (crisis) based on surprise."""
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
