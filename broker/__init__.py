"""Governed Broker Framework — cognitive governance framework for LLM-driven
agent-based models.

Provides skill-based governance, memory engines, and reflection capabilities
for coupled human-environment simulations.  Domain-specific content (flood,
irrigation, education, finance, …) is supplied by pluggable domain packs
under ``broker.domains``.
"""

# 1. Base Interfaces (No dependencies)
from .interfaces.skill_types import (
    SkillProposal, SkillDefinition, ApprovedSkill,
    ExecutionResult, SkillBrokerResult, SkillOutcome, ValidationResult
)
from .interfaces.environment_protocols import (
    EnvironmentProtocol, TieredEnvironmentProtocol, SocialEnvironmentProtocol
)
from .interfaces.event_generator import EventGeneratorProtocol
from .interfaces.simulation_protocols import SimulationEngineProtocol, SkillExecutorProtocol
from .interfaces.lifecycle_protocols import PreYearHook, PostStepHook, PostYearHook

# 2. Utils (Dependent on interfaces)
from .utils.model_adapter import ModelAdapter, UnifiedAdapter, deepseek_preprocessor
from .utils.agent_config import load_agent_config, ValidationRule, CoherenceRule, AgentTypeConfig
from .utils.data_loader import load_agents_from_csv
from .utils.performance_tuner import get_optimal_config, apply_to_llm_config

# 3. Components (Dependent on interfaces/utils)
from .components.memory.engine import MemoryEngine, WindowMemoryEngine, ImportanceMemoryEngine, HumanCentricMemoryEngine
from .components.memory.registry import MemoryEngineRegistry
from .components.governance.registry import SkillRegistry
from .components.context.builder import (
    ContextBuilder, BaseAgentContextBuilder, TieredContextBuilder,
    create_context_builder, load_prompt_templates
)
from .components.analytics.interaction import InteractionHub
from .components.social.graph import NeighborhoodGraph, SocialGraph, create_social_graph
from .components.analytics.audit import GenericAuditWriter, AuditConfig, GenericAuditWriter as AuditWriter, AuditConfig as GenericAuditConfig

# 3b. Validators (part of broker namespace now)
from .validators import AgentValidator

# 4. Core (Dependent on everything above)
from .core.skill_broker_engine import SkillBrokerEngine
from .core.experiment import ExperimentBuilder, ExperimentRunner
from broker.agents import BaseAgent, AgentConfig

# 5. Domain packs (auto-register frameworks, thinking checks, etc.)
import broker.domains  # noqa: F401, E402

# Aliases
GovernedBroker = SkillBrokerEngine
