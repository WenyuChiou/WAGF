"""
Unified Memory Module (v5) - Consolidated Cognitive Memory Architecture.

This module provides a unified, pluggable memory system that consolidates
the best features from v2 (HumanCentric), v3 (Universal/EMA), and v4 (Symbolic).

Key components:
- UnifiedMemoryItem: Standardized memory data structure
- SurpriseStrategy: Pluggable surprise calculation (EMA, Symbolic, Hybrid)
- UnifiedMemoryStore: Working/Long-term memory with consolidation
- AdaptiveRetrievalEngine: Dynamic retrieval weight adjustment

Usage:
    from governed_ai_sdk.memory import (
        UnifiedCognitiveEngine,
        UnifiedMemoryItem,
        EMASurpriseStrategy,
        SymbolicSurpriseStrategy,
    )

Reference: Task-040 Memory Module Optimization
"""

from .unified_engine import (
    UnifiedCognitiveEngine,
    UnifiedMemoryItem,
)
from .strategies import (
    SurpriseStrategy,
    EMASurpriseStrategy,
    SymbolicSurpriseStrategy,
    HybridSurpriseStrategy,
)
from .store import UnifiedMemoryStore
from .retrieval import AdaptiveRetrievalEngine

__all__ = [
    # Main engine
    "UnifiedCognitiveEngine",
    "UnifiedMemoryItem",
    # Strategies
    "SurpriseStrategy",
    "EMASurpriseStrategy",
    "SymbolicSurpriseStrategy",
    "HybridSurpriseStrategy",
    # Store & Retrieval
    "UnifiedMemoryStore",
    "AdaptiveRetrievalEngine",
]
