"""Context provider implementations.

Phase 8: Added SDK observer support for domain-agnostic observation.
"""
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING
from broker.utils.logging import setup_logger

from broker.components.memory.engine import MemoryEngine
from broker.components.analytics.interaction import InteractionHub


def get_neighbor_summary(agents: Dict[str, Any], agent_id: str) -> List[Dict[str, Any]]:
    """Get summary of neighbor agents' observable state."""
    summaries = []
    for name, agent in agents.items():
        if name != agent_id:
            summaries.append({
                "agent_name": name,
                "agent_type": getattr(agent, "agent_type", "default"),
                "state_summary": {
                    k: (round(v, 2) if isinstance(v, (int, float)) else v)
                    for k, v in list(getattr(agent, "get_all_state", lambda: {})().items())[:3]
                },
            })
    return summaries[:5]

# SDK observer imports (optional, for Phase 8)
if TYPE_CHECKING:
    from cognitive_governance.v1_prototype.social import SocialObserver
    from cognitive_governance.v1_prototype.observation import EnvironmentObserver
    from broker.components.events.manager import EnvironmentEventManager

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
        query = kwargs.get("query")

        context["memory"] = self.engine.retrieve(
            agent,
            query=query,
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
        from broker.components.analytics.observable import (
            ObservableStateManager, create_rate_metric,
        )
        from .providers import ObservableStateProvider

        manager = ObservableStateManager()
        manager.register_many(domain_observable_metrics)  # see broker/domains/<domain>/
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
        from broker.components.events.manager import EnvironmentEventManager
        from .providers import EnvironmentEventProvider

        event_manager = EnvironmentEventManager()
        # MyHazardEventGenerator is a placeholder for any domain-specific
        # EnvironmentEventGenerator subclass (e.g. FloodEventGenerator
        # at broker.domains.water.event_generators.flood).
        event_manager.register("hazard", MyHazardEventGenerator())
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


class SocialMediaProvider(ContextProvider):
    """Phase 6T-E.B (2026-05-28): inject ``{social_media_feed}``
    into the agent's prompt context.

    Walks ``environment.social_feeds`` (a Dict[author_id, List[Post]]
    populated by domain event handlers when the feed flag is ON),
    filters to authors the agent follows via ``FollowerNetwork``,
    drops suppressed tiers + pack-filter rejects, picks weighted
    top-K and renders via ``pack.verbalise_post``. When the agent
    has no followed authors OR no posts survive filtering, writes
    an empty string — the prompt's ``{social_media_feed}`` placeholder
    then formats to the empty string, byte-identical to a run that
    had no provider at all.

    Audit trail: also writes ``context["_social_media_audit"]`` (a
    list of ``(author_id, event_year, event_type, tier_id)`` tuples)
    so Phase 6T-G cross-channel dedup can join social posts with
    OFFICIAL / GLOBAL channel emissions.

    Phase 6T-E.B: paper-3 byte-identity guard — this class is
    instantiated ONLY when ``UnifiedContextBuilder.enable_social_feeds``
    is True. With the flag OFF (the default for paper-3 flood
    experiments), this class never lands in the provider chain.
    """

    def __init__(
        self,
        environment: Any,
        follower_network: Any,
        pack: Any,
        top_k: int = 5,
        current_year_fn: Optional[Callable[[], int]] = None,
        half_life_years: float = 2.0,
    ):
        """Initialize the provider.

        Args:
            environment: A ``TieredEnvironment`` (or duck-typed object
                exposing ``social_feeds: Dict[str, List[Post]]``).
            follower_network: A ``FollowerNetwork`` exposing
                ``get_followed(agent_id) -> Set[str]``. Posts from
                authors the agent does NOT follow are filtered out.
            pack: The active ``DomainPack``. Required for
                ``credibility_weight`` / ``verbalise_post`` /
                ``suppressed_tiers`` / ``social_media_post_filter``.
            top_k: Max posts injected per agent per call. Default 5
                bounds prompt-length inflation to ~50-200 tokens.
            current_year_fn: Zero-arg callable returning the current
                simulation year (for age-decay). If ``None``, the
                provider reads ``kwargs["year"]`` in ``provide``.
            half_life_years: Age-decay half-life for post weighting.
                A post 2 years old has half the weight of a current
                post; 4 years old = 1/4 weight. Tunable per YAML.
        """
        self.environment = environment
        self.follower_network = follower_network
        self.pack = pack
        self.top_k = top_k
        self.current_year_fn = current_year_fn
        self.half_life_years = half_life_years

    def provide(self, agent_id, agents, context, **kwargs):
        # Lazy import to keep this module importable in environments
        # without the social subpackage on the path (e.g. minimal
        # broker installs).
        from broker.components.social.post import age_weight

        feeds = getattr(self.environment, "social_feeds", None)
        if not feeds:
            context["social_media_feed"] = ""
            context["_social_media_audit"] = []
            return

        agent = agents.get(agent_id)
        if agent is None:
            context["social_media_feed"] = ""
            context["_social_media_audit"] = []
            return

        # Year resolution: explicit fn wins, else kwargs, else 0.
        if self.current_year_fn is not None:
            year = self.current_year_fn()
        else:
            year = kwargs.get("year", 0)

        # Author-graph filter
        followed = self.follower_network.get_followed(agent_id) if self.follower_network else set()
        if not followed:
            context["social_media_feed"] = ""
            context["_social_media_audit"] = []
            return

        suppressed = self.pack.suppressed_tiers() if hasattr(self.pack, "suppressed_tiers") else set()

        candidates = []
        for author_id in followed:
            for post in feeds.get(author_id, []):
                if getattr(post, "tier_id", "") in suppressed:
                    continue
                kept = self.pack.social_media_post_filter(agent, post)
                if kept is None:
                    continue
                candidates.append(kept)

        if not candidates:
            context["social_media_feed"] = ""
            context["_social_media_audit"] = []
            return

        # Weighted top-K. Credibility ranges [0, 1] by convention but
        # we don't enforce — pack-supplied; age_weight is positive;
        # engagement_score is non-negative. The (1 + engagement)
        # factor avoids zeroing a post that no one liked yet.
        def _score(post):
            cred = self.pack.credibility_weight(getattr(post, "tier_id", ""))
            age = age_weight(
                getattr(post, "event_year", year),
                year,
                self.half_life_years,
            )
            eng = float(getattr(post, "engagement_score", 0.0))
            return cred * age * (1.0 + eng)

        ranked = sorted(candidates, key=_score, reverse=True)[: self.top_k]

        rendered = []
        audit = []
        for post in ranked:
            try:
                line = self.pack.verbalise_post(post)
            except Exception:  # noqa: BLE001 — verbalise is operator code, must not break dispatch
                line = f"[{getattr(post, 'tier_id', 'unknown')}] {getattr(post, 'text', '')}"
            rendered.append(f"- {line}")
            audit.append((
                getattr(post, "author_id", ""),
                getattr(post, "event_year", year),
                getattr(post, "event_type", ""),
                getattr(post, "tier_id", ""),
            ))

        # Phase 6T-E.B v0.5.1: byte-identity-safe section format.
        # When EMPTY, the value is "" (no characters at all). The
        # household prompt template places ``{social_media_feed}``
        # flush against surrounding context with no template-side
        # newlines, so an empty value renders to byte-identical text
        # versus a pre-6T-E.B prompt (the placeholder collapses to
        # nothing). When NON-EMPTY, the provider adds its own leading
        # ``\n\n`` + header so the social-media block visually
        # separates from prior context.
        if rendered:
            context["social_media_feed"] = (
                "\n\n## Social media (recent posts):\n"
                + "\n".join(rendered)
            )
        else:
            context["social_media_feed"] = ""
        context["_social_media_audit"] = audit


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
        from .providers import PerceptionAwareProvider
        from broker.components.social.perception import PerceptionFilterRegistry

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
                If None, creates a default registry built from the active DomainPack.
        """
        self._registry = filter_registry
        self._initialized = False

    def _ensure_registry(self):
        """Lazy initialization of registry to avoid circular imports."""
        if not self._initialized:
            if self._registry is None:
                from broker.components.social.perception import PerceptionFilterRegistry
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

        # Determine agent type. Phase 6R-B-1 (2026-05-26 / audit
        # cluster E item #15): removed the silent fallback to the
        # literal ``"household"`` here. That fallback fired only for
        # malformed agents missing the ``agent_type`` field, but in a
        # non-water domain it silently routed them through whatever
        # filter was registered under the ``"household"`` key in the
        # PerceptionFilterRegistry — typically the verbalizing default,
        # which is harmless in practice but masks the upstream bug
        # (the agent constructor forgot to set agent_type). Raising
        # surfaces the bug immediately at the perception layer.
        if isinstance(agent, dict):
            agent_type = agent.get("agent_type")
        else:
            agent_type = getattr(agent, "agent_type", None)
        if not agent_type:
            raise ValueError(
                f"PerceptionAwareProvider: agent {agent_id!r} has no "
                f"`agent_type` attribute (or it's empty). Every agent "
                f"MUST declare its agent_type explicitly so the "
                f"perception filter registry can route it correctly. "
                f"Previously this fell back to the literal 'household' "
                f"string — a flood-domain default that misrouted "
                f"non-water agents. Set agent.agent_type at construction "
                f"time. (Phase 6R-B-1, audit cluster E #15.)"
            )

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


# Phase 6U-C (2026-05-28): InsuranceInfoProvider relocated to
# broker/domains/water/insurance_provider.py. Legacy import path
# preserved via module-level __getattr__ shim at the bottom of this
# file with DeprecationWarning.


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
    "SocialMediaProvider",  # Phase 6T-E.B: feed_flag-gated social-media injection
    "InsuranceInfoProvider",  # Task-060A: Insurance premium disclosure
    "FeedbackDashboardProvider",  # Config-driven env feedback dashboard
    "AgentMetricsTracker",  # Per-agent metrics history for trends
]

# Re-exports from feedback_provider.
# IMPORTANT: feedback_provider.py MUST only import ContextProvider (the base
# class) from this module.  Importing other providers would create a circular
# dependency.
from broker.components.analytics.feedback import FeedbackDashboardProvider, AgentMetricsTracker  # noqa: E402


def __getattr__(name):
    """Phase 6U-C: InsuranceInfoProvider relocated to broker.domains.water.

    Legacy import path preserved with DeprecationWarning. Other
    unknown attributes raise AttributeError as normal.
    """
    if name == "InsuranceInfoProvider":
        import warnings

        from broker.domains.water.insurance_provider import InsuranceInfoProvider

        warnings.warn(
            "InsuranceInfoProvider moved to broker.domains.water.insurance_provider; "
            "import from there",
            DeprecationWarning,
            stacklevel=2,
        )
        return InsuranceInfoProvider
    raise AttributeError(name)
