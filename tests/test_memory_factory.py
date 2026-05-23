import pytest

from broker.components.memory.factory import create_memory_engine


# Phase 6K-A (2026-05-22): UniversalCognitiveEngine now fails fast in
# scalar mode without a stimulus_key (the previous silent water-domain
# default was removed). Engines that route through it need an explicit
# generic stimulus_key in the smoke check.
_CONFIG_BY_ENGINE = {
    "universal": {"stimulus_key": "environmental_indicator"},
    "unified": {"stimulus_key": "environmental_indicator"},
}


@pytest.mark.parametrize("engine_type", [
    "window", "importance", "humancentric",
    "hierarchical", "universal", "unified"
])
def test_create_engine(engine_type):
    engine = create_memory_engine(engine_type, config=_CONFIG_BY_ENGINE.get(engine_type))
    assert engine is not None


def test_unified_engine_from_sdk():
    engine = create_memory_engine("unified", config={
        "arousal_threshold": 0.5,
        "window_size": 10,
        "stimulus_key": "environmental_indicator",  # 6K-A: required
    })
    engine.add_memory("agent1", "Test memory")
    memories = engine.retrieve("agent1")
    assert len(memories) > 0


def test_invalid_engine_raises():
    with pytest.raises(ValueError):
        create_memory_engine("nonexistent")
