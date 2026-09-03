"""
Governed AI SDK - Agents Module.

Provides agent protocols and base implementations for the water agent governance framework.

Usage:
    # Load from user-defined YAML
    from broker.agents import load_agents
    agents = load_agents("my_agents.yaml")

    # Or create programmatically
    from broker.agents import BaseAgent, AgentConfig
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

from .deciders import (
    DEFAULT_DECIDER_NAME,
    DEFAULT_DECIDER_SPEC,
    DeciderRegistry,
    DeciderSpec,
    DecisionContext,
    DecisionRule,
    parse_decider_spec,
    register_domain_deciders,
    take_decider_path,
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
    # Deciders (PR-8): who decides an agent's action, per agent type
    "DEFAULT_DECIDER_NAME",
    "DEFAULT_DECIDER_SPEC",
    "DeciderRegistry",
    "DeciderSpec",
    "DecisionContext",
    "DecisionRule",
    "parse_decider_spec",
    "register_domain_deciders",
    "take_decider_path",
]
