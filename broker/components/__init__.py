"""Broker components package.

Core components for the water agent governance framework:
- Context building and providers
- Memory systems
- Observable state management
- Perception filters
- Social graph configuration
- Event management
"""

# Perception filter exports (Task-043)
from .social.perception import (
    QualitativePerceptionFilter,
    PassThroughPerceptionFilter,
    PerceptionFilterRegistry,
)

# Social graph configuration exports (Task-043)
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

# Observable state exports (Task-041)
from .analytics.observable import (
    ObservableStateManager,
    create_rate_metric,
)

# Event manager exports (Task-042)
from .events.manager import (
    EnvironmentEventManager,
)

# Domain adapter exports
from .cognitive.adapters import DomainReflectionAdapter

__all__ = [
    # Domain adapters
    "DomainReflectionAdapter",
    # Perception (Task-043)
    "QualitativePerceptionFilter",
    "HouseholdPerceptionFilter",  # deprecated alias
    "PassThroughPerceptionFilter",
    "PerceptionFilterRegistry",
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
    "create_rate_metric",
    # Event manager (Task-042)
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
