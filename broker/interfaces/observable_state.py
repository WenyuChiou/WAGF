"""
Observable State Module - General-purpose mechanism for cross-agent observation.

Design Principles:
1. Domain-agnostic: Core module knows nothing about flood/insurance/etc
2. Pluggable metrics: Register any compute function
3. Multi-scope: community, neighbors, type-based, spatial
4. Update modes: per_year, per_step, on_demand
"""
from typing import Dict, Any, List, Protocol, Callable, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


class ObservableScope(Enum):
    """Scope at which an observable is computed."""
    COMMUNITY = "community"      # All agents
    NEIGHBORS = "neighbors"      # Per-agent neighborhood
    TYPE = "type"                # Per agent_type
    SPATIAL = "spatial"          # Per spatial region/tract


class UpdateFrequency(Enum):
    """When observables are recomputed."""
    PER_YEAR = "per_year"        # Once per simulation year
    PER_STEP = "per_step"        # After each agent decision
    ON_DEMAND = "on_demand"      # Manually triggered


@dataclass
class ObservableMetric:
    """Definition of an observable metric.

    Args:
        name: Unique identifier for this metric
        compute_fn: Function that takes agents dict and returns float/dict
        scope: At what level to compute (community, neighbors, type, spatial)
        update_frequency: When to recompute
        description: Human-readable description
    """
    name: str
    compute_fn: Callable[[Dict[str, Any]], Union[float, Dict[str, float]]]
    scope: ObservableScope = ObservableScope.COMMUNITY
    update_frequency: UpdateFrequency = UpdateFrequency.PER_YEAR
    description: str = ""


@dataclass
class ObservableSnapshot:
    """Container for all observable values at a point in time."""
    year: int
    step: int = 0
    community: Dict[str, float] = field(default_factory=dict)
    by_type: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_neighborhood: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_region: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def get(self, name: str, scope: str = "community", scope_id: str = None) -> float:
        """Get observable value with safe defaults."""
        if scope == "community":
            return self.community.get(name, 0.0)
        elif scope == "type":
            return self.by_type.get(name, {}).get(scope_id, 0.0)
        elif scope == "neighbors":
            return self.by_neighborhood.get(scope_id, {}).get(name, 0.0)
        elif scope == "spatial":
            return self.by_region.get(scope_id, {}).get(name, 0.0)
        return 0.0


class ObservableStateProtocol(Protocol):
    """Interface for observable state management.

    Implementations must provide these methods for compatibility with
    the broker's context provider system.
    """

    def register(self, metric: ObservableMetric) -> None:
        """Register a new observable metric."""
        ...

    def register_many(self, metrics: List[ObservableMetric]) -> None:
        """Register multiple metrics at once."""
        ...

    def compute(self, agents: Dict[str, Any], year: int, step: int = 0) -> ObservableSnapshot:
        """Compute all registered metrics from current agent states."""
        ...

    def get(self, name: str, scope: str = "community", scope_id: str = None) -> float:
        """Get a specific observable value from current snapshot."""
        ...

    @property
    def snapshot(self) -> Optional[ObservableSnapshot]:
        """Current computed snapshot."""
        ...


class NeighborGraphProtocol(Protocol):
    """Interface for neighbor graph (for NEIGHBORS scope)."""

    def get_neighbors(self, agent_id: str) -> List[str]:
        """Return list of neighbor agent IDs."""
        ...


__all__ = [
    "ObservableScope",
    "UpdateFrequency",
    "ObservableMetric",
    "ObservableSnapshot",
    "ObservableStateProtocol",
    "NeighborGraphProtocol",
]
