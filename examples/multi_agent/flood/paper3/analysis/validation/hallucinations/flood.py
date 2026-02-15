"""
Hallucination Detection for Flood ABM.

Checks for physically impossible actions given agent state.
Implements HallucinationChecker protocol.
"""

import json
from typing import Dict

from validation.io.trace_reader import _normalize_action, _extract_action


def _is_hallucination(trace: Dict) -> bool:
    """Check if trace contains a hallucination (physically impossible action).

    Backward-compatible free function. For new code, use FloodHallucinationChecker.
    """
    action = _normalize_action(_extract_action(trace))
    state_before = trace.get("state_before", {})
    if isinstance(state_before, str):
        try:
            state_before = json.loads(state_before)
        except (json.JSONDecodeError, TypeError):
            state_before = {}

    # Already elevated and trying to elevate again
    if action == "elevate" and state_before.get("elevated", False):
        return True

    # Already bought out but still making decisions
    if state_before.get("bought_out", False) and action and action != "do_nothing":
        return True

    # Renter trying to elevate
    agent_type = trace.get("agent_type", "")
    if agent_type and ("renter" in agent_type.lower()) and action == "elevate":
        return True

    return False


class FloodHallucinationChecker:
    """Flood ABM hallucination checker implementing HallucinationChecker protocol."""

    @property
    def name(self) -> str:
        return "flood_physical"

    def is_hallucination(self, trace: Dict) -> bool:
        return _is_hallucination(trace)
