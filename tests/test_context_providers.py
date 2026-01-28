"""Tests for context providers."""
import pytest
from broker.components.context_providers import (
    ObservableStateProvider,
    EnvironmentEventProvider,
)
from broker.components.observable_state import (
    ObservableStateManager,
    create_flood_observables,
    create_rate_metric,
)
from broker.interfaces.observable_state import ObservableScope
from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventSeverity,
    EventScope,
)
from broker.components.event_manager import EnvironmentEventManager


class TestObservableStateProvider:
    """Test ObservableStateProvider context injection."""

    def test_provides_community_metrics(self):
        """Community metrics are injected into context."""
        manager = ObservableStateManager()
        manager.register(create_rate_metric(
            "test_rate",
            condition=lambda a: getattr(a, 'is_active', False),
        ))

        agents = {
            "a1": type('A', (), {'is_active': True})(),
            "a2": type('A', (), {'is_active': False})(),
        }
        manager.compute(agents, year=1)

        provider = ObservableStateProvider(manager)
        context = {}
        provider.provide("a1", agents, context)

        assert "observables" in context
        assert context["observables"]["test_rate"] == 0.5

    def test_provides_neighborhood_metrics(self):
        """Neighborhood metrics are prefixed with 'my_'."""
        manager = ObservableStateManager()

        class MockGraph:
            def get_neighbors(self, agent_id):
                return ["a2", "a3"] if agent_id == "a1" else []

        manager.set_neighbor_graph(MockGraph())
        manager.register(create_rate_metric(
            "neighbor_active",
            condition=lambda a: getattr(a, 'is_active', False),
            scope=ObservableScope.NEIGHBORS,
        ))

        agents = {
            "a1": type('A', (), {'is_active': False})(),
            "a2": type('A', (), {'is_active': True})(),
            "a3": type('A', (), {'is_active': True})(),
        }
        manager.compute(agents, year=1)

        provider = ObservableStateProvider(manager)
        context = {}
        provider.provide("a1", agents, context)

        assert "observables" in context
        assert context["observables"]["my_neighbor_active"] == 1.0

    def test_provides_type_metrics(self):
        """Type metrics are prefixed with 'type_'."""
        manager = ObservableStateManager()
        manager.register(create_rate_metric(
            "type_active",
            condition=lambda a: getattr(a, 'is_active', False),
            scope=ObservableScope.TYPE,
        ))

        agents = {
            "a1": type('A', (), {'agent_type': 'household', 'is_active': True})(),
            "a2": type('A', (), {'agent_type': 'household', 'is_active': False})(),
            "a3": type('A', (), {'agent_type': 'business', 'is_active': True})(),
        }
        manager.compute(agents, year=1)

        provider = ObservableStateProvider(manager)
        context = {}
        provider.provide("a1", agents, context)

        assert "observables" in context
        # Agent a1 is household, so should see household type rate (50%)
        assert context["observables"]["type_type_active"] == 0.5

    def test_no_snapshot_returns_early(self):
        """If no snapshot computed, observables not added."""
        manager = ObservableStateManager()
        manager.register(create_rate_metric("test", lambda a: True))
        # Don't compute snapshot

        provider = ObservableStateProvider(manager)
        context = {}
        provider.provide("a1", {"a1": {}}, context)

        assert "observables" not in context

    def test_integration_with_flood_observables(self):
        """Full integration with flood observable factory."""
        manager = ObservableStateManager()
        manager.register_many(create_flood_observables())

        class MockGraph:
            def get_neighbors(self, agent_id):
                return ["a2"] if agent_id == "a1" else ["a1"]

        manager.set_neighbor_graph(MockGraph())

        agents = {
            "a1": type('A', (), {
                'has_insurance': True,
                'elevated': False,
                'relocated': False,
            })(),
            "a2": type('A', (), {
                'has_insurance': False,
                'elevated': True,
                'relocated': False,
            })(),
        }
        manager.compute(agents, year=1)

        provider = ObservableStateProvider(manager)
        context = {}
        provider.provide("a1", agents, context)

        obs = context["observables"]
        assert obs["insurance_penetration_rate"] == 0.5
        assert obs["elevation_penetration_rate"] == 0.5
        assert obs["adaptation_rate"] == 1.0  # Both have some protection
        assert obs["relocation_rate"] == 0.0

        # Neighborhood: a1's neighbor is a2 (no insurance, has elevation)
        assert obs["my_neighbor_insurance_rate"] == 0.0
        assert obs["my_neighbor_elevation_rate"] == 1.0


class MockEventGenerator:
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


class TestEnvironmentEventProvider:
    """Test EnvironmentEventProvider context injection."""

    def test_provides_global_events(self):
        """Global events are injected into context."""
        manager = EnvironmentEventManager()

        events = [
            EnvironmentEvent(
                event_type="flood",
                severity=EventSeverity.SEVERE,
                scope=EventScope.GLOBAL,
                description="Severe flooding",
                data={"intensity": 0.7},
                domain="flood",
            )
        ]
        manager.register("flood", MockEventGenerator(events=events))
        manager.generate_all(year=1)

        provider = EnvironmentEventProvider(manager)
        agents = {"a1": type('A', (), {'location': 'T001'})()}
        context = {}
        provider.provide("a1", agents, context)

        assert "events" in context
        assert len(context["events"]) == 1
        assert context["events"][0]["type"] == "flood"
        assert context["events"][0]["severity"] == "severe"
        assert context["events"][0]["data"]["intensity"] == 0.7

    def test_filters_regional_events_by_location(self):
        """Regional events only affect agents in that location."""
        manager = EnvironmentEventManager()

        events = [
            EnvironmentEvent(
                event_type="regional_flood",
                severity=EventSeverity.MODERATE,
                scope=EventScope.REGIONAL,
                description="Regional flooding",
                location="T001",
                domain="flood",
            )
        ]
        manager.register("flood", MockEventGenerator(events=events))
        manager.generate_all(year=1)

        provider = EnvironmentEventProvider(manager)

        # Agent in T001 should see the event
        agents_t001 = {"a1": type('A', (), {'location': 'T001'})()}
        context_t001 = {}
        provider.provide("a1", agents_t001, context_t001)
        assert len(context_t001["events"]) == 1

        # Agent in T002 should not see the event
        agents_t002 = {"a2": type('A', (), {'location': 'T002'})()}
        context_t002 = {}
        provider.provide("a2", agents_t002, context_t002)
        assert len(context_t002["events"]) == 0

    def test_handles_dict_agents(self):
        """Works with dict-based agents."""
        manager = EnvironmentEventManager()

        events = [
            EnvironmentEvent(
                event_type="test",
                severity=EventSeverity.INFO,
                scope=EventScope.GLOBAL,
                description="Test event",
                domain="test",
            )
        ]
        manager.register("test", MockEventGenerator(events=events))
        manager.generate_all(year=1)

        provider = EnvironmentEventProvider(manager)
        agents = {"a1": {"location": "T001", "name": "Agent 1"}}
        context = {}
        provider.provide("a1", agents, context)

        assert "events" in context
        assert len(context["events"]) == 1

    def test_no_events_when_none_generated(self):
        """Empty events list when no events match."""
        manager = EnvironmentEventManager()
        manager.register("empty", MockEventGenerator(events=[]))
        manager.generate_all(year=1)

        provider = EnvironmentEventProvider(manager)
        agents = {"a1": type('A', (), {})()}
        context = {}
        provider.provide("a1", agents, context)

        assert "events" in context
        assert len(context["events"]) == 0

    def test_missing_agent_returns_early(self):
        """If agent not found, no events added."""
        manager = EnvironmentEventManager()
        events = [
            EnvironmentEvent(
                event_type="test",
                severity=EventSeverity.INFO,
                scope=EventScope.GLOBAL,
                description="Test",
                domain="test",
            )
        ]
        manager.register("test", MockEventGenerator(events=events))
        manager.generate_all(year=1)

        provider = EnvironmentEventProvider(manager)
        context = {}
        provider.provide("nonexistent", {}, context)

        assert "events" not in context
