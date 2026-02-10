"""
Cognitive Governance SDK — cognitive governance middleware for LLM-driven
agent-based models of coupled human-water systems.

Provides agent protocols, configuration loaders, environment protocols,
and memory engines for governing LLM agent behavior in water-domain
simulations (flood risk adaptation, irrigation water management).

Domain-specific implementations (environments, validators, learning
algorithms) reside in their respective example directories:
  - examples/irrigation_abm/  — Irrigation water management (CRSS)
  - examples/multi_agent/flood/ — Multi-agent flood adaptation
  - examples/single_agent/     — Single-agent flood adaptation

Usage:
    from cognitive_governance.agents import BaseAgent, AgentConfig
    from cognitive_governance.simulation import EnvironmentProtocol
    from cognitive_governance.memory import UnifiedCognitiveEngine
"""

__version__ = "0.30.0"
__author__ = "GovernedAI Team"

# Core Agent Framework
from .agents import (
    # Protocols
    AgentProtocol,
    StatefulAgentProtocol,
    MemoryCapableAgentProtocol,
    # Classes
    BaseAgent,
    AgentConfig,
    # Utilities
    normalize,
    denormalize,
    # Loader
    load_agents,
    load_agent_configs,
)

# Domain Configuration (removed — use broker.config.schema instead)
DomainConfigLoader = None
load_domain = None
SkillDefinition = None
ValidatorConfig = None

# Simulation Protocols
from .simulation import (
    EnvironmentProtocol,
    TieredEnvironmentProtocol,
    SocialEnvironmentProtocol,
)

__all__ = [
    # Version
    "__version__",
    # Agent Protocols
    "AgentProtocol",
    "StatefulAgentProtocol",
    "MemoryCapableAgentProtocol",
    # Agent Classes
    "BaseAgent",
    "AgentConfig",
    # Agent Utilities
    "normalize",
    "denormalize",
    "load_agents",
    "load_agent_configs",
    # Config
    "DomainConfigLoader",
    "load_domain",
    "SkillDefinition",
    "ValidatorConfig",
    # Environment Protocols
    "EnvironmentProtocol",
    "TieredEnvironmentProtocol",
    "SocialEnvironmentProtocol",
]
