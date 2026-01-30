from examples.multi_agent.flood.run_unified_experiment import build_memory_engine


def test_build_memory_engine_with_flood_scorer():
    engine = build_memory_engine({"scorer": "flood", "arousal_threshold": 0.5})
    assert engine.scorer is not None
