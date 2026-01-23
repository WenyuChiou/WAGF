import unittest
import sys
from pathlib import Path

# Adjust path to import broker package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.components.symbolic_context import Sensor, SignatureEngine, SymbolicContextMonitor


class TestSensor(unittest.TestCase):
    def test_quantize(self):
        sensor = Sensor(
            path="x",
            name="X",
            bins=[
                {"label": "LOW", "max": 0.5},
                {"label": "HIGH", "max": 1.0},
            ],
        )
        self.assertEqual(sensor.quantize(0.3), "X:LOW")
        self.assertEqual(sensor.quantize(0.8), "X:HIGH")
        self.assertEqual(sensor.quantize(2.0), "X:UNKNOWN")


class TestSignatureEngine(unittest.TestCase):
    def test_hash_deterministic(self):
        sensors = [
            Sensor(path="a", name="A", bins=[{"label": "LO", "max": 0.0}, {"label": "HI", "max": 10.0}]),
            Sensor(path="b", name="B", bins=[{"label": "LO", "max": 0.0}, {"label": "HI", "max": 10.0}]),
        ]
        engine = SignatureEngine(sensors)
        state = {"a": 1.0, "b": 2.0}
        sig1 = engine.compute_signature(state)
        sig2 = engine.compute_signature(state)
        self.assertEqual(sig1, sig2)


class TestSymbolicContextMonitor(unittest.TestCase):
    def setUp(self):
        sensor = Sensor(path="x", name="X", bins=[{"label": "LO", "max": 0.5}, {"label": "HI", "max": 99.0}])
        self.monitor = SymbolicContextMonitor([sensor], arousal_threshold=0.5)

    def test_frequency_surprise(self):
        sig1, s1 = self.monitor.observe({"x": 0.8})
        self.assertEqual(s1, 1.0)

        sig2, s2 = self.monitor.observe({"x": 0.8})
        self.assertEqual(sig1, sig2)
        self.assertLess(s2, 1.0)

        sig3, s3 = self.monitor.observe({"x": 0.3})
        self.assertNotEqual(sig1, sig3)
        self.assertEqual(s3, 1.0)

    def test_system_switch(self):
        self.assertEqual(self.monitor.determine_system(0.6), "SYSTEM_2")
        self.assertEqual(self.monitor.determine_system(0.4), "SYSTEM_1")


if __name__ == '__main__':
    unittest.main()
