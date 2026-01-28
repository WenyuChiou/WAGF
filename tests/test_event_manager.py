"""Tests for EnvironmentEventManager."""
import pytest
from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventSeverity,
    EventScope,
)
from broker.components.event_manager import EnvironmentEventManager
from broker.components.event_generators.flood import (
    FloodEventGenerator,
    FloodConfig,
)


class MockGenerator:
    """Mock generator for testing."""

    def __init__(self, domain: str = "mock", events: list = None, freq: str = "per_year"):
        self._domain = domain
        self._events = events or []
        self._update_frequency = freq

    @property
    def domain(self):
        return self._domain

    @property
    def update_frequency(self):
        return self._update_frequency

    def generate(self, year, step=0, context=None):
        return self._events

    def configure(self, **kwargs):
        pass


class TestEnvironmentEventManager:
    """Test EnvironmentEventManager implementation."""

    def test_register_and_generate(self):
        """Registered generators produce events."""
        manager = EnvironmentEventManager()

        events = [
            EnvironmentEvent(
                event_type="test",
                severity=EventSeverity.INFO,
                scope=EventScope.GLOBAL,
                description="Test event",
                domain="mock",
            )
        ]
        generator = MockGenerator(domain="mock", events=events)
        manager.register("mock", generator)

        result = manager.generate_all(year=1)
        assert "mock" in result
        assert len(result["mock"]) == 1
        assert result["mock"][0].event_type == "test"

    def test_per_year_only_generates_on_step_zero(self):
        """Per-year generators only run on step 0."""
        manager = EnvironmentEventManager()

        events = [
            EnvironmentEvent(
                event_type="yearly",
                severity=EventSeverity.INFO,
                scope=EventScope.GLOBAL,
                description="Yearly event",
            )
        ]
        generator = MockGenerator(events=events, freq="per_year")
        manager.register("yearly", generator)

        # Step 0: should generate
        result = manager.generate_all(year=1, step=0)
        assert "yearly" in result
        assert len(result["yearly"]) == 1

        # Clear and try step 1
        manager.clear_current()
        result = manager.generate_all(year=1, step=1)
        assert "yearly" not in result or len(result.get("yearly", [])) == 0

    def test_per_step_generates_every_step(self):
        """Per-step generators run every step."""
        manager = EnvironmentEventManager()

        events = [
            EnvironmentEvent(
                event_type="frequent",
                severity=EventSeverity.INFO,
                scope=EventScope.GLOBAL,
                description="Frequent event",
            )
        ]
        generator = MockGenerator(events=events, freq="per_step")
        manager.register("frequent", generator)

        # Step 0: should generate
        result = manager.generate_all(year=1, step=0)
        assert "frequent" in result

        # Step 1: should also generate
        result = manager.generate_all(year=1, step=1)
        assert "frequent" in result

    def test_get_events_for_agent_global(self):
        """Global events affect all agents."""
        manager = EnvironmentEventManager()

        events = [
            EnvironmentEvent(
                event_type="global",
                severity=EventSeverity.SEVERE,
                scope=EventScope.GLOBAL,
                description="Global event",
            )
        ]
        manager.register("test", MockGenerator(events=events))
        manager.generate_all(year=1)

        agent_events = manager.get_events_for_agent("H001", location="T001")
        assert len(agent_events) == 1
        assert agent_events[0].event_type == "global"

    def test_get_events_for_agent_regional(self):
        """Regional events only affect agents in that region."""
        manager = EnvironmentEventManager()

        events = [
            EnvironmentEvent(
                event_type="regional",
                severity=EventSeverity.MODERATE,
                scope=EventScope.REGIONAL,
                description="Regional event",
                location="T001",
            )
        ]
        manager.register("test", MockGenerator(events=events))
        manager.generate_all(year=1)

        # Agent in T001: affected
        agent_events = manager.get_events_for_agent("H001", location="T001")
        assert len(agent_events) == 1

        # Agent in T002: not affected
        agent_events = manager.get_events_for_agent("H002", location="T002")
        assert len(agent_events) == 0

    def test_history_accumulates(self):
        """Event history accumulates across years."""
        manager = EnvironmentEventManager()

        events = [
            EnvironmentEvent(
                event_type="yearly",
                severity=EventSeverity.INFO,
                scope=EventScope.GLOBAL,
                description="Yearly event",
            )
        ]
        manager.register("test", MockGenerator(events=events))

        manager.generate_all(year=1)
        manager.generate_all(year=2)
        manager.generate_all(year=3)

        assert len(manager.history) == 3

    def test_integration_with_flood_generator(self):
        """Integration with real FloodEventGenerator."""
        manager = EnvironmentEventManager()

        config = FloodConfig(mode="fixed", fixed_years=[1, 3])
        generator = FloodEventGenerator(config)
        manager.register("flood", generator)

        # Year 1: flood
        result = manager.generate_all(year=1)
        assert "flood" in result
        assert result["flood"][0].event_type == "flood"

        # Year 2: no flood
        result = manager.generate_all(year=2)
        assert result["flood"][0].event_type == "no_flood"

    def test_unregister_domain(self):
        """unregister removes a domain."""
        manager = EnvironmentEventManager()
        manager.register("test", MockGenerator())

        assert "test" in manager.registered_domains

        result = manager.unregister("test")
        assert result is True
        assert "test" not in manager.registered_domains

        # Unregister non-existent
        result = manager.unregister("nonexistent")
        assert result is False

    def test_generate_for_domain_on_demand(self):
        """generate_for_domain triggers specific domain."""
        manager = EnvironmentEventManager()

        events = [
            EnvironmentEvent(
                event_type="demand",
                severity=EventSeverity.INFO,
                scope=EventScope.GLOBAL,
                description="On-demand event",
            )
        ]
        generator = MockGenerator(events=events, freq="on_demand")
        manager.register("demand", generator)

        # generate_all should skip on_demand generators
        result = manager.generate_all(year=1)
        assert "demand" not in result

        # generate_for_domain triggers it
        events = manager.generate_for_domain("demand", year=1)
        assert len(events) == 1
        assert events[0].event_type == "demand"
