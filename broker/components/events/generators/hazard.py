"""
Hazard Event Generator - Adapter for existing HazardModule.

Wraps domain-specific hazard modules (flood, earthquake, etc.) to produce
domain-agnostic EnvironmentEvents for the event framework.
"""
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass, field

from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventGeneratorProtocol,
    EventSeverity,
    EventScope,
)

if TYPE_CHECKING:
    # Avoid circular imports
    pass


@dataclass
class HazardEventConfig:
    """Configuration for hazard event generation."""
    domain: str = "flood"
    mode: str = "global"  # "global" or "per_agent"
    update_frequency: str = "per_year"
    # For global mode
    depth_threshold: float = 0.0  # Minimum depth to count as event
    # Severity thresholds (in meters for flood)
    severity_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "critical": 1.2,  # ~4 ft
        "severe": 0.6,    # ~2 ft
        "moderate": 0.3,  # ~1 ft
        "minor": 0.0,
    })


class HazardEventGenerator:
    """Generates hazard events by wrapping existing hazard modules.

    This is an adapter pattern that converts domain-specific hazard data
    (e.g., flood depth from HazardModule) into generic EnvironmentEvents.

    Supports two modes:
    - global: Single event affecting all agents (uniform depth)
    - per_agent: Individual events per agent (spatially varying depth)

    Usage:
        from examples.multi_agent.flood.environment.hazard import HazardModule

        hazard_module = HazardModule(grid_dir=Path("data/prb"))
        generator = HazardEventGenerator(
            hazard_module=hazard_module,
            config=HazardEventConfig(mode="per_agent"),
        )

        # Register with event manager
        event_manager.register("hazard", generator)
    """

    def __init__(
        self,
        hazard_module: Any = None,
        config: HazardEventConfig = None,
        get_depth_fn: Callable[[int, str], float] = None,
        agent_positions: Dict[str, tuple] = None,
    ):
        """Initialize hazard event generator.

        Args:
            hazard_module: Domain-specific hazard module (e.g., HazardModule)
            config: Configuration for event generation
            get_depth_fn: Optional custom function to get depth for agent
                          Signature: (year, agent_id) -> depth_m
            agent_positions: Dict mapping agent_id to (grid_x, grid_y)
        """
        self._hazard_module = hazard_module
        self._config = config or HazardEventConfig()
        self._get_depth_fn = get_depth_fn
        self._agent_positions = agent_positions or {}
        self._update_frequency = self._config.update_frequency

    @property
    def domain(self) -> str:
        return self._config.domain

    @property
    def update_frequency(self) -> str:
        return self._update_frequency

    def configure(self, **kwargs) -> None:
        """Configure generator parameters."""
        if "mode" in kwargs:
            self._config.mode = kwargs["mode"]
        if "update_frequency" in kwargs:
            self._update_frequency = kwargs["update_frequency"]
        if "agent_positions" in kwargs:
            self._agent_positions = kwargs["agent_positions"]
        if "depth_threshold" in kwargs:
            self._config.depth_threshold = kwargs["depth_threshold"]

    def set_agent_positions(self, positions: Dict[str, tuple]) -> None:
        """Set agent grid positions for per-agent mode."""
        self._agent_positions = positions

    def generate(
        self,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> List[EnvironmentEvent]:
        """Generate hazard events for current year.

        Args:
            year: Simulation year
            step: Step within year (unused for per_year)
            context: Optional context with agents dict

        Returns:
            List of hazard events (one global or many per-agent)
        """
        if self._config.mode == "per_agent":
            return self._generate_per_agent(year, context)
        else:
            return self._generate_global(year, context)

    def _generate_global(
        self,
        year: int,
        context: Dict[str, Any] = None
    ) -> List[EnvironmentEvent]:
        """Generate single global hazard event."""
        depth_m = self._get_global_depth(year)
        severity = self._depth_to_severity(depth_m)

        if depth_m > self._config.depth_threshold:
            return [EnvironmentEvent(
                event_type=self._config.domain,
                severity=severity,
                scope=EventScope.GLOBAL,
                description=self._get_description(severity, depth_m),
                data={
                    "depth_m": depth_m,
                    "depth_ft": depth_m * 3.28084,
                    "year": year,
                    "occurred": True,
                },
                domain=self._config.domain,
            )]
        else:
            return [EnvironmentEvent(
                event_type=f"no_{self._config.domain}",
                severity=EventSeverity.INFO,
                scope=EventScope.GLOBAL,
                description=f"No {self._config.domain} occurred this year.",
                data={
                    "depth_m": 0.0,
                    "depth_ft": 0.0,
                    "year": year,
                    "occurred": False,
                },
                domain=self._config.domain,
            )]

    def _generate_per_agent(
        self,
        year: int,
        context: Dict[str, Any] = None
    ) -> List[EnvironmentEvent]:
        """Generate per-agent hazard events with spatial variation."""
        events = []
        agents = context.get("agents", {}) if context else {}

        # Use agent_positions if set, otherwise try to extract from agents
        positions = self._agent_positions
        if not positions and agents:
            positions = self._extract_positions(agents)

        for agent_id, pos in positions.items():
            depth_m = self._get_agent_depth(year, agent_id, pos)
            severity = self._depth_to_severity(depth_m)

            if depth_m > self._config.depth_threshold:
                events.append(EnvironmentEvent(
                    event_type=self._config.domain,
                    severity=severity,
                    scope=EventScope.AGENT,
                    description=self._get_description(severity, depth_m),
                    data={
                        "depth_m": depth_m,
                        "depth_ft": depth_m * 3.28084,
                        "year": year,
                        "occurred": True,
                        "grid_x": pos[0] if pos else None,
                        "grid_y": pos[1] if pos else None,
                    },
                    affected_agents=[agent_id],
                    domain=self._config.domain,
                ))
            else:
                events.append(EnvironmentEvent(
                    event_type=f"no_{self._config.domain}",
                    severity=EventSeverity.INFO,
                    scope=EventScope.AGENT,
                    description=f"No {self._config.domain} at this location.",
                    data={
                        "depth_m": 0.0,
                        "depth_ft": 0.0,
                        "year": year,
                        "occurred": False,
                    },
                    affected_agents=[agent_id],
                    domain=self._config.domain,
                ))

        return events

    def _get_global_depth(self, year: int) -> float:
        """Get global/community-wide flood depth."""
        if self._get_depth_fn:
            return self._get_depth_fn(year, None)

        if self._hazard_module:
            # Use hazard module's get_flood_event
            event = self._hazard_module.get_flood_event(year)
            return event.depth_m

        return 0.0

    def _get_agent_depth(
        self,
        year: int,
        agent_id: str,
        pos: Optional[tuple]
    ) -> float:
        """Get flood depth for specific agent."""
        if self._get_depth_fn:
            return self._get_depth_fn(year, agent_id)

        if self._hazard_module and pos:
            grid_x, grid_y = pos
            event = self._hazard_module.get_agent_flood_event(
                sim_year=year,
                grid_x=grid_x,
                grid_y=grid_y,
                agent_id=agent_id,
            )
            return event.depth_m

        return 0.0

    def _extract_positions(self, agents: Dict) -> Dict[str, tuple]:
        """Extract grid positions from agent objects."""
        positions = {}
        for agent_id, agent in agents.items():
            if isinstance(agent, dict):
                x = agent.get("grid_x") or agent.get("grid_col", 0)
                y = agent.get("grid_y") or agent.get("grid_row", 0)
            else:
                x = getattr(agent, "grid_x", 0) or getattr(agent, "grid_col", 0)
                y = getattr(agent, "grid_y", 0) or getattr(agent, "grid_row", 0)
            positions[agent_id] = (x, y)
        return positions

    def _depth_to_severity(self, depth_m: float) -> EventSeverity:
        """Convert depth to event severity."""
        thresholds = self._config.severity_thresholds
        if depth_m >= thresholds.get("critical", 1.2):
            return EventSeverity.CRITICAL
        elif depth_m >= thresholds.get("severe", 0.6):
            return EventSeverity.SEVERE
        elif depth_m >= thresholds.get("moderate", 0.3):
            return EventSeverity.MODERATE
        elif depth_m > thresholds.get("minor", 0.0):
            return EventSeverity.MINOR
        return EventSeverity.INFO

    def _get_description(self, severity: EventSeverity, depth_m: float) -> str:
        """Generate human-readable description."""
        depth_ft = depth_m * 3.28084
        descriptions = {
            EventSeverity.CRITICAL: f"Catastrophic flooding ({depth_ft:.1f} ft) with extreme damage potential.",
            EventSeverity.SEVERE: f"Severe flooding ({depth_ft:.1f} ft) causing significant damage.",
            EventSeverity.MODERATE: f"Moderate flooding ({depth_ft:.1f} ft) with localized damage.",
            EventSeverity.MINOR: f"Minor flooding ({depth_ft:.1f} ft) with minimal impact.",
            EventSeverity.INFO: "No flooding occurred.",
        }
        return descriptions.get(severity, f"Flood event ({depth_ft:.1f} ft).")


__all__ = ["HazardEventGenerator", "HazardEventConfig"]
