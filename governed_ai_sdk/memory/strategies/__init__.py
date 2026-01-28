"""
Surprise Calculation Strategies.

Provides pluggable strategies for computing surprise/arousal:
- EMASurpriseStrategy: EMA predictor-based (from v3)
- SymbolicSurpriseStrategy: Frequency-based novelty (from v4)
- HybridSurpriseStrategy: Combination of EMA + Symbolic
"""

from .base import SurpriseStrategy
from .ema import EMASurpriseStrategy
from .symbolic import SymbolicSurpriseStrategy
from .hybrid import HybridSurpriseStrategy

__all__ = [
    "SurpriseStrategy",
    "EMASurpriseStrategy",
    "SymbolicSurpriseStrategy",
    "HybridSurpriseStrategy",
]
