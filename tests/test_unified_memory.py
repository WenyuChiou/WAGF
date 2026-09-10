"""
Unit tests for the pluggable surprise strategies (EMA / Symbolic / Hybrid).

Tests:
- EMASurpriseStrategy (EMA formula, surprise calculation)
- SymbolicSurpriseStrategy (novelty-first logic)
- HybridSurpriseStrategy (weighted combination)

Org-3 note (2026-09): this file used to also cover UnifiedMemoryStore /
AdaptiveRetrievalEngine / UnifiedCognitiveEngine / UnifiedMemoryItem —
all deleted as dead code (no production importer, only this test).
Those classes' tests were removed with them; the strategy tests below
are unaffected (EMASurpriseStrategy / SymbolicSurpriseStrategy /
HybridSurpriseStrategy remain live, consumed by
broker.components.memory.engines.humancentric and
broker.components.memory.universal).

Reference: Task-040 Memory Module Optimization
"""

import unittest
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

# Adjust path to import cognitive_governance
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.memory import (
    EMASurpriseStrategy,
    SymbolicSurpriseStrategy,
    HybridSurpriseStrategy,
)
from broker.memory.strategies.ema import EMAPredictor
from broker.memory.strategies.symbolic import Sensor, SignatureEngine


class TestEMAPredictor(unittest.TestCase):
    """Test EMA predictor formula correctness."""

    def test_ema_update_formula_alpha_05(self):
        """Verify EMA formula: E_t = (alpha * R) + ((1-alpha) * E_{t-1})."""
        # alpha=0.5 means equal weighting of old and new
        predictor = EMAPredictor(alpha=0.5, initial_value=0.0)

        # First update: E_0=0, R_1=10 -> E_1 = 0.5*10 + 0.5*0 = 5
        predictor.update(10.0)
        self.assertAlmostEqual(predictor.predict(), 5.0, places=2)

    def test_ema_update_formula_alpha_01(self):
        """High inertia: slow adaptation."""
        predictor = EMAPredictor(alpha=0.1, initial_value=0.0)
        predictor.update(10.0)
        # E_1 = 0.1*10 + 0.9*0 = 1.0
        self.assertAlmostEqual(predictor.predict(), 1.0, places=2)

    def test_ema_convergence(self):
        """EMA should converge to constant stimulus over time."""
        predictor = EMAPredictor(alpha=0.3, initial_value=0.0)

        # Apply constant stimulus 20 times
        for _ in range(20):
            predictor.update(10.0)

        # Should converge close to 10.0
        self.assertAlmostEqual(predictor.predict(), 10.0, delta=0.5)

    def test_surprise_calculation(self):
        """Surprise = |Reality - Expectation|."""
        predictor = EMAPredictor(alpha=0.5, initial_value=5.0)

        # Reality=10, Expectation=5 -> Surprise=5
        surprise = predictor.surprise(10.0)
        self.assertAlmostEqual(surprise, 5.0)

    def test_invalid_alpha_raises(self):
        """Alpha must be in [0, 1]."""
        with self.assertRaises(ValueError):
            EMAPredictor(alpha=1.5)
        with self.assertRaises(ValueError):
            EMAPredictor(alpha=-0.1)


class TestEMASurpriseStrategy(unittest.TestCase):
    """Test EMA-based surprise strategy."""

    def test_basic_surprise_update(self):
        """Strategy should compute and return normalized surprise."""
        strategy = EMASurpriseStrategy(
            stimulus_key="flood_depth",
            alpha=0.5,
            initial_expectation=0.0
        )

        # First observation: large surprise
        surprise = strategy.update({"flood_depth": 5.0})
        self.assertGreater(surprise, 0.0)

    def test_repeated_stimulus_decreases_surprise(self):
        """Repeated same stimulus should decrease surprise (normalization)."""
        strategy = EMASurpriseStrategy(
            stimulus_key="flood_depth",
            alpha=0.5
        )

        # First observation
        s1 = strategy.update({"flood_depth": 5.0})

        # Repeat same stimulus multiple times
        for _ in range(10):
            strategy.update({"flood_depth": 5.0})

        # Final surprise should be low (expectation caught up)
        s_final = strategy.update({"flood_depth": 5.0})
        self.assertLess(s_final, s1)

    def test_get_surprise_no_update(self):
        """get_surprise() should not modify internal state."""
        strategy = EMASurpriseStrategy(stimulus_key="flood_depth", alpha=0.5)

        # Update once
        strategy.update({"flood_depth": 5.0})
        expectation_before = strategy._predictor.predict()

        # Call get_surprise multiple times
        strategy.get_surprise({"flood_depth": 10.0})
        strategy.get_surprise({"flood_depth": 10.0})

        # Expectation should not have changed
        expectation_after = strategy._predictor.predict()
        self.assertEqual(expectation_before, expectation_after)

    def test_trace_data(self):
        """Trace should capture observation details."""
        strategy = EMASurpriseStrategy(stimulus_key="flood_depth", alpha=0.3)
        strategy.update({"flood_depth": 2.0})

        trace = strategy.get_trace()
        self.assertIsNotNone(trace)
        self.assertEqual(trace["strategy"], "EMA")
        self.assertEqual(trace["stimulus_key"], "flood_depth")
        self.assertEqual(trace["reality"], 2.0)
        self.assertIn("expectation", trace)
        self.assertIn("surprise", trace)


class TestSensor(unittest.TestCase):
    """Test sensor quantization."""

    def test_quantization_bins(self):
        """Sensor should quantize values into correct bins."""
        sensor = Sensor(
            path="flood_depth",
            name="FLOOD",
            bins=[
                {"label": "NONE", "max": 0.0},
                {"label": "MINOR", "max": 0.5},
                {"label": "MODERATE", "max": 1.5},
                {"label": "SEVERE", "max": 3.0},
            ]
        )

        self.assertEqual(sensor.quantize(-0.1), "FLOOD:NONE")
        self.assertEqual(sensor.quantize(0.0), "FLOOD:NONE")
        self.assertEqual(sensor.quantize(0.3), "FLOOD:MINOR")
        self.assertEqual(sensor.quantize(1.0), "FLOOD:MODERATE")
        self.assertEqual(sensor.quantize(2.5), "FLOOD:SEVERE")

    def test_value_above_all_bins(self):
        """Values above all bins should return UNKNOWN."""
        sensor = Sensor(
            path="x",
            name="X",
            bins=[{"label": "LOW", "max": 1.0}]
        )
        self.assertEqual(sensor.quantize(5.0), "X:UNKNOWN")


class TestSymbolicSurpriseStrategy(unittest.TestCase):
    """Test symbolic novelty-first surprise strategy."""

    def test_novel_state_max_surprise(self):
        """First occurrence of state should be 100% surprise."""
        sensors = [
            Sensor(
                path="flood_depth",
                name="FLOOD",
                bins=[
                    {"label": "LOW", "max": 1.0},
                    {"label": "HIGH", "max": 99.0}
                ]
            )
        ]
        strategy = SymbolicSurpriseStrategy(sensors=sensors)

        # First observation: completely novel
        surprise = strategy.update({"flood_depth": 0.5})
        self.assertEqual(surprise, 1.0)

    def test_repeated_state_decreases_surprise(self):
        """Repeated same state should have lower surprise."""
        sensors = [
            Sensor(
                path="x",
                name="X",
                bins=[{"label": "A", "max": 1.0}, {"label": "B", "max": 99.0}]
            )
        ]
        strategy = SymbolicSurpriseStrategy(sensors=sensors)

        # First: novel
        s1 = strategy.update({"x": 0.5})
        self.assertEqual(s1, 1.0)

        # Second: seen before
        s2 = strategy.update({"x": 0.5})
        self.assertLess(s2, 1.0)

        # Third: even more familiar (or equal if at minimum)
        s3 = strategy.update({"x": 0.5})
        self.assertLessEqual(s3, s2)  # Can be equal at 0.0

    def test_different_states_all_novel(self):
        """Different states should all be novel initially."""
        sensors = [
            Sensor(
                path="x",
                name="X",
                bins=[{"label": "A", "max": 0.5}, {"label": "B", "max": 1.0}]
            )
        ]
        strategy = SymbolicSurpriseStrategy(sensors=sensors)

        # State A: novel
        self.assertEqual(strategy.update({"x": 0.3}), 1.0)
        # State B: also novel
        self.assertEqual(strategy.update({"x": 0.8}), 1.0)
        # State A again: not novel anymore
        self.assertLess(strategy.update({"x": 0.3}), 1.0)

    def test_trace_captures_novelty(self):
        """Trace should indicate if state was novel."""
        strategy = SymbolicSurpriseStrategy(default_sensor_key="flood_depth")

        strategy.update({"flood_depth": 1.0})
        trace = strategy.get_trace()

        self.assertIsNotNone(trace)
        self.assertEqual(trace["strategy"], "Symbolic")
        self.assertTrue(trace["is_novel"])

    def test_reset_clears_history(self):
        """Reset should clear frequency map."""
        strategy = SymbolicSurpriseStrategy(default_sensor_key="flood_depth")

        # Build up history
        strategy.update({"flood_depth": 1.0})
        strategy.update({"flood_depth": 1.0})
        self.assertLess(strategy.get_surprise({"flood_depth": 1.0}), 1.0)

        # Reset
        strategy.reset()

        # Same state should now be novel again
        self.assertEqual(strategy.update({"flood_depth": 1.0}), 1.0)


class TestHybridSurpriseStrategy(unittest.TestCase):
    """Test hybrid EMA + Symbolic strategy."""

    def test_weighted_combination(self):
        """Hybrid should combine EMA and Symbolic surprises."""
        strategy = HybridSurpriseStrategy(
            ema_weight=0.6,
            symbolic_weight=0.4,
            ema_stimulus_key="flood_depth",
            ema_alpha=0.5
        )

        surprise = strategy.update({"flood_depth": 5.0})

        # Should be between 0 and 1
        self.assertGreaterEqual(surprise, 0.0)
        self.assertLessEqual(surprise, 1.0)

    def test_trace_includes_both_components(self):
        """Trace should show both EMA and Symbolic components.

        Phase 6Q-C (2026-05-26): `ema_stimulus_key` is now required —
        previously defaulted silently to "flood_depth". Test still
        exercises flood mechanics; just passes the key explicitly.
        """
        strategy = HybridSurpriseStrategy(
            ema_weight=0.5, symbolic_weight=0.5,
            ema_stimulus_key="flood_depth",
        )
        strategy.update({"flood_depth": 2.0})

        trace = strategy.get_trace()
        self.assertIsNotNone(trace)
        self.assertEqual(trace["strategy"], "Hybrid")
        self.assertIn("ema_surprise", trace)
        self.assertIn("symbolic_surprise", trace)
        self.assertIn("combined_surprise", trace)

    def test_weights_normalized(self):
        """Weights should be normalized to sum to 1.

        Phase 6Q-C: `ema_stimulus_key` now required.
        """
        strategy = HybridSurpriseStrategy(
            ema_weight=3, symbolic_weight=7,
            ema_stimulus_key="flood_depth",
        )
        # 3/(3+7)=0.3, 7/(3+7)=0.7
        self.assertAlmostEqual(strategy.ema_weight, 0.3)
        self.assertAlmostEqual(strategy.symbolic_weight, 0.7)



if __name__ == "__main__":
    unittest.main()
