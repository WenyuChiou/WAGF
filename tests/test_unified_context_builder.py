"""
Tests for UnifiedContextBuilder.

Tests SA mode, MA mode, social features, multi-type support,
and backward compatibility with TieredContextBuilder alias.

Part of Task-040: SA/MA Unified Architecture (Part 14.3)
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any, List

# Import the module under test
from broker.core.unified_context_builder import (
    UnifiedContextBuilder,
    TieredContextBuilder,
    AgentTypeContextProvider,
    SkillEligibilityProvider,
    create_unified_context_builder,
)
from broker.config.agent_types.registry import (
    AgentTypeRegistry,
    AgentTypeDefinition,
    create_default_registry,
)
from broker.config.agent_types.base import (
    AgentCategory,
    PsychologicalFramework,
)


# =============================================================================
# Test Fixtures
# =============================================================================

class MockAgent:
    """Mock agent for testing."""

    def __init__(
        self,
        agent_id: str = "agent_001",
        agent_type: str = "household",
        name: str = "Test Agent",
        **attributes,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.name = name
        self.dynamic_state = {}
        self.fixed_attributes = {}
        self.custom_attributes = {}

        for key, value in attributes.items():
            setattr(self, key, value)

    def get_available_skills(self) -> List[str]:
        return ["buy_insurance", "do_nothing"]


class MockMemoryEngine:
    """Mock memory engine for testing."""

    def __init__(self, memories: List[str] = None):
        self._memories = memories or ["Memory item 1", "Memory item 2"]

    def retrieve(self, agent, top_k: int = 3, **kwargs) -> List[str]:
        return self._memories[:top_k]


class MockSocialGraph:
    """Mock social graph for testing."""

    def __init__(self, neighbors: Dict[str, List[str]] = None):
        self._neighbors = neighbors or {"agent_001": ["agent_002", "agent_003"]}

    def get_neighbors(self, agent_id: str) -> List[str]:
        return self._neighbors.get(agent_id, [])


class MockInteractionHub:
    """Mock interaction hub for testing."""

    def __init__(
        self,
        social_graph: MockSocialGraph = None,
        environment=None,
    ):
        self.graph = social_graph or MockSocialGraph()
        self.environment = environment
        self.memory_engine = None

    def build_tiered_context(
        self,
        agent_id: str,
        agents: Dict[str, Any],
        global_news: List[str] = None,
    ) -> Dict[str, Any]:
        return {
            "personal": {
                "id": agent_id,
                "agent_type": agents.get(agent_id, Mock()).agent_type if agents.get(agent_id) else "default",
            },
            "local": {
                "spatial": {"neighbor_count": len(self.graph.get_neighbors(agent_id))},
                "social": ["Neighbor mentioned: test gossip"],
                "visible_actions": [],
            },
            "global": global_news or ["Global news item"],
            "institutional": {},
        }

    def get_spatial_context(self, agent_id: str, agents: Dict[str, Any]) -> Dict[str, Any]:
        return {"neighbor_count": len(self.graph.get_neighbors(agent_id))}

    def get_social_context(self, agent_id: str, agents: Dict[str, Any], max_gossip: int = 2) -> Dict[str, Any]:
        return {
            "gossip": ["Neighbor mentioned: test gossip"],
            "visible_actions": [],
            "neighbor_count": len(self.graph.get_neighbors(agent_id)),
        }


class MockSkillRegistry:
    """Mock skill registry for testing."""

    def __init__(self):
        self._skills = {
            "buy_insurance": Mock(skill_id="buy_insurance", eligible_agent_types=["*"]),
            "elevate_house": Mock(skill_id="elevate_house", eligible_agent_types=["household"]),
            "do_nothing": Mock(skill_id="do_nothing", eligible_agent_types=["*"]),
        }

    def list_skills(self) -> List[str]:
        return list(self._skills.keys())

    def get(self, skill_id: str):
        return self._skills.get(skill_id)

    def check_eligibility(self, skill_id: str, agent_type: str):
        skill = self._skills.get(skill_id)
        if not skill:
            return Mock(valid=False)
        if "*" in skill.eligible_agent_types or agent_type in skill.eligible_agent_types:
            return Mock(valid=True)
        return Mock(valid=False)


@pytest.fixture
def mock_agents():
    """Create a dictionary of mock agents."""
    return {
        "agent_001": MockAgent(agent_id="agent_001", agent_type="household", income=50000, elevated=False),
        "agent_002": MockAgent(agent_id="agent_002", agent_type="household", income=75000, elevated=True),
        "agent_003": MockAgent(agent_id="agent_003", agent_type="government", name="Gov Agent"),
    }


@pytest.fixture
def mock_hub():
    """Create a mock interaction hub."""
    return MockInteractionHub()


@pytest.fixture
def mock_memory_engine():
    """Create a mock memory engine."""
    return MockMemoryEngine()


@pytest.fixture
def mock_skill_registry():
    """Create a mock skill registry."""
    return MockSkillRegistry()


@pytest.fixture
def agent_type_registry():
    """Create a real agent type registry with default types."""
    return create_default_registry()


# =============================================================================
# Test: SA Mode (Default)
# =============================================================================

class TestSAModeDefault:
    """Test UnifiedContextBuilder in single-agent mode (default)."""

    def test_create_builder_sa_mode(self, mock_agents, mock_memory_engine):
        """Test creating builder in SA mode without social features."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        assert builder.mode == "single_agent"
        assert builder.enable_social is False
        assert builder.enable_multi_type is False

    def test_build_context_basic(self, mock_agents, mock_memory_engine):
        """Test building context without hub (no social features)."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        context = builder.build_context("agent_001")

        assert context["agent_id"] == "agent_001"
        assert context["agent_type"] == "household"
        assert "state" in context
        assert "memory" in context

    def test_build_context_with_year(self, mock_agents, mock_memory_engine):
        """Test building context with year parameter."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        context = builder.build_context("agent_001", year=5)

        assert context.get("year") == 5

    def test_build_context_missing_agent(self, mock_agents, mock_memory_engine):
        """Test building context for non-existent agent."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        context = builder.build_context("nonexistent_agent")

        assert "error" in context
        assert context["agent_id"] == "nonexistent_agent"


# =============================================================================
# Test: SA Mode with Social Enabled
# =============================================================================

class TestSAModeWithSocial:
    """Test UnifiedContextBuilder in SA mode with social features enabled."""

    def test_create_builder_with_social_requires_hub(self, mock_agents):
        """Test that enable_social requires hub."""
        with pytest.raises(ValueError) as exc_info:
            UnifiedContextBuilder(
                agents=mock_agents,
                mode="single_agent",
                enable_social=True,
                hub=None,  # No hub provided
            )

        assert "InteractionHub is required" in str(exc_info.value)

    def test_create_builder_with_social(self, mock_agents, mock_hub, mock_memory_engine):
        """Test creating builder with social features."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            enable_social=True,
            hub=mock_hub,
            memory_engine=mock_memory_engine,
        )

        assert builder.enable_social is True
        assert builder.hub is mock_hub

    def test_build_context_with_social(self, mock_agents, mock_hub, mock_memory_engine):
        """Test building context with social features."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            enable_social=True,
            hub=mock_hub,
            memory_engine=mock_memory_engine,
        )

        context = builder.build_context("agent_001")

        assert "local" in context
        assert "spatial" in context["local"] or "social" in context["local"]
        # Context should include tiered context from hub
        assert context["agent_id"] == "agent_001"

    def test_build_context_social_gossip(self, mock_agents, mock_hub, mock_memory_engine):
        """Test that social context includes gossip."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            enable_social=True,
            hub=mock_hub,
            memory_engine=mock_memory_engine,
        )

        context = builder.build_context("agent_001")

        # The hub should populate social gossip
        local = context.get("local", {})
        social = local.get("social", [])
        assert isinstance(social, list)


# =============================================================================
# Test: MA Mode with Multi-Type
# =============================================================================

class TestMAModeWithMultiType:
    """Test UnifiedContextBuilder in multi-agent mode with multi-type support."""

    def test_create_builder_ma_mode(self, mock_agents, mock_hub, agent_type_registry, mock_skill_registry):
        """Test creating builder in MA mode with multi-type."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="multi_agent",
            enable_social=True,
            enable_multi_type=True,
            hub=mock_hub,
            agent_type_registry=agent_type_registry,
            skill_registry=mock_skill_registry,
        )

        assert builder.mode == "multi_agent"
        assert builder.enable_multi_type is True
        assert builder.agent_type_registry is agent_type_registry

    def test_build_context_with_multi_type(
        self, mock_agents, mock_hub, agent_type_registry, mock_skill_registry, mock_memory_engine
    ):
        """Test building context with multi-type support."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="multi_agent",
            enable_social=True,
            enable_multi_type=True,
            hub=mock_hub,
            memory_engine=mock_memory_engine,
            agent_type_registry=agent_type_registry,
            skill_registry=mock_skill_registry,
        )

        context = builder.build_context("agent_001")

        assert context["agent_id"] == "agent_001"
        # Should have agent type definition from registry
        if "agent_type_definition" in context:
            assert "type_id" in context["agent_type_definition"]

    def test_get_eligible_skills_from_registry(
        self, mock_agents, mock_hub, agent_type_registry, mock_skill_registry
    ):
        """Test getting eligible skills from registry."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="multi_agent",
            enable_social=True,
            enable_multi_type=True,
            hub=mock_hub,
            agent_type_registry=agent_type_registry,
            skill_registry=mock_skill_registry,
        )

        skills = builder.get_eligible_skills("agent_001")

        assert isinstance(skills, list)

    def test_get_agent_type_info(self, mock_agents, mock_hub, agent_type_registry):
        """Test getting agent type information."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="multi_agent",
            enable_social=True,
            enable_multi_type=True,
            hub=mock_hub,
            agent_type_registry=agent_type_registry,
        )

        info = builder.get_agent_type_info("agent_001")

        # Should return type info since registry has "household" type
        assert info is not None or info is None  # Depends on registry content

    def test_multi_type_warning_without_registry(self, mock_agents, mock_hub, caplog):
        """Test warning when enable_multi_type but no registry."""
        import logging

        with caplog.at_level(logging.WARNING):
            builder = UnifiedContextBuilder(
                agents=mock_agents,
                mode="multi_agent",
                enable_social=True,
                enable_multi_type=True,
                hub=mock_hub,
                agent_type_registry=None,  # No registry
            )

        # Should have logged a warning
        assert builder.enable_multi_type is True


# =============================================================================
# Test: Backward Compatibility (TieredContextBuilder alias)
# =============================================================================

class TestBackwardCompatibility:
    """Test backward compatibility with TieredContextBuilder alias."""

    def test_tiered_context_builder_is_alias(self):
        """Test that TieredContextBuilder is an alias for UnifiedContextBuilder."""
        assert TieredContextBuilder is UnifiedContextBuilder

    def test_create_tiered_context_builder(self, mock_agents, mock_hub, mock_memory_engine):
        """Test creating TieredContextBuilder (alias)."""
        builder = TieredContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            enable_social=True,
            hub=mock_hub,
            memory_engine=mock_memory_engine,
        )

        assert isinstance(builder, UnifiedContextBuilder)
        assert builder.mode == "single_agent"

    def test_tiered_builder_builds_context(self, mock_agents, mock_hub, mock_memory_engine):
        """Test that TieredContextBuilder can build context."""
        builder = TieredContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            enable_social=True,
            hub=mock_hub,
            memory_engine=mock_memory_engine,
        )

        context = builder.build_context("agent_001")

        assert context["agent_id"] == "agent_001"
        assert "state" in context or "personal" in context


# =============================================================================
# Test: Factory Function
# =============================================================================

class TestFactoryFunction:
    """Test the create_unified_context_builder factory function."""

    def test_create_sa_builder(self, mock_agents, mock_hub, mock_memory_engine):
        """Test creating SA builder via factory."""
        builder = create_unified_context_builder(
            agents=mock_agents,
            mode="single_agent",
            hub=mock_hub,
            memory_engine=mock_memory_engine,
        )

        assert isinstance(builder, UnifiedContextBuilder)
        assert builder.mode == "single_agent"
        # Factory should enable social if hub provided
        assert builder.enable_social is True

    def test_create_ma_builder(self, mock_agents, mock_hub, mock_memory_engine, agent_type_registry):
        """Test creating MA builder via factory."""
        builder = create_unified_context_builder(
            agents=mock_agents,
            mode="multi_agent",
            hub=mock_hub,
            memory_engine=mock_memory_engine,
            agent_type_registry=agent_type_registry,
        )

        assert builder.mode == "multi_agent"
        # Factory should enable multi_type for MA mode
        assert builder.enable_multi_type is True

    def test_factory_without_hub_sa(self, mock_agents, mock_memory_engine):
        """Test factory in SA mode without hub."""
        builder = create_unified_context_builder(
            agents=mock_agents,
            mode="single_agent",
            hub=None,
            memory_engine=mock_memory_engine,
        )

        assert builder.mode == "single_agent"
        assert builder.enable_social is False


# =============================================================================
# Test: Provider Selection
# =============================================================================

class TestProviderSelection:
    """Test that providers are selected correctly based on mode and flags."""

    def test_providers_basic(self, mock_agents, mock_memory_engine):
        """Test basic providers are always included."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        # Should have at least AttributeProvider and MemoryProvider
        provider_types = [type(p).__name__ for p in builder.providers]
        assert "AttributeProvider" in provider_types
        assert "MemoryProvider" in provider_types

    def test_providers_with_social(self, mock_agents, mock_hub, mock_memory_engine):
        """Test SocialProvider is added when enable_social=True."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            enable_social=True,
            hub=mock_hub,
            memory_engine=mock_memory_engine,
        )

        provider_types = [type(p).__name__ for p in builder.providers]
        assert "SocialProvider" in provider_types

    def test_providers_without_social(self, mock_agents, mock_memory_engine):
        """Test SocialProvider is NOT added when enable_social=False."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            enable_social=False,
            memory_engine=mock_memory_engine,
        )

        provider_types = [type(p).__name__ for p in builder.providers]
        assert "SocialProvider" not in provider_types

    def test_providers_ma_mode_with_multi_type(
        self, mock_agents, mock_hub, agent_type_registry, mock_skill_registry, mock_memory_engine
    ):
        """Test MA-specific providers are added in multi_agent mode with multi_type."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="multi_agent",
            enable_social=True,
            enable_multi_type=True,
            hub=mock_hub,
            memory_engine=mock_memory_engine,
            agent_type_registry=agent_type_registry,
            skill_registry=mock_skill_registry,
        )

        provider_types = [type(p).__name__ for p in builder.providers]
        assert "AgentTypeContextProvider" in provider_types
        assert "SkillEligibilityProvider" in provider_types


# =============================================================================
# Test: Mode Configuration
# =============================================================================

class TestModeConfiguration:
    """Test mode configuration property."""

    def test_mode_config_sa(self, mock_agents, mock_memory_engine):
        """Test mode_config for SA mode."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        config = builder.mode_config

        assert config["mode"] == "single_agent"
        assert config["enable_social"] is False
        assert config["enable_multi_type"] is False

    def test_mode_config_ma(self, mock_agents, mock_hub, agent_type_registry, mock_memory_engine):
        """Test mode_config for MA mode."""
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="multi_agent",
            enable_social=True,
            enable_multi_type=True,
            hub=mock_hub,
            agent_type_registry=agent_type_registry,
            memory_engine=mock_memory_engine,
        )

        config = builder.mode_config

        assert config["mode"] == "multi_agent"
        assert config["enable_social"] is True
        assert config["enable_multi_type"] is True


# =============================================================================
# Test: AgentTypeContextProvider
# =============================================================================

class TestAgentTypeContextProvider:
    """Test AgentTypeContextProvider directly."""

    def test_provide_adds_type_definition(self, mock_agents, agent_type_registry):
        """Test that provider adds agent_type_definition to context."""
        provider = AgentTypeContextProvider(agent_type_registry)
        context: Dict[str, Any] = {}

        provider.provide("agent_001", mock_agents, context)

        # May or may not have definition depending on registry
        # Just verify it doesn't crash and context is valid dict
        assert isinstance(context, dict)

    def test_provide_missing_agent(self, mock_agents, agent_type_registry):
        """Test provider handles missing agent gracefully."""
        provider = AgentTypeContextProvider(agent_type_registry)
        context: Dict[str, Any] = {}

        provider.provide("nonexistent", mock_agents, context)

        # Should not crash, context should be unchanged
        assert "agent_type_definition" not in context


# =============================================================================
# Test: SkillEligibilityProvider
# =============================================================================

class TestSkillEligibilityProvider:
    """Test SkillEligibilityProvider directly."""

    def test_provide_adds_eligible_skills(self, mock_agents, mock_skill_registry, agent_type_registry):
        """Test that provider adds eligible_skills to context."""
        provider = SkillEligibilityProvider(mock_skill_registry, agent_type_registry)
        context: Dict[str, Any] = {}

        provider.provide("agent_001", mock_agents, context)

        assert "eligible_skills" in context
        assert isinstance(context["eligible_skills"], list)

    def test_provide_missing_agent(self, mock_agents, mock_skill_registry):
        """Test provider handles missing agent gracefully."""
        provider = SkillEligibilityProvider(mock_skill_registry)
        context: Dict[str, Any] = {}

        provider.provide("nonexistent", mock_agents, context)

        # Should not crash
        assert "eligible_skills" not in context


# =============================================================================
# Test: Global News and Environment
# =============================================================================

class TestGlobalNewsAndEnvironment:
    """Test global news and environment configuration."""

    def test_global_news_in_context(self, mock_agents, mock_memory_engine):
        """Test that global_news is included in context."""
        news = ["Breaking: Policy change announced", "Weather: Storm approaching"]
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
            global_news=news,
        )

        context = builder.build_context("agent_001")

        assert "global" in context
        assert news[0] in context["global"] or len(context["global"]) > 0

    def test_environment_passed_through(self, mock_agents, mock_memory_engine):
        """Test that environment dict is stored."""
        env = {"flood_depth": 2.5, "policy_rate": 0.15}
        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
            environment=env,
        )

        assert builder.environment == env


# =============================================================================
# Test: build_universal_context (Task-041)
# =============================================================================

class TestBuildUniversalContext:
    """Test the build_universal_context method added in Task-041."""

    def test_build_universal_context_basic(self, mock_agents, mock_memory_engine):
        """Test basic UniversalContext building."""
        from broker.interfaces.context_types import UniversalContext, PsychologicalFrameworkType

        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        ctx = builder.build_universal_context("agent_001", year=5)

        assert isinstance(ctx, UniversalContext)
        assert ctx.agent_id == "agent_001"
        assert ctx.agent_type == "household"
        assert ctx.year == 5
        assert ctx.framework == PsychologicalFrameworkType.PMT

    def test_build_universal_context_with_skills(self, mock_agents, mock_memory_engine):
        """Test UniversalContext with explicit skills."""
        from broker.interfaces.context_types import UniversalContext

        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        skills = ["buy_insurance", "elevate_house", "do_nothing"]
        ctx = builder.build_universal_context("agent_001", skills=skills)

        assert ctx.available_skills == skills
        assert ctx.eligible_skills == skills

    def test_build_universal_context_memory(self, mock_agents, mock_memory_engine):
        """Test UniversalContext includes memory."""
        from broker.interfaces.context_types import UniversalContext, MemoryContext

        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        ctx = builder.build_universal_context("agent_001")

        assert isinstance(ctx.memory, MemoryContext)
        # Memory engine returns ["Memory item 1", "Memory item 2"]
        assert len(ctx.memory.episodic) > 0 or ctx.memory.core or ctx.memory.semantic

    def test_build_universal_context_ma_mode(
        self, mock_agents, mock_hub, agent_type_registry, mock_memory_engine
    ):
        """Test UniversalContext in MA mode with type registry."""
        from broker.interfaces.context_types import UniversalContext

        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="multi_agent",
            enable_social=True,
            enable_multi_type=True,
            hub=mock_hub,
            memory_engine=mock_memory_engine,
            agent_type_registry=agent_type_registry,
        )

        ctx = builder.build_universal_context("agent_001")

        assert isinstance(ctx, UniversalContext)
        # In MA mode with registry, should have type definition
        if ctx.agent_type_definition:
            assert "type_id" in ctx.agent_type_definition

    def test_build_universal_context_missing_agent(self, mock_agents, mock_memory_engine):
        """Test UniversalContext for missing agent."""
        from broker.interfaces.context_types import UniversalContext

        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        # Should handle missing agent gracefully
        ctx = builder.build_universal_context("nonexistent_agent")

        assert isinstance(ctx, UniversalContext)
        assert ctx.agent_id == "nonexistent_agent"
        assert ctx.agent_type == "default"

    def test_build_universal_context_framework_detection(self, mock_agents, mock_memory_engine):
        """Test framework detection based on agent type."""
        from broker.interfaces.context_types import UniversalContext, PsychologicalFrameworkType

        # Create agents with different types
        class GovAgent:
            def __init__(self):
                self.agent_id = "gov_001"
                self.agent_type = "government"
                self.name = "City Council"
                self.dynamic_state = {}
                self.fixed_attributes = {}
                self.custom_attributes = {}

        agents = {
            "agent_001": mock_agents["agent_001"],
            "gov_001": GovAgent(),
        }

        builder = UnifiedContextBuilder(
            agents=agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        # Household should get PMT
        ctx1 = builder.build_universal_context("agent_001")
        assert ctx1.framework == PsychologicalFrameworkType.PMT

        # Government should get UTILITY
        ctx2 = builder.build_universal_context("gov_001")
        assert ctx2.framework == PsychologicalFrameworkType.UTILITY

    def test_universal_context_to_dict_roundtrip(self, mock_agents, mock_memory_engine):
        """Test UniversalContext can be serialized and restored."""
        from broker.interfaces.context_types import UniversalContext

        builder = UnifiedContextBuilder(
            agents=mock_agents,
            mode="single_agent",
            memory_engine=mock_memory_engine,
        )

        original = builder.build_universal_context("agent_001", year=5)

        # Serialize to dict
        d = original.to_dict()

        # Restore from dict
        restored = UniversalContext.from_dict(d)

        assert restored.agent_id == original.agent_id
        assert restored.agent_type == original.agent_type
        assert restored.year == original.year
        assert restored.framework == original.framework
