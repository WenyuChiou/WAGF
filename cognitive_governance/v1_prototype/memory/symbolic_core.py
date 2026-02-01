"""
Symbolic Context Core - Multi-variate frequency-based surprise detection.

Core primitives for symbolic memory:
- Sensor: Quantizes continuous values into discrete symbols
- SignatureEngine: Fuses sensor outputs into unique state hashes
- SymbolicContextMonitor: Frequency-based novelty/surprise detection

Sensor and SignatureEngine are canonical in
``cognitive_governance.memory.strategies.symbolic`` and re-exported here
for backward compatibility.

Reference: Task-037 SDK Architecture Refactor
"""
from typing import List, Dict, Tuple, Optional, Any

# Canonical source for Sensor and SignatureEngine
from cognitive_governance.memory.strategies.symbolic import Sensor, SignatureEngine


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
