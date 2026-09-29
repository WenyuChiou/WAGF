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
    UB_SUBBASINS,
    IrrigationEnvironment,
    WaterSystemConfig,
)

# WP1b (item 20): see the identical constant in test_v3_water_system.py --
# every agent in this file's _agent()/_env() has no supply_group, so this
# placeholder's actual values never bind anything (proven identical to the
# single Lees Ferry pool, irrigation_v3_ub_subbasin_supply_2026-09-29.md
# section 10); it only needs to exist so _settle's per-sub-basin lookups
# find every key.
_UB_SUBBASIN_PLACEHOLDER_MAF = {s: 5.0 for s in UB_SUBBASINS}


def _agent(basin: str, request: float, water_right: float = 4_000_000.0,
           supply_group=None) -> dict:
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
        # WP1b (item 20): None (the default) is the "no sub-basin" pool
        # every other test in this file relies on; LOW 8's fuzz test below
        # is the one caller that sets a real sub-basin.
        "supply_group": supply_group,
        "ub_subbasin_member_count": None,
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
    # v3 (spec 1.2): Upper Basin non-farm consumptive use leaves the system
    # between Lees Ferry and Powell, alongside D_U -- it must be on the
    # RHS too, or the identity is short by exactly ub_non_farm_maf.
    rhs = (st["natural_flow_maf"] + st["lb_tributary_maf"] - st["ub_delivered_maf"]
           - st.get("ub_non_farm_maf", 0.0)
           - st["powell_evap_maf"] - st["mead_evap_maf"] - withdrawals - st["mead_spill_maf"])
    return lhs - rhs


def _random_snapshot(rng, cfg):
    return {
        "powell_storage": float(rng.uniform(cfg.powell_dead_pool_maf, cfg.powell_capacity_maf)),
        "mead_storage": float(rng.uniform(cfg.mead_dead_pool_maf, cfg.mead_capacity_maf)),
        "natural_flow": float(rng.uniform(6.0, 17.0)),
        # PI decision 2026-09-28: _settle now computes g from the declared
        # shortage VOLUME (0-0.5 MAF, the real tier range) and the
        # non-agricultural bucket, not a supplied ratio. WP1c review round 2
        # (LOW 6): a random volume in this range never matches a real
        # tier's exact figure, and _settle now raises rather than silently
        # guessing tier 0 for an unrecognised volume -- state tier 0
        # explicitly (f_g = 0, inert for this file's synthetic LB agents,
        # which are not in lb_priority_split_v3.csv and are treated as
        # fully senior regardless).
        "lb_shortage_volume_maf": float(rng.uniform(0.0, 0.5)),
        "lb_shortage_tier": 0,
        "mexico": float(rng.uniform(1.225, 1.5)),
        # Review fix 8: no silent fallback -- the default config's source
        # is "usbr_intervening", which REQUIRES this key.
        "lb_tributary": float(rng.uniform(0.3, 2.0)),
        # Re-review 2026-09-29 (HIGH 1): the release-planning projection,
        # frozen at the 1 January snapshot -- deliberately independent of
        # whatever request a fuzz test's loop body sets on the agents
        # afterward, exactly like a real year where the projection is made
        # before this year's requests are known. The invariants these
        # fuzz tests check (mass balance closes, storages stay in bounds)
        # hold for any projection, matched or not.
        "lb_request_projected_maf": float(rng.uniform(0.3, 3.5)),
        # Re-review 2026-09-29 (HIGH A round 3): a random projected Upper
        # Basin total too, independent of whatever the loop body sets on
        # the agents -- see _random_snapshot_planned below, which turns
        # this into powell_release_planned_maf via the real planning
        # method.
        "ub_request_projected_maf": float(rng.uniform(0.0, 5.0)),
    }


def _planned(env, snap):
    """Test helper: compute powell_release_planned_maf via the REAL
    planning method (_plan_powell_release), from the snapshot's own
    projected totals -- so hand-built snapshots exercise realistic
    settlement without each test needing to hand-derive the release
    itself. Returns a NEW dict (does not mutate snap).

    Re-review 2026-09-29 round 4 (LOW 1): the default Upper Basin total
    (when the snapshot has no explicit ub_request_projected_maf override,
    e.g. a fuzz test's own random value) comes from the SAME
    _basin_request_projected_maf advance_year itself calls, water-right
    cap included -- not a hand-rolled, easily-stale re-derivation."""
    cfg = env.config
    ub_requested = snap.get(
        "ub_request_projected_maf",
        env._basin_request_projected_maf(is_upper_basin=True),
    )
    out = dict(snap)
    out.setdefault(
        "ub_subbasin_available_af",
        {s: v * 1e6 for s, v in _UB_SUBBASIN_PLACEHOLDER_MAF.items()},
    )
    out["powell_release_planned_maf"] = env._plan_powell_release(
        nf=snap["natural_flow"], s_p=snap["powell_storage"], s_m=snap["mead_storage"],
        trib=snap.get("lb_tributary", cfg.lb_tributary_maf),
        shortage_volume=snap["lb_shortage_volume_maf"], mexico=snap["mexico"],
        ub_requested_maf=ub_requested,
        lb_requested_maf=snap["lb_request_projected_maf"],
        # WP1b (item 20): this file's agents never set supply_group, so the
        # whole (possibly overridden, possibly random) Upper Basin total
        # goes into the unconstrained "no sub-basin" bucket -- see
        # _UB_SUBBASIN_PLACEHOLDER_MAF above.
        ub_requested_by_subbasin_maf={None: ub_requested},
        ub_available_by_subbasin_maf=_UB_SUBBASIN_PLACEHOLDER_MAF,
    )
    out.pop("ub_request_projected_maf", None)
    return out


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
            snap = _planned(env, _random_snapshot(rng, cfg))
            st = env._settle(snap)
            assert abs(_balance_error(st)) < 1e-9
            assert cfg.powell_dead_pool_maf - 1e-9 <= st["powell_storage_end_maf"] <= cfg.powell_capacity_maf + 1e-9
            # Re-review 2026-09-29 (NIT): _settle spills any end-of-year Mead
            # storage above the conservation pool (review fix 11), so that
            # -- not the curve's larger flood-control-inclusive
            # mead_capacity_maf, which end storage never actually reaches --
            # is the real upper bound to assert here.
            assert cfg.mead_dead_pool_maf - 1e-9 <= st["mead_storage_end_maf"] <= cfg.mead_conservation_pool_maf + 1e-9

    def test_extreme_low_states_close(self):
        """Both reservoirs at dead pool, lowest flow: still closes, nothing
        goes below a dead pool."""
        env = _env()
        cfg = env.config
        snap = {"powell_storage": cfg.powell_dead_pool_maf, "mead_storage": cfg.mead_dead_pool_maf,
                "natural_flow": 6.0, "lb_shortage_volume_maf": 0.5, "mexico": 1.225,
                "lb_tributary": 0.8, "lb_request_projected_maf": 2.6}
        st = env._settle(_planned(env, snap))
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

    def test_conservation_with_random_subbasin_sharing(self):
        """LOW 8 (2026-09-29 re-review): T1 above fuzzes requests only,
        with every agent in the "no sub-basin" pool
        (_UB_SUBBASIN_PLACEHOLDER_MAF, never binding). This fuzzes REAL
        sub-basin agents (several per sub-basin, spread over all nine) AND
        a random A_s(t) per sub-basin each iteration -- the pro-rata
        sharing / basin-wide backstop code path T1 never exercises -- and
        checks the same two-reservoir identity still closes to 1e-9 MAF,
        every delivery stays within its own request, and Upper Basin
        deliveries never exceed availability."""
        rng = np.random.default_rng(13)
        env = IrrigationEnvironment(WaterSystemConfig(seed=13))
        for s_idx, s in enumerate(UB_SUBBASINS):
            for j in range(3):  # 3 agents per sub-basin, 27 Upper Basin agents
                env._agents[f"{s}_{j}"] = _agent("upper_basin", 0.0, supply_group=s)
        for i in range(2):
            env._agents[f"LB_{i}"] = _agent("lower_basin", 0.0)

        for _ in range(500):
            for aid in env._agents:
                env._agents[aid]["request"] = float(rng.uniform(0.0, 1_500_000.0))
            available_af = {s: float(rng.uniform(0.0, 3_000_000.0)) for s in UB_SUBBASINS}
            snap = _planned(env, _random_snapshot(rng, env.config))
            snap["ub_subbasin_available_af"] = available_af
            st = env._settle(snap)
            assert abs(_balance_error(st)) < 1e-9
            for aid, rec in st["agents"].items():
                assert rec["delivered"] <= rec["request"] + 1e-6
            for s in UB_SUBBASINS:
                delivered_s = sum(
                    rec["delivered"] for aid, rec in st["agents"].items()
                    if env._agents[aid].get("supply_group") == s
                )
                # A sub-basin's own delivery never exceeds its own A_s(t):
                # true whether or not the basin-wide backstop also fired,
                # since the backstop only ever scales every sub-basin's
                # already-capped delivery DOWN by a shared factor <= 1.
                assert delivered_s <= available_af[s] + 1e-3, s
            assert st["ub_delivered_maf"] <= min(5.0, st["natural_flow_maf"]) + 1e-9


class TestDeliveriesWithinAvailability:
    def test_ub_never_exceeds_capacity_flow_or_request(self):
        """T3 (Powell side, PI decision 4 2026-09-28): D_U <= min(request,
        5.0 MAF, non-farm-net natural flow) -- the Upper Basin has priority
        and is no longer bounded by what leaves Powell able to keep its
        minimum release. Every agent receives at most its request."""
        rng = np.random.default_rng(11)
        env = _env(ub=(3_000_000.0, 3_000_000.0))  # 6.0 MAF > 5.0 capacity
        cfg = env.config
        for _ in range(500):
            snap = _planned(env, _random_snapshot(rng, cfg))
            st = env._settle(snap)
            nf_net = snap["natural_flow"] - cfg.ub_non_farm_depletion_maf
            assert st["ub_delivered_maf"] <= min(
                st["ub_request_maf"], cfg.ub_infrastructure_cap_maf, nf_net
            ) + 1e-12
            for rec in st["agents"].values():
                assert rec["delivered"] <= rec["request"] + 1e-6

    def test_mead_withdrawals_within_available(self):
        """T3 (Mead side): LB ag + non-ag + Mexico <= storage above dead pool
        + release + tributaries - evaporation."""
        rng = np.random.default_rng(12)
        env = _env(lb=(2_000_000.0, 2_000_000.0))
        cfg = env.config
        for _ in range(500):
            snap = _planned(env, _random_snapshot(rng, cfg))
            st = env._settle(snap)
            withdrawals = st["lb_delivered_maf"] + st["lb_non_ag_delivered_maf"] + st["mexico_delivered_maf"]
            # snap["lb_tributary"], not cfg.lb_tributary_maf (the constant
            # fallback only) -- _random_snapshot supplies its own value.
            available = (snap["mead_storage"] - cfg.mead_dead_pool_maf) + st["powell_release_maf"] \
                + snap["lb_tributary"] - st["mead_evap_maf"]
            assert withdrawals <= available + 1e-9

    def test_mead_short_scales_pro_rata(self):
        """Mead near dead pool with a low release: phi < 1, and every Lower
        Basin withdrawal (ag, non-ag, Mexico) is scaled by the same phi."""
        env = _env(lb=(1_000_000.0, 3_000_000.0))
        cfg = env.config
        # v3: 0.3 MAF above the dead pool (was a bare 2.3 against the old
        # 2.0 MAF dead pool; kept relative so "low but not empty" survives
        # the H4 curve/dead-pool fix).
        snap = {"powell_storage": cfg.powell_dead_pool_maf + 0.5,
                "mead_storage": cfg.mead_dead_pool_maf + 0.3,
                "natural_flow": 6.0, "lb_shortage_volume_maf": 0.0, "mexico": 1.5,
                "lb_tributary": 0.8, "lb_request_projected_maf": 4.0}
        st = env._settle(_planned(env, snap))
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
                "lb_shortage_volume_maf": 0.0, "mexico": 1.5, "lb_tributary": 0.8,
                "lb_request_projected_maf": 2.6}
        st = env._settle(_planned(env, snap))
        ub = [st["agents"][f"UB{i}"] for i in range(3)]
        assert sum(r["delivered"] for r in ub) / 1e6 == pytest.approx(st["ub_delivered_maf"])
        assert st["ub_delivered_maf"] == pytest.approx(5.0)
        ratios = {round(r["delivery_ratio"], 12) for r in ub}
        assert len(ratios) == 1
        assert ub[0]["gap_reason"] == "ub_capacity"

    def test_lb_tier_cut_reduces_non_ag_only_not_agricultural(self):
        """PI decision 2026-09-28 (replaces the pro-rata-across-all-LB-use
        rule tested here until this review round): the declared shortage
        volume V reduces ONLY the 5.0 MAF non-agricultural bucket
        (non_ag = max(0, N - V)); the 22 agricultural agents are senior
        and are NOT reduced by the declared tier -- only by physical Mead
        availability (phi, here == 1.0, Mead has ample storage). Upper
        Basin agents are unaffected either way (Q2)."""
        env = _env()
        cfg = env.config
        v = 0.417  # Tier 2 volume
        snap = {"powell_storage": 15.0, "mead_storage": 20.0, "natural_flow": 12.0,
                "lb_shortage_volume_maf": v, "mexico": 1.396, "lb_tributary": 0.8,
                "lb_request_projected_maf": 2.6}
        st = env._settle(_planned(env, snap))
        assert st["lb_phys_ratio"] == pytest.approx(1.0)
        assert st["lb_non_ag_delivered_maf"] == pytest.approx(cfg.lb_non_ag_total_maf - v)
        lb_sum = sum(st["agents"][f"LB{i}"]["delivered"] for i in range(2)) / 1e6
        # Agricultural requests are delivered IN FULL (phi == 1, no tier
        # factor) -- unlike the pre-review rule, which would have cut this
        # by 10%.
        assert lb_sum == pytest.approx(st["lb_request_maf"])
        assert st["agents"]["LB0"]["gap_reason"] == "none"
        assert st["agents"]["LB0"]["delivery_ratio"] == pytest.approx(1.0)
        assert st["agents"]["UB0"]["delivery_ratio"] == 1.0
        # Informational only: curtailment_ratio (_apply_curtailment) is
        # V / N, not applied to the agricultural delivery above.
        assert st["lb_cut"] == pytest.approx(v / cfg.lb_non_ag_total_maf)


class TestUpperBasinNotZeroed:
    def test_low_natural_flow_does_not_zero_ub_when_powell_has_storage(self):
        """The old model set UB = max(0, NF - 7.0) = 0 in a 6.0 MAF year
        (2022). With Powell storage covering the minimum release, UB keeps
        its full request."""
        env = _env()
        snap = {"powell_storage": 9.62, "mead_storage": 9.0, "natural_flow": 6.0,
                "lb_shortage_volume_maf": 0.5, "mexico": 1.225, "lb_tributary": 0.8,
                "lb_request_projected_maf": 2.6}
        st = env._settle(_planned(env, snap))
        assert st["ub_delivered_maf"] == pytest.approx(st["ub_request_maf"])
        assert st["powell_release_maf"] == pytest.approx(7.0)

    def test_low_powell_does_not_cut_ub_release_falls_short_instead(self):
        """PI decision 4 (2026-09-28, reverses the pre-v3 rule tested here
        until then): with little Powell storage in a 6.0 MAF year, the
        Upper Basin is NOT cut -- it has priority, bounded only by
        non-farm-net natural flow and the 5.0 MAF capacity. Powell's
        release falls short of its 7.0 MAF floor instead (pass-through at
        low storage), never below its dead pool."""
        env = _env()
        cfg = env.config
        snap = {"powell_storage": cfg.powell_dead_pool_maf + 2.0, "mead_storage": 9.0,
                "natural_flow": 6.0, "lb_shortage_volume_maf": 0.5, "mexico": 1.225,
                "lb_tributary": 0.8, "lb_request_projected_maf": 2.6}
        st = env._settle(_planned(env, snap))
        nf_net = 6.0 - cfg.ub_non_farm_depletion_maf
        assert st["ub_delivered_maf"] == pytest.approx(st["ub_request_maf"])
        assert st["ub_delivered_maf"] == pytest.approx(min(st["ub_request_maf"], nf_net))
        ratios = [st["agents"][f"UB{i}"]["delivery_ratio"] for i in range(2)]
        assert ratios[0] == pytest.approx(1.0) and ratios[0] == pytest.approx(ratios[1])
        assert st["powell_release_maf"] < 7.0
        assert st["powell_storage_end_maf"] >= cfg.powell_dead_pool_maf - 1e-9
        assert st["agents"]["UB0"]["gap_reason"] == "none"

    def test_powell_empty_ub_still_gets_full_request(self):
        """PI decision 4 (2026-09-28, reverses the pre-v3 rule tested here
        until then): Powell at dead pool and flow below 7.0 no longer
        zeroes the Upper Basin -- it still receives its (non-farm-net
        natural-flow-bounded) full request; Powell's release is whatever
        is physically available (pass-through at dead pool), never
        negative and never below the dead pool."""
        env = _env()
        cfg = env.config
        snap = {"powell_storage": cfg.powell_dead_pool_maf, "mead_storage": 9.0,
                "natural_flow": 6.0, "lb_shortage_volume_maf": 0.5, "mexico": 1.225,
                "lb_tributary": 0.8, "lb_request_projected_maf": 2.6}
        st = env._settle(_planned(env, snap))
        nf_net = 6.0 - cfg.ub_non_farm_depletion_maf
        pass_through = nf_net - st["ub_delivered_maf"]
        assert st["ub_delivered_maf"] == pytest.approx(min(st["ub_request_maf"], nf_net))
        assert st["ub_delivered_maf"] > 0.0
        assert st["powell_release_maf"] == pytest.approx(pass_through - st["powell_evap_maf"])
        assert st["powell_storage_end_maf"] == pytest.approx(cfg.powell_dead_pool_maf)

    def test_balancing_equalises_fractions_when_bounds_allow(self):
        """PI decision 2026-09-28 (storage-balancing rule), re-review
        2026-09-29 (HIGH 1): the release target now includes this year's
        projected Lower Basin withdrawals O = r_LB_projected + non_ag +
        Mexico -- the first version of this rule (and this test) left O
        out of Mead's side entirely, so Mead looked far healthier than it
        would be after real withdrawals and got too little release
        (measured on the 2018-demand replay: Powell full and spilling
        while Mead sat in Tier 1, 12 Tier-3 years, minimum 985.4 ft).
        When the equalizing release falls inside [7.0, 9.5] MAF and Mead
        can physically deliver everything the projection assumed (phi ==
        1, so the actual withdrawal matches the projected O), Powell's
        and Mead's end-of-year LIVE fractions -- AFTER withdrawals, not
        before -- come out equal."""
        env = _env()
        cfg = env.config
        r_lb_projected = 2.6  # _env()'s default two 1.3 MAF Lower Basin agents
        snap = {"powell_storage": 16.0, "mead_storage": 16.0,
                "natural_flow": 11.0 + cfg.ub_non_farm_depletion_maf,
                "lb_shortage_volume_maf": 0.0, "mexico": 1.5, "lb_tributary": 0.8,
                "lb_request_projected_maf": r_lb_projected}
        st = env._settle(_planned(env, snap))
        release = st["powell_release_maf"]
        assert cfg.min_powell_release_maf + 1e-6 < release < cfg.max_powell_release_maf - 1e-6, (
            "scenario must land strictly inside the band, or it tests the "
            "bound-clipping branch instead of equalization"
        )
        assert st["lb_phys_ratio"] == pytest.approx(1.0), (
            "scenario must give phi == 1 (ample Mead availability) so the "
            "actual withdrawal matches the projected O the release was "
            "planned against"
        )
        powell_live_cap = cfg.powell_capacity_maf - cfg.powell_dead_pool_maf
        mead_live_cap = cfg.mead_conservation_pool_maf - cfg.mead_dead_pool_maf
        f_p = (st["powell_storage_end_maf"] - cfg.powell_dead_pool_maf) / powell_live_cap
        f_m = (st["mead_storage_end_maf"] - cfg.mead_dead_pool_maf) / mead_live_cap
        assert f_p == pytest.approx(f_m, abs=1e-6)
        assert abs(_balance_error(st)) < 1e-9

    def test_balancing_bounds_respected_when_equalizing_release_is_extreme(self):
        """When Powell is nearly full and Mead nearly empty, the pure
        equalizing release would exceed 9.5 MAF; the rule clips to the
        Guidelines' own Lower Elevation Balancing Tier ceiling instead."""
        env = _env()
        cfg = env.config
        # Full enough to want much more than 9.5 MAF release, but not so
        # full that even a 9.5 MAF release leaves it above capacity
        # (which would ALSO add a spill on top -- test_storage_above_
        # capacity_spills_into_release below covers that separately).
        snap = {"powell_storage": cfg.powell_capacity_maf - 3.0,
                "mead_storage": cfg.mead_dead_pool_maf + 0.5,
                "natural_flow": 15.0 + cfg.ub_non_farm_depletion_maf,
                "lb_shortage_volume_maf": 0.0, "mexico": 1.5, "lb_tributary": 0.8,
                "lb_request_projected_maf": 2.6}
        st = env._settle(_planned(env, snap))
        assert st["powell_release_maf"] == pytest.approx(cfg.max_powell_release_maf)
        assert st["powell_spill_maf"] == 0.0
        assert abs(_balance_error(st)) < 1e-9

    def test_balancing_release_never_below_floor_when_physically_available(self):
        """Symmetric case: Mead nearly full and Powell nearly empty (but
        not at dead pool) -- pure equalizing wants near-zero release, but
        the rule floors it at 7.0 MAF since that much is available."""
        env = _env()
        cfg = env.config
        snap = {"powell_storage": cfg.powell_dead_pool_maf + 3.0,
                "mead_storage": cfg.mead_conservation_pool_maf - 0.5,
                "natural_flow": 15.0 + cfg.ub_non_farm_depletion_maf,
                "lb_shortage_volume_maf": 0.0, "mexico": 1.5, "lb_tributary": 0.8,
                "lb_request_projected_maf": 2.6}
        st = env._settle(_planned(env, snap))
        assert st["powell_release_maf"] == pytest.approx(cfg.min_powell_release_maf)
        assert abs(_balance_error(st)) < 1e-9

    def test_storage_above_capacity_spills_into_release(self):
        """A snapshot already above full pool, with Mead ALSO nearly full
        and a large natural flow, spills the excess into the release and
        still closes the balance. Re-review 2026-09-29 (HIGH 1): with O
        now subtracted from Mead's side, a small Lower Basin projection
        and a large natural flow keep the balancing release wanting far
        more than the [7.0, 9.5] MAF band even with Mead this full, so the
        clipped release plus spill together drain Powell back to exactly
        its capacity."""
        env = _env()
        cfg = env.config
        snap = {"powell_storage": cfg.powell_capacity_maf + 2.0,
                "mead_storage": cfg.mead_conservation_pool_maf - 1.0,
                "natural_flow": 15.0 + cfg.ub_non_farm_depletion_maf,
                "lb_shortage_volume_maf": 0.5, "mexico": 1.225, "lb_tributary": 0.3,
                "lb_request_projected_maf": 0.5}
        st = env._settle(_planned(env, snap))
        assert st["powell_spill_maf"] > 0.0
        assert st["powell_storage_end_maf"] == pytest.approx(cfg.powell_capacity_maf)
        assert abs(_balance_error(st)) < 1e-9
        # Spill alone does not discriminate old vs new code (a spill always
        # drains end storage to exactly capacity and mass balance always
        # closes, by construction, regardless of which release was chosen)
        # -- the release VALUE itself must differ. Pre-HIGH-1 (no O
        # subtracted from Mead's side) gives release~7.70/spill~5.60 for
        # this exact scenario; this asserts the actual HIGH-1 numbers.
        assert st["powell_release_maf"] == pytest.approx(13.3, abs=1e-2)
        assert st["powell_spill_maf"] == pytest.approx(3.8, abs=1e-2)


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
        cfg = env.config
        # v3 (USBR 2009 curve, L2 H4): storage in [8.528, 10.230) MAF puts
        # the elevation in [1025, 1050) ft -> Tier 2.
        env._mead_storage = [9.0]
        # PI decision 2026-09-28: curtailment_ratio is V / N (the declared
        # volume over the 5.0 MAF non-agricultural bucket alone), not
        # dependent on Lower Basin requests at all (superseding the WP1
        # V / (r_LB + N) version reviewed the same day).
        expected_ratio = env._tier_shortage_volume_maf(2) / cfg.lb_non_ag_total_maf
        env.advance_year()
        assert env._compute_shortage_tier() == 2
        for a in env._agents.values():
            if a["basin"] == "upper_basin":
                assert a["curtailment_ratio"] == 0.0
            else:
                assert a["curtailment_ratio"] == pytest.approx(expected_ratio)


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
    def test_declared_tier_does_not_add_to_physical_gap_reason(self):
        """PI decision 2026-09-28 (replaces the pre-review
        'lb_shortage_tier+lb_mead_availability' combined reason tested
        here): even with a large declared shortage volume AND physical
        Mead scarcity both present, an agricultural agent's gap_reason is
        just 'lb_mead_availability' -- the declared volume only ever
        reduces the non-agricultural bucket, never appearing in an
        agricultural agent's own reason."""
        env = _env(lb=(2_000_000.0, 2_000_000.0))
        cfg = env.config
        # 0.2 MAF above the dead pool: low but not empty (USBR 2009 curve).
        snap = {"powell_storage": cfg.powell_dead_pool_maf + 0.2,
                "mead_storage": cfg.mead_dead_pool_maf + 0.2,
                "natural_flow": 6.0, "lb_shortage_volume_maf": 0.5, "mexico": 1.225,
                "lb_tributary": 0.8, "lb_request_projected_maf": 4.0}
        st = env._settle(_planned(env, snap))
        assert st["lb_phys_ratio"] < 1.0
        assert st["agents"]["LB0"]["gap_reason"] == "lb_mead_availability"
        assert st["agents"]["LB0"]["delivery_ratio"] == pytest.approx(st["lb_phys_ratio"])
        assert st["lb_non_ag_delivered_maf"] == pytest.approx(
            max(0.0, cfg.lb_non_ag_total_maf - 0.5) * st["lb_phys_ratio"]
        )

    def test_planned_release_does_not_move_with_mid_year_request_changes(self):
        """HIGH A round 3: the Powell release is planned ONCE in
        advance_year, from PROJECTED (pre-decision) Upper AND Lower Basin
        request totals -- raising either basin's requests after
        advance_year must not move the release, as long as Powell is not
        at its own physical limit (where the ACTUAL-inflow cap, not the
        plan, is the only thing allowed to move it, review fix HIGH A).

        Fails on the pre-HIGH-A code, which still re-derived the release
        inside _settle from that call's own ACTUAL Upper Basin request
        (only the Lower Basin side was frozen by the HIGH 1 fix): a 15
        percent Upper Basin raise after advance_year moved the release
        (reviewer's probe: 16 of 42 years, up to 0.237 MAF; reproduced
        here as 8.4435 -> 8.3858 MAF on this exact seed/scenario)."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=11))
        env.initialize_synthetic(n_agents=24, basin_split=(10, 14))
        env.advance_year()
        planned = env._snapshot["powell_release_planned_maf"]
        provisional = env.settle_year()
        # Sanity: Powell is not at its own physical limit here -- the
        # planned release is exactly what gets delivered, not a lower
        # physically-capped value. If this ever fails, the scenario needs
        # adjusting (it would no longer isolate the plan from the cap).
        assert provisional["powell_release_maf"] == pytest.approx(planned)

        for aid, agent in env._agents.items():
            agent["request"] = min(agent["request"] * 1.15, agent["water_right"])
        after = env.settle_year()
        assert env._snapshot["powell_release_planned_maf"] == pytest.approx(planned)
        assert after["powell_release_maf"] == pytest.approx(planned)

    def test_settle_raises_on_missing_planned_release(self):
        """Re-review 2026-09-29 round 4 (LOW 1): powell_release_planned_maf
        is REQUIRED (HIGH A moved release planning out of _settle entirely,
        into advance_year's _plan_powell_release) -- a snapshot missing it
        must raise KeyError, not silently recompute some other release or
        fall back to a stale default."""
        env = _env()
        snap = _planned(env, {
            "powell_storage": 15.0, "mead_storage": 12.0, "natural_flow": 12.0,
            "lb_shortage_volume_maf": 0.0, "mexico": 1.5, "lb_tributary": 0.8,
            "lb_request_projected_maf": 2.6,
        })
        del snap["powell_release_planned_maf"]
        with pytest.raises(KeyError, match="powell_release_planned_maf"):
            env._settle(snap)

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
        # Review 2026-09-28: powell_target_fill is removed (the storage-
        # balancing release rule replaces it); mead_conservation_pool_maf
        # must sit strictly between the dead pool and capacity.
        with pytest.raises(TypeError):
            WaterSystemConfig(powell_target_fill=0.5)
        with pytest.raises(ValueError):
            WaterSystemConfig(mead_conservation_pool_maf=WaterSystemConfig().mead_dead_pool_maf)
        with pytest.raises(ValueError):
            WaterSystemConfig(mead_conservation_pool_maf=WaterSystemConfig().mead_capacity_maf + 1.0)
        # mead_dead_pool_maf must match the USBR table's dead storage.
        with pytest.raises(ValueError):
            WaterSystemConfig(mead_dead_pool_maf=2.0)
