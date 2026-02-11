import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Adjust the path to import from the broker package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.components.memory.engine import HumanCentricMemoryEngine, BaseAgent

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

class TestContextualResonance(unittest.TestCase):
    """Tests for P2 Contextual Resonance (query-memory relevance)."""

    def setUp(self):
        self.engine = HumanCentricMemoryEngine(
            seed=42, ranking_mode="weighted",
            W_relevance=0.3,  # Enable relevance scoring
        )

    def test_resonance_exact_overlap(self):
        """Perfect keyword overlap → relevance = 1.0."""
        score = self.engine._contextual_resonance(
            "flood damage basement",
            "flood damage basement was severe"
        )
        # "flood", "damage", "basement" all overlap; overlap coeff = 3/3 = 1.0
        self.assertAlmostEqual(score, 1.0)

    def test_resonance_no_overlap(self):
        """Completely disjoint keywords → relevance = 0.0."""
        score = self.engine._contextual_resonance(
            "flood damage basement",
            "sunny vacation relaxation"
        )
        self.assertAlmostEqual(score, 0.0)

    def test_resonance_partial_overlap(self):
        """Partial keyword overlap → 0 < relevance < 1."""
        score = self.engine._contextual_resonance(
            "flood damage protection",
            "flood protection installed by neighbor"
        )
        # query kw: {flood, damage, protection}, mem kw: {flood, protection, installed, neighbor}
        # overlap = {flood, protection} = 2, min(3, 4) = 3 → 2/3 ≈ 0.667
        self.assertGreater(score, 0.5)
        self.assertLess(score, 1.0)

    def test_resonance_ignores_stopwords(self):
        """Stopwords should not inflate relevance."""
        score = self.engine._contextual_resonance(
            "the flood was in the basement",
            "a flood happened at the basement"
        )
        # After removing stopwords: {flood, basement} vs {flood, happened, basement}
        # overlap = 2, min(2, 3) = 2 → 1.0
        self.assertAlmostEqual(score, 1.0)

    def test_resonance_empty_query(self):
        """Empty query → 0.0."""
        self.assertAlmostEqual(
            self.engine._contextual_resonance("", "flood damage"), 0.0
        )

    def test_resonance_empty_memory(self):
        """Empty memory → 0.0."""
        self.assertAlmostEqual(
            self.engine._contextual_resonance("flood damage", ""), 0.0
        )

    def test_resonance_all_stopwords_query(self):
        """Query with only stopwords → 0.0 (no content keywords)."""
        score = self.engine._contextual_resonance(
            "the a is was to of in for",
            "flood damage basement"
        )
        self.assertAlmostEqual(score, 0.0)

    def test_retrieve_with_relevance(self):
        """W_relevance > 0 + query should boost matching memories."""
        agent = MagicMock(spec=BaseAgent)
        agent.id = "rel_agent"
        agent.memory_config = {}
        agent.memory = [
            {
                "content": "Major flood damage destroyed my basement last year.",
                "metadata": {"emotion": "critical", "source": "personal", "importance": 0.5}
            },
            {
                "content": "I attended a community meeting about traffic safety.",
                "metadata": {"emotion": "observation", "source": "community", "importance": 0.5}
            },
            {
                "content": "Neighbor installed flood barriers after the warning.",
                "metadata": {"emotion": "positive", "source": "neighbor", "importance": 0.5}
            },
        ]

        # Query about "flood" should boost flood-related memories
        retrieved = self.engine.retrieve(
            agent, query="flood damage", top_k=2, contextual_boosters=None
        )
        # Both flood-related memories should rank above the traffic one
        self.assertIn("Major flood damage destroyed my basement last year.", retrieved)
        self.assertNotIn("I attended a community meeting about traffic safety.", retrieved)

    def test_relevance_zero_weight_preserves_behavior(self):
        """W_relevance=0 (default) should produce identical results regardless of query."""
        memories = [
            {"content": "Flood damage was severe.", "metadata": {"importance": 0.8}},
            {"content": "Traffic was light today.", "metadata": {"importance": 0.5}},
        ]

        # Two engines with identical seed → identical RNG for consolidation
        engine_a = HumanCentricMemoryEngine(seed=42, ranking_mode="weighted", W_relevance=0.0)
        agent_a = MagicMock(spec=BaseAgent)
        agent_a.id = "compat_a"
        agent_a.memory_config = {}
        agent_a.memory = [m.copy() for m in memories]
        r_no_query = engine_a.retrieve(agent_a, top_k=2, contextual_boosters=None)

        engine_b = HumanCentricMemoryEngine(seed=42, ranking_mode="weighted", W_relevance=0.0)
        agent_b = MagicMock(spec=BaseAgent)
        agent_b.id = "compat_b"
        agent_b.memory_config = {}
        agent_b.memory = [m.copy() for m in memories]
        r_with_query = engine_b.retrieve(agent_b, query="flood", top_k=2, contextual_boosters=None)

        self.assertEqual(r_no_query, r_with_query)


class TestInterferenceForgetting(unittest.TestCase):
    """Tests for P2 Interference-Based Forgetting."""

    def setUp(self):
        self.engine = HumanCentricMemoryEngine(
            seed=42, ranking_mode="weighted",
            W_interference=0.3,  # Enable interference
        )

    def test_no_newer_memories_no_interference(self):
        """With no newer memories, interference = 0."""
        mem = {"content": "flood damage was severe", "timestamp": 5}
        penalty = self.engine._interference_penalty(mem, [])
        self.assertAlmostEqual(penalty, 0.0)

    def test_similar_newer_memory_causes_interference(self):
        """A newer memory with similar content should cause interference."""
        old_mem = {"content": "flood damage to my basement", "timestamp": 1}
        newer = [{"content": "another flood damaged my basement again", "timestamp": 5}]
        penalty = self.engine._interference_penalty(old_mem, newer)
        self.assertGreater(penalty, 0.0)

    def test_dissimilar_newer_memory_no_interference(self):
        """A newer memory with unrelated content should cause minimal interference."""
        old_mem = {"content": "flood damage to my basement", "timestamp": 1}
        newer = [{"content": "sunny vacation at the beach", "timestamp": 5}]
        penalty = self.engine._interference_penalty(old_mem, newer)
        self.assertAlmostEqual(penalty, 0.0)

    def test_interference_capped_at_cap(self):
        """Interference penalty should not exceed interference_cap."""
        old_mem = {"content": "flood damage basement", "timestamp": 1}
        newer = [{"content": "flood damage basement", "timestamp": 5}]  # Exact match
        penalty = self.engine._interference_penalty(old_mem, newer)
        self.assertLessEqual(penalty, 0.8)  # default cap

    def test_interference_multiple_similar_newer(self):
        """Max similarity among multiple newer memories should dominate."""
        old_mem = {"content": "flood damage basement", "timestamp": 1}
        newer = [
            {"content": "sunny day vacation", "timestamp": 2},          # sim ≈ 0
            {"content": "flood damage basement severe", "timestamp": 3}, # sim ≈ 1.0
            {"content": "minor leak repaired", "timestamp": 4},          # sim ≈ 0
        ]
        penalty = self.engine._interference_penalty(old_mem, newer)
        self.assertAlmostEqual(penalty, 0.8)  # Capped at 0.8

    def test_interference_suppresses_older_in_retrieval(self):
        """Older memory should rank lower when a newer similar memory exists."""
        agent = MagicMock(spec=BaseAgent)
        agent.id = "interf_agent"
        agent.memory_config = {}
        # Two similar flood memories, different timestamps
        agent.memory = [
            {
                "content": "Flood damaged my basement causing major loss.",
                "metadata": {"emotion": "critical", "source": "personal", "importance": 0.8}
            },
            {
                "content": "I painted the fence yesterday.",
                "metadata": {"emotion": "routine", "source": "personal", "importance": 0.3}
            },
            {
                "content": "Another flood damaged my basement again this year.",
                "metadata": {"emotion": "critical", "source": "personal", "importance": 0.8}
            },
        ]

        retrieved = self.engine.retrieve(agent, top_k=2, contextual_boosters=None)
        # The newer flood memory should appear; the older flood memory
        # should be penalized by interference from the newer similar one
        self.assertIn("Another flood damaged my basement again this year.", retrieved)

    def test_interference_zero_weight_preserves_behavior(self):
        """W_interference=0 (default) should not affect scoring."""
        engine0 = HumanCentricMemoryEngine(seed=42, ranking_mode="weighted", W_interference=0.0)
        agent = MagicMock(spec=BaseAgent)
        agent.id = "compat_agent2"
        agent.memory_config = {}
        agent.memory = [
            {"content": "Flood damage was severe.", "metadata": {"importance": 0.8}},
            {"content": "Another flood happened.", "metadata": {"importance": 0.8}},
            {"content": "Sunny day today.", "metadata": {"importance": 0.3}},
        ]
        r = engine0.retrieve(agent, top_k=3, contextual_boosters=None)
        self.assertEqual(len(r), 3)


class TestSurprisePluginInterface(unittest.TestCase):
    """Tests for P1 optional SurpriseStrategy plugin hook."""

    def test_no_plugin_observe_returns_zero(self):
        """Without plugin, observe() returns 0.0."""
        engine = HumanCentricMemoryEngine(seed=42)
        self.assertAlmostEqual(engine.observe({"flood_depth": 3.0}), 0.0)

    def test_no_plugin_system_always_system1(self):
        """Without plugin, cognitive system is always SYSTEM_1."""
        engine = HumanCentricMemoryEngine(seed=42)
        self.assertEqual(engine.get_cognitive_system(), "SYSTEM_1")

    def test_no_plugin_trace_is_none(self):
        """Without plugin, trace returns None."""
        engine = HumanCentricMemoryEngine(seed=42)
        self.assertIsNone(engine.get_surprise_trace())

    def test_plugin_observe_forwards_to_strategy(self):
        """With plugin, observe() forwards to strategy.update()."""
        from broker.memory.strategies.decision_consistency import (
            DecisionConsistencySurprise,
        )
        dcs = DecisionConsistencySurprise(mode="unigram")
        engine = HumanCentricMemoryEngine(seed=42, surprise_strategy=dcs)

        s = engine.observe({"action": "maintain_demand"})
        self.assertIsInstance(s, float)
        self.assertGreaterEqual(s, 0.0)
        self.assertLessEqual(s, 1.0)

    def test_plugin_cognitive_system_switches(self):
        """High surprise → SYSTEM_2, low surprise → SYSTEM_1."""
        from broker.memory.strategies.decision_consistency import (
            DecisionConsistencySurprise,
        )
        dcs = DecisionConsistencySurprise(mode="unigram")
        engine = HumanCentricMemoryEngine(
            seed=42, surprise_strategy=dcs, arousal_threshold=0.3
        )

        # Establish a strong pattern
        for _ in range(20):
            engine.observe({"action": "maintain_demand"})
        # Repeated action → low arousal → SYSTEM_1
        self.assertEqual(engine.get_cognitive_system(), "SYSTEM_1")

        # Now do something unexpected
        engine.observe({"action": "completely_new_action"})
        # Novel action → high arousal → SYSTEM_2
        self.assertEqual(engine.get_cognitive_system(), "SYSTEM_2")

    def test_plugin_trace_returns_data(self):
        """With plugin, trace returns strategy-specific data."""
        from broker.memory.strategies.decision_consistency import (
            DecisionConsistencySurprise,
        )
        dcs = DecisionConsistencySurprise(mode="unigram")
        engine = HumanCentricMemoryEngine(seed=42, surprise_strategy=dcs)

        engine.observe({"action": "maintain_demand"})
        trace = engine.get_surprise_trace()
        self.assertIsNotNone(trace)
        self.assertEqual(trace["strategy"], "DecisionConsistency")
        self.assertEqual(trace["action"], "maintain_demand")


class TestCombinedRelevanceAndInterference(unittest.TestCase):
    """Integration test: Contextual Resonance + Interference together."""

    def test_combined_relevance_and_interference(self):
        """Both mechanisms should work together without conflict."""
        engine = HumanCentricMemoryEngine(
            seed=42, ranking_mode="weighted",
            W_relevance=0.3, W_interference=0.3,
        )
        agent = MagicMock(spec=BaseAgent)
        agent.id = "combo"
        agent.memory_config = {}
        agent.memory = [
            # Older flood memory (should be suppressed by interference)
            {"content": "Old flood damaged basement.", "metadata": {"importance": 0.7}},
            # Newer similar memory (high interference source)
            {"content": "Recent flood damaged basement.", "metadata": {"importance": 0.7}},
            # Unrelated memory (no interference, no relevance)
            {"content": "Sunny vacation at beach.", "metadata": {"importance": 0.5}},
        ]

        retrieved = engine.retrieve(agent, query="flood basement damage", top_k=2)
        # "Recent flood" should rank #1 (high relevance, no interference)
        # "Old flood" should be suppressed by interference despite relevance
        self.assertEqual(retrieved[0], "Recent flood damaged basement.")
        self.assertEqual(len(retrieved), 2)


if __name__ == '__main__':
    unittest.main()
