"""
Environment Event Manager - Orchestrates multiple event generators.

Manages domain-specific event generators and distributes events to agents.
"""
from typing import Dict, List, Any, Optional
from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventGeneratorProtocol,
)


class EnvironmentEventManager:
    """Manages multiple event generators and distributes events.

    Supports registering multiple domain-specific generators (flood, market, health)
    and provides unified event generation and distribution.

    Usage:
        manager = EnvironmentEventManager()
        manager.register("flood", FloodEventGenerator())
        manager.register("market", MarketEventGenerator())

        # In simulation loop:
        events = manager.generate_all(year=1)
        agent_events = manager.get_events_for_agent("H001", location="T001")

    Attributes:
        current_events: Dict of current step's events by domain
        history: List of all historical events
    """

    def __init__(self):
        self._generators: Dict[str, EventGeneratorProtocol] = {}
        self._current_events: Dict[str, List[EnvironmentEvent]] = {}
        self._event_history: List[EnvironmentEvent] = []

    def register(self, domain: str, generator: EventGeneratorProtocol) -> None:
        """Register an event generator for a domain.

        Args:
            domain: Domain identifier (e.g., "flood", "market")
            generator: Event generator implementation
        """
        self._generators[domain] = generator

    def unregister(self, domain: str) -> bool:
        """Unregister an event generator.

        Args:
            domain: Domain to unregister

        Returns:
            True if domain was registered, False otherwise
        """
        if domain in self._generators:
            del self._generators[domain]
            return True
        return False

    def generate_all(
        self,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> Dict[str, List[EnvironmentEvent]]:
        """Generate events from all registered generators.

        Respects each generator's update_frequency:
        - "per_year": Only generates when step == 0
        - "per_step": Generates every step
        - "on_demand": Never auto-generates (call generate_for_domain instead)

        Args:
            year: Simulation year
            step: Step within year
            context: Optional global context

        Returns:
            Dict mapping domain to list of events
        """
        self._current_events = {}

        for domain, generator in self._generators.items():
            freq = generator.update_frequency
            if freq == "per_step" or (freq == "per_year" and step == 0):
                events = generator.generate(year, step, context)
                self._current_events[domain] = events
                self._event_history.extend(events)

        return self._current_events

    def generate_for_domain(
        self,
        domain: str,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> List[EnvironmentEvent]:
        """Generate events for a specific domain (on-demand).

        Args:
            domain: Domain to generate events for
            year: Simulation year
            step: Step within year
            context: Optional global context

        Returns:
            List of events generated (empty if domain not registered)
        """
        if domain not in self._generators:
            return []

        events = self._generators[domain].generate(year, step, context)
        self._current_events[domain] = events
        self._event_history.extend(events)
        return events

    def get_events_for_agent(
        self,
        agent_id: str,
        location: str = None
    ) -> List[EnvironmentEvent]:
        """Get events relevant to a specific agent.

        Filters current events by:
        - GLOBAL scope: All agents
        - REGIONAL/LOCAL scope: Agents at matching location
        - AGENT scope: Agents in affected_agents list

        Args:
            agent_id: Agent identifier
            location: Agent's location (for spatial filtering)

        Returns:
            List of events affecting this agent
        """
        relevant = []
        for events in self._current_events.values():
            for event in events:
                if event.affects_agent(agent_id, location):
                    relevant.append(event)
        return relevant

    def get_events_by_domain(self, domain: str) -> List[EnvironmentEvent]:
        """Get current events for a specific domain.

        Args:
            domain: Domain identifier

        Returns:
            List of events for that domain (empty if none)
        """
        return self._current_events.get(domain, [])

    def clear_current(self) -> None:
        """Clear current events (called at end of step if needed)."""
        self._current_events = {}

    @property
    def current_events(self) -> Dict[str, List[EnvironmentEvent]]:
        """Current step's events by domain."""
        return self._current_events.copy()

    @property
    def history(self) -> List[EnvironmentEvent]:
        """All historical events."""
        return self._event_history.copy()

    @property
    def registered_domains(self) -> List[str]:
        """List of registered domain identifiers."""
        return list(self._generators.keys())


__all__ = ["EnvironmentEventManager"]
