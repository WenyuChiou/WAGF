"""Irrigation case study v3, Work Package 1 (water system and data).

Spec: .research/design_specs/irrigation_v3_spec_2026-09-28.md (WP1) and
.research/design_specs/irrigation_v3_design_provenance_2026-09-28.md.
Audit: .ai/irrigation_prerun_audit_2026-09-28/L2_water_system.md (H1, H2,
H4, D1, D2, D6, N2).

Re-review 2026-09-29 (NIT): most tests here fail on the pre-WP1 code (main
f3aa2d87 / the persona commit cb1656eb) -- ``_natural_flow_for_year``,
``_tier_shortage_volume_maf``, ``precip_group``, ``precipitation_flag`` and
the new data files do not exist there, and the pre-WP1 Mead curve,
evaporation calibration and Mexico schedule give different numbers -- but
this is no longer true of EVERY test: several (the storage-balancing
Powell release, the non-agricultural-only shortage sharing, and the tests
each review round added since) instead fail on an EARLIER post-WP1 code
state, the one each test's own docstring names, not necessarily on
f3aa2d87/cb1656eb.

Covers: the committed hydrology table and its checksum (1.1); natural
flow with no clamp (1.1); Upper Basin non-farm use taken first, never
curtailed (1.2); the Lower Basin tributary series (1.3); Upper Basin
priority over Powell's release, and the release never exceeding
inflow plus storage above dead pool (PI decision 4); the USBR 2009 Mead
curve and its calibrated evaporation (1.4, PI decision 5); shortage
volumes by tier and the Minute 323 Mexico schedule including the
1,045-1,025 ft band (1.5, PI decisions f and 6); 42-year mass balance
closure at fixed demand; and per-sub-basin precipitation (1.6).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from examples.irrigation_abm.irrigation_env import (
    HYDROLOGY_V3_PATH,
    HYDROLOGY_V3_SHA256,
    MEAD_CAPACITY_PATH,
    MEAD_CAPACITY_SHA256,
    UB_SUBBASINS,
    IrrigationEnvironment,
    WaterSystemConfig,
)

# WP1b (item 20): a large per-sub-basin placeholder for tests in this file
# that never assign any agent a supply_group (_agent/_env below). Such an
# agent falls into _settle's / _ub_delivery_for_planning's unconstrained
# "no sub-basin" bucket regardless of these numbers -- proven identical to
# the single Lees Ferry pool in
# .research/design_specs/irrigation_v3_ub_subbasin_supply_2026-09-29.md
# section 10 -- so its actual value never binds anything in this file; it
# only needs to exist so _settle's "every UB_SUBBASINS key present" check
# passes for a hand-built snapshot that (unlike advance_year) does not
# come from the real 42-row table.
_UB_SUBBASIN_PLACEHOLDER_MAF = {s: 5.0 for s in UB_SUBBASINS}
from examples.irrigation_abm.irrigation_personas import create_profiles_from_data

CRSS_PARAMS_CSV = Path("ref/RL-ABM-CRSS/ALL_colorado_ABM_params_cal_1108.csv")
CRSS_DB_DIR = Path("ref/CRSS_DB/CRSS_DB")
_REAL_REF_AVAILABLE = CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir()


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
    }


def _env(ub=(), lb=()) -> IrrigationEnvironment:
    env = IrrigationEnvironment(WaterSystemConfig(seed=42))
    for i, r in enumerate(ub):
        env._agents[f"UB{i}"] = _agent("upper_basin", r)
    for i, r in enumerate(lb):
        env._agents[f"LB{i}"] = _agent("lower_basin", r)
    return env


def _planned(env, snap, ub_requested_maf=None):
    """Test helper (re-review 2026-09-29, HIGH A round 3): compute
    powell_release_planned_maf via the REAL planning method
    (_plan_powell_release), from the snapshot's own projected Lower Basin
    total and either an explicit projected Upper Basin total or (default)
    the env's actual Upper Basin request sum -- i.e. no planned-vs-actual
    divergence unless a test explicitly asks for one. Returns a NEW dict
    (does not mutate snap).

    Re-review 2026-09-29 round 4 (LOW 1): the default comes from the SAME
    _basin_request_projected_maf advance_year itself calls, water-right
    cap included -- not a hand-rolled, easily-stale re-derivation.

    WP1b (item 20): also injects ``ub_subbasin_available_af`` into the
    returned snapshot (required by ``_settle`` in ``subbasin`` mode,
    ``WaterSystemConfig``'s default) and passes the live per-sub-basin
    projected-request breakdown to ``_plan_powell_release`` -- see
    ``_UB_SUBBASIN_PLACEHOLDER_MAF`` above for why the actual availability
    numbers are inert for every test in this file."""
    cfg = env.config
    if ub_requested_maf is None:
        ub_requested_maf = env._basin_request_projected_maf(is_upper_basin=True)
    ub_by_subbasin = env._ub_request_projected_by_subbasin_maf()
    out = dict(snap)
    out.setdefault(
        "ub_subbasin_available_af",
        {s: v * 1e6 for s, v in _UB_SUBBASIN_PLACEHOLDER_MAF.items()},
    )
    out["powell_release_planned_maf"] = env._plan_powell_release(
        nf=snap["natural_flow"], s_p=snap["powell_storage"], s_m=snap["mead_storage"],
        trib=snap.get("lb_tributary", cfg.lb_tributary_maf),
        shortage_volume=snap["lb_shortage_volume_maf"], mexico=snap["mexico"],
        ub_requested_maf=ub_requested_maf,
        lb_requested_maf=snap["lb_request_projected_maf"],
        year=env._current_year,
        ub_requested_by_subbasin_maf=ub_by_subbasin,
        ub_available_by_subbasin_maf=_UB_SUBBASIN_PLACEHOLDER_MAF,
    )
    return out


# ===========================================================================
# 1.1 Hydrology table
# ===========================================================================

class TestHydrologyTable:
    def test_hydrology_table_checksum_and_row_count(self):
        """42-row table, sha256-pinned; first and last rows match the
        source USBR sheet exactly."""
        data = Path(HYDROLOGY_V3_PATH).read_bytes()
        assert hashlib.sha256(data).hexdigest() == HYDROLOGY_V3_SHA256
        lines = data.decode("utf-8").splitlines()
        assert len(lines) == 43, "header + 42 rows"
        assert lines[0] == (
            "sim_year,source_calendar_year,lees_ferry_cy_natural_flow_af,"
            "lees_ferry_to_below_hoover_cy_intervening_af"
        )
        assert lines[1] == "2019,1988,11210331,821325"
        assert lines[-1] == "2060,1947,16380601,700234"

    def test_hydrology_table_sums(self):
        """Acceptance: 42-year sums 563,919,110 AF (Lees Ferry) and
        33,323,733 AF (intervening)."""
        lines = Path(HYDROLOGY_V3_PATH).read_text(encoding="utf-8").splitlines()[1:]
        lf_sum = sum(int(line.split(",")[2]) for line in lines)
        trib_sum = sum(int(line.split(",")[3]) for line in lines)
        assert lf_sum == 563_919_110
        assert trib_sum == 33_323_733

    def test_natural_flow_no_clamp(self):
        """2028 = 21.655579 MAF (above the old [6, 17] MAF ceiling -- no
        clamp), 2033 = 6.088144 MAF."""
        env = _env()
        assert env._natural_flow_for_year(2028) == pytest.approx(21.655579)
        assert env._natural_flow_for_year(2028) > 17.0
        assert env._natural_flow_for_year(2033) == pytest.approx(6.088144)

    def test_year_outside_table_raises(self):
        env = _env()
        with pytest.raises(ValueError, match="2061"):
            env._natural_flow_for_year(2061)
        with pytest.raises(ValueError):
            env._natural_flow_for_year(2018)

    def test_mead_capacity_table_checksum(self):
        data = Path(MEAD_CAPACITY_PATH).read_bytes()
        assert hashlib.sha256(data).hexdigest() == MEAD_CAPACITY_SHA256


# ===========================================================================
# 1.2 Upper Basin non-farm consumptive use
# ===========================================================================

class TestUbNonFarm:
    def test_ub_non_farm_subtracted(self):
        """Powell inflow = NF - 1.2213 - D_U (spec 1.2)."""
        env = _env(ub=(500_000.0,))  # well below NF, fully delivered
        snap = {"powell_storage": 15.0, "mead_storage": 12.0,
                "natural_flow": 11.210331, "lb_shortage_volume_maf": 0.0,
                "mexico": 1.5, "lb_tributary": 0.8, "lb_request_projected_maf": 0.0}
        st = env._settle(_planned(env, snap))
        assert st["ub_non_farm_maf"] == pytest.approx(1.2213)
        assert st["ub_delivered_maf"] == pytest.approx(0.5)
        inflow_p = st["natural_flow_maf"] - st["ub_non_farm_maf"] - st["ub_delivered_maf"]
        assert inflow_p == pytest.approx(11.210331 - 1.2213 - 0.5)

    def test_ub_non_farm_is_constant_and_documented(self):
        cfg = WaterSystemConfig()
        assert cfg.ub_non_farm_depletion_maf == pytest.approx(1.2213)

    def test_ub_non_farm_taken_first_never_negative_net_flow(self):
        """A pathologically low natural flow (below the non-farm amount):
        review fix 12 caps non-farm use itself at NF (the ACTUAL amount
        consumed, never more than NF even in an extremely dry year), so
        net flow floors at 0 rather than going negative, and the Upper
        Basin gets nothing."""
        env = _env(ub=(1_000_000.0,))
        snap = {"powell_storage": 15.0, "mead_storage": 12.0,
                "natural_flow": 0.5, "lb_shortage_volume_maf": 0.0,
                "mexico": 1.5, "lb_tributary": 0.8, "lb_request_projected_maf": 0.0}
        st = env._settle(_planned(env, snap))
        assert st["ub_non_farm_maf"] == pytest.approx(0.5)
        assert st["ub_delivered_maf"] == 0.0


# ===========================================================================
# 1.3 Lower Basin tributary inflow
# ===========================================================================

class TestTributary:
    def test_tributary_series_usbr_intervening(self):
        """2019 = 0.821325 MAF under usbr_intervening (the default)."""
        env = _env()
        assert env.config.lb_tributary_source == "usbr_intervening"
        assert env._lb_tributary_for_year(2019) == pytest.approx(0.821325)

    def test_tributary_constant_fallback(self):
        env = IrrigationEnvironment(WaterSystemConfig(seed=42, lb_tributary_source="constant"))
        assert env._lb_tributary_for_year(2019) == pytest.approx(1.0)

    def test_settle_uses_snapshot_tributary_when_present(self):
        """_settle reads the snapshot's own lb_tributary (spec 1.3). Review
        fix 8 (no silent fallbacks): a missing key falls back to the
        config constant only when config.lb_tributary_source is itself
        'constant'; with the default 'usbr_intervening' source a missing
        key is a hard error, since advance_year always supplies a real
        value and a silent substitution would hide a real bug."""
        env = _env(lb=(1_000_000.0,))
        snap_with = _planned(env, {
            "powell_storage": 15.0, "mead_storage": 12.0, "natural_flow": 11.0,
            "lb_shortage_volume_maf": 0.0, "mexico": 1.5, "lb_tributary": 0.3,
            "lb_request_projected_maf": 1.0,
        })
        st_with = env._settle(snap_with)
        assert st_with["lb_tributary_maf"] == pytest.approx(0.3)

        snap_without = dict(snap_with)
        del snap_without["lb_tributary"]
        with pytest.raises(ValueError, match="lb_tributary"):
            env._settle(snap_without)

        const_env = IrrigationEnvironment(WaterSystemConfig(seed=42, lb_tributary_source="constant"))
        const_env._agents["LB0"] = _agent("lower_basin", 1_000_000.0)
        st_without = const_env._settle(snap_without)
        assert st_without["lb_tributary_maf"] == pytest.approx(const_env.config.lb_tributary_maf)


# ===========================================================================
# Powell operations: Upper Basin priority (PI decision 4)
# ===========================================================================

class TestPowellPriority:
    def test_upper_basin_never_curtailed_for_powell_release(self):
        """Even with Powell empty and a low natural flow, the Upper Basin
        is bounded only by (non-farm-net) natural flow and the 5.0 MAF
        capacity -- never cut to protect Powell's release. Reverses the
        pre-v3 'ub_powell_release' gap reason, which no longer occurs."""
        env = _env(ub=(1_500_000.0, 1_500_000.0))
        cfg = env.config
        for p_storage in (cfg.powell_dead_pool_maf, cfg.powell_dead_pool_maf + 2.0, 15.0):
            snap = {"powell_storage": p_storage, "mead_storage": 9.0,
                    "natural_flow": 6.0, "lb_shortage_volume_maf": 0.417,
                    "mexico": 1.225, "lb_tributary": 0.8, "lb_request_projected_maf": 0.0}
            st = env._settle(_planned(env, snap))
            nf_net = 6.0 - cfg.ub_non_farm_depletion_maf
            assert st["ub_delivered_maf"] == pytest.approx(min(st["ub_request_maf"], nf_net))
            for aid in ("UB0", "UB1"):
                assert st["agents"][aid]["gap_reason"] != "ub_powell_release"
            assert st["powell_storage_end_maf"] >= cfg.powell_dead_pool_maf - 1e-9

    def test_upper_basin_bound_by_natural_flow_not_capacity(self):
        """Review fix 9: when (non-farm-net) natural flow is the tighter
        constraint, gap_reason is 'ub_natural_flow' and the delivered
        amount is the flow itself -- the 5.0 MAF capacity never gets
        reported as binding when it did not."""
        env = _env(ub=(2_450_000.0, 2_450_000.0))  # r_UB = 4.9 MAF
        cfg = env.config
        snap = {"powell_storage": 15.0, "mead_storage": 12.0,
                "natural_flow": 6.0, "lb_shortage_volume_maf": 0.0,
                "mexico": 1.5, "lb_tributary": 0.8, "lb_request_projected_maf": 0.0}
        st = env._settle(_planned(env, snap))
        nf_net = 6.0 - cfg.ub_non_farm_depletion_maf  # 4.7787, below both
        # r_UB (4.9) and the 5.0 MAF capacity -- flow is the tight bound.
        assert nf_net < cfg.ub_infrastructure_cap_maf
        assert st["ub_delivered_maf"] == pytest.approx(nf_net)
        assert st["ub_delivered_maf"] < cfg.ub_infrastructure_cap_maf
        for aid in ("UB0", "UB1"):
            assert st["agents"][aid]["gap_reason"] == "ub_natural_flow"

    def test_powell_evaporation_capped_after_upper_basin_depletion_at_dead_pool(self):
        """Review fix 1: at Powell's dead pool with 2033's natural flow
        (6.088144 MAF) and an Upper Basin request (4.9 MAF) that consumes
        essentially all of net flow (inflow_p = 0), evaporation must be
        capped at usable storage PLUS inflow_p (both zero here) -- not at
        the pre-Upper-Basin nf_net (4.866844 MAF), which would let Powell
        'evaporate' water the Upper Basin already took and push storage
        below the dead pool. Fails on the pre-fix ordering (e_p would be
        ~0.105 MAF, s_p_end ~1.785 < the 1.89 MAF dead pool); passes
        after."""
        env = _env(ub=(4_900_000.0,), lb=(2_000_000.0,))
        # _agent()'s default water_right (4.0 MAF) would itself clamp the
        # request below 4.9 MAF; raise it so the request really is 4.9.
        env._agents["UB0"]["water_right"] = 6_000_000.0
        cfg = env.config
        snap = {"powell_storage": cfg.powell_dead_pool_maf, "mead_storage": 12.0,
                "natural_flow": 6.088144, "lb_shortage_volume_maf": 0.0,
                "mexico": 1.5, "lb_tributary": 0.8, "lb_request_projected_maf": 2.0}
        st = env._settle(_planned(env, snap))
        nf_net = st["natural_flow_maf"] - st["ub_non_farm_maf"]
        inflow_p = nf_net - st["ub_delivered_maf"]
        assert inflow_p == pytest.approx(0.0, abs=1e-6)
        # The raw (uncapped) evaporation demand at the dead pool is
        # strictly positive -- if it were applied uncapped (or capped at
        # nf_net instead of inflow_p) storage would go negative below
        # dead pool. The fix caps it at (usable + inflow_p) = 0.
        raw_evap = env._powell_evaporation_maf(cfg.powell_dead_pool_maf)
        assert raw_evap > 0.0
        assert st["powell_evap_maf"] == pytest.approx(0.0, abs=1e-9)
        assert st["powell_release_maf"] == pytest.approx(0.0, abs=1e-9)
        assert st["powell_storage_end_maf"] == pytest.approx(cfg.powell_dead_pool_maf)

    def test_powell_never_below_dead_pool(self):
        """Fuzz: 2,000 random snapshots and requests, Powell's end storage
        never drops below its dead pool."""
        rng = np.random.default_rng(101)
        env = _env(ub=(3_000_000.0,), lb=(2_000_000.0,))
        cfg = env.config
        for _ in range(2000):
            for aid in env._agents:
                env._agents[aid]["request"] = float(rng.uniform(0.0, 4_000_000.0))
            snap = {
                "powell_storage": float(rng.uniform(cfg.powell_dead_pool_maf, cfg.powell_capacity_maf)),
                "mead_storage": float(rng.uniform(cfg.mead_dead_pool_maf, cfg.mead_capacity_maf)),
                "natural_flow": float(rng.uniform(6.0, 22.0)),
                # WP1c review round 2 (LOW 6): a random volume never matches
                # a real declared tier's exact figure, and _settle now
                # raises rather than silently guessing tier 0 for such a
                # volume -- this fuzz test is about Powell/Mead storage
                # bounds, not the declared tier, so it states tier 0
                # explicitly (f_g = 0, inert either way for this file's
                # synthetic LB0/LB1 agents, which are not in
                # lb_priority_split_v3.csv and are treated as fully senior
                # regardless).
                "lb_shortage_volume_maf": float(rng.uniform(0.0, 0.5)),
                "lb_shortage_tier": 0,
                "mexico": float(rng.uniform(1.0, 1.5)),
                "lb_tributary": float(rng.uniform(0.3, 2.0)),
                # Re-review 2026-09-29 (HIGH 1): independent of the requests
                # randomized above, exactly like a real year where the
                # projection is frozen before requests are known.
                "lb_request_projected_maf": float(rng.uniform(0.0, 4.0)),
            }
            st = env._settle(_planned(env, snap))
            assert st["powell_storage_end_maf"] >= cfg.powell_dead_pool_maf - 1e-9
            assert st["mead_storage_end_maf"] >= cfg.mead_dead_pool_maf - 1e-9

    def test_release_never_exceeds_physically_available(self):
        """Fuzz: Powell's release never exceeds inflow plus storage above
        the dead pool (pass-through at dead pool, PI decision 4)."""
        rng = np.random.default_rng(102)
        env = _env(ub=(1_000_000.0,), lb=(2_000_000.0,))
        cfg = env.config
        for _ in range(2000):
            snap = {
                "powell_storage": float(rng.uniform(cfg.powell_dead_pool_maf, cfg.powell_capacity_maf)),
                "mead_storage": float(rng.uniform(cfg.mead_dead_pool_maf, cfg.mead_capacity_maf)),
                "natural_flow": float(rng.uniform(6.0, 22.0)),
                # WP1c review round 2 (LOW 6): explicit tier 0, same
                # rationale as test_conservation_and_bounds_random_states
                # above -- a random volume never matches a real tier, and
                # _settle now raises rather than guessing.
                "lb_shortage_volume_maf": float(rng.uniform(0.0, 0.5)),
                "lb_shortage_tier": 0,
                "mexico": float(rng.uniform(1.0, 1.5)),
                "lb_tributary": float(rng.uniform(0.3, 2.0)),
                "lb_request_projected_maf": float(rng.uniform(0.0, 4.0)),
            }
            st = env._settle(_planned(env, snap))
            nf_net = max(0.0, snap["natural_flow"] - cfg.ub_non_farm_depletion_maf)
            inflow_p = nf_net - st["ub_delivered_maf"]
            p_usable = max(0.0, snap["powell_storage"] - cfg.powell_dead_pool_maf)
            available = inflow_p + p_usable  # generous upper bound (ignores evap)
            assert st["powell_release_maf"] <= available + 1e-6


# ===========================================================================
# 1.4 Lake Mead USBR 2009 curve and calibrated evaporation
# ===========================================================================

class TestMeadCurve:
    def test_mead_curve_usbr2009_checkpoints(self):
        """Acceptance checkpoints (available capacity + 2.547 MAF dead
        storage), and the 1081.46 ft round trip."""
        env = _env()
        checkpoints_kaf = {
            950: 2006, 1000: 4475, 1025: 5981, 1050: 7683, 1075: 9601,
            1100: 11735, 1220: 26177, 1229: 27620,
        }
        for ft, kaf in checkpoints_kaf.items():
            assert env._elevation_to_storage(ft) == pytest.approx(kaf / 1000 + 2.547, abs=1e-6)
        assert env._storage_to_elevation(10.132 + 2.547) == pytest.approx(1081.46, abs=0.01)
        assert env._elevation_to_storage(1050.0) == pytest.approx(7.683 + 2.547, abs=1e-6)

    def test_mead_curve_monotone(self):
        env = _env()
        assert np.all(np.diff(env._ELEVATION_FT) > 0)
        assert np.all(np.diff(env._STORAGE_MAF) > 0)

    def test_mead_dead_pool_and_capacity_config(self):
        cfg = WaterSystemConfig()
        assert cfg.mead_dead_pool_maf == pytest.approx(2.547)
        assert cfg.mead_capacity_maf == pytest.approx(30.167)

    def test_mead_evaporation_calibration_point(self):
        """Evaporation at the WY2018 Mead condition is within 1% of
        0.541 MAF (Feb 2019 24-Month Study)."""
        env = _env()
        cfg = env.config
        evap = env._mead_evaporation_maf(cfg.mead_evap_ref_storage_maf)
        assert evap == pytest.approx(0.541, rel=0.01)
        assert cfg.mead_evap_ref_storage_maf == pytest.approx(10.132 + 2.547, abs=1e-6)

    def test_mead_evaporation_scales_away_from_calibration_point(self):
        """Re-review 2026-09-29 (NIT): a check away from the 1,081.46 ft
        calibration point -- evaporation tracks surface area, not a
        constant, so it must be LOWER near the dead pool (a small, shallow
        remaining surface) and HIGHER near full pool. LOW 8 dropped the
        unsourced 1.5x cap on the area ratio: at 1,200 ft the real area
        ratio exceeds 1.5x the reference, so this also fails if that cap
        is ever restored (0.541 x 1.5 = 0.8115 MAF, well below the
        uncapped value asserted here)."""
        env = _env()
        cfg = env.config
        evap_dead_pool = env._mead_evaporation_maf(cfg.mead_dead_pool_maf)
        evap_near_full = env._mead_evaporation_maf(env._elevation_to_storage(1200.0))
        assert evap_dead_pool < 0.3
        assert evap_near_full > 0.9
        assert evap_dead_pool < evap_near_full


# ===========================================================================
# 1.5 Shortage volumes and Mexico schedule
# ===========================================================================

class TestShortageVolumesAndMexico:
    def test_shortage_volume_by_tier(self):
        env = _env()
        assert env._tier_shortage_volume_maf(0) == 0.0
        assert env._tier_shortage_volume_maf(1) == pytest.approx(0.333)
        assert env._tier_shortage_volume_maf(2) == pytest.approx(0.417)
        assert env._tier_shortage_volume_maf(3) == pytest.approx(0.500)

    def test_shortage_volume_informational_ratio_is_v_over_n(self):
        """PI decision 2026-09-28 (supersedes the spec's original pro-rata
        acceptance example, V / (r_LB + N) = 0.417 / 7.7): the
        informational lb_cut _settle produces is V / N alone -- the
        non-agricultural bucket's own share -- because agricultural
        deliveries are no longer part of the shared denominator."""
        env = _env(lb=(1_350_000.0, 1_350_000.0))  # r_LB = 2.7 MAF, irrelevant to g now
        cfg = env.config
        v = env._tier_shortage_volume_maf(2)
        snap = {"powell_storage": 15.0, "mead_storage": 20.0, "natural_flow": 15.0,
                "lb_shortage_volume_maf": v, "mexico": 1.5, "lb_tributary": 0.8,
                "lb_request_projected_maf": 2.7}
        st = env._settle(_planned(env, snap))
        assert st["lb_cut"] == pytest.approx(v / cfg.lb_non_ag_total_maf)
        assert st["lb_cut"] != pytest.approx(v / (2.7 + cfg.lb_non_ag_total_maf))

    def test_declared_shortage_volume_reduces_non_ag_bucket_only(self):
        """PI decision 2026-09-28 (supersedes review fix 4 and the spec's
        original pro-rata-across-all-LB-use rule): the declared tier's
        shortage volume V comes ENTIRELY out of the non-agricultural
        bucket (5.2 MAF, item 25; 5.0 MAF before it -- the assertions
        below read `cfg.lb_non_ag_total_maf`, not a literal, so they hold
        either way). The 22 LB agricultural agents are senior
        and unaffected by the declared tier itself -- only by physical
        Mead availability (phi, = 1.0 here since Mead has ample storage).
        ADOPT 12: assert on the actual 'lb_cut' the environment produces
        (V / N, informational only -- not a ratio applied to ag
        deliveries)."""
        env = _env(lb=(1_350_000.0, 1_350_000.0))  # r_LB = 2.7 MAF
        cfg = env.config
        v = env._tier_shortage_volume_maf(2)  # 0.417 MAF
        snap = {"powell_storage": 15.0, "mead_storage": 20.0, "natural_flow": 15.0,
                "lb_shortage_volume_maf": v, "mexico": 1.5, "lb_tributary": 0.8,
                "lb_request_projected_maf": 2.7}
        st = env._settle(_planned(env, snap))
        assert st["lb_phys_ratio"] == pytest.approx(1.0)  # Mead has ample storage here
        assert st["lb_non_ag_delivered_maf"] == pytest.approx(cfg.lb_non_ag_total_maf - v)
        lb_sum = sum(st["agents"][f"LB{i}"]["delivered"] for i in range(2)) / 1e6
        assert lb_sum == pytest.approx(2.7)  # unaffected by the declared tier
        for aid in ("LB0", "LB1"):
            assert st["agents"][aid]["gap_reason"] == "none"
        assert st["lb_cut"] == pytest.approx(v / cfg.lb_non_ag_total_maf)

    def test_mexico_schedule_by_band(self):
        """Minute 323 / BWSCP bands (review fix 3, PI decision 6): the DOI
        2022 Minute 323 base reduction (70 kaf = the 104 kaf total at
        1,050-1,045 ft minus its 34 kaf BWSCP saving) plus each band's own
        IBWC 2019 BWSCP saving (76/84/92/101 kaf for 1,045-1,040 /
        1,040-1,035 / 1,035-1,030 / 1,030-1,025 ft) gives the exact
        146/154/162/171 kaf reductions -- replacing the single 158.5 kaf
        midpoint the pre-fix code used for that whole span (L2 N2)."""
        env = _env()
        treaty = env.config.mexico_treaty_maf
        cases = [
            (1095.0, treaty - 0.0),
            (1080.0, treaty - 0.041),
            (1060.0, treaty - 0.080),
            (1047.0, treaty - 0.104),
            (1042.0, treaty - 0.146),
            (1037.0, treaty - 0.154),
            (1032.0, treaty - 0.162),
            (1027.0, treaty - 0.171),
            (1000.0, treaty - 0.275),
        ]
        for mead_level, expected in cases:
            assert env._mexico_delivery_maf(mead_level) == pytest.approx(expected)
        # Strictly decreasing delivery (increasing reduction) through the
        # four 5-ft bands the pre-v3 code collapsed into one.
        levels = [1047.0, 1042.0, 1037.0, 1032.0, 1027.0, 1000.0]
        deliveries = [env._mexico_delivery_maf(lv) for lv in levels]
        assert deliveries == sorted(deliveries, reverse=True)
        assert len(set(deliveries)) == len(deliveries)


# ===========================================================================
# LB return-flow option (item 36e, 2026-10-05 design-basis audit + fix
# proposals; wording fixed per Opus review P2-3, 2026-10-06): a CPU
# sensitivity, default 0.0, byte-identical, on the diversion-versus-
# consumptive-use units gap. A non-zero fraction of the LB agricultural
# draw is treated as reused downstream (e.g. credited toward the Mexico
# delivery) rather than lost to the system, so Mead releases LESS this
# year by that share -- it is NOT water physically returned to the river
# below Mead, and NOT water credited back into Mead's own storage.
# ===========================================================================

def _env_with_return_flow(lb, fraction: float) -> IrrigationEnvironment:
    env = IrrigationEnvironment(WaterSystemConfig(seed=42, lb_return_flow_fraction=fraction))
    for i, r in enumerate(lb):
        env._agents[f"LB{i}"] = _agent("lower_basin", r)
    return env


class TestLbReturnFlowFraction:
    def _settle(self, fraction: float):
        env = _env_with_return_flow((1_350_000.0, 1_350_000.0), fraction)  # r_LB = 2.7 MAF
        snap = {"powell_storage": 15.0, "mead_storage": 20.0, "natural_flow": 15.0,
                "lb_shortage_volume_maf": 0.0, "mexico": 1.5, "lb_tributary": 0.8,
                "lb_request_projected_maf": 2.7}
        return env, env._settle(_planned(env, snap))

    def test_config_rejects_out_of_range_fraction(self):
        """Capped at 0.5, not 1.0 (Opus review P2-3): the only
        diversion-to-consumptive-use anchor this model has is the Upper
        Basin's own 50 percent depletion convention; a Lower Basin
        fraction above that would claim MORE reuse than that convention
        assumes, which no source supports."""
        for bad in (-0.01, 0.51, 0.6, -5.0, 2.0, 1.0):
            with pytest.raises(ValueError, match="lb_return_flow_fraction"):
                WaterSystemConfig(lb_return_flow_fraction=bad)

    def test_default_is_zero_and_byte_identical(self):
        """Default (0.0): lb_return_flow_maf is 0.0, and the settlement is
        IDENTICAL to a hand-built env that never set the field at all."""
        default_env, default_st = self._settle(0.0)
        plain_env = _env(lb=(1_350_000.0, 1_350_000.0))
        snap = {"powell_storage": 15.0, "mead_storage": 20.0, "natural_flow": 15.0,
                "lb_shortage_volume_maf": 0.0, "mexico": 1.5, "lb_tributary": 0.8,
                "lb_request_projected_maf": 2.7}
        plain_st = plain_env._settle(_planned(plain_env, snap))
        assert default_st["lb_return_flow_maf"] == 0.0
        assert default_st["mead_storage_end_maf"] == pytest.approx(plain_st["mead_storage_end_maf"], abs=1e-12)
        for aid in ("LB0", "LB1"):
            assert default_st["agents"][aid]["delivered"] == pytest.approx(
                plain_st["agents"][aid]["delivered"], abs=1e-9)

    def test_nonzero_fraction_reduces_meads_outflow_without_changing_deliveries(self):
        """A non-zero fraction treats part of the LB agricultural draw as
        reused downstream, charging Mead's outflow for less of it,
        WITHOUT changing what any agent is delivered -- it is a
        bookkeeping change to Mead's outflow, not to the agents' own
        settlement."""
        zero_env, zero_st = self._settle(0.0)
        quarter_env, quarter_st = self._settle(0.25)
        half_env, half_st = self._settle(0.5)

        for aid in ("LB0", "LB1"):
            assert quarter_st["agents"][aid]["delivered"] == pytest.approx(
                zero_st["agents"][aid]["delivered"], abs=1e-9)
            assert half_st["agents"][aid]["delivered"] == pytest.approx(
                zero_st["agents"][aid]["delivered"], abs=1e-9)

        lb_ag_draw_maf = zero_st["lb_delivered_maf"]
        assert quarter_st["lb_return_flow_maf"] == pytest.approx(0.25 * lb_ag_draw_maf, abs=1e-9)
        assert half_st["lb_return_flow_maf"] == pytest.approx(0.5 * lb_ag_draw_maf, abs=1e-9)
        assert zero_st["lb_return_flow_maf"] == 0.0

        # More reused downstream -> less charged against Mead's outflow
        # -> more left in storage at year end (strictly increasing in
        # the fraction, all else equal).
        assert zero_st["mead_storage_end_maf"] < quarter_st["mead_storage_end_maf"] < half_st["mead_storage_end_maf"]
        assert half_st["mead_storage_end_maf"] - quarter_st["mead_storage_end_maf"] == pytest.approx(
            quarter_st["mead_storage_end_maf"] - zero_st["mead_storage_end_maf"], abs=1e-9,
        )  # linear in the fraction


# ===========================================================================
# Minimum-use floor as a config field (2026-10-06 CPU rerun finding, spec
# item 36k): promoted from the bare MIN_UTIL module constant to
# WaterSystemConfig.min_utilisation_fraction, default 0.10, byte-identical,
# so the 0 and 0.05 x W CPU sensitivities (provenance C6b) can be run via
# --min-utilisation-fraction instead of editing tracked code.
# ===========================================================================

class TestMinUtilisationFraction:
    def test_config_rejects_out_of_range_fraction(self):
        for bad in (-0.01, 1.01, -5.0, 2.0):
            with pytest.raises(ValueError, match="min_utilisation_fraction"):
                WaterSystemConfig(min_utilisation_fraction=bad)

    def test_boundary_values_are_accepted(self):
        WaterSystemConfig(min_utilisation_fraction=0.0)
        WaterSystemConfig(min_utilisation_fraction=1.0)

    def test_default_matches_the_min_util_module_constant(self):
        """MIN_UTIL (irrigation_env.py) is kept only as a literal mirror
        for the test suite's own assertions; this pins the two equal so
        they cannot silently drift apart (see MIN_UTIL's own comment)."""
        from examples.irrigation_abm.irrigation_env import MIN_UTIL
        assert WaterSystemConfig().min_utilisation_fraction == MIN_UTIL == 0.10

    def test_update_agent_request_floor_follows_the_config_not_the_default(self):
        """Proof that update_agent_request reads
        config.min_utilisation_fraction, not the module-level MIN_UTIL
        constant: a request strictly between the default floor (10% W)
        and a non-default floor (20% W) reads below_minimum_utilisation
        differently depending on which config the environment was built
        with."""
        water_right = 4_000_000.0
        request_between_floors = 0.15 * water_right  # below 20% W, above 10% W

        default_env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        default_env._agents["LB0"] = _agent("lower_basin", water_right, water_right)
        default_env.update_agent_request("LB0", request_between_floors)
        assert default_env._agents["LB0"]["below_minimum_utilisation"] is False

        raised_floor_env = IrrigationEnvironment(
            WaterSystemConfig(seed=42, min_utilisation_fraction=0.20)
        )
        raised_floor_env._agents["LB0"] = _agent("lower_basin", water_right, water_right)
        raised_floor_env.update_agent_request("LB0", request_between_floors)
        assert raised_floor_env._agents["LB0"]["below_minimum_utilisation"] is True

    def test_reset_requests_to_base_floor_follows_the_config_not_the_default(self):
        """Same proof as above for _reset_requests_to_base (the OTHER
        below_minimum_utilisation producer, run at the start of every
        year -- WP2 spec 2.1)."""
        water_right = 4_000_000.0
        base_between_floors = 0.15 * water_right

        default_env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        default_env._agents["LB0"] = _agent("lower_basin", base_between_floors, water_right)
        default_env._reset_requests_to_base()
        assert default_env._agents["LB0"]["below_minimum_utilisation"] is False

        raised_floor_env = IrrigationEnvironment(
            WaterSystemConfig(seed=42, min_utilisation_fraction=0.20)
        )
        raised_floor_env._agents["LB0"] = _agent("lower_basin", base_between_floors, water_right)
        raised_floor_env._reset_requests_to_base()
        assert raised_floor_env._agents["LB0"]["below_minimum_utilisation"] is True


class TestLbNonAgTotalMafValidation:
    """2026-10-06 Opus review P3-4: --lb-non-ag-total-maf is now threaded
    in from run_fql_baseline.py / run_experiment.py, so an out-of-range
    value (a typo, a unit confusion with AF instead of MAF) must be
    refused here rather than silently accepted into the physics."""

    def test_rejects_non_finite_values(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValueError, match="lb_non_ag_total_maf"):
                WaterSystemConfig(lb_non_ag_total_maf=bad)

    def test_rejects_non_positive_and_too_large_values(self):
        for bad in (0.0, -1.0, -5.2, 20.0, 25.0, 1_000_000.0):
            with pytest.raises(ValueError, match="lb_non_ag_total_maf"):
                WaterSystemConfig(lb_non_ag_total_maf=bad)

    def test_accepts_the_default_and_other_plausible_values(self):
        WaterSystemConfig()  # 5.2, the record-implied default
        WaterSystemConfig(lb_non_ag_total_maf=5.0)
        WaterSystemConfig(lb_non_ag_total_maf=0.01)
        WaterSystemConfig(lb_non_ag_total_maf=19.99)


# ===========================================================================
# 42-year mass balance closure at fixed demand
# ===========================================================================

class TestMassBalanceClosureV3:
    def test_synthetic_fixed_demand_42_years(self):
        """No decisions between advance_year() calls == every agent
        maintains its carried request (the F11b contract); residual below
        1e-9 MAF every year, exactly as required for a 42-year run over
        the full v3 hydrology table."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=11))
        env.initialize_synthetic(n_agents=24, basin_split=(10, 14))
        for year_index in range(1, 43):
            env.advance_year()
            st = env.settle_year()
            assert env._natural_flow_for_year(2018 + year_index) == pytest.approx(
                st["natural_flow_maf"]
            )
            lhs = (st["powell_storage_end_maf"] - st["powell_storage_maf"]) + (
                st["mead_storage_end_maf"] - st["mead_storage_maf"])
            withdrawals = st["lb_delivered_maf"] + st["lb_non_ag_delivered_maf"] + st["mexico_delivered_maf"]
            rhs = (st["natural_flow_maf"] + st["lb_tributary_maf"] - st["ub_non_farm_maf"]
                   - st["ub_delivered_maf"] - st["powell_evap_maf"] - st["mead_evap_maf"]
                   - withdrawals - st["mead_spill_maf"])
            assert abs(lhs - rhs) < 1e-9
            for aid, rec in st["agents"].items():
                assert rec["delivered"] <= rec["request"] + 1e-6

    @staticmethod
    def _run_real_2018_fixed_demand_42_years(ub_supply_mode: str, hold_requests_fixed: bool = True):
        """Shared body (WP1b, item 20): the L2-replay scenario, real
        78-agent 2018 requests, 42 years, under the given
        ``ub_supply_mode``. Asserts mass balance closes and natural flow
        equals the committed table every year; returns ``(tier_counts,
        mead_min_maf)`` for the caller to pin.

        ``hold_requests_fixed`` (WP2 review round 1, HIGH 1; default True,
        this scenario's original meaning): every agent's request stays at
        its 2018 use for the whole replay, via
        ``WaterSystemConfig.hold_requests_fixed`` -- NOT an emergent
        property of "no decisions are ever applied" any more, since
        ``IrrigationEnvironment._reset_requests_to_base`` (spec 2.1) runs
        unconditionally otherwise and would let a cut sub-basin's request
        decay below 2018 use after its first short year. ``False`` gives
        the OTHER real scenario -- every agent always chooses "keep",
        every year, with no other option ever available -- see
        ``TestKeepEveryYear42Years`` below, which pins that case
        separately."""
        rng = np.random.default_rng(7)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        env = IrrigationEnvironment(WaterSystemConfig(
            seed=7, ub_supply_mode=ub_supply_mode, hold_requests_fixed=hold_requests_fixed,
        ))
        env.initialize_from_profiles(profiles)
        tier_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        mead_min_maf = None
        for year_index in range(1, 43):
            env.advance_year()
            tier_counts[env._compute_shortage_tier()] += 1
            mead_1jan = env._mead_storage[-1]
            if mead_min_maf is None or mead_1jan < mead_min_maf:
                mead_min_maf = mead_1jan
            st = env.settle_year()
            assert env._natural_flow_for_year(2018 + year_index) == pytest.approx(
                st["natural_flow_maf"]
            )
            lhs = (st["powell_storage_end_maf"] - st["powell_storage_maf"]) + (
                st["mead_storage_end_maf"] - st["mead_storage_maf"])
            withdrawals = st["lb_delivered_maf"] + st["lb_non_ag_delivered_maf"] + st["mexico_delivered_maf"]
            rhs = (st["natural_flow_maf"] + st["lb_tributary_maf"] - st["ub_non_farm_maf"]
                   - st["ub_delivered_maf"] - st["powell_evap_maf"] - st["mead_evap_maf"]
                   - withdrawals - st["mead_spill_maf"])
            assert abs(lhs - rhs) < 1e-9
            assert st["powell_storage_end_maf"] >= env.config.powell_dead_pool_maf - 1e-9
            assert st["mead_storage_end_maf"] >= env.config.mead_dead_pool_maf - 1e-9
        return tier_counts, mead_min_maf

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_real_2018_fixed_demand_42_years(self):
        """The L2-replay scenario under ``ub_supply_mode="subbasin"``, the
        v3 default (WP1b, item 20).

        Re-review 2026-09-29 round 3 (NIT): also pins the shortage-tier
        counts and Mead's minimum 1 January storage this exact scenario
        produces -- confirmed to come from THIS real 78-agent run (not a
        smaller synthetic replay, LOW C), and matched independently on
        seed 7 here and seed 42 elsewhere to 4 decimal places (the
        aggregate is set by the real CRSS demand data, not the profile
        RNG seed).

        WP1b (2026-09-29): these values CHANGED from the WP1 pin
        ({0: 20, 1: 11, 2: 8, 3: 3}, mead_min ~7.3516 MAF / ~1,005.8 ft --
        now held under ``ub_supply_mode="lees_ferry_pool"``, see
        ``test_real_2018_fixed_demand_42_years_pool_mode`` below) once the
        Upper Basin's single 5.0 MAF-or-natural-flow pool was replaced by
        nine independent sub-basin supplies. Several sub-basins (UT1 most,
        per the sub-basin memo section 5: 2018 is UT1's highest use in 48
        years) are now short of their fixed 2018 request in below-median-
        flow years even though the Upper Basin AGGREGATE never was under
        the single pool (memo section 6: 19 short sub-basin-years at 2018
        use).

        WP2 review round 1 (HIGH 1, 2026-09-29): these values are held
        through ``hold_requests_fixed=True`` (the helper's default), which
        makes ``IrrigationEnvironment._reset_requests_to_base`` (spec 2.1,
        unconditional otherwise) a no-op for this replay, so this pin is
        UNCHANGED from the WP1b value above -- "2018 requests held fixed"
        means literally that again, not "every agent's first-ever
        shortfall permanently lowers its request". The OTHER real
        scenario -- every agent always chooses keep, so the reset DOES
        apply every year -- is a different experiment, pinned separately
        by ``TestKeepEveryYear42Years`` below.

        Spec items 25/26/27 (2026-09-29): moved AGAIN, from
        {0: 21, 1: 11, 2: 7, 3: 3} / 7.4665 MAF, by the same two default
        changes as every other pin in this module -- ``lb_non_ag_total_maf``
        5.0 -> 5.2 MAF (item 25) and ``powell_release_mode``
        "storage_balancing" -> "ig2007_tiers" (item 26/27, the 2007 Interim
        Guidelines Lake Powell operating tiers). Cross-checked against the
        design memo's own replay table (design memo
        .research/design_specs/irrigation_v3_powell_tiers_2026-09-29.md
        section 4, "A, 2018 use held (subbasin)": proposed 10/10/14/8, Mead
        minimum 7.0652 MAF, ~1,000.8 ft in 2024) and reproduced exactly
        here (7.065235... MAF).

        Item 36c (2026-10-05 design-basis audit + fix proposals, spec
        item 36c): the post2026 Equalization default moves from
        "hold_2026" to "extend_slope", moving tier counts from
        {0: 10, 1: 10, 2: 14, 3: 8} to the values below; Mead's minimum
        1 January storage is unchanged."""
        tier_counts, mead_min_maf = self._run_real_2018_fixed_demand_42_years("subbasin")
        assert tier_counts == {0: 7, 1: 11, 2: 16, 3: 8}
        assert mead_min_maf == pytest.approx(7.0652, abs=1e-3)  # ~1,000.8 ft (2024)

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_real_2018_fixed_demand_42_years_pool_mode(self):
        """The WP1 regression pin, held under ``ub_supply_mode=
        "lees_ferry_pool"`` (the SI mode, spec 1b.3) now that "subbasin"
        is the v3 default and changes these numbers (see
        ``test_real_2018_fixed_demand_42_years`` above): this is
        ``lees_ferry_pool`` mode's own bitwise reproduction of the pin
        WP1 originally pinned in this scenario, and must never drift.
        Held fixed the same way (``hold_requests_fixed=True``, the
        helper's default) -- though in this mode the single pool delivers
        every agent's full 2018 request every year regardless (delivered
        always equals requested), so the reset was always a no-op here.

        Spec items 25/26/27 (2026-09-29): moved AGAIN, from
        {0: 20, 1: 11, 2: 8, 3: 3} / 7.3516 MAF, for the SAME reason as
        the subbasin pin above (5.2 MAF non-ag bucket + ig2007_tiers).
        The design memo (section 4, "A, lees_ferry_pool") gives 10/8/17/7
        and states the Mead minimum is the SAME 7.0652 MAF "in both UB
        modes" -- reproduced exactly here.

        Item 36c (2026-10-05): the post2026 Equalization default move
        (hold_2026 -> extend_slope) moves this to 7/10/18/7; Mead's
        minimum is unchanged, still the SAME value as the "subbasin"
        pin above."""
        tier_counts, mead_min_maf = self._run_real_2018_fixed_demand_42_years("lees_ferry_pool")
        assert tier_counts == {0: 7, 1: 10, 2: 18, 3: 7}
        assert mead_min_maf == pytest.approx(7.0652, abs=1e-3)  # ~1,000.8 ft (2024)


class TestKeepEveryYear42Years:
    """WP2 review round 1 (HIGH 1, 2026-09-29): the OTHER real 42-year,
    no-agents scenario -- every agent always chooses "keep" (the only
    thing a no-decisions replay can represent once WP2's
    ``_reset_requests_to_base`` runs unconditionally by default), so a
    request follows its OWN delivery down after its first shortfall,
    exactly as a real "always keep" LLM or FQL agent's would (provenance
    B7/B8). This is a DIFFERENT scenario from
    ``TestMassBalanceClosureV3.test_real_2018_fixed_demand_42_years``
    (2018 requests held fixed forever, via ``hold_requests_fixed=True``)
    -- both are real, named scenarios, not one a regression of the other.
    """

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_keep_every_year_42_years_subbasin(self):
        """``hold_requests_fixed=False`` (the default -- every real LLM or
        FQL run's actual behaviour): under ``subbasin`` mode, a UB agent
        short in one of the 19 short sub-basin-years (memo section 6,
        starting with UT1 in 2020) has its request permanently track that
        lower delivery from then on. Less Upper Basin draw leaves more
        water for Powell's inflow than the held-fixed replay above, so
        more years clear Tier 0 (21->29) and Mead's 1 January minimum
        rises again (7.4665->7.4989 MAF, about 1,007.7 to 1,008.3 ft).

        WP1c (item 22, PI-approved 2026-09-29) moved this pin AGAIN, from
        {0: 29, 1: 7, 2: 4, 3: 2} / 7.4989 MAF to the values below: this is
        the one scenario in this file with real request FEEDBACK (a "keep"
        request tracks the AGENT'S OWN prior delivery, unlike the held-
        fixed replay above, where item 22 is proven mathematically inert
        in test_v3_lb_priority.py: TestSplitMatchesSeniorAllAggregate).
        item 22's split (the v3 default, lb_priority_mode="split") gives
        the six Arizona 4th/5th/6th-priority agents a genuinely smaller
        delivery than "senior_all" in a declared-tier year whenever their
        request already exceeds their (much smaller) senior entitlement --
        true from year 1 for several of them (e.g. MohaveValleyIDD's 2018
        use, 28,295 AF, is roughly 4.8x its PUBLISHED 5,940 AF senior
        entitlement, review round 2 MEDIUM 4) -- so their OWN subsequent
        "keep" requests decay lower than under "senior_all", shifting one
        year from Tier 2 to Tier 1 (Tier 1 count 7->8, Tier 2 count 4->3)
        over the 42-year trajectory and raising Mead's minimum a little
        further (7.4989->7.5184 MAF, about 1,008.3 to 1,008.6 ft).

        Review round 2 (MEDIUM 4, 2026-09-29): moved this pin's Mead
        minimum a further hair, from round 1's 7.5173 to 7.5184 MAF, when
        the split switched from a share of each agent's water_right to
        the agents' own PUBLISHED USBR entitlement figures (round 1's
        MohaveValleyIDD senior entitlement, 7,243.90 AF, was a share of
        its 50,000 AF water_right; the published figure is 5,940 AF, its
        actual Priority 1 entitlement) -- the Tier counts did not move
        again. Read directly off ``_run_real_2018_fixed_demand_42_years``
        (this test's own callee), not re-derived by hand.

        Spec items 25/26/27 (2026-09-29): moved AGAIN, from
        {0: 29, 1: 8, 2: 3, 3: 2} / 7.5184 MAF, by the same lb_non_ag
        5.0->5.2 MAF (item 25) and powell_release_mode
        storage_balancing->ig2007_tiers (item 26/27) default changes as
        every other pin in this module. The design memo's own replay
        table (section 4, "Keep every year") gives 17/11/8/6 and Mead
        minimum 7.1028 MAF -- reproduced exactly here.

        Item 36c (2026-10-05 design-basis audit + fix proposals, spec
        item 36c): the post2026 Equalization default move (hold_2026 ->
        extend_slope) moves tier counts to {0: 14, 1: 15, 2: 8, 3: 5};
        Mead's minimum is unchanged, still 7.1028 MAF."""
        tier_counts, mead_min_maf = (
            TestMassBalanceClosureV3._run_real_2018_fixed_demand_42_years(
                "subbasin", hold_requests_fixed=False,
            )
        )
        assert tier_counts == {0: 14, 1: 15, 2: 8, 3: 5}
        assert mead_min_maf == pytest.approx(7.1028, abs=1e-3)


# ===========================================================================
# 1.6 Per-sub-basin precipitation
# ===========================================================================

class TestPrecipOwnGroup:
    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_precip_own_group_nm(self):
        """An NM-group UB agent in 2019 reads the NM column x 25.4 mm; the
        flag compares against the 2018 row (H&Y's strict '>')."""
        rng = np.random.default_rng(1)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        nm_profiles = [p for p in profiles if p.precip_group == "NM"]
        assert nm_profiles, "expected at least one NM-group profile"
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env.initialize_from_profiles(profiles)
        env.load_crss_precipitation(
            str(CRSS_DB_DIR / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv")
        )
        env.advance_year()  # sim year 2019 -> calendar year 1988's row... see note below
        ctx = env.get_agent_context(nm_profiles[0].agent_id)
        # NOTE: precipitation is read from the PRISM CSV by CALENDAR year of
        # the CSV itself (2017-2060 index), independent of the hydrology
        # resample -- 2019 is literally row 2019 of the PRISM file, per
        # H&Y's own information design (D9/G4 in the provenance doc).
        assert ctx["precipitation"] == pytest.approx(5.591091328 * 25.4)
        assert ctx["precipitation_flag"] == 0  # 2019 (142.0 mm) < 2018 (233.8 mm)
        assert ctx["preceding_factor"] == ctx["precipitation_flag"]

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_precip_flag_seeded_from_2018_when_2019_is_wetter(self):
        """Review fix 2: load_crss_precipitation seeds _precip_history with
        the sim_start_year - 1 (2018) row, so every UB group's first
        (2019) flag compares 2019 against the real 2018 row rather than
        against nothing. UT1 is wetter in 2019 (1.899918 in) than 2018
        (1.680784 in), so the flag must be 1."""
        rng = np.random.default_rng(1)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        ut1_profiles = [p for p in profiles if p.precip_group == "UT1"]
        assert ut1_profiles, "expected at least one UT1-group profile"
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env.initialize_from_profiles(profiles)
        env.load_crss_precipitation(
            str(CRSS_DB_DIR / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv")
        )
        env.advance_year()  # sim year 2019 -> PRISM row 2019 (see note above)
        ctx = env.get_agent_context(ut1_profiles[0].agent_id)
        assert ctx["precipitation"] == pytest.approx(1.899917512 * 25.4)
        assert ctx["precipitation_flag"] == 1  # 2019 (48.26 mm) > 2018 (42.69 mm)
        assert ctx["preceding_factor"] == ctx["precipitation_flag"]

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_az_ub_group_reads_az_column(self):
        """AZ_UB agents read PRISM column 'AZ', not 'AZ_UB' (spec 1.6)."""
        rng = np.random.default_rng(1)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        az_profiles = [p for p in profiles if p.precip_group == "AZ"]
        assert az_profiles, "expected at least one AZ_UB-group (precip_group='AZ') profile"

    def test_agent_without_precip_group_falls_back_to_basin_mean(self):
        """A synthetic/mock profile with no precip_group still gets a
        sane, present precipitation value (the basin-level legacy mean),
        not a KeyError or crash."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env.initialize_synthetic(n_agents=4, basin_split=(2, 2))
        env.advance_year()
        ub_agent = next(a for a in env.agent_ids if env._agents[a]["basin"] == "upper_basin")
        assert env._agents[ub_agent].get("precip_group") is None
        ctx = env.get_agent_context(ub_agent)
        assert ctx["precipitation"] > 0
        assert ctx["precipitation_flag"] in (0, 1)
