"""Integration tests for irrigation ABM — GBF pipeline components."""
import json

from types import SimpleNamespace

from cognitive_governance.simulation.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
)
from broker.interfaces.skill_types import ApprovedSkill


def _make_env_with_agent(agent_id="TestAgent", water_right=100_000.0):
    """Helper: create an IrrigationEnvironment with a single test agent."""
    env = IrrigationEnvironment(WaterSystemConfig(seed=42))
    profile = SimpleNamespace(
        agent_id=agent_id,
        basin="upper_basin",
        water_right=water_right,
        has_efficient_system=False,
        cluster="aggressive",
    )
    env.initialize_from_profiles([profile])
    return env


def test_execute_skill_increase_demand():
    """execute_skill with increase_demand adds magnitude_pct% of water_right."""
    env = _make_env_with_agent(water_right=100_000)
    skill = ApprovedSkill(
        skill_name="increase_demand",
        agent_id="TestAgent",
        approval_status="APPROVED",
        execution_mapping="env.execute_skill",
    )
    skill.metadata = {"magnitude_pct": 15}
    result = env.execute_skill(skill)
    assert result.success
    state = env.get_agent_state("TestAgent")
    # Initial request = 100_000 * 0.8 = 80_000; increase by 15% of 100_000 = 15_000
    assert state["request"] == 95_000.0


def test_execute_skill_decrease_demand():
    """execute_skill with decrease_demand subtracts magnitude_pct% of water_right."""
    env = _make_env_with_agent(water_right=100_000)
    skill = ApprovedSkill(
        skill_name="decrease_demand",
        agent_id="TestAgent",
        approval_status="APPROVED",
        execution_mapping="env.execute_skill",
    )
    skill.metadata = {"magnitude_pct": 10}
    result = env.execute_skill(skill)
    assert result.success
    state = env.get_agent_state("TestAgent")
    # Initial request = 80_000; decrease by 10% of 100_000 = 10_000
    assert state["request"] == 70_000.0


def test_build_regret_feedback_formats_shortfall():
    from examples.irrigation_abm.irrigation_personas import (
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
    from broker.components.engines.window_engine import WindowMemoryEngine

    engine = WindowMemoryEngine(window_size=5)
    agent = SimpleNamespace(id="Agent_001", memory=[])
    for i in range(10):
        engine.add_memory(agent.id, f"mem-{i}")
    mems = engine.retrieve(agent, top_k=5)
    assert mems == ["mem-5", "mem-6", "mem-7", "mem-8", "mem-9"]


def test_hierarchical_memory_returns_semantic():
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


def test_execute_skill_maintain_demand():
    """execute_skill with maintain_demand keeps request unchanged."""
    env = _make_env_with_agent(water_right=100_000)
    skill = ApprovedSkill(
        skill_name="maintain_demand",
        agent_id="TestAgent",
        approval_status="APPROVED",
        execution_mapping="env.execute_skill",
    )
    skill.metadata = {}
    result = env.execute_skill(skill)
    assert result.success
    state = env.get_agent_state("TestAgent")
    # Initial request = 80_000; no change
    assert state["request"] == 80_000.0
