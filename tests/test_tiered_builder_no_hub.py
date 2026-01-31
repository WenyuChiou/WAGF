"""Tests for TieredContextBuilder with hub=None (irrigation domain)."""

import pytest
from unittest.mock import MagicMock
from broker.components.tiered_builder import TieredContextBuilder
from broker.components.context_providers import MemoryProvider


@pytest.fixture
def minimal_agents():
    """Minimal agent dict for testing."""
    agent = MagicMock()
    agent.agent_type = "irrigation_farmer"
    agent.state = {"income": 50000, "savings": 20000}
    agent.attributes = {"risk_tolerance": 0.5}
    return {"agent_001": agent}


class _FakeAgent:
    """Lightweight agent mimicking irrigation _profiles_to_agents() output."""

    def __init__(self):
        self.agent_type = "irrigation_farmer"
        self.custom_attributes = {
            "narrative_persona": "You are a bold farmer in the Lower Basin.",
            "basin": "lower_basin",
            "cluster": "aggressive",
            "water_right": 50000.0,
            "farm_size_acres": 250.0,
        }
        # Bare attributes (set at init + pre_year hook)
        self.narrative_persona = "You are a bold farmer in the Lower Basin."
        self.basin = "lower_basin"
        self.cluster = "aggressive"
        self.water_right = 50000.0
        self.farm_size_acres = 250.0
        self.water_situation_text = "Drought index is 0.7, moderate scarcity."
        self.conservation_status = "have not yet adopted"
        self.trust_forecasts_text = "are sceptical of"
        self.trust_neighbors_text = "occasionally listen to"
        self.has_efficient_system = False
        self.at_allocation_cap = False
        self.dynamic_state = {}

    def get_available_skills(self):
        return []


def _make_irrigation_agent(agent_id="agent_001"):
    return _FakeAgent()


class TestTieredBuilderNoHub:
    """Verify TieredContextBuilder works when hub=None."""

    def test_init_no_hub(self, minimal_agents):
        """Constructor should not crash with hub=None."""
        builder = TieredContextBuilder(
            agents=minimal_agents,
            hub=None,
        )
        assert builder.hub is None

    def test_build_no_hub_returns_context(self, minimal_agents):
        """build() should return a valid context dict when hub=None."""
        builder = TieredContextBuilder(
            agents=minimal_agents,
            hub=None,
        )
        ctx = builder.build("agent_001")
        assert isinstance(ctx, dict)
        assert ctx["agent_id"] == "agent_001"
        assert "personal" in ctx
        assert "local" in ctx
        assert "global" in ctx

    def test_build_no_hub_fallback_structure(self, minimal_agents):
        """Fallback context should have expected keys."""
        builder = TieredContextBuilder(
            agents=minimal_agents,
            hub=None,
            global_news=["Drought warning issued"],
        )
        ctx = builder.build("agent_001")
        assert ctx["global"] == ["Drought warning issued"]
        assert ctx["local"]["social"] == []
        assert ctx["local"]["spatial"] == {}
        assert "institutional" in ctx

    def test_build_no_hub_with_env_context(self, minimal_agents):
        """env_context kwarg should work without hub."""
        builder = TieredContextBuilder(
            agents=minimal_agents,
            hub=None,
        )
        env = {"year": 5, "drought_index": 0.7}
        ctx = builder.build("agent_001", env_context=env)
        assert ctx["agent_id"] == "agent_001"

    def test_build_no_hub_agent_type(self, minimal_agents):
        """Agent type should be extracted from agent object."""
        builder = TieredContextBuilder(
            agents=minimal_agents,
            hub=None,
        )
        ctx = builder.build("agent_001")
        assert ctx["agent_type"] == "irrigation_farmer"

    def test_build_no_hub_unknown_agent(self, minimal_agents):
        """build() should not crash for unknown agent_id."""
        builder = TieredContextBuilder(
            agents=minimal_agents,
            hub=None,
        )
        ctx = builder.build("nonexistent_agent")
        assert ctx["agent_id"] == "nonexistent_agent"
        assert ctx["agent_type"] == "default"


class TestNoHubPersonalPopulation:
    """Fix 1A: Verify personal dict is populated from agent attributes."""

    def test_custom_attributes_reach_personal(self):
        agent = _make_irrigation_agent()
        builder = TieredContextBuilder(agents={"a1": agent}, hub=None)
        ctx = builder.build("a1")
        p = ctx["personal"]
        assert p["narrative_persona"] == "You are a bold farmer in the Lower Basin."
        assert p["basin"] == "lower_basin"
        assert p["water_right"] == 50000.0

    def test_bare_attrs_reach_personal(self):
        agent = _make_irrigation_agent()
        builder = TieredContextBuilder(agents={"a1": agent}, hub=None)
        ctx = builder.build("a1")
        p = ctx["personal"]
        assert p["water_situation_text"] == "Drought index is 0.7, moderate scarcity."
        assert p["conservation_status"] == "have not yet adopted"
        assert p["trust_forecasts_text"] == "are sceptical of"
        assert p["trust_neighbors_text"] == "occasionally listen to"

    def test_dynamic_state_overlay(self):
        agent = _make_irrigation_agent()
        agent.dynamic_state = {"at_allocation_cap": True, "penalty_count": 3}
        builder = TieredContextBuilder(agents={"a1": agent}, hub=None)
        ctx = builder.build("a1")
        assert ctx["personal"]["at_allocation_cap"] is True
        assert ctx["personal"]["penalty_count"] == 3


class TestMemoryProviderPropagation:
    """Fix 1B: Verify MemoryProvider engine gets updated."""

    def test_provider_engine_initially_none(self):
        agent = _make_irrigation_agent()
        builder = TieredContextBuilder(agents={"a1": agent}, hub=None)
        mem_providers = [p for p in builder.providers if isinstance(p, MemoryProvider)]
        assert len(mem_providers) == 1
        assert mem_providers[0].engine is None

    def test_provider_engine_set_at_init(self):
        from broker.components.engines.window_engine import WindowMemoryEngine
        agent = _make_irrigation_agent()
        mem = WindowMemoryEngine(window_size=3)
        builder = TieredContextBuilder(agents={"a1": agent}, hub=None, memory_engine=mem)
        mem_providers = [p for p in builder.providers if isinstance(p, MemoryProvider)]
        assert mem_providers[0].engine is mem


class TestFormatPromptMemory:
    """Fix 1C: Verify memory list/dict formatting in format_prompt."""

    def _build_context_with_memory(self, memory_val):
        agent = _make_irrigation_agent()
        template = "Memory: {memory}"
        builder = TieredContextBuilder(
            agents={"a1": agent}, hub=None,
            prompt_templates={"irrigation_farmer": template, "default": template},
        )
        ctx = builder.build("a1")
        ctx["personal"]["memory"] = memory_val
        return builder.format_prompt(ctx)

    def test_list_memory(self):
        result = self._build_context_with_memory(["Year 1: Maintained demand", "Year 2: Adopted efficiency"])
        assert "Year 1: Maintained demand" in result
        assert "Year 2: Adopted efficiency" in result
        assert "[N/A]" not in result

    def test_hierarchical_memory(self):
        result = self._build_context_with_memory({
            "episodic": ["Recent: curtailment hit hard"],
            "semantic": ["Long-term: droughts are worsening"],
            "core": {"trait": "cautious"},
        })
        assert "CORE:" in result
        assert "RECENT:" in result
        assert "HISTORIC:" in result
        assert "curtailment hit hard" in result

    def test_empty_memory(self):
        result = self._build_context_with_memory([])
        assert "No memories yet." in result
        assert "[N/A]" not in result

    def test_no_n_a_in_full_prompt(self):
        """End-to-end: irrigation template with all fields should have zero [N/A]."""
        agent = _make_irrigation_agent()
        template = (
            "{narrative_persona}\n{water_situation_text}\n"
            "Memory: {memory}\n"
            "You currently {conservation_status} water conservation.\n"
            "You {trust_forecasts_text} forecasts. You {trust_neighbors_text} neighbors."
        )
        builder = TieredContextBuilder(
            agents={"a1": agent}, hub=None,
            prompt_templates={"irrigation_farmer": template, "default": template},
        )
        ctx = builder.build("a1")
        prompt = builder.format_prompt(ctx)
        assert "[N/A]" not in prompt
        assert "You are a bold farmer" in prompt
        assert "Drought index" in prompt
        assert "No memories yet." in prompt
        assert "have not yet adopted" in prompt
        assert "are sceptical of" in prompt
