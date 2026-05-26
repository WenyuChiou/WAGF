"""
FloodDomainPack — concrete :class:`broker.domains.protocol.DomainPack`
implementation for the flood-risk household example.

Phase 6C-v2 (2026-05-10): wraps the existing :class:`FloodAdapter` with
the DomainPack facade and adds the methods previously hardcoded in
broker/ hot paths:

- ``reflection_status_text`` — replaces
  ``broker/components/cognitive/reflection.py:301-313`` (C3)
- ``skill_emotion_metadata`` — replaces
  ``broker/core/experiment_runner.py:383-388`` (W2)
- ``event_handlers`` — replaces
  ``broker/components/events/ma_manager.py:275-330`` chain (W5)
- ``mg_barrier_text`` — replaces the Passaic-specific text in
  ``broker/components/context/providers.py:704-712`` (C2)
- ``extreme_actions`` — replaces the kwarg in
  ``broker/domains/water/validator_bundles.py:87`` (C5 partial)

Backward compatibility
======================
Every method produces byte-identical output to the pre-refactor
hardcoded site. Verified by ``tests/test_domain_pack_contract.py``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from broker.components.memory.content_types import MemoryContentType
from broker.domains.default import DefaultDomainPack
from broker.interfaces.action_taxonomy import (
    ActionTaxonomyEntry,
    load_action_taxonomy_from_skill_registry,
)
from broker.domains.protocol import BuiltinCheck, EventHandler, MemoryPolicyBundle

from examples.governed_flood.adapters.flood_adapter import FloodAdapter
from examples.governed_flood.adapters.flood_perception import (
    COMMUNITY_OBSERVABLE_FIELDS,
    DOLLAR_AMOUNT_FIELDS,
    NEIGHBOR_ACTION_FIELDS,
    PERCENTAGE_FIELDS,
    PERCEPTION_DESCRIPTORS,
)


# ─────────────────────────────────────────────────────────────────────
# Event handlers — extracted verbatim from
# broker/components/events/ma_manager.py:275-330
# ─────────────────────────────────────────────────────────────────────

def _handle_flood(event: Any, gs: Dict[str, Any]) -> None:
    gs["flood_occurred"] = event.data.get("occurred", True)
    gs["flood_depth_m"] = event.data.get("depth_m", 0)
    gs["flood_depth_ft"] = event.data.get("depth_ft", 0)


def _handle_no_flood(event: Any, gs: Dict[str, Any]) -> None:
    gs["flood_occurred"] = False
    gs["flood_depth_m"] = 0
    gs["flood_depth_ft"] = 0


def _handle_subsidy_change(event: Any, gs: Dict[str, Any]) -> None:
    gs["subsidy_rate"] = event.data.get("new_value", gs.get("subsidy_rate", 0.5))
    gs["govt_message"] = event.description


def _handle_premium_change(event: Any, gs: Dict[str, Any]) -> None:
    gs["premium_rate"] = event.data.get("new_value", gs.get("premium_rate", 0.02))
    gs["insurance_message"] = event.description


# ─────────────────────────────────────────────────────────────────────
# Per-agent impact handlers — extracted verbatim from the flood
# event-type chain in broker/components/events/ma_manager.py:get_agent_impact.
# These AGGREGATE into a per-agent impact dict (max for depth, sum for
# dollar amounts) rather than overwriting global env state.
# ─────────────────────────────────────────────────────────────────────

def _impact_flood(event: Any, impact: Dict[str, Any]) -> None:
    impact["flooded"] = True
    impact["depth_m"] = max(
        impact.get("depth_m", 0.0), event.data.get("depth_m", 0)
    )


def _impact_flood_damage(event: Any, impact: Dict[str, Any]) -> None:
    impact["damage_amount"] = (
        impact.get("damage_amount", 0.0) + event.data.get("damage_amount", 0)
    )
    impact["oop_cost"] = (
        impact.get("oop_cost", 0.0) + event.data.get("oop_cost", 0)
    )


def _impact_insurance_payout(event: Any, impact: Dict[str, Any]) -> None:
    impact["payout_amount"] = (
        impact.get("payout_amount", 0.0) + event.data.get("payout_amount", 0)
    )


# ─────────────────────────────────────────────────────────────────────
# DomainPack
# ─────────────────────────────────────────────────────────────────────

class FloodDomainPack(DefaultDomainPack):
    """DomainPack for the flood-risk household example.

    Subclasses :class:`DefaultDomainPack` so any DomainPack method not
    overridden below (incl. Phase 6H v2 additions) falls through to the
    no-op default.
    """

    name: str = "flood"

    def __init__(self) -> None:
        self._inner = FloodAdapter()

    # ─── Reflection ───────────────────────────────────────────────

    def reflection_status_text(self, context: Any) -> Optional[str]:
        """Flood status line for the individual reflection prompt.

        Summarises the agent's elevated / insured / flood_count /
        mg_status flags into ``"Current status: ..."``. Returns ``None``
        if no flag is set. The elevated/insured/flood_count values are
        read from ``context.custom_traits`` (Phase 6H Item 9 — the flood
        example populates them there; mg_status stays a generic field).
        """
        # Match the original gate: only emit for "household" agent_type.
        if getattr(context, "agent_type", None) != "household":
            return None

        traits = getattr(context, "custom_traits", None) or {}
        status_parts = []
        if traits.get("elevated", False):
            status_parts.append("your house is elevated")
        if traits.get("insured", False):
            status_parts.append("you have flood insurance")
        flood_count = traits.get("flood_count", 0)
        if flood_count > 0:
            status_parts.append(f"you've been flooded {flood_count} time(s)")
        if getattr(context, "mg_status", False):
            status_parts.append("you have limited resources")

        if not status_parts:
            return None
        return f"Current status: {', '.join(status_parts)}."

    def reflection_questions(self) -> List[str]:
        # Empty → AgentTypeConfig.get_reflection_questions() resolves from
        # agent_types.yaml reflection.questions, else the domain-neutral
        # _DEFAULT_REFLECTION_QUESTIONS fallback in reflection.py.
        return []

    def reflection_persona(self) -> Optional[str]:
        return None

    def reflection_trait_labels(self, context: Any) -> List[str]:
        """Short flood trait labels for the compact batch reflection
        prompt. ``flooded {n}x`` short form (distinct from the status-text
        ``flooded {n} time(s)`` long form). elevated/insured/flood_count
        are read from ``context.custom_traits`` (Phase 6H Item 9);
        mg_status stays a generic field."""
        traits = getattr(context, "custom_traits", None) or {}
        labels: List[str] = []
        if traits.get("elevated", False):
            labels.append("elevated")
        if traits.get("insured", False):
            labels.append("insured")
        flood_count = traits.get("flood_count", 0)
        if flood_count > 0:
            labels.append(f"flooded {flood_count}x")
        if getattr(context, "mg_status", False):
            labels.append("MG")
        return labels

    # ─── Memory / importance / emotion (delegate to existing adapter) ─

    def importance_profiles(self) -> Dict[str, float]:
        return dict(self._inner.importance_profiles)

    def compute_importance(self, context: Any, base: float = 0.9) -> float:
        return self._inner.compute_importance(context, base)

    def classify_emotion(self, decision: str, context: Any) -> str:
        return self._inner.classify_emotion(decision, context)

    def emotional_keywords(self) -> Dict[str, str]:
        return dict(self._inner.emotional_keywords)

    def retrieval_weights(self) -> Dict[str, float]:
        return dict(self._inner.retrieval_weights)

    # ─── Skills ────────────────────────────────────────────────────

    def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]:
        """Reproduces ``experiment_runner.py:383-388`` flood skill→emotion
        mapping byte-identically (importance values 0.7 and 0.6 match
        the pre-refactor literals)."""
        if skill_name in {"elevate_house", "relocate"}:
            return {"emotion": "major", "importance": 0.7, "source": "personal"}
        if skill_name == "buy_insurance":
            return {"emotion": "positive", "importance": 0.6, "source": "personal"}
        # buyout_program and other flood skills fall through to the
        # broker's default "routine" tag (importance 0.1) — preserves
        # pre-refactor behaviour where only the 3 explicitly-named
        # skills got special tags.
        return {}

    def extreme_actions(self) -> Set[str]:
        """Replaces the explicit kwarg in ``validator_bundles.py:87``."""
        return {"relocate", "elevate_house"}

    # ─── Events ────────────────────────────────────────────────────

    def action_taxonomy(self) -> Dict[str, ActionTaxonomyEntry]:
        """Phase 6O-B — read taxonomy from single_agent skill_registry.yaml.

        Note: single-agent flood and governed_flood share the same skill
        set (buy_insurance / elevate_house / relocate / do_nothing); the
        canonical taxonomy declaration lives at
        examples/single_agent/skill_registry.yaml.
        """
        from pathlib import Path
        # examples/single_agent/skill_registry.yaml relative to this file
        yaml_path = (
            Path(__file__).resolve().parents[2]
            / "single_agent"
            / "skill_registry.yaml"
        )
        return load_action_taxonomy_from_skill_registry(yaml_path)

    def event_handlers(self) -> Dict[str, EventHandler]:
        """Replaces the ``ma_manager.py:275-289`` if/elif chain."""
        return {
            "flood": _handle_flood,
            "no_flood": _handle_no_flood,
            "subsidy_change": _handle_subsidy_change,
            "premium_change": _handle_premium_change,
        }

    def agent_impact_handlers(self) -> Dict[str, EventHandler]:
        """Replaces the flood event-type chain in
        ``ma_manager.py:get_agent_impact()`` (Phase 6J-B)."""
        return {
            "flood": _impact_flood,
            "flood_damage": _impact_flood_damage,
            "insurance_payout": _impact_insurance_payout,
        }

    # ─── Memory policy (Phase 6K-A) ───────────────────────────────

    def memory_policy(self) -> MemoryPolicyBundle:
        """Replaces three flood literals previously hardcoded in
        generic ``broker/components/memory/`` (Phase 6K-A 2026-05-22):
        the ``policy_classifier._DEFAULT_RULES`` flood category keys,
        the ``initial_loader`` EXTERNAL_EVENT whitelist, and the
        ``universal.py`` EMA ``stimulus_key`` fallback."""
        return MemoryPolicyBundle(
            category_rules={
                "flood_experience": MemoryContentType.EXTERNAL_EVENT,
                "flood_event": MemoryContentType.EXTERNAL_EVENT,
                "damage": MemoryContentType.EXTERNAL_EVENT,
                "insurance_claim": MemoryContentType.INITIAL_FACTUAL,
                "insurance_history": MemoryContentType.INITIAL_FACTUAL,
            },
            external_event_whitelist=(
                "flood_experience", "flood_event", "damage",
            ),
            stimulus_key="flood_depth_m",
        )

    # ─── Context provider hooks ────────────────────────────────────

    def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
        """Reproduces the Passaic-specific text in ``providers.py:706-712``.

        The original site applies this only when (is_mg, flood_count==1,
        not flooded_this_year, not has_insurance). We keep that gating
        logic in providers.py and just return the text body here so the
        broker code can stay generic.
        """
        return (
            "- **Insurance Enrollment Context**: Among households with your "
            "income profile and community background in the Passaic River Basin "
            "who have experienced one prior flood, carrying NFIP flood insurance "
            "is uncommon — many face enrollment barriers including documentation "
            "requirements, upfront costs, and distrust of federal programs."
        )

    # ─── Validators ────────────────────────────────────────────────

    def builtin_checks(self) -> Dict[str, List[BuiltinCheck]]:
        # Already registered via ValidatorRegistry at
        # examples/governed_flood/validators/__init__.py import time.
        return {}

    # ─── Memory templates ─────────────────────────────────────────

    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]:
        # Provided via FloodMemoryTemplateProvider (Phase 6B-2);
        # broker.core.agent_initializer continues to use that path.
        return []

    # ─── Perception (Phase 6H Item 5) ─────────────────────────────

    def perception_descriptors(self) -> Dict[str, Any]:
        """Numeric→qualitative verbalization rules for the household
        perception filter, keyed by INPUT context field (Phase 6H
        Item 5b). `PerceptionFilterRegistry` injects these."""
        return dict(PERCEPTION_DESCRIPTORS)

    def perception_field_policy(self) -> Dict[str, List[str]]:
        """Field-name lists controlling what HouseholdPerceptionFilter
        strips / aggregates — replaces the former module-level flood
        constants in broker/components/social/perception.py."""
        return {
            "dollar_fields": list(DOLLAR_AMOUNT_FIELDS),
            "percentage_fields": list(PERCENTAGE_FIELDS),
            "community_observable_fields": list(COMMUNITY_OBSERVABLE_FIELDS),
            "neighbor_action_fields": list(NEIGHBOR_ACTION_FIELDS),
        }

    def passthrough_agent_types(self) -> Set[str]:
        """Government and insurance are institutional agents — they
        perceive raw numerical data (Phase 6H Item 5c). Households
        verbalize (the default).

        The MA-flood subtypes ``nj_government`` / ``fema_nfip`` are
        deliberately NOT listed: pre-6H they fell through to the
        verbalizing default, and MA flood (Paper 3) is frozen — keeping
        them off this set preserves byte-identical perception. List them
        here if a future MA-flood run wants institutional subtypes to
        see raw numbers."""
        return {"government", "insurance"}

    def affordability_constraints(self) -> Dict[str, Any]:
        """Flood elevation cost model — replaces the hardcoded
        ``elevate_house`` rule in ``AgentValidator.validate_affordability()``
        (Phase 6H Item 6). $150k base, 50% subsidy default, affordable
        iff post-subsidy cost <= 3x annual income. Insurance
        affordability stays prompt-level guidance (not a hard gate)."""
        return {
            "elevate_house": {
                "base_cost": 150_000.0,
                "income_multiplier": 3.0,
                "default_subsidy_rate": 0.5,
            },
        }

    def phase_layout(self) -> List[Any]:
        """Phase 6P-B (2026-05-25): replaces the hardcoded
        ``if domain.lower() == "flood":`` branch in
        ``broker/components/orchestration/phases.py::from_domain``.
        Returns the four-phase water MAS execution order
        (institutional → household → resolution → observation)."""
        from broker.domains.water.phase_layouts import water_default_phases
        return water_default_phases()

    def hazard_severity_thresholds(self) -> Dict[str, float]:
        """Phase 6P-E (2026-05-25): exposes the four flood-domain
        water-depth thresholds (metres) as a DomainPack-owned
        configuration surface. The values are byte-identical to the
        ``HazardEventConfig.severity_thresholds`` ``default_factory``
        that pre-6P-E lived inside generic broker code; this hook
        relocates the *declaration* of the values to the flood domain
        bundle without (yet) changing the generator's lookup order.
        Full consumer wiring (the generator preferring this hook over
        its built-in defaults) lands in Phase 6P-F when the first
        non-flood hazard domain arrives. Today the hook is advisory."""
        return {
            "critical": 1.2,  # ~4 ft
            "severe": 0.6,    # ~2 ft
            "moderate": 0.3,  # ~1 ft
            "minor": 0.0,
        }

    def csv_loader_class(self) -> Any:
        """Phase 6P-C (2026-05-25): replaces the hardcoded
        ``if domain_name == "flood":`` branch in
        ``broker/core/agent_initializer.py::_resolve_csv_loader_class``.
        ``FloodCSVLoader`` populates the flood-specific profile fields
        (zone, depth, household_value, etc.) on top of the generic
        ``CSVLoader``."""
        from broker.domains.water.loaders import FloodCSVLoader
        return FloodCSVLoader

    def synthetic_loader_class(self) -> Any:
        """Phase 6P-C (2026-05-25): replaces the hardcoded
        ``if domain_name == "flood":`` branch in
        ``broker/core/agent_initializer.py::_resolve_synthetic_loader_class``.
        ``FloodSyntheticLoader`` generates flood-specific synthetic
        profiles with PRB-grid-aware zone assignment."""
        from broker.domains.water.loaders import FloodSyntheticLoader
        return FloodSyntheticLoader
