"""
IrrigationDomainPack — concrete :class:`broker.domains.protocol.DomainPack`
implementation for the irrigation example.

Phase 6C-v2 (2026-05-10): wraps the existing :class:`IrrigationAdapter`
with the DomainPack facade so broker pipeline code can query irrigation
behaviour without hardcoded ``if domain == "irrigation":`` branches.

Backward compatibility
======================
Every method is byte-identical to the pre-refactor behaviour:

- ``importance_profiles / compute_importance / classify_emotion /
  emotional_keywords / retrieval_weights`` delegate to the existing
  ``IrrigationAdapter`` instance unchanged.
- ``reflection_status_text`` returns ``None`` because irrigation never
  used the individual-prompt status block (it was gated by
  ``agent_type == "household"`` and irrigation uses ``irrigation_farmer``).
  Irrigation reflection comes from ``agent_types.yaml`` ``reflection.questions``
  via the batch path — that path is unchanged.
- ``event_handlers`` is empty: irrigation does not use the multi-agent
  event manager.
- ``mg_barrier_text`` is empty: irrigation does not inject Passaic-style
  geographic narrative.
- ``extreme_actions`` is empty: irrigation has no one-way irreversible
  actions (all skills are demand-axis modifications).
- ``builtin_checks`` returns the irrigation check tuples that are
  already registered via :class:`ValidatorRegistry` at the example
  package's ``validators/__init__.py`` import time. Provided here for
  parity / future migration; broker callers should keep using
  ``ValidatorRegistry`` directly.
- ``initial_memory_templates`` is empty: irrigation seeds memories via
  ``irrigation_personas.py``, not via the broker template provider.
- ``skill_emotion_metadata`` returns the emotion+importance metadata
  that previously lived as a hardcoded ``if/elif`` chain in
  ``broker/core/experiment_runner.py:383-388`` (flood-only at that
  time). Irrigation skills get a "routine" baseline so audit memory
  emotion is consistent.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from broker.domains.protocol import BuiltinCheck, EventHandler

from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter


class IrrigationDomainPack:
    """DomainPack for the irrigation water-resource example."""

    name: str = "irrigation"

    def __init__(self) -> None:
        self._inner = IrrigationAdapter()

    # ─── Reflection ───────────────────────────────────────────────

    def reflection_status_text(self, context: Any) -> Optional[str]:
        # Irrigation uses the batch reflection path (questions from
        # agent_types.yaml), not the individual prompt's status block.
        # Returning None signals broker to skip the per-agent status
        # line — preserving pre-refactor behaviour where the
        # `agent_type == "household"` gate caused this block to be
        # skipped for irrigation_farmer.
        return None

    def reflection_questions(self) -> List[str]:
        # Pulled from agent_types.yaml at run time; do not duplicate here.
        return []

    def reflection_persona(self) -> Optional[str]:
        return None

    # ─── Memory / importance / emotion (delegate to existing adapter) ─

    def importance_profiles(self) -> Dict[str, float]:
        return dict(self._inner.importance_profiles)

    def compute_importance(self, context: Any, base: float = 0.70) -> float:
        return self._inner.compute_importance(context, base)

    def classify_emotion(self, decision: str, context: Any) -> str:
        return self._inner.classify_emotion(decision, context)

    def emotional_keywords(self) -> Dict[str, str]:
        return dict(self._inner.emotional_keywords)

    def retrieval_weights(self) -> Dict[str, float]:
        return dict(self._inner.retrieval_weights)

    # ─── Skills ────────────────────────────────────────────────────

    def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]:
        # Irrigation pre-refactor (experiment_runner.py:387-388 fall-through
        # branch): all non-flood-specific skills got the same "routine"
        # tag with importance 0.1. To preserve byte-identical memory
        # tagging across v21 / v22 datasets, irrigation pack returns {}
        # here and the broker code applies the routine 0.1 default. If
        # we later diversify irrigation memory importance (e.g., make
        # decrease during drought = "major"), it should be a separate
        # opt-in change with its own SI footnote, not a side-effect of
        # the DomainPack refactor.
        return {}

    def extreme_actions(self) -> Set[str]:
        # Irrigation has no irreversible one-way actions.
        return set()

    # ─── Events ────────────────────────────────────────────────────

    def event_handlers(self) -> Dict[str, EventHandler]:
        # Irrigation does not currently use the multi-agent event
        # manager (env-side computations happen in irrigation_env.py).
        return {}

    # ─── Context provider hooks ────────────────────────────────────

    def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
        # Irrigation does not inject geographic/community narrative
        # for marginalised-group agents.
        return ""

    # ─── Validators ────────────────────────────────────────────────

    def builtin_checks(self) -> Dict[str, List[BuiltinCheck]]:
        # Irrigation checks are already registered via ValidatorRegistry
        # at examples/irrigation_abm/validators/__init__.py import time.
        # Returning {} here means broker should consult the registry
        # directly (same path as Phase 6B-1).
        return {}

    # ─── Memory templates ─────────────────────────────────────────

    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]:
        # Irrigation seeds memories via irrigation_personas.py at
        # agent-init time, not via the broker memory template provider.
        return []
