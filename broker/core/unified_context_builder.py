"""
Unified Context Builder - SA/MA compatible context construction.

This module provides a unified context builder that supports both Single-Agent (SA)
and Multi-Agent (MA) modes. It replaces the separate context builders with a single,
configurable implementation.

Part of Task-040: SA/MA Unified Architecture (Part 14.3)
Part of Task-041: Universal Prompt/Context/Governance Framework (build_universal_context)
"""
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass
import logging

from broker.components.context_providers import (
    ContextProvider,
    AttributeProvider,
    MemoryProvider,
    SocialProvider,
    InstitutionalProvider,
    DynamicStateProvider,
    NarrativeProvider,
    EnvironmentObservationProvider,
)
from broker.components.memory_engine import MemoryEngine
from broker.components.interaction_hub import InteractionHub
from broker.config.agent_types.registry import AgentTypeRegistry
from broker.interfaces.context_types import (
    UniversalContext,
    MemoryContext,
    PsychologicalFrameworkType,
)

if TYPE_CHECKING:
    from broker.components.skill_registry import SkillRegistry
    from cognitive_governance.v1_prototype.social import SocialObserver
    from cognitive_governance.v1_prototype.observation import EnvironmentObserver

logger = logging.getLogger(__name__)


class AgentTypeContextProvider(ContextProvider):
    """
    Provides agent type specific context from the AgentTypeRegistry.

    Used in MA mode when enable_multi_type is True.
    """

    def __init__(self, registry: AgentTypeRegistry):
        self.registry = registry

    def provide(self, agent_id: str, agents: Dict[str, Any], context: Dict[str, Any], **kwargs):
        agent = agents.get(agent_id)
        if not agent:
            return

        agent_type = getattr(agent, "agent_type", "default")
        type_def = self.registry.get(agent_type)

        if type_def:
            context["agent_type_definition"] = {
                "type_id": type_def.type_id,
                "category": type_def.category.value if hasattr(type_def.category, 'value') else str(type_def.category),
                "framework": type_def.psychological_framework.value if hasattr(type_def.psychological_framework, 'value') else str(type_def.psychological_framework),
                "eligible_skills": type_def.eligible_skills,
                "constructs": list(type_def.constructs.keys()) if type_def.constructs else [],
            }


class SkillEligibilityProvider(ContextProvider):
    """
    Provides skill eligibility information based on agent type.

    Used in MA mode when enable_multi_type is True.
    """

    def __init__(
        self,
        skill_registry: "SkillRegistry",
        agent_type_registry: Optional[AgentTypeRegistry] = None,
    ):
        self.skill_registry = skill_registry
        self.agent_type_registry = agent_type_registry

    def provide(self, agent_id: str, agents: Dict[str, Any], context: Dict[str, Any], **kwargs):
        agent = agents.get(agent_id)
        if not agent:
            return

        agent_type = getattr(agent, "agent_type", "default")

        # Get eligible skills from agent type definition
        eligible_skills = []
        if self.agent_type_registry:
            type_def = self.agent_type_registry.get(agent_type)
            if type_def and type_def.eligible_skills:
                eligible_skills = type_def.eligible_skills

        # If no type-specific eligibility, check skill registry
        if not eligible_skills and self.skill_registry:
            all_skills = self.skill_registry.list_skills()
            for skill_id in all_skills:
                result = self.skill_registry.check_eligibility(skill_id, agent_type)
                if result.valid:
                    eligible_skills.append(skill_id)

        context["eligible_skills"] = eligible_skills
        context["available_skills"] = eligible_skills


class UnifiedContextBuilder:
    """
    Unified context builder supporting both SA and MA modes.

    This builder consolidates the functionality of TieredContextBuilder with
    additional support for multi-agent configurations. It uses a provider
    pipeline pattern for extensibility.

    Mode-based provider selection:
        - Always include: AttributeProvider, MemoryProvider
        - If enable_social: add SocialProvider
        - If enable_multi_type and MA mode: add AgentTypeContextProvider, SkillEligibilityProvider

    Usage (SA mode):
        builder = UnifiedContextBuilder(
            agents=agents,
            mode="single_agent",
            hub=interaction_hub,
            memory_engine=memory_engine,
        )
        context = builder.build_context("agent_001", year=1)

    Usage (MA mode with multi-type):
        builder = UnifiedContextBuilder(
            agents=agents,
            mode="multi_agent",
            enable_multi_type=True,
            hub=interaction_hub,
            memory_engine=memory_engine,
            agent_type_registry=registry,
            skill_registry=skill_registry,
        )
        context = builder.build_context("household_001", year=1)
    """

    def __init__(
        self,
        agents: Dict[str, Any],
        mode: str = "single_agent",  # "single_agent" | "multi_agent"
        enable_social: bool = False,
        enable_media: bool = False,
        enable_multi_type: bool = False,
        prompt_templates: Dict[str, str] = None,
        memory_engine: Optional[MemoryEngine] = None,
        agent_type_registry: Optional[AgentTypeRegistry] = None,
        hub: Optional[InteractionHub] = None,  # SA: required if enable_social
        environment: Optional[Dict] = None,     # MA: global environment state
        skill_registry: Optional["SkillRegistry"] = None,
        # Phase 8: SDK observer support
        social_observer: Optional["SocialObserver"] = None,
        environment_observer: Optional["EnvironmentObserver"] = None,
        # Additional configuration
        dynamic_whitelist: Optional[List[str]] = None,
        global_news: Optional[List[str]] = None,
        media_hub: Optional[Any] = None,
        yaml_path: Optional[str] = None,
        max_prompt_tokens: int = 16384,
    ):
        """
        Initialize the UnifiedContextBuilder.

        Args:
            agents: Dictionary of agent_id -> agent object
            mode: Operating mode ("single_agent" or "multi_agent")
            enable_social: Enable social context (gossip, visible actions)
            enable_media: Enable media channel context
            enable_multi_type: Enable multi-agent-type support (MA mode)
            prompt_templates: Custom prompt templates per agent type
            memory_engine: Memory engine for historical traces
            agent_type_registry: Registry for agent type definitions
            hub: InteractionHub for social/spatial context (required for social features)
            environment: Environment state dictionary
            skill_registry: Registry for skill definitions
            social_observer: SDK SocialObserver (Phase 8)
            environment_observer: SDK EnvironmentObserver (Phase 8)
            dynamic_whitelist: List of environment keys to inject
            global_news: Global news items
            media_hub: Media hub for broadcast/peer messages
            yaml_path: Path to YAML config file
            max_prompt_tokens: Maximum prompt token limit
        """
        self.agents = agents
        self.mode = mode
        self.enable_social = enable_social
        self.enable_media = enable_media
        self.enable_multi_type = enable_multi_type
        self.prompt_templates = prompt_templates or {}
        self.memory_engine = memory_engine
        self.agent_type_registry = agent_type_registry
        self.hub = hub
        self.environment = environment or {}
        self.skill_registry = skill_registry
        self.social_observer = social_observer
        self.environment_observer = environment_observer
        self.dynamic_whitelist = dynamic_whitelist or []
        self.global_news = global_news or []
        self.media_hub = media_hub
        self.yaml_path = yaml_path
        self.max_prompt_tokens = max_prompt_tokens

        # Validate configuration
        if enable_social and hub is None:
            raise ValueError(
                "InteractionHub is required when enable_social=True. "
                "Please provide a hub instance."
            )

        if enable_multi_type and agent_type_registry is None:
            logger.warning(
                "enable_multi_type=True but no agent_type_registry provided. "
                "Multi-type features will be limited."
            )

        # Build the provider pipeline
        self.providers = self._build_providers()

    def _build_providers(self) -> List[ContextProvider]:
        """
        Build the provider pipeline based on mode and feature flags.

        Returns:
            List of ContextProvider instances
        """
        providers: List[ContextProvider] = []

        # Dynamic state provider (environment keys injection)
        if self.dynamic_whitelist:
            providers.append(DynamicStateProvider(self.dynamic_whitelist))

        # Core providers (always included)
        providers.append(AttributeProvider())

        # Memory provider
        if self.memory_engine:
            providers.append(MemoryProvider(self.memory_engine))

        # Social provider (if enabled and hub available)
        if self.enable_social and self.hub:
            providers.append(SocialProvider(self.hub, observer=self.social_observer))

        # Narrative provider
        providers.append(NarrativeProvider())

        # Institutional provider (if hub has environment)
        if self.hub and getattr(self.hub, "environment", None):
            providers.append(InstitutionalProvider(self.hub.environment))

        # Environment observation provider (SDK Phase 8)
        if self.environment_observer and self.hub and getattr(self.hub, "environment", None):
            providers.append(
                EnvironmentObservationProvider(self.environment_observer, self.hub.environment)
            )

        # Multi-type providers (MA mode only)
        if self.enable_multi_type and self.mode == "multi_agent":
            if self.agent_type_registry:
                providers.append(AgentTypeContextProvider(self.agent_type_registry))

            if self.skill_registry:
                providers.append(
                    SkillEligibilityProvider(
                        self.skill_registry,
                        self.agent_type_registry,
                    )
                )

        return providers

    def build_context(self, agent_id: str, year: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Build context for an agent.

        This method gathers context from all configured providers and returns
        a unified context dictionary suitable for LLM prompt construction.

        Args:
            agent_id: The agent identifier
            year: Current simulation year (optional)
            **kwargs: Additional context parameters

        Returns:
            Dict containing:
                - agent_id: Agent identifier
                - agent_type: Agent type string
                - state: Agent state attributes
                - memory: Retrieved memory items (if memory_engine enabled)
                - local: Local context (spatial, social, visible_actions)
                - global: Global news/events
                - institutional: Institutional context
                - personal: Personal context (alias for backward compatibility)
                - eligible_skills: List of eligible skills (if multi-type enabled)
                - agent_type_definition: Type definition (if multi-type enabled)
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return {"agent_id": agent_id, "error": "Agent not found"}

        # Initialize context
        context: Dict[str, Any] = {
            "agent_id": agent_id,
            "agent_type": getattr(agent, "agent_type", "default"),
            "agent_name": getattr(agent, "name", agent_id),
            "state": {},
            "personal": {},
            "local": {},
            "global": list(self.global_news),
            "institutional": {},
        }

        if year is not None:
            context["year"] = year
            kwargs["env_context"] = kwargs.get("env_context", {})
            kwargs["env_context"]["year"] = year

        # Use InteractionHub's tiered context if available and social enabled
        if self.enable_social and self.hub:
            tiered_context = self.hub.build_tiered_context(
                agent_id, self.agents, self.global_news
            )
            context.update(tiered_context)

        # Apply all providers
        for provider in self.providers:
            provider.provide(agent_id, self.agents, context, **kwargs)

        # Handle media hub (if enabled)
        if self.enable_media and self.media_hub:
            env_context = kwargs.get("env_context", {})
            current_year = env_context.get("year", year or 1)
            media_context = self.media_hub.get_media_context(agent_id, current_year)
            if media_context:
                broadcast = media_context.get("broadcast", media_context.get("news", []))
                peer_messages = media_context.get("peer_messages", media_context.get("social_media", []))

                if broadcast:
                    context["global"] = broadcast
                if peer_messages:
                    local = context.get("local") or {}
                    local_social = local.get("social", [])
                    local["social"] = local_social + peer_messages
                    context["local"] = local

        # Ensure backward compatibility: 'personal' mirrors relevant state
        if not context.get("personal"):
            context["personal"] = dict(context.get("state", {}))
            context["personal"]["id"] = agent_id

        # Add state alias for validator compatibility
        if "state" not in context or not context["state"]:
            context["state"] = context.get("personal", {})

        return context

    def build_universal_context(
        self,
        agent_id: str,
        year: Optional[int] = None,
        skills: Optional[List[str]] = None,
        **kwargs
    ) -> UniversalContext:
        """
        Build UniversalContext for an agent.

        This method builds a structured UniversalContext suitable for
        prompt assembly, governance validation, and reflection generation.

        Args:
            agent_id: The agent identifier
            year: Current simulation year (optional)
            skills: List of available skill IDs (optional)
            **kwargs: Additional context parameters

        Returns:
            UniversalContext instance with all context populated
        """
        # First build the dict-based context
        ctx_dict = self.build_context(agent_id, year=year, **kwargs)

        # Get agent for type information
        agent = self.agents.get(agent_id)
        agent_type = getattr(agent, "agent_type", "default") if agent else "default"

        # Determine framework
        framework = self._get_framework_for_type(agent_type)

        # Get constructs from framework
        constructs = self._get_constructs_for_type(agent_type)

        # Build memory context
        memory_ctx = self._build_memory_context(ctx_dict)

        # Get eligible skills
        eligible = skills or self.get_eligible_skills(agent_id)

        # Get agent type definition if available
        type_def = None
        if self.agent_type_registry:
            td = self.agent_type_registry.get(agent_type)
            if td:
                type_def = {
                    "type_id": td.type_id,
                    "category": td.category.value if hasattr(td.category, 'value') else str(td.category),
                    "framework": td.psychological_framework.value if hasattr(td.psychological_framework, 'value') else str(td.psychological_framework),
                    "eligible_skills": td.eligible_skills,
                }

        return UniversalContext(
            agent_id=agent_id,
            agent_type=agent_type,
            agent_name=ctx_dict.get("agent_name", agent_id),
            framework=framework,
            constructs=constructs,
            state=ctx_dict.get("state", {}),
            personal=ctx_dict.get("personal", {}),
            local=ctx_dict.get("local", {}),
            institutional=ctx_dict.get("institutional", {}),
            global_context=ctx_dict.get("global", []),
            memory=memory_ctx,
            available_skills=eligible,
            eligible_skills=eligible,
            agent_type_definition=type_def,
            year=year,
        )

    def _get_framework_for_type(self, agent_type: str) -> PsychologicalFrameworkType:
        """
        Get psychological framework for an agent type.

        Args:
            agent_type: The agent type string

        Returns:
            PsychologicalFrameworkType enum value
        """
        if self.agent_type_registry:
            type_def = self.agent_type_registry.get(agent_type)
            if type_def and type_def.psychological_framework:
                fw = type_def.psychological_framework
                fw_str = fw.value if hasattr(fw, 'value') else str(fw)
                try:
                    return PsychologicalFrameworkType(fw_str.lower())
                except ValueError:
                    pass

        # Default mapping based on common agent types
        type_lower = agent_type.lower()
        if "household" in type_lower or "resident" in type_lower:
            return PsychologicalFrameworkType.PMT
        elif "government" in type_lower or "policy" in type_lower:
            return PsychologicalFrameworkType.UTILITY
        elif "insurance" in type_lower or "finance" in type_lower:
            return PsychologicalFrameworkType.FINANCIAL

        return PsychologicalFrameworkType.PMT  # Default

    def _get_constructs_for_type(self, agent_type: str) -> Dict[str, Any]:
        """
        Get construct definitions for an agent type.

        Args:
            agent_type: The agent type string

        Returns:
            Dictionary of construct definitions
        """
        if self.agent_type_registry:
            type_def = self.agent_type_registry.get(agent_type)
            if type_def and type_def.constructs:
                return type_def.constructs

        # Default PMT constructs
        return {
            "TP_LABEL": {"name": "Threat Perception", "values": ["VL", "L", "M", "H", "VH"]},
            "CP_LABEL": {"name": "Coping Perception", "values": ["VL", "L", "M", "H", "VH"]},
        }

    def _build_memory_context(self, ctx_dict: Dict[str, Any]) -> MemoryContext:
        """
        Build MemoryContext from context dictionary.

        Args:
            ctx_dict: Context dictionary from build_context()

        Returns:
            MemoryContext instance
        """
        memory_data = ctx_dict.get("memory", [])

        if isinstance(memory_data, MemoryContext):
            return memory_data
        elif isinstance(memory_data, dict):
            return MemoryContext.from_dict(memory_data)
        elif isinstance(memory_data, list):
            # Legacy format: list of memory strings or dicts
            memories = []
            for m in memory_data:
                if isinstance(m, str):
                    memories.append(m)
                elif isinstance(m, dict):
                    memories.append(m.get("content", str(m)))

            # Extract core state from personal context
            core_state = {}
            personal = ctx_dict.get("personal", {})
            for key in ["elevated", "insured", "relocated", "savings", "income"]:
                if key in personal:
                    core_state[key] = personal[key]

            return MemoryContext(
                core=core_state,
                episodic=memories,
                semantic=[],
                retrieval_info={"source": "build_context"},
            )
        else:
            return MemoryContext()

    def get_eligible_skills(self, agent_id: str) -> List[str]:
        """
        Get eligible skills for an agent.

        Args:
            agent_id: The agent identifier

        Returns:
            List of eligible skill IDs
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return []

        agent_type = getattr(agent, "agent_type", "default")

        # Check agent type registry first
        if self.agent_type_registry:
            return self.agent_type_registry.get_eligible_skills(agent_type)

        # Fallback: check skill registry
        if self.skill_registry:
            eligible = []
            for skill_id in self.skill_registry.list_skills():
                result = self.skill_registry.check_eligibility(skill_id, agent_type)
                if result.valid:
                    eligible.append(skill_id)
            return eligible

        # Final fallback: check agent's own skills
        if hasattr(agent, "get_available_skills"):
            return agent.get_available_skills()

        return []

    def get_agent_type_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent type information.

        Args:
            agent_id: The agent identifier

        Returns:
            Dict with type info or None
        """
        agent = self.agents.get(agent_id)
        if not agent or not self.agent_type_registry:
            return None

        agent_type = getattr(agent, "agent_type", "default")
        type_def = self.agent_type_registry.get(agent_type)

        if type_def:
            return {
                "type_id": type_def.type_id,
                "category": type_def.category.value if hasattr(type_def.category, 'value') else str(type_def.category),
                "framework": type_def.psychological_framework.value if hasattr(type_def.psychological_framework, 'value') else str(type_def.psychological_framework),
                "eligible_skills": type_def.eligible_skills,
                "description": type_def.description,
            }

        return None

    @property
    def mode_config(self) -> Dict[str, bool]:
        """Get current mode configuration."""
        return {
            "mode": self.mode,
            "enable_social": self.enable_social,
            "enable_media": self.enable_media,
            "enable_multi_type": self.enable_multi_type,
        }


# Backward compatibility alias
TieredContextBuilder = UnifiedContextBuilder


def create_unified_context_builder(
    agents: Dict[str, Any],
    mode: str = "single_agent",
    hub: Optional[InteractionHub] = None,
    memory_engine: Optional[MemoryEngine] = None,
    **kwargs,
) -> UnifiedContextBuilder:
    """
    Factory function for creating a UnifiedContextBuilder.

    This function provides sensible defaults based on the mode.

    Args:
        agents: Dictionary of agent_id -> agent object
        mode: Operating mode ("single_agent" or "multi_agent")
        hub: InteractionHub instance
        memory_engine: Memory engine instance
        **kwargs: Additional configuration options

    Returns:
        Configured UnifiedContextBuilder instance
    """
    # Set mode-specific defaults
    if mode == "single_agent":
        kwargs.setdefault("enable_social", hub is not None)
        kwargs.setdefault("enable_multi_type", False)
    elif mode == "multi_agent":
        kwargs.setdefault("enable_social", True)
        kwargs.setdefault("enable_multi_type", True)

    return UnifiedContextBuilder(
        agents=agents,
        mode=mode,
        hub=hub,
        memory_engine=memory_engine,
        **kwargs,
    )


__all__ = [
    "UnifiedContextBuilder",
    "TieredContextBuilder",  # Backward compatibility alias
    "AgentTypeContextProvider",
    "SkillEligibilityProvider",
    "create_unified_context_builder",
    # Re-exported from context_types for convenience
    "UniversalContext",
    "MemoryContext",
    "PsychologicalFrameworkType",
]
