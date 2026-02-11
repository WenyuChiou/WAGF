"""Tests for ReflectionTrigger system (Task-059D)."""

from broker.components.cognitive.reflection import (
    ReflectionEngine,
    ReflectionTrigger,
    ReflectionTriggerConfig,
)


class TestReflectionTriggerEnum:
    """Verify trigger types exist."""

    def test_crisis_trigger(self):
        assert ReflectionTrigger.CRISIS.value == "crisis"

    def test_periodic_trigger(self):
        assert ReflectionTrigger.PERIODIC.value == "periodic"

    def test_decision_trigger(self):
        assert ReflectionTrigger.DECISION.value == "decision"

    def test_institutional_trigger(self):
        assert ReflectionTrigger.INSTITUTIONAL.value == "institutional"


class TestReflectionTriggerConfig:
    """Verify config defaults and loading."""

    def test_default_config(self):
        cfg = ReflectionTriggerConfig()
        assert cfg.crisis is True
        assert cfg.periodic_interval == 5
        assert cfg.decision_types == []  # domain-agnostic default
        assert cfg.institutional_threshold == 0.05

    def test_load_from_dict(self):
        d = {
            "triggers": {
                "crisis": False,
                "periodic_interval": 3,
                "decision_types": ["relocate"],
                "institutional_threshold": 0.10,
            },
            "method": "llm",
            "batch_size": 5,
        }
        cfg = ReflectionEngine.load_trigger_config(d)
        assert cfg.crisis is False
        assert cfg.periodic_interval == 3
        assert cfg.decision_types == ["relocate"]
        assert cfg.method == "llm"

    def test_load_none_returns_defaults(self):
        cfg = ReflectionEngine.load_trigger_config(None)
        assert cfg.crisis is True
        assert cfg.periodic_interval == 5


class TestShouldReflectTriggered:
    """Verify trigger logic per agent type."""

    def setup_method(self):
        self.engine = ReflectionEngine()
        self.config = ReflectionTriggerConfig()

    def test_crisis_trigger_all_types(self):
        """Crisis trigger fires for all agent types."""
        for atype in ["household", "government", "insurance"]:
            assert self.engine.should_reflect_triggered(
                "a1", atype, 3, ReflectionTrigger.CRISIS, self.config
            )

    def test_crisis_disabled(self):
        cfg = ReflectionTriggerConfig(crisis=False)
        assert not self.engine.should_reflect_triggered(
            "a1", "household", 3, ReflectionTrigger.CRISIS, cfg
        )

    def test_periodic_trigger(self):
        cfg = ReflectionTriggerConfig(periodic_interval=5)
        assert self.engine.should_reflect_triggered(
            "a1", "household", 5, ReflectionTrigger.PERIODIC, cfg
        )
        assert not self.engine.should_reflect_triggered(
            "a1", "household", 3, ReflectionTrigger.PERIODIC, cfg
        )
        assert self.engine.should_reflect_triggered(
            "a1", "household", 10, ReflectionTrigger.PERIODIC, cfg
        )

    def test_periodic_year_zero(self):
        """Year 0 should not trigger periodic reflection."""
        cfg = ReflectionTriggerConfig(periodic_interval=1)
        assert not self.engine.should_reflect_triggered(
            "a1", "household", 0, ReflectionTrigger.PERIODIC, cfg
        )

    def test_decision_trigger(self):
        flood_cfg = ReflectionTriggerConfig(
            decision_types=["elevate_house", "buyout_program", "relocate"]
        )
        ctx = {"decision": "elevate_house"}
        assert self.engine.should_reflect_triggered(
            "a1", "household", 3, ReflectionTrigger.DECISION, flood_cfg, ctx
        )

    def test_decision_trigger_not_listed(self):
        flood_cfg = ReflectionTriggerConfig(
            decision_types=["elevate_house", "buyout_program", "relocate"]
        )
        ctx = {"decision": "buy_insurance"}
        assert not self.engine.should_reflect_triggered(
            "a1", "household", 3, ReflectionTrigger.DECISION, flood_cfg, ctx
        )

    def test_institutional_trigger_government(self):
        ctx = {"policy_change_magnitude": 0.10}
        assert self.engine.should_reflect_triggered(
            "gov1", "government", 3, ReflectionTrigger.INSTITUTIONAL, self.config, ctx
        )

    def test_institutional_trigger_household_ignored(self):
        """Household agents don't respond to institutional triggers."""
        ctx = {"policy_change_magnitude": 0.50}
        assert not self.engine.should_reflect_triggered(
            "a1", "household", 3, ReflectionTrigger.INSTITUTIONAL, self.config, ctx
        )

    def test_institutional_below_threshold(self):
        ctx = {"policy_change_magnitude": 0.01}
        assert not self.engine.should_reflect_triggered(
            "gov1", "government", 3, ReflectionTrigger.INSTITUTIONAL, self.config, ctx
        )


class TestBackwardCompatibility:
    """Verify existing should_reflect() is unchanged."""

    def test_legacy_should_reflect(self):
        engine = ReflectionEngine(reflection_interval=3)
        assert engine.should_reflect("a1", 3) is True
        assert engine.should_reflect("a1", 4) is False
        assert engine.should_reflect("a1", 6) is True

    def test_legacy_should_reflect_zero_interval(self):
        engine = ReflectionEngine(reflection_interval=0)
        assert engine.should_reflect("a1", 5) is False
