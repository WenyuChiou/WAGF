"""Tests for dynamic reflection importance scoring (Task-057C)."""
import pytest

from broker.components.reflection_engine import (
    ReflectionEngine,
    AgentReflectionContext,
    IMPORTANCE_PROFILES,
)


@pytest.fixture
def engine():
    return ReflectionEngine()


class TestDynamicImportance:
    def test_first_flood_highest(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", flood_count=1)
        imp = engine.compute_dynamic_importance(ctx)
        assert imp == 0.95

    def test_repeated_floods_diminish(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", flood_count=5)
        imp = engine.compute_dynamic_importance(ctx)
        assert imp == 0.75

    def test_stable_year_lowest(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", flood_count=0, recent_decision="do_nothing")
        imp = engine.compute_dynamic_importance(ctx)
        assert imp == 0.6

    def test_mg_agent_boost(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", mg_status=True)
        imp = engine.compute_dynamic_importance(ctx)
        assert imp >= 0.9

    def test_post_action_boost(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", recent_decision="elevate_house")
        imp = engine.compute_dynamic_importance(ctx)
        assert imp >= 0.8

    def test_importance_bounded(self, engine):
        ctx = AgentReflectionContext(agent_id="H1", flood_count=1, mg_status=True)
        imp = engine.compute_dynamic_importance(ctx)
        assert 0.0 <= imp <= 1.0

    def test_profiles_dict_exists(self):
        assert "first_flood" in IMPORTANCE_PROFILES
        assert "stable_year" in IMPORTANCE_PROFILES
        assert all(0.0 <= v <= 1.0 for v in IMPORTANCE_PROFILES.values())
