"""FakeTrafficDomainPack — non-water DomainPack for E2E genericity (Phase 6Q-F-2).

Scope: minimum hooks to drive `ExperimentBuilder` end-to-end with a
domain that uses the FRAMEWORK_ESCAPE_HATCH path (no registered
psychometric framework). Skill vocabulary is congestion-response
themed (take_alternate_route / delay_departure / switch_to_transit
/ carpool / do_nothing). Agent types: ``commuter`` (the household
analogue) + ``dispatcher`` (the institutional analogue).

What this fixture is NOT: a paper-shipping example. It deliberately
lacks calibrated reflection text / importance profiles / event
handlers / domain-specific validators — the broker's
DefaultDomainPack defaults are exercised for everything not
overridden here. That's the point: prove the generic broker can
run a non-water domain on no-op defaults.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from broker.domains.default import DefaultDomainPack
from broker.validators.governance.thinking_validator import (
    FRAMEWORK_ESCAPE_HATCH,
)


class FakeTrafficDomainPack(DefaultDomainPack):
    """Minimum-viable non-water DomainPack for E2E genericity gate."""

    name: str = "traffic"

    # ─── Reflection ─────────────────────────────────────────────────

    def reflection_status_text(self, context: Any) -> Optional[str]:
        """Per-agent narrative status block. Domain-neutral text — no
        flood / household / insurance vocabulary."""
        if getattr(context, "agent_type", None) != "commuter":
            return None
        parts: List[str] = []
        custom = getattr(context, "custom_traits", {}) or {}
        if custom.get("last_action") == "switch_to_transit":
            parts.append("you switched to transit last week")
        if custom.get("congestion_observed"):
            parts.append("you observed significant congestion on your route")
        if not parts:
            return None
        return "Current commute context: " + "; ".join(parts) + "."

    def reflection_questions(self) -> List[str]:
        return [
            "Did my last commute choice reduce my exposure to congestion?",
            "What signals from peers or media suggest tomorrow's commute risk?",
        ]

    def reflection_persona(self) -> Optional[str]:
        return (
            "Speak in first person as a commuter weighing daily trade-offs "
            "between travel time, cost, and reliability."
        )

    # ─── Importance / memory ────────────────────────────────────────

    def importance_profiles(self) -> Dict[str, float]:
        # Domain-neutral salience anchors. Pre-6Q-C any fallback used
        # PMT TP/CP labels; this domain explicitly declares its own.
        return {
            "first_severe_congestion": 0.92,
            "transit_switch_year": 0.85,
            "routine_commute": 0.30,
        }

    def emotional_keywords(self) -> Dict[str, str]:
        return {
            "delay": "frustration",
            "gridlock": "frustration",
            "smooth": "satisfaction",
            "on_time": "satisfaction",
        }

    # ─── Skills ─────────────────────────────────────────────────────

    def extreme_actions(self) -> Set[str]:
        """One-way actions (irreversible per simulation year). Empty —
        traffic decisions are revocable each day."""
        return set()

    def action_taxonomy(self) -> Dict[str, Any]:
        # Phase 6O-B contract — structural metadata for the readiness
        # reporter. All traffic skills are reversible + low-cost; no
        # extreme actions.
        from broker.interfaces.action_taxonomy import ActionTaxonomyEntry
        return {
            skill: ActionTaxonomyEntry(
                category="mobility_choice",
                intensity="moderate" if skill != "do_nothing" else "low",
                reversibility="reversible",
            )
            for skill in [
                "take_alternate_route",
                "delay_departure",
                "switch_to_transit",
                "carpool",
                "do_nothing",
            ]
        }

    # ─── Psychological framework ────────────────────────────────────

    def psychological_framework(self) -> str:
        """Phase 6Q-D contract: FRAMEWORK_ESCAPE_HATCH — this fixture
        intentionally has no registered psychometric framework. The
        broker should still construct + run via the generic
        VL/L/M/H/VH label-ordering fallback (this is the point of
        the genericity E2E gate)."""
        return FRAMEWORK_ESCAPE_HATCH
