"""Water-domain (flood) observable metrics.

Pre-built :class:`ObservableMetric` factories for the flood adaptation
model — insurance / elevation penetration, adaptation and relocation
rates. The generic :class:`ObservableStateManager` and
:func:`create_rate_metric` live in
``broker/components/analytics/observable.py``; this module only supplies
the flood-specific metric definitions (Phase 6I-D — de-flood of the
generic analytics layer).
"""
from typing import List

from broker.interfaces.observable_state import ObservableMetric, ObservableScope
from broker.components.analytics.observable import create_rate_metric


def create_flood_observables() -> List[ObservableMetric]:
    """Factory for flood domain observable metrics.

    Returns metrics for:
    - insurance_penetration_rate (community): % of active agents with insurance
    - elevation_penetration_rate (community): % of active agents with elevation
    - adaptation_rate (community): % of active agents with any protection
    - relocation_rate (community): % of all agents relocated
    - neighbor_insurance_rate (neighbors): % of neighbors with insurance
    - neighbor_elevation_rate (neighbors): % of neighbors with elevation

    Example:
        >>> from broker.components.analytics.observable import ObservableStateManager
        >>> manager = ObservableStateManager()
        >>> manager.register_many(create_flood_observables())
        >>> snapshot = manager.compute(agents, year=1)
        >>> print(snapshot.community["insurance_penetration_rate"])
    """
    def is_active(a):
        return not getattr(a, 'relocated', False)

    return [
        create_rate_metric(
            "insurance_penetration_rate",
            condition=lambda a: getattr(a, 'has_insurance', False),
            filter_fn=is_active,
            description="% of active agents with insurance",
        ),
        create_rate_metric(
            "elevation_penetration_rate",
            condition=lambda a: getattr(a, 'elevated', False),
            filter_fn=is_active,
            description="% of active agents with elevation",
        ),
        create_rate_metric(
            "adaptation_rate",
            condition=lambda a: getattr(a, 'elevated', False) or getattr(a, 'has_insurance', False),
            filter_fn=is_active,
            description="% of active agents with any protection",
        ),
        create_rate_metric(
            "relocation_rate",
            condition=lambda a: getattr(a, 'relocated', False),
            filter_fn=None,  # Include all agents
            description="% of agents relocated",
        ),
        # Neighborhood variants
        create_rate_metric(
            "neighbor_insurance_rate",
            condition=lambda a: getattr(a, 'has_insurance', False),
            filter_fn=is_active,
            scope=ObservableScope.NEIGHBORS,
            description="% of neighbors with insurance",
        ),
        create_rate_metric(
            "neighbor_elevation_rate",
            condition=lambda a: getattr(a, 'elevated', False),
            filter_fn=is_active,
            scope=ObservableScope.NEIGHBORS,
            description="% of neighbors with elevation",
        ),
    ]


__all__ = ["create_flood_observables"]
