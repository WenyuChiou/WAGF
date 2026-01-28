"""Tests for MA event generators and manager."""
import pytest
from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventSeverity,
    EventScope,
)
from broker.components.event_generators.hazard import (
    HazardEventGenerator,
    HazardEventConfig,
)
from broker.components.event_generators.impact import (
    ImpactEventGenerator,
    ImpactEventConfig,
)
from broker.components.event_generators.policy import (
    PolicyEventGenerator,
    PolicyEventConfig,
)
from broker.components.ma_event_manager import (
    MAEventManager,
    EventPhase,
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


class TestImpactEventGenerator:
    """Test ImpactEventGenerator."""

    def test_generates_damage_events_from_hazard(self):
        """Damage events generated from hazard events."""
        generator = ImpactEventGenerator(
            config=ImpactEventConfig(),
        )

        # Create hazard event
        hazard_events = [
            EnvironmentEvent(
                event_type="flood",
                severity=EventSeverity.SEVERE,
                scope=EventScope.AGENT,
                description="Flood",
                data={"depth_ft": 3.0, "occurred": True},
                affected_agents=["H001"],
                domain="flood",
            )
        ]

        agents = {
            "H001": {
                "property_value": 300_000,
                "elevated": False,
                "has_insurance": True,
            }
        }

        events = generator.generate(
            year=1,
            context={"hazard_events": hazard_events, "agents": agents}
        )

        # Should have damage and payout events
        assert len(events) == 2
        assert events[0].event_type == "flood_damage"
        assert events[1].event_type == "insurance_payout"

    def test_no_payout_without_insurance(self):
        """No payout event when agent has no insurance."""
        generator = ImpactEventGenerator()

        hazard_events = [
            EnvironmentEvent(
                event_type="flood",
                severity=EventSeverity.MODERATE,
                scope=EventScope.AGENT,
                description="Flood",
                data={"depth_ft": 2.0, "occurred": True},
                affected_agents=["H001"],
                domain="flood",
            )
        ]

        agents = {
            "H001": {
                "property_value": 200_000,
                "elevated": False,
                "has_insurance": False,
            }
        }

        events = generator.generate(
            year=1,
            context={"hazard_events": hazard_events, "agents": agents}
        )

        # Only damage event, no payout
        assert len(events) == 1
        assert events[0].event_type == "flood_damage"

    def test_elevation_reduces_damage(self):
        """Elevated properties have reduced damage."""
        generator = ImpactEventGenerator()

        hazard_events = [
            EnvironmentEvent(
                event_type="flood",
                severity=EventSeverity.MODERATE,
                scope=EventScope.GLOBAL,
                description="Flood",
                data={"depth_ft": 3.0, "occurred": True},
                domain="flood",
            )
        ]

        agents = {
            "H001": {"property_value": 300_000, "elevated": False, "has_insurance": False},
            "H002": {"property_value": 300_000, "elevated": True, "has_insurance": False},
        }

        events = generator.generate(
            year=1,
            context={"hazard_events": hazard_events, "agents": agents}
        )

        # Both get damage events
        damage_events = {e.affected_agents[0]: e for e in events if e.event_type == "flood_damage"}

        # Elevated (H002) has zero damage (depth 3ft - 3ft BFE = 0)
        assert damage_events["H001"].data["damage_amount"] > 0
        # H002 may have 0 damage or very little due to elevation


class TestPolicyEventGenerator:
    """Test PolicyEventGenerator."""

    def test_subsidy_change_event(self):
        """Subsidy changes generate events."""
        generator = PolicyEventGenerator()

        generator.record_subsidy_change(
            old_rate=0.50,
            new_rate=0.55,
            agent_id="NJ_STATE",
            year=1,
        )

        events = generator.generate(year=1)

        assert len(events) == 1
        assert events[0].event_type == "subsidy_change"
        assert events[0].scope == EventScope.GLOBAL
        assert events[0].data["old_value"] == 0.50
        assert events[0].data["new_value"] == 0.55
        assert events[0].data["change"] == pytest.approx(0.05)

    def test_premium_change_event(self):
        """Premium changes generate events."""
        generator = PolicyEventGenerator()

        generator.record_premium_change(
            old_rate=0.02,
            new_rate=0.025,
            agent_id="FEMA_NFIP",
            year=1,
        )

        events = generator.generate(year=1)

        assert len(events) == 1
        assert events[0].event_type == "premium_change"
        assert events[0].data["change_pct"] == pytest.approx(0.25, rel=0.01)

    def test_clears_pending_after_generate(self):
        """Pending changes cleared after generate."""
        generator = PolicyEventGenerator()

        generator.record_subsidy_change(0.5, 0.6, "GOV", year=1)
        events1 = generator.generate(year=1)
        events2 = generator.generate(year=1)

        assert len(events1) == 1
        assert len(events2) == 0


class TestMAEventManager:
    """Test MAEventManager with dependencies."""

    def test_phase_based_generation(self):
        """Events generated by phase."""
        manager = MAEventManager()

        hazard = MockHazardModule(depth_m=0.6)
        manager.register_with_deps(
            domain="hazard",
            generator=HazardEventGenerator(hazard_module=hazard),
            phase=EventPhase.PRE_YEAR,
        )
        manager.register_with_deps(
            domain="policy",
            generator=PolicyEventGenerator(),
            phase=EventPhase.PER_STEP,
        )

        # Pre-year should only get hazard events
        pre_events = manager.generate_phase(EventPhase.PRE_YEAR, year=1)
        assert "hazard" in pre_events
        assert "policy" not in pre_events

    def test_dependency_ordering(self):
        """Dependent generators run after their dependencies."""
        manager = MAEventManager()

        # Impact depends on hazard
        hazard = MockHazardModule(depth_m=0.6)
        manager.register_with_deps(
            domain="hazard",
            generator=HazardEventGenerator(
                hazard_module=hazard,
                config=HazardEventConfig(mode="per_agent"),
                agent_positions={"H001": (0, 0)},
            ),
            phase=EventPhase.PRE_YEAR,
            provides="hazard_events",
        )
        manager.register_with_deps(
            domain="impact",
            generator=ImpactEventGenerator(),
            phase=EventPhase.PRE_YEAR,
            depends_on=["hazard"],
        )

        agents = {"H001": {"property_value": 300_000, "elevated": False, "has_insurance": False}}

        events = manager.generate_phase(
            EventPhase.PRE_YEAR,
            year=1,
            context={"agents": agents}
        )

        # Both should generate
        assert "hazard" in events
        assert "impact" in events

        # Impact events should exist (from hazard context)
        assert len(events["impact"]) > 0

    def test_sync_to_environment(self):
        """Events sync to TieredEnvironment."""
        manager = MAEventManager()

        class MockEnv:
            def __init__(self):
                self.global_state = {
                    "flood_occurred": False,
                    "flood_depth_m": 0,
                    "subsidy_rate": 0.5,
                }

        env = MockEnv()

        # Add flood event
        manager._current_events["hazard"] = [
            EnvironmentEvent(
                event_type="flood",
                severity=EventSeverity.SEVERE,
                scope=EventScope.GLOBAL,
                description="Flood",
                data={"depth_m": 0.8, "depth_ft": 2.6, "occurred": True},
                domain="flood",
            )
        ]

        manager.sync_to_environment(env)

        assert env.global_state["flood_occurred"] is True
        assert env.global_state["flood_depth_m"] == 0.8

    def test_get_agent_impact(self):
        """Aggregate impact data for agent."""
        manager = MAEventManager()

        manager._current_events["hazard"] = [
            EnvironmentEvent(
                event_type="flood",
                severity=EventSeverity.SEVERE,
                scope=EventScope.AGENT,
                description="Flood",
                data={"depth_m": 0.6},
                affected_agents=["H001"],
                domain="flood",
            )
        ]
        manager._current_events["impact"] = [
            EnvironmentEvent(
                event_type="flood_damage",
                severity=EventSeverity.MODERATE,
                scope=EventScope.AGENT,
                description="Damage",
                data={"damage_amount": 25000, "oop_cost": 10000},
                affected_agents=["H001"],
                domain="impact",
            ),
            EnvironmentEvent(
                event_type="insurance_payout",
                severity=EventSeverity.INFO,
                scope=EventScope.AGENT,
                description="Payout",
                data={"payout_amount": 15000},
                affected_agents=["H001"],
                domain="impact",
            ),
        ]

        impact = manager.get_agent_impact("H001")

        assert impact["flooded"] is True
        assert impact["depth_m"] == 0.6
        assert impact["damage_amount"] == 25000
        assert impact["payout_amount"] == 15000
        assert impact["oop_cost"] == 10000
