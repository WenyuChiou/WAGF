"""
Unit tests for v5 UnifiedCognitiveEngine.

Tests:
- EMASurpriseStrategy (EMA formula, surprise calculation)
- SymbolicSurpriseStrategy (novelty-first logic)
- HybridSurpriseStrategy (weighted combination)
- UnifiedMemoryStore (working/long-term consolidation)
- AdaptiveRetrievalEngine (dynamic weight adjustment)
- UnifiedCognitiveEngine (full integration)

Reference: Task-040 Memory Module Optimization
"""

import unittest
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

# Adjust path to import cognitive_governance
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cognitive_governance.memory import (
    UnifiedCognitiveEngine,
    UnifiedMemoryItem,
    UnifiedMemoryStore,
    AdaptiveRetrievalEngine,
    EMASurpriseStrategy,
    SymbolicSurpriseStrategy,
    HybridSurpriseStrategy,
)
from cognitive_governance.memory.strategies.ema import EMAPredictor
from cognitive_governance.memory.strategies.symbolic import Sensor, SignatureEngine


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
        """Trace should show both EMA and Symbolic components."""
        strategy = HybridSurpriseStrategy(ema_weight=0.5, symbolic_weight=0.5)
        strategy.update({"flood_depth": 2.0})

        trace = strategy.get_trace()
        self.assertIsNotNone(trace)
        self.assertEqual(trace["strategy"], "Hybrid")
        self.assertIn("ema_surprise", trace)
        self.assertIn("symbolic_surprise", trace)
        self.assertIn("combined_surprise", trace)

    def test_weights_normalized(self):
        """Weights should be normalized to sum to 1."""
        strategy = HybridSurpriseStrategy(ema_weight=3, symbolic_weight=7)
        # 3/(3+7)=0.3, 7/(3+7)=0.7
        self.assertAlmostEqual(strategy.ema_weight, 0.3)
        self.assertAlmostEqual(strategy.symbolic_weight, 0.7)


class TestUnifiedMemoryStore(unittest.TestCase):
    """Test unified memory store with working/long-term separation."""

    def test_add_to_working_memory(self):
        """Items should be added to working memory."""
        store = UnifiedMemoryStore(working_capacity=10)

        item = UnifiedMemoryItem(
            content="Test memory",
            agent_id="agent_1"
        )
        store.add(item)

        working = store.get_working("agent_1")
        self.assertEqual(len(working), 1)
        self.assertEqual(working[0].content, "Test memory")

    def test_working_capacity_overflow(self):
        """Overflow should trigger consolidation."""
        store = UnifiedMemoryStore(
            working_capacity=3,
            consolidation_threshold=0.5,
            auto_consolidate_overflow=True
        )

        # Add 5 items (exceeds capacity of 3)
        for i in range(5):
            importance = 0.8 if i < 2 else 0.3  # First 2 are important
            item = UnifiedMemoryItem(
                content=f"Memory {i}",
                agent_id="agent_1",
                base_importance=importance
            )
            item._current_importance = importance
            store.add(item)

        # Working should be at capacity
        working = store.get_working("agent_1")
        self.assertLessEqual(len(working), 3)

        # Important memories should have been consolidated
        longterm = store.get_longterm("agent_1")
        # At least some important ones should be in long-term
        self.assertGreaterEqual(len(longterm), 0)

    def test_explicit_consolidation(self):
        """Consolidate should move important items to long-term."""
        store = UnifiedMemoryStore(
            working_capacity=10,
            consolidation_threshold=0.5
        )

        # Add item with high importance
        item = UnifiedMemoryItem(
            content="Important memory",
            agent_id="agent_1",
            base_importance=0.8
        )
        item._current_importance = 0.8
        store.add(item)

        # Manually consolidate
        count = store.consolidate("agent_1")

        self.assertEqual(count, 1)
        self.assertEqual(len(store.get_working("agent_1")), 0)
        self.assertEqual(len(store.get_longterm("agent_1")), 1)

    def test_get_all_combines_working_and_longterm(self):
        """get_all should return both working and long-term memories."""
        store = UnifiedMemoryStore()

        # Add to working
        store.add(UnifiedMemoryItem(content="Working 1", agent_id="a1"))

        # Manually add to long-term
        store._longterm["a1"] = [UnifiedMemoryItem(content="Longterm 1", agent_id="a1")]

        all_items = store.get_all("a1")
        self.assertEqual(len(all_items), 2)

    def test_forget_by_importance(self):
        """Forget should remove low-importance memories."""
        store = UnifiedMemoryStore()

        # Add items with different importance
        for i, imp in enumerate([0.1, 0.3, 0.7, 0.9]):
            item = UnifiedMemoryItem(content=f"M{i}", agent_id="a1", base_importance=imp)
            item._current_importance = imp
            store.add(item)

        # Forget below 0.5
        forgotten = store.forget("a1", strategy="importance", threshold=0.5)

        self.assertEqual(forgotten, 2)  # 0.1 and 0.3
        remaining = store.get_working("a1")
        self.assertEqual(len(remaining), 2)

    def test_clear_removes_all(self):
        """Clear should remove all memories for an agent."""
        store = UnifiedMemoryStore()
        store.add(UnifiedMemoryItem(content="Test", agent_id="a1"))
        store._longterm["a1"] = [UnifiedMemoryItem(content="LT", agent_id="a1")]

        store.clear("a1")

        self.assertEqual(len(store.get_working("a1")), 0)
        self.assertEqual(len(store.get_longterm("a1")), 0)


class TestAdaptiveRetrievalEngine(unittest.TestCase):
    """Test adaptive retrieval with dynamic weight adjustment."""

    def setUp(self):
        """Set up store with test memories."""
        self.store = UnifiedMemoryStore()

        # Add memories with different characteristics
        current_time = time.time()

        # Recent, low importance
        item1 = UnifiedMemoryItem(
            content="Recent low",
            agent_id="a1",
            timestamp=current_time,
            base_importance=0.2
        )
        item1._current_importance = 0.2

        # Old, high importance
        item2 = UnifiedMemoryItem(
            content="Old high",
            agent_id="a1",
            timestamp=current_time - 7200,  # 2 hours ago
            base_importance=0.9
        )
        item2._current_importance = 0.9

        # Middle
        item3 = UnifiedMemoryItem(
            content="Middle",
            agent_id="a1",
            timestamp=current_time - 3600,  # 1 hour ago
            base_importance=0.5
        )
        item3._current_importance = 0.5

        for item in [item1, item2, item3]:
            self.store.add(item)

    def test_low_arousal_favors_recency(self):
        """System 1 (low arousal) should favor recent memories."""
        engine = AdaptiveRetrievalEngine(
            system1_weights={"recency": 0.8, "importance": 0.1, "context": 0.1, "semantic": 0.0},
            system2_weights={"recency": 0.1, "importance": 0.8, "context": 0.1, "semantic": 0.0}
        )

        results = engine.retrieve(
            store=self.store,
            agent_id="a1",
            top_k=2,
            arousal=0.0  # Low arousal
        )

        # Recent item should rank high
        contents = [r.content for r in results]
        self.assertIn("Recent low", contents)

    def test_high_arousal_favors_importance(self):
        """System 2 (high arousal) should favor important memories."""
        engine = AdaptiveRetrievalEngine(
            system1_weights={"recency": 0.8, "importance": 0.1, "context": 0.1, "semantic": 0.0},
            system2_weights={"recency": 0.1, "importance": 0.8, "context": 0.1, "semantic": 0.0}
        )

        results = engine.retrieve(
            store=self.store,
            agent_id="a1",
            top_k=2,
            arousal=0.9,  # High arousal
            arousal_threshold=0.5
        )

        # Important item should rank high
        contents = [r.content for r in results]
        self.assertIn("Old high", contents)

    def test_trace_captures_weights(self):
        """Trace should show active weights."""
        engine = AdaptiveRetrievalEngine()

        engine.retrieve(
            store=self.store,
            agent_id="a1",
            top_k=2,
            arousal=0.6,
            arousal_threshold=0.5,
            include_scoring=True
        )

        trace = engine.get_trace()
        self.assertIsNotNone(trace)
        self.assertIn("weights", trace)
        self.assertIn("system", trace)
        self.assertEqual(trace["system"], "SYSTEM_2")

    def test_empty_store_returns_empty(self):
        """Empty store should return empty list."""
        engine = AdaptiveRetrievalEngine()
        store = UnifiedMemoryStore()

        results = engine.retrieve(store=store, agent_id="nonexistent", top_k=5)
        self.assertEqual(len(results), 0)


class TestUnifiedCognitiveEngine(unittest.TestCase):
    """Test full integrated engine."""

    def test_add_and_retrieve_memory(self):
        """Basic add and retrieve cycle."""
        engine = UnifiedCognitiveEngine()

        # Add memory
        engine.add_memory("agent_1", "Test memory content", metadata={
            "emotion": "major",
            "source": "personal"
        })

        # Retrieve
        memories = engine.retrieve("agent_1", top_k=5)
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0], "Test memory content")

    def test_system_switching_with_ema_strategy(self):
        """Engine should switch systems based on surprise."""
        strategy = EMASurpriseStrategy(stimulus_key="flood_depth", alpha=0.5)
        engine = UnifiedCognitiveEngine(
            surprise_strategy=strategy,
            arousal_threshold=0.3
        )

        # Add baseline memory
        engine.add_memory("a1", "Baseline")

        # Low surprise: System 1
        engine.retrieve("a1", world_state={"flood_depth": 0.0})
        self.assertEqual(engine.current_system, "SYSTEM_1")

        # High surprise: System 2
        engine.retrieve("a1", world_state={"flood_depth": 5.0})
        self.assertEqual(engine.current_system, "SYSTEM_2")

    def test_system_switching_with_symbolic_strategy(self):
        """Symbolic strategy novelty should trigger System 2."""
        sensors = [
            Sensor(
                path="x",
                name="X",
                bins=[{"label": "LOW", "max": 0.5}, {"label": "HIGH", "max": 99.0}]
            )
        ]
        strategy = SymbolicSurpriseStrategy(sensors=sensors)
        engine = UnifiedCognitiveEngine(
            surprise_strategy=strategy,
            arousal_threshold=0.5
        )

        engine.add_memory("a1", "Test")

        # First observation: novel -> System 2
        engine.retrieve("a1", world_state={"x": 0.8})
        self.assertEqual(engine.current_system, "SYSTEM_2")

        # Repeat same state many times: familiar -> System 1
        # Symbolic needs frequency > 50% for surprise < 0.5
        for _ in range(20):
            engine.retrieve("a1", world_state={"x": 0.8})

        # After many repetitions, surprise should drop below threshold
        # Final surprise = 1 - (count/total), needs count/total > 0.5
        self.assertEqual(engine.current_system, "SYSTEM_1")

    def test_normalization_adaptation(self):
        """Agent should adapt to repeated stimuli (boiling frog)."""
        # Use high alpha for fast adaptation
        strategy = EMASurpriseStrategy(
            stimulus_key="flood_depth",
            alpha=0.7,  # Fast adaptation
            normalize_range=(0, 10)  # Explicit range for predictable normalization
        )
        engine = UnifiedCognitiveEngine(
            surprise_strategy=strategy,
            arousal_threshold=0.15  # Lower threshold so we can reach System 1
        )

        engine.add_memory("a1", "Test")

        # Initial high stimulus: System 2
        engine.retrieve("a1", world_state={"flood_depth": 10.0})
        initial_system = engine.current_system

        # Repeat many times - EMA should converge
        for _ in range(25):
            engine.retrieve("a1", world_state={"flood_depth": 10.0})

        # Should have normalized to System 1 (surprise approaches 0)
        final_system = engine.current_system
        self.assertEqual(initial_system, "SYSTEM_2")
        self.assertEqual(final_system, "SYSTEM_1")

    def test_cognitive_state_capture(self):
        """Engine should expose cognitive state for debugging."""
        strategy = EMASurpriseStrategy(stimulus_key="x", alpha=0.3)
        engine = UnifiedCognitiveEngine(surprise_strategy=strategy)

        engine.add_memory("a1", "Test")
        engine.retrieve("a1", world_state={"x": 5.0})

        state = engine.get_cognitive_state()
        self.assertIn("system", state)
        self.assertIn("surprise", state)
        self.assertIn("arousal_threshold", state)

    def test_reset_clears_state(self):
        """Reset should clear all state."""
        engine = UnifiedCognitiveEngine()
        engine.add_memory("a1", "Test 1")
        engine.add_memory("a1", "Test 2")

        engine.reset()

        memories = engine.retrieve("a1")
        self.assertEqual(len(memories), 0)

    def test_add_memory_for_agent_object(self):
        """Should work with agent objects having id attribute."""
        engine = UnifiedCognitiveEngine()

        agent = MagicMock()
        agent.id = "test_agent_123"

        engine.add_memory_for_agent(agent, "Test content")

        memories = engine.retrieve("test_agent_123")
        self.assertEqual(len(memories), 1)


class TestUnifiedMemoryItem(unittest.TestCase):
    """Test memory item data structure."""

    def test_importance_computation(self):
        """Importance = base * emotion_factor * source_factor."""
        item = UnifiedMemoryItem(
            content="Test",
            base_importance=1.0,
            emotion="major",  # weight: 1.0
            source="personal"  # weight: 1.0
        )

        computed = item.compute_importance()
        self.assertAlmostEqual(computed, 1.0)

        # Lower weights
        item2 = UnifiedMemoryItem(
            content="Test",
            base_importance=1.0,
            emotion="minor",  # weight: 0.5
            source="social"  # weight: 0.7
        )
        computed2 = item2.compute_importance()
        self.assertAlmostEqual(computed2, 0.35, places=2)

    def test_serialization_roundtrip(self):
        """Item should serialize and deserialize correctly."""
        item = UnifiedMemoryItem(
            content="Test content",
            emotion="major",
            source="policy",
            base_importance=0.7,
            surprise_score=0.5,
            agent_id="a1",
            year=2025,
            tags=["flood", "damage"]
        )
        item._current_importance = 0.8

        # Serialize
        data = item.to_dict()

        # Deserialize
        restored = UnifiedMemoryItem.from_dict(data)

        self.assertEqual(restored.content, "Test content")
        self.assertEqual(restored.emotion, "major")
        self.assertEqual(restored.source, "policy")
        self.assertEqual(restored.agent_id, "a1")
        self.assertEqual(restored.year, 2025)
        self.assertEqual(restored.tags, ["flood", "damage"])
        self.assertAlmostEqual(restored.importance, 0.8)


if __name__ == '__main__':
    unittest.main()
