"""Tests for event generators."""
import pytest
from broker.interfaces.event_generator import (
    EventSeverity,
    EventScope,
    EnvironmentEvent,
)
from broker.components.event_generators.flood import (
    FloodEventGenerator,
    FloodConfig,
)


class TestEnvironmentEvent:
    """Test EnvironmentEvent dataclass."""

    def test_global_scope_affects_all_agents(self):
        """Global scope events affect all agents."""
        event = EnvironmentEvent(
            event_type="flood",
            severity=EventSeverity.SEVERE,
            scope=EventScope.GLOBAL,
            description="Major flood",
        )
        assert event.affects_agent("H001")
        assert event.affects_agent("H002", "T001")

    def test_regional_scope_requires_location_match(self):
        """Regional scope events only affect agents in that region."""
        event = EnvironmentEvent(
            event_type="flood",
            severity=EventSeverity.MODERATE,
            scope=EventScope.REGIONAL,
            description="Regional flood",
            location="T001",
        )
        assert event.affects_agent("H001", "T001")
        assert not event.affects_agent("H002", "T002")
        assert not event.affects_agent("H003")  # No location

    def test_agent_scope_requires_agent_match(self):
        """Agent scope events only affect listed agents."""
        event = EnvironmentEvent(
            event_type="damage",
            severity=EventSeverity.SEVERE,
            scope=EventScope.AGENT,
            description="Direct damage",
            affected_agents=["H001", "H002"],
        )
        assert event.affects_agent("H001")
        assert event.affects_agent("H002")
        assert not event.affects_agent("H003")


class TestFloodEventGenerator:
    """Test FloodEventGenerator implementation."""

    def test_probabilistic_mode_generates_events(self):
        """Probabilistic mode generates flood or no_flood events."""
        config = FloodConfig(mode="probabilistic", probability=0.5)
        generator = FloodEventGenerator(config)

        events = generator.generate(year=1)
        assert len(events) == 1
        assert events[0].event_type in ("flood", "no_flood")
        assert events[0].domain == "flood"

    def test_fixed_mode_respects_years(self):
        """Fixed mode generates flood only in specified years."""
        config = FloodConfig(mode="fixed", fixed_years=[3, 5, 8])
        generator = FloodEventGenerator(config)

        # Year 1: no flood
        events = generator.generate(year=1)
        assert events[0].event_type == "no_flood"

        # Year 3: flood
        events = generator.generate(year=3)
        assert events[0].event_type == "flood"

        # Year 5: flood
        events = generator.generate(year=5)
        assert events[0].event_type == "flood"

    def test_historical_mode_uses_intensity_data(self):
        """Historical mode uses provided intensity values."""
        config = FloodConfig(
            mode="historical",
            historical_data={1: 0.6, 3: 0.9}
        )
        generator = FloodEventGenerator(config)

        # Year 1: flood with intensity 0.6
        events = generator.generate(year=1)
        assert events[0].event_type == "flood"
        assert events[0].data["intensity"] == 0.6

        # Year 2: no flood (not in historical data)
        events = generator.generate(year=2)
        assert events[0].event_type == "no_flood"

        # Year 3: flood with intensity 0.9
        events = generator.generate(year=3)
        assert events[0].event_type == "flood"
        assert events[0].data["intensity"] == 0.9

    def test_intensity_to_severity_mapping(self):
        """Intensity correctly maps to severity levels."""
        generator = FloodEventGenerator()

        # Test internal method
        assert generator._intensity_to_severity(0.9) == EventSeverity.CRITICAL
        assert generator._intensity_to_severity(0.7) == EventSeverity.SEVERE
        assert generator._intensity_to_severity(0.5) == EventSeverity.MODERATE
        assert generator._intensity_to_severity(0.3) == EventSeverity.MINOR

    def test_configure_updates_settings(self):
        """configure() updates generator settings."""
        generator = FloodEventGenerator()

        generator.configure(
            mode="fixed",
            fixed_years=[1, 2, 3],
            update_frequency="per_step"
        )

        assert generator._config.mode == "fixed"
        assert generator._config.fixed_years == [1, 2, 3]
        assert generator.update_frequency == "per_step"

    def test_domain_property(self):
        """domain property returns 'flood'."""
        generator = FloodEventGenerator()
        assert generator.domain == "flood"

    def test_update_frequency_default(self):
        """Default update_frequency is per_year."""
        generator = FloodEventGenerator()
        assert generator.update_frequency == "per_year"

    def test_flood_event_has_correct_scope(self):
        """Flood events have GLOBAL scope."""
        config = FloodConfig(mode="fixed", fixed_years=[1])
        generator = FloodEventGenerator(config)

        events = generator.generate(year=1)
        assert events[0].scope == EventScope.GLOBAL
