import pytest

from broker.components.memory_factory import create_memory_engine


@pytest.mark.parametrize("engine_type", [
    "window", "importance", "humancentric",
    "hierarchical", "universal", "unified"
])
def test_create_engine(engine_type):
    engine = create_memory_engine(engine_type)
    assert engine is not None


def test_unified_engine_from_sdk():
    engine = create_memory_engine("unified", config={
        "arousal_threshold": 0.5,
        "window_size": 10,
    })
    engine.add_memory("agent1", "Test memory")
    memories = engine.retrieve("agent1")
    assert len(memories) > 0


def test_invalid_engine_raises():
    with pytest.raises(ValueError):
        create_memory_engine("nonexistent")
