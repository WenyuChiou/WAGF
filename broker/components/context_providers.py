"""Context provider implementations."""
from typing import Dict, List, Any, Optional, Callable
from broker.utils.logging import setup_logger

from .memory_engine import MemoryEngine
from .interaction_hub import InteractionHub

logger = setup_logger(__name__)


class ContextProvider:
    """Interface for context providers."""

    def provide(self, agent_id: str, agents: Dict[str, Any], context: Dict[str, Any], **kwargs):
        pass


class SystemPromptProvider(ContextProvider):
    """Provides mandatory system-level formatting instructions."""

    def provide(self, agent_id, agents, context, **kwargs):
        context["system_prompt"] = (
            "### [STRICT FORMATTING RULE]\n"
            "You MUST wrap your final decision JSON in <decision> and </decision> tags.\n"
            "Example: <decision>{\"strategy\": \"...\", \"confidence\": 0.8, \"decision\": 1}</decision>\n"
            "DO NOT include any commentary outside these tags."
        )


class AttributeProvider(ContextProvider):
    """Provides internal state from agent attributes."""

    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent:
            return

        state = context.setdefault("state", {})
        for k, v in agent.__dict__.items():
            if not k.startswith("_") and isinstance(v, (str, int, float, bool)) and k not in state:
                state[k] = v

        if hasattr(agent, "get_observable_state"):
            state.update(agent.get_observable_state())
        if hasattr(agent, "fixed_attributes"):
            state.update(
                {k: v for k, v in agent.fixed_attributes.items() if isinstance(v, (str, int, float, bool))}
            )
        if hasattr(agent, "dynamic_state"):
            state.update(
                {k: v for k, v in agent.dynamic_state.items() if isinstance(v, (str, int, float, bool))}
            )
        if hasattr(agent, "custom_attributes"):
            state.update(agent.custom_attributes)

        if hasattr(agent, "get_available_skills"):
            context["available_skills"] = agent.get_available_skills()


class PrioritySchemaProvider(ContextProvider):
    """Applies domain-specific priority weights to context attributes."""

    def __init__(self, schema: Dict[str, float] = None):
        self.schema = schema or {}

    def provide(self, agent_id, agents, context, **kwargs):
        if not self.schema:
            return

        state = context.get("state", {})
        priority_items = []

        for attr, priority in sorted(self.schema.items(), key=lambda x: -x[1]):
            if attr in state:
                priority_items.append({"attribute": attr, "value": state[attr], "priority": priority})

        context["priority_schema"] = priority_items
        context["_priority_attributes"] = list(self.schema.keys())


class EnvironmentProvider(ContextProvider):
    """Provides perception signals from the environment."""

    def __init__(self, environment: Dict[str, float]):
        self.environment = environment

    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent or not hasattr(agent, "observe"):
            return

        context["perception"] = agent.observe(self.environment, agents)


class MemoryProvider(ContextProvider):
    """Provides historical traces via MemoryEngine."""

    def __init__(self, engine: Optional[MemoryEngine]):
        self.engine = engine

    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent or not self.engine:
            return

        contextual_boosters = kwargs.get("contextual_boosters")
        env_context = kwargs.get("env_context", {})

        context["memory"] = self.engine.retrieve(
            agent,
            top_k=3,
            contextual_boosters=contextual_boosters,
            world_state=env_context,
        )


class SocialProvider(ContextProvider):
    """Provides T1 Social/Spatial context from InteractionHub."""

    def __init__(self, hub: InteractionHub):
        self.hub = hub

    def provide(self, agent_id, agents, context, **kwargs):
        spatial = self.hub.get_spatial_context(agent_id, agents)
        social = self.hub.get_social_context(agent_id, agents)

        local = context.setdefault("local", {})
        local["spatial"] = spatial
        local["social"] = social


class InstitutionalProvider(ContextProvider):
    """Provides T2/T3 Regional/Institutional context from environment."""

    def __init__(self, environment: "TieredEnvironment"):
        self.environment = environment

    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent:
            return

        global_news = list(self.environment.global_state.values())
        context["global"] = global_news

        local = context.setdefault("local", {})
        tract_id = getattr(agent, "tract_id", None) or getattr(agent, "location", None)
        if tract_id:
            local["environment"] = self.environment.local_states.get(tract_id, {})

        inst_id = getattr(agent, "institution_id", None) or getattr(agent, "agent_type", None)
        if inst_id:
            context["institutional"] = self.environment.institutions.get(inst_id, {})


class DynamicStateProvider(ContextProvider):
    """Injects whitelisted environment state into top-level context."""

    def __init__(self, whitelist: List[str] = None):
        self.whitelist = whitelist or []

    def provide(self, agent_id, agents, context, **kwargs):
        env_context = kwargs.get("env_context", {})
        if not env_context:
            return

        for key in self.whitelist:
            if key in env_context:
                context[key] = env_context[key]


class NarrativeProvider(ContextProvider):
    """Consolidates raw attributes into qualitative narrative strings."""

    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent:
            return

        fixed = getattr(agent, "fixed_attributes", {})
        if not fixed:
            return

        persona_parts = []
        exclude_keys = {"id", "agent_type", "config", "skills", "custom_attributes"}
        for k, v in fixed.items():
            if k not in exclude_keys and isinstance(v, (str, int, float)):
                label = k.replace("_", " ").capitalize()
                persona_parts.append(f"{label}: {v}")

        if persona_parts:
            context["narrative_persona"] = " | ".join(persona_parts)

        history_key = next((k for k in fixed.keys() if "history" in k.lower()), None)
        if history_key:
            hist = fixed.get(history_key, {})
            if isinstance(hist, dict):
                hist_parts = [f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in hist.items()]
                context["history_summary"] = "; ".join(hist_parts)
            else:
                context["history_summary"] = str(hist)


__all__ = [
    "ContextProvider",
    "SystemPromptProvider",
    "AttributeProvider",
    "PrioritySchemaProvider",
    "EnvironmentProvider",
    "MemoryProvider",
    "SocialProvider",
    "InstitutionalProvider",
    "DynamicStateProvider",
    "NarrativeProvider",
]
