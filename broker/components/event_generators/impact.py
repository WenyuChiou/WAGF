"""
Impact Event Generator - Calculates financial impact from hazard events.

This generator depends on hazard events and produces damage/payout events.
It wraps existing CatastropheModule/VulnerabilityModule functionality.
"""
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass

from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventGeneratorProtocol,
    EventSeverity,
    EventScope,
)

if TYPE_CHECKING:
    pass


@dataclass
class ImpactEventConfig:
    """Configuration for impact event generation."""
    domain: str = "impact"
    update_frequency: str = "on_demand"  # Triggered after hazard events
    # NFIP-like defaults
    coverage_limit: float = 250_000
    deductible: float = 2_000
    payout_ratio: float = 1.0
    # Damage thresholds for severity
    damage_thresholds: Dict[str, float] = None

    def __post_init__(self):
        if self.damage_thresholds is None:
            self.damage_thresholds = {
                "critical": 100_000,
                "severe": 50_000,
                "moderate": 20_000,
                "minor": 5_000,
            }


class ImpactEventGenerator:
    """Generates financial impact events from hazard events.

    This generator is typically triggered on-demand after hazard events,
    calculating per-agent financial outcomes (damage, insurance payout, OOP).

    Depends on hazard events being passed in context["hazard_events"].

    Usage:
        from examples.multi_agent.environment.catastrophe import CatastropheModule

        catastrophe = CatastropheModule()
        generator = ImpactEventGenerator(
            catastrophe_module=catastrophe,
            agents=household_agents,
        )

        # Register with event manager
        event_manager.register("impact", generator)

        # Generate after hazard events
        impact_events = event_manager.generate_for_domain(
            "impact",
            year=1,
            context={"hazard_events": hazard_events, "agents": agents}
        )
    """

    def __init__(
        self,
        catastrophe_module: Any = None,
        vulnerability_module: Any = None,
        config: ImpactEventConfig = None,
        agents: Dict[str, Any] = None,
        insurance_state: Any = None,
    ):
        """Initialize impact event generator.

        Args:
            catastrophe_module: Domain-specific impact calculator
            vulnerability_module: Depth-damage curve module
            config: Configuration for event generation
            agents: Dict of agent states (agent_id -> agent)
            insurance_state: Global insurance state for payout calculation
        """
        self._catastrophe = catastrophe_module
        self._vulnerability = vulnerability_module
        self._config = config or ImpactEventConfig()
        self._agents = agents or {}
        self._insurance_state = insurance_state
        self._update_frequency = self._config.update_frequency

    @property
    def domain(self) -> str:
        return self._config.domain

    @property
    def update_frequency(self) -> str:
        return self._update_frequency

    def configure(self, **kwargs) -> None:
        """Configure generator parameters."""
        if "agents" in kwargs:
            self._agents = kwargs["agents"]
        if "insurance_state" in kwargs:
            self._insurance_state = kwargs["insurance_state"]
        if "update_frequency" in kwargs:
            self._update_frequency = kwargs["update_frequency"]

    def set_agents(self, agents: Dict[str, Any]) -> None:
        """Update agent references."""
        self._agents = agents

    def set_insurance_state(self, state: Any) -> None:
        """Update insurance state."""
        self._insurance_state = state

    def generate(
        self,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> List[EnvironmentEvent]:
        """Generate impact events from hazard events.

        Args:
            year: Simulation year
            step: Step within year
            context: Must contain "hazard_events" list

        Returns:
            List of damage and payout events
        """
        context = context or {}
        hazard_events = context.get("hazard_events", [])
        agents = context.get("agents", self._agents)

        if not hazard_events:
            return []

        events = []

        for hazard_event in hazard_events:
            # Skip non-occurring events
            if not hazard_event.data.get("occurred", False):
                continue

            # Get affected agents
            if hazard_event.scope == EventScope.GLOBAL:
                affected = list(agents.keys())
            elif hazard_event.scope == EventScope.AGENT:
                affected = hazard_event.affected_agents
            else:
                affected = []

            for agent_id in affected:
                agent = agents.get(agent_id)
                if not agent:
                    continue

                # Calculate financial impact
                depth_ft = hazard_event.data.get("depth_ft", 0.0)
                impact = self._calculate_impact(agent, depth_ft)

                if impact["damage_amount"] > 0:
                    # Damage event
                    events.append(self._create_damage_event(
                        agent_id, year, hazard_event, impact
                    ))

                    # Payout event (if insured)
                    if impact["payout_amount"] > 0:
                        events.append(self._create_payout_event(
                            agent_id, year, hazard_event, impact
                        ))

        return events

    def _calculate_impact(self, agent: Any, depth_ft: float) -> Dict[str, float]:
        """Calculate financial impact for an agent.

        Returns dict with:
        - damage_amount: Total damage in dollars
        - payout_amount: Insurance payout
        - oop_cost: Out-of-pocket cost
        - damage_ratio: Damage as fraction of property value
        """
        # Get agent properties
        if isinstance(agent, dict):
            property_value = agent.get("property_value", 300_000)
            elevated = agent.get("elevated", False)
            has_insurance = agent.get("has_insurance", False)
        else:
            property_value = getattr(agent, "property_value", 300_000)
            elevated = getattr(agent, "elevated", False)
            has_insurance = getattr(agent, "has_insurance", False)

        # Use CatastropheModule if available
        if self._catastrophe:
            return self._catastrophe.calculate_financials(
                agent_id=getattr(agent, "id", "unknown"),
                agent_state=agent,
                depth_ft=depth_ft,
                insurance_state=self._insurance_state,
            )

        # Fallback simplified calculation
        return self._simplified_impact(
            depth_ft=depth_ft,
            property_value=property_value,
            elevated=elevated,
            has_insurance=has_insurance,
        )

    def _simplified_impact(
        self,
        depth_ft: float,
        property_value: float,
        elevated: bool,
        has_insurance: bool,
    ) -> Dict[str, float]:
        """Simplified impact calculation when no module available."""
        # Simple depth-damage curve (linear approximation)
        if elevated:
            effective_depth = max(0, depth_ft - 3.0)  # BFE+1ft reduction
        else:
            effective_depth = depth_ft

        # Damage ratio (simplified)
        if effective_depth <= 0:
            damage_ratio = 0.0
        elif effective_depth >= 8:
            damage_ratio = 0.50  # 50% damage at 8+ ft
        else:
            damage_ratio = effective_depth * 0.0625  # Linear up to 50%

        damage_amount = property_value * damage_ratio

        # Insurance payout
        payout_amount = 0.0
        if has_insurance and damage_amount > 0:
            deductible = self._config.deductible
            coverage = min(damage_amount, self._config.coverage_limit)
            payout_amount = max(0, coverage - deductible) * self._config.payout_ratio

        oop_cost = damage_amount - payout_amount

        return {
            "damage_amount": damage_amount,
            "payout_amount": payout_amount,
            "oop_cost": oop_cost,
            "damage_ratio": damage_ratio,
            "effective_depth": effective_depth,
        }

    def _create_damage_event(
        self,
        agent_id: str,
        year: int,
        hazard_event: EnvironmentEvent,
        impact: Dict[str, float],
    ) -> EnvironmentEvent:
        """Create a damage event for an agent."""
        damage = impact["damage_amount"]
        severity = self._damage_to_severity(damage)

        return EnvironmentEvent(
            event_type="flood_damage",
            severity=severity,
            scope=EventScope.AGENT,
            description=f"Flood damage of ${damage:,.0f}",
            data={
                "damage_amount": damage,
                "damage_ratio": impact["damage_ratio"],
                "oop_cost": impact["oop_cost"],
                "effective_depth": impact.get("effective_depth", 0),
                "year": year,
                "source_event": hazard_event.event_type,
            },
            affected_agents=[agent_id],
            domain="impact",
        )

    def _create_payout_event(
        self,
        agent_id: str,
        year: int,
        hazard_event: EnvironmentEvent,
        impact: Dict[str, float],
    ) -> EnvironmentEvent:
        """Create an insurance payout event for an agent."""
        payout = impact["payout_amount"]

        return EnvironmentEvent(
            event_type="insurance_payout",
            severity=EventSeverity.INFO,
            scope=EventScope.AGENT,
            description=f"Insurance payout of ${payout:,.0f}",
            data={
                "payout_amount": payout,
                "damage_amount": impact["damage_amount"],
                "coverage_ratio": payout / max(impact["damage_amount"], 1),
                "year": year,
            },
            affected_agents=[agent_id],
            domain="impact",
        )

    def _damage_to_severity(self, damage: float) -> EventSeverity:
        """Convert damage amount to severity."""
        thresholds = self._config.damage_thresholds
        if damage >= thresholds.get("critical", 100_000):
            return EventSeverity.CRITICAL
        elif damage >= thresholds.get("severe", 50_000):
            return EventSeverity.SEVERE
        elif damage >= thresholds.get("moderate", 20_000):
            return EventSeverity.MODERATE
        elif damage >= thresholds.get("minor", 5_000):
            return EventSeverity.MINOR
        return EventSeverity.INFO


__all__ = ["ImpactEventGenerator", "ImpactEventConfig"]
