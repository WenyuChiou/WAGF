"""
Flood Domain Reflection Adapter for Multi-Agent Flood ABM.

Provides flood-specific importance scoring and emotional classification
for the ReflectionEngine. Without this adapter, reflection uses generic
defaults that do not account for flood depth, flood count, or
adaptation-specific importance.

Implements the DomainReflectionAdapter protocol from
broker.components.cognitive.adapters.
"""

from __future__ import annotations

from typing import Dict, Any


class FloodHouseholdAdapter:
    """Domain adapter for multi-agent flood household ABM."""

    importance_profiles: Dict[str, float] = {
        "severe_flood": 0.95,          # flood_depth > 1.0m
        "moderate_flood": 0.82,        # flood_depth 0.3-1.0m
        "minor_flood": 0.65,           # flood_depth < 0.3m
        "post_flood_year": 0.70,       # year after any flood
        "no_flood": 0.45,              # stable year
        "first_insurance": 0.80,       # first time buying insurance
        "elevation_decision": 0.90,    # costly structural decision
        "buyout_decision": 0.95,       # irreversible decision
        "relocation_decision": 0.90,   # major life change
    }

    emotional_keywords: Dict[str, str] = {
        "severe_damage": "critical",
        "flood_experience": "major",
        "insurance_purchase": "positive",
        "elevation_complete": "positive",
        "do_nothing_flooded": "critical",
        "routine_year": "routine",
        "neighbor_action": "observation",
    }

    retrieval_weights: Dict[str, float] = {
        "W_recency": 0.25,
        "W_importance": 0.50,      # flood memories should persist longer
        "W_context": 0.25,
    }

    def compute_importance(
        self, context: Dict[str, Any], base: float = 0.65
    ) -> float:
        """Compute dynamic importance from flood-domain agent context.

        Primary driver: flood_depth (current year).
        Secondary: flood_count (cumulative), decision type.
        """
        importance = base

        flood_depth = context.get("flood_depth", context.get("flood_depth_m", 0))
        flood_count = context.get("flood_count", 0)
        decision = context.get("recent_decision", "")
        flooded_this_year = context.get("flooded_this_year", False)

        # Flood severity
        if flood_depth > 1.0:
            importance = self.importance_profiles["severe_flood"]       # 0.95
        elif flood_depth > 0.3:
            importance = self.importance_profiles["moderate_flood"]     # 0.82
        elif flooded_this_year:
            importance = self.importance_profiles["minor_flood"]        # 0.65
        elif flood_count > 0:
            importance = self.importance_profiles["post_flood_year"]    # 0.70
        else:
            importance = self.importance_profiles["no_flood"]           # 0.45

        # Decision-type boost
        if decision in ("elevate_house",):
            importance = max(importance, self.importance_profiles["elevation_decision"])
        elif decision in ("buyout_program",):
            importance = max(importance, self.importance_profiles["buyout_decision"])
        elif decision in ("relocate",):
            importance = max(importance, self.importance_profiles["relocation_decision"])

        return round(min(1.0, max(0.0, importance)), 2)

    def classify_emotion(
        self, decision: str, context: Dict[str, Any]
    ) -> str:
        """Classify emotion for flood-domain decisions."""
        flood_depth = context.get("flood_depth", context.get("flood_depth_m", 0))
        flood_count = context.get("flood_count", 0)
        flooded = context.get("flooded_this_year", False)

        if flood_depth > 1.0:
            return "critical"
        if flooded and decision == "do_nothing":
            return "critical"
        if decision in ("elevate_house", "buyout_program", "relocate"):
            return "major"
        if decision in ("buy_insurance", "buy_contents_insurance") and flood_count == 0:
            return "positive"
        if flooded:
            return "major"
        return "routine"
