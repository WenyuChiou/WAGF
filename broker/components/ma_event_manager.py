"""
Multi-Agent Event Manager - Orchestrates events with dependencies.

Extends EnvironmentEventManager to handle:
1. Event dependencies (impact events depend on hazard events)
2. Phase-based generation (pre_year, per_step, post_year)
3. TieredEnvironment synchronization
"""
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from broker.interfaces.event_generator import EnvironmentEvent, EventScope
from broker.components.event_manager import EnvironmentEventManager


class EventPhase(Enum):
    """When events should be generated in simulation cycle."""
    PRE_YEAR = "pre_year"      # At start of year (hazard determination)
    PER_STEP = "per_step"      # After each agent step (policy changes)
    POST_YEAR = "post_year"    # At end of year (damage calculation)
    ON_DEMAND = "on_demand"    # Manually triggered


@dataclass
class GeneratorSpec:
    """Specification for a registered generator."""
    domain: str
    generator: Any
    phase: EventPhase = EventPhase.PRE_YEAR
    depends_on: List[str] = field(default_factory=list)
    provides: str = ""  # What context key this generator provides

    def __post_init__(self):
        if not self.provides:
            self.provides = f"{self.domain}_events"


class MAEventManager(EnvironmentEventManager):
    """Event manager for multi-agent simulations with dependencies.

    Features:
    - Phase-based event generation (pre_year, per_step, post_year)
    - Dependency resolution between generators
    - TieredEnvironment synchronization
    - Per-agent event filtering

    Usage:
        manager = MAEventManager()

        # Register with dependencies
        manager.register_with_deps(
            domain="hazard",
            generator=HazardEventGenerator(...),
            phase=EventPhase.PRE_YEAR,
        )
        manager.register_with_deps(
            domain="impact",
            generator=ImpactEventGenerator(...),
            phase=EventPhase.POST_YEAR,
            depends_on=["hazard"],  # Needs hazard events first
        )
        manager.register_with_deps(
            domain="policy",
            generator=PolicyEventGenerator(...),
            phase=EventPhase.PER_STEP,
        )

        # Generate by phase
        manager.generate_phase(EventPhase.PRE_YEAR, year=1, context={...})
        # ... agent decisions happen ...
        manager.generate_phase(EventPhase.POST_YEAR, year=1, context={...})
    """

    def __init__(self):
        super().__init__()
        self._specs: Dict[str, GeneratorSpec] = {}
        self._phase_order: Dict[EventPhase, List[str]] = {
            phase: [] for phase in EventPhase
        }
        self._event_context: Dict[str, List[EnvironmentEvent]] = {}

    def register_with_deps(
        self,
        domain: str,
        generator: Any,
        phase: EventPhase = EventPhase.PRE_YEAR,
        depends_on: List[str] = None,
        provides: str = None,
    ) -> None:
        """Register a generator with phase and dependency info.

        Args:
            domain: Domain identifier
            generator: Event generator instance
            phase: When to generate events
            depends_on: List of domains this depends on
            provides: Context key for generated events
        """
        spec = GeneratorSpec(
            domain=domain,
            generator=generator,
            phase=phase,
            depends_on=depends_on or [],
            provides=provides or f"{domain}_events",
        )
        self._specs[domain] = spec
        self._generators[domain] = generator

        # Add to phase order (respecting dependencies)
        self._update_phase_order(domain, phase)

    def _update_phase_order(self, domain: str, phase: EventPhase) -> None:
        """Update phase order with topological sort for dependencies."""
        if domain not in self._phase_order[phase]:
            self._phase_order[phase].append(domain)

        # Re-sort based on dependencies
        order = self._phase_order[phase]
        sorted_order = self._topological_sort(order, phase)
        self._phase_order[phase] = sorted_order

    def _topological_sort(
        self,
        domains: List[str],
        phase: EventPhase
    ) -> List[str]:
        """Sort domains by dependencies within a phase."""
        # Build dependency graph for this phase
        in_phase = set(domains)
        graph: Dict[str, Set[str]] = {d: set() for d in domains}

        for domain in domains:
            spec = self._specs.get(domain)
            if spec:
                for dep in spec.depends_on:
                    if dep in in_phase:
                        graph[domain].add(dep)

        # Kahn's algorithm
        in_degree = {d: len(graph[d]) for d in domains}
        queue = [d for d in domains if in_degree[d] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for d in domains:
                if node in graph[d]:
                    graph[d].remove(node)
                    in_degree[d] -= 1
                    if in_degree[d] == 0:
                        queue.append(d)

        # If not all nodes processed, there's a cycle
        if len(result) != len(domains):
            # Fall back to original order
            return domains

        return result

    def generate_phase(
        self,
        phase: EventPhase,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> Dict[str, List[EnvironmentEvent]]:
        """Generate all events for a specific phase.

        Args:
            phase: Which phase to generate
            year: Simulation year
            step: Step within year (for PER_STEP)
            context: Shared context (agents, environment, etc.)

        Returns:
            Dict mapping domain to events
        """
        context = context or {}
        phase_events = {}

        # Add previously generated events to context
        context.update(self._event_context)

        for domain in self._phase_order[phase]:
            spec = self._specs.get(domain)
            if not spec:
                continue

            generator = spec.generator

            # Add dependency events to context
            for dep in spec.depends_on:
                dep_spec = self._specs.get(dep)
                if dep_spec:
                    provides_key = dep_spec.provides
                    if provides_key in self._event_context:
                        context[provides_key] = self._event_context[provides_key]

            # Generate events
            events = generator.generate(year, step, context)
            phase_events[domain] = events
            self._current_events[domain] = events
            self._event_history.extend(events)

            # Store for dependent generators
            self._event_context[spec.provides] = events

        return phase_events

    def generate_all(
        self,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> Dict[str, List[EnvironmentEvent]]:
        """Generate events for appropriate phase based on step.

        For step=0: PRE_YEAR phase
        For step>0: PER_STEP phase
        """
        if step == 0:
            return self.generate_phase(EventPhase.PRE_YEAR, year, step, context)
        else:
            return self.generate_phase(EventPhase.PER_STEP, year, step, context)

    def generate_post_year(
        self,
        year: int,
        context: Dict[str, Any] = None
    ) -> Dict[str, List[EnvironmentEvent]]:
        """Generate POST_YEAR phase events."""
        return self.generate_phase(EventPhase.POST_YEAR, year, 0, context)

    def clear_year(self) -> None:
        """Clear event context at end of year."""
        self._event_context.clear()
        self._current_events.clear()

    def sync_to_environment(
        self,
        env: Any,
        domains: List[str] = None
    ) -> None:
        """Sync event data to TieredEnvironment.

        Updates env.global_state with event summaries:
        - flood_occurred: bool
        - flood_depth_m: float
        - subsidy_rate: float
        - premium_rate: float
        - etc.

        Args:
            env: TieredEnvironment instance
            domains: Domains to sync (default: all)
        """
        if not hasattr(env, "global_state"):
            return

        domains = domains or list(self._current_events.keys())

        for domain, events in self._current_events.items():
            if domains and domain not in domains:
                continue

            for event in events:
                self._sync_event_to_env(env, event)

    def _sync_event_to_env(self, env: Any, event: EnvironmentEvent) -> None:
        """Sync a single event to environment state."""
        gs = env.global_state

        if event.event_type == "flood":
            gs["flood_occurred"] = event.data.get("occurred", True)
            gs["flood_depth_m"] = event.data.get("depth_m", 0)
            gs["flood_depth_ft"] = event.data.get("depth_ft", 0)
        elif event.event_type == "no_flood":
            gs["flood_occurred"] = False
            gs["flood_depth_m"] = 0
            gs["flood_depth_ft"] = 0
        elif event.event_type == "subsidy_change":
            gs["subsidy_rate"] = event.data.get("new_value", gs.get("subsidy_rate", 0.5))
            gs["govt_message"] = event.description
        elif event.event_type == "premium_change":
            gs["premium_rate"] = event.data.get("new_value", gs.get("premium_rate", 0.02))
            gs["insurance_message"] = event.description

    def get_events_by_type(
        self,
        event_type: str,
        domain: str = None
    ) -> List[EnvironmentEvent]:
        """Get all events of a specific type."""
        events = []
        sources = [domain] if domain else list(self._current_events.keys())

        for d in sources:
            for event in self._current_events.get(d, []):
                if event.event_type == event_type:
                    events.append(event)

        return events

    def get_agent_impact(self, agent_id: str) -> Dict[str, Any]:
        """Get aggregated impact data for an agent."""
        impact = {
            "flooded": False,
            "depth_m": 0.0,
            "damage_amount": 0.0,
            "payout_amount": 0.0,
            "oop_cost": 0.0,
        }

        for domain, events in self._current_events.items():
            for event in events:
                if not event.affects_agent(agent_id):
                    continue

                if event.event_type == "flood":
                    impact["flooded"] = True
                    impact["depth_m"] = max(
                        impact["depth_m"],
                        event.data.get("depth_m", 0)
                    )
                elif event.event_type == "flood_damage":
                    impact["damage_amount"] += event.data.get("damage_amount", 0)
                    impact["oop_cost"] += event.data.get("oop_cost", 0)
                elif event.event_type == "insurance_payout":
                    impact["payout_amount"] += event.data.get("payout_amount", 0)

        return impact


__all__ = ["MAEventManager", "EventPhase", "GeneratorSpec"]
