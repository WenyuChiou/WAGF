"""
Memory layer components.

- symbolic.py: v4 Symbolic Context integration (Phase 3 - Claude Code)
- scoring.py: Domain-aware memory scoring (Task-034 Phase 9)
- persistence.py: Memory persistence backends (Task-034 Phase 9)
"""

from .symbolic import (
    Sensor,
    SignatureEngine,
    SymbolicContextMonitor,
    SymbolicMemory,
)

from .scoring import (
    MemoryScore,
    MemoryScorer,
    GenericMemoryScorer,
    FloodMemoryScorer,
    FinanceMemoryScorer,
    EducationMemoryScorer,
    HealthMemoryScorer,
    get_memory_scorer,
    register_memory_scorer,
    MEMORY_SCORERS,
)

from .persistence import (
    MemoryPersistence,
    JSONMemoryPersistence,
    SQLiteMemoryPersistence,
    InMemoryPersistence,
    create_persistence,
)

__all__ = [
    # Symbolic memory (v4)
    "Sensor",
    "SignatureEngine",
    "SymbolicContextMonitor",
    "SymbolicMemory",
    # Memory scoring (Task-034)
    "MemoryScore",
    "MemoryScorer",
    "GenericMemoryScorer",
    "FloodMemoryScorer",
    "FinanceMemoryScorer",
    "EducationMemoryScorer",
    "HealthMemoryScorer",
    "get_memory_scorer",
    "register_memory_scorer",
    "MEMORY_SCORERS",
    # Memory persistence (Task-034)
    "MemoryPersistence",
    "JSONMemoryPersistence",
    "SQLiteMemoryPersistence",
    "InMemoryPersistence",
    "create_persistence",
]
