"""Memory sub-package — operational memory integration.

Modules:
    engine   — MemoryEngine ABC
    bridge   — MemoryBridge
    factory  — create_memory_engine
    registry — MemoryEngineRegistry
    seeding  — seed_memory_from_agents
    universal — UniversalMemorySystem
    legacy   — CognitiveMemory (deprecated v2)
    engines/ — WindowMemoryEngine, ImportanceMemoryEngine, etc.
"""

# Backward compat: legacy CognitiveMemory (no cross-cluster deps, safe to import)
from .legacy import CognitiveMemory, MemoryProvider  # noqa: F401
