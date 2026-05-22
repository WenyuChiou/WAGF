"""Public API for broker.components.cognitive.

Re-exports the symbols currently consumed via deep imports across the
repository so callers have a shorter canonical import path. Existing deep
imports remain supported.
"""

from .reflection import (
    AgentReflectionContext,
    ReflectionEngine,
    ReflectionTrigger,
)
from .trace import CognitiveTrace

# REFLECTION_QUESTIONS removed (Phase 6H Item 4): the per-flood-agent-type
# hardcoded dict was replaced by AgentTypeConfig.get_reflection_questions()
# (YAML / DomainPack resolution) + a private domain-neutral
# _DEFAULT_REFLECTION_QUESTIONS fallback in reflection.py.
# IMPORTANCE_PROFILES removed (Phase 6H Item 9): the legacy flood-keyword
# importance fallback in compute_dynamic_importance was deleted —
# importance scoring comes from the DomainPack / DomainReflectionAdapter.

__all__ = [
    "AgentReflectionContext",
    "CognitiveTrace",
    "ReflectionEngine",
    "ReflectionTrigger",
]
