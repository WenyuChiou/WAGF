"""
IrrigationDomainPack — concrete :class:`broker.domains.protocol.DomainPack`
implementation for the irrigation example.

Phase 6C-v2 (2026-05-10): wraps the existing :class:`IrrigationAdapter`
with the DomainPack facade so broker pipeline code can query irrigation
behaviour without hardcoded ``if domain == "irrigation":`` branches.

Phase 6R-D-6a (2026-05-26): the previously-monolithic
``IrrigationDomainPack`` class body splits into six sub-pack mixins
corresponding to the Phase 6R-D-1 sub-protocols the irrigation pack
overrides (Reflection, Memory, Skill, Event, Governance, Setup —
PerceptionPack is NOT overridden so no IrrigationPerceptionMixin
exists). The composite ``IrrigationDomainPack`` inherits from the six
mixins + ``DefaultDomainPack``, preserving the
``DomainPackRegistry.register("irrigation", IrrigationDomainPack())``
contract.

The irrigation-specific ``appraisal_grounding_map`` method (consumed
by ``broker/domains/water/tools/appraisal_grounding_audit.py``) is
NOT a Protocol method — it lives on the composite class directly,
not in any mixin.

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
from pathlib import Path

from typing import Any, Dict, List, Optional, Set

from broker.domains.default import DefaultDomainPack
from broker.interfaces.action_taxonomy import (
    ActionTaxonomyEntry,
    load_action_taxonomy_from_skill_registry,
)
from broker.domains.protocol import BuiltinCheck, EventHandler

from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter


# ─────────────────────────────────────────────────────────────────────
# Sub-pack mixins (Phase 6R-D-6a, 2026-05-26)
# ─────────────────────────────────────────────────────────────────────


class IrrigationReflectionMixin:
    """ReflectionPack methods — irrigation uses the batch reflection
    path (questions from agent_types.yaml), not the individual status
    block. All three reflection hooks return empty/None to preserve
    pre-refactor behaviour."""

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


class IrrigationMemoryMixin:
    """MemoryPack methods — delegate to the legacy IrrigationAdapter
    for importance / emotion / retrieval tuning. ``compute_importance``
    base default (0.70) differs from the Protocol default (0.5) —
    irrigation memories are higher-baseline-salience than the generic
    fallback assumes."""

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


class IrrigationSkillMixin:
    """SkillPack methods — empty skill metadata, no extreme actions,
    taxonomy from YAML."""

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

    def action_taxonomy(self) -> Dict[str, ActionTaxonomyEntry]:
        """Phase 6O-B — read taxonomy from irrigation skill_registry.yaml."""
        yaml_path = (
            Path(__file__).resolve().parent.parent
            / "config"
            / "skill_registry.yaml"
        )
        return load_action_taxonomy_from_skill_registry(yaml_path)


class IrrigationEventMixin:
    """EventPack methods — irrigation does NOT use the multi-agent
    event manager (env-side computations live in
    ``examples/irrigation_abm/irrigation_env.py``); the override
    returns empty handlers."""

    def event_handlers(self) -> Dict[str, EventHandler]:
        # Irrigation does not currently use the multi-agent event
        # manager (env-side computations happen in irrigation_env.py).
        return {}


class IrrigationGovernanceMixin:
    """GovernancePack methods — irrigation uses
    ``cognitive_appraisal`` framework (WSA/ACA constructs). Validator
    bundles already registered via ValidatorRegistry, so
    ``builtin_checks`` returns empty."""

    def psychological_framework(self) -> str:
        """Phase 6Q-D (2026-05-26): cognitive-appraisal framework (WSA
        / ACA constructs) — pre-registered by
        ``broker.domains.water.thinking_checks``. Matches the
        ``psychological_framework: cognitive_appraisal`` declaration in
        ``examples/irrigation_abm/config/agent_types.yaml`` (previously
        dead config)."""
        return "cognitive_appraisal"

    def builtin_checks(self) -> Dict[str, List[BuiltinCheck]]:
        # Irrigation checks are already registered via ValidatorRegistry
        # at examples/irrigation_abm/validators/__init__.py import time.
        # Returning {} here means broker should consult the registry
        # directly (same path as Phase 6B-1).
        return {}


class IrrigationSetupMixin:
    """SetupPack methods — no geographic narrative for MG agents, no
    initial-memory templating via the broker provider (irrigation
    seeds memories at agent-init time via irrigation_personas.py)."""

    def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
        # Irrigation does not inject geographic/community narrative
        # for marginalised-group agents.
        return ""

    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]:
        # Irrigation seeds memories via irrigation_personas.py at
        # agent-init time, not via the broker memory template provider.
        return []


# ─────────────────────────────────────────────────────────────────────
# Composite — IrrigationDomainPack
# ─────────────────────────────────────────────────────────────────────


class IrrigationDomainPack(
    IrrigationReflectionMixin,
    IrrigationMemoryMixin,
    IrrigationSkillMixin,
    IrrigationEventMixin,
    IrrigationGovernanceMixin,
    IrrigationSetupMixin,
    DefaultDomainPack,
):
    """DomainPack for the irrigation water-resource example.

    Phase 6R-D-6a (2026-05-26): composite of 6 sub-pack mixins (no
    Perception mixin — irrigation doesn't override perception). Public
    surface unchanged: callers still
    ``DomainPackRegistry.register("irrigation", IrrigationDomainPack())``
    and the broker's `pack.reflection_status_text(...)` etc. resolve
    via Python MRO.
    """

    name: str = "irrigation"

    def __init__(self) -> None:
        self._inner = IrrigationAdapter()

    # ─── Irrigation-specific (not a DomainPack Protocol method) ──────
    # Consumed by ``broker/domains/water/tools/appraisal_grounding_audit.py``.
    # Lives on the composite directly because it doesn't fit any
    # Phase 6R-D-1 sub-protocol; it's a custom irrigation API.

    def appraisal_grounding_map(self) -> Dict[str, Any]:
        return {
            "construct": "WSA_LABEL",
            "shortage_tier_to_wsa": {0: "L", 1: "M", 2: "H", 3: "VH"},
            "drought_index_bump_threshold": 0.6,
        }
