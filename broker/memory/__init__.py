"""Memory support package: pluggable surprise strategies + cognitive
capacity config consumed by the production memory engines.

Org-3 note (2026-09): the unified/FAISS memory stack that used to live
here (``unified_engine.py`` / ``UnifiedCognitiveEngine``, ``store.py``,
``retrieval.py``, ``graph.py``, ``persistence.py``, ``vector_db.py``,
``embeddings.py``) was deleted as dead code — it had no production
importer (only its own tests + the lazy ``engine_type="unified"``
registration in ``broker.components.memory.registry``, also removed).
What remains here IS live: ``broker.components.memory.engines.humancentric``
and ``broker.components.memory.universal`` import
``broker.memory.strategies.*`` directly, and ``broker.domains.water.*``
imports ``broker.memory.config.*``.

Key components:
- SurpriseStrategy: Pluggable surprise calculation (EMA, Symbolic, Hybrid)
- GlobalMemoryConfig / DomainMemoryConfig: memory configuration
- CognitiveConstraints: Miller/Cowan-based capacity limits

Usage:
    from broker.memory import (
        EMASurpriseStrategy,
        SymbolicSurpriseStrategy,
    )

Reference: Task-040 Memory Module Optimization, Task-050 Memory Optimization
"""

from .strategies import (
    SurpriseStrategy,
    EMASurpriseStrategy,
    SymbolicSurpriseStrategy,
    HybridSurpriseStrategy,
    # Task-050C: Multi-dimensional surprise
    MultiDimensionalSurpriseStrategy,
)
# Phase 6Q-D-2 (2026-05-26): `create_flood_surprise_strategy` factory
# relocated to broker.domains.water.memory_strategies — was Layer 3
# audit finding #20 (flood-specific factory in generic broker).
from .config import (
    GlobalMemoryConfig,
    DomainMemoryConfig,
    # Cognitive Constraints (Task-050E)
    CognitiveConstraints,
    MILLER_STANDARD,
    COWAN_CONSERVATIVE,
    EXTENDED_CONTEXT,
    MINIMAL,
)

__all__ = [
    # Strategies
    "SurpriseStrategy",
    "EMASurpriseStrategy",
    "SymbolicSurpriseStrategy",
    "HybridSurpriseStrategy",
    # Multi-dimensional (Task-050C)
    "MultiDimensionalSurpriseStrategy",
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


def __getattr__(name):
    if name == "FloodDomainConfig":
        from .config import FloodDomainConfig

        return FloodDomainConfig
    raise AttributeError(name)
