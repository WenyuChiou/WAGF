
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Adjust path to import broker package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.components.universal_memory import UniversalCognitiveEngine, EMAPredictor
from broker.components.memory_engine import BaseAgent

class TestEMAPredictor(unittest.TestCase):
    def test_ema_update_math(self):
        """Verify EMA formula: E_t = (alpha * R) + ((1-alpha) * E_{t-1})"""
        # Case 1: alpha=0.5 (Simple average)
        # E_0 = 0, R_1 = 10 -> E_1 = 5
        predictor = EMAPredictor(alpha=0.5, initial_value=0.0)
        predictor.update(10.0)
        self.assertAlmostEqual(predictor.predict(), 5.0)
        
        # Case 2: alpha=0.1 (High Inertia)
        # E_0 = 0, R_1 = 10 -> E_1 = 1
        predictor = EMAPredictor(alpha=0.1, initial_value=0.0)
        predictor.update(10.0)
        self.assertAlmostEqual(predictor.predict(), 1.0)
        
        # Case 3: Normalization over time
        # If R is constant 10, E should approach 10 asymptotically
        for _ in range(20):
            predictor.update(10.0)
        self.assertAlmostEqual(predictor.predict(), 10.0, delta=1.5)

class TestUniversalCognitiveEngine(unittest.TestCase):
    def setUp(self):
        self.agent = MagicMock(spec=BaseAgent)
        self.agent.id = "test_agent"
        # Set up agent memory attribute for the engine to use
        self.agent.memory = []
        # Mock the parent retrieve to track calls - patch at memory_engine module level
        self.patcher = patch('broker.components.memory_engine.HumanCentricMemoryEngine.retrieve')
        self.mock_super_retrieve = self.patcher.start()
        self.mock_super_retrieve.return_value = ["Mocked Memory"]

    def tearDown(self):
        self.patcher.stop()

    def test_system_1_routine_low_surprise(self):
        """Test System 1 activation when Surprise is low."""
        engine = UniversalCognitiveEngine(stimulus_key='environmental_indicator', arousal_threshold=2.0, ema_alpha=0.5)

        # Reality matches Expectation (0 vs 0) -> Surprise = 0
        state = {'environmental_indicator': 0.0}
        engine.retrieve(self.agent, world_state=state)

        self.assertEqual(engine.current_system, "SYSTEM_1")
        # In System 1, we force "legacy" mode temporarily, but it restores to "weighted"
        self.assertEqual(engine.ranking_mode, "weighted") 

    def test_system_2_crisis_high_surprise(self):
        """Test System 2 activation when Surprise is high."""
        engine = UniversalCognitiveEngine(stimulus_key='environmental_indicator', arousal_threshold=2.0, ema_alpha=0.5)
        # Expectation = 0.0

        # Reality = 5.0 -> Surprise = 5.0 > 2.0 -> System 2
        state = {'environmental_indicator': 5.0}
        engine.retrieve(self.agent, world_state=state)

        self.assertEqual(engine.current_system, "SYSTEM_2")
        # In System 2, we use explicit 'weighted' mode (via super init)
        # The engine was init with ranking_mode="weighted" in super call, so it should stay weighted
        self.assertEqual(engine.ranking_mode, "weighted")

    def test_normalization_adaptation_cycle(self):
        """
        Test the 'Boiling Frog' (Maladaptive Normalization).
        Constant stimulus should eventually become routine (System 2 -> System 1).
        """
        # Alpha=0.5 means fast adaptation for testing
        engine = UniversalCognitiveEngine(stimulus_key='environmental_indicator', arousal_threshold=1.0, ema_alpha=0.5)

        # Tick 1: Surprise! (0 vs 10) -> System 2
        state = {'environmental_indicator': 10.0}
        engine.retrieve(self.agent, world_state=state)
        self.assertEqual(engine.current_system, "SYSTEM_2", "Tick 1 should be System 2")
        # Expectation becomes 5.0

        # Tick 2: Still Surprising? (5 vs 10) -> Diff=5 > 1 -> System 2
        engine.retrieve(self.agent, world_state=state)
        self.assertEqual(engine.current_system, "SYSTEM_2", "Tick 2 should be System 2")
        # Expectation becomes 7.5

        # Tick 3: (7.5 vs 10) -> Diff=2.5 > 1 -> System 2
        engine.retrieve(self.agent, world_state=state)
        # Expectation becomes 8.75

        # ... Fast forward logic:
        # After enough ticks, expectation approaches 10. Surprise approaches 0.
        # Let's force update many times
        for _ in range(10):
             engine.retrieve(self.agent, world_state=state)

        # Now Expectation should be ~10. Surprise ~0.
        # Should drop back to System 1
        self.assertEqual(engine.current_system, "SYSTEM_1", "Agent should have normalized by now.")

if __name__ == '__main__':
    unittest.main()
