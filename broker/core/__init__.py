"""Public API for broker.core.

Re-exports the symbols currently consumed via deep imports across the
repository so callers have a shorter canonical import path. Existing deep
imports remain supported.

Phase 6Q-F-1 (2026-05-26): the eager ``from .psychometric import
(PMTFramework, UtilityFramework, FinancialFramework, ...)`` line
defeated the PEP 562 lazy ``__getattr__`` already present in
``broker/core/psychometric.py`` — plain ``import broker.core`` was
pulling 7 ``broker.domains.water.*`` modules into sys.modules
regardless of the active domain. Fixed by splitting the eager-safe
re-exports (``ConstructDef`` / ``PsychologicalFramework`` /
``ValidationResult`` / registry helpers) from the water-namespace
moved-class lazy re-exports (handled via package-level
``__getattr__`` below). ``from broker.core import PMTFramework``
still works for legacy callers; ``import broker.core`` alone no
longer triggers water loads.
"""

from .agent_initializer import (
    AgentProfile,
    CSVLoader,
    SyntheticLoader,
    generate_initial_memories,
    initialize_agents,
)
from .efficiency import CognitiveCache
from .experiment import ExperimentBuilder, ExperimentConfig, ExperimentRunner
from .psychometric import (
    ConstructDef,
    PsychologicalFramework,
    ValidationResult,
    get_framework,
    list_frameworks,
    register_framework,
)
from .skill_broker_engine import SkillBrokerEngine
from .unified_context_builder import (
    AgentTypeContextProvider,
    SkillEligibilityProvider,
    TieredContextBuilder,
    UnifiedContextBuilder,
    create_unified_context_builder,
)


# Phase 6Q-F-1 — PEP 562 lazy access for water-namespace moved
# classes. Triggers ``broker.domains.water.*`` import only when the
# attribute is actually accessed, so a plain ``import broker.core``
# from a non-water domain remains water-module-free at runtime.
_LAZY_WATER_REEXPORTS = {
    "PMTFramework": "broker.domains.water.pmt",
    "UtilityFramework": "broker.domains.water.utility",
    "FinancialFramework": "broker.domains.water.financial",
}


def __getattr__(name):
    if name in _LAZY_WATER_REEXPORTS:
        import importlib
        mod = importlib.import_module(_LAZY_WATER_REEXPORTS[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AgentProfile",
    "AgentTypeContextProvider",
    "CSVLoader",
    "CognitiveCache",
    "ConstructDef",
    "ExperimentBuilder",
    "ExperimentConfig",
    "ExperimentRunner",
    "FinancialFramework",
    "PMTFramework",
    "PsychologicalFramework",
    "SkillBrokerEngine",
    "SkillEligibilityProvider",
    "SyntheticLoader",
    "TieredContextBuilder",
    "UnifiedContextBuilder",
    "UtilityFramework",
    "ValidationResult",
    "create_unified_context_builder",
    "generate_initial_memories",
    "get_framework",
    "initialize_agents",
    "list_frameworks",
    "register_framework",
]
