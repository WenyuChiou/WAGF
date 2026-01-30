import json

from examples.multi_agent.irrigation_abm.run_experiment import _apply_skill, _parse_decision


def test_parse_decision_extracts_magnitude():
    payload = {
        "water_threat_appraisal": {"label": "H", "reason": ""},
        "water_coping_appraisal": {"label": "M", "reason": ""},
        "decision": "1",
        "magnitude": 15,
        "reasoning": "",
    }
    raw = "<<<DECISION_START>>>\n" + json.dumps(payload) + "\n<<<DECISION_END>>>"
    result = _parse_decision(raw)
    assert result["magnitude"] == 15
    assert result["skill"] == "increase_demand"


def test_apply_skill_uses_magnitude_percent():
    # 15% of 100k = 15k increase
    new_request = _apply_skill("increase_demand", 50_000, 100_000, magnitude_pct=15)
    assert new_request == 65_000


def test_build_regret_feedback_formats_shortfall():
    from examples.multi_agent.irrigation_abm.irrigation_personas import (
        build_regret_feedback,
    )

    text = build_regret_feedback(
        year=2025,
        request=120_000,
        diversion=90_000,
        drought_index=0.72,
        preceding_factor=0,
    )
    assert "Year 2025" in text
    assert "requested 120000" in text.replace(",", "")
    assert "received 90000" in text.replace(",", "")
    assert "shortfall" in text.lower()
    assert "drought index" in text.lower()


def test_memory_window_keeps_last_five():
    from types import SimpleNamespace

    from broker.components.engines.window_engine import WindowMemoryEngine

    engine = WindowMemoryEngine(window_size=5)
    agent = SimpleNamespace(id="Agent_001", memory=[])
    for i in range(10):
        engine.add_memory(agent.id, f"mem-{i}")
    mems = engine.retrieve(agent, top_k=5)
    assert mems == ["mem-5", "mem-6", "mem-7", "mem-8", "mem-9"]


def test_hierarchical_memory_returns_semantic():
    from types import SimpleNamespace

    from broker.components.engines.hierarchical_engine import HierarchicalMemoryEngine

    engine = HierarchicalMemoryEngine(window_size=3, semantic_top_k=2)
    agent = SimpleNamespace(id="Agent_001", memory=[])
    engine.add_memory(agent.id, "routine year", {"importance": 0.2})
    engine.add_memory(agent.id, "big shortfall", {"importance": 0.9})
    engine.add_memory(agent.id, "moderate shortfall", {"importance": 0.7})
    engine.add_memory(agent.id, "recent 1", {"importance": 0.1})
    engine.add_memory(agent.id, "recent 2", {"importance": 0.1})
    engine.add_memory(agent.id, "recent 3", {"importance": 0.1})
    mems = engine.retrieve(agent)
    assert "semantic" in mems
    assert len(mems["semantic"]) == 2


def test_reflection_triggers():
    from broker.components.reflection_engine import ReflectionEngine, ReflectionTrigger

    engine = ReflectionEngine(reflection_interval=5)
    assert engine.should_reflect_triggered("A", "household", 10, ReflectionTrigger.PERIODIC)
    assert engine.should_reflect_triggered("A", "household", 1, ReflectionTrigger.CRISIS)
    assert (
        engine.should_reflect_triggered(
            "A",
            "household",
            1,
            ReflectionTrigger.DECISION,
            context={"decision": "decrease_demand"},
        )
        is False
    )


def test_governance_validate_magnitude_cap():
    from broker.validators.governance import validate_all

    ctx = {"proposed_magnitude": 25, "cluster": "forward_looking_conservative"}
    results = validate_all("increase_demand", [], ctx, domain="irrigation")
    errors = [r for r in results if not r.valid]
    assert len(errors) >= 1


def test_apply_skill_with_governance_bounded_magnitude():
    new_req = _apply_skill("increase_demand", 50_000, 100_000, magnitude_pct=10)
    assert new_req == 60_000
