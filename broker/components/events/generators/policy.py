"""
Policy Event Generator - Institutional decision events.

Generates events when government or insurance agents make policy changes
(subsidy rate changes, premium adjustments, etc.).
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventGeneratorProtocol,
    EventSeverity,
    EventScope,
)


@dataclass
class PolicyEventConfig:
    """Configuration for policy event generation."""
    domain: str = "policy"
    update_frequency: str = "per_step"  # After each agent step


class PolicyEventGenerator:
    """Generates policy change events from institutional decisions.

    This generator is typically triggered per_step after government
    or insurance agents make decisions. It converts their actions
    into broadcast events that household agents can observe.

    Usage:
        generator = PolicyEventGenerator()

        # After government decision
        generator.record_policy_change(
            policy_type="subsidy",
            old_value=0.50,
            new_value=0.55,
            agent_id="NJ_STATE",
            message="Subsidy increased to support flood protection",
        )

        # Generate events
        events = generator.generate(year=1, step=1)
    """

    def __init__(self, config: PolicyEventConfig = None):
        self._config = config or PolicyEventConfig()
        self._update_frequency = self._config.update_frequency
        self._pending_changes: List[Dict[str, Any]] = []

    @property
    def domain(self) -> str:
        return self._config.domain

    @property
    def update_frequency(self) -> str:
        return self._update_frequency

    def configure(self, **kwargs) -> None:
        if "update_frequency" in kwargs:
            self._update_frequency = kwargs["update_frequency"]

    def record_policy_change(
        self,
        policy_type: str,
        old_value: float,
        new_value: float,
        agent_id: str,
        message: str = "",
        year: int = 0,
    ) -> None:
        """Record a policy change to be emitted as an event.

        Args:
            policy_type: Type of policy (subsidy, premium, regulation, etc.)
            old_value: Previous value
            new_value: New value
            agent_id: Agent that made the change
            message: Optional message/rationale
            year: Year of change
        """
        self._pending_changes.append({
            "policy_type": policy_type,
            "old_value": old_value,
            "new_value": new_value,
            "agent_id": agent_id,
            "message": message,
            "year": year,
        })

    def record_subsidy_change(
        self,
        old_rate: float,
        new_rate: float,
        agent_id: str = "government",
        message: str = "",
        year: int = 0,
    ) -> None:
        """Convenience method for subsidy rate changes."""
        self.record_policy_change(
            policy_type="subsidy",
            old_value=old_rate,
            new_value=new_rate,
            agent_id=agent_id,
            message=message or self._generate_subsidy_message(old_rate, new_rate),
            year=year,
        )

    def record_premium_change(
        self,
        old_rate: float,
        new_rate: float,
        agent_id: str = "insurance",
        message: str = "",
        year: int = 0,
    ) -> None:
        """Convenience method for premium rate changes."""
        self.record_policy_change(
            policy_type="premium",
            old_value=old_rate,
            new_value=new_rate,
            agent_id=agent_id,
            message=message or self._generate_premium_message(old_rate, new_rate),
            year=year,
        )

    def clear_pending(self) -> None:
        """Clear all pending policy changes."""
        self._pending_changes.clear()

    def generate(
        self,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> List[EnvironmentEvent]:
        """Generate events from recorded policy changes.

        Returns:
            List of policy change events
        """
        events = []

        for change in self._pending_changes:
            event_type = f"{change['policy_type']}_change"
            severity = self._determine_severity(change)
            description = change.get("message") or f"{change['policy_type']} changed"

            events.append(EnvironmentEvent(
                event_type=event_type,
                severity=severity,
                scope=EventScope.GLOBAL,  # Policy changes affect all agents
                description=description,
                data={
                    "policy_type": change["policy_type"],
                    "old_value": change["old_value"],
                    "new_value": change["new_value"],
                    "change": change["new_value"] - change["old_value"],
                    "change_pct": self._calculate_change_pct(
                        change["old_value"], change["new_value"]
                    ),
                    "source_agent": change["agent_id"],
                    "year": change.get("year", year),
                },
                domain=self._config.domain,
            ))

        # Clear after generating
        self._pending_changes.clear()

        return events

    def _determine_severity(self, change: Dict[str, Any]) -> EventSeverity:
        """Determine event severity based on change magnitude."""
        old_val = change["old_value"]
        new_val = change["new_value"]

        if old_val == 0:
            return EventSeverity.MODERATE

        change_pct = abs(new_val - old_val) / abs(old_val)

        if change_pct >= 0.20:  # 20%+ change
            return EventSeverity.SEVERE
        elif change_pct >= 0.10:  # 10-20% change
            return EventSeverity.MODERATE
        elif change_pct >= 0.05:  # 5-10% change
            return EventSeverity.MINOR
        else:
            return EventSeverity.INFO

    def _calculate_change_pct(self, old_val: float, new_val: float) -> float:
        """Calculate percentage change."""
        if old_val == 0:
            return 1.0 if new_val > 0 else 0.0
        return (new_val - old_val) / abs(old_val)

    def _generate_subsidy_message(self, old_rate: float, new_rate: float) -> str:
        """Generate human-readable subsidy message."""
        if new_rate > old_rate:
            return f"Government increased flood protection subsidy from {old_rate:.0%} to {new_rate:.0%}"
        elif new_rate < old_rate:
            return f"Government reduced flood protection subsidy from {old_rate:.0%} to {new_rate:.0%}"
        else:
            return f"Government maintained subsidy at {new_rate:.0%}"

    def _generate_premium_message(self, old_rate: float, new_rate: float) -> str:
        """Generate human-readable premium message."""
        if new_rate > old_rate:
            return f"Insurance premiums increased from {old_rate:.1%} to {new_rate:.1%}"
        elif new_rate < old_rate:
            return f"Insurance premiums decreased from {old_rate:.1%} to {new_rate:.1%}"
        else:
            return f"Insurance premiums remain at {new_rate:.1%}"


__all__ = ["PolicyEventGenerator", "PolicyEventConfig"]
