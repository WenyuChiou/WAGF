"""
GovernedAI SDK v1 Prototype

Universal Cognitive Governance Middleware for Agent Frameworks.

Quick Start:
    >>> from governed_ai_sdk.v1_prototype import PolicyRule, GovernanceTrace
    >>> from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
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

# Core types (Phase 0 + Phase 1 v2)
from .types import (
    PolicyRule,
    GovernanceTrace,
    CounterFactualResult,
    EntropyFriction,
    RuleOperator,
    RuleLevel,
    CounterFactualStrategy,
    # v2 additions
    ParamType,
    Domain,
    SensorConfig,
    ResearchTrace,
)

# Memory layer (Phase 3)
from .memory.symbolic import SymbolicMemory

# XAI engine (Phase 4A)
from .xai.counterfactual import CounterfactualEngine

# Entropy calibrator (Phase 4B)
from .core.calibrator import EntropyCalibrator


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
    # Memory
    "SymbolicMemory",
    # XAI
    "CounterfactualEngine",
    # Calibrator
    "EntropyCalibrator",
]

__version__ = "0.1.0"
