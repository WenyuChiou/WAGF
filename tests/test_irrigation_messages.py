"""Irrigation messages (supply-side redesign, 2026-09-25, spec S1 to S6): one
reason helper shared by the situation text, the rule messages and the memory
line; neutral and explicit rejection lines; realised F07 magnitude."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.irrigation_abm.irrigation_env import IrrigationEnvironment, WaterSystemConfig
from examples.irrigation_abm.irrigation_personas import (
    build_action_outcome_feedback,
    build_water_situation_text,
    describe_gap_reason,
)
from examples.irrigation_abm.validators.irrigation_validators import (
    _sharing_sentence,
    curtailment_awareness_check,
    supply_gap_block_increase,
)

CRSS_PARAMS_CSV = Path("ref/RL-ABM-CRSS/ALL_colorado_ABM_params_cal_1108.csv")
CRSS_DB_DIR = Path("ref/CRSS_DB/CRSS_DB")
_REAL_REF_AVAILABLE = CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir()


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
            "curtailment_ratio": 0.10, "shortage_tier": 2, "lb_shortage_volume_maf": 0.417,
            "loop_year": 5}


def test_describe_gap_reason_codes():
    assert describe_gap_reason({"gap_reason": "none"}) == ""
    assert describe_gap_reason({}) == ""
    assert "minimum release" in describe_gap_reason({"gap_reason": "ub_powell_release"})
    assert "5.0 million acre-ft" in describe_gap_reason({"gap_reason": "ub_capacity"})
    assert "natural flow" in describe_gap_reason({"gap_reason": "ub_natural_flow"})
    # PI decision 2026-09-28: the declared tier's shortage volume is borne
    # entirely by the Lower Basin non-agricultural bucket, never by an
    # agricultural agent's own delivery, so "lb_shortage_tier" is no
    # longer a real per-agent gap reason -- describe_gap_reason silently
    # contributes nothing for it (not a guessed phrase).
    assert describe_gap_reason({"gap_reason": "lb_shortage_tier", "curtailment_ratio": 0.2}) == ""
    combined = describe_gap_reason({"gap_reason": "lb_shortage_tier+lb_mead_availability",
                                    "curtailment_ratio": 0.2, "shortage_tier": 3})
    # Only the physical lb_mead_availability half is real now; the tier
    # half contributes nothing, so this reduces to that single phrase
    # (no "and", no injected "Tier 3").
    assert "minimum pool" in combined
    assert "Tier 3" not in combined
    assert " and " not in combined


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
    # PI decision 2026-09-28: this fixture's gap_reason ("lb_shortage_tier")
    # is a declared-tier-only state with no physical Mead shortfall, so it
    # no longer reduces this agent's own delivery -- describe_gap_reason
    # correctly has nothing to name (reason == ""), unlike the pre-PI
    # behaviour this test used to check ("reason in text" would otherwise
    # pass vacuously for any text once reason is empty).
    assert reason == ""
    assert "Tier 2 Lower Basin shortage" in text
    # Re-review 2026-09-29 (HIGH 2): the declared tier cuts the
    # non-agricultural bucket by an acre-feet volume, never "Lower Basin
    # deliveries" as a flat percentage of this (agricultural) agent's own
    # delivery.
    assert "deliveries are reduced by" not in text
    assert "417,000 acre-ft" in text
    assert "Full allocation is available" not in text
    msg = curtailment_awareness_check("increase_small", [], st)[0].errors[0]
    assert "Tier 2 Lower Basin shortage has been declared" in msg
    assert "1040 ft on 1 January" in msg


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


def test_f07_decrease_magnitude_is_realised_at_the_floor():
    """T14 (Hung and Yang action model, 2026-09-26): a decrease that would
    go below the 10 percent floor is cut at the floor; memory reports the
    realised percentage, and magnitude_pct_sampled the drawn step."""
    env = IrrigationEnvironment(WaterSystemConfig(seed=1))
    env._agents["A"] = {
        "basin": "lower_basin", "diversion": 12_000.0, "request": 12_000.0,
        "water_right": 100_000.0, "curtailment_ratio": 0.0, "delivery_ratio": 1.0,
        "gap_reason": "none", "at_allocation_cap": False, "has_efficient_system": False,
        "below_minimum_utilisation": False, "cluster": "aggressive",
        "mu": 1.0, "sigma": 0.5, "bin_size_af": 4_000.0,
    }
    res = env.execute_skill(SimpleNamespace(skill_name="decrease_large", agent_id="A", parameters={}))
    new_req = env._agents["A"]["request"]
    assert new_req == pytest.approx(10_000.0)
    realised = 100.0 * (12_000.0 - new_req) / 12_000.0
    assert res.action_context["magnitude_pct"] == pytest.approx(realised)
    assert res.state_changes["magnitude_af"] == pytest.approx(2_000.0)
    assert res.state_changes["magnitude_pct_sampled"] > realised
    mem = build_action_outcome_feedback(res.action_context | {"skill_name": "decrease_large"},
                                        1, new_req, new_req, 0.1, 0)
    assert f"(by {realised:.0f}%)" in mem


def test_option_descriptions_have_no_yield():
    """Both sources of option text: agent_types.yaml actions and the skill
    registry descriptions (the registry text is what options_text renders
    into the prompt). No yield, crops, curtailment risk or percentages."""
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "examples/irrigation_abm/config/agent_types.yaml").read_text(encoding="utf-8"))
    reg = yaml.safe_load((root / "examples/irrigation_abm/config/skill_registry.yaml").read_text(encoding="utf-8"))
    texts = [a["description"] for a in cfg["irrigation_farmer"]["actions"]]
    texts += [sk["description"] for sk in reg["skills"]]
    assert len(texts) == 10
    for d in texts:
        d = d.lower()
        assert "yield" not in d and "crop" not in d and "curtailment risk" not in d
        assert "%" not in d and "percent" not in d
    assert cfg["irrigation_farmer"]["memory"]["rejection_line_style"] == "neutral"


def test_dashboard_situation_and_memory_state_the_same_numbers(tmp_path):
    """T12 end to end for a Lower Basin agent under a real Lake Mead
    physical shortfall: the dashboard WARNING (recorded in post_year from
    the settlement), the next year's "Last year" situation sentence and
    the memory line carry the same request and delivery, and the
    situation text and memory line the same reason.

    PI decision 2026-09-28 (supersedes review fix 4 and this test's
    original below-0.85 setup, which shrank
    WaterSystemConfig.lb_non_ag_total_maf): the declared tier's shortage
    volume is borne entirely by the Lower Basin non-agricultural bucket,
    never by an agricultural agent's own delivery -- shrinking that
    bucket no longer pushes an agricultural agent's own delivery down (if
    anything it frees more water for agriculture). The below-0.85
    dashboard alert is restored here by forcing a genuine PHYSICAL Lake
    Mead shortfall instead (both reservoirs just above their dead pools,
    plus an overridden severe-drought natural flow), which is the only
    way an agricultural agent's delivery is reduced under the new rule
    (lb_phys_ratio, phi < 1)."""
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
    cfg_ws = env.config
    # Both reservoirs just above their dead pools, plus an overridden
    # severe-drought natural flow for every year, force a real physical
    # shortfall (lb_phys_ratio well below 0.85) -- not a declared-tier
    # cut, which no longer touches agricultural delivery at all.
    env._mead_storage = [cfg_ws.mead_dead_pool_maf + 0.2]  # ~901 ft, near dead pool
    env._powell_storage = cfg_ws.powell_dead_pool_maf + 0.2
    env._natural_flow_for_year = lambda year: 0.5
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
    # PI decision 2026-09-28: an agricultural agent's own delivery ratio
    # is exactly lb_phys_ratio (phi) -- the declared tier plays no part.
    phi = env.last_settlement["lb_phys_ratio"]
    assert env.last_settlement["agents"]["LB1"]["gap_reason"] == "lb_mead_availability"
    assert phi < 0.85, "scenario must actually cross the dashboard alert threshold"
    assert got / req == pytest.approx(phi)

    ctx = {}
    FeedbackDashboardProvider(tracker, fb_cfg).provide("LB1", {}, ctx, env_context={})
    dash = ctx["feedback_dashboard"]
    # The property this test cares about -- the dashboard shows the SAME
    # numbers as the situation text and memory line -- plus the below-0.85
    # WARNING sentence itself (config/agent_types.yaml,
    # irrigation_farmer.feedback.assertions), restored here via a real
    # physical shortfall rather than a declared tier. Re-review 2026-09-29
    # (MEDIUM 5): restore the exact phrase assertions (confirmed to still
    # hold under the new physical-shortfall scenario), not just a loose
    # number/keyword check.
    assert f"You requested {req:,.0f} AF and received {got:,.0f} AF" in dash
    assert "The reason is stated in your water situation above" in dash

    runner._current_year = 2
    env.advance_year()
    hooks.pre_year(2, {}, {"LB1": agent})
    # The physical shortfall (lb_mead_availability), not a declared tier,
    # is why LB1's delivery was below its request last year.
    reason = describe_gap_reason({"gap_reason": "lb_mead_availability"})
    assert f"Last year you requested {req:,.0f} acre-ft and received {got:,.0f} acre-ft" in agent.water_situation_text
    assert reason in agent.water_situation_text
    mem = runner.memory_engine.add_memory_for_agent.call_args.args[1]
    assert f"received {got:,.0f} acre-ft" in mem and reason in mem


def test_dashboard_message_true_for_tier_only_year():
    """PI decision 2026-09-28: a declared shortage tier alone (no Lake
    Mead physical limit) no longer reduces a Lower Basin agricultural
    agent's delivery at all, so the F13 message must say so rather than
    claim a same-share cut that no longer happens in that case."""
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "examples/irrigation_abm/config/agent_types.yaml").read_text(encoding="utf-8"))
    msg = cfg["irrigation_farmer"]["feedback"]["assertions"][0]["message"]
    assert "A declared shortage does not by itself reduce your delivery" in msg
    assert "When a physical limit binds" in msg
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


def test_missing_shortage_volume_raises_only_when_it_would_be_shown():
    """Re-review 2026-09-29 (LOW D): a Lower Basin context with a declared
    tier and no lb_shortage_volume_maf is a real data-shape defect
    (get_agent_context should always set it once a tier is declared) --
    raise rather than silently reporting a fabricated 0 acre-ft cut. An
    Upper Basin context never reads the value at all (the sentence it
    feeds is Lower-Basin-only), so the same missing key must not raise
    there, and neither does a Lower Basin context at tier 0 (never
    displayed)."""
    st = dict(_lb_tier2_state(), shortage_tier=2)
    del st["lb_shortage_volume_maf"]
    with pytest.raises(ValueError, match="lb_shortage_volume_maf"):
        build_water_situation_text(st)

    st_tier0 = dict(st, shortage_tier=0)
    build_water_situation_text(st_tier0)  # does not raise

    ub_state = dict(_ub_powell_state())
    ub_state.pop("lb_shortage_volume_maf", None)
    assert ub_state["shortage_tier"] > 0
    build_water_situation_text(ub_state)  # does not raise: Upper Basin never reads it


def test_new_message_text_has_no_em_dash():
    st = _ub_powell_state()
    texts = [build_water_situation_text(st, last_year={"request": 1.0, "diversion": 0.5,
                                                       "gap_reason": "ub_powell_release"}),
             supply_gap_block_increase("increase_small", [], st)[0].errors[0],
             curtailment_awareness_check("increase_small", [], _lb_tier2_state())[0].errors[0]]
    for code in ("ub_capacity", "ub_powell_release", "lb_shortage_tier", "lb_mead_availability"):
        texts.append(describe_gap_reason({"gap_reason": code, "curtailment_ratio": 0.1}))
    assert not any("\u2014" in t for t in texts)


def test_smoke_check_j_checks_step_class():
    import pandas as pd
    from examples.irrigation_abm.validate_smoke import check_j_magnitude_bounds
    ok_sim = pd.DataFrame([{"yearly_decision": "decrease_large", "magnitude_pct": 5.78,
                            "magnitude_af": 2_000.0, "magnitude_class": "large"}])
    assert check_j_magnitude_bounds(ok_sim)[0]
    bad_sim = ok_sim.assign(magnitude_class="small")
    assert not check_j_magnitude_bounds(bad_sim)[0]
    legacy = pd.DataFrame([{"yearly_decision": "decrease_large", "magnitude_pct": 13.0}])
    assert check_j_magnitude_bounds(legacy)[0]


def test_zero_delivery_message_does_not_claim_sharing():
    st = dict(_ub_powell_state(), current_diversion=0.0, delivery_ratio=0.0)
    msg = supply_gap_block_increase("increase_small", [], st)[0].errors[0]
    assert "no delivery is expected" in msg and "other users" not in msg


@pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
def test_pre_year_wires_subbasin_fields_for_sharing_sentence(tmp_path):
    """WP1b re-review (HIGH 1, 2026-09-29): IrrigationLifecycleHooks.
    pre_year must copy supply_group and ub_subbasin_member_count into
    validator_fields, or _sharing_sentence cannot tell a sub-basin-scoped
    shortfall from a basin-wide one and falls back to naming "other Upper
    Basin users" even for a UT1 agent, whose real sharing group is its own
    eleven-member sub-basin. Goes through pre_year's OWN field wiring
    (like test_dashboard_message_true_for_tier_only_year above), not a
    hand-built context dict, for both a real (UT1) and the lone-member
    (UT2) case."""
    from unittest.mock import MagicMock

    import numpy as np

    from broker.agents import AgentConfig, BaseAgent
    from examples.irrigation_abm.irrigation_personas import create_profiles_from_data
    from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks

    def _make_agent(agent_id: str) -> BaseAgent:
        a = BaseAgent(AgentConfig(name=agent_id, agent_type="irrigation_farmer", state_params=[],
                                  objectives=[], constraints=[], skills=[]))
        a.custom_attributes = {}
        return a

    rng = np.random.default_rng(7)
    profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
    env = IrrigationEnvironment(WaterSystemConfig(seed=7))
    env.initialize_from_profiles(profiles)
    ut1_profile = next(p for p in profiles if p.precip_group == "UT1")
    ut2_profile = next(p for p in profiles if p.precip_group == "UT2")
    assert ut1_profile.agent_id != ut2_profile.agent_id

    runner = SimpleNamespace(memory_engine=MagicMock(), _current_year=1)
    runner.memory_engine.retrieve.return_value = []
    hooks = IrrigationLifecycleHooks(env, runner, profiles, reflection_engine=None, output_dir=tmp_path)

    # UT1: 2018 requests held fixed through sim year 2033 (loop year 15),
    # where UT1's own sub-basin is genuinely short (memo section 6: ratio
    # 0.674) -- no manual manipulation, a real settlement.
    for _ in range(15):
        env.advance_year()
        env.settle_year()
    assert env._current_year == 2033
    ut1_agent = _make_agent(ut1_profile.agent_id)
    runner._current_year = 15
    hooks.pre_year(15, {}, {ut1_profile.agent_id: ut1_agent})
    assert ut1_agent.custom_attributes["supply_group"] == "UT1"
    assert ut1_agent.custom_attributes["ub_subbasin_member_count"] == 11
    assert ut1_agent.custom_attributes["gap_reason"] == "ub_subbasin_supply"
    sentence = _sharing_sentence(ut1_agent.custom_attributes)
    assert "other users in your sub-basin" in sentence
    assert "other Upper Basin users" not in sentence

    # UT2: never short at 2018 use (memo section 6), so its own sub-basin
    # shortfall is forced here for test purposes only -- _settle is pure
    # (its own docstring), so this does not disturb any other agent's
    # already-committed state.
    forced_snapshot = dict(env._snapshot)
    forced_available = dict(forced_snapshot["ub_subbasin_available_af"])
    forced_available["UT2"] = 1.0  # AF: far below UT2's request
    forced_snapshot["ub_subbasin_available_af"] = forced_available
    env._write_agent_deliveries(env._settle(forced_snapshot))
    ut2_agent = _make_agent(ut2_profile.agent_id)
    hooks.pre_year(15, {}, {ut2_profile.agent_id: ut2_agent})
    assert ut2_agent.custom_attributes["supply_group"] == "UT2"
    assert ut2_agent.custom_attributes["ub_subbasin_member_count"] == 1
    assert ut2_agent.custom_attributes["gap_reason"] == "ub_subbasin_supply"
    assert _sharing_sentence(ut2_agent.custom_attributes) == (
        "When water is short, a larger request would not add water."
    )


@pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
def test_sharing_sentence_raises_on_missing_count_for_subbasin_reason():
    """HIGH 1: a context that names gap_reason=ub_subbasin_supply without
    ub_subbasin_member_count is the exact wiring defect this re-review
    found (pre_year not copying the field) -- must raise, never silently
    read as basin-wide."""
    incomplete = {"basin": "upper_basin", "gap_reason": "ub_subbasin_supply"}
    with pytest.raises(ValueError, match="ub_subbasin_member_count"):
        _sharing_sentence(incomplete)
