"""
WAGF - Agents Module.

Provides agent protocols and base implementations for the Water Agent Governance Framework.

Usage:
    from broker.agents import BaseAgent, AgentConfig
"""
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


__all__ = [
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
]
