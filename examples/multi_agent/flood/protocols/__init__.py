"""
Multi-Agent Governance Protocols (Task-058)

Domain-specific implementations for the flood ABM multi-agent coordination:

- artifacts: Structured message types (PolicyArtifact, MarketArtifact, HouseholdIntention)
- cross_validators: Domain validation rules for CrossAgentValidator
- saga_definitions: Multi-step transaction workflows with compensation
- role_config: Role-based permission definitions for RoleEnforcer
"""

from .artifacts import PolicyArtifact, MarketArtifact, HouseholdIntention
from .cross_validators import FLOOD_VALIDATION_RULES
from .saga_definitions import FLOOD_SAGA_DEFINITIONS
from .role_config import FLOOD_ROLES

__all__ = [
    "PolicyArtifact",
    "MarketArtifact",
    "HouseholdIntention",
    "FLOOD_VALIDATION_RULES",
    "FLOOD_SAGA_DEFINITIONS",
    "FLOOD_ROLES",
]
