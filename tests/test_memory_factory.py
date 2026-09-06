import pytest

from broker.components.memory.factory import create_memory_engine


# Phase 6K-A (2026-05-22): UniversalCognitiveEngine now fails fast in
# scalar mode without a stimulus_key (the previous silent water-domain
# default was removed). Engines that route through it need an explicit
# generic stimulus_key in the smoke check.
#
# Org-3 note (2026-09): "unified" (broker.memory.unified_engine.
# UnifiedCognitiveEngine) was removed as dead code — no production
# importer, only its own tests. It is no longer a registered engine
# type; test_invalid_engine_raises below now also covers it (any
# unregistered name raises ValueError the same way).
_CONFIG_BY_ENGINE = {
    "universal": {"stimulus_key": "environmental_indicator"},
}


@pytest.mark.parametrize("engine_type", [
    "window", "importance", "humancentric",
    "hierarchical", "universal",
])
def test_create_engine(engine_type):
    engine = create_memory_engine(engine_type, config=_CONFIG_BY_ENGINE.get(engine_type))
    assert engine is not None


def test_invalid_engine_raises():
    with pytest.raises(ValueError):
        create_memory_engine("nonexistent")
