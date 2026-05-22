"""
Observable State Manager - Computes and caches cross-agent observables.

Usage:
    manager = ObservableStateManager()
    manager.register(ObservableMetric("rate", compute_fn, ObservableScope.COMMUNITY))
    manager.set_neighbor_graph(graph)  # Optional, for NEIGHBORS scope

    snapshot = manager.compute(agents, year=1)
    value = manager.get("rate")  # From current snapshot

Factories:
    create_rate_metric() - Generic penetration/rate metric

Domain-specific metric bundles (e.g. the flood insurance / elevation
observables) live under ``broker/domains/<domain>/`` — see
``broker/domains/water/observables.py``.
"""
from typing import Dict, Any, List, Optional, Set, Callable
from broker.interfaces.observable_state import (
    ObservableMetric,
    ObservableScope,
    ObservableSnapshot,
    ObservableStateProtocol,
    NeighborGraphProtocol,
)


class ObservableStateManager:
    """Manages observable metrics with multi-scope support.

    Implements ObservableStateProtocol for use with broker components.
    """

    def __init__(self):
        self._metrics: Dict[str, ObservableMetric] = {}
        self._snapshot: Optional[ObservableSnapshot] = None
        self._neighbor_graph: Optional[NeighborGraphProtocol] = None
        self._type_field: str = "agent_type"  # Field name for TYPE scope

    def register(self, metric: ObservableMetric) -> None:
        """Register a single metric."""
        self._metrics[metric.name] = metric

    def register_many(self, metrics: List[ObservableMetric]) -> None:
        """Register multiple metrics."""
        for m in metrics:
            self.register(m)

    def set_neighbor_graph(self, graph: NeighborGraphProtocol) -> None:
        """Set the neighbor graph for NEIGHBORS scope metrics."""
        self._neighbor_graph = graph

    def set_type_field(self, field_name: str) -> None:
        """Set the attribute name used for TYPE scope grouping."""
        self._type_field = field_name

    def compute(self, agents: Dict[str, Any], year: int, step: int = 0) -> ObservableSnapshot:
        """Compute all registered metrics and cache snapshot."""
        snapshot = ObservableSnapshot(year=year, step=step)

        for name, metric in self._metrics.items():
            if metric.scope == ObservableScope.COMMUNITY:
                self._compute_community(snapshot, name, metric, agents)
            elif metric.scope == ObservableScope.TYPE:
                self._compute_by_type(snapshot, name, metric, agents)
            elif metric.scope == ObservableScope.NEIGHBORS:
                self._compute_by_neighborhood(snapshot, name, metric, agents)
            elif metric.scope == ObservableScope.SPATIAL:
                self._compute_by_region(snapshot, name, metric, agents)

        self._snapshot = snapshot
        return snapshot

    def _compute_community(self, snapshot: ObservableSnapshot, name: str,
                           metric: ObservableMetric, agents: Dict) -> None:
        """Compute community-wide metric."""
        try:
            value = metric.compute_fn(agents) if agents else 0.0
            snapshot.community[name] = float(value)
        except Exception:
            snapshot.community[name] = 0.0

    def _compute_by_type(self, snapshot: ObservableSnapshot, name: str,
                         metric: ObservableMetric, agents: Dict) -> None:
        """Compute metric per agent type."""
        types = self._get_unique_types(agents)
        by_type = {}
        for type_id in types:
            type_agents = {
                k: v for k, v in agents.items()
                if self._get_type(v) == type_id
            }
            try:
                by_type[type_id] = float(metric.compute_fn(type_agents)) if type_agents else 0.0
            except Exception:
                by_type[type_id] = 0.0
        snapshot.by_type[name] = by_type

    def _compute_by_neighborhood(self, snapshot: ObservableSnapshot, name: str,
                                  metric: ObservableMetric, agents: Dict) -> None:
        """Compute metric per agent's neighborhood."""
        if not self._neighbor_graph:
            return

        for agent_id in agents:
            neighbors = self._neighbor_graph.get_neighbors(agent_id)
            neighbor_agents = {k: agents[k] for k in neighbors if k in agents}

            if agent_id not in snapshot.by_neighborhood:
                snapshot.by_neighborhood[agent_id] = {}

            try:
                value = float(metric.compute_fn(neighbor_agents)) if neighbor_agents else 0.0
            except Exception:
                value = 0.0
            snapshot.by_neighborhood[agent_id][name] = value

    def _compute_by_region(self, snapshot: ObservableSnapshot, name: str,
                           metric: ObservableMetric, agents: Dict) -> None:
        """Compute metric per spatial region."""
        regions = self._get_unique_regions(agents)
        by_region = {}
        for region_id in regions:
            region_agents = {
                k: v for k, v in agents.items()
                if getattr(v, 'region', getattr(v, 'tract_id', None)) == region_id
            }
            try:
                by_region[region_id] = float(metric.compute_fn(region_agents)) if region_agents else 0.0
            except Exception:
                by_region[region_id] = 0.0
        snapshot.by_region[name] = by_region

    def _get_type(self, agent: Any) -> str:
        """Get agent type from agent object or dict."""
        if isinstance(agent, dict):
            return agent.get(self._type_field, "default")
        return getattr(agent, self._type_field, "default")

    def _get_unique_types(self, agents: Dict) -> Set[str]:
        """Get set of unique agent types."""
        return {self._get_type(a) for a in agents.values()}

    def _get_unique_regions(self, agents: Dict) -> Set[str]:
        """Get set of unique regions."""
        regions = set()
        for a in agents.values():
            region = getattr(a, 'region', getattr(a, 'tract_id', None))
            if region:
                regions.add(region)
        return regions

    def get(self, name: str, scope: str = "community", scope_id: str = None) -> float:
        """Get observable value from current snapshot."""
        if not self._snapshot:
            return 0.0
        return self._snapshot.get(name, scope, scope_id)

    @property
    def snapshot(self) -> Optional[ObservableSnapshot]:
        """Current computed snapshot."""
        return self._snapshot

    @property
    def metrics(self) -> Dict[str, ObservableMetric]:
        """Registered metrics."""
        return self._metrics.copy()


# ============================================================================
# Metric Factories
# ============================================================================

def create_rate_metric(
    name: str,
    condition: Callable[[Any], bool],
    filter_fn: Callable[[Any], bool] = None,
    scope: ObservableScope = ObservableScope.COMMUNITY,
    description: str = "",
) -> ObservableMetric:
    """Factory for rate/penetration metrics.

    Args:
        name: Metric name
        condition: Function that returns True if agent meets condition
        filter_fn: Optional filter (e.g., exclude relocated agents)
        scope: Observable scope
        description: Human description

    Returns:
        ObservableMetric configured for rate computation

    Example:
        >>> metric = create_rate_metric(
        ...     name="insurance_rate",
        ...     condition=lambda a: getattr(a, 'has_insurance', False),
        ...     filter_fn=lambda a: not getattr(a, 'relocated', False),
        ... )
    """
    def compute_rate(agents: Dict[str, Any]) -> float:
        if filter_fn:
            filtered = [a for a in agents.values() if filter_fn(a)]
        else:
            filtered = list(agents.values())

        if not filtered:
            return 0.0

        count = sum(1 for a in filtered if condition(a))
        return count / len(filtered)

    return ObservableMetric(
        name=name,
        compute_fn=compute_rate,
        scope=scope,
        description=description,
    )


def create_drift_observables(drift_detector=None) -> Dict[str, Callable]:
    """Factory for drift-related observable metrics.

    Returns a dict of callables (agents, env) -> float:
    - decision_entropy
    - dominant_action_pct
    - stagnation_rate
    """

    def _entropy_compute(agents, env) -> float:
        if drift_detector and drift_detector.population_snapshots:
            latest = drift_detector.population_snapshots[-1]
            dist = latest.get("distribution", {})
            from .drift import DriftDetector
            return DriftDetector.compute_shannon_entropy(dist)
        return 0.0

    def _dominant_pct_compute(agents, env) -> float:
        if drift_detector and drift_detector.population_snapshots:
            latest = drift_detector.population_snapshots[-1]
            dist = latest.get("distribution", {})
            total = sum(dist.values())
            if total > 0:
                return max(dist.values()) / total
        return 0.0

    def _stagnation_compute(agents, env) -> float:
        if drift_detector:
            total = len(drift_detector.decision_history)
            if total == 0:
                return 0.0
            stagnant = sum(
                1 for aid in drift_detector.decision_history
                if drift_detector.compute_jaccard_similarity(aid) > drift_detector.jaccard_threshold
            )
            return stagnant / total
        return 0.0

    return {
        "decision_entropy": _entropy_compute,
        "dominant_action_pct": _dominant_pct_compute,
        "stagnation_rate": _stagnation_compute,
    }


__all__ = [
    "ObservableStateManager",
    "create_rate_metric",
    "create_drift_observables",
]
