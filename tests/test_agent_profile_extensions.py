
from types import SimpleNamespace

from broker.modules.survey.agent_initializer import AgentProfile, AgentInitializer


def make_profile():
    return AgentProfile(
        agent_id="A001",
        record_id="R001",
        family_size=2,
        generations="1",
        income_bracket="$50,000 - $74,999",
        income_midpoint=60000,
        housing_status="mortgage",
        house_type="single_family",
        is_classified=False,
        classification_score=0,
        classification_criteria={},
        has_children=False,
        has_elderly=False,
        has_vulnerable_members=False,
    )


def test_agent_profile_has_extensions():
    profile = make_profile()
    assert isinstance(profile.extensions, dict)


def test_enrich_with_position_populates_extensions():
    profile = make_profile()
    profile.extensions = {}

    class DummySampler:
        def assign_position(self, profile):
            return SimpleNamespace(zone_name="moderate", base_depth_m=0.5, flood_probability=0.3)

    AgentInitializer().enrich_with_position([profile], DummySampler(), extension_key="flood")

    assert "flood" in profile.extensions
    flood = profile.extensions["flood"]
    assert flood.zone_name == "moderate"
    assert flood.base_depth_m == 0.5
    assert flood.flood_probability == 0.3


def test_enrich_with_values_populates_extensions():
    profile = make_profile()
    profile.extensions = {}

    class DummyRCV:
        def generate(self, **kwargs):
            return SimpleNamespace(building_rcv_usd=100.0, contents_rcv_usd=50.0)

    AgentInitializer().enrich_with_values([profile], DummyRCV(), extension_key="flood")

    assert "flood" in profile.extensions
    flood = profile.extensions["flood"]
    assert flood.building_rcv_usd == 100.0
    assert flood.contents_rcv_usd == 50.0
