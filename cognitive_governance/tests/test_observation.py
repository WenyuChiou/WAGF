"""
Tests for environment observation abstraction.
"""
import pytest
from cognitive_governance.v1_prototype.observation import (
    EnvironmentObserver,
    EnvironmentObservation,
    EnvironmentObserverRegistry,
    FloodEnvironmentObserver,
    FinanceEnvironmentObserver,
    EducationEnvironmentObserver,
)


class MockAgent:
    """Mock agent for testing."""
    def __init__(self, id: str, **kwargs):
        self.id = id
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockEnvironment:
    """Mock environment for testing."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestEnvironmentObservation:
    """Tests for EnvironmentObservation dataclass."""

    def test_default_values(self):
        """EnvironmentObservation has sensible defaults."""
        obs = EnvironmentObservation(observer_id="agent1")

        assert obs.observer_id == "agent1"
        assert obs.sensed_state == {}
        assert obs.detected_events == []
        assert obs.location is None
        assert obs.observation_accuracy == 1.0
        assert obs.domain == "generic"

    def test_full_observation(self):
        """EnvironmentObservation with all fields."""
        obs = EnvironmentObservation(
            observer_id="agent1",
            sensed_state={"flood_level": 2.5},
            detected_events=[{"event_type": "flood", "severity": "high"}],
            location="zone_A",
            observation_accuracy=0.9,
            domain="flood",
        )

        assert obs.sensed_state["flood_level"] == 2.5
        assert len(obs.detected_events) == 1
        assert obs.location == "zone_A"
        assert obs.observation_accuracy == 0.9
        assert obs.domain == "flood"


class TestFloodEnvironmentObserver:
    """Tests for FloodEnvironmentObserver."""

    def test_domain(self):
        """FloodEnvironmentObserver has correct domain."""
        observer = FloodEnvironmentObserver()
        assert observer.domain == "flood"

    def test_sense_state_basic(self):
        """FloodEnvironmentObserver senses basic state."""
        observer = FloodEnvironmentObserver()
        agent = MockAgent("agent1", location="zone_A")
        env = MockEnvironment(
            flood_level=2.5,
            flood_warning_active=True,
            days_since_flood=30,
        )

        state = observer.sense_state(agent, env)

        assert state["current_flood_level"] == 2.5
        assert state["flood_warning"] is True
        assert state["days_since_last_flood"] == 30

    def test_sense_state_with_methods(self):
        """FloodEnvironmentObserver uses environment methods."""
        observer = FloodEnvironmentObserver()
        agent = MockAgent("agent1", location="zone_A")

        class EnvWithMethods:
            def get_flood_level(self, location):
                return 3.0 if location == "zone_A" else 1.0

            def get_flood_zone(self, location):
                return "AE" if location == "zone_A" else "X"

        env = EnvWithMethods()
        state = observer.sense_state(agent, env)

        assert state["current_flood_level"] == 3.0
        assert state["flood_zone"] == "AE"

    def test_detect_events_flooding(self):
        """FloodEnvironmentObserver detects flood events."""
        observer = FloodEnvironmentObserver()
        agent = MockAgent("agent1")
        env = MockEnvironment(
            is_flooding=True,
            flood_severity="severe",
        )

        events = observer.detect_events(agent, env)

        assert len(events) == 1
        assert events[0]["event_type"] == "flood_active"
        assert "severe" in events[0]["description"]

    def test_detect_events_multiple(self):
        """FloodEnvironmentObserver detects multiple events."""
        observer = FloodEnvironmentObserver()
        agent = MockAgent("agent1")
        env = MockEnvironment(
            is_flooding=True,
            flood_severity="moderate",
            new_warning_issued=True,
            evacuation_ordered=True,
        )

        events = observer.detect_events(agent, env)

        assert len(events) == 3
        event_types = [e["event_type"] for e in events]
        assert "flood_active" in event_types
        assert "flood_warning" in event_types
        assert "evacuation_order" in event_types

    def test_observation_accuracy_base(self):
        """Base observation accuracy is 0.8."""
        observer = FloodEnvironmentObserver()
        agent = MockAgent("agent1")

        accuracy = observer.get_observation_accuracy(agent, "flood_level")
        assert accuracy == 0.8

    def test_observation_accuracy_with_insurance(self):
        """Agents with insurance have better accuracy."""
        observer = FloodEnvironmentObserver()
        agent = MockAgent("agent1", has_flood_insurance=True)

        accuracy = observer.get_observation_accuracy(agent, "flood_level")
        assert accuracy == 0.9

    def test_observe_full(self):
        """observe() returns complete EnvironmentObservation."""
        observer = FloodEnvironmentObserver()
        agent = MockAgent("agent1", location="zone_A", has_flood_insurance=True)
        env = MockEnvironment(
            flood_level=2.5,
            is_flooding=True,
            flood_severity="moderate",
        )

        obs = observer.observe(agent, env)

        assert isinstance(obs, EnvironmentObservation)
        assert obs.observer_id == "agent1"
        assert obs.sensed_state["current_flood_level"] == 2.5
        assert len(obs.detected_events) == 1
        assert obs.location == "zone_A"
        assert obs.domain == "flood"


class TestFinanceEnvironmentObserver:
    """Tests for FinanceEnvironmentObserver."""

    def test_domain(self):
        """FinanceEnvironmentObserver has correct domain."""
        observer = FinanceEnvironmentObserver()
        assert observer.domain == "finance"

    def test_sense_state(self):
        """FinanceEnvironmentObserver senses financial state."""
        observer = FinanceEnvironmentObserver()
        agent = MockAgent("agent1")
        env = MockEnvironment(
            interest_rate=0.05,
            inflation_rate=0.03,
            unemployment_rate=0.04,
            market_index=4500,
        )

        state = observer.sense_state(agent, env)

        assert state["interest_rate"] == 0.05
        assert state["inflation_rate"] == 0.03
        assert state["unemployment_rate"] == 0.04
        assert state["market_index"] == 4500

    def test_detect_events(self):
        """FinanceEnvironmentObserver detects financial events."""
        observer = FinanceEnvironmentObserver()
        agent = MockAgent("agent1")
        env = MockEnvironment(
            market_crash=True,
            in_recession=True,
        )

        events = observer.detect_events(agent, env)

        assert len(events) == 2
        event_types = [e["event_type"] for e in events]
        assert "market_crash" in event_types
        assert "recession" in event_types

    def test_accuracy_with_literacy(self):
        """Financially literate agents have better accuracy."""
        observer = FinanceEnvironmentObserver()
        agent = MockAgent("agent1", financial_literacy=0.9)

        accuracy = observer.get_observation_accuracy(agent, "interest_rate")
        assert abs(accuracy - 0.9) < 0.01  # floating point tolerance


class TestEducationEnvironmentObserver:
    """Tests for EducationEnvironmentObserver."""

    def test_domain(self):
        """EducationEnvironmentObserver has correct domain."""
        observer = EducationEnvironmentObserver()
        assert observer.domain == "education"

    def test_sense_state(self):
        """EducationEnvironmentObserver senses educational state."""
        observer = EducationEnvironmentObserver()
        agent = MockAgent("agent1")
        env = MockEnvironment(
            current_semester="Fall 2026",
            scholarship_available=True,
            graduate_employment_rate=0.85,
        )

        state = observer.sense_state(agent, env)

        assert state["current_semester"] == "Fall 2026"
        assert state["scholarship_available"] is True
        assert state["graduate_employment_rate"] == 0.85

    def test_detect_events(self):
        """EducationEnvironmentObserver detects education events."""
        observer = EducationEnvironmentObserver()
        agent = MockAgent("agent1")
        env = MockEnvironment(
            enrollment_deadline_approaching=True,
            exam_period=True,
        )

        events = observer.detect_events(agent, env)

        assert len(events) == 2
        event_types = [e["event_type"] for e in events]
        assert "enrollment_deadline" in event_types
        assert "exam_period" in event_types


class TestEnvironmentObserverRegistry:
    """Tests for EnvironmentObserverRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        EnvironmentObserverRegistry.clear()

    def test_register_and_get(self):
        """Can register and retrieve observers."""
        observer = FloodEnvironmentObserver()
        EnvironmentObserverRegistry.register(observer)

        retrieved = EnvironmentObserverRegistry.get("flood")
        assert retrieved is observer

    def test_list_domains(self):
        """Can list registered domains."""
        EnvironmentObserverRegistry.register(FloodEnvironmentObserver())
        EnvironmentObserverRegistry.register(FinanceEnvironmentObserver())

        domains = EnvironmentObserverRegistry.list_domains()
        assert "flood" in domains
        assert "finance" in domains

    def test_has_domain(self):
        """has() works correctly."""
        assert not EnvironmentObserverRegistry.has("flood")
        EnvironmentObserverRegistry.register(FloodEnvironmentObserver())
        assert EnvironmentObserverRegistry.has("flood")

    def test_clear(self):
        """clear() removes all observers."""
        EnvironmentObserverRegistry.register(FloodEnvironmentObserver())
        EnvironmentObserverRegistry.register(FinanceEnvironmentObserver())

        EnvironmentObserverRegistry.clear()

        assert not EnvironmentObserverRegistry.has("flood")
        assert not EnvironmentObserverRegistry.has("finance")
