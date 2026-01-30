"""
Governed AI SDK - Agents Module.

Provides agent protocols and base implementations for the governed broker framework.

Usage:
    # Load from user-defined YAML
    from cognitive_governance.agents import load_agents
    agents = load_agents("my_agents.yaml")

    # Or create programmatically
    from cognitive_governance.agents import BaseAgent, AgentConfig
"""
from .protocols import (
    AgentProtocol,
    StatefulAgentProtocol,
    MemoryCapableAgentProtocol,
)

from .base import (
    # Normalization utilities
    normalize,
    denormalize,
    # Configuration classes
    StateParam,
    Objective,
    Constraint,
    PerceptionSource,
    Skill,
    AgentConfig,
    # Agent base class
    BaseAgent,
)

from .loader import (
    load_agent_configs,
    load_agents,
)


__all__ = [
    # Protocols
    "AgentProtocol",
    "StatefulAgentProtocol",
    "MemoryCapableAgentProtocol",
    # Utils
    "normalize",
    "denormalize",
    # Config
    "StateParam",
    "Objective",
    "Constraint",
    "PerceptionSource",
    "Skill",
    "AgentConfig",
    # Agent
    "BaseAgent",
    # Loader
    "load_agent_configs",
    "load_agents",
]
