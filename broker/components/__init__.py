"""Broker components package.

Domain-agnostic cognitive governance components:
- Context building and providers
- Memory systems
- Observable state management
- Perception filters
- Social graph configuration
- Event management
"""

# Perception filter exports
from .social.perception import (
    QualitativePerceptionFilter,
    PassThroughPerceptionFilter,
    PerceptionFilterRegistry,
)

# Social graph configuration exports
from .social.config import (
    SocialGraphSpec,
    AGENT_SOCIAL_SPECS,
    get_social_spec,
    configure_social_graph_for_agent,
)

# Context provider exports
from .context.providers import (
    ContextProvider,
    PerceptionAwareProvider,
    ObservableStateProvider,
    EnvironmentEventProvider,
)

# Observable state exports
from .analytics.observable import (
    ObservableStateManager,
    create_rate_metric,
)

# Event manager exports
from .events.manager import (
    EnvironmentEventManager,
)

# Domain adapter exports
from .cognitive.adapters import DomainReflectionAdapter

__all__ = [
    # Domain adapters
    "DomainReflectionAdapter",
    # Perception
    "QualitativePerceptionFilter",
    "HouseholdPerceptionFilter",  # deprecated alias
    "PassThroughPerceptionFilter",
    "PerceptionFilterRegistry",
    # Social graph
    "SocialGraphSpec",
    "AGENT_SOCIAL_SPECS",
    "get_social_spec",
    "configure_social_graph_for_agent",
    # Context providers
    "ContextProvider",
    "PerceptionAwareProvider",
    "ObservableStateProvider",
    "EnvironmentEventProvider",
    # Observable state
    "ObservableStateManager",
    "create_rate_metric",
    # Event manager
    "EnvironmentEventManager",
]


def __getattr__(name):
    if name == "HouseholdPerceptionFilter":
        import warnings

        warnings.warn(
            "HouseholdPerceptionFilter is deprecated; use QualitativePerceptionFilter",
            DeprecationWarning,
            stacklevel=2,
        )
        return QualitativePerceptionFilter
    raise AttributeError(name)
