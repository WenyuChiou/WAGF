import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.components.memory_engine import (
    create_memory_engine, 
    WindowMemoryEngine, 
    ImportanceMemoryEngine, 
    HumanCentricMemoryEngine
)
from broker.components.universal_memory import UniversalCognitiveEngine

class TestMemoryEngineFactory(unittest.TestCase):
    def test_create_window_engine(self):
        engine = create_memory_engine("window", window_size=5)
        self.assertIsInstance(engine, WindowMemoryEngine)
        self.assertEqual(engine.window_size, 5)

    def test_create_humancentric_legacy(self):
        engine = create_memory_engine("humancentric", ranking_mode="legacy")
        self.assertIsInstance(engine, HumanCentricMemoryEngine)
        self.assertEqual(engine.ranking_mode, "legacy")

    def test_create_humancentric_weighted(self):
        engine = create_memory_engine("humancentric", ranking_mode="weighted")
        self.assertIsInstance(engine, HumanCentricMemoryEngine)
        self.assertEqual(engine.ranking_mode, "weighted")

    def test_create_universal_dynamic(self):
        engine = create_memory_engine("universal", arousal_threshold=0.5, ema_alpha=0.3)
        self.assertIsInstance(engine, UniversalCognitiveEngine)
        self.assertEqual(engine.arousal_threshold, 0.5)
        self.assertEqual(engine.flood_predictor.alpha, 0.3)

    def test_unknown_engine_raises(self):
        with self.assertRaises(ValueError):
            create_memory_engine("unknown_type")

if __name__ == '__main__':
    unittest.main()
