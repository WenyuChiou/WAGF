"""
Abstract base for environment observation.

Provides a universal pattern for modeling what agents can sense
from their environment across different research domains.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class EnvironmentObservation:
    """Result of observing the environment."""

    observer_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Sensed environment state
    sensed_state: Dict[str, Any] = field(default_factory=dict)

    # Events detected (floods, price changes, etc.)
    detected_events: List[Dict[str, Any]] = field(default_factory=list)

    # Observation metadata
    location: Optional[str] = None
    observation_accuracy: float = 1.0  # 0-1: sensor accuracy

    # Domain context
    domain: str = "generic"


class EnvironmentObserver(ABC):
    """
    Abstract base for domain-specific environment observation.

    Implement this for each domain to define what agents can sense
    from their environment. This enables bounded rationality modeling
    without exposing complete environment state.

    Example:
        >>> class FloodEnvObserver(EnvironmentObserver):
        ...     @property
        ...     def domain(self) -> str:
        ...         return "flood"
        ...
        ...     def sense_state(self, agent, env):
        ...         return {"flood_level": env.get_level(agent.location)}
    """

    @property
    @abstractmethod
    def domain(self) -> str:
        """Return the domain this observer handles."""
        ...

    @abstractmethod
    def sense_state(
        self,
        agent: Any,
        environment: Any
    ) -> Dict[str, Any]:
        """
        Sense current environment state from agent's perspective.

        Should return only what the agent can realistically perceive,
        not omniscient environment state.

        Args:
            agent: The agent doing the sensing
            environment: The environment being sensed

        Returns:
            Dictionary of sensed variable names to values
        """
        ...

    @abstractmethod
    def detect_events(
        self,
        agent: Any,
        environment: Any
    ) -> List[Dict[str, Any]]:
        """
        Detect notable events in the environment.

        Events are discrete occurrences the agent would notice.

        Args:
            agent: The agent doing the sensing
            environment: The environment being sensed

        Returns:
            List of event dictionaries with keys: event_type, description, severity
        """
        ...

    def get_observation_accuracy(
        self,
        agent: Any,
        variable: str
    ) -> float:
        """
        Get accuracy of observation for a specific variable.

        Override to model sensor noise or bounded rationality.
        Default returns 1.0 (perfect observation).

        Args:
            agent: The observing agent
            variable: The variable being observed

        Returns:
            Accuracy score between 0 and 1
        """
        return 1.0

    def observe(
        self,
        agent: Any,
        environment: Any,
        location: Optional[str] = None
    ) -> EnvironmentObservation:
        """
        Perform full environment observation.

        Args:
            agent: The agent doing the sensing
            environment: The environment being sensed
            location: Optional location context

        Returns:
            EnvironmentObservation with all sensed information
        """
        agent_id = getattr(agent, "id", str(id(agent)))
        loc = location or getattr(agent, "location", None)

        sensed = self.sense_state(agent, environment)
        events = self.detect_events(agent, environment)

        # Calculate average accuracy across all sensed variables
        accuracies = [
            self.get_observation_accuracy(agent, var)
            for var in sensed.keys()
        ]
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 1.0

        return EnvironmentObservation(
            observer_id=agent_id,
            sensed_state=sensed,
            detected_events=events,
            location=loc,
            observation_accuracy=avg_accuracy,
            domain=self.domain,
        )


__all__ = [
    "EnvironmentObserver",
    "EnvironmentObservation",
]
