"""
GovernedAI SDK - Universal Cognitive Governance Middleware

Provides "Cognitive Governance" (Identity & Thinking Rules) to ANY agent framework
(LangChain, CrewAI, AutoGen, etc.)

Task-037: SDK-Broker Architecture Separation
- Added agents module (BaseAgent, AgentConfig, AgentProtocol)
- Added config module (DomainConfigLoader)
- Added simulation module (EnvironmentProtocol)

Usage:
    # Agents
    from cognitive_governance.agents import BaseAgent, AgentConfig, AgentProtocol

    # Config
    from cognitive_governance.config import DomainConfigLoader, load_domain

    # Simulation
    from cognitive_governance.simulation import EnvironmentProtocol
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

# Domain Configuration
from .config import (
    DomainConfigLoader,
    load_domain,
    SkillDefinition,
    ValidatorConfig,
)

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
