import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.components.symbolic_context import Sensor, SignatureEngine, SymbolicContextMonitor


def test_sensor_quantize_flood_depth():
    sensor = Sensor(
        path="flood_depth",
        name="FLOOD",
        bins=[{"label": "SAFE", "max": 0.1}, {"label": "MAJOR", "max": 99.9}],
    )
    assert sensor.quantize(0.05) == "FLOOD:SAFE"
    assert sensor.quantize(1.5) == "FLOOD:MAJOR"


def test_signature_hash_deterministic():
    sensors = [
        Sensor(path="a", name="A", bins=[{"label": "LO", "max": 0.0}, {"label": "HI", "max": 10.0}]),
        Sensor(path="b", name="B", bins=[{"label": "LO", "max": 0.0}, {"label": "HI", "max": 10.0}]),
    ]
    engine = SignatureEngine(sensors)
    state = {"a": 1.0, "b": 2.0}
    assert engine.compute_signature(state) == engine.compute_signature(state)


def test_novelty_first_logic():
    sensors = [Sensor(path="flood", name="FLOOD", bins=[{"label": "LO", "max": 1}, {"label": "HI", "max": 99}])]
    monitor = SymbolicContextMonitor(sensors, arousal_threshold=0.5)

    sig1, surp1 = monitor.observe({"flood": 5.0})
    assert surp1 == 1.0
    assert monitor.determine_system(surp1) == "SYSTEM_2"

    sig2, surp2 = monitor.observe({"flood": 5.0})
    assert sig2 == sig1
    assert surp2 < 1.0

    sig3, surp3 = monitor.observe({"flood": 0.5})
    assert sig3 != sig1
    assert surp3 == 1.0

    sig4, surp4 = monitor.observe({"flood": 5.0})
    assert surp4 < 1.0
