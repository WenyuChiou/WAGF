"""Irrigation case study v3, WP1e: the 2007 Interim Guidelines Lake Powell
operational tiers (spec items 26, 27).

Design: .research/design_specs/irrigation_v3_powell_tiers_2026-09-29.md
(design memo section 3, "Design specification"; orchestrator-accepted
2026-09-29, item 27). All tests here fail on the pre-item-26/27 code,
where ``_plan_powell_release_ig2007``, ``PowellReleasePlan``,
``_powell_active_storage_at``, ``_powell_elevation_ft``,
``_powell_equalization_elevation_ft``, ``WaterSystemConfig.
powell_release_mode`` and ``WaterSystemConfig.powell_post2026_equalization``
do not exist (an ``AttributeError`` / ``TypeError`` at collection or call
time), and every tier-specific assertion below would in any case be
scored against the OLD storage-balancing algebra, which uses no ROD tiers
at all.

Covers (design memo section 3, "Tests"):
  1. the Equalization elevation table and the six-point p.50 curve;
  2. tier boundaries ("at or above" is inclusive, ROD Section 6);
  3. each tier's release, the equal-active-storage balance, the 1,105 ft
     proviso (6.A.1), the April adjustment both ways (6.B.3, 6.B.4), and
     the 1,025 ft Mid-Elevation-Release switch (6.C.1);
  4. the post-2026 Equalization-elevation extension options;
  5. the release planned once on 1 January, and 42-year mass balance
     closure, in BOTH ``powell_release_mode`` values;
  6. ``storage_balancing`` reproducing the pre-item-26/27 pin exactly
     (bit-identical to 58a1d0ea when combined with the pre-item-25
     ``lb_non_ag_total_maf=5.0`` -- the fuller, git-diff-based version of
     this check is ``test_v3_lb_priority.py::TestSeniorAllBitIdenticalToHead``);
  7. the new ig2007 headline replay numbers -- pinned in
     ``test_v3_water_system.py`` (``TestMassBalanceClosureV3``,
     ``TestKeepEveryYear42Years``) and ``test_v3_lb_priority.py``
     (``TestSplitMatchesSeniorAllAggregate``), not repeated here;
  8. the hindcast's own 1-January-tier-vs-declared-AOP-tier check (the
     M1-M3 gates themselves are ``test_v3_hindcast.py``'s job).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from examples.irrigation_abm.irrigation_env import (
    POWELL_CURVE_ACTIVE_STORAGE_MAF,
    POWELL_CURVE_ELEVATION_FT,
    POWELL_EQ_ELEVATION_FT_BY_YEAR,
    UB_SUBBASINS,
    IrrigationEnvironment,
    PowellReleasePlan,
    WaterSystemConfig,
)

CRSS_PARAMS_CSV = Path("ref/RL-ABM-CRSS/ALL_colorado_ABM_params_cal_1108.csv")
CRSS_DB_DIR = Path("ref/CRSS_DB/CRSS_DB")
_REAL_REF_AVAILABLE = CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir()

# A large, basin-wide-backstop-free placeholder (every real per-sub-basin
# check lives in test_v3_ub_subbasin_supply.py; the scenarios here send
# ub_requested_maf=0.0 so no sub-basin's own availability ever binds).
_SUBS_PLACEHOLDER = {s: 5.0 for s in UB_SUBBASINS}

# Common inputs for the tier-release scenarios below: a mid-sized natural
# flow, a fixed tributary/Mexico/Lower-Basin-request set, no Upper Basin
# request (so ub_non_farm/d_u_plan/inflow_plan reduce to the simplest
# case: min(nf, 1.2213) taken first, then the rest is inflow) and no
# declared Lower Basin shortage (shortage_volume=0). Year 2019
# (Equalization elevation 3,655 ft, active storage 17.915 MAF) unless a
# scenario says otherwise.
_NF, _TRIB, _MEXICO, _LB_REQ, _YEAR = 12.0, 0.8, 1.5, 2.6, 2019


def _plan(s_p: float, s_m: float, *, year: int = _YEAR, shortage_volume: float = 0.0,
          mexico: float = _MEXICO, lb_requested_maf: float = _LB_REQ,
          nf: float = _NF, trib: float = _TRIB) -> PowellReleasePlan:
    cfg = WaterSystemConfig(powell_release_mode="ig2007_tiers")
    env = IrrigationEnvironment(cfg)
    return env._plan_powell_release_ig2007(
        nf=nf, s_p=s_p, s_m=s_m, trib=trib, shortage_volume=shortage_volume,
        mexico=mexico, ub_requested_maf=0.0, lb_requested_maf=lb_requested_maf,
        year=year, ub_requested_by_subbasin_maf={None: 0.0},
        ub_available_by_subbasin_maf=_SUBS_PLACEHOLDER,
    )


# ===========================================================================
# 1. Equalization elevation table and the six-point p.50 curve
# ===========================================================================

class TestEqualizationElevationTable:
    def test_table_matches_rod_p51(self):
        """2007 ROD p. 51: 2008 = 3,636 ft; 2019 = 3,655 ft (H&Y's own year
        1); 2026 (last published) = 3,666 ft; every year 2008-2026 present,
        no gaps."""
        assert POWELL_EQ_ELEVATION_FT_BY_YEAR[2008] == 3636.0
        assert POWELL_EQ_ELEVATION_FT_BY_YEAR[2019] == 3655.0
        assert POWELL_EQ_ELEVATION_FT_BY_YEAR[2026] == 3666.0
        assert sorted(POWELL_EQ_ELEVATION_FT_BY_YEAR) == list(range(2008, 2027))
        # Strictly increasing (ROD p. 51's schedule never plateaus or drops).
        values = [POWELL_EQ_ELEVATION_FT_BY_YEAR[y] for y in range(2008, 2027)]
        assert all(b > a for a, b in zip(values, values[1:]))

    def test_equalization_elevation_ft_raises_before_2008(self):
        env = IrrigationEnvironment(WaterSystemConfig())
        with pytest.raises(ValueError, match="2008"):
            env._powell_equalization_elevation_ft(2007)
        with pytest.raises(ValueError):
            env._powell_equalization_elevation_ft(1999)

    def test_equalization_elevation_ft_matches_table_2008_to_2026(self):
        env = IrrigationEnvironment(WaterSystemConfig())
        for year, ft in POWELL_EQ_ELEVATION_FT_BY_YEAR.items():
            assert env._powell_equalization_elevation_ft(year) == pytest.approx(ft)


class TestPowellCurve:
    def test_curve_anchors_match_rod_p50(self):
        """2007 ROD p. 50 tier diagram, Powell ACTIVE storage (MAF) at six
        elevations: 3,370/0; 3,525/5.93; 3,575/9.52; 3,636/15.54;
        3,666/19.29; 3,700/24.32 (full pool)."""
        env = IrrigationEnvironment(WaterSystemConfig())
        expected = dict(zip(POWELL_CURVE_ELEVATION_FT, POWELL_CURVE_ACTIVE_STORAGE_MAF))
        assert expected[3370.0] == 0.0
        assert expected[3525.0] == 5.93
        assert expected[3575.0] == 9.52
        assert expected[3636.0] == 15.54
        assert expected[3666.0] == 19.29
        assert expected[3700.0] == 24.32
        for ft, maf in expected.items():
            assert env._powell_active_storage_at(ft) == pytest.approx(maf)

    def test_curve_monotone_and_round_trips(self):
        env = IrrigationEnvironment(WaterSystemConfig())
        assert all(b > a for a, b in zip(POWELL_CURVE_ACTIVE_STORAGE_MAF,
                                          POWELL_CURVE_ACTIVE_STORAGE_MAF[1:]))
        for total_maf in (1.89, 5.0, 11.99, 20.0, 26.21):
            ft = env._powell_elevation_ft(total_maf)
            active = env._powell_active_storage_at(ft)
            assert active == pytest.approx(max(0.0, total_maf - 1.89), abs=1e-6)

    def test_elevation_beyond_full_pool_returns_infinite_active_storage(self):
        """The USBR 2012 Basin Study slope extension (extend_slope) can
        push a late-run Equalization elevation past 3,700 ft (full pool,
        design memo section 3); Powell can never physically reach it, so
        the EQ tier's own condition (a_p >= a_eq) must never spuriously
        hold there."""
        env = IrrigationEnvironment(WaterSystemConfig())
        assert env._powell_active_storage_at(3700.0) == pytest.approx(24.32)
        assert env._powell_active_storage_at(3717.0) == float("inf")


# ===========================================================================
# 4. Post-2026 Equalization-elevation extension options
# ===========================================================================

class TestPost2026Extension:
    def test_extend_slope_default(self):
        """Item 36c (2026-10-05 design-basis audit + fix proposals, spec
        item 36c): "extend_slope" is now the v3 default -- USBR's own
        documented CRSS continuation practice (the 2012 Colorado River
        Basin Study, Technical Report G Appendix G2, and Reclamation's
        5-Year Probabilistic Projections page), not a stated assumption
        of this model's own. Before item 36c the default was
        "hold_2026" (see test_hold_2026_opt_in below, now the SI
        sensitivity)."""
        env = IrrigationEnvironment(WaterSystemConfig())
        assert env.config.powell_post2026_equalization == "extend_slope"
        slope = (3666.0 - 3645.0) / (2026 - 2012)
        assert slope == pytest.approx(1.5, abs=0.01)
        assert env._powell_equalization_elevation_ft(2027) == pytest.approx(3666.0 + slope)
        assert env._powell_equalization_elevation_ft(2060) == pytest.approx(3666.0 + slope * 34)

    def test_extend_slope(self):
        """USBR 2012 Colorado River Basin Study, Technical Report G
        Appendix G2: extends the 2012-2026 slope, about 1.5 ft/yr
        ((3,666 - 3,645) / (2026 - 2012))."""
        env = IrrigationEnvironment(WaterSystemConfig(powell_post2026_equalization="extend_slope"))
        slope = (3666.0 - 3645.0) / (2026 - 2012)
        assert slope == pytest.approx(1.5, abs=0.01)
        assert env._powell_equalization_elevation_ft(2027) == pytest.approx(3666.0 + slope)
        assert env._powell_equalization_elevation_ft(2060) == pytest.approx(3666.0 + slope * 34)

    def test_hold_2026_opt_in(self):
        """"hold_2026" (pre-2026-10-05 default; now the SI sensitivity, a
        stated ASSUMPTION rather than USBR's own documented practice)
        still works exactly as before, opted into explicitly."""
        env = IrrigationEnvironment(WaterSystemConfig(powell_post2026_equalization="hold_2026"))
        assert env._powell_equalization_elevation_ft(2027) == pytest.approx(3666.0)
        assert env._powell_equalization_elevation_ft(2060) == pytest.approx(3666.0)

    def test_config_rejects_invalid_option(self):
        with pytest.raises(ValueError, match="powell_post2026_equalization"):
            WaterSystemConfig(powell_post2026_equalization="reset_isg")

    def test_config_rejects_invalid_release_mode(self):
        with pytest.raises(ValueError, match="powell_release_mode"):
            WaterSystemConfig(powell_release_mode="ig2007")  # missing "_tiers"


# ===========================================================================
# 2. Tier boundaries: "at or above" is inclusive (ROD Section 6)
# ===========================================================================

class TestTierBoundariesInclusive:
    def test_mer_leb_boundary_at_3525_ft(self):
        dp = WaterSystemConfig().powell_dead_pool_maf
        at = _plan(dp + 5.93, 16.0)
        below = _plan(dp + 5.93 - 1e-6, 16.0)
        assert at.tier == "MER"
        assert below.tier == "LEB"

    def test_ueb_mer_boundary_at_3575_ft(self):
        dp = WaterSystemConfig().powell_dead_pool_maf
        at = _plan(dp + 9.52, 16.0)
        below = _plan(dp + 9.52 - 1e-6, 16.0)
        assert at.tier == "UEB"
        assert below.tier == "MER"

    def test_eq_ueb_boundary_at_equalization_elevation(self):
        env = IrrigationEnvironment(WaterSystemConfig())
        dp = env.config.powell_dead_pool_maf
        a_eq = env._powell_active_storage_at(env._powell_equalization_elevation_ft(_YEAR))
        at = _plan(dp + a_eq, 16.0)
        below = _plan(dp + a_eq - 1e-6, 16.0)
        assert at.tier == "EQ"
        assert below.tier == "UEB"

    def test_mead_1025_ft_switch_inclusive(self):
        """6.C.1: Mead >= 1,025 ft releases 7.48 MAF; below it, 8.23 MAF."""
        env = IrrigationEnvironment(WaterSystemConfig())
        s_m_1025 = env._elevation_to_storage(1025.0)
        at = _plan(8.0, s_m_1025)
        below = _plan(8.0, s_m_1025 - 1e-6)
        assert at.tier == "MER" and at.release_maf == pytest.approx(7.48)
        assert below.tier == "MER" and below.release_maf == pytest.approx(8.23)

    def test_mead_1075_ft_switch_inclusive(self):
        """6.B.1 vs 6.B.2: at exactly 1,075 ft the >= branch (whose own
        release is 8.23 MAF, or -- as at this exact snapshot -- its 6.B.4
        April-adjustment variant, still a MEMBER of the >=1,075 family)
        is entered, not 6.B.2's balancing formula."""
        env = IrrigationEnvironment(WaterSystemConfig())
        s_m_1075 = env._elevation_to_storage(1075.0)
        at = _plan(12.0, s_m_1075)
        below = _plan(12.0, s_m_1075 - 1e-6)
        assert at.tier == "UEB" and at.rule != "6.B.2"
        assert below.tier == "UEB" and below.rule == "6.B.2"


# ===========================================================================
# 3. Each tier's release
# ===========================================================================

class TestTierReleases:
    def test_leb_clamps_to_balancing_band(self):
        """6.D.1: Powell well below 3,525 ft -> clamp(r_bal, 7.0, 9.5).
        Mead here is high enough that pure equalization wants far less
        than 7.0 MAF, so the floor binds."""
        plan = _plan(4.0, 16.0)
        assert plan.tier == "LEB" and plan.rule == "6.D.1"
        assert plan.release_maf == pytest.approx(7.0)

    def test_mer_releases_748_when_mead_at_or_above_1025(self):
        plan = _plan(8.0, 10.0)
        assert plan.tier == "MER" and plan.rule == "6.C.1 (7.48)"
        assert plan.release_maf == pytest.approx(7.48)

    def test_mer_releases_823_when_mead_below_1025(self):
        plan = _plan(8.0, 8.0)
        assert plan.tier == "MER" and plan.rule == "6.C.1 (8.23)"
        assert plan.release_maf == pytest.approx(8.23)

    def test_ueb_releases_823_when_mead_at_or_above_1075_no_april_trigger(self):
        plan = _plan(12.0, 16.0)
        assert plan.tier == "UEB" and plan.rule == "6.B.1"
        assert plan.release_maf == pytest.approx(8.23)

    def test_ueb_balances_within_7_to_9_when_mead_below_1075(self):
        """6.B.2: the pure equalizing release here (r_bal ~= 12.97 MAF,
        independently recomputed in the test) exceeds 9.0, so it clamps
        to the UPPER end of [7.0, 9.0] -- a real clamp, not a coincidence
        (confirmed by recomputing r_bal from the same shared formula
        _plan_powell_release_storage_balancing and this method both use
        for their projected pieces)."""
        env = IrrigationEnvironment(WaterSystemConfig())
        cfg = env.config
        ub_non_farm = min(_NF, cfg.ub_non_farm_depletion_maf)
        nf_net = _NF - ub_non_farm
        e_p_plan = env._powell_evaporation_maf(12.0)
        p0 = 12.0 + nf_net - e_p_plan - cfg.powell_dead_pool_maf
        e_m = env._mead_evaporation_maf(6.0)
        o_projected = _LB_REQ + cfg.lb_non_ag_total_maf + _MEXICO
        m0 = 6.0 + _TRIB - e_m - o_projected - cfg.mead_dead_pool_maf
        r_bal = (p0 - m0) / 2.0
        assert r_bal > 9.0, "scenario must actually need clamping, or this test proves nothing"

        plan = _plan(12.0, 6.0)
        assert plan.tier == "UEB" and plan.rule == "6.B.2"
        assert plan.release_maf == pytest.approx(9.0)

    def test_april_6b3_equalization_supersedes_6b1(self):
        """6.B.3: Powell high enough that even the 8.23 MAF 6.B.1 release
        would leave it above the Equalization elevation on 31 December --
        the Equalization release governs instead."""
        plan = _plan(18.0, 16.0)
        assert plan.tier == "UEB"
        assert plan.rule.startswith("6.B.3 -> 6.A.1")
        assert plan.release_maf == pytest.approx(8.492967, abs=1e-4)
        assert 8.23 < plan.release_maf < 9.0

    def test_april_6b4_raises_release_to_protect_mead(self):
        """6.B.4: Mead starts at/above 1,075 ft (so the 6.B.1 branch is
        entered), but the projected 31 December state under an 8.23 MAF
        release would leave Mead below 1,075 ft while Powell stays at or
        above 3,575 ft -- the release is raised within [8.23, 9.0]."""
        plan = _plan(12.0, 12.2)
        assert plan.tier == "UEB" and plan.rule == "6.B.4"
        assert plan.release_maf == pytest.approx(9.0)
        assert 8.23 <= plan.release_maf <= 9.0

    def test_equalization_basic(self):
        """6.A.1, no proviso: max(8.23, min(r_bal, p0 - a_eq))."""
        plan = _plan(22.0, 20.0)
        assert plan.tier == "EQ" and plan.rule == "6.A.1"
        assert plan.release_maf == pytest.approx(11.049957, abs=1e-4)

    def test_equalization_2011_case(self):
        """The design memo's headline reproduced event (section 4, 7):
        Powell far above its Equalization elevation and Mead comparatively
        low reproduces a large equalizing release (14.63 MAF observed in
        water year 2011; TestHindcastTierMatchesDeclaredAOP below drives
        this from the real 2011 state end to end)."""
        plan = _plan(26.0, 6.0, year=2012)  # year 2012's EQ elevation, closest to the 2011 event
        assert plan.tier == "EQ"
        assert plan.release_maf > 12.0

    def test_1105_ft_proviso_raises_release_above_pure_eq_floor(self):
        """6.A.1 proviso: the pure "hold Powell at its EQ elevation"
        release (r_floor) is below what equalization alone (r_bal) would
        give, AND Mead at that lower release would still sit below
        1,105 ft on 31 December -- the release is raised (bounded by
        r_bal, by what it takes to reach 1,105 ft on Mead, and by holding
        Powell at 20 ft below its EQ elevation)."""
        no_proviso_like = _plan(22.0, 20.0)  # from test_equalization_basic: no proviso
        assert "proviso" not in no_proviso_like.rule

        plan = _plan(24.0, 6.0)
        assert plan.tier == "EQ"
        assert plan.rule == "6.A.1 (1,105 ft proviso)"
        assert plan.release_maf == pytest.approx(16.806412, abs=1e-4)
        # The proviso release is strictly larger than the plain r_floor
        # release would have been (max(8.23, min(r_bal, r_floor))) --
        # otherwise the proviso branch changed nothing.
        env = IrrigationEnvironment(WaterSystemConfig())
        cfg = env.config
        nf_net = _NF - min(_NF, cfg.ub_non_farm_depletion_maf)
        e_p_plan = env._powell_evaporation_maf(24.0)
        p0 = 24.0 + nf_net - e_p_plan - cfg.powell_dead_pool_maf
        e_m = env._mead_evaporation_maf(6.0)
        o_projected = _LB_REQ + cfg.lb_non_ag_total_maf + _MEXICO
        m0 = 6.0 + _TRIB - e_m - o_projected - cfg.mead_dead_pool_maf
        r_bal = (p0 - m0) / 2.0
        eq_ft = env._powell_equalization_elevation_ft(_YEAR)
        a_eq = env._powell_active_storage_at(eq_ft)
        r_floor = p0 - a_eq
        release_without_proviso = max(8.23, min(r_bal, r_floor))
        assert plan.release_maf > release_without_proviso + 1e-6

    def test_release_never_exceeds_projected_availability(self):
        """The physical cap (min(release, available_p_plan)) still applies
        in ig2007_tiers mode, exactly as in storage_balancing: Powell
        nearly empty (LEB tier, whose OWN target clamps to at least the
        7.0 MAF floor) with a natural flow barely above the Upper Basin
        non-farm amount (1.2213 MAF) leaves almost no projected inflow, so
        the physically-capped release is 0.0, far below the tier's own
        7.0 MAF floor target."""
        dp = WaterSystemConfig().powell_dead_pool_maf
        plan = _plan(dp + 0.01, 6.0, nf=1.3)
        assert plan.tier == "LEB"
        assert plan.release_maf == pytest.approx(0.0, abs=1e-9)


# ===========================================================================
# 5. Release planned once on 1 January; 42-year mass balance, both modes
# ===========================================================================

class TestReleasePlannedOnceAndMassBalance:
    @pytest.mark.parametrize("mode", ["storage_balancing", "ig2007_tiers"])
    def test_planned_release_does_not_move_with_mid_year_request_changes(self, mode):
        """Weak invariant check, both modes: the STORED plan never moves.
        For ``ig2007_tiers`` this seed's year-1 tier happens to be the
        FIXED 6.B.1 rule (release == 8.23 MAF regardless of request
        totals), so on its own it cannot tell a correctly-frozen plan from
        a mutant that replans off LIVE (post-mutation) requests -- both
        give 8.23 MAF here. See
        ``test_planned_release_does_not_move_with_mid_year_request_changes_ig2007_sensitive_tier``
        below for a scenario that actually discriminates (re-review
        2026-09-29 round 4, LOW 8)."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=11, powell_release_mode=mode))
        env.initialize_synthetic(n_agents=24, basin_split=(10, 14))
        env.advance_year()
        planned = env._snapshot["powell_release_planned_maf"]
        provisional = env.settle_year()
        assert provisional["powell_release_maf"] == pytest.approx(planned)
        for agent in env._agents.values():
            agent["request"] = min(agent["request"] * 1.15, agent["water_right"])
        after = env.settle_year()
        assert env._snapshot["powell_release_planned_maf"] == pytest.approx(planned)
        assert after["powell_release_maf"] == pytest.approx(planned)

    def test_planned_release_does_not_move_with_mid_year_request_changes_ig2007_sensitive_tier(self):
        """The scenario above lands in a tier/rule whose release is a
        FIXED constant (6.B.1's 8.23 MAF) or a clamped boundary, so it
        cannot distinguish "planned once from frozen requests" from a
        live-replan bug. This scenario lands in the Lower Elevation
        Balancing tier (6.D.1) with the balancing release comfortably
        INSIDE the [7.0, 9.5] MAF band (not pinned to either bound), where
        the release genuinely depends on the projected request totals --
        confirmed below by showing a mutant that replans from the LIVE
        (post-mutation) totals would give a measurably different release
        (0.075 MAF) than the correctly-frozen one, before checking that
        the real environment's stored plan matches the frozen value, not
        the mutant's."""
        config = WaterSystemConfig(seed=23, powell_release_mode="ig2007_tiers",
                                    ub_supply_mode="lees_ferry_pool")
        env = IrrigationEnvironment(config)
        env._powell_storage = 5.0   # LEB tier: active storage 3.11 MAF, well below the 5.93 MAF MER floor
        env._mead_storage = [5.0]
        base_ub_maf, base_lb_maf = 1.0, 2.0
        env._agents["UB1"] = {
            "basin": "upper_basin", "diversion": base_ub_maf * 1e6, "request": base_ub_maf * 1e6,
            "water_right": 4_950_000.0, "curtailment_ratio": 0.0, "delivery_ratio": 1.0,
            "gap_reason": "none", "at_allocation_cap": False, "has_efficient_system": False,
            "below_minimum_utilisation": False, "cluster": "x", "mu": 0.2, "sigma": 0.5,
            "bin_size_af": 10_000.0, "step_bin_af": 10_000.0, "supply_group": None,
            "ub_subbasin_member_count": None, "ub_subbasin_ratio": None,
            "ub_subbasin_sole_bound": 0.0,
        }
        env._agents["LB1"] = {
            "basin": "lower_basin", "diversion": base_lb_maf * 1e6, "request": base_lb_maf * 1e6,
            "water_right": 4_000_000.0, "curtailment_ratio": 0.0, "delivery_ratio": 1.0,
            "gap_reason": "none", "at_allocation_cap": False, "has_efficient_system": False,
            "below_minimum_utilisation": False, "cluster": "x", "mu": 0.2, "sigma": 0.5,
            "bin_size_af": 10_000.0, "step_bin_af": 10_000.0,
        }

        env.advance_year()  # first-ever call: reset/sums/plan all still run
        frozen_plan = env._snapshot["powell_release_planned_maf"]
        assert env._powell_plan_detail["tier"] == "LEB", (
            "scenario drifted out of the Lower Elevation Balancing tier -- "
            "adjust s_p/s_m, or this test no longer exercises a "
            "request-sensitive release"
        )
        assert env._snapshot["ub_request_projected_maf"] == pytest.approx(base_ub_maf)
        assert env._snapshot["lb_request_projected_maf"] == pytest.approx(base_lb_maf)

        common_kwargs = dict(
            nf=env._snapshot["natural_flow"], s_p=env._snapshot["powell_storage"],
            s_m=env._snapshot["mead_storage"], trib=env._snapshot["lb_tributary"],
            shortage_volume=env._snapshot["lb_shortage_volume_maf"], mexico=env._snapshot["mexico"],
            year=env._current_year,
        )
        recomputed_from_frozen = env._plan_powell_release(
            ub_requested_maf=base_ub_maf, lb_requested_maf=base_lb_maf, **common_kwargs
        )
        mutated_ub_maf, mutated_lb_maf = base_ub_maf * 1.15, base_lb_maf * 1.15
        recomputed_from_live_mutant = env._plan_powell_release(
            ub_requested_maf=mutated_ub_maf, lb_requested_maf=mutated_lb_maf, **common_kwargs
        )
        assert recomputed_from_frozen == pytest.approx(frozen_plan)
        # The scenario must actually discriminate a live-replan mutant, or
        # this test proves nothing about which totals advance_year() used.
        assert recomputed_from_live_mutant == pytest.approx(frozen_plan + 0.075, abs=1e-3), (
            "the live-replan mutant no longer gives a measurably different "
            "release from the frozen one -- this scenario stopped "
            "discriminating"
        )

        for agent in env._agents.values():
            agent["request"] = agent["request"] * 1.15
        after = env.settle_year()
        # The REAL regression check: advance_year() already froze the plan
        # from the BASE requests -- a live-replan bug would move this
        # toward recomputed_from_live_mutant instead.
        assert env._snapshot["powell_release_planned_maf"] == pytest.approx(frozen_plan)
        assert after["powell_release_maf"] == pytest.approx(frozen_plan)

    @pytest.mark.parametrize("mode", ["storage_balancing", "ig2007_tiers"])
    def test_42_year_mass_balance_closes(self, mode):
        env = IrrigationEnvironment(WaterSystemConfig(seed=17, powell_release_mode=mode))
        env.initialize_synthetic(n_agents=20, basin_split=(8, 12))
        for _ in range(42):
            env.advance_year()
            st = env.settle_year()
            lhs = (st["powell_storage_end_maf"] - st["powell_storage_maf"]) + (
                st["mead_storage_end_maf"] - st["mead_storage_maf"])
            withdrawals = st["lb_delivered_maf"] + st["lb_non_ag_delivered_maf"] + st["mexico_delivered_maf"]
            rhs = (st["natural_flow_maf"] + st["lb_tributary_maf"] - st["ub_non_farm_maf"]
                   - st["ub_delivered_maf"] - st["powell_evap_maf"] - st["mead_evap_maf"]
                   - withdrawals - st["mead_spill_maf"])
            assert abs(lhs - rhs) < 1e-9
            assert st["powell_storage_end_maf"] >= env.config.powell_dead_pool_maf - 1e-9
            assert st["mead_storage_end_maf"] >= env.config.mead_dead_pool_maf - 1e-9

    def test_ig2007_tiers_logs_tier_and_rule_every_year(self):
        """advance_year() writes powell_tier / powell_tier_rule to the
        snapshot and the settlement (design memo, "Functions"); institutions()
        reports the mode and the most recently planned tier."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=9))
        env.initialize_synthetic(n_agents=10, basin_split=(4, 6))
        for _ in range(3):
            env.advance_year()
            st = env.settle_year()
            assert st.get("powell_tier") in ("EQ", "UEB", "MER", "LEB")
            assert isinstance(st.get("powell_tier_rule"), str)
        assert env.institutions["reservoirs"]["powell_release_mode"] == "ig2007_tiers"
        assert env.institutions["reservoirs"]["powell_tier"] in ("EQ", "UEB", "MER", "LEB")

    def test_storage_balancing_logs_no_tier(self):
        env = IrrigationEnvironment(WaterSystemConfig(seed=9, powell_release_mode="storage_balancing"))
        env.initialize_synthetic(n_agents=10, basin_split=(4, 6))
        env.advance_year()
        st = env.settle_year()
        assert st.get("powell_tier") is None
        assert st.get("powell_tier_rule") == "storage_balancing"
        assert env.institutions["reservoirs"]["powell_tier"] is None


# ===========================================================================
# 6. storage_balancing reproduces the pre-item-26/27 pin exactly
# ===========================================================================

class TestStorageBalancingUnchangedFromHead:
    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_storage_balancing_at_5p0_matches_58a1d0ea_pin(self):
        """Both defaults pinned back to what they were at 58a1d0ea
        (lb_non_ag_total_maf=5.0, item 25; powell_release_mode=
        "storage_balancing", item 26/27): reproduces the ORIGINAL
        {0: 21, 1: 11, 2: 7, 3: 3} / 7.4665 MAF real-78-agent 2018-fixed-
        demand pin exactly. The fuller, field-by-field check against a
        LIVE git extraction of 58a1d0ea itself (not just these two
        aggregate numbers) is
        test_v3_lb_priority.py::TestSplitDefaultBitIdenticalTo58a1d0ea
        (corrected 2026-09-29 round 4, LOW 7 -- this docstring previously
        pointed at TestSeniorAllBitIdenticalToHead, which validates a
        DIFFERENT claim: "senior_all" against 38e5c34b, not the v3-default
        "split" against 58a1d0ea); this test is the fast, git-independent
        confirmation of the same aggregate numbers."""
        import numpy as np
        from examples.irrigation_abm.irrigation_personas import create_profiles_from_data

        rng = np.random.default_rng(7)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        env = IrrigationEnvironment(WaterSystemConfig(
            seed=7, ub_supply_mode="subbasin", hold_requests_fixed=True,
            lb_non_ag_total_maf=5.0, powell_release_mode="storage_balancing",
        ))
        env.initialize_from_profiles(profiles)
        tier_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        mead_min_maf = None
        for _ in range(42):
            env.advance_year()
            tier_counts[env._compute_shortage_tier()] += 1
            mead_1jan = env._mead_storage[-1]
            if mead_min_maf is None or mead_1jan < mead_min_maf:
                mead_min_maf = mead_1jan
            env.settle_year()
        assert tier_counts == {0: 21, 1: 11, 2: 7, 3: 3}
        assert mead_min_maf == pytest.approx(7.4665, abs=1e-3)


class TestStorageBalancingHindcast:
    """Re-review 2026-09-29 round 4 (LOW 6): the storage_balancing
    hindcast numbers the design memo's own prototype table reports
    (13.0 ft / +1.09 MAF / KGE 0.74 at the v3-default 5.2 MAF bucket) --
    test_v3_hindcast.py's default-constant test docstring pointed here;
    this is that test."""

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_storage_balancing_at_5p2_hindcast(self):
        from examples.irrigation_abm.analysis import hindcast_v3 as hv

        r = hv.run_hindcast(2000, 2018, powell_release_mode="storage_balancing")
        assert r.gate == {"M1": True, "M2": True, "M3_bias": True, "M3_change": True}
        assert r.metrics["M1_mead_mae_ft"] == pytest.approx(13.0, abs=0.1)
        # Item 36f/36g (2026-10-05): the hindcast runs on real agent
        # profiles, so the basin-specific water-right formula shifts this
        # pin slightly (1.09 -> 1.08 MAF); re-pinned to the new value,
        # same tolerance. The gate (above) is the actual acceptance
        # bound and is unaffected.
        assert r.metrics["M3_combined_bias_maf"] == pytest.approx(1.08, abs=0.01)
        assert r.metrics["mead_kge"] == pytest.approx(0.74, abs=0.01)

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_storage_balancing_split_sample_mode_reaches_every_row(self):
        """Re-review 2026-09-29 round 5 (L2): ``split_sample`` previously
        ignored ``powell_release_mode`` entirely, so ``main()``'s
        ``--powell-release-mode`` only ever reached the "pre-registered"
        and "reference 5.0" rows, never the split-sample ones -- every
        split-sample row silently ran under whatever WaterSystemConfig's
        OWN default was (ig2007_tiers), regardless of what was asked for.
        Threaded through now: the two "derived on X" rows scored with the
        MODEL release (not the observed-release diagnostic rows) must
        show storage_balancing's own held-out KGE (-0.38 / -0.14, the
        design memo's original split-sample finding for this rule),
        clearly different from ig2007_tiers's (+0.76 / +0.68, caveat 18)
        -- fails on the pre-fix code, which gives the ig2007_tiers values
        here regardless of the ``powell_release_mode`` argument."""
        from examples.irrigation_abm.analysis import hindcast_v3 as hv

        rows = hv.split_sample(powell_release_mode="storage_balancing")
        derived_model_rule = {
            row["case"]: row["result"] for row in rows
            if row["case"].startswith("derived on") and not row["result"].observed_release
        }
        assert set(derived_model_rule) == {"derived on 2003-2010", "derived on 2011-2018"}
        for row in rows:
            assert row["result"].powell_release_mode == "storage_balancing", row["case"]
        assert derived_model_rule["derived on 2003-2010"].metrics["mead_kge"] == pytest.approx(-0.38, abs=0.01)
        assert derived_model_rule["derived on 2011-2018"].metrics["mead_kge"] == pytest.approx(-0.14, abs=0.01)


# ===========================================================================
# 8. Hindcast: the 1 January tier equals the declared AOP tier, 2008-2019
# ===========================================================================

class TestHindcastTierMatchesDeclaredAOP:
    """USBR Annual Operating Plans (AOP), water years 2008-2019 (design
    memo section 1: pages cited there); "declared tier" = the tier the
    August 24-Month Study actually assigned. Model tier = this
    implementation's tier from the (real, observed) 1 January storages.
    Design memo section 4: "Right tier: 12 of 12 on 1 January"."""

    _DECLARED_TIER = {
        2008: "UEB", 2009: "UEB", 2010: "UEB", 2011: "UEB", 2012: "EQ",
        2013: "UEB", 2014: "MER", 2015: "UEB", 2016: "UEB", 2017: "UEB",
        2018: "UEB", 2019: "UEB",
    }

    @staticmethod
    def _hindcast_env(observed, profiles, requests):
        dead_pool = WaterSystemConfig().powell_dead_pool_maf
        from examples.irrigation_abm.analysis import hindcast_v3 as hv

        env = hv.HistoricalIrrigationEnvironment(
            WaterSystemConfig(
                hold_requests_fixed=True, sim_start_year=2000, sim_end_year=2018,
                mead_initial_elevation=observed[1999]["mead_elev_ft_eoy"],
                powell_initial_storage_maf=observed[1999]["powell_live_af_eoy"] / 1e6 + dead_pool,
            ),
            observed, requests,
        )
        env.initialize_from_profiles(profiles)
        return env

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_2008_to_2018_tier_matches_aop(self):
        """Years with a full observed request row (H&Y's data period ends
        2018): drives the real hindcast environment from 2000 ONCE (re-
        review 2026-09-29 round 4, LOW 9: a second, identical run for the
        2011 release check was redundant) and reads the logged
        ``powell_tier`` / ``powell_release_maf`` off each year's
        settlement."""
        from examples.irrigation_abm.analysis import hindcast_v3 as hv

        observed = hv.load_observed()
        profiles = hv.load_profiles()
        requests = hv.observed_requests(profiles, range(2000, 2019))
        env = self._hindcast_env(observed, profiles, requests)
        model_tier: dict = {}
        release_2011 = None
        for t in range(2000, 2019):
            env.advance_year()
            st = env.settle_year()
            if 2008 <= t <= 2018:
                model_tier[t] = st["powell_tier"]
            if t == 2011:
                release_2011 = st["powell_release_maf"]
        assert model_tier == {y: self._DECLARED_TIER[y] for y in range(2008, 2019)}
        # The design memo's headline 2011 equalization event: a release
        # well above the ordinary ~8.23 MAF band, from this SAME real run.
        assert release_2011 == pytest.approx(14.63, abs=0.1)

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_2019_tier_classification_matches_aop(self):
        """Water year 2019's tier is set from the 1 January 2019 (= end of
        2018) state; H&Y's own observed-request data ends in 2018 (spec
        item 3's hindcast window), so this calls the PRODUCTION
        ``_plan_powell_release_ig2007(year=2019, ...)`` directly on the
        end-of-2018 simulated storages (re-review 2026-09-29 round 4, LOW
        9: no longer a hand-reimplemented tier ladder) rather than driving
        a further ``advance_year()`` that would need a 2019 request row
        that does not exist -- the same "tier for 1 Jan (last+1) from the
        final simulated state" the design memo's own prototype reports.
        The non-tier inputs (nf/trib/shortage_volume/mexico/the two
        request totals) do not affect which TIER the production method
        picks -- only ``s_p``, ``s_m`` and ``year`` do -- so simple
        placeholder values are enough; only ``.tier`` is asserted."""
        from examples.irrigation_abm.analysis import hindcast_v3 as hv

        observed = hv.load_observed()
        profiles = hv.load_profiles()
        requests = hv.observed_requests(profiles, range(2000, 2019))
        env = self._hindcast_env(observed, profiles, requests)
        last_settlement = None
        for _ in range(2000, 2019):
            env.advance_year()
            last_settlement = env.settle_year()
        plan = env._plan_powell_release_ig2007(
            nf=12.0, s_p=last_settlement["powell_storage_end_maf"],
            s_m=last_settlement["mead_storage_end_maf"], trib=0.8, shortage_volume=0.0,
            mexico=1.5, ub_requested_maf=0.0, lb_requested_maf=2.6, year=2019,
            ub_requested_by_subbasin_maf={None: 0.0},
            ub_available_by_subbasin_maf={s: 5.0 for s in UB_SUBBASINS},
        )
        assert plan.tier == self._DECLARED_TIER[2019]
