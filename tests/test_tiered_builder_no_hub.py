"""Tests for TieredContextBuilder with hub=None (irrigation domain)."""

import pytest
from unittest.mock import MagicMock
from broker.components.tiered_builder import TieredContextBuilder


@pytest.fixture
def minimal_agents():
    """Minimal agent dict for testing."""
    agent = MagicMock()
    agent.agent_type = "irrigation_farmer"
    agent.state = {"income": 50000, "savings": 20000}
    agent.attributes = {"risk_tolerance": 0.5}
    return {"agent_001": agent}


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
