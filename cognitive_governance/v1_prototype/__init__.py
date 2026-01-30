"""
GovernedAI SDK v1 Prototype

Universal Cognitive Governance Middleware for Agent Frameworks.

Quick Start:
    >>> from cognitive_governance.v1_prototype import PolicyRule, GovernanceTrace
    >>> from cognitive_governance.v1_prototype.core.engine import PolicyEngine
    >>>
    >>> engine = PolicyEngine()
    >>> trace = engine.verify(action={}, state={"savings": 300}, policy={"rules": [...]})
    >>> if not trace.valid:
    ...     print(trace.explain())

Components:
    - types: Core dataclasses (PolicyRule, GovernanceTrace, CounterFactualResult, EntropyFriction)
    - core.engine: Stateless policy verification
    - core.wrapper: Universal agent wrapper
    - core.calibrator: Entropy-based governance calibration
    - memory.symbolic: O(1) state signature lookup
    - xai.counterfactual: Explainable AI through counterfactual analysis
"""

# Core types (Phase 0 + Phase 1 v2 + Phase 3)
from .types import (
    PolicyRule,
    GovernanceTrace,
    CounterFactualResult,
    EntropyFriction,
    RuleOperator,
    RuleLevel,
    CounterFactualStrategy,
    # v2 additions (Phase 1)
    ParamType,
    Domain,
    SensorConfig,
    ResearchTrace,
    # v2 additions (Phase 3)
    CompositeRule,
    TemporalRule,
)

# Operator Registry (Phase 3)
from .core.operators import OperatorRegistry, RuleEvaluator

# Memory layer (Phase 3)
from .memory.symbolic import SymbolicMemory

# XAI engine (Phase 4A)
from .xai.counterfactual import CounterfactualEngine

# Entropy calibrator (Phase 4B)
from .core.calibrator import EntropyCalibrator

# Social observation (Phase 6)
from .social import (
    SocialObserver,
    ObservationResult,
    ObserverRegistry,
    FloodObserver,
    FinanceObserver,
    EducationObserver,
    HealthObserver,
)

# Environment observation (Phase 6b)
from .observation import (
    EnvironmentObserver,
    EnvironmentObservation,
    EnvironmentObserverRegistry,
    FloodEnvironmentObserver,
    FinanceEnvironmentObserver,
    EducationEnvironmentObserver,
    HealthEnvironmentObserver,
)


__all__ = [
    # Types (Phase 0)
    "PolicyRule",
    "GovernanceTrace",
    "CounterFactualResult",
    "EntropyFriction",
    "RuleOperator",
    "RuleLevel",
    "CounterFactualStrategy",
    # Types (Phase 1 v2)
    "ParamType",
    "Domain",
    "SensorConfig",
    "ResearchTrace",
    # Types (Phase 3)
    "CompositeRule",
    "TemporalRule",
    # Operators (Phase 3)
    "OperatorRegistry",
    "RuleEvaluator",
    # Memory
    "SymbolicMemory",
    # XAI
    "CounterfactualEngine",
    # Calibrator
    "EntropyCalibrator",
    # Social (Phase 6)
    "SocialObserver",
    "ObservationResult",
    "ObserverRegistry",
    "FloodObserver",
    "FinanceObserver",
    "EducationObserver",
    "HealthObserver",
    # Environment Observation (Phase 6b)
    "EnvironmentObserver",
    "EnvironmentObservation",
    "EnvironmentObserverRegistry",
    "FloodEnvironmentObserver",
    "FinanceEnvironmentObserver",
    "EducationEnvironmentObserver",
    "HealthEnvironmentObserver",
]

__version__ = "0.1.0"
