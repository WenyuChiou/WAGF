import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Adjust the path to import from the broker package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.components.memory_engine import HumanCentricMemoryEngine, BaseAgent

class TestHumanCentricMemoryEngine(unittest.TestCase):

    def setUp(self):
        # Initialize engine with deterministic seed and weighted ranking mode
        self.engine = HumanCentricMemoryEngine(seed=42, ranking_mode="weighted")
        self.agent = MagicMock(spec=BaseAgent)
        self.agent.id = "test_agent"
        # Ensure agent has a memory_config if needed by _classify_emotion or _compute_importance
        self.agent.memory_config = {}
        
        # Define initial memories with metadata, as they would be loaded from a profile.
        # These memories will be added via the retrieve method's initialization, which calls add_memory_for_agent.
        self.agent.memory = [
            {
                "content": "I saw my neighbor install flood protection. It seemed effective.",
                "emotion": "positive",
                "source": "neighbor",
                "importance": 0.6
            },
            {
                "content": "The government announced a new subsidy for home elevation.",
                "emotion": "shift",
                "source": "abstract",
                "importance": 0.7
            },
            {
                "content": "Last year, my basement was completely flooded, causing major damage.",
                "emotion": "fear",
                "source": "personal",
                "importance": 0.9  # High importance trauma
            },
            {
                "content": "A small leak in the roof was repaired. Minor issue.",
                "emotion": "routine",
                "source": "personal",
                "importance": 0.1
            },
            {
                "content": "I read a newspaper article about general climate change trends.",
                "emotion": "observation",
                "source": "abstract",
                "importance": 0.4
            },
            {
                "content": "Another local flood event caused significant distress to my friends.",
                "emotion": "fear",
                "source": "community",
                "importance": 0.7  # Another fear memory
            }
        ]

    def test_retrieve_without_boosters(self):
        print("\n--- Test Retrieve Without Boosters ---")
        retrieved = self.engine.retrieve(self.agent, top_k=3, contextual_boosters=None)
        print(f"Retrieved without boosters: {retrieved}")
        
        # Expectation: The highest-scoring memories should be prioritized given current_time
        # derived from timestamps (which can skip when items consolidate).
        self.assertIn("Last year, my basement was completely flooded, causing major damage.", retrieved)
        self.assertIn("Another local flood event caused significant distress to my friends.", retrieved)
        self.assertIn("I read a newspaper article about general climate change trends.", retrieved)
        self.assertEqual(len(retrieved), 3)

    def test_retrieve_with_fear_booster(self):
        print("\n--- Test Retrieve With Fear Booster ---")
        # Simulate a flood event (boost "emotion:fear" memories)
        contextual_boosters = {"emotion:fear": 5.0} # A strong boost
        retrieved = self.engine.retrieve(self.agent, top_k=3, contextual_boosters=contextual_boosters)
        print(f"Retrieved with fear booster: {retrieved}")

        # Expectation: "emotion:fear" memories should be heavily prioritized.
        # 'Last year, my basement...' (imp=0.9, ts=2, rec=0.66, emotion:fear, boost=5.0) Score = 0.198 + 0.45 + 0.2*5.0 = 0.648 + 1.0 = 1.648
        # 'Another local flood event...' (imp=0.7, ts=5, rec=0.16, emotion:fear, boost=5.0) Score = 0.048 + 0.35 + 0.2*5.0 = 0.398 + 1.0 = 1.398
        
        self.assertIn("Last year, my basement was completely flooded, causing major damage.", retrieved)
        self.assertIn("Another local flood event caused significant distress to my friends.", retrieved)
        self.assertEqual(len(retrieved), 3)

        # Check if the top 2 are indeed the fear-related memories (or boosted ones)
        # The exact 3rd item can vary depending on scores, but the two fear ones should be top.
        top_two_retrieved = retrieved[:2]
        self.assertIn("Last year, my basement was completely flooded, causing major damage.", top_two_retrieved)
        self.assertIn("Another local flood event caused significant distress to my friends.", top_two_retrieved)

    def test_retrieve_with_no_matching_booster(self):
        print("\n--- Test Retrieve With No Matching Booster ---")
        # Boost an emotion that none of the current memories have
        contextual_boosters = {"emotion:joy": 10.0}
        retrieved = self.engine.retrieve(self.agent, top_k=3, contextual_boosters=contextual_boosters)
        print(f"Retrieved with no matching booster: {retrieved}")
        
        # Should behave identically to no boosters.
        self.assertIn("Last year, my basement was completely flooded, causing major damage.", retrieved)
        self.assertIn("Another local flood event caused significant distress to my friends.", retrieved)
        self.assertIn("I read a newspaper article about general climate change trends.", retrieved)
        self.assertEqual(len(retrieved), 3)

if __name__ == '__main__':
    unittest.main()
