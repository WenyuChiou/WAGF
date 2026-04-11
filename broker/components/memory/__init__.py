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
from .content_types import MemoryContentType
from .policy_classifier import classify as classify_memory_content
from .policy_filter import PolicyFilteredMemoryEngine
from .initial_loader import (
    InitialLoadReport,
    load_initial_memories_from_json,
)

__all__ = [
    # Legacy (pre-existing)
    "CognitiveMemory",
    "MemoryProvider",
    # Broker-level memory governance (2026-04-11)
    "MemoryContentType",
    "classify_memory_content",
    "PolicyFilteredMemoryEngine",
    "InitialLoadReport",
    "load_initial_memories_from_json",
]
