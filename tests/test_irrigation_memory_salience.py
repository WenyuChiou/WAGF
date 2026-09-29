"""Irrigation memory salience (supply-side redesign, 2026-09-25, spec M1 to M3):
importance bands on the unmet fraction, proposed skill and fallback flag."""
import pytest

from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter


@pytest.fixture
def ad():
    return IrrigationAdapter()


@pytest.mark.parametrize("unmet,band", [
    (0.0, 0.30), (0.05, 0.45), (0.10, 0.60), (0.15, 0.60),
    (0.25, 0.75), (0.30, 0.75), (0.50, 0.90), (0.60, 0.90), (1.0, 0.90),
])
def test_outcome_importance_bands(ad, unmet, band):
    assert ad.outcome_importance(unmet) == band


def test_all_parameters_on_unit_interval(ad):
    vals = list(ad.severity_edges) + list(ad.band_importance) + [
        ad.reflection_offset, ad.reflection_cap, ad.crisis_frac,
    ] + list(ad.importance_profiles.values())
    assert all(0.0 <= v <= 1.0 for v in vals)


@pytest.mark.parametrize("unmet,expected", [
    (0.05, 0.55), (0.15, 0.70), (0.30, 0.85), (0.60, 0.95),
])
def test_reflection_importance_is_band_plus_offset_capped(ad, unmet, expected):
    ctx = {"proposed_skill": "increase_small", "was_fallback": False,
           "unmet_frac": unmet, "water_right_pct": 0.5}
    assert ad.compute_importance(ctx) == pytest.approx(expected)


def test_fallback_year_never_gets_stable_emotion(ad):
    """A rejected increase (maintain executed as fallback) with full delivery
    is not a stable year: it is scored like any other full-delivery year,
    and classified as a strategic choice, not a positive outcome."""
    rejected = {"proposed_skill": "increase_large", "recent_decision": "maintain_demand",
                "was_fallback": True, "unmet_frac": 0.0, "water_right_pct": 0.5}
    stable = {"proposed_skill": "maintain_demand", "was_fallback": False,
              "unmet_frac": 0.0, "water_right_pct": 0.5}
    assert ad.compute_importance(rejected) == pytest.approx(0.40)
    assert ad.compute_importance(stable) == pytest.approx(0.40)  # band 0.30 + 0.10, under the 0.55 ceiling
    assert ad.classify_emotion("maintain_demand", rejected) == "strategic_choice"
    assert ad.classify_emotion("maintain_demand", stable) == "positive_outcome"


def test_stable_ceiling_applies_only_to_proposed_maintain(ad):
    at_cap_stable = {"proposed_skill": "maintain_demand", "was_fallback": False,
                     "unmet_frac": 0.0, "water_right_pct": 1.0}
    at_cap_fallback = dict(at_cap_stable, was_fallback=True, proposed_skill="increase_small")
    assert ad.compute_importance(at_cap_stable) == pytest.approx(0.55)
    assert ad.compute_importance(at_cap_fallback) == pytest.approx(0.70)


def test_emotion_uses_proposed_skill_and_crisis_fraction(ad):
    assert ad.classify_emotion("maintain_demand", {"unmet_frac": 0.30}) == "water_crisis"
    assert ad.classify_emotion("maintain_demand", {"proposed_skill": "decrease_small", "unmet_frac": 0.1}) == "strategic_choice"
    assert ad.classify_emotion("maintain_demand", {"proposed_skill": "maintain_demand", "unmet_frac": 0.1}) == "baseline_observation"


def test_legacy_supply_ratio_still_accepted(ad):
    assert ad.compute_importance({"supply_ratio": 0.7, "recent_decision": "increase_small"}) == pytest.approx(0.85)


def _hooks_with_snapshot(tmp_path, action_ctx, request, diversion):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from broker.agents import AgentConfig, BaseAgent
    from examples.irrigation_abm.irrigation_env import IrrigationEnvironment, WaterSystemConfig
    from examples.irrigation_abm.irrigation_personas import IrrigationAgentProfile
    from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks

    profile = IrrigationAgentProfile(
        agent_id="A1", basin="lower_basin", cluster="aggressive",
        water_right=100_000.0,
        # WP1c review round 2 (LOW 6): "A1" is not one of the 22 real
        # Lower Basin names -- mark it, same as synthetic_no_subbasin.
        synthetic_no_priority_split=True,
    )
    env = IrrigationEnvironment(WaterSystemConfig(seed=42))
    env.initialize_from_profiles([profile])
    agent = BaseAgent(AgentConfig(name="A1", agent_type="irrigation_farmer", state_params=[],
                                  objectives=[], constraints=[], skills=[]))
    agent.custom_attributes = {}
    agent._last_action_context = action_ctx
    agent._last_year_outcome = {"year": 1, "request": request, "diversion": diversion,
                                "gap_reason": "none", "curtailment_ratio": 0.0,
                                "drought_index": 0.1, "preceding_factor": 1}
    runner = SimpleNamespace(memory_engine=MagicMock(), _current_year=2)
    hooks = IrrigationLifecycleHooks(env, runner, [profile], reflection_engine=None,
                                     output_dir=tmp_path)
    env.advance_year()
    hooks.pre_year(2, {}, {"A1": agent})
    return runner.memory_engine.add_memory_for_agent.call_args.args[2]


def test_outcome_line_metadata_is_banded_not_keyword(tmp_path):
    """M3: the yearly outcome line carries band importance from the unmet
    fraction (5 percent unmet -> 0.45, not the keyword bank's 1.0)."""
    meta = _hooks_with_snapshot(tmp_path, {"skill_name": "increase_small", "year": 1},
                                100_000.0, 95_000.0)
    assert meta == {"importance": 0.45, "emotion": "strategic_choice",
                    "source": "personal", "type": "outcome"}


def test_fallback_outcome_line_gets_same_band_as_approved(tmp_path):
    fallback = _hooks_with_snapshot(
        tmp_path, {"skill_name": "maintain_demand", "year": 1, "was_fallback": True,
                   "proposed_skill": "increase_large"}, 100_000.0, 100_000.0)
    approved = _hooks_with_snapshot(
        tmp_path, {"skill_name": "increase_large", "year": 1}, 100_000.0, 100_000.0)
    assert fallback["importance"] == approved["importance"] == 0.30
    assert fallback["emotion"] == "strategic_choice"


def test_irrigation_config_uses_composed_retrieval():
    """SI section 3.8 (2026-09-26): composed retrieval 5 recent + 2
    significant; reserve_types off for irrigation."""
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "examples/irrigation_abm/config/agent_types.yaml").read_text(encoding="utf-8"))
    mem = cfg["irrigation_farmer"]["memory"]
    assert mem["ranking_mode"] == "legacy" and mem["composed_retrieval"] is True
    assert mem["window_size"] == 5 and mem["top_k_significant"] == 2
    assert "reserve_types" not in mem
    assert cfg["global_config"]["memory"]["window_size"] == 5
    assert cfg["global_config"]["memory"]["top_k_significant"] == 2


def test_proposed_and_fallback_helper():
    from examples.irrigation_abm.run_experiment import _proposed_and_fallback
    assert _proposed_and_fallback(None) == ("", False)
    assert _proposed_and_fallback({"skill_name": "increase_small"}) == ("increase_small", False)
    assert _proposed_and_fallback({"skill_name": "maintain_demand", "was_fallback": True,
                                   "proposed_skill": None}) == ("", True)
    assert _proposed_and_fallback({"skill_name": "maintain_demand", "was_fallback": True,
                                   "proposed_skill": "increase_large"}) == ("increase_large", True)


def test_uncertain_row_agrees_between_reflection_and_outcome_line(ad):
    """An explicit empty proposal (UNCERTAIN row) is not read as the executed
    maintain_demand by either call site."""
    ctx = {"proposed_skill": "", "recent_decision": "maintain_demand", "was_fallback": False,
           "unmet_frac": 0.0, "water_right_pct": 1.0}
    assert ad.classify_emotion("maintain_demand", ctx) == "baseline_observation"
    assert ad.compute_importance(ctx) == pytest.approx(0.70)  # at_cap floor, no stable ceiling
