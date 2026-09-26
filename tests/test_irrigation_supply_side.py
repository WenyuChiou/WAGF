"""Supply-side redesign (2026-09-25): Lake Powell storage buffer, Lake Mead
deliveries limited by availability, pro-rata sharing, idempotent settlement.

Spec: .research/design_specs/irrigation_scenario_redesign_2026-09-25.md
(simplified version: storage buffer with a minimum release, no Interim
Guidelines release tiers).
"""
from types import SimpleNamespace

import numpy as np
import pytest

from examples.irrigation_abm.irrigation_env import (
    CRSS_DEMAND_TARGET_AF,
    IrrigationEnvironment,
    WaterSystemConfig,
)


def _agent(basin: str, request: float, water_right: float = 4_000_000.0) -> dict:
    return {
        "basin": basin,
        "diversion": request,
        "request": request,
        "water_right": water_right,
        "curtailment_ratio": 0.0,
        "delivery_ratio": 1.0,
        "gap_reason": "none",
        "at_allocation_cap": False,
        "has_efficient_system": False,
        "below_minimum_utilisation": False,
        "cluster": "aggressive",
        "persona_scale": 1.0,
        "skill_magnitude": {},
        "magnitude_default": 0.0,
        "magnitude_sigma": 0.0,
        "magnitude_min": 1.0,
        "magnitude_max": 30.0,
        "exploration_rate": 0.0,
    }


def _env(ub=(1_500_000.0, 1_500_000.0), lb=(1_300_000.0, 1_300_000.0)) -> IrrigationEnvironment:
    env = IrrigationEnvironment(WaterSystemConfig(seed=42))
    for i, r in enumerate(ub):
        env._agents[f"UB{i}"] = _agent("upper_basin", r)
    for i, r in enumerate(lb):
        env._agents[f"LB{i}"] = _agent("lower_basin", r)
    return env


def _balance_error(st: dict) -> float:
    lhs = (st["powell_storage_end_maf"] - st["powell_storage_maf"]) + (
        st["mead_storage_end_maf"] - st["mead_storage_maf"])
    withdrawals = st["lb_delivered_maf"] + st["lb_non_ag_delivered_maf"] + st["mexico_delivered_maf"]
    rhs = (st["natural_flow_maf"] + st["lb_tributary_maf"] - st["ub_delivered_maf"]
           - st["powell_evap_maf"] - st["mead_evap_maf"] - withdrawals - st["mead_spill_maf"])
    return lhs - rhs


def _random_snapshot(rng, cfg):
    return {
        "powell_storage": float(rng.uniform(cfg.powell_dead_pool_maf, cfg.powell_capacity_maf)),
        "mead_storage": float(rng.uniform(cfg.mead_dead_pool_maf, cfg.mead_capacity_maf)),
        "natural_flow": float(rng.uniform(6.0, 17.0)),
        "lb_cut": float(rng.choice([0.0, 0.05, 0.10, 0.20])),
        "mexico": float(rng.uniform(1.225, 1.5)),
    }


class TestMassBalance:
    def test_conservation_and_bounds_random_states(self):
        """T1: for 3,000 random states and request vectors, the two-reservoir
        identity closes to 1e-9 MAF and both storages stay within their dead
        pool and full pool."""
        rng = np.random.default_rng(7)
        env = _env()
        cfg = env.config
        for _ in range(3000):
            for aid in env._agents:
                env._agents[aid]["request"] = float(rng.uniform(0.0, 2_000_000.0))
            snap = _random_snapshot(rng, cfg)
            st = env._settle(snap)
            assert abs(_balance_error(st)) < 1e-9
            assert cfg.powell_dead_pool_maf - 1e-9 <= st["powell_storage_end_maf"] <= cfg.powell_capacity_maf + 1e-9
            assert cfg.mead_dead_pool_maf - 1e-9 <= st["mead_storage_end_maf"] <= cfg.mead_capacity_maf + 1e-9

    def test_extreme_low_states_close(self):
        """Both reservoirs at dead pool, lowest flow: still closes, nothing
        goes below a dead pool."""
        env = _env()
        cfg = env.config
        snap = {"powell_storage": cfg.powell_dead_pool_maf, "mead_storage": cfg.mead_dead_pool_maf,
                "natural_flow": 6.0, "lb_cut": 0.20, "mexico": 1.225}
        st = env._settle(snap)
        assert abs(_balance_error(st)) < 1e-9
        assert st["mead_storage_end_maf"] >= cfg.mead_dead_pool_maf - 1e-12
        assert st["powell_storage_end_maf"] >= cfg.powell_dead_pool_maf - 1e-12

    def test_multi_year_run_closes_every_year(self):
        env = IrrigationEnvironment(WaterSystemConfig(seed=3))
        env.initialize_synthetic(n_agents=20, basin_split=(8, 12))
        for _ in range(42):
            env.advance_year()
            st = env.settle_year()
            assert abs(_balance_error(st)) < 1e-9


class TestDeliveriesWithinAvailability:
    def test_ub_never_exceeds_capacity_flow_or_request(self):
        """T3 (Powell side): D_U <= min(request, 5.0 MAF, what leaves Powell
        its minimum release), and every agent receives at most its request."""
        rng = np.random.default_rng(11)
        env = _env(ub=(3_000_000.0, 3_000_000.0))  # 6.0 MAF > 5.0 capacity
        cfg = env.config
        for _ in range(500):
            snap = _random_snapshot(rng, cfg)
            st = env._settle(snap)
            room = snap["natural_flow"] + (snap["powell_storage"] - cfg.powell_dead_pool_maf) \
                - st["powell_evap_maf"] - cfg.min_powell_release_maf
            assert st["ub_delivered_maf"] <= min(st["ub_request_maf"], cfg.ub_infrastructure_cap_maf) + 1e-12
            assert st["ub_delivered_maf"] <= max(0.0, room) + 1e-12
            for rec in st["agents"].values():
                assert rec["delivered"] <= rec["request"] + 1e-6

    def test_mead_withdrawals_within_available(self):
        """T3 (Mead side): LB ag + non-ag + Mexico <= storage above dead pool
        + release + tributaries - evaporation."""
        rng = np.random.default_rng(12)
        env = _env(lb=(2_000_000.0, 2_000_000.0))
        cfg = env.config
        for _ in range(500):
            snap = _random_snapshot(rng, cfg)
            st = env._settle(snap)
            withdrawals = st["lb_delivered_maf"] + st["lb_non_ag_delivered_maf"] + st["mexico_delivered_maf"]
            available = (snap["mead_storage"] - cfg.mead_dead_pool_maf) + st["powell_release_maf"] \
                + cfg.lb_tributary_maf - st["mead_evap_maf"]
            assert withdrawals <= available + 1e-9

    def test_mead_short_scales_pro_rata(self):
        """Mead near dead pool with a low release: phi < 1, and every Lower
        Basin withdrawal (ag, non-ag, Mexico) is scaled by the same phi."""
        env = _env(lb=(1_000_000.0, 3_000_000.0))
        cfg = env.config
        snap = {"powell_storage": cfg.powell_dead_pool_maf + 0.5, "mead_storage": 2.3,
                "natural_flow": 6.0, "lb_cut": 0.0, "mexico": 1.5}
        st = env._settle(snap)
        phi = st["lb_phys_ratio"]
        assert 0.0 < phi < 1.0
        assert st["agents"]["LB0"]["delivery_ratio"] == pytest.approx(phi)
        assert st["agents"]["LB1"]["delivery_ratio"] == pytest.approx(phi)
        assert st["mexico_delivered_maf"] == pytest.approx(1.5 * phi)
        assert st["mead_storage_end_maf"] == pytest.approx(cfg.mead_dead_pool_maf)
        assert st["agents"]["LB0"]["gap_reason"] == "lb_mead_availability"


class TestProRata:
    def test_ub_pro_rata_sums_to_delivered(self):
        """T2: UB deliveries sum to D_U and every UB ratio is equal."""
        env = _env(ub=(1_000_000.0, 2_000_000.0, 3_000_000.0))  # 6.0 > 5.0 capacity
        snap = {"powell_storage": 15.0, "mead_storage": 12.0, "natural_flow": 12.0,
                "lb_cut": 0.0, "mexico": 1.5}
        st = env._settle(snap)
        ub = [st["agents"][f"UB{i}"] for i in range(3)]
        assert sum(r["delivered"] for r in ub) / 1e6 == pytest.approx(st["ub_delivered_maf"])
        assert st["ub_delivered_maf"] == pytest.approx(5.0)
        ratios = {round(r["delivery_ratio"], 12) for r in ub}
        assert len(ratios) == 1
        assert ub[0]["gap_reason"] == "ub_capacity"

    def test_lb_tier_cut_applies_to_whole_lower_basin(self):
        """Q1: the declared cut reduces agricultural agents AND the 5.0 MAF
        non-agricultural bucket; Upper Basin agents are not cut (Q2)."""
        env = _env()
        snap = {"powell_storage": 15.0, "mead_storage": 12.0, "natural_flow": 12.0,
                "lb_cut": 0.10, "mexico": 1.396}
        st = env._settle(snap)
        assert st["lb_phys_ratio"] == 1.0
        assert st["lb_non_ag_delivered_maf"] == pytest.approx(5.0 * 0.90)
        lb_sum = sum(st["agents"][f"LB{i}"]["delivered"] for i in range(2)) / 1e6
        assert lb_sum == pytest.approx(st["lb_request_maf"] * 0.90)
        assert st["agents"]["LB0"]["gap_reason"] == "lb_shortage_tier"
        assert st["agents"]["UB0"]["delivery_ratio"] == 1.0


class TestUpperBasinNotZeroed:
    def test_low_natural_flow_does_not_zero_ub_when_powell_has_storage(self):
        """The old model set UB = max(0, NF - 7.0) = 0 in a 6.0 MAF year
        (2022). With Powell storage covering the minimum release, UB keeps
        its full request."""
        env = _env()
        snap = {"powell_storage": 9.62, "mead_storage": 9.0, "natural_flow": 6.0,
                "lb_cut": 0.20, "mexico": 1.225}
        st = env._settle(snap)
        assert st["ub_delivered_maf"] == pytest.approx(st["ub_request_maf"])
        assert st["powell_release_maf"] == pytest.approx(7.0)

    def test_low_powell_cuts_ub_pro_rata_but_not_to_zero(self):
        """Powell with little usable storage in a 6.0 MAF year: UB is cut
        (pro-rata) so Powell can still release 7.0, but not zeroed."""
        env = _env()
        cfg = env.config
        snap = {"powell_storage": cfg.powell_dead_pool_maf + 2.0, "mead_storage": 9.0,
                "natural_flow": 6.0, "lb_cut": 0.20, "mexico": 1.225}
        st = env._settle(snap)
        assert 0.0 < st["ub_delivered_maf"] < st["ub_request_maf"]
        ratios = [st["agents"][f"UB{i}"]["delivery_ratio"] for i in range(2)]
        assert 0.0 < ratios[0] < 1.0 and ratios[0] == pytest.approx(ratios[1])
        assert st["powell_release_maf"] == pytest.approx(7.0)
        assert st["agents"]["UB0"]["gap_reason"] == "ub_powell_release"

    def test_powell_empty_releases_what_is_available(self):
        """Powell at dead pool and flow below 7.0: UB gets 0 and the release
        is the flow net of evaporation (below the 7.0 MAF minimum)."""
        env = _env()
        cfg = env.config
        snap = {"powell_storage": cfg.powell_dead_pool_maf, "mead_storage": 9.0,
                "natural_flow": 6.0, "lb_cut": 0.20, "mexico": 1.225}
        st = env._settle(snap)
        assert st["ub_delivered_maf"] == 0.0
        assert st["powell_release_maf"] == pytest.approx(6.0 - st["powell_evap_maf"])
        assert st["powell_storage_end_maf"] == pytest.approx(cfg.powell_dead_pool_maf)

    def test_normal_year_release_equals_pass_through(self):
        """Options (c)/(d), decision 2026-09-26: when natural flow minus
        Upper Basin use is within [7.0, 9.0] MAF, Powell releases exactly
        that, and its storage does not creep upward (it only loses
        evaporation)."""
        env = _env()
        cfg = env.config
        for s0 in (5.0, 12.0, cfg.powell_capacity_maf):
            snap = {"powell_storage": s0, "mead_storage": 12.0, "natural_flow": 11.0,
                    "lb_cut": 0.0, "mexico": 1.5}
            st = env._settle(snap)
            pass_through = st["natural_flow_maf"] - st["ub_delivered_maf"]
            assert 7.0 <= pass_through <= 9.0
            assert st["powell_release_maf"] == pytest.approx(pass_through)
            assert st["powell_storage_end_maf"] == pytest.approx(s0 - st["powell_evap_maf"])
            assert st["powell_storage_end_maf"] <= s0
            assert st["powell_spill_maf"] == 0.0

    def test_dry_year_storage_tops_release_up_to_minimum(self):
        """Pass-through below 7.0 with storage available: release is exactly
        7.0 and the shortfall comes out of storage; the Upper Basin keeps
        its request."""
        env = _env()
        snap = {"powell_storage": 12.0, "mead_storage": 12.0, "natural_flow": 8.0,
                "lb_cut": 0.0, "mexico": 1.5}
        st = env._settle(snap)
        pass_through = 8.0 - st["ub_delivered_maf"]
        assert pass_through < 7.0
        assert st["ub_delivered_maf"] == pytest.approx(st["ub_request_maf"])
        assert st["powell_release_maf"] == pytest.approx(7.0)
        assert st["powell_storage_end_maf"] == pytest.approx(
            12.0 + pass_through - st["powell_evap_maf"] - 7.0)


    @staticmethod
    def _target(cfg):
        return cfg.powell_dead_pool_maf + cfg.powell_target_fill * (
            cfg.powell_capacity_maf - cfg.powell_dead_pool_maf)

    def test_wet_year_below_target_retains_excess(self):
        """Option (e), as (d) below the target fill: release 9.0 and storage
        rises by pass_through - 9.0 minus evaporation."""
        env = _env()
        snap = {"powell_storage": 5.0, "mead_storage": 12.0, "natural_flow": 15.0,
                "lb_cut": 0.0, "mexico": 1.5}
        st = env._settle(snap)
        pass_through = 15.0 - st["ub_delivered_maf"]
        assert pass_through > 9.0
        assert st["powell_release_maf"] == pytest.approx(9.0)
        assert st["powell_storage_end_maf"] == pytest.approx(
            5.0 + (pass_through - 9.0) - st["powell_evap_maf"])
        assert st["powell_storage_end_maf"] < self._target(env.config)
        assert st["powell_spill_maf"] == 0.0
        assert abs(_balance_error(st)) < 1e-9

    def test_wet_year_above_target_passes_through(self):
        """Option (e), as (c) above the target fill: the whole inflow passes
        through and storage only loses evaporation."""
        env = _env()
        cfg = env.config
        s0 = self._target(cfg) + 3.0
        snap = {"powell_storage": s0, "mead_storage": 12.0, "natural_flow": 15.0,
                "lb_cut": 0.0, "mexico": 1.5}
        st = env._settle(snap)
        pass_through = 15.0 - st["ub_delivered_maf"]
        assert st["powell_release_maf"] == pytest.approx(pass_through)
        assert st["powell_storage_end_maf"] == pytest.approx(s0 - st["powell_evap_maf"])
        assert st["powell_spill_maf"] == 0.0

    def test_wet_year_crossing_target_retains_only_up_to_target(self):
        env = _env()
        cfg = env.config
        s0 = self._target(cfg) - 1.0
        snap = {"powell_storage": s0, "mead_storage": 12.0, "natural_flow": 15.0,
                "lb_cut": 0.0, "mexico": 1.5}
        st = env._settle(snap)
        pass_through = 15.0 - st["ub_delivered_maf"]
        assert pass_through - 9.0 > 1.0 + st["powell_evap_maf"]  # would overshoot at 9.0
        assert st["powell_storage_end_maf"] == pytest.approx(self._target(cfg))
        assert 9.0 < st["powell_release_maf"] < pass_through
        assert abs(_balance_error(st)) < 1e-9

    def test_storage_above_capacity_spills_into_release(self):
        """A snapshot already above full pool spills into the release in a
        normal year and still closes the balance."""
        env = _env()
        cfg = env.config
        snap = {"powell_storage": cfg.powell_capacity_maf + 1.5, "mead_storage": 9.0,
                "natural_flow": 11.0, "lb_cut": 0.0, "mexico": 1.5}
        st = env._settle(snap)
        assert st["powell_spill_maf"] > 0.0
        assert st["powell_storage_end_maf"] == pytest.approx(cfg.powell_capacity_maf)
        assert abs(_balance_error(st)) < 1e-9


class TestSettleIdempotence:
    def test_second_settle_is_bitwise_identical(self):
        """T4: settle_year() twice gives identical agents and settlement."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=5))
        env.initialize_synthetic(n_agents=10, basin_split=(4, 6))
        env.advance_year()
        first = env.settle_year()
        agents_first = {a: dict(v) for a, v in env._agents.items()}
        second = env.settle_year()
        assert agents_first == env._agents
        assert first == second

    def test_unexecuted_agent_equals_maintain(self):
        """The F11b regression on the new physics: two equal UB agents under
        a binding limit, one executes maintain_demand, one never executes;
        both end with the same delivery."""
        env = _env(ub=(3_000_000.0, 3_000_000.0))  # 6.0 MAF > 5.0 capacity
        env._precip_history = []
        env._crss_precip = None
        env.advance_year()
        skill = SimpleNamespace(skill_name="maintain_demand", agent_id="UB0", parameters={})
        assert env.execute_skill(skill).success
        env.settle_year()
        assert env._agents["UB0"]["diversion"] == pytest.approx(env._agents["UB1"]["diversion"])
        assert env._agents["UB0"]["diversion"] == pytest.approx(2_500_000.0)

    def test_storage_committed_once_per_year(self):
        """T7: storage moves only in advance_year, once, whatever the number
        of settle_year() calls in between."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=5))
        env.initialize_synthetic(n_agents=6, basin_split=(2, 4))
        env.advance_year()
        s0 = (env._powell_storage, env._mead_storage[-1])
        st = env.settle_year()
        env.settle_year()
        assert (env._powell_storage, env._mead_storage[-1]) == s0
        env.advance_year()
        assert env._powell_storage == pytest.approx(st["powell_storage_end_maf"])
        assert env._mead_storage[-1] == pytest.approx(st["mead_storage_end_maf"])
        assert len(env._mead_storage) == 2

    def test_advance_without_settle_still_settles_once(self):
        """Callers that never call settle_year() (the FQL baseline) still get
        exactly one settlement per year, at last year's final requests."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=5))
        env.initialize_synthetic(n_agents=6, basin_split=(2, 4))
        for _ in range(4):
            env.advance_year()
        assert len(env._settlement_history) == 3
        assert len(env._mead_storage) == 4


class TestTimingAndInitialState:
    def test_year_one_uses_observed_initial_states(self):
        """Loop year 1 = 2019 sees the Dec 2018 observed Mead level and the
        USBR Dec 2018 Powell storage (declarations from 1 January states)."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=5))
        env.initialize_synthetic(n_agents=6, basin_split=(2, 4))
        env.advance_year()
        assert env.get_local("lower_basin", "lake_mead_level") == pytest.approx(1081.46)
        assert env._powell_storage == pytest.approx(11.99)
        assert env._mead_history[-2:] == [1082.52, pytest.approx(1081.46)]

    def test_tier_depends_only_on_committed_storage(self):
        env = IrrigationEnvironment(WaterSystemConfig(seed=5))
        env.initialize_synthetic(n_agents=6, basin_split=(2, 4))
        env.advance_year()
        st = env.settle_year()
        env.advance_year()
        expected = env._storage_to_elevation(st["mead_storage_end_maf"])
        assert env.get_local("lower_basin", "lake_mead_level") == pytest.approx(expected)

    def test_upper_basin_never_tier_curtailed(self):
        env = IrrigationEnvironment(WaterSystemConfig(seed=5))
        env.initialize_synthetic(n_agents=6, basin_split=(2, 4))
        env._mead_storage = [8.5]  # below 1,050 ft -> Tier 2
        env.advance_year()
        for a in env._agents.values():
            if a["basin"] == "upper_basin":
                assert a["curtailment_ratio"] == 0.0
            else:
                assert a["curtailment_ratio"] == pytest.approx(0.10)


class TestBasinRequestMetric:
    def test_basin_request_over_target_is_logged_ratio(self):
        env = IrrigationEnvironment(WaterSystemConfig(seed=5))
        env.initialize_synthetic(n_agents=6, basin_split=(2, 4))
        state = env.advance_year()
        total = sum(a["request"] for a in env._agents.values())
        assert state["basin_request_over_target"] == pytest.approx(total / CRSS_DEMAND_TARGET_AF)
        ctx = env.get_agent_context(env.agent_ids[0])
        assert ctx["basin_request_over_target"] == pytest.approx(total / CRSS_DEMAND_TARGET_AF)
        assert 0.0 <= ctx["delivery_ratio"] <= 1.0


class TestReviewFollowUps:
    def test_combined_lb_gap_reason(self):
        env = _env(lb=(2_000_000.0, 2_000_000.0))
        cfg = env.config
        snap = {"powell_storage": cfg.powell_dead_pool_maf + 0.2, "mead_storage": 2.2,
                "natural_flow": 6.0, "lb_cut": 0.20, "mexico": 1.225}
        st = env._settle(snap)
        assert st["lb_phys_ratio"] < 1.0
        assert st["agents"]["LB0"]["gap_reason"] == "lb_shortage_tier+lb_mead_availability"
        assert st["agents"]["LB0"]["delivery_ratio"] == pytest.approx(0.80 * st["lb_phys_ratio"])

    def test_request_change_after_settle_is_what_gets_committed(self):
        env = _env()
        env.advance_year()
        env.settle_year()
        env.update_agent_request("LB0", 2_500_000.0)
        expected = env._settle(env._snapshot)["mead_storage_end_maf"]
        env.advance_year()
        assert env._mead_storage[1] == pytest.approx(expected)

    def test_config_rejects_out_of_range_parameters(self):
        with pytest.raises(ValueError):
            WaterSystemConfig(evap_min_frac=1.5)
        with pytest.raises(ValueError):
            WaterSystemConfig(powell_initial_storage_maf=30.0)
        with pytest.raises(ValueError):
            WaterSystemConfig(min_powell_release_maf=9.5, max_powell_release_maf=9.0)
        for bad in (-0.1, 1.1):
            with pytest.raises(ValueError):
                WaterSystemConfig(powell_target_fill=bad)
        assert 0.0 <= WaterSystemConfig().powell_target_fill <= 1.0
        WaterSystemConfig(powell_target_fill=0.0)
        WaterSystemConfig(powell_target_fill=1.0)
