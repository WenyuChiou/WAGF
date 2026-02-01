"""Broker components package.

Core components for the governed broker framework:
- Context building and providers
- Memory systems
- Observable state management
- Perception filters
- Social graph configuration
- Event management
"""

# Perception filter exports (Task-043)
from .perception_filter import (
    HouseholdPerceptionFilter,
    GovernmentPerceptionFilter,
    InsurancePerceptionFilter,
    PerceptionFilterRegistry,
    DOLLAR_AMOUNT_FIELDS,
    PERCENTAGE_FIELDS,
    COMMUNITY_OBSERVABLE_FIELDS,
    NEIGHBOR_ACTION_FIELDS,
)

# Social graph configuration exports (Task-043)
from .social_graph_config import (
    SocialGraphSpec,
    AGENT_SOCIAL_SPECS,
    get_social_spec,
    configure_social_graph_for_agent,
)

# Context provider exports
from .context_providers import (
    ContextProvider,
    PerceptionAwareProvider,
    ObservableStateProvider,
    EnvironmentEventProvider,
)

# Observable state exports (Task-041)
from .observable_state import (
    ObservableStateManager,
    create_flood_observables,
    create_rate_metric,
)

# Event manager exports (Task-042)
from .event_manager import (
    EnvironmentEventManager,
)

# Domain adapter exports
from .domain_adapters import DomainReflectionAdapter

__all__ = [
    # Domain adapters
    "DomainReflectionAdapter",
    # Perception (Task-043)
    "HouseholdPerceptionFilter",
    "GovernmentPerceptionFilter",
    "InsurancePerceptionFilter",
    "PerceptionFilterRegistry",
    "DOLLAR_AMOUNT_FIELDS",
    "PERCENTAGE_FIELDS",
    "COMMUNITY_OBSERVABLE_FIELDS",
    "NEIGHBOR_ACTION_FIELDS",
    # Social graph (Task-043)
    "SocialGraphSpec",
    "AGENT_SOCIAL_SPECS",
    "get_social_spec",
    "configure_social_graph_for_agent",
    # Context providers
    "ContextProvider",
    "PerceptionAwareProvider",
    "ObservableStateProvider",
    "EnvironmentEventProvider",
    # Observable state (Task-041)
    "ObservableStateManager",
    "create_flood_observables",
    "create_rate_metric",
    # Event manager (Task-042)
    "EnvironmentEventManager",
]
