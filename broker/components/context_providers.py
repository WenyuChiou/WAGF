"""Context provider implementations.

Phase 8: Added SDK observer support for domain-agnostic observation.
"""
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
from broker.utils.logging import setup_logger

from .memory_engine import MemoryEngine
from .interaction_hub import InteractionHub

# SDK observer imports (optional, for Phase 8)
if TYPE_CHECKING:
    from cognitive_governance.v1_prototype.social import SocialObserver
    from cognitive_governance.v1_prototype.observation import EnvironmentObserver
    from broker.components.event_manager import EnvironmentEventManager

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

        # Handle both dict and object agents
        if isinstance(agent, dict):
            for k, v in agent.items():
                if not k.startswith("_") and isinstance(v, (str, int, float, bool)) and k not in state:
                    state[k] = v
        else:
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
            for k, v in agent.custom_attributes.items():
                if k not in state:
                    state[k] = v

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
    """Provides T1 Social/Spatial context from InteractionHub.

    Phase 8: Supports SDK SocialObserver for domain-agnostic observation.
    """

    def __init__(
        self,
        hub: InteractionHub,
        observer: Optional["SocialObserver"] = None,
    ):
        self.hub = hub
        self.observer = observer  # SDK observer (optional)

    def provide(self, agent_id, agents, context, **kwargs):
        spatial = self.hub.get_spatial_context(agent_id, agents)

        # Phase 8: Use SDK observer if available
        if self.observer:
            social = self.hub.get_social_context_v2(agent_id, agents, self.observer)
        else:
            social = self.hub.get_social_context(agent_id, agents)

        local = context.setdefault("local", {})
        local["spatial"] = spatial
        local["social"] = social.get("gossip", []) if isinstance(social, dict) else social
        local["visible_actions"] = social.get("visible_actions", []) if isinstance(social, dict) else []

        # Phase 8: Include aggregated observable attributes from SDK
        if self.observer and isinstance(social, dict):
            local["observable_attrs"] = social.get("observable_attrs", {})


class EnvironmentObservationProvider(ContextProvider):
    """Provides environment observation using SDK EnvironmentObserver.

    Phase 8: Uses domain-agnostic observer pattern for environment sensing.
    This is separate from the legacy EnvironmentProvider which checks for
    agent.observe() method.
    """

    def __init__(
        self,
        observer: "EnvironmentObserver",
        environment: Any,
    ):
        self.observer = observer
        self.environment = environment

    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent:
            return

        # Use SDK observer
        observation = self.observer.observe(agent, self.environment)

        local = context.setdefault("local", {})
        local["sensed_environment"] = observation.sensed_state
        local["detected_events"] = observation.detected_events
        local["observation_accuracy"] = observation.observation_accuracy


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


class ObservableStateProvider(ContextProvider):
    """Injects observable state metrics into agent context.

    Provides cross-agent observation: agents can see metrics computed from
    other agents' states (e.g., "45% of neighbors have insurance").

    Adds `observables` dict to context with:
    - Community-level metrics (all agents see same values)
    - Neighborhood-level metrics (agent-specific based on neighbors)
    - Type-level metrics (agent's type group)

    Usage:
        from broker.components.observable_state import ObservableStateManager
        from broker.components.context_providers import ObservableStateProvider

        manager = ObservableStateManager()
        manager.register_many(create_flood_observables())
        provider = ObservableStateProvider(manager)

        # Add to context builder
        ctx_builder.providers.append(provider)
    """

    def __init__(self, state_manager: "ObservableStateManager"):
        """Initialize with an ObservableStateManager.

        Args:
            state_manager: Manager that computes and caches observables
        """
        self.state_manager = state_manager

    def provide(self, agent_id: str, agents: Dict[str, Any], context: Dict[str, Any], **kwargs):
        """Inject observable values into agent context.

        Args:
            agent_id: Current agent's ID
            agents: All agents in simulation
            context: Context dict to populate
            **kwargs: Additional context (unused)
        """
        if not self.state_manager.snapshot:
            return

        observables = context.setdefault("observables", {})
        snapshot = self.state_manager.snapshot

        # Community-level metrics (same for all agents)
        for name, value in snapshot.community.items():
            observables[name] = value

        # Neighborhood-level metrics (agent-specific)
        if agent_id in snapshot.by_neighborhood:
            for name, value in snapshot.by_neighborhood[agent_id].items():
                observables[f"my_{name}"] = value  # Prefix with "my_" for clarity

        # Type-level metrics (agent's type group)
        agent = agents.get(agent_id)
        if agent:
            agent_type = getattr(agent, 'agent_type', 'default')
            if isinstance(agent, dict):
                agent_type = agent.get('agent_type', 'default')
            for name, by_type in snapshot.by_type.items():
                if agent_type in by_type:
                    observables[f"type_{name}"] = by_type[agent_type]

        # Spatial-level metrics (agent's region)
        if agent:
            region = getattr(agent, 'region', None) or getattr(agent, 'tract_id', None)
            if isinstance(agent, dict):
                region = agent.get('region') or agent.get('tract_id')
            if region:
                for name, by_region in snapshot.by_region.items():
                    if region in by_region:
                        observables[f"region_{name}"] = by_region[region]


class EnvironmentEventProvider(ContextProvider):
    """Injects environment events into agent context.

    Provides discrete environment events (e.g., flood, market crash) to agents.
    Events are filtered by agent location and relevance (GLOBAL, REGIONAL, LOCAL, AGENT scope).

    Adds `events` list to context with event details:
    - type: Event type identifier (e.g., "flood", "no_flood")
    - severity: Impact level (info, minor, moderate, severe, critical)
    - description: Human-readable description
    - data: Event-specific payload (e.g., intensity, year)

    Usage:
        from broker.components.event_manager import EnvironmentEventManager
        from broker.components.event_generators.flood import FloodEventGenerator
        from broker.components.context_providers import EnvironmentEventProvider

        event_manager = EnvironmentEventManager()
        event_manager.register("flood", FloodEventGenerator())
        provider = EnvironmentEventProvider(event_manager)

        # Add to context builder
        ctx_builder.providers.append(provider)

        # In pre_year hook:
        event_manager.generate_all(year)
    """

    def __init__(self, event_manager: "EnvironmentEventManager"):
        """Initialize with an EnvironmentEventManager.

        Args:
            event_manager: Manager that orchestrates event generators
        """
        self.event_manager = event_manager

    def provide(self, agent_id: str, agents: Dict[str, Any], context: Dict[str, Any], **kwargs):
        """Inject relevant events into agent context.

        Args:
            agent_id: Current agent's ID
            agents: All agents in simulation
            context: Context dict to populate
            **kwargs: Additional context (unused)
        """
        agent = agents.get(agent_id)
        if not agent:
            return

        # Get agent location for spatial filtering
        if isinstance(agent, dict):
            location = agent.get('location') or agent.get('tract_id')
        else:
            location = getattr(agent, 'location', None) or getattr(agent, 'tract_id', None)

        # Get relevant events filtered by agent location
        events = self.event_manager.get_events_for_agent(agent_id, location)

        # Inject into context
        context["events"] = [
            {
                "type": e.event_type,
                "severity": e.severity.value,
                "description": e.description,
                "data": e.data,
                "domain": e.domain,
            }
            for e in events
        ]


class PerceptionAwareProvider(ContextProvider):
    """Applies perception filter as final step in context building.

    Task-043: Agent-type aware perception transformation.

    This provider MUST be added LAST to the provider chain. It transforms
    the full context based on agent type:

    - Household agents: Numerical data → qualitative descriptions
      ("$25,000 damage" → "significant damage")
    - Government agents: Full numerical data preserved
    - Insurance agents: Full numerical data for policyholders

    For MG (Marginalized Group) agents, community-wide observables are
    removed, keeping only personal ("my_" prefixed) observables.

    Usage:
        from broker.components.context_providers import PerceptionAwareProvider
        from broker.components.perception_filter import PerceptionFilterRegistry

        # Use default filters
        provider = PerceptionAwareProvider()

        # Or provide custom registry
        registry = PerceptionFilterRegistry()
        registry.register("custom_type", CustomFilter())
        provider = PerceptionAwareProvider(registry)

        # Add LAST to context builder
        ctx_builder.providers.append(provider)
    """

    def __init__(self, filter_registry: "PerceptionFilterRegistry" = None):
        """Initialize with optional custom filter registry.

        Args:
            filter_registry: Registry of perception filters by agent type.
                If None, creates default registry with household/government/insurance filters.
        """
        self._registry = filter_registry
        self._initialized = False

    def _ensure_registry(self):
        """Lazy initialization of registry to avoid circular imports."""
        if not self._initialized:
            if self._registry is None:
                from broker.components.perception_filter import PerceptionFilterRegistry
                self._registry = PerceptionFilterRegistry()
            self._initialized = True

    def provide(self, agent_id: str, agents: Dict[str, Any], context: Dict[str, Any], **kwargs):
        """Apply perception filter to transform context for agent type.

        Args:
            agent_id: Current agent's ID
            agents: All agents in simulation
            context: Context dict to transform (modified in place)
            **kwargs: Additional context (unused)
        """
        self._ensure_registry()

        agent = agents.get(agent_id)
        if not agent:
            return

        # Determine agent type
        if isinstance(agent, dict):
            agent_type = agent.get('agent_type', 'household')
        else:
            agent_type = getattr(agent, 'agent_type', 'household')

        # Apply perception filter
        filtered = self._registry.filter_context(agent_type, context, agent)

        # Replace context contents with filtered version
        context.clear()
        context.update(filtered)

        # Add perception metadata for audit trail
        context["_perception"] = {
            "agent_type": agent_type,
            "filter_applied": True,
        }


class InsuranceInfoProvider(ContextProvider):
    """Pre-decision insurance cost disclosure for agents.

    Injects insurance premium information into agent context so agents
    have symmetric cost information for all adaptation options (not just
    elevation grants).

    Literature: DYNAMO model (de Ruig et al. 2023) uses NFIP actuarial
    premium structure as input to agent decisions.

    Reference: Task-060A Insurance Premium Disclosure
    """

    def __init__(
        self,
        premium_calculator: Callable[[str, Any, Dict[str, Any]], Dict[str, Any]],
        mode: str = "qualitative",
    ):
        """Initialize with a domain-specific premium calculator.

        Args:
            premium_calculator: Function(agent_id, agent, env_context) -> dict
                with keys: text, amount, pct_of_income, affordability_level
            mode: "qualitative" (narrative) or "quantitative" (numeric)
        """
        self.premium_calculator = premium_calculator
        self.mode = mode

    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent:
            return

        env_context = kwargs.get("env_context", {})
        # Also check context for env_state (TieredContextBuilder pattern)
        if not env_context:
            env_context = context.get("env_state", {})

        cost_info = self.premium_calculator(agent_id, agent, env_context)
        personal = context.setdefault("personal", {})
        personal["insurance_cost_text"] = cost_info.get("text", "")
        personal["insurance_premium_amount"] = cost_info.get("amount", 0)
        personal["insurance_pct_of_income"] = cost_info.get("pct_of_income", 0)
        personal["insurance_affordability"] = cost_info.get("affordability_level", "unknown")


class FinancialCostProvider(ContextProvider):
    """Pre-decision financial cost disclosure for all adaptation options.

    Injects per-agent elevation costs, buyout offers, and other financial
    details into agent context. Uses agent RCV, subsidy rate, and foundation
    type to compute personalized cost estimates.

    Reference: Paper 3 Section 3.3 (Financial information in prompt)
    """

    # Baseline elevation costs by feet (pre-subsidy, average US)
    ELEVATION_COST_BASE = {
        3: 45000,
        5: 80000,
        8: 150000,
    }

    # Buyout offer as fraction of pre-flood RCV
    BUYOUT_OFFER_FRACTION = 0.75

    def __init__(self, subsidy_rate_fn: Optional[Callable] = None):
        """Initialize with optional dynamic subsidy rate function.

        Args:
            subsidy_rate_fn: Optional callable() -> float returning current
                subsidy rate. If None, reads from env_context.
        """
        self.subsidy_rate_fn = subsidy_rate_fn

    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent:
            return

        env_context = kwargs.get("env_context", {})
        if not env_context:
            env_context = context.get("env_state", {})

        personal = context.setdefault("personal", {})

        # Get subsidy rate
        if self.subsidy_rate_fn:
            subsidy_rate = self.subsidy_rate_fn()
        else:
            subsidy_rate = env_context.get("subsidy_rate", 0.5)

        # Get agent's RCV (replacement cost value) from fixed_attributes or direct attribute
        fixed = getattr(agent, "fixed_attributes", {}) or {}
        rcv_building = fixed.get("rcv_building", 0)
        if not rcv_building:
            if hasattr(agent, "rcv_building"):
                rcv_building = agent.rcv_building
            elif isinstance(agent, dict):
                rcv_building = agent.get("rcv_building", 0)

        rcv_contents = fixed.get("rcv_contents", 0)
        income = fixed.get("income", 50000)
        premium_rate = env_context.get("premium_rate", 0.02)

        # Elevation costs (after subsidy)
        for feet, base_cost in self.ELEVATION_COST_BASE.items():
            after_subsidy = base_cost * (1 - subsidy_rate)
            personal[f"elevation_cost_{feet}ft"] = after_subsidy

        # Buyout offer
        buyout_offer = rcv_building * self.BUYOUT_OFFER_FRACTION
        personal["buyout_offer"] = buyout_offer

        # Per-agent insurance premium estimate
        property_value = rcv_building + rcv_contents
        current_premium = premium_rate * property_value
        personal["current_premium"] = current_premium

        # Subsidy rate (ensure it's in context for template)
        personal["subsidy_rate"] = subsidy_rate


__all__ = [
    "ContextProvider",
    "SystemPromptProvider",
    "AttributeProvider",
    "PrioritySchemaProvider",
    "EnvironmentProvider",
    "EnvironmentObservationProvider",  # Phase 8: SDK observer
    "MemoryProvider",
    "SocialProvider",
    "InstitutionalProvider",
    "DynamicStateProvider",
    "NarrativeProvider",
    "ObservableStateProvider",  # Task-041: Cross-agent observation
    "EnvironmentEventProvider",  # Task-042: Environment events
    "PerceptionAwareProvider",  # Task-043: Agent-type perception
    "InsuranceInfoProvider",  # Task-060A: Insurance premium disclosure
    "FinancialCostProvider",  # Paper 3: Per-agent financial cost disclosure
]
