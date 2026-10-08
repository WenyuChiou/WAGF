"""Irrigation spec 45p/45q: shared eligibility for the TR1 exception."""
from typing import Optional

TR1_RULE = 'high_scarcity_no_increase'
TR1_HIGH_WSA = frozenset({'H', 'VH'})


def restoration_available(previous_gap_reason: Optional[str],
                          previous_request_af: Optional[float],
                          base_af: Optional[float]) -> bool:
    """A tier-only cut reduced last year's delivery below its request.

    The ordinary H&Y increase can exceed the previous request. Eligibility
    never depends on a sampled step or on this year's resulting request.
    """
    return bool(previous_gap_reason == 'lb_junior_tier_cut'
                and previous_request_af is not None and base_af is not None
                and previous_request_af > base_af)


def tr1_violation(skill: Optional[str], wsa: Optional[str], *,
                  previous_gap_reason: Optional[str] = None,
                  previous_request_af: Optional[float] = None,
                  base_af: Optional[float] = None) -> bool:
    """An increase at H/VH violates TR1 unless the prior tier cut qualifies."""
    return (skill == 'increase_demand' and wsa in TR1_HIGH_WSA
            and not restoration_available(previous_gap_reason, previous_request_af, base_af))
