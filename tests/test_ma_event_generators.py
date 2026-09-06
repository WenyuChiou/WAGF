"""Tests for the hazard event generator.

Org-3 note (2026-09): this file previously also covered
ImpactEventGenerator, PolicyEventGenerator, and MAEventManager — all
deleted as dead code (reachable only via MAEventManager, which itself
had no production importer, only its own tests). Their test classes
(TestImpactEventGenerator / TestPolicyEventGenerator /
TestMAEventManager) were removed with them. TestHazardEventGenerator
below is unaffected — HazardEventGenerator itself was not deleted in
this round (out of scope; tracked separately per
broker/domains/protocol.py's own note that it has zero non-test
production callers).
"""
import pytest
from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventSeverity,
    EventScope,
)
from broker.domains.water.event_generators.hazard_per_agent import (
    HazardEventGenerator,
    HazardEventConfig,
)


class MockHazardModule:
    """Mock hazard module for testing."""

    def __init__(self, depth_m: float = 0.6):
        self.depth_m = depth_m

    def get_flood_event(self, year):
        class FloodEvent:
            def __init__(self, depth_m):
                self.depth_m = depth_m
        return FloodEvent(self.depth_m)

    def get_agent_flood_event(self, sim_year, grid_x, grid_y, agent_id, year_mapping=None):
        class FloodEvent:
            def __init__(self, depth_m):
                self.depth_m = depth_m
        # Vary depth by position
        return FloodEvent(self.depth_m + grid_x * 0.1)


class TestHazardEventGenerator:
    """Test HazardEventGenerator."""

    def test_global_mode_generates_single_event(self):
        """Global mode produces one event for all agents."""
        hazard = MockHazardModule(depth_m=0.6)
        generator = HazardEventGenerator(
            hazard_module=hazard,
            config=HazardEventConfig(mode="global"),
        )

        events = generator.generate(year=1)
        assert len(events) == 1
        assert events[0].event_type == "flood"
        assert events[0].scope == EventScope.GLOBAL
        assert events[0].data["depth_m"] == 0.6

    def test_per_agent_mode_generates_multiple_events(self):
        """Per-agent mode produces events per agent."""
        hazard = MockHazardModule(depth_m=0.3)
        generator = HazardEventGenerator(
            hazard_module=hazard,
            config=HazardEventConfig(mode="per_agent"),
            agent_positions={"H001": (0, 0), "H002": (1, 0), "H003": (2, 0)},
        )

        events = generator.generate(year=1)
        assert len(events) == 3

        # Each agent has different depth
        agent_events = {e.affected_agents[0]: e for e in events}
        assert agent_events["H001"].data["depth_m"] == 0.3  # base
        assert agent_events["H002"].data["depth_m"] == 0.4  # base + 0.1
        assert agent_events["H003"].data["depth_m"] == 0.5  # base + 0.2

    def test_no_flood_when_depth_zero(self):
        """Returns no_flood event when depth is zero."""
        hazard = MockHazardModule(depth_m=0.0)
        generator = HazardEventGenerator(
            hazard_module=hazard,
            config=HazardEventConfig(mode="global"),
        )

        events = generator.generate(year=1)
        assert len(events) == 1
        assert events[0].event_type == "no_flood"
        assert events[0].data["occurred"] is False

    def test_severity_mapping(self):
        """Depth correctly maps to severity."""
        generator = HazardEventGenerator(config=HazardEventConfig())

        assert generator._depth_to_severity(1.5) == EventSeverity.CRITICAL
        assert generator._depth_to_severity(0.8) == EventSeverity.SEVERE
        assert generator._depth_to_severity(0.4) == EventSeverity.MODERATE
        assert generator._depth_to_severity(0.1) == EventSeverity.MINOR
        assert generator._depth_to_severity(0.0) == EventSeverity.INFO
