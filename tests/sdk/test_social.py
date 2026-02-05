"""
Tests for social observation abstraction (Phase 6).
"""
import pytest
from cognitive_governance.v1_prototype.social.observer import SocialObserver, ObservationResult
from cognitive_governance.v1_prototype.social.registry import ObserverRegistry
from cognitive_governance.v1_prototype.social.observers import (
    FloodObserver,
    FinanceObserver,
    EducationObserver,
)


class MockAgent:
    """Mock agent for testing."""
    def __init__(self, id: str, **kwargs):
        self.id = id
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestSocialObserver:
    """Tests for SocialObserver base class."""

    def test_flood_observer_attributes(self):
        """FloodObserver returns correct attributes."""
        observer = FloodObserver()
        agent = MockAgent(
            "agent1",
            house_elevated=True,
            has_flood_insurance=True,
            flood_zone="AE",
        )

        attrs = observer.get_observable_attributes(agent)
        assert attrs["house_elevated"] is True
        assert attrs["has_flood_insurance"] is True
        assert attrs["flood_zone"] == "AE"

    def test_flood_observer_actions(self):
        """FloodObserver returns visible actions."""
        observer = FloodObserver()
        agent = MockAgent(
            "agent1",
            recently_elevated=True,
            recently_purchased_insurance=False,
        )

        actions = observer.get_visible_actions(agent)
        assert len(actions) == 1
        assert actions[0]["action"] == "elevated_house"

    def test_flood_observer_multiple_actions(self):
        """FloodObserver returns multiple visible actions."""
        observer = FloodObserver()
        agent = MockAgent(
            "agent1",
            recently_elevated=True,
            recently_purchased_insurance=True,
            recently_evacuated=True,
        )

        actions = observer.get_visible_actions(agent)
        assert len(actions) == 3
        action_types = [a["action"] for a in actions]
        assert "elevated_house" in action_types
        assert "purchased_insurance" in action_types
        assert "evacuated" in action_types

    def test_finance_observer(self):
        """FinanceObserver works correctly."""
        observer = FinanceObserver()
        agent = MockAgent(
            "agent1",
            owns_home=True,
            car_type="luxury",
            recently_bought_house=True,
        )

        attrs = observer.get_observable_attributes(agent)
        assert attrs["owns_home"] is True
        assert attrs["car_type"] == "luxury"

        actions = observer.get_visible_actions(agent)
        assert len(actions) == 1
        assert actions[0]["action"] == "bought_house"

    def test_education_observer(self):
        """EducationObserver works correctly."""
        observer = EducationObserver()
        agent = MockAgent(
            "agent1",
            enrolled_in_school=True,
            school_name="State University",
            recently_graduated=True,
        )

        attrs = observer.get_observable_attributes(agent)
        assert attrs["enrolled"] is True
        assert attrs["school_name"] == "State University"

        actions = observer.get_visible_actions(agent)
        assert len(actions) == 1
        assert actions[0]["action"] == "graduated"

    def test_observe_returns_result(self):
        """observe() returns complete ObservationResult."""
        observer = FloodObserver()
        observer_agent = MockAgent("observer1")
        observed_agent = MockAgent(
            "observed1",
            house_elevated=True,
            has_flood_insurance=False,
        )

        result = observer.observe(observer_agent, observed_agent, relationship_strength=0.8)

        assert isinstance(result, ObservationResult)
        assert result.observer_id == "observer1"
        assert result.observed_id == "observed1"
        assert result.relationship_strength == 0.8
        assert result.visible_attributes["house_elevated"] is True

    def test_observe_neighborhood(self):
        """observe_neighborhood processes multiple neighbors."""
        observer = FloodObserver()
        me = MockAgent("me")
        neighbors = [
            MockAgent("n1", house_elevated=True),
            MockAgent("n2", house_elevated=False),
            MockAgent("n3", has_flood_insurance=True),
        ]

        results = observer.observe_neighborhood(me, neighbors)
        assert len(results) == 3
        assert all(isinstance(r, ObservationResult) for r in results)

    def test_observe_neighborhood_with_relationship_map(self):
        """observe_neighborhood uses relationship map."""
        observer = FloodObserver()
        me = MockAgent("me")
        neighbors = [
            MockAgent("n1"),
            MockAgent("n2"),
        ]
        relationship_map = {"n1": 0.9, "n2": 0.3}

        results = observer.observe_neighborhood(me, neighbors, relationship_map)

        assert results[0].relationship_strength == 0.9
        assert results[1].relationship_strength == 0.3


class TestObserverRegistry:
    """Tests for ObserverRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        ObserverRegistry.clear()

    def test_register_and_get(self):
        """Can register and retrieve observers."""
        observer = FloodObserver()
        ObserverRegistry.register(observer)

        retrieved = ObserverRegistry.get("flood")
        assert retrieved is observer

    def test_list_domains(self):
        """Can list registered domains."""
        ObserverRegistry.register(FloodObserver())
        ObserverRegistry.register(FinanceObserver())

        domains = ObserverRegistry.list_domains()
        assert "flood" in domains
        assert "finance" in domains

    def test_has_domain(self):
        """has() works correctly."""
        assert not ObserverRegistry.has("flood")
        ObserverRegistry.register(FloodObserver())
        assert ObserverRegistry.has("flood")

    def test_clear(self):
        """clear() removes all observers."""
        ObserverRegistry.register(FloodObserver())
        ObserverRegistry.register(FinanceObserver())

        ObserverRegistry.clear()

        assert not ObserverRegistry.has("flood")
        assert not ObserverRegistry.has("finance")
        assert len(ObserverRegistry.list_domains()) == 0


class TestDomainProperty:
    """Test domain property on observers."""

    def test_flood_domain(self):
        assert FloodObserver().domain == "flood"

    def test_finance_domain(self):
        assert FinanceObserver().domain == "finance"

    def test_education_domain(self):
        assert EducationObserver().domain == "education"


class TestObservationResult:
    """Tests for ObservationResult dataclass."""

    def test_default_values(self):
        """ObservationResult has sensible defaults."""
        result = ObservationResult(
            observer_id="obs1",
            observed_id="target1",
        )

        assert result.observer_id == "obs1"
        assert result.observed_id == "target1"
        assert result.visible_attributes == {}
        assert result.visible_actions == []
        assert result.gossip is None
        assert result.relationship_strength == 1.0
        assert result.observation_quality == 1.0

    def test_full_result(self):
        """ObservationResult with all fields."""
        result = ObservationResult(
            observer_id="obs1",
            observed_id="target1",
            visible_attributes={"elevated": True},
            visible_actions=[{"action": "elevated", "description": "test"}],
            gossip="Did you hear about the flood?",
            relationship_strength=0.7,
            observation_quality=0.9,
        )

        assert result.visible_attributes["elevated"] is True
        assert len(result.visible_actions) == 1
        assert result.gossip is not None


class TestGossipContent:
    """Tests for gossip content retrieval."""

    def test_flood_gossip_with_experience(self):
        """FloodObserver returns gossip for flood experience."""
        observer = FloodObserver()

        class FloodExperience:
            year = 2020

        agent = MockAgent("agent1", flood_experience=FloodExperience())

        gossip = observer.get_gossip_content(agent)
        assert gossip is not None
        assert "2020" in gossip

    def test_flood_gossip_no_experience(self):
        """FloodObserver returns None without experience."""
        observer = FloodObserver()
        agent = MockAgent("agent1")

        gossip = observer.get_gossip_content(agent)
        assert gossip is None

    def test_finance_gossip_with_tip(self):
        """FinanceObserver returns financial tip."""
        observer = FinanceObserver()
        agent = MockAgent("agent1", financial_tip="Always save 20%!")

        gossip = observer.get_gossip_content(agent)
        assert gossip == "Always save 20%!"

    def test_education_gossip_with_tip(self):
        """EducationObserver returns study tip."""
        observer = EducationObserver()
        agent = MockAgent("agent1", study_tip="Review notes daily!")

        gossip = observer.get_gossip_content(agent)
        assert gossip == "Review notes daily!"
