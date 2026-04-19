"""Public API for broker.components.cognitive.

Re-exports the symbols currently consumed via deep imports across the
repository so callers have a shorter canonical import path. Existing deep
imports remain supported.
"""

from .reflection import (
    AgentReflectionContext,
    IMPORTANCE_PROFILES,
    REFLECTION_QUESTIONS,
    ReflectionEngine,
    ReflectionTrigger,
)
from .trace import CognitiveTrace

__all__ = [
    "AgentReflectionContext",
    "CognitiveTrace",
    "IMPORTANCE_PROFILES",
    "REFLECTION_QUESTIONS",
    "ReflectionEngine",
    "ReflectionTrigger",
]
