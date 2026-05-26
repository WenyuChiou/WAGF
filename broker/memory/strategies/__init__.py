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
from .multidimensional import MultiDimensionalSurpriseStrategy
from .decision_consistency import DecisionConsistencySurprise

# Phase 6Q-D-2 (2026-05-26): the ``create_flood_surprise_strategy``
# factory previously re-exported from here has relocated to
# ``broker.domains.water.memory_strategies``. Its body hardcoded
# flood-domain variable names; it never belonged in a generic
# memory-strategies package. Callers should now use:
#     from broker.domains.water.memory_strategies import (
#         create_flood_surprise_strategy,
#     )

__all__ = [
    "SurpriseStrategy",
    "EMASurpriseStrategy",
    "SymbolicSurpriseStrategy",
    "HybridSurpriseStrategy",
    # Task-050C: Multi-dimensional surprise
    "MultiDimensionalSurpriseStrategy",
    # P2 Innovation: Domain-agnostic action-history surprise
    "DecisionConsistencySurprise",
]
