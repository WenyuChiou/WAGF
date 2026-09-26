"""Irrigation messages (supply-side redesign, 2026-09-25, spec S1 to S6): one
reason helper shared by the situation text, the rule messages and the memory
line; neutral and explicit rejection lines; realised F07 magnitude."""
from types import SimpleNamespace

import pytest

from examples.irrigation_abm.irrigation_env import IrrigationEnvironment, WaterSystemConfig
from examples.irrigation_abm.irrigation_personas import (
    build_action_outcome_feedback,
    build_water_situation_text,
    describe_gap_reason,
)
from examples.irrigation_abm.validators.irrigation_validators import (
    curtailment_awareness_check,
    supply_gap_block_increase,
)


def _ub_powell_state():
    return {"basin": "upper_basin", "year": 2022, "drought_index": 0.5, "precipitation": 50,
            "preceding_factor": 0, "natural_flow_maf": 6.0, "powell_storage_maf": 3.2,
            "current_request": 100_000.0, "current_diversion": 60_000.0, "delivery_ratio": 0.6,
            "water_right": 200_000.0, "gap_reason": "ub_powell_release",
            "curtailment_ratio": 0.0, "shortage_tier": 3}


def _lb_tier2_state():
    return {"basin": "lower_basin", "year": 2021, "drought_index": 0.5, "lake_mead_level": 1040.0,
            "preceding_factor": 0, "current_request": 100_000.0, "current_diversion": 90_000.0,
            "delivery_ratio": 0.9, "water_right": 200_000.0, "gap_reason": "lb_shortage_tier",
            "curtailment_ratio": 0.10, "shortage_tier": 2, "loop_year": 5}


def test_describe_gap_reason_codes():
    assert describe_gap_reason({"gap_reason": "none"}) == ""
    assert describe_gap_reason({}) == ""
    assert "minimum release" in describe_gap_reason({"gap_reason": "ub_powell_release"})
    assert "5.0 million acre-ft" in describe_gap_reason({"gap_reason": "ub_capacity"})
    tier = describe_gap_reason({"gap_reason": "lb_shortage_tier", "curtailment_ratio": 0.2})
    assert tier == "because the Tier 3 Lower Basin shortage reduces Lower Basin deliveries by 20%"
    both = describe_gap_reason({"gap_reason": "lb_shortage_tier+lb_mead_availability",
                                "curtailment_ratio": 0.2, "shortage_tier": 3})
    assert "Tier 3" in both and "minimum pool" in both and " and " in both


def test_ub_powell_consistent_across_situation_rule_and_memory():
    """T12 (Upper Basin under a Powell release cut): situation text, the
    supply-gap rule message and the memory line carry the same numbers and
    the same reason phrase."""
    st = _ub_powell_state()
    reason = describe_gap_reason(st)
    text = build_water_situation_text(st, last_year={"request": 100_000.0, "diversion": 60_000.0,
                                                     "gap_reason": "ub_powell_release"})
    assert "Full allocation is available" not in text
    assert "Lower Basin shortage" not in text  # tiers bind the Lower Basin only
    assert "requested 100,000 acre-ft and received 60,000 acre-ft" in text
    assert text.count(reason) == 2
    # The Lower Basin is at Tier 3 in this state; the Upper Basin agent is not
    # tier-curtailed, so the supply-gap rule must still cover it.
    msg = supply_gap_block_increase("increase_small", [], st)[0].errors[0]
    assert "60%" in msg and "40,000 AF short" in msg and reason in msg
    assert "cannot deliver more" not in msg
    mem = build_action_outcome_feedback({"skill_name": "maintain_demand"}, 2021, 100_000, 60_000,
                                        0.5, 0, basin="upper_basin", gap_reason=reason)
    assert "received 60,000 acre-ft" in mem and reason in mem


def test_lb_tier2_consistent_across_situation_and_rule():
    st = _lb_tier2_state()
    text = build_water_situation_text(st)
    reason = describe_gap_reason(st)
    assert "Tier 2 Lower Basin shortage" in text and reason in text
    assert "Full allocation is available" not in text
    msg = curtailment_awareness_check("increase_small", [], st)[0].errors[0]
    assert reason in msg and "1040 ft on 1 January" in msg


def test_full_allocation_only_when_ratio_one():
    st = dict(_lb_tier2_state(), delivery_ratio=1.0, current_diversion=100_000.0,
              gap_reason="none", curtailment_ratio=0.0, shortage_tier=0)
    text = build_water_situation_text(st)
    assert "Full allocation is available" in text
    assert "No Lower Basin shortage has been declared" in text


def test_neutral_rejection_line_names_rule_not_proposal():
    """T13."""
    ctx = {"skill_name": "maintain_demand", "was_fallback": True,
           "proposed_skill": "increase_large", "blocking_rules": ["supply_gap_block_increase"]}
    neutral = build_action_outcome_feedback(ctx, 3, 100_000, 90_000, 0.4, 0,
                                            rejection_line_style="neutral")
    assert neutral.startswith("Year 3: maintain demand was applied under the shortage-sharing rule. ")
    unmapped = dict(ctx, blocking_rules=["some_new_rule"])
    assert build_action_outcome_feedback(unmapped, 3, 100_000, 90_000, 0.4, 0,
                                         rejection_line_style="neutral").startswith(
        "Year 3: maintain demand was applied under a governance rule. ")
    assert "rejected" not in neutral and "increase large" not in neutral
    explicit = build_action_outcome_feedback(ctx, 3, 100_000, 90_000, 0.4, 0)
    assert explicit.startswith("Year 3: your proposal to increase large was rejected; "
                               "maintain demand was applied. ")


def test_f07_decrease_magnitude_is_realised_after_taper():
    """T14: near the 10 percent floor the decrease is tapered; memory reports
    the realised percentage."""
    env = IrrigationEnvironment(WaterSystemConfig(seed=1))
    env._agents["A"] = {
        "basin": "lower_basin", "diversion": 20_000.0, "request": 20_000.0,
        "water_right": 100_000.0, "curtailment_ratio": 0.0, "delivery_ratio": 1.0,
        "gap_reason": "none", "at_allocation_cap": False, "has_efficient_system": False,
        "below_minimum_utilisation": False, "cluster": "aggressive", "persona_scale": 1.0,
        "skill_magnitude": {"decrease_large": {"mu": 13.0, "sigma": 0.0, "min": 8.0, "max": 20.0}},
        "exploration_rate": 0.0,
    }
    res = env.execute_skill(SimpleNamespace(skill_name="decrease_large", agent_id="A", parameters={}))
    new_req = env._agents["A"]["request"]
    realised = 100.0 * (20_000.0 - new_req) / 20_000.0
    assert res.action_context["magnitude_pct"] == pytest.approx(realised)
    assert realised < 13.0
    assert res.state_changes["magnitude_pct_sampled"] == pytest.approx(13.0)
    mem = build_action_outcome_feedback(res.action_context | {"skill_name": "decrease_large"},
                                        1, new_req, new_req, 0.1, 0)
    assert f"(by {realised:.0f}%)" in mem


def test_option_descriptions_have_no_yield():
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "examples/irrigation_abm/config/agent_types.yaml").read_text(encoding="utf-8"))
    for action in cfg["irrigation_farmer"]["actions"]:
        d = action["description"].lower()
        assert "yield" not in d and "crop" not in d and "curtailment risk" not in d
    assert cfg["irrigation_farmer"]["memory"]["rejection_line_style"] == "neutral"


def test_dashboard_situation_and_memory_state_the_same_numbers(tmp_path):
    """T12 end to end for a Lower Basin agent at Tier 3: the dashboard WARNING
    (recorded in post_year from the settlement), the next year's "Last year"
    situation sentence and the memory line carry the same request and
    delivery, and the situation text and memory line the same reason."""
    from unittest.mock import MagicMock

    from broker.agents import AgentConfig, BaseAgent
    from broker.components.analytics.feedback import AgentMetricsTracker, FeedbackDashboardProvider
    from broker.interfaces.skill_types import ApprovedSkill
    from examples.irrigation_abm.irrigation_personas import IrrigationAgentProfile
    from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks
    import yaml
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "examples/irrigation_abm/config/agent_types.yaml").read_text(encoding="utf-8"))
    fb_cfg = cfg["irrigation_farmer"]["feedback"]

    profile = IrrigationAgentProfile(agent_id="LB1", basin="lower_basin", cluster="aggressive",
                                     water_right=200_000.0)
    env = IrrigationEnvironment(WaterSystemConfig(seed=42))
    env.initialize_from_profiles([profile])
    env._mead_storage = [7.0]  # about 1,012 ft on 1 January -> Tier 3
    agent = BaseAgent(AgentConfig(name="LB1", agent_type="irrigation_farmer", state_params=[],
                                  objectives=[], constraints=[], skills=[]))
    agent.custom_attributes = {}
    runner = SimpleNamespace(memory_engine=MagicMock(), _current_year=1)
    runner.memory_engine.retrieve.return_value = []
    hooks = IrrigationLifecycleHooks(env, runner, [profile], reflection_engine=None, output_dir=tmp_path)
    tracker = AgentMetricsTracker([m["name"] for m in fb_cfg["tracked_metrics"]], window=5)
    hooks.metrics_tracker, hooks.feedback_config = tracker, fb_cfg

    env.advance_year()
    hooks.pre_year(1, {}, {"LB1": agent})
    skill = ApprovedSkill(skill_name="maintain_demand", agent_id="LB1", approval_status="APPROVED",
                          execution_mapping="env.execute_skill")
    skill.parameters = {}
    res = env.execute_skill(skill)
    agent._last_action_context = {"skill_name": "maintain_demand", "year": 1}
    hooks.post_step(agent, SimpleNamespace(approved_skill=skill, execution_result=res, skill_proposal=None))
    hooks.post_year(1, {"LB1": agent})
    req, got = hooks.logs[-1]["request"], hooks.logs[-1]["diversion"]
    assert got / req == pytest.approx(0.80)

    ctx = {}
    FeedbackDashboardProvider(tracker, fb_cfg).provide("LB1", {}, ctx, env_context={})
    dash = ctx["feedback_dashboard"]
    assert f"You requested {req:,.0f} AF and received {got:,.0f} AF" in dash
    assert "The reason is stated in your water situation above" in dash

    runner._current_year = 2
    env.advance_year()
    hooks.pre_year(2, {}, {"LB1": agent})
    reason = describe_gap_reason({"gap_reason": "lb_shortage_tier", "curtailment_ratio": 0.20})
    assert f"Last year you requested {req:,.0f} acre-ft and received {got:,.0f} acre-ft" in agent.water_situation_text
    assert reason in agent.water_situation_text
    mem = runner.memory_engine.add_memory_for_agent.call_args.args[1]
    assert f"received {got:,.0f} acre-ft" in mem and reason in mem


def test_dashboard_message_true_for_tier_only_year():
    """The F13 text must hold in a tier-only year (ratio 0.80, no physical
    limit), where a larger request is cut by the same share, not taken from
    other users."""
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "examples/irrigation_abm/config/agent_types.yaml").read_text(encoding="utf-8"))
    msg = cfg["irrigation_farmer"]["feedback"]["assertions"][0]["message"]
    assert "A declared shortage reduces any larger request by the same share" in msg
    assert "when a physical limit binds" in msg
    assert "raises your share only by lowering" in msg


@pytest.mark.parametrize("code,needle", [
    ("ub_capacity", "5.0 million acre-ft delivery capacity"),
    ("lb_mead_availability", "without falling below its minimum pool"),
    ("lb_shortage_tier+lb_mead_availability", "Tier 3 Lower Basin shortage"),
])
def test_situation_text_carries_each_reason(code, needle):
    st = dict(_lb_tier2_state(), gap_reason=code, curtailment_ratio=0.20, shortage_tier=3,
              delivery_ratio=0.7, current_diversion=70_000.0)
    if code == "ub_capacity":
        st.update(basin="upper_basin", curtailment_ratio=0.0, natural_flow_maf=12.0,
                  powell_storage_maf=12.0)
    text = build_water_situation_text(st)
    assert needle in text
    assert "Full allocation is available" not in text


def test_year_one_has_no_last_year_sentence():
    text = build_water_situation_text(_lb_tier2_state(), last_year=None)
    assert "Last year you requested" not in text


def test_new_message_text_has_no_em_dash():
    st = _ub_powell_state()
    texts = [build_water_situation_text(st, last_year={"request": 1.0, "diversion": 0.5,
                                                       "gap_reason": "ub_powell_release"}),
             supply_gap_block_increase("increase_small", [], st)[0].errors[0],
             curtailment_awareness_check("increase_small", [], _lb_tier2_state())[0].errors[0]]
    for code in ("ub_capacity", "ub_powell_release", "lb_shortage_tier", "lb_mead_availability"):
        texts.append(describe_gap_reason({"gap_reason": code, "curtailment_ratio": 0.1}))
    assert not any("\u2014" in t for t in texts)


def test_smoke_check_j_uses_sampled_magnitude():
    import pandas as pd
    from examples.irrigation_abm.validate_smoke import check_j_magnitude_bounds
    sim = pd.DataFrame([{"yearly_decision": "decrease_large", "magnitude_pct": 5.78,
                         "magnitude_pct_sampled": 13.0, "is_exploration": False}])
    ok, _ = check_j_magnitude_bounds(sim)
    assert ok


def test_zero_delivery_message_does_not_claim_sharing():
    st = dict(_ub_powell_state(), current_diversion=0.0, delivery_ratio=0.0)
    msg = supply_gap_block_increase("increase_small", [], st)[0].errors[0]
    assert "no delivery is expected" in msg and "other users" not in msg
