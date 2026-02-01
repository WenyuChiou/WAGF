"""
Flood-Risk Domain Adapter.

Extracted from the original hardcoded logic in reflection_engine.py:337-364
and IMPORTANCE_PROFILES at reflection_engine.py:67-74.

Context fields expected (from AgentReflectionContext or dict):
    flood_count  : int   — number of floods experienced
    mg_status    : bool  — marginalized group flag
    recent_decision : str — last skill chosen (e.g. "elevate_house")
    elevated     : bool  — house is elevated
    insured      : bool  — has flood insurance
"""

from __future__ import annotations

from typing import Dict, Any


class FloodAdapter:
    """Domain adapter for flood-risk household ABM."""

    importance_profiles: Dict[str, float] = {
        "first_flood": 0.95,       # First flood experience → very memorable
        "repeated_flood": 0.75,    # Repeated floods → diminishing impact
        "post_action": 0.80,       # Just took a major action (elevate/relocate)
        "stable_year": 0.60,       # Nothing major happened
        "denied_action": 0.85,     # Governance denial → memorable frustration
        "mg_agent": 0.90,          # MG agents retain reflections more
    }

    emotional_keywords: Dict[str, str] = {
        "flood_damage": "critical",
        "evacuation": "critical",
        "elevate_house": "major",
        "relocate": "major",
        "buy_insurance": "important",
        "do_nothing": "minor",
        "stable_year": "minor",
    }

    retrieval_weights: Dict[str, float] = {
        "W_recency": 0.30,
        "W_importance": 0.50,
        "W_context": 0.20,
    }

    def compute_importance(
        self, context: Dict[str, Any], base: float = 0.9
    ) -> float:
        """Compute dynamic importance for flood-risk agents.

        Mirrors the original ``ReflectionEngine.compute_dynamic_importance``
        method (reflection_engine.py:337-364), now extracted for reuse.
        """
        importance = base

        flood_count = context.get("flood_count", 0)
        mg_status = context.get("mg_status", False)
        recent_decision = context.get("recent_decision", "")

        # Flood-count scaling
        if flood_count == 1:
            importance = self.importance_profiles["first_flood"]
        elif flood_count > 2:
            importance = self.importance_profiles["repeated_flood"]

        # Marginalized group boost
        if mg_status:
            importance = max(importance, self.importance_profiles["mg_agent"])

        # Post-action boost
        if recent_decision in ("elevate_house", "relocate", "buy_insurance"):
            importance = max(importance, self.importance_profiles["post_action"])

        # Stable year floor
        if (
            not mg_status
            and flood_count == 0
            and recent_decision in ("do_nothing", "")
        ):
            importance = min(importance, self.importance_profiles["stable_year"])

        return round(min(1.0, max(0.0, importance)), 2)

    def classify_emotion(
        self, decision: str, context: Dict[str, Any]
    ) -> str:
        """Classify emotion for flood-domain decisions."""
        if decision in self.emotional_keywords:
            return self.emotional_keywords[decision]

        flood_count = context.get("flood_count", 0)
        if flood_count > 0 and decision == "do_nothing":
            return "major"  # doing nothing after a flood is significant
        return "minor"
