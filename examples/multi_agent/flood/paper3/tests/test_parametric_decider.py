"""Tests for the Paper 3 parametric household decision arm."""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from broker.interfaces.skill_types import SkillProposal
from examples.multi_agent.flood.generate_agents import HouseholdProfile
from examples.multi_agent.flood.orchestration.agent_factories import wrap_household


def _decider_module():
    try:
        return importlib.import_module(
            "examples.multi_agent.flood.parametric.parametric_decider"
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"Parametric decider module is missing: {exc}")


def _household(
    agent_id: str = "H0001",
    *,
    tenure: str = "Owner",
    income: float = 80_000.0,
    flood_zone: str = "HIGH",
    flood_frequency: int = 0,
    tp_score: float = 3.0,
    cp_score: float = 3.0,
    sc_score: float = 3.0,
    pa_score: float = 3.0,
    rcv_building: float = 200_000.0,
    rcv_contents: float = 80_000.0,
    elevated: bool = False,
    has_insurance: bool = False,
) -> Any:
    profile = HouseholdProfile(
        agent_id=agent_id,
        tenure=tenure,  # type: ignore[arg-type]
        income=income,
        flood_zone=flood_zone,
        flood_experience=flood_frequency > 0,
        flood_frequency=flood_frequency,
        tp_score=tp_score,
        cp_score=cp_score,
        sc_score=sc_score,
        pa_score=pa_score,
        rcv_building=rcv_building if tenure == "Owner" else 0.0,
        rcv_contents=rcv_contents,
        elevated=elevated,
        has_insurance=has_insurance,
    )
    return wrap_household(profile)


def test_calibration_block_pins_requested_defaults():
    module = _decider_module()

    calibration = module.PARAMETRIC_CALIBRATION

    assert calibration["base_rates"] == {
        "flood_prone_owner": 0.25,
        "flood_prone_renter": 0.08,
        "non_flood_prone_owner": 0.03,
        "non_flood_prone_renter": 0.01,
    }
    assert calibration["slopes"] == {
        "threat": 2.0,
        "coping": 1.0,
        "cost": 1.5,
    }
    assert calibration["anchors"] == {"tp0": 0.5, "cp0": 0.5}
    assert calibration["gates"]["elevate"]["min_flood_count"] == 2
    assert calibration["gates"]["buyout"]["min_flood_count"] == 3
    assert calibration["gates"]["relocate"]["min_flood_count"] == 1


def test_decider_returns_broker_proposal_with_construct_labels():
    module = _decider_module()
    decider = module.ParametricHouseholdDecider(seed=17)
    agent = _household(
        tenure="Renter",
        flood_zone="LOW",
        tp_score=1.0,
        cp_score=5.0,
        rcv_contents=20_000.0,
    )

    proposal = decider.decide(agent, {"current_year": 1}, year=1, agent_depth_m=0.0)

    assert isinstance(proposal, SkillProposal)
    assert proposal.skill_name in {
        "buy_contents_insurance",
        "relocate",
        "do_nothing",
    }
    assert proposal.agent_id == "H0001"
    assert proposal.agent_type == "household_renter"
    assert proposal.reasoning["TP_LABEL"] == "VL"
    assert proposal.reasoning["CP_LABEL"] == "VH"
    assert proposal.reasoning["reasoning"] == "parametric PMT decision"
    assert proposal.raw_output == "parametric PMT decision"
    assert proposal.parse_layer == "parametric"
    assert proposal.construct_completeness == 1.0


def test_hard_gates_exclude_ineligible_actions_before_draws():
    module = _decider_module()
    decider = module.ParametricHouseholdDecider(seed=42)

    low_zone_owner = _household(flood_zone="LOW", flood_frequency=10)
    assert decider.eligible_actions(low_zone_owner) == [
        "buy_insurance",
        "do_nothing",
    ]

    early_owner = _household(flood_zone="HIGH", flood_frequency=1)
    assert decider.eligible_actions(early_owner) == [
        "buy_insurance",
        "do_nothing",
    ]

    repeat_owner = _household(flood_zone="HIGH", flood_frequency=3)
    assert decider.eligible_actions(repeat_owner) == [
        "buy_insurance",
        "elevate_house",
        "buyout_program",
        "do_nothing",
    ]

    first_year_renter = _household(tenure="Renter", flood_frequency=0)
    assert decider.eligible_actions(first_year_renter) == [
        "buy_contents_insurance",
        "do_nothing",
    ]

    flooded_renter = _household(tenure="Renter", flood_frequency=1)
    assert decider.eligible_actions(flooded_renter) == [
        "buy_contents_insurance",
        "relocate",
        "do_nothing",
    ]


def test_decisions_are_deterministic_and_idempotent_for_same_agent_year():
    module = _decider_module()
    agent = _household(
        agent_id="H0099",
        flood_zone="HIGH",
        flood_frequency=3,
        tp_score=4.0,
        cp_score=4.0,
    )
    env = {"current_year": 2, "effective_rate": 0.0068}

    decider_a = module.ParametricHouseholdDecider(seed=123)
    decider_b = module.ParametricHouseholdDecider(seed=123)

    first = decider_a.decide(agent, env, year=2, agent_depth_m=0.5).to_dict()
    retry_same_year = decider_a.decide(agent, env, year=2, agent_depth_m=0.5).to_dict()
    independent_same_seed = decider_b.decide(agent, env, year=2, agent_depth_m=0.5).to_dict()

    assert first == retry_same_year
    assert first == independent_same_seed


def test_tp_decay_engine_shock_feeds_construct_label():
    module = _decider_module()
    decider = module.ParametricHouseholdDecider(seed=0)
    agent = _household(
        tp_score=1.0,
        cp_score=3.0,
        rcv_building=100_000.0,
        rcv_contents=50_000.0,
    )

    no_flood = decider.decide(agent, {"current_year": 1}, year=1, agent_depth_m=0.0)

    flooded_agent = _household(
        agent_id="H0002",
        tp_score=1.0,
        cp_score=3.0,
        rcv_building=100_000.0,
        rcv_contents=50_000.0,
    )
    flooded = module.ParametricHouseholdDecider(seed=0).decide(
        flooded_agent,
        {"current_year": 1},
        year=1,
        agent_depth_m=4.5,
    )

    assert no_flood.reasoning["TP_LABEL"] == "VL"
    assert flooded.reasoning["TP_LABEL"] in {"H", "VH"}


def test_runner_installer_routes_only_households_to_parametric_decider():
    module = _decider_module()
    from examples.multi_agent.flood import run_unified_experiment as runner_module

    owner = _household(agent_id="H0007", flood_zone="HIGH", flood_frequency=2)

    class FakeBroker:
        def process_step(
            self,
            *,
            agent_id,
            step_id,
            run_id,
            seed,
            llm_invoke,
            agent_type="default",
            env_context=None,
        ):
            return llm_invoke("prompt text")

    class FakeRunner:
        def __init__(self):
            self.agents = {"H0007": owner, "gov": object()}
            self.broker = FakeBroker()

    class FakeHooks:
        per_agent_depth = True
        agent_flood_depths = {"H0007": 0.25}

    runner = FakeRunner()
    decider = module.ParametricHouseholdDecider(seed=5)

    runner_module._install_parametric_household_decider(runner, decider, FakeHooks())

    household_result = runner.broker.process_step(
        agent_id="H0007",
        step_id=1,
        run_id="r",
        seed=6,
        llm_invoke=lambda _prompt: pytest.fail("household path called LLM"),
        agent_type="household_owner",
        env_context={"current_year": 1},
    )
    institutional_result = runner.broker.process_step(
        agent_id="gov",
        step_id=2,
        run_id="r",
        seed=7,
        llm_invoke=lambda _prompt: "llm-result",
        agent_type="government",
        env_context={"current_year": 1},
    )

    assert isinstance(household_result, SkillProposal)
    assert household_result.agent_id == "H0007"
    assert household_result.parse_layer == "parametric"
    assert institutional_result == "llm-result"
