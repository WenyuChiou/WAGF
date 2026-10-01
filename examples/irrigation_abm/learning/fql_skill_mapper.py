"""
FQL action → skill mapping for the irrigation ABM baseline.

Maps FQL's continuous signed action (diversion change in acre-ft) to the
skill model used by the execution layer.

FQL (Hung & Yang 2021) natively has only 2 actions: increase or decrease.
There is NO maintain, NO large/small distinction in the original algorithm.
The sign of the action determines direction; the magnitude is the FQL
agent's own sampled step (WP5, irrigation_v3_spec_2026-09-28.md section 5:
run_fql_baseline.py writes the request directly, with no execute_skill()
redraw -- see _fql_agent_decision).

``fql_action_to_skill`` itself only maps a signed float to increase/
decrease/maintain by sign; whether maintain_demand is common or rare
depends entirely on WHAT the caller passes it. WP5's run_simulation
passes the EXECUTED change (spec 5.7: req_final - Div_t, after the
water-right cap, the minimum-use floor, and any governance reversion),
not the raw sampled action, so maintain_demand is produced whenever that
executed change is exactly zero -- at the cap with an increase drawn, at
the floor with a decrease drawn, or whenever governance reverts a blocked
increase to keep -- not only the a == 0.0 exactly edge case. Measured
across a 5-seed, 42-year, 78-agent real calibrated corpus (seeds 42-46,
--no-governance, 2026-09-30): 5.7 percent of rows (927 of 16,380) are
maintain_demand, not "extremely rare".

Also provides WSA/ACA label helpers for logging parity with LLM output.

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
"""

from __future__ import annotations


def fql_action_to_skill(action: float) -> str:
    """Map FQL continuous action to increase or decrease.

    Faithful to FQL's 2-action design: positive → increase, negative →
    decrease.  No large/small distinction (that is an LLM-path concept).

    Args:
        action: Signed diversion change (acre-ft).  Positive = increase.

    Returns:
        One of: increase_demand, decrease_demand, maintain_demand.
    """
    if action > 0:
        return "increase_demand"
    elif action < 0:
        return "decrease_demand"
    else:
        # Degenerate case: exactly zero (extremely rare)
        return "maintain_demand"


def compute_wsa_label(drought_index: float) -> str:
    """Map drought index to Water Scarcity Assessment label.

    Mirrors the 5-level WSA scale used in the LLM prompt template.
    Thresholds from irrigation_personas.py build_water_situation_text().

    Args:
        drought_index: Composite drought severity [0, 1].

    Returns:
        One of: VL, L, M, H, VH.
    """
    if drought_index < 0.2:
        return "VL"
    elif drought_index < 0.4:
        return "L"
    elif drought_index < 0.6:
        return "M"
    elif drought_index < 0.8:
        return "H"
    else:
        return "VH"


def compute_aca_label(cluster: str) -> str:
    """Map FQL cluster to Adaptive Capacity Assessment label.

    Mirrors the LLM's ACA_LABEL extraction in post_step.
    Aggressive -> H (high adaptive capacity, willing to change)
    Forward-looking -> M (moderate, balanced approach)
    Myopic -> L (low adaptive capacity, resistant to change)

    Args:
        cluster: One of aggressive, forward_looking_conservative,
                 myopic_conservative.

    Returns:
        One of: H, M, L.
    """
    mapping = {
        "aggressive": "H",
        "forward_looking_conservative": "M",
        "myopic_conservative": "L",
    }
    return mapping.get(cluster, "M")
