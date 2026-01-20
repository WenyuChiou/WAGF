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
        # These will be processed by the retrieve method's initialization logic.
        self.agent.memory = [
            {
                "content": "I saw my neighbor install flood protection. It seemed effective.", 
                "metadata": {"emotion": "positive", "source": "neighbor", "importance": 0.6}
            },
            {
                "content": "The government announced a new subsidy for home elevation.", 
                "metadata": {"emotion": "shift", "source": "abstract", "importance": 0.7}
            },
            {
                "content": "Last year, my basement was completely flooded, causing major damage.", 
                "metadata": {"emotion": "fear", "source": "personal", "importance": 0.9} # High importance trauma
            },
            {
                "content": "A small leak in the roof was repaired. Minor issue.", 
                "metadata": {"emotion": "routine", "source": "personal", "importance": 0.1}
            },
            {
                "content": "I read a newspaper article about general climate change trends.", 
                "metadata": {"emotion": "observation", "source": "abstract", "importance": 0.4}
            },
            {
                "content": "Another local flood event caused significant distress to my friends.", 
                "metadata": {"emotion": "fear", "source": "community", "importance": 0.7} # Another fear memory
            }
        ]

    def test_retrieve_without_boosters(self):
        print("\n--- Test Retrieve Without Boosters ---")
        # When no boosters are applied, retrieval should be based on recency and importance.
        # The order can shift when timestamps advance or consolidation occurs, so we assert on set.
        retrieved = self.engine.retrieve(self.agent, top_k=3, contextual_boosters=None)
        print(f"Retrieved without boosters: {retrieved}")

        expected = {
            "Another local flood event caused significant distress to my friends.",
            "Last year, my basement was completely flooded, causing major damage.",
            "I read a newspaper article about general climate change trends."
        }
        self.assertEqual(set(retrieved), expected)

    def test_retrieve_with_fear_booster(self):
        print("\n--- Test Retrieve With Fear Booster ---")
        # Simulate a flood event (boost "emotion:fear" memories)
        contextual_boosters = {"emotion:fear": 5.0} # A strong boost
        retrieved = self.engine.retrieve(self.agent, top_k=3, contextual_boosters=contextual_boosters)
        print(f"Retrieved with fear booster: {retrieved}")

        # Expectation: "emotion:fear" memories should be heavily prioritized.
        # Memories with emotion="fear":
        # - 'Last year, my basement...' (imp=0.9, ts=2, rec=0.66)
        #   Score = (0.66*0.3) + (0.9*0.5) + (5.0*0.2) = 0.198 + 0.45 + 1.0 = 1.648
        # - 'Another local flood event...' (imp=0.7, ts=4, rec=0.37)
        #   Score = (0.37*0.3) + (0.7*0.5) + (5.0*0.2) = 0.111 + 0.35 + 1.0 = 1.461
        
        # These two should be the top items. The third item will depend on scores.
        self.assertIn("Last year, my basement was completely flooded, causing major damage.", retrieved)
        self.assertIn("Another local flood event caused significant distress to my friends.", retrieved)
        self.assertEqual(len(retrieved), 3)

        # Ensure the two fear-related memories are the top 2
        top_two_retrieved = retrieved[:2]
        self.assertIn("Last year, my basement was completely flooded, causing major damage.", top_two_retrieved)
        self.assertIn("Another local flood event caused significant distress to my friends.", top_two_retrieved)


    def test_retrieve_with_no_matching_booster(self):
        print("\n--- Test Retrieve With No Matching Booster ---")
        # Boost an emotion that none of the current memories have explicitly tagged (they default to routine)
        contextual_boosters = {"emotion:joy": 10.0}
        retrieved = self.engine.retrieve(self.agent, top_k=3, contextual_boosters=contextual_boosters)
        print(f"Retrieved with no matching booster: {retrieved}")
        
        # Should behave identically to no boosters, as the 'joy' tag won't match any memory's emotion.
        expected = {
            "Another local flood event caused significant distress to my friends.",
            "Last year, my basement was completely flooded, causing major damage.",
            "I read a newspaper article about general climate change trends."
        }
        self.assertEqual(set(retrieved), expected)

if __name__ == '__main__':
    unittest.main()
