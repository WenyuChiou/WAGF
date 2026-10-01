"""Integration tests for irrigation ABM — WAGF pipeline components."""
import json

from types import SimpleNamespace

from examples.irrigation_abm.irrigation_env import (
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
        # WP1b (item 20): initialize_from_profiles now requires every
        # Upper Basin profile to carry a sub-basin (supply_group, from
        # precip_group) -- this test is about execute_skill's action-model
        # step math, unrelated to which sub-basin, so any valid one works.
        precip_group="WY",
    )
    env.initialize_from_profiles([profile])
    return env


def _expected_step(env, agent_id, skill, size_class):
    """The Hung and Yang step the env draws for (agent, year, skill)."""
    from examples.irrigation_abm.irrigation_env import hy_step_af
    a = env._agents[agent_id]
    return hy_step_af(env._decision_rng(agent_id, skill), a["mu"], a["sigma"],
                      a["bin_size_af"], size_class)


def test_execute_skill_increase_demand():
    """execute_skill adds the Hung and Yang step (mu + |N(0, sigma)|) x
    bin_size to the current request; the LLM's magnitude_pct is ignored."""
    env = _make_env_with_agent(water_right=100_000)
    skill = ApprovedSkill(
        skill_name="increase_demand",
        agent_id="TestAgent",
        approval_status="APPROVED",
        execution_mapping="env.execute_skill",
    )
    skill.parameters = {"magnitude_pct": 15}
    step = _expected_step(env, "TestAgent", "increase_demand", "any")
    result = env.execute_skill(skill)
    assert result.success
    state = env.get_agent_state("TestAgent")
    assert state["request"] == min(80_000.0 + step, 100_000.0)


def test_execute_skill_increase_demand_reports_applied_magnitude_in_action_context():
    """F07 (2026-09-25 audit): action_context carries the magnitude actually
    applied (realised percent of the request), not the LLM's proposal."""
    env = _make_env_with_agent(water_right=100_000)
    skill = ApprovedSkill(
        skill_name="increase_demand",
        agent_id="TestAgent",
        approval_status="APPROVED",
        execution_mapping="env.execute_skill",
    )
    skill.parameters = {"magnitude_pct": 15}
    result = env.execute_skill(skill)
    assert result.success
    assert result.action_context["magnitude_pct"] == result.state_changes["magnitude_pct_applied"]
    assert result.action_context["magnitude_pct"] != 15
    assert result.state_changes["magnitude_af"] == env.get_agent_state("TestAgent")["request"] - 80_000.0


def test_execute_skill_decrease_demand():
    """execute_skill subtracts the Hung and Yang step from the current
    request, floored at 10 percent of the water right (no taper)."""
    env = _make_env_with_agent(water_right=100_000)
    skill = ApprovedSkill(
        skill_name="decrease_demand",
        agent_id="TestAgent",
        approval_status="APPROVED",
        execution_mapping="env.execute_skill",
    )
    skill.parameters = {"magnitude_pct": 10}
    step = _expected_step(env, "TestAgent", "decrease_demand", "any")
    result = env.execute_skill(skill)
    assert result.success
    state = env.get_agent_state("TestAgent")
    assert abs(state["request"] - max(80_000 - step, 10_000)) < 1e-6


def test_build_action_outcome_feedback_formats_shortfall():
    """F15 (2026-09-25 audit): build_regret_feedback was dead (nothing
    called it; build_action_outcome_feedback superseded it) and has been
    removed; this test now covers the same shortfall-formatting behaviour
    through the live function."""
    from examples.irrigation_abm.irrigation_personas import (
        build_action_outcome_feedback,
    )

    text = build_action_outcome_feedback(
        action_ctx=None,
        year=2025,
        request=120_000,
        diversion=90_000,
        preceding_factor=0,
    )
    assert "Year 2025" in text
    assert "requested 120000" in text.replace(",", "")
    assert "received 90000" in text.replace(",", "")
    assert "shortfall" in text.lower()
    # WP4 (spec 4.5): no drought index in any agent-facing text.
    assert "drought index" not in text.lower()


def test_memory_window_keeps_last_five():
    from broker.components.memory.engines.window import WindowMemoryEngine

    engine = WindowMemoryEngine(window_size=5)
    agent = SimpleNamespace(id="Agent_001", memory=[])
    for i in range(10):
        engine.add_memory(agent.id, f"mem-{i}")
    mems = engine.retrieve(agent, top_k=5)
    assert mems == ["mem-5", "mem-6", "mem-7", "mem-8", "mem-9"]


def test_hierarchical_memory_returns_semantic():
    import warnings
    from broker.components.memory.engines.hierarchical import HierarchicalMemoryEngine

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
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
    from broker.components.cognitive.reflection import ReflectionEngine, ReflectionTrigger

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


def test_governance_validate_magnitude_cap_not_dispatched():
    """F04 (2026-09-25 audit): magnitude_cap_check is intentionally excluded
    from IRRIGATION_PHYSICAL_CHECKS: magnitude_pct is not in the irrigation
    response_format the paper runs use, so the broker never injects
    proposed_magnitude and this check fired zero times across 49,140 audited
    rows. Domain dispatch must NOT warn on it any more; the function itself
    still works when called directly (magnitude_cap_check in
    irrigation_validators.py)."""
    from broker.validators.governance import validate_all

    # WP3: the dispatched v3 supply rule reads its inputs (a full supply
    # here, so it adds no result of its own).
    ctx = {"proposed_magnitude": 25, "cluster": "forward_looking_conservative",
           "basin": "upper_basin", "gap_reason": "none",
           "supply_keep_request_af": 50_000, "supply_expected_at_keep_af": 50_000,
           "supply_ratio": 1.0, "supply_physical_ratio": 1.0, "full_supply_ratio": 0.999}
    results = validate_all("increase_demand", [], ctx, domain="irrigation")
    magnitude_warnings = [
        r for r in results
        if r.valid and r.warnings and r.metadata.get("rule_id") == "magnitude_cap"
    ]
    assert len(magnitude_warnings) == 0


def test_execute_skill_maintain_demand():
    """execute_skill with maintain_demand keeps request unchanged."""
    env = _make_env_with_agent(water_right=100_000)
    skill = ApprovedSkill(
        skill_name="maintain_demand",
        agent_id="TestAgent",
        approval_status="APPROVED",
        execution_mapping="env.execute_skill",
    )
    skill.parameters = {}
    result = env.execute_skill(skill)
    assert result.success
    state = env.get_agent_state("TestAgent")
    # Initial request = 80_000; no change
    assert state["request"] == 80_000.0


# ---------------------------------------------------------------------------
# Context pipeline integration: Fix 1A + 1B + 1C
# ---------------------------------------------------------------------------
def test_irrigation_context_pipeline_no_n_a():
    """Full pipeline: irrigation agent attributes + memory reach the prompt (no [N/A])."""
    from broker.components.context.tiered import TieredContextBuilder
    from broker.components.memory.engines.window import WindowMemoryEngine

    class _Agent:
        def __init__(self):
            self.id = "TestFarmer"
            self.agent_type = "irrigation_farmer"
            self.custom_attributes = {
                "narrative_persona": "You are TestFarmer, a cautious farmer.",
                "basin": "upper_basin",
                "cluster": "forward_looking_conservative",
                "water_right": 100000.0,
            }
            self.narrative_persona = "You are TestFarmer, a cautious farmer."
            self.basin = "upper_basin"
            self.water_situation_text = "Severe drought. Lake Mead at 1050 ft."
            self.conservation_status = "practice"
            self.trust_forecasts_text = "moderately trust"
            self.trust_neighbors_text = "generally trust"
            self.has_efficient_system = False
            self.at_allocation_cap = False
            self.water_right = 100000.0
            self.cluster = "forward_looking_conservative"
            self.dynamic_state = {}

        def get_available_skills(self):
            return []

    agent = _Agent()

    # Memory engine with one memory
    mem_engine = WindowMemoryEngine(window_size=5)
    mem_engine.add_memory("TestFarmer", "Year 1: Decided to adopt efficiency. Shortfall: 5%.")

    template = (
        "{narrative_persona}\n{water_situation_text}\n"
        "Your memory includes:\n{memory}\n\n"
        "You currently {conservation_status} water conservation practices.\n"
        "You {trust_forecasts_text} climate forecasts. "
        "You {trust_neighbors_text} neighboring farmers."
    )

    builder = TieredContextBuilder(
        agents={"TestFarmer": agent},
        hub=None,
        memory_engine=mem_engine,
        prompt_templates={"irrigation_farmer": template, "default": template},
    )

    ctx = builder.build("TestFarmer")
    prompt = builder.format_prompt(ctx)

    # Verify NO [N/A] placeholders
    assert "[N/A]" not in prompt, f"Found [N/A] in prompt:\n{prompt[:500]}"

    # Verify key content is present
    assert "You are TestFarmer, a cautious farmer." in prompt
    assert "Severe drought" in prompt
    assert "Year 1: Decided to adopt efficiency" in prompt
    assert "practice" in prompt
    assert "moderately trust" in prompt
    assert "generally trust" in prompt
