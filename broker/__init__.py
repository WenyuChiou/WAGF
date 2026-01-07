"""
Governed Broker Framework - Core Package

Governance middleware for LLM-driven Agent-Based Models.
Version 0.2.1 - Consolidated Skill-Governed Architecture
"""

# =============================================================================
# Core Skill-Governed Architecture
# =============================================================================
from .skill_types import (
    SkillProposal, SkillDefinition, ApprovedSkill,
    SkillBrokerResult, SkillOutcome, ExecutionResult, ValidationResult
)
from .skill_registry import SkillRegistry, create_flood_adaptation_registry
from .skill_broker_engine import SkillBrokerEngine
from .model_adapter import ModelAdapter, OllamaAdapter, OpenAIAdapter, UnifiedAdapter, get_adapter

# =============================================================================
# Consolidated Framework (Generic Components)
# =============================================================================
from .agent_config import AgentTypeConfig, load_agent_config
from .context_builder import ContextBuilder, BaseAgentContextBuilder, create_context_builder
from .audit_writer import GenericAuditWriter, AuditConfig as GenericAuditConfig

# =============================================================================
# Memory and Retrieval Module
# =============================================================================
from .memory import (
    SimpleMemory, CognitiveMemory,
    MemoryProvider, SimpleRetrieval,
    MemoryAwareContextBuilder
)

__all__ = [
    # Core Skill-Governed
    "SkillProposal", "SkillDefinition", "ApprovedSkill", "SkillBrokerResult", "SkillOutcome",
    "SkillRegistry", "create_flood_adaptation_registry",
    "SkillBrokerEngine",
    "ModelAdapter", "OllamaAdapter", "OpenAIAdapter", "UnifiedAdapter", "get_adapter",
    "ExecutionResult", "ValidationResult",
    
    # Context Building
    "ContextBuilder", "BaseAgentContextBuilder", "create_context_builder",
    
    # Auditing
    "GenericAuditWriter", "GenericAuditConfig",
    
    # Agent Configuration
    "AgentTypeConfig", "load_agent_config",
    
    # Memory and Retrieval
    "SimpleMemory", "CognitiveMemory", "MemoryProvider", "SimpleRetrieval",
    "MemoryAwareContextBuilder",
]

__version__ = "0.2.1"
