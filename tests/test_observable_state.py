"""Tests for ObservableStateManager."""
import pytest
from broker.interfaces.observable_state import (
    ObservableMetric, ObservableScope, UpdateFrequency
)
from broker.components.observable_state import ObservableStateManager


class TestObservableStateManager:
    """Test ObservableStateManager implementation."""

    def test_register_and_compute_community_metric(self):
        """Community-scope metric computes over all agents."""
        manager = ObservableStateManager()

        def count_active(agents):
            return sum(1 for a in agents.values() if getattr(a, 'is_active', True))

        manager.register(ObservableMetric(
            name="active_count",
            compute_fn=count_active,
            scope=ObservableScope.COMMUNITY,
        ))

        agents = {"a1": type('A', (), {'is_active': True})(),
                  "a2": type('A', (), {'is_active': False})()}

        snapshot = manager.compute(agents, year=1)
        assert snapshot.community["active_count"] == 1.0

    def test_neighborhood_scope_uses_graph(self):
        """Neighborhood-scope metric uses neighbor graph."""
        manager = ObservableStateManager()

        class MockGraph:
            def get_neighbors(self, agent_id):
                return ["a2", "a3"] if agent_id == "a1" else []

        manager.set_neighbor_graph(MockGraph())

        def count_elevated(agents):
            return sum(1 for a in agents.values() if getattr(a, 'elevated', False))

        manager.register(ObservableMetric(
            name="neighbor_elevated",
            compute_fn=count_elevated,
            scope=ObservableScope.NEIGHBORS,
        ))

        agents = {
            "a1": type('A', (), {'elevated': False})(),
            "a2": type('A', (), {'elevated': True})(),
            "a3": type('A', (), {'elevated': True})(),
        }

        snapshot = manager.compute(agents, year=1)
        assert snapshot.by_neighborhood["a1"]["neighbor_elevated"] == 2.0

    def test_empty_agents_returns_zero(self):
        """Empty agent dict returns 0.0 for all metrics."""
        manager = ObservableStateManager()

        manager.register(ObservableMetric(
            name="any_metric",
            compute_fn=lambda a: len(a),
        ))

        snapshot = manager.compute({}, year=1)
        assert snapshot.community["any_metric"] == 0.0

    def test_get_from_current_snapshot(self):
        """get() returns value from current snapshot."""
        manager = ObservableStateManager()
        manager.register(ObservableMetric("test", lambda a: 42.0))
        manager.compute({"a1": {}}, year=1)

        assert manager.get("test") == 42.0
        assert manager.get("nonexistent") == 0.0

    def test_type_scope_groups_by_agent_type(self):
        """Type-scope metric computes per agent type."""
        manager = ObservableStateManager()

        def count_agents(agents):
            return len(agents)

        manager.register(ObservableMetric(
            name="type_count",
            compute_fn=count_agents,
            scope=ObservableScope.TYPE,
        ))

        agents = {
            "a1": type('A', (), {'agent_type': 'household'})(),
            "a2": type('A', (), {'agent_type': 'household'})(),
            "a3": type('A', (), {'agent_type': 'business'})(),
        }

        snapshot = manager.compute(agents, year=1)
        assert snapshot.by_type["type_count"]["household"] == 2.0
        assert snapshot.by_type["type_count"]["business"] == 1.0


class TestMetricFactories:
    """Test metric factory functions."""

    def test_flood_observables_factory(self):
        """create_flood_observables returns valid metrics."""
        from broker.components.observable_state import create_flood_observables

        metrics = create_flood_observables()
        assert len(metrics) >= 4
        assert any(m.name == "insurance_penetration_rate" for m in metrics)
        assert any(m.name == "elevation_penetration_rate" for m in metrics)

    def test_generic_rate_metric(self):
        """create_rate_metric creates valid rate computation."""
        from broker.components.observable_state import create_rate_metric

        metric = create_rate_metric(
            name="has_foo_rate",
            condition=lambda a: getattr(a, 'has_foo', False),
            description="Rate of agents with has_foo=True"
        )

        agents = {
            "a1": type('A', (), {'has_foo': True})(),
            "a2": type('A', (), {'has_foo': False})(),
        }

        rate = metric.compute_fn(agents)
        assert rate == 0.5

    def test_rate_metric_with_filter(self):
        """create_rate_metric applies filter correctly."""
        from broker.components.observable_state import create_rate_metric

        metric = create_rate_metric(
            name="active_insurance_rate",
            condition=lambda a: getattr(a, 'has_insurance', False),
            filter_fn=lambda a: not getattr(a, 'relocated', False),
        )

        agents = {
            "a1": type('A', (), {'has_insurance': True, 'relocated': False})(),
            "a2": type('A', (), {'has_insurance': False, 'relocated': False})(),
            "a3": type('A', (), {'has_insurance': True, 'relocated': True})(),  # filtered out
        }

        rate = metric.compute_fn(agents)
        assert rate == 0.5  # 1 out of 2 active agents has insurance

    def test_flood_observables_compute_correctly(self):
        """Flood observables compute correct rates."""
        from broker.components.observable_state import (
            ObservableStateManager, create_flood_observables
        )

        manager = ObservableStateManager()
        manager.register_many(create_flood_observables())

        agents = {
            "a1": type('A', (), {'has_insurance': True, 'elevated': False, 'relocated': False})(),
            "a2": type('A', (), {'has_insurance': False, 'elevated': True, 'relocated': False})(),
            "a3": type('A', (), {'has_insurance': True, 'elevated': True, 'relocated': True})(),  # relocated
        }

        snapshot = manager.compute(agents, year=1)

        # Active agents: a1, a2 (a3 is relocated)
        # Insurance: a1 has it, a2 doesn't -> 50%
        assert snapshot.community["insurance_penetration_rate"] == 0.5
        # Elevation: a2 has it, a1 doesn't -> 50%
        assert snapshot.community["elevation_penetration_rate"] == 0.5
        # Adaptation (either): both a1 and a2 have something -> 100%
        assert snapshot.community["adaptation_rate"] == 1.0
        # Relocation: 1 out of 3 -> 33.33%
        assert abs(snapshot.community["relocation_rate"] - 1/3) < 0.01
