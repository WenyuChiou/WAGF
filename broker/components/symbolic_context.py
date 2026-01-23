from dataclasses import dataclass
from typing import List, Dict, Tuple
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
    """Frequency-based surprise detection (System 1/2 switch)."""

    def __init__(self, sensors: List[Sensor], arousal_threshold: float = 0.5):
        self.signature_engine = SignatureEngine(sensors)
        self.frequency_map: Dict[str, int] = {}
        self.total_events: int = 0
        self.arousal_threshold = arousal_threshold

    def observe(self, world_state: Dict) -> Tuple[str, float]:
        sig = self.signature_engine.compute_signature(world_state)

        # Novelty-first: check before counting.
        is_novel = sig not in self.frequency_map

        if is_novel:
            surprise = 1.0
            self.frequency_map[sig] = 1
        else:
            prior_count = self.frequency_map[sig]
            frequency = prior_count / self.total_events if self.total_events > 0 else 0.0
            surprise = 1.0 - frequency
            self.frequency_map[sig] += 1

        self.total_events += 1
        return sig, surprise

    def determine_system(self, surprise: float) -> str:
        return "SYSTEM_2" if surprise > self.arousal_threshold else "SYSTEM_1"
