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

    # Supply-side redesign (2026-09-25, spec M1 to M3). Every value below is
    # on [0, 1] (Prof. Yang's rule). Importance of a memory about a year is
    # set by how much of the request went undelivered (the unmet fraction,
    # 1 - delivered / requested, from the final settlement), in bands:
    #   unmet == 0            -> 0.30
    #   0     < unmet < 0.10  -> 0.45
    #   0.10 <= unmet < 0.25  -> 0.60
    #   0.25 <= unmet < 0.50  -> 0.75
    #   0.50 <= unmet         -> 0.90
    # A rejected proposal (fallback year) gets the same band as an approved
    # one: the rejection itself adds no salience. A reflection adds
    # reflection_offset, capped at reflection_cap.
    severity_edges = (0.10, 0.25, 0.50)
    band_importance = (0.30, 0.45, 0.60, 0.75, 0.90)
    reflection_offset: float = 0.10
    reflection_cap: float = 0.95
    crisis_frac: float = 0.25

    _INCREASE = ("increase_large", "increase_small", "increase_demand")
    _DECREASE = ("decrease_large", "decrease_small", "decrease_demand")

    @staticmethod
    def _unmet_frac(context: Dict[str, Any]) -> float:
        """Unmet fraction on [0, 1]: ``unmet_frac`` when given, else
        ``1 - supply_ratio`` (older callers)."""
        if context.get("unmet_frac") is not None:
            u = float(context["unmet_frac"])
        else:
            u = 1.0 - float(context.get("supply_ratio", 1.0))
        return round(min(1.0, max(0.0, u)), 6)

    def outcome_importance(self, unmet_frac: float) -> float:
        """Band importance of a memory line about a year with this unmet
        fraction (see the band table above)."""
        u = min(1.0, max(0.0, float(unmet_frac)))
        if u <= 0.0:
            return self.band_importance[0]
        for edge, value in zip(self.severity_edges, self.band_importance[1:]):
            if u < edge:
                return value
        return self.band_importance[-1]

    def compute_importance(
        self, context: Dict[str, Any], base: float = 0.70
    ) -> float:
        """Importance of a reflection about the year in ``context``.

        Supply-side redesign (2026-09-25): the band of the unmet fraction
        plus ``reflection_offset``, capped at ``reflection_cap``; at least
        ``at_cap`` when the request is at the water right; at most
        ``stable_year`` for a truly stable year, which now means the agent
        PROPOSED maintain_demand, was not overruled (no fallback) and got
        its whole request. Before this, the executed skill was read, so a
        rejected increase (maintain_demand executed as the fallback) looked
        like a stable year and got the floor.

        Context keys: ``proposed_skill`` (the agent's own proposal; falls
        back to ``recent_decision``), ``was_fallback`` (bool),
        ``unmet_frac`` (or ``supply_ratio``), ``water_right_pct``. ``base``
        is accepted for the ReflectionEngine call signature and not used:
        the band table replaces a fixed base.
        """
        unmet = self._unmet_frac(context)
        # An explicit proposed_skill (even "" for a row with no usable
        # proposal) wins; recent_decision only for callers that predate it.
        proposed = (context["proposed_skill"] if "proposed_skill" in context
                    else context.get("recent_decision", "")) or ""
        was_fallback = bool(context.get("was_fallback", False))
        water_right = context.get("water_right_pct", 0.5)

        importance = min(
            self.reflection_cap,
            self.outcome_importance(unmet) + self.reflection_offset,
        )

        # ---- Cap awareness ----
        if water_right >= 0.95:
            importance = max(importance, self.importance_profiles["at_cap"])

        # ---- Stable year ceiling ----
        if proposed == "maintain_demand" and not was_fallback and unmet == 0.0:
            importance = min(importance, self.importance_profiles["stable_year"])

        return round(min(1.0, max(0.0, importance)), 2)

    def classify_emotion(
        self, decision: str, context: Dict[str, Any]
    ) -> str:
        """Classify the emotion of a memory about one year.

        Returns a key of ``irrigation_farmer.memory.emotional_weights``
        (water_crisis / strategic_choice / positive_outcome /
        baseline_observation), so the engine never falls back to its 0.1
        default (F08+F33).

        Supply-side redesign (2026-09-25): reads the PROPOSED skill
        (``context["proposed_skill"]``, else ``decision``) and the fallback
        flag, not the executed skill: unmet fraction at or above
        ``crisis_frac`` is a water crisis; a proposed change of demand, or a
        year whose proposal was overruled, is a strategic choice; a proposed
        maintain with the whole request delivered is a positive outcome;
        anything else is a baseline observation.
        """
        unmet = self._unmet_frac(context)
        proposed = (context["proposed_skill"] if "proposed_skill" in context
                    else decision) or ""
        was_fallback = bool(context.get("was_fallback", False))

        if unmet >= self.crisis_frac:
            return "water_crisis"
        if proposed in self._INCREASE or proposed in self._DECREASE or was_fallback:
            return "strategic_choice"
        if proposed == "maintain_demand" and unmet == 0.0:
            return "positive_outcome"
        return "baseline_observation"
