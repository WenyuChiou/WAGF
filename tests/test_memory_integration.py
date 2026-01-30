import pytest
from broker.components.memory_engine import create_memory_engine
from broker.components.universal_memory import UniversalCognitiveEngine


class MockAgent:
    """Lightweight mock agent for memory engine tests."""
    def __init__(self, agent_id="test_agent"):
        self.id = agent_id
        self.memory = []
        self.custom_attributes = {}

def test_v3_integration_flow():
    """
    Simulates a 10-step run where flood depth changes, triggering
    Surprise -> System 2 -> Adaptation -> System 1.
    """
    
    # 1. Setup Engine
    engine = create_memory_engine(
        engine_type="universal",
        window_size=3,
        arousal_threshold=0.5,
        ema_alpha=0.5,       # Fast learning
        ranking_mode="dynamic"
    )
    
    agent = MockAgent()
    
    # 2. Phase A: Routine (Expectation = 0.0)
    # Steps 1-3: No flood.
    print("\n[Phase A] Routine (0.0m)")
    for i in range(3):
        engine.retrieve(agent, top_k=3, world_state={"flood_depth_m": 0.0})
        # Should stay in System 1 (Legacy)
        assert engine.current_system == "SYSTEM_1"
        assert engine.last_surprise < 0.2
        
    # 3. Phase B: Shock (Flood = 2.0m)
    # This is a huge deviation from expectation (0.0).
    print("\n[Phase B] Shock (2.0m)")
    engine.retrieve(agent, top_k=3, world_state={"flood_depth_m": 2.0})
    
    # Surprise = |2.0 - 0.0| = 2.0 -> Sigmoid maps to ~0.88
    # Arousal should spike > 0.5
    assert engine.last_surprise > 0.5
    assert engine.current_system == "SYSTEM_2", "Should switch to System 2 (Weighted)"
    
    # 4. Phase C: Adaptation (Flood continues = 2.0m)
    # EMA should update expectation towards 2.0.
    # Surprise should decrease.
    print("\n[Phase C] Adaptation (2.0m continues)")
    for i in range(5):
        engine.retrieve(agent, top_k=3, world_state={"flood_depth_m": 2.0})
        
    # Eventually, expectation ~ 2.0, surprise ~ 0.
    # Should revert to System 1.
    print(f"Final Arousal: {engine.last_surprise}")
    assert engine.last_surprise < 0.5
    assert engine.current_system == "SYSTEM_1", "Should revert to System 1 after adapting"

def test_legacy_engine_ignores_kwargs():
    """
    Verify that legacy engines don't crash when receiving world_state.
    """
    legacy = create_memory_engine("humancentric", ranking_mode="legacy")
    agent = MockAgent()
    
    try:
        legacy.retrieve(agent, top_k=3, world_state={"flood_depth_m": 5.0})
    except TypeError as e:
        pytest.fail(f"Legacy engine crashed on kwargs: {e}")
