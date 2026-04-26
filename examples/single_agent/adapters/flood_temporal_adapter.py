"""Flood-domain implementation of DomainTemporalAdapter.

Maps generic temporal-rule framework concepts into flood-specific
semantics:

- salient event  = memory tagged with emotion ∈ {critical, major}
                    (flood occurrence, direct damage, major protective
                    commitment — see emotion keyword map in
                    agent_types.yaml for the flood household config)
- irreversible   = elevate_house, relocate
- low appraisal  = {'VL', 'L'} — PMT low-threat labels
- high volatility = threat appraisal ordinal range ≥ 2 levels

Lives under examples/<domain>/adapters/ per Invariant 5. The broker/
framework code never imports from this file.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

from broker.components.governance.temporal_rules import AgentTurn

_TP_ORDER = ("VL", "L", "M", "H", "VH")


class FloodTemporalAdapter:
    """Single-agent flood domain temporal adapter.

    Salience set was chosen to match the flood-household emotion
    keyword map used throughout the governed-broker flood runs;
    adapter is the SINGLE point where the flood-specific assumptions
    live, so switching to a different domain (e.g., irrigation, drought)
    only requires writing a new adapter — framework stays untouched.
    """

    _SALIENT_EMOTIONS: Set[str] = {"critical", "major"}
    _IRREVERSIBLE_SKILLS: Set[str] = {"elevate_house", "relocate"}
    _LOW_APPRAISAL: Set[str] = {"VL", "L"}

    def is_salient_event(self, memory: Dict[str, Any]) -> bool:
        emotion = str(memory.get("emotion", "")).strip().lower()
        return emotion in self._SALIENT_EMOTIONS

    def is_irreversible(self, skill_id: str) -> bool:
        return str(skill_id).strip().lower() in self._IRREVERSIBLE_SKILLS

    def low_appraisal_set(self) -> Set[str]:
        return set(self._LOW_APPRAISAL)

    def high_volatility(self, window: List[AgentTurn]) -> bool:
        """High volatility = threat appraisal range spans ≥ 2 ordinal levels.

        Uses {VL:0, L:1, M:2, H:3, VH:4} ordinal mapping. Missing labels
        are skipped (NOT counted as 0, to avoid spurious range).
        """
        levels = [
            _TP_ORDER.index(t.threat_label)
            for t in window
            if t.threat_label in _TP_ORDER
        ]
        if len(levels) < 2:
            return False
        return (max(levels) - min(levels)) >= 2
