"""
Irrigation Domain Adapter.

Literature-informed importance profiles for water-resource irrigation ABM.

Design basis:
    - Miller 1956, Cowan 2001   — working memory capacity
    - Ebbinghaus 1885           — exponential decay with event resistance
    - Lazarus 1991, Rogers 1983 — dual-appraisal (WSA=threat, ACA=coping)
    - Godden & Baddeley 1975    — context-dependent retrieval
    - Schon 1983, Argyris 1977  — reflection after significant events

Context fields expected (from agent state or dict):
    water_right_pct   : float  — current water-right utilization (0-1)
    supply_ratio      : float  — water_supply / water_demand
    years_farming     : int    — agent tenure
    has_efficient_system : bool — whether agent has efficient irrigation
    recent_decision   : str    — last skill chosen
    drought_count     : int    — cumulative droughts experienced
    cluster           : str    — behavioral cluster label
"""

from __future__ import annotations

from typing import Dict, Any


class IrrigationAdapter:
    """Domain adapter for irrigation water-resource ABM."""

    importance_profiles: Dict[str, float] = {
        "first_shortage": 0.92,       # First water shortage — formative event
        "repeated_shortage": 0.78,    # Subsequent shortages — habituated
        "drought_year": 0.95,         # Severe drought (supply < 60%)
        "stable_year": 0.55,          # No stress, adequate water
        "at_cap": 0.70,               # At water_right cap, limited options
        "policy_change": 0.88,        # External policy/allocation change
    }

    emotional_keywords: Dict[str, str] = {
        "water_crisis": "critical",       # Drought or severe shortage
        "strategic_choice": "major",      # Efficiency adoption, crop change
        "routine_season": "minor",        # Normal year, maintain demand
        "financial_stress": "critical",   # Cost pressure from water markets
        "community_impact": "major",      # Neighbour effects, basin-level
    }

    retrieval_weights: Dict[str, float] = {
        "W_recency": 0.30,       # Recent experiences matter but less than flood
        "W_importance": 0.40,    # Importance of memory (drought = high)
        "W_context": 0.30,       # Context match (same season, same crop)
    }

    def compute_importance(
        self, context: Dict[str, Any], base: float = 0.70
    ) -> float:
        """Compute dynamic importance for irrigation agents.

        Uses supply_ratio as the primary driver (analogous to flood_count
        in the flood domain).  Secondary drivers are decision type and
        water-right utilisation.
        """
        importance = base

        supply = context.get("supply_ratio", 1.0)
        drought_count = context.get("drought_count", 0)
        decision = context.get("recent_decision", "")
        water_right = context.get("water_right_pct", 0.5)

        # ---- Drought / shortage severity ----
        if supply < 0.60:
            importance = self.importance_profiles["drought_year"]       # 0.95
        elif supply < 0.80:
            if drought_count <= 1:
                importance = self.importance_profiles["first_shortage"]  # 0.92
            else:
                importance = self.importance_profiles["repeated_shortage"]  # 0.78

        # ---- Cap awareness ----
        if water_right >= 0.95:
            importance = max(importance, self.importance_profiles["at_cap"])

        # ---- Stable year floor ----
        if supply >= 1.0 and decision == "maintain_demand":
            importance = min(
                importance, self.importance_profiles["stable_year"]      # 0.55
            )

        return round(min(1.0, max(0.0, importance)), 2)

    def classify_emotion(
        self, decision: str, context: Dict[str, Any]
    ) -> str:
        """Classify emotion for irrigation-domain decisions."""
        supply = context.get("supply_ratio", 1.0)

        if supply < 0.60:
            return "critical"
        if decision == "increase_demand" and context.get("water_right_pct", 0) >= 0.9:
            return "major"  # risky increase near cap
        if decision == "maintain_demand" and supply >= 1.0:
            return "minor"
        return "important"
