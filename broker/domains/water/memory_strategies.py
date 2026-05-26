"""Water-domain memory-strategy factories.

Phase 6Q-D-2 (2026-05-26): relocated ``create_flood_surprise_strategy``
from generic ``broker.memory.strategies.multidimensional`` to this
water-namespace home. The factory's body hardcodes flood-domain
variable names (``flood_depth`` / ``neighbor_panic`` / ``elevated_pct``
/ ``subsidy_rate``) — it was never domain-neutral and its previous
address in generic broker namespace was a Layer 3 audit finding
(#20 from the Phase 6P-E follow-up audit).

The underlying ``MultiDimensionalSurpriseStrategy`` class itself
stays in ``broker.memory.strategies.multidimensional`` — it accepts
an arbitrary ``variables: Dict[str, float]`` and is genuinely
domain-neutral. Only the flood-flavoured factory shorthand moved.
"""
from __future__ import annotations

from broker.memory.strategies.multidimensional import (
    MultiDimensionalSurpriseStrategy,
)


def create_flood_surprise_strategy(
    include_social: bool = True,
    include_policy: bool = True,
    alpha: float = 0.3,
) -> MultiDimensionalSurpriseStrategy:
    """
    Create a pre-configured multi-dimensional surprise strategy for the
    flood domain.

    Args:
        include_social: Include neighbor panic tracking
        include_policy: Include policy change tracking
        alpha: EMA smoothing factor

    Returns:
        Configured ``MultiDimensionalSurpriseStrategy`` with flood-
        domain stimulus keys (``flood_depth``, optionally
        ``neighbor_panic`` / ``elevated_pct`` / ``subsidy_rate``).
    """
    variables = {
        "flood_depth": 0.4,
    }

    if include_social:
        variables["neighbor_panic"] = 0.3
        variables["elevated_pct"] = 0.15

    if include_policy:
        variables["subsidy_rate"] = 0.15

    return MultiDimensionalSurpriseStrategy(
        variables=variables,
        alpha=alpha,
        aggregation="max",  # Any spike triggers System 2
    )


__all__ = ["create_flood_surprise_strategy"]
