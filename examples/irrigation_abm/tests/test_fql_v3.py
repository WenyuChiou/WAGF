"""
Tests for the WP5 FQL reference (irrigation_v3_spec_2026-09-28.md section 5).

Each test here targets a specific fidelity gap the pre-WP5 code (HEAD
af15f6ef) carries and closes:

  L1-06 (spec 5.1): Div_t must be the BASE (last final delivery), not
      ctx["current_diversion"] (the PROVISIONAL delivery at the keep
      request the supply rule reads -- a different quantity).
  L1-04 (spec 5.2): the FQL's own action sets the request directly
      (env.update_agent_request); run_simulation must not call
      env.execute_skill(), which redraws its OWN step from a DIFFERENT
      RNG stream (env._decision_rng, seeded off WaterSystemConfig, never
      touched by the FQL agent's own rng).
  L1-05, L1-15 (spec 5.3): the pair passed to FQLAgent.step is
      (pf_prev, pf_now), not a same-year persistence assumption; pf_prev
      is 1 in year 1 (2019), matching H&Y's own hardcoded f_t[0].
  L1-02 (spec 5.4): the FQL state and the action-magnitude bin must run
      on Div_t/k and step_bin_af/k -- H&Y's own diversion-unit grid for an
      Upper Basin agent, not the environment's depletion-unit acre-feet.
  spec 5.6: the governed ("FQL plus rules") CPU-sensitivity path falls a
      blocked increase back to keep (maintain_demand) ONLY -- no further
      "last resort" tier.
  spec 5.7: the logged skill is the sign of the EXECUTED change.

All tests here are constructed to FAIL on the pre-WP5 code: several call
functions (_fql_agent_decision, _fql_request_and_prev_action) that do not
exist there at all; the rest exercise a specific numeric/behavioral
difference the fix introduces (see each test's own docstring).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from examples.irrigation_abm.learning.fql import (
    FQLAgent,
    FQLConfig,
    FQLState,
    _hy_div_to_state,
)
from examples.irrigation_abm.run_fql_baseline import (
    _fql_agent_decision,
    _fql_request_and_prev_action,
    _create_synthetic_profiles,
    create_fql_agents,
    run_simulation,
    validate_skill,
)
import examples.irrigation_abm.run_fql_baseline as run_fql_baseline_module
from examples.irrigation_abm.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
    MIN_UTIL,
)
from examples.irrigation_abm.irrigation_personas import (
    IrrigationAgentProfile,
    create_profiles_from_data,
)
from broker.interfaces.skill_types import ValidationResult

CRSS_PARAMS_CSV = PROJECT_ROOT / "ref" / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"
CRSS_DB_DIR = PROJECT_ROOT / "ref" / "CRSS_DB" / "CRSS_DB"
FQL_INIT_DIR = CRSS_DB_DIR / "Initial_Files" / "All-1109"
_REAL_REF_AVAILABLE = (
    CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir() and FQL_INIT_DIR.is_dir()
)


def _make_single_agent_env(
    basin: str = "lower_basin",
    water_right: float = 100_000.0,
    actual_2018_diversion: float = None,
    demand_per_grid_unit: float = None,
    precip_group: str = None,
    agent_id: str = "TestAgent",
    seed: int = 7,
) -> Tuple[IrrigationEnvironment, IrrigationAgentProfile]:
    """One agent, the v3-default WaterSystemConfig, no LLM/CRSS dependency.

    Marks the profile synthetic_no_subbasin / synthetic_no_priority_split
    (the same mock-smoke-only treatment _create_synthetic_profiles uses)
    unless a real precip_group is given, so initialize_from_profiles never
    needs ref/CRSS_DB data for these unit-level tests.
    """
    config = WaterSystemConfig(seed=seed)
    env = IrrigationEnvironment(config)
    kwargs: Dict[str, Any] = dict(
        agent_id=agent_id,
        basin=basin,
        cluster="aggressive",
        water_right=water_right,
        mu=0.3,
        sigma=0.5,
        actual_2018_diversion=actual_2018_diversion,
        demand_per_grid_unit=demand_per_grid_unit,
        precip_group=precip_group,
    )
    if basin == "upper_basin" and not precip_group:
        kwargs["synthetic_no_subbasin"] = True
    if basin == "lower_basin":
        kwargs["synthetic_no_priority_split"] = True
    profile = IrrigationAgentProfile(**kwargs)
    env.initialize_from_profiles([profile])
    return env, profile


# ── spec 5.2 (L1-04): no execute_skill redraw ──

class TestRequestFormula:
    def test_request_is_div_plus_own_action(self):
        """req = Div_t + k*a, using the FQL agent's OWN sampled action --
        no env.execute_skill() redraw. Proven by independently replaying
        the SAME FQLAgent.step() call (identical config, identical seed,
        identical freshly-initialised state) on a clone that never touches
        the environment, then checking the environment's resulting
        request against that independent expectation via
        _fql_request_and_prev_action.

        On pre-change code (HEAD af15f6ef) run_simulation calls
        env.execute_skill(), which redraws its own step from
        env._decision_rng -- a per-(seed, year, agent, skill) stream
        derived from WaterSystemConfig's seed, never touched by the
        FQLAgent's own rng -- so the actually-written request would NOT
        match this independently-computed expectation, and
        _fql_agent_decision/_fql_request_and_prev_action do not exist
        there at all (ImportError)."""
        env, profile = _make_single_agent_env(
            basin="lower_basin", water_right=100_000.0,
            actual_2018_diversion=40_000.0, demand_per_grid_unit=1.0,
        )
        aid = profile.agent_id
        env.advance_year()
        div_t = float(env.get_agent_state(aid)["base_af"])
        assert div_t == pytest.approx(40_000.0)
        pf_now = int(env.get_agent_context(aid)["preceding_factor"])
        water_right = float(env.get_agent_context(aid)["water_right"])
        floor = water_right * MIN_UTIL

        config = FQLConfig(mu=0.3, sigma=0.5, alpha=0.7, gamma=0.7, epsilon=0.2, regret=1.5)

        def _fresh_agent_and_state(seed: int):
            state = FQLState(state_bounds=np.linspace(0, 100_000, 21))
            state.initialize(config)
            return FQLAgent(config, rng=np.random.default_rng(seed)), state

        # Independent clone: predicts the raw action WITHOUT touching env.
        clone_agent, clone_state = _fresh_agent_and_state(123)
        expected_action = clone_agent.step(clone_state, div_t, (1, pf_now))
        expected_req, _ = _fql_request_and_prev_action(
            div_t, 1.0, expected_action, water_right, floor
        )

        real_agent, real_state = _fresh_agent_and_state(123)
        decision = _fql_agent_decision(
            env=env, profile=profile, fql_agent=real_agent, fql_state=real_state,
            pf_prev=1, year_idx=1, no_governance=True,
        )
        assert decision["action"] == pytest.approx(expected_req - div_t)
        assert env.get_agent_state(aid)["request"] == pytest.approx(expected_req)

    def test_prev_action_executed_convention_at_cap(self):
        """At the water-right cap, req - Div_t = 0 regardless of the
        sampled action's sign, so prev_action_executed = 0 exactly -- H&Y's
        own int(a_t > 0) then books it as the DECREASE index for the next
        Bayesian update (disclosed, not a bug)."""
        water_right = 100_000.0
        div_t = water_right  # already at the cap
        floor = water_right * MIN_UTIL
        req, prev_action = _fql_request_and_prev_action(
            div_t, k=0.5, action=250.0, water_right=water_right, floor=floor,
        )
        assert req == pytest.approx(water_right)
        assert prev_action == pytest.approx(0.0)

    def test_prev_action_formula_nonboundary_case(self):
        """WP5 review (2026-09-30, item 1): a NON-boundary case for
        _fql_request_and_prev_action's own prev_action return value.

        The mutation injection "/k on prev_action" passed every test
        before this one existed, because BOTH pre-existing tests of this
        function used a req - Div_t == 0 scenario (at the cap; within the
        floor tolerance), where dividing 0 by k is 0 regardless of k --
        the mutation's effect was invisible there. It was ALSO invisible
        end-to-end because _fql_agent_decision discarded this exact
        return value via ``_`` and recomputed prev_action inline instead
        (fixed in the same review round: _fql_agent_decision now reuses
        this function's own prev_action_raw for the not-blocked case).
        This test uses k=0.5 and an increase well clear of the cap, so
        req - Div_t is a large, definitely-nonzero number and the /k
        division is directly observable."""
        div_t = 1_000.0
        k = 0.5
        water_right = 100_000.0
        floor = water_right * MIN_UTIL
        req, prev_action = _fql_request_and_prev_action(
            div_t, k, action=100.0, water_right=water_right, floor=floor,
        )
        assert req == pytest.approx(1_000.0 + 0.5 * 100.0)  # 1050.0
        assert prev_action == pytest.approx((req - div_t) / k)  # 100.0
        assert prev_action == pytest.approx(100.0)

    def test_floor_rule_no_op_below_tolerance(self):
        """The 2.1 floor rule: a decrease is a no-op (never floor-anchored
        up) once Div_t is already within 1 percent of the floor."""
        water_right = 100_000.0
        floor = water_right * MIN_UTIL  # 10,000
        div_t = floor * 1.005  # within the 1.01x tolerance
        req, prev_action = _fql_request_and_prev_action(
            div_t, k=1.0, action=-500.0, water_right=water_right, floor=floor,
        )
        assert req == pytest.approx(div_t)
        assert prev_action == pytest.approx(0.0)


# ── spec 5.1 (L1-06): Div_t is the base, not the provisional delivery ──

class TestDivTIsBase:
    def test_div_t_is_last_final_delivery(self, monkeypatch):
        """Poking agent_state["diversion"] (the PROVISIONAL delivery a
        shortage year's advance_year() settlement writes there) to differ
        from agent_state["base_af"] and confirming FQLAgent.step() still
        receives base_af/k proves Div_t reads the base, not the
        provisional delivery."""
        env, profile = _make_single_agent_env(
            basin="lower_basin", water_right=100_000.0,
            actual_2018_diversion=40_000.0, demand_per_grid_unit=1.0,
        )
        aid = profile.agent_id
        env.advance_year()
        base_af = float(env.get_agent_state(aid)["base_af"])
        assert base_af == pytest.approx(40_000.0)

        # Simulate what a real shortage year's provisional settlement
        # would do: "diversion" (the supply rule's own provisional-
        # delivery input) drops below "base_af" (the keep request).
        env._agents[aid]["diversion"] = base_af * 0.4

        calls: List[float] = []
        original_step = FQLAgent.step

        def _spy_step(self, state, current_diversion, preceding_factor):
            calls.append(current_diversion)
            return original_step(self, state, current_diversion, preceding_factor)

        monkeypatch.setattr(FQLAgent, "step", _spy_step)

        fql_agent, fql_state = create_fql_agents([profile], seed=5, fql_init="zero")[aid]
        _fql_agent_decision(
            env=env, profile=profile, fql_agent=fql_agent, fql_state=fql_state,
            pf_prev=1, year_idx=1, no_governance=True,
        )
        assert calls == [pytest.approx(base_af)]


# ── spec 5.3 (L1-05, L1-15): (pf_prev, pf_now), not a persistence assumption ──

class TestPrecedingFactorPair:
    def test_preceding_pair_lagged(self, monkeypatch):
        """pf_prev in year 1 (2019) is 1 (H&Y's f_t[0]); each later year's
        pf_prev is the PREVIOUS year's pf_now, not that same year's own
        value (the pre-change "persistence assumption f_next = f_t")."""
        env, profile = _make_single_agent_env(
            basin="lower_basin", water_right=100_000.0,
            actual_2018_diversion=40_000.0, demand_per_grid_unit=1.0,
        )
        aid = profile.agent_id
        fql_agent, fql_state = create_fql_agents([profile], seed=5, fql_init="zero")[aid]

        calls: List[Tuple[int, int]] = []
        original_step = FQLAgent.step

        def _spy_step(self, state, current_diversion, preceding_factor):
            calls.append(tuple(preceding_factor))
            return original_step(self, state, current_diversion, preceding_factor)

        monkeypatch.setattr(FQLAgent, "step", _spy_step)

        pf_prev = 1
        for year_idx in range(1, 4):
            env.advance_year()
            decision = _fql_agent_decision(
                env=env, profile=profile, fql_agent=fql_agent, fql_state=fql_state,
                pf_prev=pf_prev, year_idx=year_idx, no_governance=True,
            )
            pf_prev = decision["pf_now"]

        assert len(calls) == 3
        assert calls[0][0] == 1  # spec 5.3: pf_prev = 1 in 2019
        assert calls[1][0] == calls[0][1]  # this year's pf_prev = last year's pf_now
        assert calls[2][0] == calls[1][1]

    def test_ub_regional_flag(self, monkeypatch):
        """An Upper Basin agent's pf_now comes from ITS OWN sub-basin
        column (get_agent_context, WP1) -- two agents in different
        sub-basins with different flags must see DIFFERENT pf_now values
        threaded into FQLAgent.step(), proving _fql_agent_decision reads
        the per-agent signal rather than a shared/basin-level one."""
        config = WaterSystemConfig(seed=11)
        env = IrrigationEnvironment(config)
        profile_wy = IrrigationAgentProfile(
            agent_id="WYAgent", basin="upper_basin", cluster="aggressive",
            water_right=50_000.0, mu=0.3, sigma=0.5, precip_group="WY",
            demand_per_grid_unit=0.5,
        )
        profile_co1 = IrrigationAgentProfile(
            agent_id="CO1Agent", basin="upper_basin", cluster="aggressive",
            water_right=50_000.0, mu=0.3, sigma=0.5, precip_group="CO1",
            demand_per_grid_unit=0.5,
        )
        env.initialize_from_profiles([profile_wy, profile_co1])
        env.advance_year()  # populates _precip_history (synthetic fallback, all 9 groups)

        # Directly control the per-group flag (WP1's own internal state)
        # instead of needing real CRSS precipitation data -- this test is
        # about WP5's INTEGRATION reading it per-agent, not about WP1's
        # own flag computation (covered elsewhere).
        env._precip_group_flags = {"WY": 1, "CO1": 0}

        calls: List[Tuple[int, int]] = []
        original_step = FQLAgent.step

        def _spy_step(self, state, current_diversion, preceding_factor):
            calls.append(tuple(preceding_factor))
            return original_step(self, state, current_diversion, preceding_factor)

        monkeypatch.setattr(FQLAgent, "step", _spy_step)
        fql_agent_wy, fql_state_wy = create_fql_agents(
            [profile_wy], seed=1, fql_init="zero"
        )["WYAgent"]
        fql_agent_co1, fql_state_co1 = create_fql_agents(
            [profile_co1], seed=2, fql_init="zero"
        )["CO1Agent"]

        _fql_agent_decision(
            env=env, profile=profile_wy, fql_agent=fql_agent_wy,
            fql_state=fql_state_wy, pf_prev=1, year_idx=1, no_governance=True,
        )
        _fql_agent_decision(
            env=env, profile=profile_co1, fql_agent=fql_agent_co1,
            fql_state=fql_state_co1, pf_prev=1, year_idx=1, no_governance=True,
        )

        assert len(calls) == 2
        assert calls[0][1] == 1  # WY: own column flag = 1
        assert calls[1][1] == 0  # CO1: own column flag = 0


# ── WP5 review item 4 (2026-09-30): per-agent RNG streams must not collide ──

class TestRngStreamIndependence:
    def test_different_seeds_agent_streams_do_not_coincide(self):
        """Pre-fix: create_fql_agents used
        np.random.default_rng(seed + i), so agent index i+1 at seed S draws
        EXACTLY what agent index i draws at seed S+1 (both resolve to the
        same integer, e.g. 42+1 == 43+0 == 43) -- a real independence
        defect across the five-seed corpus (42-46), not a style
        preference. np.random.SeedSequence(seed).spawn(n) (the current
        implementation, WP5 review item 5, round 3) must not collide this
        way: agent 1 at seed 42 and agent 0 at seed 43 must draw different
        sequences."""
        profiles = _create_synthetic_profiles(3, seed=1)
        agents_42 = create_fql_agents(profiles, seed=42, fql_init="zero")
        agents_43 = create_fql_agents(profiles, seed=43, fql_init="zero")

        ids = [p.agent_id for p in profiles]
        agent_42_i1, _ = agents_42[ids[1]]
        agent_43_i0, _ = agents_43[ids[0]]

        draws_42_i1 = agent_42_i1.rng.random(5)
        draws_43_i0 = agent_43_i0.rng.random(5)
        assert not np.allclose(draws_42_i1, draws_43_i0)

        # And every pairwise (seed, agent-index) combination actually used
        # across the 5-seed corpus (42-46, 78 agents) is distinct too --
        # the general form of the same property, not just one instance.
        profiles78 = _create_synthetic_profiles(6, seed=2)
        seen = set()
        for seed in range(42, 47):
            agents = create_fql_agents(profiles78, seed=seed, fql_init="zero")
            for i, p in enumerate(profiles78):
                draw = tuple(agents[p.agent_id][0].rng.random(3))
                assert draw not in seen, (
                    f"seed={seed} agent_index={i}: RNG stream collides with "
                    "an earlier (seed, agent_index) pair"
                )
                seen.add(draw)


# ── spec 5.4 (L1-02): UB state/action run on H&Y's diversion-unit grid ──

class TestUpperBasinUnits:
    def test_ub_state_uses_diversion_units(self, monkeypatch):
        """An Upper Basin agent's real (depletion) diversion must be
        divided by k (0.5) BEFORE _hy_div_to_state, or it maps to roughly
        HALF the correct H&Y grid state.

        WP5 review (2026-09-30, item 1): fixed to exercise the REAL
        _fql_agent_decision path (a hand-picked agent/grid, not a bare
        call to _hy_div_to_state with fabricated numbers), so a mutation
        dropping the /k at the ACTUAL call site -- not just in the pure
        function -- is caught too. The five k-mutation injections
        (drop /k at the state; k at the request; /k on prev_action; /k on
        the warm start; /k on action_bin_size) all still passed every FQL
        test before this fix existed."""
        env, profile = _make_single_agent_env(
            basin="upper_basin", water_right=200_000.0,
            actual_2018_diversion=50.0, demand_per_grid_unit=0.5,
        )
        aid = profile.agent_id
        env.advance_year()
        base = float(env.get_agent_state(aid)["base_af"])
        assert base == pytest.approx(50.0)

        agt_states = np.linspace(0, 200.0, 21)  # bin_size = 10.0
        hy_bin_size = float(agt_states[2] - agt_states[1])

        captured: Dict[str, float] = {}
        original_step = FQLAgent.step

        def _spy_step(self, state, current_diversion, preceding_factor):
            captured["current_diversion"] = current_diversion
            return original_step(self, state, current_diversion, preceding_factor)

        monkeypatch.setattr(FQLAgent, "step", _spy_step)

        config = FQLConfig(mu=0.2, sigma=0.1)
        state = FQLState(
            state_bounds=agt_states, state_grid_mode="hy_exact", hy_bin_size=hy_bin_size,
        )
        state.initialize(config)
        agent = FQLAgent(config, rng=np.random.default_rng(3))

        _fql_agent_decision(
            env=env, profile=profile, fql_agent=agent, fql_state=state,
            pf_prev=1, year_idx=1, no_governance=True,
        )

        assert captured["current_diversion"] == pytest.approx(base / 0.5)
        actual_state = _hy_div_to_state(captured["current_diversion"], agt_states, hy_bin_size, 21)
        wrong_state = _hy_div_to_state(base, agt_states, hy_bin_size, 21)  # what it WOULD be without /k
        assert actual_state == 10
        assert wrong_state == 5
        assert actual_state != wrong_state

    def test_ub_k_conversion_through_decision(self, monkeypatch):
        """WP5 review (2026-09-30, item 1): a UB k=0.5 test through the
        FULL _fql_agent_decision path. Every earlier k-formula test used
        k=1.0 (Lower Basin), where a mutation dropping or misapplying k
        is a no-op (a Lower Basin test would pass unchanged even with any
        of the five injected k mutations); this test uses k=0.5, so each
        of those mutations breaks at least one assertion here:
          - "drop /k at the state" -> the first assert.
          - "k at the request" (formula uses action instead of k*action,
            or similar) -> the second and third asserts (independently
            re-derived, not just re-calling _fql_request_and_prev_action).
          - "/k on prev_action" -> the fourth and fifth asserts.
        """
        env, profile = _make_single_agent_env(
            basin="upper_basin", water_right=100_000.0,
            actual_2018_diversion=40_000.0, demand_per_grid_unit=0.5,
        )
        aid = profile.agent_id
        env.advance_year()
        base = float(env.get_agent_state(aid)["base_af"])
        assert base == pytest.approx(40_000.0)
        water_right = float(env.get_agent_context(aid)["water_right"])
        floor = water_right * MIN_UTIL
        k = 0.5

        captured: Dict[str, float] = {}
        original_step = FQLAgent.step

        def _spy_step(self, state, current_diversion, preceding_factor):
            captured["current_diversion"] = current_diversion
            a = original_step(self, state, current_diversion, preceding_factor)
            captured["raw_action"] = a
            return a

        monkeypatch.setattr(FQLAgent, "step", _spy_step)

        config = FQLConfig(mu=0.3, sigma=0.5, alpha=0.7, gamma=0.7, epsilon=0.2, regret=1.5)
        state = FQLState(state_bounds=np.linspace(0, 200_000, 21))
        state.initialize(config)
        agent = FQLAgent(config, rng=np.random.default_rng(321))

        _fql_agent_decision(
            env=env, profile=profile, fql_agent=agent, fql_state=state,
            pf_prev=1, year_idx=1, no_governance=True,
        )

        # step() must receive base/k, not base itself.
        assert captured["current_diversion"] == pytest.approx(base / k)

        a = captured["raw_action"]
        # Independently re-derived (not just re-calling
        # _fql_request_and_prev_action, which could share a bug with the
        # production call site).
        expected_req = min(base + k * a, water_right) if a >= 0 else (
            max(base + k * a, floor) if base > 1.01 * floor else base
        )
        actual_req = env.get_agent_state(aid)["request"]
        assert actual_req == pytest.approx(expected_req)
        assert state.prev_action == pytest.approx((actual_req - base) / k)
        assert state.prev_action == pytest.approx((expected_req - base) / k)

    def test_action_bin_size_separate_from_hy_bin_size(self):
        """FQLState.action_bin_size drives _sample_actions when set,
        independently of hy_bin_size (which stays on H&Y's own grid for
        state discretisation only) -- the WP5 5.4 mechanism that lets a
        rescaled (spec 2.4) agent's FQL request size match its
        language-model-arm typical step."""
        config = FQLConfig(mu=0.2, sigma=0.0)  # sigma=0: deterministic magnitude
        state = FQLState(
            state_bounds=np.linspace(0, 200.0, 21),
            state_grid_mode="hy_exact",
            hy_bin_size=10.0,
            action_bin_size=4.0,
        )
        state.initialize(config)
        agent = FQLAgent(config, rng=np.random.default_rng(0))
        actions = agent._sample_actions(state)
        # magnitude = (mu + |z|) * action_bin_size, sigma=0 -> z=0 exactly
        expected = 0.2 * 4.0
        np.testing.assert_allclose(np.abs(actions), [expected, expected])

    def test_synthetic_ub_agent_starts_mid_grid_not_at_top(self, monkeypatch):
        """WP5 review (2026-09-30, item 1, MEDIUM): a synthetic or
        --from-logs Upper Basin profile has no grid_top_af, so
        create_fql_agents' zero-init branch falls back to water_right.
        That fallback must be divided by k (0.5), or the agent's own
        base (converted to diversion units) is compared against a grid
        HALF as wide as it should be, pinning the agent at the TOP state
        (20) every year and halving every sampled step. actual_2018_
        diversion is set to exactly half of water_right so the fixed
        behaviour lands at the grid's exact middle (state 10) and the
        bug's own effect lands at the exact top (state 20) -- not just
        "near" either, for an unambiguous assertion."""
        env, profile = _make_single_agent_env(
            basin="upper_basin", water_right=100_000.0,
            actual_2018_diversion=50_000.0, demand_per_grid_unit=0.5,
        )
        aid = profile.agent_id
        env.advance_year()
        base = float(env.get_agent_state(aid)["base_af"])
        assert base == pytest.approx(50_000.0)

        agent, state = create_fql_agents([profile], seed=1, fql_init="zero")[aid]
        # Fixed: q_grid_top = water_right / k = 200,000 (bug: 100,000).
        assert state.state_bounds[-1] == pytest.approx(200_000.0)

        captured: Dict[str, float] = {}
        original_step = FQLAgent.step

        def _spy_step(self, st, current_diversion, preceding_factor):
            captured["current_diversion"] = current_diversion
            return original_step(self, st, current_diversion, preceding_factor)

        monkeypatch.setattr(FQLAgent, "step", _spy_step)

        _fql_agent_decision(
            env=env, profile=profile, fql_agent=agent, fql_state=state,
            pf_prev=1, year_idx=1, no_governance=True,
        )
        # base/k = 100,000; on the fixed [0, 200,000] grid (bin 10,000)
        # that is state 10, the MIDDLE -- the bug's narrower [0, 100,000]
        # grid (bin 5,000) would clamp the same value to state 20, the TOP.
        actual_state = agent._div_to_state(captured["current_diversion"], state)
        assert actual_state == 10
        assert actual_state != 20


class TestZeroInitKConversion:
    """WP5 review item 6 (round 2, 2026-09-30): a direct, minimal pin on
    create_fql_agents' zero-init prev_diversion -- fails when
    ``state.prev_diversion = init_div / k`` is reverted to
    ``state.prev_diversion = init_div`` (pre-round-2 behavior), isolated
    from item 1's q_grid_top fix (TestUpperBasinUnits above) so each
    broken line is pinned by its own test."""

    def test_ub_prev_diversion_divided_by_k(self):
        profile = IrrigationAgentProfile(
            agent_id="UBAgent", basin="upper_basin", cluster="aggressive",
            water_right=100_000.0, actual_2018_diversion=40_000.0,
            demand_per_grid_unit=0.5, precip_group="WY",
        )
        _, state = create_fql_agents([profile], seed=1, fql_init="zero")["UBAgent"]
        assert state.prev_diversion == pytest.approx(40_000.0 / 0.5)

    def test_lb_prev_diversion_k_is_noop(self):
        profile = IrrigationAgentProfile(
            agent_id="LBAgent", basin="lower_basin", cluster="aggressive",
            water_right=100_000.0, actual_2018_diversion=40_000.0,
            demand_per_grid_unit=1.0,
        )
        _, state = create_fql_agents([profile], seed=1, fql_init="zero")["LBAgent"]
        assert state.prev_diversion == pytest.approx(40_000.0)


@pytest.mark.skipif(
    not _REAL_REF_AVAILABLE,
    reason="CRSS reference data not found under ref/CRSS_DB/CRSS_DB/",
)
class TestCalibratedWarmStartKConversion:
    """WP5 review (2026-09-30, item 1): the calibrated create_fql_agents
    path, on all 56 real Upper Basin agents. Catches the "/k on the warm
    start" and "/k on action_bin_size" mutation injections, neither of
    which the synthetic/hand-built tests above exercise (both need REAL
    div_states_grid/bin_size_af/step_bin_af data)."""

    def test_ub_warm_start_values_and_year1_state(self):
        profiles = create_profiles_from_data(
            params_csv_path=str(CRSS_PARAMS_CSV), crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42), paper_water_margin=0.4,
        )
        ub_profiles = [p for p in profiles if p.basin == "upper_basin"]
        assert ub_profiles

        agents = create_fql_agents(
            profiles, seed=42, fql_init="calibrated",
            fql_init_dir=FQL_INIT_DIR, crss_db_dir=CRSS_DB_DIR,
        )

        state_indices = []
        for p in ub_profiles:
            agent, state = agents[p.agent_id]
            k = float(p.demand_per_grid_unit)
            assert k == pytest.approx(0.5)
            prov = state.init_provenance

            # The three /k warm-start values (create_fql_agents):
            # prev_action, prev_diversion, prev_diversion_request.
            assert state.prev_action == pytest.approx(prov["prev_action"] / k)
            assert state.prev_diversion == pytest.approx(prov["prev_diversion_2017"] / k)
            assert state.prev_diversion_request == pytest.approx(
                state.prev_diversion + state.prev_action
            )
            # WP5 review item 5: prev_action is exactly 0 for every Upper
            # Basin agent (H&Y's own yi==0 override), a stronger, direct
            # check beyond the /k-consistency one above.
            assert state.prev_action == pytest.approx(0.0)

            # action_bin_size = step_bin_af / k (the 5th mutation site).
            assert state.action_bin_size == pytest.approx(float(p.step_bin_af) / k)

            base = float(p.actual_2018_diversion)
            s = _hy_div_to_state(base / k, state.state_bounds, state.hy_bin_size, 21)
            state_indices.append(s)

        median_state = float(np.median(state_indices))
        assert 7 <= median_state <= 13, (
            f"median year-1 Upper Basin state {median_state} not near grid "
            "index 10 -- expected an agent's own 2018 use, correctly "
            "converted to diversion units, to sit roughly mid-grid"
        )


# ── WP5 review item 8c (2026-09-30): prev_diversion_request invariant ──

class TestPrevDiversionRequestInvariant:
    """prev_diversion_request must equal prev_diversion + prev_action
    (fql.py's own convention, step()'s internal formula, and
    tests/test_fql.py's explicit assertion of it) in EVERY construction
    path. The pre-fix create_fql_agents calibrated branch set it to
    init_div/k + prev_action instead, which double-counted prev_action
    for the Lower Basin (prev_action != 0 there): init_div/k already
    equals prev_diversion + prev_action by construction
    (prev_action = (Div_2018-Div_2017)/k, prev_diversion = Div_2017/k,
    summing to Div_2018/k = init_div/k), so adding prev_action again was
    wrong. Harmless in practice (nothing reads this field), but a real
    formula bug the mutation testing in TestRequestFormula/
    TestUpperBasinUnits above does not reach (it is set only at
    construction and after a live decision, never read back into either
    of those code paths)."""

    def test_calibrated_lb_agent_invariant_holds(self):
        if not _REAL_REF_AVAILABLE:
            pytest.skip("CRSS reference data not found under ref/CRSS_DB/CRSS_DB/")
        profiles = create_profiles_from_data(
            params_csv_path=str(CRSS_PARAMS_CSV), crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42), paper_water_margin=0.4,
        )
        lb_profiles = [p for p in profiles if p.basin == "lower_basin"]
        # At least one LB agent must have a nonzero prev_action (not an
        # exact 2017/2018 tie) for this test to be meaningful -- the
        # pre-fix bug is invisible when prev_action == 0.
        agents = create_fql_agents(
            profiles, seed=42, fql_init="calibrated",
            fql_init_dir=FQL_INIT_DIR, crss_db_dir=CRSS_DB_DIR,
        )
        checked_nonzero = False
        for p in lb_profiles:
            _, state = agents[p.agent_id]
            assert state.prev_diversion_request == pytest.approx(
                state.prev_diversion + state.prev_action
            ), f"{p.agent_id}: prev_diversion_request invariant broken"
            if abs(state.prev_action) > 1e-6:
                checked_nonzero = True
        assert checked_nonzero, "no Lower Basin agent had a nonzero prev_action to test against"

    def test_zero_init_both_basins_invariant_holds(self):
        profiles = _create_synthetic_profiles(4, seed=1)
        agents = create_fql_agents(profiles, seed=1, fql_init="zero")
        for p in profiles:
            _, state = agents[p.agent_id]
            assert state.prev_diversion_request == pytest.approx(
                state.prev_diversion + state.prev_action
            ), f"{p.agent_id}: prev_diversion_request invariant broken (zero-init)"


# ── spec 5.6: governed ("FQL plus rules") dispatch falls back to keep only ──

class TestFQLPlusRulesDispatch:
    def test_validate_skill_falls_back_to_keep_only(self, monkeypatch):
        """A blocked increase falls back to maintain_demand ONLY -- no
        further "last resort" tier. Forcing EVERY skill (including
        maintain_demand) to fail via a fake check still returns
        maintain_demand, not decrease_demand, proving the old 2-tier
        cascade (... -> decrease_demand) is gone."""
        def _block_everything(skill_name, rules, context):
            return [ValidationResult(valid=False, validator_name="test_fake_block_everything")]

        monkeypatch.setattr(run_fql_baseline_module, "ALL_IRRIGATION_CHECKS", [_block_everything])

        valid, skill = validate_skill("increase_demand", {})
        assert valid is True
        assert skill == "maintain_demand"

    def test_blocked_increase_reverts_request_to_base(self, monkeypatch):
        """When governance blocks the FQL's proposed change, the ACTUAL
        request written to the environment reverts to Div_t (keep), not
        just the logged skill label."""
        env, profile = _make_single_agent_env(
            basin="lower_basin", water_right=100_000.0,
            actual_2018_diversion=40_000.0, demand_per_grid_unit=1.0,
        )
        aid = profile.agent_id
        env.advance_year()
        div_t = float(env.get_agent_state(aid)["base_af"])

        config = FQLConfig(mu=0.4, sigma=0.5, alpha=0.7, gamma=0.7, epsilon=0.15, regret=1.5)
        state = FQLState(state_bounds=np.linspace(0, 100_000, 21))
        state.initialize(config)
        agent = FQLAgent(config, rng=np.random.default_rng(0))

        monkeypatch.setattr(
            run_fql_baseline_module, "validate_skill",
            lambda skill_name, context: (True, "maintain_demand"),
        )

        decision = _fql_agent_decision(
            env=env, profile=profile, fql_agent=agent, fql_state=state,
            pf_prev=1, year_idx=1, no_governance=False,
        )
        # sigma=0.5 (nonzero) from seed 0 makes an exact-zero draw
        # vanishingly unlikely, so the mocked validate_skill (always
        # "maintain_demand") blocks whatever raw_skill actually was.
        assert decision["was_blocked"] is True
        assert decision["final_skill"] == "maintain_demand"
        assert env.get_agent_state(aid)["request"] == pytest.approx(div_t)
        assert decision["action"] == pytest.approx(0.0)
        # WP5 review (2026-09-30, item 3, round 3): prev_action must ALSO
        # revert to 0 on a block, not just the request and the logged
        # action -- otherwise next year's Bayesian update would credit a
        # nonzero action that was never actually executed.
        assert state.prev_action == pytest.approx(0.0)
        # WP5 review (item 3, round 3): fql_action_precap (item 8b, round
        # 2) keeps the RAW sampled delta even when governance blocks it --
        # it must differ from the (zeroed) executed action, or the column
        # would be indistinguishable from fql_action and item 8b's whole
        # point (seeing how often/how much clipping bites) would be lost.
        assert decision["action_precap"] != pytest.approx(0.0)
        assert decision["action_precap"] != decision["action"]


# ── determinism: same seed -> same output; different seeds -> different ──

class TestDeterminism:
    @staticmethod
    def _run(seed: int, n_years: int = 2, n_agents: int = 4) -> List[Dict[str, Any]]:
        profiles = _create_synthetic_profiles(n_agents, seed=seed)
        config = WaterSystemConfig(seed=seed)
        env = IrrigationEnvironment(config)
        env.initialize_from_profiles(profiles)
        fql_agents = create_fql_agents(profiles, seed=seed, fql_init="zero")
        profiles_dict = {p.agent_id: p for p in profiles}
        with tempfile.TemporaryDirectory() as tmpdir:
            logs = run_simulation(
                env=env, fql_agents=fql_agents, profiles=profiles_dict,
                n_years=n_years, output_dir=Path(tmpdir), seed=seed,
            )
        return logs

    def test_same_seed_same_output(self):
        logs_a = self._run(seed=42)
        logs_b = self._run(seed=42)
        assert len(logs_a) == len(logs_b) > 0
        for row_a, row_b in zip(logs_a, logs_b):
            assert row_a["agent_id"] == row_b["agent_id"]
            assert row_a["yearly_decision"] == row_b["yearly_decision"]
            assert row_a["request"] == pytest.approx(row_b["request"])
            assert row_a["fql_action"] == pytest.approx(row_b["fql_action"])

    def test_different_seeds_differ(self):
        logs_a = self._run(seed=42)
        logs_c = self._run(seed=43)
        requests_a = [r["request"] for r in logs_a]
        requests_c = [r["request"] for r in logs_c]
        assert requests_a != pytest.approx(requests_c)


# ── WP5 review item 3, round 2; item 2, round 3 (2026-09-30): trajectory goldens ──

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _assert_matches_golden(fresh: pd.DataFrame, golden_csv: Path, golden_meta: Path) -> None:
    """Compare a fresh (agent_id, year, request, diversion, fql_action)
    trajectory against a checked-in golden fixture.

    WP5 review (item 2, round 3, 2026-09-30):
    - The numpy version is read from the golden's own sidecar .meta.json,
      never hardcoded in this file (round 2 hardcoded "2.4.2" twice,
      independently of the fixture, which could silently drift from it).
    - A version mismatch FAILS (pytest.fail), it does not skip: a skip
      would quietly let a real numeric regression through on any machine
      running a different numpy, which is exactly the failure mode a
      golden exists to catch. Regenerating the golden is a human decision.
    - Row count is asserted directly on the two (sorted) frames, not on
      an inner merge's result -- an inner merge silently DROPS rows with
      no match on the other side, so len(merged) can still equal
      len(golden) even when the fresh run is missing or has duplicated
      agent-year rows (a different, worse bug a merge-based check hides).
    - np.testing.assert_allclose(rtol=0, atol=1e-9, equal_nan=False) --
      not pytest.approx -- compares the full numeric arrays explicitly,
      and a NaN on either side fails the comparison outright rather than
      being treated as a possible match.
    """
    with open(golden_meta, encoding="utf-8") as f:
        meta = json.load(f)
    golden_numpy_version = meta["numpy_version"]
    if np.__version__ != golden_numpy_version:
        pytest.fail(
            f"{golden_csv.name} was captured under numpy "
            f"{golden_numpy_version!r}; running under {np.__version__!r}, "
            "which can differ at ULP level -- regenerate the golden (see "
            "its sidecar .meta.json) rather than silently accept the drift."
        )

    golden = pd.read_csv(golden_csv).sort_values(["agent_id", "year"]).reset_index(drop=True)
    fresh = fresh.sort_values(["agent_id", "year"]).reset_index(drop=True)
    assert len(fresh) == len(golden), (
        f"row count mismatch against {golden_csv.name}: "
        f"fresh={len(fresh)} golden={len(golden)}"
    )
    assert (fresh["agent_id"].to_numpy() == golden["agent_id"].to_numpy()).all(), (
        f"agent_id ordering/membership mismatch against {golden_csv.name}"
    )
    assert (fresh["year"].to_numpy() == golden["year"].to_numpy()).all(), (
        f"year ordering/membership mismatch against {golden_csv.name}"
    )
    for col in ("request", "diversion", "fql_action"):
        np.testing.assert_allclose(
            fresh[col].to_numpy(dtype=float),
            golden[col].to_numpy(dtype=float),
            rtol=0, atol=1e-9, equal_nan=False,
            err_msg=f"column {col!r} diverged from {golden_csv.name}",
        )


class TestSyntheticTrajectoryGolden:
    """Always runs (no ref/ dependency) -- a small, fully synthetic
    4-agent, 3-year trajectory (--fql-init zero, seed 7) pinned to 1e-9
    against examples/irrigation_abm/tests/fixtures/
    fql_v3_synthetic_zero_init_seed7_3yr_golden.csv (see the sidecar
    .meta.json). Complements TestRealTrajectoryGolden below (which is
    skipped without ref/ data): this one catches a request-setting/
    RNG-seeding regression on every machine, every run, not only where
    CRSS reference data happens to be checked out."""

    _GOLDEN_CSV = _FIXTURE_DIR / "fql_v3_synthetic_zero_init_seed7_3yr_golden.csv"
    _GOLDEN_META = _FIXTURE_DIR / "fql_v3_synthetic_zero_init_seed7_3yr_golden.meta.json"

    def test_synthetic_trajectory_matches_golden(self):
        seed = 7
        profiles = _create_synthetic_profiles(4, seed=seed)
        config = WaterSystemConfig(seed=seed)
        env = IrrigationEnvironment(config)
        env.initialize_from_profiles(profiles)
        fql_agents = create_fql_agents(profiles, seed=seed, fql_init="zero")
        profiles_dict = {p.agent_id: p for p in profiles}
        with tempfile.TemporaryDirectory() as tmpdir:
            logs = run_simulation(
                env=env, fql_agents=fql_agents, profiles=profiles_dict,
                n_years=3, output_dir=Path(tmpdir), seed=seed,
            )
        fresh = pd.DataFrame(logs)[["agent_id", "year", "request", "diversion", "fql_action"]]
        _assert_matches_golden(fresh, self._GOLDEN_CSV, self._GOLDEN_META)


@pytest.mark.skipif(
    not _REAL_REF_AVAILABLE,
    reason="CRSS reference data not found under ref/CRSS_DB/CRSS_DB/",
)
class TestRealTrajectoryGolden:
    """A seed-42, 5-year, real 78-agent calibrated FQL reference run
    (--no-governance, WP7 7.5's own command), pinned to 1e-9 against
    examples/irrigation_abm/tests/fixtures/
    fql_v3_real_calibrated_seed42_5yr_golden.csv (see the sidecar
    .meta.json)."""

    _GOLDEN_CSV = _FIXTURE_DIR / "fql_v3_real_calibrated_seed42_5yr_golden.csv"
    _GOLDEN_META = _FIXTURE_DIR / "fql_v3_real_calibrated_seed42_5yr_golden.meta.json"

    def test_five_year_seed42_matches_golden(self, tmp_path):
        script = PROJECT_ROOT / "examples" / "irrigation_abm" / "run_fql_baseline.py"
        result = subprocess.run(
            [
                sys.executable, str(script), "--real", "--no-governance",
                "--fql-init", "calibrated", "--years", "5", "--seed", "42",
                "--output", str(tmp_path),
            ],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=300,
        )
        assert result.returncode == 0, result.stderr

        df = pd.read_csv(tmp_path / "simulation_log.csv")
        fresh = df[["agent_id", "year", "request", "diversion", "fql_action"]]
        assert len(fresh) == 78 * 5
        _assert_matches_golden(fresh, self._GOLDEN_CSV, self._GOLDEN_META)


# ── WP5 review item 3 (round 3, 2026-09-30): fql_action_precap column ──

class TestPrecapColumn:
    def test_precap_differs_from_executed_on_a_capped_increase(self):
        """WP5 review (2026-09-30, round 4, item 4): a DETERMINISTIC capped
        increase, not a probabilistic one -- epsilon=0 with a freshly
        zero-initialised Q-table (q_decrease == q_increase == 0) makes
        _epsilon_greedy's own "<=" tie rule always choose the increase
        branch, and mu=5.0 on a 5,000 af bin guarantees a raw magnitude
        (>=25,000 af) far beyond the 1,000 af headroom to the water-right
        cap. fql_action_precap (the RAW, pre-cap delta) must then differ
        from fql_action (the EXECUTED, post-cap delta): this test FAILS if
        a bug writes the executed value into the precap column too."""
        env, profile = _make_single_agent_env(
            basin="lower_basin", water_right=100_000.0,
            actual_2018_diversion=99_000.0, demand_per_grid_unit=1.0,
        )
        aid = profile.agent_id
        env.advance_year()
        base = float(env.get_agent_state(aid)["base_af"])
        assert base == pytest.approx(99_000.0)

        config = FQLConfig(mu=5.0, sigma=0.1, alpha=0.7, gamma=0.7, epsilon=0.0, regret=1.5)
        state = FQLState(state_bounds=np.linspace(0, 100_000, 21))  # bin_size = 5,000
        state.initialize(config)
        agent = FQLAgent(config, rng=np.random.default_rng(0))

        decision = _fql_agent_decision(
            env=env, profile=profile, fql_agent=agent, fql_state=state,
            pf_prev=1, year_idx=1, no_governance=True,
        )
        assert decision["final_skill"] == "increase_demand"
        assert env.get_agent_state(aid)["request"] == pytest.approx(100_000.0)
        # Executed: capped at the water right (1,000 af of headroom).
        assert decision["action"] == pytest.approx(1_000.0)
        # Raw: far beyond the cap, and NOT equal to the executed value.
        assert decision["action_precap"] > 20_000.0
        assert decision["action_precap"] != pytest.approx(decision["action"])

    def test_fql_action_precap_present_on_every_row(self):
        """Structural check on the full run_simulation/CSV pipeline (not
        just _fql_agent_decision's own dict key): every row carries a
        finite fql_action_precap, governed or not."""
        seed = 7
        profiles = _create_synthetic_profiles(4, seed=seed)
        config = WaterSystemConfig(seed=seed)
        env = IrrigationEnvironment(config)
        env.initialize_from_profiles(profiles)
        fql_agents = create_fql_agents(profiles, seed=seed, fql_init="zero")
        profiles_dict = {p.agent_id: p for p in profiles}
        with tempfile.TemporaryDirectory() as tmpdir:
            logs = run_simulation(
                env=env, fql_agents=fql_agents, profiles=profiles_dict,
                n_years=2, output_dir=Path(tmpdir), seed=seed,
                no_governance=False,
            )
        assert logs
        assert all("fql_action_precap" in row for row in logs)
        assert all(np.isfinite(row["fql_action_precap"]) for row in logs)


# ── WP5 review item 3 (round 3, 2026-09-30): manifest provenance pins ──

class TestManifestProvenance:
    def test_synthetic_run_manifest_has_git_checksums_and_config(self, tmp_path):
        """The round-2/3 manifest additions (git HEAD/dirty, the pinned
        v3 data checksums including the round-3 additions, the full
        water-system config dump) do not need --real or ref/ data --
        crss_db_input_checksums is the ONLY --real-gated field, and must
        be an empty dict (not populated, not missing) on a synthetic run."""
        script = PROJECT_ROOT / "examples" / "irrigation_abm" / "run_fql_baseline.py"
        result = subprocess.run(
            [
                sys.executable, str(script), "--agents", "3", "--years", "1",
                "--seed", "1", "--fql-init", "zero", "--output", str(tmp_path),
            ],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr
        with open(tmp_path / "reproducibility_manifest.json", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "git_head" in manifest
        assert "git_dirty" in manifest

        pinned = manifest["pinned_v3_data_checksums"]
        assert isinstance(pinned, dict)
        for key in (
            "hydrology_v3_csv", "mead_capacity_usbr2009_1ft_csv",
            "ub_subbasin_supply_v3_csv", "ub_subbasin_supply_v3_variant",
            "ub_subbasin_envelope_v3_csv", "ub_subbasin_variant_means_v3_csv",
            "lb_priority_split_v3_csv",
        ):
            assert key in pinned, f"pinned_v3_data_checksums missing {key}"
        assert pinned["ub_subbasin_supply_v3_variant"] == "recommended"

        config = manifest["water_system_config"]
        assert isinstance(config, dict)
        assert "ub_supply_mode" in config
        assert "lb_priority_mode" in config

        assert manifest["crss_db_input_checksums"] == {}

    def test_pinned_checksum_follows_the_active_variant_not_the_default(self):
        """WP5 review item 4 (round 3): a run on a non-default Upper Basin
        supply variant (rho_0_2) must record THAT variant's own checksum,
        not always "recommended"'s -- the two differ, so this fails if the
        function silently falls back to the default regardless of what is
        passed in."""
        from examples.irrigation_abm.run_fql_baseline import _pinned_v3_data_checksums

        recommended = _pinned_v3_data_checksums("recommended")
        rho02 = _pinned_v3_data_checksums("rho_0_2")
        assert recommended["ub_subbasin_supply_v3_csv"] != rho02["ub_subbasin_supply_v3_csv"]
        assert rho02["ub_subbasin_supply_v3_variant"] == "rho_0_2"
        # Everything else (hydrology, Mead, envelope, variant means, LB
        # priority split) is variant-independent and must be unchanged.
        for key in (
            "hydrology_v3_csv", "mead_capacity_usbr2009_1ft_csv",
            "ub_subbasin_envelope_v3_csv", "ub_subbasin_variant_means_v3_csv",
            "lb_priority_split_v3_csv",
        ):
            assert recommended[key] == rho02[key]

    def test_manifest_write_failure_is_fatal_for_real(self, tmp_path):
        """WP5 review item 2 (round 2); item 3 (round 3): the extracted
        _write_reproducibility_manifest raises on a --real run when the
        write itself fails -- here, output_dir's own parent does not
        exist, so open() raises."""
        bad_dir = tmp_path / "does_not_exist_parent" / "sub"
        with pytest.raises(OSError):
            run_fql_baseline_module._write_reproducibility_manifest(
                {"a": 1}, bad_dir, is_real=True,
            )

    def test_manifest_write_failure_only_warns_for_synthetic(self, tmp_path, capsys):
        """The SAME write failure must NOT raise for is_real=False -- only
        a WARNING is printed."""
        bad_dir = tmp_path / "does_not_exist_parent" / "sub"
        run_fql_baseline_module._write_reproducibility_manifest(
            {"a": 1}, bad_dir, is_real=False,
        )
        captured = capsys.readouterr()
        assert "WARNING" in captured.out
        assert "could not write reproducibility_manifest.json" in captured.out

    def test_k_raise_for_missing_demand_per_grid_unit(self):
        """WP5 review item 8a (round 2); item 3 (round 3): a profile with
        no demand_per_grid_unit must raise, not silently default to 1.0
        (which would be a substantive, wrong model value for an Upper
        Basin agent, not a harmless 'no conversion' default)."""
        profile = IrrigationAgentProfile(
            agent_id="NoK", basin="upper_basin", cluster="aggressive",
            water_right=100_000.0,
        )
        assert profile.demand_per_grid_unit is None
        with pytest.raises(ValueError, match="demand_per_grid_unit"):
            run_fql_baseline_module._resolve_demand_per_grid_unit(profile)


# ── acceptance: a short real, calibrated FQL reference run ──

@pytest.mark.skipif(
    not _REAL_REF_AVAILABLE,
    reason="CRSS reference data not found under ref/CRSS_DB/CRSS_DB/",
)
class TestRealShortRun:
    def test_three_year_real_run_log_and_manifest_complete(self, tmp_path):
        """WP7 7.5's own FQL-reference command
        (`--real --no-governance --fql-init calibrated`), 3 years instead
        of 42: the log columns and the manifest's WP5 essentials
        ("--fql-init, the table directory, the water-system config fields
        and the seed") must all be present."""
        script = PROJECT_ROOT / "examples" / "irrigation_abm" / "run_fql_baseline.py"
        result = subprocess.run(
            [
                sys.executable, str(script), "--real", "--no-governance",
                "--fql-init", "calibrated", "--years", "3", "--seed", "42",
                "--output", str(tmp_path),
            ],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=300,
        )
        assert result.returncode == 0, result.stderr

        csv_path = tmp_path / "simulation_log.csv"
        assert csv_path.is_file()
        df = pd.read_csv(csv_path)
        assert len(df) == 78 * 3

        required_cols = {
            "agent_id", "year", "cluster", "basin", "yearly_decision",
            "request", "diversion", "water_right", "base_af",
            "fql_raw_skill", "fql_action", "fql_action_precap", "fql_blocked",
            "natural_flow_maf", "mead_storage_maf", "lake_mead_level",
        }
        missing = required_cols - set(df.columns)
        assert not missing, f"missing log columns: {missing}"
        assert df["base_af"].notna().all()
        assert (df["request"] <= df["water_right"] + 1e-6).all()

        manifest_path = tmp_path / "reproducibility_manifest.json"
        assert manifest_path.is_file()
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        for field in (
            "fql_init", "fql_init_dir", "fql_init_dir_name",
            "hold_requests_fixed", "powell_release_mode",
            "lb_non_ag_total_maf", "ub_supply_mode",
            "ub_subbasin_supply_variant", "lb_priority_mode", "seed",
            "fql_init_per_agent",
            # WP5 review (item 3, round 3, 2026-09-30): the round-2/3
            # provenance additions, checked here too since this is a real
            # --real run (crss_db_input_checksums is only populated then).
            "git_head", "git_dirty", "crss_db_input_checksums",
            "pinned_v3_data_checksums", "water_system_config",
        ):
            assert field in manifest, f"manifest missing field: {field}"
        for key in (
            "prism_winter_precip_csv", "ub_discrete_states_csv",
            "lb_discrete_states_csv", "ub_historical_annual_depletion_csv",
            "lb_historical_annual_diversion_csv", "ub_abm_groups_and_agents_csv",
        ):
            assert manifest["crss_db_input_checksums"].get(key), (
                f"crss_db_input_checksums missing or empty for {key} on a --real run"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
