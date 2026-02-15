"""
Flood ABM Grounding Strategy — rule-based TP/CP grounding.

Implements GroundingStrategy protocol for PMT-based flood adaptation.
"""

from typing import Dict

from validation.metrics.cgr import ground_tp_from_state, ground_cp_from_state


class FloodGroundingStrategy:
    """Flood ABM grounding: TP from flood risk indicators, CP from socioeconomic."""

    @property
    def name(self) -> str:
        return "flood_pmt"

    def ground_constructs(self, state_before: Dict) -> Dict[str, str]:
        return {
            "TP": ground_tp_from_state(state_before),
            "CP": ground_cp_from_state(state_before),
        }
