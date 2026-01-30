"""
Abstract base for domain-specific social observation.

Provides a universal pattern for modeling what neighbors can observe
about each other across different research domains (flood, finance,
education, health).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class ObservationResult:
    """Result of observing a neighbor."""
    observer_id: str
    observed_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Observable attributes (what can be seen)
    visible_attributes: Dict[str, Any] = field(default_factory=dict)

    # Observable actions (recent visible behavioral changes)
    visible_actions: List[Dict[str, Any]] = field(default_factory=list)

    # Gossip content (shared memory/stories)
    gossip: Optional[str] = None

    # Observation metadata
    relationship_strength: float = 1.0  # 0-1: how close are they?
    observation_quality: float = 1.0  # 0-1: how accurate is this observation?


class SocialObserver(ABC):
    """
    Abstract base for domain-specific social observation.

    Implement this for each domain to define what neighbors can see
    about each other. This enables peer influence modeling without
    exposing internal state.

    Example:
        >>> class FloodObserver(SocialObserver):
        ...     @property
        ...     def domain(self) -> str:
        ...         return "flood"
        ...
        ...     def get_observable_attributes(self, agent):
        ...         return {"house_elevated": agent.house_elevated}
    """

    @property
    @abstractmethod
    def domain(self) -> str:
        """Return the domain this observer handles (e.g., 'flood', 'finance')."""
        ...

    @abstractmethod
    def get_observable_attributes(self, agent: Any) -> Dict[str, Any]:
        """
        Return attributes that neighbors can observe.

        These should be externally visible characteristics, not internal state.
        Examples:
            - Flood: house_elevated, has_insurance (visible), NOT savings amount
            - Finance: drives_new_car, owns_home (visible), NOT exact income
            - Education: enrolled_in_school, graduated (visible), NOT GPA

        Args:
            agent: The agent being observed

        Returns:
            Dictionary of observable attribute names to values
        """
        ...

    @abstractmethod
    def get_visible_actions(self, agent: Any) -> List[Dict[str, Any]]:
        """
        Return recent visible behavioral changes.

        These are actions that neighbors would notice.
        Examples:
            - Flood: elevated_house, purchased_flood_insurance
            - Finance: bought_new_car, moved_to_new_house
            - Education: changed_schools, graduated

        Args:
            agent: The agent whose actions are observed

        Returns:
            List of action dictionaries with keys: action, description, timestamp
        """
        ...

    @abstractmethod
    def get_gossip_content(
        self,
        agent: Any,
        memory: Optional[Any] = None
    ) -> Optional[str]:
        """
        Return shareable memory content (gossip).

        This is information the agent might share in conversation.
        Should be filtered for privacy/realism.

        Args:
            agent: The agent sharing information
            memory: Optional memory system for context

        Returns:
            Gossip string or None if nothing to share
        """
        ...

    def observe(
        self,
        observer: Any,
        observed: Any,
        relationship_strength: float = 1.0
    ) -> ObservationResult:
        """
        Perform observation of one agent by another.

        Args:
            observer: The agent doing the observing
            observed: The agent being observed
            relationship_strength: How close they are (0-1)

        Returns:
            ObservationResult with all observable information
        """
        observer_id = getattr(observer, "id", str(id(observer)))
        observed_id = getattr(observed, "id", str(id(observed)))

        return ObservationResult(
            observer_id=observer_id,
            observed_id=observed_id,
            visible_attributes=self.get_observable_attributes(observed),
            visible_actions=self.get_visible_actions(observed),
            gossip=self.get_gossip_content(observed),
            relationship_strength=relationship_strength,
        )

    def observe_neighborhood(
        self,
        observer: Any,
        neighbors: List[Any],
        relationship_map: Optional[Dict[str, float]] = None
    ) -> List[ObservationResult]:
        """
        Observe all neighbors.

        Args:
            observer: The agent doing the observing
            neighbors: List of neighbor agents
            relationship_map: Optional map of neighbor_id -> relationship_strength

        Returns:
            List of ObservationResults
        """
        results = []
        for neighbor in neighbors:
            neighbor_id = getattr(neighbor, "id", str(id(neighbor)))
            strength = 1.0
            if relationship_map:
                strength = relationship_map.get(neighbor_id, 1.0)
            results.append(self.observe(observer, neighbor, strength))
        return results


__all__ = [
    "SocialObserver",
    "ObservationResult",
]
