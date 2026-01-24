"""
GovernedAI SDK v1 Prototype

This module contains the first iteration of the universal governance middleware.
"""

from .types import (
    # Enums
    RuleOperator,
    RuleLevel,
    CounterFactualStrategy,
    # Dataclasses
    PolicyRule,
    GovernanceTrace,
    CounterFactualResult,
    EntropyFriction,
    # Type aliases
    State,
    Action,
    Policy,
)

# Phase 3: Memory Layer
from .memory.symbolic import (
    Sensor,
    SymbolicMemory,
)

# Phase 4A: XAI Counterfactual
from .xai.counterfactual import (
    CounterfactualEngine,
    explain_blocked_action,
)

# Phase 4B: Entropy Calibrator
from .core.calibrator import EntropyCalibrator

__all__ = [
    # Enums
    "RuleOperator",
    "RuleLevel",
    "CounterFactualStrategy",
    # Dataclasses
    "PolicyRule",
    "GovernanceTrace",
    "CounterFactualResult",
    "EntropyFriction",
    # Type aliases
    "State",
    "Action",
    "Policy",
    # Phase 3: Memory
    "Sensor",
    "SymbolicMemory",
    # Phase 4A: XAI
    "CounterfactualEngine",
    "explain_blocked_action",
    "EntropyCalibrator",
]
