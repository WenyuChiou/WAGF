"""
Event Generator Protocol - Domain-agnostic event generation.

Design Principles:
1. Domain-agnostic: Core knows nothing about flood/market/health
2. Pluggable generators: Register any event source
3. Configurable frequency: per_year, per_step, on_demand
4. Spatial awareness: Events can target specific locations
"""
from typing import Dict, Any, List, Protocol, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class EventSeverity(Enum):
    """Event severity levels."""
    INFO = "info"           # Informational only
    MINOR = "minor"         # Minor impact
    MODERATE = "moderate"   # Moderate impact
    SEVERE = "severe"       # Severe impact
    CRITICAL = "critical"   # Critical/catastrophic


class EventScope(Enum):
    """Spatial scope of event."""
    GLOBAL = "global"       # Affects all agents
    REGIONAL = "regional"   # Affects specific region/tract
    LOCAL = "local"         # Affects specific location
    AGENT = "agent"         # Affects specific agent(s)


@dataclass
class EnvironmentEvent:
    """A discrete environmental event.

    Args:
        event_type: Type identifier (e.g., "flood", "market_crash", "epidemic")
        severity: Impact level
        scope: Spatial scope
        description: Human-readable description
        data: Event-specific payload (e.g., flood_depth, price_change)
        location: Target location (if REGIONAL/LOCAL scope)
        affected_agents: Target agents (if AGENT scope)
        timestamp: When event occurred
        domain: Domain identifier
    """
    event_type: str
    severity: EventSeverity
    scope: EventScope
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    location: Optional[str] = None
    affected_agents: List[str] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    domain: str = "generic"

    def affects_agent(self, agent_id: str, agent_location: str = None) -> bool:
        """Check if this event affects a specific agent.

        Args:
            agent_id: Agent identifier
            agent_location: Agent's location (for spatial filtering)

        Returns:
            True if event affects this agent
        """
        if self.scope == EventScope.GLOBAL:
            return True
        if self.scope == EventScope.AGENT:
            return agent_id in self.affected_agents
        if self.scope in (EventScope.REGIONAL, EventScope.LOCAL):
            return agent_location == self.location
        return False


class EventGeneratorProtocol(Protocol):
    """Interface for event generators.

    Implementations generate domain-specific events.
    """

    @property
    def domain(self) -> str:
        """Domain identifier (e.g., 'flood', 'market', 'health')."""
        ...

    @property
    def update_frequency(self) -> str:
        """When to generate events: 'per_year', 'per_step', 'on_demand'."""
        ...

    def generate(
        self,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> List[EnvironmentEvent]:
        """Generate events for current time step.

        Args:
            year: Simulation year
            step: Step within year (0 if per_year)
            context: Optional global context (e.g., previous events, state)

        Returns:
            List of events generated
        """
        ...

    def configure(self, **kwargs) -> None:
        """Configure generator parameters."""
        ...


__all__ = [
    "EventSeverity",
    "EventScope",
    "EnvironmentEvent",
    "EventGeneratorProtocol",
]
