"""Irrigation case study v3, WP4 review (MEDIUM 4, 2026-09-30): regression
tests for two fixes to the last-year snapshot that
``IrrigationLifecycleHooks.post_year`` takes and ``pre_year`` of the next
year reads, without the CRSS reference data (``ref/CRSS_DB`` is not in git).

1. A Lower Basin agent holding junior-priority water whose junior part the
   declared tier cut: the snapshot lacked the cut share, so the next year's
   memory line raised ValueError (a real run crashed in its third year, the
   year after the first tier year).
2. An Upper Basin agent's memory line read the basin-level precipitation
   flag instead of the agent's own sub-basin flag, so it could contradict the
   situation text of the same year.

Both fail on HEAD 9f4986c4 (the first with the ValueError, the second on the
flag). The agents are hand-built profiles with the real Lower Basin name
MohaveValleyIDD (its published split is in the tracked
lb_priority_split_v3.csv: 5,940 AF senior, 35,060 AF junior) and an Upper
Basin agent in sub-basin UT1 (tracked ub_subbasin_supply_v3.csv).
"""
from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from broker.agents import AgentConfig, BaseAgent
from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from examples.irrigation_abm.irrigation_env import IrrigationEnvironment, WaterSystemConfig
from examples.irrigation_abm.irrigation_personas import IrrigationAgentProfile
from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks


def _two_years(profile: IrrigationAgentProfile, config: WaterSystemConfig, *, before_year_1=None):
    """advance_year, pre_year, post_year for 2019, then advance_year and
    pre_year for 2020, with no decision in between (every agent keeps)."""
    env = IrrigationEnvironment(config)
    env.initialize_from_profiles([profile])
    engine = HumanCentricMemoryEngine(window_size=5, top_k_significant=2, seed=1)
    agent = BaseAgent(AgentConfig(name=profile.agent_id, agent_type="irrigation_farmer",
                                  state_params=[], objectives=[], constraints=[], skills=[]))
    agent.custom_attributes = {}
    agent.is_active = True
    agents = {profile.agent_id: agent}
    runner = SimpleNamespace(broker=SimpleNamespace(_retry_feedback_mode="full"),
                             agents=agents, memory_engine=engine)
    hooks = IrrigationLifecycleHooks(env, runner, [profile], None, None)
    env.advance_year()
    if before_year_1 is not None:
        before_year_1(env)
    hooks.pre_year(1, {}, agents)
    situation_2019 = agent.water_situation_text
    hooks.post_year(1, agents)
    env.advance_year()
    hooks.pre_year(2, {}, agents)
    memory = [m["content"] for m in engine.working[profile.agent_id]]
    return situation_2019, agent.water_situation_text, memory


def test_request_below_junior_tier_ceiling_is_followed_by_a_full_delivery_memory_line():
    """Lake Mead below 1,075 ft on 1 January 2019 declares Tier 1; the keep
    request (the 2018 use, 28,295 AF) is above the 5,940 AF senior
    entitlement but below the Tier 1 ceiling. The tier sentence states the
    entitlement ceiling and the 2020 memory records a full delivery."""
    profile = IrrigationAgentProfile(
        agent_id="MohaveValleyIDD", basin="lower_basin", cluster="myopic_conservative",
        water_right=50_000.0, actual_2018_diversion=28_295.0)
    config = WaterSystemConfig(seed=42, mead_initial_elevation=1_060.0)
    situation_2019, situation_2020, memory = _two_years(profile, config)
    assert "A Tier 1 Lower Basin shortage applies this year" in situation_2019
    assert ("limits your junior-priority water this year to about 27,958 acre-ft "
            "(80% of your 35,060 acre-ft junior-priority entitlement)") in situation_2019
    assert "your 33,898 acre-ft tier ceiling is not reduced by the tier" in situation_2019
    (line,) = [m for m in memory if m.startswith("Year ")]
    assert line.startswith("Year 2019:")
    assert "You requested 28,295 acre-ft and received 28,295 acre-ft. Demand fully met." in line
    assert "Shortfall:" not in line
    assert ("Last year you requested 28,295 acre-ft and received 28,295 acre-ft "
            "(100% delivered).") in situation_2020


@pytest.mark.parametrize("own_flag,basin_flag", [(1, 0), (0, 1)])
def test_upper_basin_memory_line_reads_the_agents_own_flag(own_flag, basin_flag):
    """The agent's own sub-basin flag (spec 1.6) is forced to differ from the
    basin-level legacy flag in 2019: the 2019 situation text and the 2019
    memory line read in 2020 must state the same direction, the own one."""
    profile = IrrigationAgentProfile(
        agent_id="UT1Agent", basin="upper_basin", cluster="aggressive",
        water_right=100_000.0, actual_2018_diversion=50_000.0, precip_group="UT1")

    def force_flags(env):
        env._precip_group_flags["UT1"] = own_flag
        env._basins["upper_basin"]["preceding_factor"] = basin_flag

    situation_2019, _, memory = _two_years(profile, WaterSystemConfig(seed=42),
                                           before_year_1=force_flags)
    word = "above" if own_flag else "below"
    # the one memory line so far, whatever its year label
    (line,) = [m for m in memory if m.startswith("Year ")]
    stated = re.search(r"precipitation[^.]*? was (above|below)", line, flags=re.I)
    assert stated is not None, line
    assert stated.group(1) == word, line
    assert line.startswith("Year 2019:")
    assert f"mm ({word} last year)." in situation_2019
