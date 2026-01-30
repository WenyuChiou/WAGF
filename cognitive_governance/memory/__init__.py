"""
Unified Memory Module (v5) - Consolidated Cognitive Memory Architecture.

This module provides a unified, pluggable memory system that consolidates
the best features from v2 (HumanCentric), v3 (Universal/EMA), and v4 (Symbolic).

Key components:
- UnifiedMemoryItem: Standardized memory data structure
- SurpriseStrategy: Pluggable surprise calculation (EMA, Symbolic, Hybrid)
- UnifiedMemoryStore: Working/Long-term memory with consolidation
- AdaptiveRetrievalEngine: Dynamic retrieval weight adjustment
- VectorMemoryIndex: FAISS-based O(log n) semantic retrieval (Task-050A)
- MemoryGraph: NetworkX-based graph memory structure (Task-050D)

Usage:
    from cognitive_governance.memory import (
        UnifiedCognitiveEngine,
        UnifiedMemoryItem,
        EMASurpriseStrategy,
        SymbolicSurpriseStrategy,
        VectorMemoryIndex,  # O(log n) retrieval
        MemoryGraph,        # Graph-based memory structure
    )

Reference: Task-040 Memory Module Optimization, Task-050 Memory Optimization
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
    # Task-050C: Multi-dimensional surprise
    MultiDimensionalSurpriseStrategy,
    create_flood_surprise_strategy,
)
from .store import UnifiedMemoryStore
from .retrieval import AdaptiveRetrievalEngine
from .config import (
    GlobalMemoryConfig,
    DomainMemoryConfig,
    FloodDomainConfig,
    # Cognitive Constraints (Task-050E)
    CognitiveConstraints,
    MILLER_STANDARD,
    COWAN_CONSERVATIVE,
    EXTENDED_CONTEXT,
    MINIMAL,
)

# Task-050A: Vector DB Integration
try:
    from .vector_db import VectorMemoryIndex, AgentVectorIndex
    VECTOR_DB_AVAILABLE = True
except ImportError:
    VectorMemoryIndex = None  # type: ignore
    AgentVectorIndex = None  # type: ignore
    VECTOR_DB_AVAILABLE = False

# Task-050B: Memory Persistence
from .persistence import (
    MemoryCheckpoint,
    MemorySerializer,
    save_checkpoint,
    load_checkpoint,
)

# Task-050D: Memory Graph
try:
    from .graph import MemoryGraph, AgentMemoryGraph
    MEMORY_GRAPH_AVAILABLE = True
except ImportError:
    MemoryGraph = None  # type: ignore
    AgentMemoryGraph = None  # type: ignore
    MEMORY_GRAPH_AVAILABLE = False

__all__ = [
    # Main engine
    "UnifiedCognitiveEngine",
    "UnifiedMemoryItem",
    # Strategies
    "SurpriseStrategy",
    "EMASurpriseStrategy",
    "SymbolicSurpriseStrategy",
    "HybridSurpriseStrategy",
    # Multi-dimensional (Task-050C)
    "MultiDimensionalSurpriseStrategy",
    "create_flood_surprise_strategy",
    # Store & Retrieval
    "UnifiedMemoryStore",
    "AdaptiveRetrievalEngine",
    # Vector DB (Task-050A)
    "VectorMemoryIndex",
    "AgentVectorIndex",
    "VECTOR_DB_AVAILABLE",
    # Persistence (Task-050B)
    "MemoryCheckpoint",
    "MemorySerializer",
    "save_checkpoint",
    "load_checkpoint",
    # Memory Graph (Task-050D)
    "MemoryGraph",
    "AgentMemoryGraph",
    "MEMORY_GRAPH_AVAILABLE",
    # Config
    "GlobalMemoryConfig",
    "DomainMemoryConfig",
    "FloodDomainConfig",
    # Cognitive Constraints (Task-050E)
    "CognitiveConstraints",
    "MILLER_STANDARD",
    "COWAN_CONSERVATIVE",
    "EXTENDED_CONTEXT",
    "MINIMAL",
]
