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

from broker.domains.protocol import BuiltinCheck, EventHandler

from examples.governed_flood.adapters.flood_adapter import FloodAdapter


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
# DomainPack
# ─────────────────────────────────────────────────────────────────────

class FloodDomainPack:
    """DomainPack for the flood-risk household example."""

    name: str = "flood"

    def __init__(self) -> None:
        self._inner = FloodAdapter()

    # ─── Reflection ───────────────────────────────────────────────

    def reflection_status_text(self, context: Any) -> Optional[str]:
        """Reproduces ``reflection.py:301-313`` flood status block.

        Returns a single line ``"Current status: ..."`` summarising the
        agent's elevated/insured/flood_count/mg_status flags. Returns
        ``None`` if no flags are set (matches pre-refactor behaviour
        where the block emitted nothing if all flags were False/0).
        """
        # Match the original gate: only emit for "household" agent_type.
        if getattr(context, "agent_type", None) != "household":
            return None

        status_parts = []
        if getattr(context, "elevated", False):
            status_parts.append("your house is elevated")
        if getattr(context, "insured", False):
            status_parts.append("you have flood insurance")
        flood_count = getattr(context, "flood_count", 0)
        if flood_count > 0:
            status_parts.append(f"you've been flooded {flood_count} time(s)")
        if getattr(context, "mg_status", False):
            status_parts.append("you have limited resources")

        if not status_parts:
            return None
        return f"Current status: {', '.join(status_parts)}."

    def reflection_questions(self) -> List[str]:
        # Falls back to REFLECTION_QUESTIONS["household"] in reflection.py;
        # not duplicated here.
        return []

    def reflection_persona(self) -> Optional[str]:
        return None

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

    def event_handlers(self) -> Dict[str, EventHandler]:
        """Replaces the ``ma_manager.py:275-289`` if/elif chain."""
        return {
            "flood": _handle_flood,
            "no_flood": _handle_no_flood,
            "subsidy_change": _handle_subsidy_change,
            "premium_change": _handle_premium_change,
        }

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
