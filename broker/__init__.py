"""
Governed Broker Framework - Core Package

Governance middleware for LLM-driven Agent-Based Models.
Version 0.2.0 - Skill-Governed Architecture

IMPORTANT: This framework has two versions:
  - v1 (Legacy MCP): broker.legacy.BrokerEngine - DEPRECATED
  - v2 (Skill-Governed): broker.SkillBrokerEngine - RECOMMENDED
"""
# =============================================================================
# V2 Skill-Governed Architecture (RECOMMENDED)
# =============================================================================
from .skill_types import (
    SkillProposal, SkillDefinition, ApprovedSkill,
    SkillBrokerResult, SkillOutcome, ExecutionResult
)
from .skill_registry import SkillRegistry, create_flood_adaptation_registry
from .skill_broker_engine import SkillBrokerEngine
from .model_adapter import ModelAdapter, OllamaAdapter, OpenAIAdapter, get_adapter

# =============================================================================
# V1 Legacy MCP Architecture (DEPRECATED - use broker.legacy for explicit access)
# =============================================================================
# For backwards compatibility, we still expose these at package level
# but they are deprecated and will be removed in v0.3.0
from .legacy.engine import BrokerEngine
from .legacy.types import BrokerResult, DecisionRequest, ValidationResult

__all__ = [
    # V2 Skill-Governed (Recommended)
    "SkillProposal", "SkillDefinition", "ApprovedSkill", "SkillBrokerResult", "SkillOutcome",
    "SkillRegistry", "create_flood_adaptation_registry",
    "SkillBrokerEngine",
    "ModelAdapter", "OllamaAdapter", "OpenAIAdapter", "get_adapter",
    "ExecutionResult",
    # V1 Legacy (Deprecated)
    "BrokerEngine", "BrokerResult", "DecisionRequest", "ValidationResult",
]
__version__ = "0.2.0"

