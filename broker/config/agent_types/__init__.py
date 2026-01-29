"""
Agent Types Module - SA/MA Unified Agent Type Configuration.

This module provides the infrastructure for managing different agent types
in both Single-Agent (SA) and Multi-Agent (MA) scenarios.

Key Components:
- AgentTypeDefinition: Complete agent type specification
- AgentTypeRegistry: Central registry for type management
- PsychologicalFramework: PMT, Utility, Financial frameworks
- Default constructs for common frameworks

Usage:
    from broker.config.agent_types import (
        AgentTypeRegistry,
        AgentTypeDefinition,
        PsychologicalFramework,
        get_default_registry,
    )

    # Load from YAML
    registry = AgentTypeRegistry()
    registry.load_from_yaml(Path("agent_types.yaml"))

    # Query agent type
    defn = registry.get("household_owner")
    skills = registry.get_eligible_skills("household_renter")

Part of Task-040: SA/MA Unified Architecture (Part 14)
"""
from broker.config.agent_types.base import (
    AgentTypeDefinition,
    AgentCategory,
    PsychologicalFramework,
    ConstructDefinition,
    ResponseFormatSpec,
    ResponseFieldDefinition,
    ValidationConfig,
    ValidationRuleRef,
    MemoryConfigSpec,
    DEFAULT_PMT_CONSTRUCTS,
    DEFAULT_UTILITY_CONSTRUCTS,
)
from broker.config.agent_types.registry import (
    AgentTypeRegistry,
    create_default_registry,
    get_default_registry,
    reset_default_registry,
)

__all__ = [
    # Core types
    "AgentTypeDefinition",
    "AgentCategory",
    "PsychologicalFramework",
    "ConstructDefinition",
    # Response format
    "ResponseFormatSpec",
    "ResponseFieldDefinition",
    # Validation
    "ValidationConfig",
    "ValidationRuleRef",
    # Memory
    "MemoryConfigSpec",
    # Registry
    "AgentTypeRegistry",
    "create_default_registry",
    "get_default_registry",
    "reset_default_registry",
    # Default constructs
    "DEFAULT_PMT_CONSTRUCTS",
    "DEFAULT_UTILITY_CONSTRUCTS",
]
