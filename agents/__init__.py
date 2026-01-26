"""
Generic Agent Framework - DEPRECATED

This module is deprecated. Please import from governed_ai_sdk.agents instead:

    # Old (deprecated)
    from agents import BaseAgent, AgentConfig

    # New
    from governed_ai_sdk.agents import BaseAgent, AgentConfig

Task-037: SDK-Broker Architecture Separation
"""
import warnings

warnings.warn(
    "The 'agents' module is deprecated. "
    "Please import from 'governed_ai_sdk.agents' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from SDK for backward compatibility
from governed_ai_sdk.agents import (
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
    # Loader
    load_agent_configs,
    load_agents,
)


__all__ = [
    # Utils
    'normalize',
    'denormalize',
    # Config
    'StateParam',
    'Objective',
    'Constraint',
    'PerceptionSource',
    'Skill',
    'AgentConfig',
    # Agent
    'BaseAgent',
    # Loader
    'load_agent_configs',
    'load_agents',
]
