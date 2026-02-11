"""
Surprise Calculation Strategies.

Provides pluggable strategies for computing surprise/arousal:
- EMASurpriseStrategy: EMA predictor-based (from v3)
- SymbolicSurpriseStrategy: Frequency-based novelty (from v4)
- HybridSurpriseStrategy: Combination of EMA + Symbolic
- MultiDimensionalSurpriseStrategy: Multi-variable tracking (Task-050C)
- DecisionConsistencySurprise: Action-history surprise (P2 innovation)
"""

from .base import SurpriseStrategy
from .ema import EMASurpriseStrategy
from .symbolic import SymbolicSurpriseStrategy
from .hybrid import HybridSurpriseStrategy
from .multidimensional import (
    MultiDimensionalSurpriseStrategy,
    create_flood_surprise_strategy,
)
from .decision_consistency import DecisionConsistencySurprise

__all__ = [
    "SurpriseStrategy",
    "EMASurpriseStrategy",
    "SymbolicSurpriseStrategy",
    "HybridSurpriseStrategy",
    # Task-050C: Multi-dimensional surprise
    "MultiDimensionalSurpriseStrategy",
    "create_flood_surprise_strategy",
    # P2 Innovation: Domain-agnostic action-history surprise
    "DecisionConsistencySurprise",
]
