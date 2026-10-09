"""Irrigation case study v3, Work Package 1c (Lower Basin priority split).

Spec: .research/design_specs/irrigation_v3_spec_2026-09-28.md, PI decision
22 (2026-09-29, "follow H&Y"), refining item 14. Rights memo:
.research/design_specs/irrigation_v3_lb_rights_check_2026-09-29.md.
Coupling reference: ref/RL-ABM-CRSS/ABM_CRSS_coupling.py
(Calculate_Annual_Div_QL_LB, multi_priority_agts).

Review round 2 (2026-09-29): MEDIUM 4 switched the split from a share of
each agent's water_right to the ABSOLUTE, PUBLISHED USBR entitlement
figures themselves (never derived from or scaled by water_right); MEDIUM 3
restored bit-for-bit identity between lb_priority_mode="senior_all" and
this repo's HEAD 38e5c34b; HIGH 1 / MEDIUM 2 fixed two agent-facing texts;
LOW 6 replaced several silent defaults with raises (with an explicit
synthetic-profile opt-out, mirroring synthetic_no_subbasin).

Every test here fails on the pre-WP1c code (HEAD 38e5c34b): there is no
``lb_priority_mode``, no ``lb_priority_split_v3.csv``, no
``lb_junior_tier_cut`` gap reason, and every Lower Basin agricultural
agent is delivered ``request * phi`` with no senior/junior split at all.
Several tests here ALSO fail on the WP1c round-1 code (share-of-water_right
split, epsilon phi threshold, multiply-then-divide delivery_ratio): see
each test's own docstring for which round it targets.
"""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

from examples.irrigation_abm.irrigation_env import (
    AZ_CAP_PRIORITY_4_ENTITLEMENT_AF,
    AZ_ON_RIVER_PRIORITY_4_ENTITLEMENT_AF,
    AZ_PRIORITY_4_TOTAL_AF,
    LB_PRIORITY_SPLIT_PATH,
    LB_PRIORITY_SPLIT_SHA256,
    UB_SUBBASINS,
    IrrigationEnvironment,
    WaterSystemConfig,
    _lb_junior_tier_fraction,
    _load_lb_priority_split_table,
)
from examples.irrigation_abm.irrigation_personas import (
    IrrigationAgentProfile,
    build_water_situation_text,
    describe_gap_reason,
)
from examples.irrigation_abm.validators.irrigation_validators import (
    supply_gap_block_increase,
)

# The six agents item 22 and the rights memo name as holding Arizona
# 4th/5th/6th-priority ("junior") water. Values below are the PUBLISHED
# USBR figures themselves (review round 2, MEDIUM 4) -- senior_af,
# junior_af -- NOT derived from water_right. See build_v3_data.py
# (_LB_PRIORITY_SOURCE_TABLE) for the full citation of each figure.
_FULLY_JUNIOR = {
    "CibolaValleyIDD": (0.0, 10_942.52),
    "HopiTribe": (0.0, 6_028.0),
    "NorthBajaLLC": (0.0, 480.0),
}
_PARTLY_JUNIOR = {
    "MohaveValleyIDD": (5_940.0, 35_060.0),
    "GilaMonsterFarms": (7_065.0, 2_091.0),
    "CocopahIndRes": (8_821.0, 2_026.0),
}
_SIX_JUNIOR_AGENTS = tuple(_FULLY_JUNIOR) + tuple(_PARTLY_JUNIOR)
# A representative senior-only agent (AZ-1 PPR, no Arizona 4th/5th/6th
# priority water at all) used throughout as the "everyone else" control.
_SENIOR_AGENT = "CRIR AZ"

_UB_SUBBASIN_PLACEHOLDER_MAF = {s: 5.0 for s in UB_SUBBASINS}

CRSS_PARAMS_CSV = Path("ref/RL-ABM-CRSS/ALL_colorado_ABM_params_cal_1108.csv")
CRSS_DB_DIR = Path("ref/CRSS_DB/CRSS_DB")
_REAL_REF_AVAILABLE = CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir()

# Review round 2 (MEDIUM 3): the exact commit this review requires
# lb_priority_mode="senior_all" to stay bit-identical to.
_HEAD_COMMIT = "38e5c34b"
# Re-review 2026-09-29 round 4 (LOW 7): the branch tip immediately before
# items 25-27 (LB non-ag 5.2, the 2007 Interim Guidelines Powell tiers)
# landed -- the exact commit the v3-DEFAULT ("split") settlement must stay
# bit-identical to when both new defaults are pinned back to what they
# were there (lb_non_ag_total_maf=5.0, powell_release_mode=
# "storage_balancing"; see TestSplitDefaultBitIdenticalTo58a1d0ea below).
_PRE_ITEMS_25_27_COMMIT = "58a1d0ea"


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


def _lb_env(requests_by_agent: dict, *, lb_priority_mode: str = "split", seed: int = 1) -> IrrigationEnvironment:
    """A bare environment with exactly the named Lower Basin agents (real
    agent ids, so ``_load_lb_priority_split_table`` covers all of them),
    each at its own request and its OWN real water right (so a request can
    legitimately reach the agent's full entitlement)."""
    env = IrrigationEnvironment(WaterSystemConfig(seed=seed, lb_priority_mode=lb_priority_mode))
    table = _load_lb_priority_split_table()
    for aid, request in requests_by_agent.items():
        wr = table[aid]["water_right_af"] if aid in table else 4_000_000.0
        env._agents[aid] = _agent("lower_basin", request, water_right=wr)
    return env


def _planned_snapshot(env: IrrigationEnvironment, snap: dict) -> dict:
    """Fill in ``powell_release_planned_maf`` / ``ub_subbasin_available_af``
    via the real planning method, matching test_v3_water_system.py's own
    ``_planned`` helper (duplicated here: this file is self-contained)."""
    cfg = env.config
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


def _ample_supply_snapshot(env: IrrigationEnvironment, tier: int) -> dict:
    """A snapshot with abundant Powell/Mead storage (phi == 1.0 exactly),
    so only the declared tier's junior cut -- never physical availability
    -- can bind. Requests are read straight off the environment's own
    agents, matching ``lb_request_projected_maf`` to what ``_settle`` will
    actually see (WP2's carried-request convention)."""
    v = env._tier_shortage_volume_maf(tier)
    lb_requested_maf = sum(a["request"] for a in env._agents.values()) / 1e6
    snap = {
        "powell_storage": 20.0, "mead_storage": 25.0, "natural_flow": 15.0,
        "lb_shortage_volume_maf": v, "lb_shortage_tier": tier, "mexico": 1.5,
        "lb_tributary": 0.8, "lb_request_projected_maf": lb_requested_maf,
    }
    return _planned_snapshot(env, snap)


def _real_profiles(seed: int = 7):
    rng = np.random.default_rng(seed)
    from examples.irrigation_abm.irrigation_personas import create_profiles_from_data
    return create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)


# ===========================================================================
# AZ priority-4 total and f_g (spec item 22, rule 3) -- unaffected by
# review round 2 (verified correct in round 1).
# ===========================================================================

class TestAzPriority4TotalAndTierFraction:
    def test_az_priority_4_total_and_components(self):
        """CAP 1,415,000 AF (Public Law 108-451, Arizona Water Settlements
        Act of 2004, Sec. 104(c)(1)(A), 118 Stat. 3490, read in full
        2026-09-29: "shall not exceed 1,415,000 acre-feet") + on-river
        164,652 AF (USBR "Water Priorities Within the State of Arizona",
        Fourth Priority (i), read in full 2026-09-29: "not to exceed
        164,652 acre-feet of diversions annually") = 1,579,652 AF."""
        assert AZ_CAP_PRIORITY_4_ENTITLEMENT_AF == 1_415_000.0
        assert AZ_ON_RIVER_PRIORITY_4_ENTITLEMENT_AF == 164_652.0
        assert AZ_PRIORITY_4_TOTAL_AF == pytest.approx(1_579_652.0)

    def test_f_g_per_tier(self):
        """f_g = AZ tier volume (320/400/480 kaf) / AZ priority-4 total.
        Tier 0 is exactly 0 (no declared shortage, nothing to cut)."""
        assert _lb_junior_tier_fraction(0) == 0.0
        assert _lb_junior_tier_fraction(1) == pytest.approx(320_000.0 / 1_579_652.0)
        assert _lb_junior_tier_fraction(2) == pytest.approx(400_000.0 / 1_579_652.0)
        assert _lb_junior_tier_fraction(3) == pytest.approx(480_000.0 / 1_579_652.0)
        assert _lb_junior_tier_fraction(1) == pytest.approx(0.202576, abs=1e-6)
        assert _lb_junior_tier_fraction(2) == pytest.approx(0.253220, abs=1e-6)
        assert _lb_junior_tier_fraction(3) == pytest.approx(0.303864, abs=1e-6)


# ===========================================================================
# Pinned data file (review round 2, MEDIUM 4: absolute published figures)
# ===========================================================================

class TestPinnedDataFile:
    def test_checksum_and_row_count(self):
        data = Path(LB_PRIORITY_SPLIT_PATH).read_bytes()
        assert hashlib.sha256(data).hexdigest() == LB_PRIORITY_SPLIT_SHA256
        lines = [ln for ln in data.decode("utf-8").splitlines() if not ln.startswith("#")]
        assert len(lines) == 23, "header + 22 Lower Basin agents"
        assert data.splitlines()[0].startswith(b"#")

    def test_sixteen_senior_only_agents_have_no_junior_entitlement(self):
        """MEDIUM 4: the 16 single-priority agents are not split at all --
        junior_entitlement_af is exactly 0 for every one of them (whatever
        their own published, or absent, senior figure is)."""
        table = _load_lb_priority_split_table()
        for aid, row in table.items():
            if aid not in _SIX_JUNIOR_AGENTS:
                assert row["junior_entitlement_af"] == pytest.approx(0.0, abs=1e-9), aid

    def test_two_agents_have_no_published_individual_total(self):
        """PVIDDiversionAG and Bard Unit share an undivided California
        Priority block with no individual USBR total -- senior_entitlement_af
        is None for them (never a fabricated number), and this is safe
        because junior_entitlement_af is 0 (no split ever reads it)."""
        table = _load_lb_priority_split_table()
        for aid in ("PVIDDiversionAG", "Bard Unit"):
            assert table[aid]["senior_entitlement_af"] is None, aid
            assert table[aid]["junior_entitlement_af"] == pytest.approx(0.0, abs=1e-9), aid

    def test_six_agents_match_published_entitlement_exactly(self):
        """MEDIUM 4: senior/junior are the ABSOLUTE published USBR figures
        (not a share of water_right_af) -- e.g. MohaveValleyIDD 5,940 AF
        Priority 1 (senior) + 35,060 AF Priority 4 (junior) = 41,000 AF
        published total, NOT its 50,000 AF water_right."""
        table = _load_lb_priority_split_table()
        for aid, (senior, junior) in {**_FULLY_JUNIOR, **_PARTLY_JUNIOR}.items():
            row = table[aid]
            assert row["senior_entitlement_af"] == pytest.approx(senior, abs=1e-6), aid
            assert row["junior_entitlement_af"] == pytest.approx(junior, abs=1e-6), aid
            # The published total need NOT equal water_right_af (MEDIUM 4's
            # whole point) -- assert they in fact DIFFER for at least the
            # partly-junior agents, so this test cannot pass by accident
            # if a future edit silently reverts to the share-of-W formula.
            if aid in _PARTLY_JUNIOR:
                assert (senior + junior) != pytest.approx(row["water_right_af"], abs=1.0), aid

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_table_agent_ids_equal_real_lb_profile_ids(self):
        """MEDIUM 4's equality check, exercised directly: every real
        create_profiles_from_data Lower Basin agent id is in the table,
        and the table has no extra id with no matching real profile."""
        profiles = _real_profiles()
        real_lb_ids = {p.agent_id for p in profiles if p.basin == "lower_basin"}
        table_ids = set(_load_lb_priority_split_table())
        assert table_ids == real_lb_ids

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_initialize_from_profiles_raises_for_unmarked_missing_agent(self):
        """LOW 6: a Lower Basin profile whose id is not one of the 22 and
        that does NOT set synthetic_no_priority_split must raise -- never
        silently treated as fully senior (which would understate a real,
        uncited entitlement gap)."""
        profiles = _real_profiles()
        bogus = IrrigationAgentProfile(
            agent_id="NotARealLBAgent", basin="lower_basin", cluster="aggressive",
            water_right=10_000.0,
        )
        env = IrrigationEnvironment(WaterSystemConfig(seed=1, lb_priority_mode="split"))
        with pytest.raises(ValueError, match="NotARealLBAgent"):
            env.initialize_from_profiles(profiles + [bogus])

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_initialize_from_profiles_routes_marked_synthetic_to_senior(self):
        """LOW 6: the SAME missing agent, but marked
        synthetic_no_priority_split=True (mirroring synthetic_no_subbasin
        on the Upper Basin side), does not raise, and _settle treats it as
        fully senior (no synthetic table row exists for it to split
        against)."""
        profiles = _real_profiles()
        mock = IrrigationAgentProfile(
            agent_id="MockLBAgent", basin="lower_basin", cluster="aggressive",
            water_right=10_000.0, synthetic_no_priority_split=True,
        )
        env = IrrigationEnvironment(WaterSystemConfig(seed=1, lb_priority_mode="split"))
        env.initialize_from_profiles(profiles + [mock])  # must not raise
        snap = _ample_supply_snapshot(env, tier=3)
        # Force the mock agent's request to its water right so a real bug
        # (accidentally splitting it) would be visible.
        env._agents["MockLBAgent"]["request"] = 10_000.0
        st = env._settle(dict(snap, lb_request_projected_maf=snap["lb_request_projected_maf"]))
        rec = st["agents"]["MockLBAgent"]
        assert rec["lb_junior_af"] == pytest.approx(0.0, abs=1e-6)
        assert rec["gap_reason"] == "none"

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_senior_all_mode_skips_the_table_check_entirely(self):
        """The equality/missing-agent checks are "split"-mode only --
        senior_all never reads the table, so an unrelated profile set
        never raises under it."""
        profiles = _real_profiles()
        bogus = IrrigationAgentProfile(
            agent_id="NotARealLBAgent", basin="lower_basin", cluster="aggressive",
            water_right=10_000.0,
        )
        env = IrrigationEnvironment(WaterSystemConfig(seed=1, lb_priority_mode="senior_all"))
        env.initialize_from_profiles(profiles + [bogus])  # must not raise


# ===========================================================================
# WaterSystemConfig.lb_priority_mode
# ===========================================================================

class TestLbPriorityModeConfig:
    def test_default_is_split(self):
        assert WaterSystemConfig().lb_priority_mode == "split"

    def test_senior_all_accepted(self):
        WaterSystemConfig(lb_priority_mode="senior_all")

    def test_invalid_value_rejected(self):
        with pytest.raises(ValueError, match="lb_priority_mode"):
            WaterSystemConfig(lb_priority_mode="bogus")


# ===========================================================================
# Split arithmetic (spec item 22, rule 1; review round 2 MEDIUM 4: against
# the PUBLISHED entitlement, not a share of water_right)
# ===========================================================================

class TestSplitArithmetic:
    def test_request_below_senior_entitlement_is_fully_senior(self):
        """MohaveValleyIDD (published senior 5,940 / junior 35,060 AF): a
        request below its senior entitlement is entirely senior, junior
        exactly 0, regardless of the declared tier."""
        env = _lb_env({"MohaveValleyIDD": 5_000.0})
        snap = _ample_supply_snapshot(env, tier=2)
        st = env._settle(snap)
        rec = st["agents"]["MohaveValleyIDD"]
        assert rec["lb_senior_af"] == pytest.approx(5_000.0)
        assert rec["lb_junior_af"] == pytest.approx(0.0, abs=1e-6)
        assert rec["lb_junior_cut_af"] == pytest.approx(0.0, abs=1e-6)
        assert rec["delivered"] == pytest.approx(5_000.0)  # phi == 1, no tier cut on 0 junior

    def test_request_between_senior_and_water_right_splits_by_published_figures(self):
        """A request of 20,000 AF (above the PUBLISHED 5,940 AF senior
        entitlement, within the 50,000 AF water right) splits 5,940
        senior + 14,060 junior; at Tier 2 (f_2), the junior part alone is
        cut. Fails on round 1's code (which would have capped senior at
        7,243.90, a share of water_right, not the published 5,940)."""
        env = _lb_env({"MohaveValleyIDD": 20_000.0})
        tier = 2
        f_2 = _lb_junior_tier_fraction(tier)
        snap = _ample_supply_snapshot(env, tier=tier)
        st = env._settle(snap)
        rec = st["agents"]["MohaveValleyIDD"]
        assert rec["lb_senior_af"] == pytest.approx(5_940.0)
        assert rec["lb_junior_af"] == pytest.approx(20_000.0 - 5_940.0)
        assert rec["lb_junior_cut_af"] == 0.0
        assert rec["delivered"] == 20_000.0
        assert rec["gap_reason"] == "none"  # item 46: below the entitlement ceiling

    def test_request_above_published_total_is_entirely_junior_beyond_it(self):
        """A request of 45,000 AF -- above the 41,000 AF PUBLISHED total
        (5,940 + 35,060) but within the 50,000 AF water right -- puts the
        extra 4,000 AF into the junior part too ("anything above the
        agent's total entitlement, which is treated as junior", rule 1):
        junior = 45,000 - 5,940 = 39,060 AF, NOT capped at the published
        35,060 AF junior figure."""
        env = _lb_env({"MohaveValleyIDD": 45_000.0})
        snap = _ample_supply_snapshot(env, tier=1)
        st = env._settle(snap)
        rec = st["agents"]["MohaveValleyIDD"]
        assert rec["lb_senior_af"] == pytest.approx(5_940.0)
        assert rec["lb_junior_af"] == pytest.approx(39_060.0)

    def test_fully_junior_agent_at_water_right(self):
        """HopiTribe (published senior 0 / junior 6,028 AF; water right
        5,900 AF, itself below the published junior figure): the ENTIRE
        request is junior, senior always exactly 0."""
        env = _lb_env({"HopiTribe": 5_900.0})
        snap = _ample_supply_snapshot(env, tier=3)
        st = env._settle(snap)
        rec = st["agents"]["HopiTribe"]
        assert rec["lb_senior_af"] == pytest.approx(0.0, abs=1e-9)
        assert rec["lb_junior_af"] == pytest.approx(5_900.0)

    def test_senior_only_agent_never_has_a_junior_part_even_above_published_figure(self):
        """CRIR AZ (AZ-1 PPR, published senior 662,402 AF; water right
        880,000 AF): a request of 750,000 AF -- ABOVE its published figure
        but within its water right -- is STILL 100% senior. This is the
        core MEDIUM 4 fix: the other 16 are never capped against their own
        published entitlement, only against water_right (already enforced
        upstream); fails on any code that applies min(request,
        senior_entitlement_af) uniformly to all 22."""
        env = _lb_env({_SENIOR_AGENT: 750_000.0})
        snap = _ample_supply_snapshot(env, tier=3)
        st = env._settle(snap)
        rec = st["agents"][_SENIOR_AGENT]
        assert rec["lb_senior_af"] == pytest.approx(750_000.0)
        assert rec["lb_junior_af"] == pytest.approx(0.0, abs=1e-6)
        assert rec["lb_junior_cut_af"] == pytest.approx(0.0, abs=1e-6)
        assert rec["gap_reason"] == "none"

    def test_senior_all_mode_never_splits_anyone(self):
        """In lb_priority_mode="senior_all", the six agents' own junior
        entitlement is ignored entirely -- even CibolaValleyIDD (100%
        junior in "split" mode) is fully senior here."""
        env = _lb_env({"CibolaValleyIDD": 43_236.2}, lb_priority_mode="senior_all")
        snap = _ample_supply_snapshot(env, tier=3)
        st = env._settle(snap)
        rec = st["agents"]["CibolaValleyIDD"]
        assert rec["lb_senior_af"] == pytest.approx(43_236.2)
        assert rec["lb_junior_af"] == pytest.approx(0.0, abs=1e-6)
        assert rec["delivered"] == pytest.approx(43_236.2)  # phi == 1, no split at all


# ===========================================================================
# Conservation of the declared volume V_g (spec item 22, rule 4)
# ===========================================================================

class TestConservationOfDeclaredVolume:
    @pytest.mark.parametrize("tier", [1, 2, 3])
    def test_non_ag_plus_junior_cuts_equals_v(self, tier):
        """non_ag's own reduction (N - non_ag) plus the junior cuts total
        must equal V exactly, in acre-feet as well as MAF."""
        env = _lb_env({
            "MohaveValleyIDD": 50_000.0, "CibolaValleyIDD": 43_236.2,
            "GilaMonsterFarms": 17_400.0, "CocopahIndRes": 12_726.0,
            "HopiTribe": 5_900.0, "NorthBajaLLC": 567.0,
            _SENIOR_AGENT: 880_000.0,
        })
        cfg = env.config
        v = env._tier_shortage_volume_maf(tier)
        snap = _ample_supply_snapshot(env, tier=tier)
        st = env._settle(snap)
        non_ag_reduction = cfg.lb_non_ag_total_maf - st["lb_non_ag_delivered_maf"]
        assert non_ag_reduction + st["lb_junior_cut_total_maf"] == pytest.approx(v, abs=1e-9)
        assert st["lb_shortage_volume_maf"] == pytest.approx(v)

    def test_zero_at_tier_zero(self):
        env = _lb_env({"HopiTribe": 5_900.0, _SENIOR_AGENT: 880_000.0})
        snap = _ample_supply_snapshot(env, tier=0)
        st = env._settle(snap)
        assert st["lb_junior_cut_total_maf"] == pytest.approx(0.0, abs=1e-12)
        assert st["lb_non_ag_delivered_maf"] == pytest.approx(env.config.lb_non_ag_total_maf)


# ===========================================================================
# Mass balance in both modes (spec item 22, rule 5)
# ===========================================================================

class TestMassBalanceBothModes:
    @pytest.mark.parametrize("mode", ["split", "senior_all"])
    @pytest.mark.parametrize("tier", [0, 1, 2, 3])
    def test_conservation_identity_holds(self, mode, tier):
        env = _lb_env({
            "MohaveValleyIDD": 50_000.0, "CibolaValleyIDD": 43_236.2,
            "GilaMonsterFarms": 17_400.0, "CocopahIndRes": 12_726.0,
            "HopiTribe": 5_900.0, "NorthBajaLLC": 567.0,
            _SENIOR_AGENT: 880_000.0,
        }, lb_priority_mode=mode)
        snap = _ample_supply_snapshot(env, tier=tier)
        st = env._settle(snap)
        withdrawals = st["lb_delivered_maf"] + st["lb_non_ag_delivered_maf"] + st["mexico_delivered_maf"]
        lhs = (st["powell_storage_end_maf"] - st["powell_storage_maf"]) + (
            st["mead_storage_end_maf"] - st["mead_storage_maf"])
        rhs = (st["natural_flow_maf"] + st["lb_tributary_maf"] - st["ub_non_farm_maf"]
               - st["ub_delivered_maf"] - st["powell_evap_maf"] - st["mead_evap_maf"]
               - withdrawals - st["mead_spill_maf"])
        assert abs(lhs - rhs) < 1e-9
        for rec in st["agents"].values():
            assert rec["delivered"] <= rec["request"] + 1e-6

    @pytest.mark.parametrize("tier", [1, 2, 3])
    def test_split_and_senior_all_give_the_same_aggregate_outflow_phi_1(self, tier):
        """item 22 redistributes an already-fixed total between the six
        junior agents and the non-agricultural bucket; it never changes
        the total itself, so lb_phys_ratio (phi) and both reservoirs'
        end-of-year storage are IDENTICAL between the two modes, given the
        SAME requests, when phi == 1 (ample supply)."""
        requests = {
            "MohaveValleyIDD": 50_000.0, "CibolaValleyIDD": 43_236.2,
            "GilaMonsterFarms": 17_400.0, "CocopahIndRes": 12_726.0,
            "HopiTribe": 5_900.0, "NorthBajaLLC": 567.0,
            _SENIOR_AGENT: 880_000.0,
        }
        results = {}
        for mode in ("split", "senior_all"):
            env = _lb_env(requests, lb_priority_mode=mode)
            snap = _ample_supply_snapshot(env, tier=tier)
            results[mode] = env._settle(snap)
        for key in (
            "lb_phys_ratio", "powell_storage_end_maf", "mead_storage_end_maf",
            "mead_evap_maf", "mead_spill_maf",
        ):
            assert results["split"][key] == pytest.approx(results["senior_all"][key], abs=1e-9), key

    @pytest.mark.parametrize("tier", [1, 2, 3])
    def test_split_and_senior_all_give_the_same_aggregate_outflow_phi_below_1(self, tier):
        """review round 2 (MEDIUM 3): the SAME aggregate-invariance proof,
        but under genuine PHYSICAL shortage (phi < 1 -- ample-supply alone,
        the round-1 test above, cannot show the outflow accounting itself
        is phi-independent). A low Mead/Powell storage forces phi well
        below 1 for both modes; item 22 must still leave phi, and both
        reservoirs' end-of-year storage, exactly aggregate-identical."""
        requests = {
            "MohaveValleyIDD": 50_000.0, "CibolaValleyIDD": 43_236.2,
            "GilaMonsterFarms": 17_400.0, "CocopahIndRes": 12_726.0,
            "HopiTribe": 5_900.0, "NorthBajaLLC": 567.0,
            _SENIOR_AGENT: 880_000.0,
        }
        results = {}
        for mode in ("split", "senior_all"):
            env = _lb_env(requests, lb_priority_mode=mode)
            v = env._tier_shortage_volume_maf(tier)
            lb_requested_maf = sum(a["request"] for a in env._agents.values()) / 1e6
            snap = {
                "powell_storage": 3.0, "mead_storage": 3.5, "natural_flow": 0.5,
                "lb_shortage_volume_maf": v, "lb_shortage_tier": tier, "mexico": 0.1,
                "lb_tributary": 0.05, "lb_request_projected_maf": lb_requested_maf,
            }
            results[mode] = env._settle(_planned_snapshot(env, snap))
        assert results["split"]["lb_phys_ratio"] < 1.0
        assert results["senior_all"]["lb_phys_ratio"] < 1.0
        for key in (
            "lb_phys_ratio", "powell_storage_end_maf", "mead_storage_end_maf",
            "mead_evap_maf", "mead_spill_maf",
        ):
            assert results["split"][key] == pytest.approx(results["senior_all"][key], abs=1e-9), key


# ===========================================================================
# Bit-identity of senior_all against HEAD 38e5c34b (review round 2, MEDIUM 3)
# ===========================================================================

def _load_head_irrigation_env(tmp_path: Path, commit: str = _HEAD_COMMIT):
    """Extract irrigation_env.py exactly as committed at ``commit``
    (default ``_HEAD_COMMIT``, 38e5c34b) and load it as an isolated module
    (registered in sys.modules first -- the @dataclass decorator needs
    cls.__module__ resolvable). __file__ is pointed at a sibling of the
    REAL irrigation_abm package so its own _DATA_DIR / *_PATH constants
    resolve to the real, checksum-matching committed CSVs (hydrology_v3.csv
    etc. have not changed since either commit this file uses)."""
    result = subprocess.run(
        ["git", "show", f"{commit}:examples/irrigation_abm/irrigation_env.py"],
        capture_output=True, text=True, check=True, cwd=Path(__file__).resolve().parents[3],
    )
    shadow_path = tmp_path / f"irrigation_env_{commit}.py"
    shadow_path.write_text(result.stdout, encoding="utf-8")
    module_name = f"irrigation_env_head_{commit}"
    spec = importlib.util.spec_from_file_location(module_name, shadow_path)
    head_mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = head_mod
    head_mod.__file__ = str(
        Path(__file__).resolve().parents[1] / "irrigation_env_HEAD_SHADOW_not_a_real_file.py"
    )
    spec.loader.exec_module(head_mod)
    if hasattr(head_mod, 'LB_PRIORITY_SPLIT_PATH'):
        # Item 46 adds a P5/P6 column; historical modules must read their
        # own pinned historical table, never the new schema/hash.
        table = subprocess.check_output(['git', 'show',
            f'{commit}:examples/irrigation_abm/data/lb_priority_split_v3.csv'],
            cwd=Path(__file__).resolve().parents[3])
        historical_csv = tmp_path / f'lb_priority_{commit}.csv'
        historical_csv.write_bytes(table)
        head_mod.LB_PRIORITY_SPLIT_PATH = historical_csv
    return head_mod


def _dump_replay(
    env_cls, cfg_cls, target: str, *, extra_cfg=None, seed=7, years=42,
    include_ub_subbasin=False,
):
    rng = np.random.default_rng(seed)
    from examples.irrigation_abm.irrigation_personas import create_profiles_from_data
    profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
    hold_fixed = target in ("2018", "0.99W")
    kwargs = dict(seed=seed, ub_supply_mode="subbasin", hold_requests_fixed=hold_fixed)
    if extra_cfg:
        kwargs.update(extra_cfg)
    env = env_cls(cfg_cls(**kwargs))
    env.initialize_from_profiles(profiles)
    if target == "0.99W":
        for a in env._agents.values():
            a["request"] = 0.99 * a["water_right"]
            a["diversion"] = a["request"]
    dump = []
    for _ in range(years):
        env.advance_year()
        st = env.settle_year()
        row = {k: v for k, v in st.items() if k not in ("agents", "ub_subbasin")}
        row["agents"] = {aid: dict(rec) for aid, rec in st["agents"].items()}
        if include_ub_subbasin:
            row["ub_subbasin"] = {
                subbasin: dict(rec) for subbasin, rec in st["ub_subbasin"].items()
            }
        dump.append(row)
    return dump


def _assert_dumps_bit_identical(dump_head, dump_new, label):
    """Compares EVERY settlement field HEAD's own record has (not only
    float-typed ones -- re-review 2026-09-29 round 4, LOW 7: the previous
    version's ``isinstance(rh[k], float)`` guard silently skipped any
    int/str/None field entirely, ``calendar_year`` among them) and EVERY
    per-agent field HEAD's own record has (not only the four hardcoded
    ``delivered`` / ``delivery_ratio`` / ``request`` / ``gap_reason``).
    Iterates HEAD's own keys, never NEW's, so a key the NEW side adds
    (``powell_tier`` / ``powell_tier_rule``, absent entirely from HEAD's
    pre-item-26/27 settlement dict; WP1c's per-agent junior-split fields,
    absent from a pre-WP1c HEAD) is correctly never expected to match
    something HEAD never had an opinion on -- exactly like a caller
    reading a dict with ``.get`` would."""
    assert len(dump_head) == len(dump_new)
    mismatches = []
    for yi, (rh, rn) in enumerate(zip(dump_head, dump_new), start=1):
        for k in rh:
            if k == "agents":
                continue
            if rh[k] != rn.get(k):
                mismatches.append(f"{label} year {yi} field {k}: HEAD={rh[k]!r} NEW={rn.get(k)!r}")
        for aid in rh["agents"]:
            for k in rh["agents"][aid]:
                if rh["agents"][aid][k] != rn["agents"][aid].get(k):
                    mismatches.append(
                        f"{label} year {yi} agent {aid} field {k}: "
                        f"HEAD={rh['agents'][aid][k]!r} NEW={rn['agents'][aid].get(k)!r}"
                    )
    assert not mismatches, "\n".join(mismatches[:20])


@pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
class TestSeniorAllBitIdenticalToHead:
    """MEDIUM 3: dumps lb_priority_mode="senior_all" against a LIVE git
    extraction of irrigation_env.py at HEAD 38e5c34b, every settlement
    field, every year, for replay A (2018 fixed demand), replay B (0.99W
    fixed demand), keep-every-year, and an in-year perturbation. Fails on
    round 1's code (epsilon phi threshold and multiply-then-divide
    delivery_ratio each move a bit relative to HEAD).

    Spec items 25/26/27 (2026-09-29, corrected re-review round 4, LOW 7 --
    the previous docstring here overclaimed this AS the "storage_balancing
    stays bit-identical to 58a1d0ea" check; it is not, precisely, because
    it compares against 38e5c34b under lb_priority_mode="senior_all", not
    58a1d0ea under the v3-DEFAULT "split" mode): HEAD 38e5c34b's
    WaterSystemConfig defaults are lb_non_ag_total_maf=5.0 and the
    storage-balancing Powell rule (the only one that existed then --
    powell_release_mode did not exist), UNCHANGED all the way to 58a1d0ea
    (WP1c and the item-24 safeguard, the commits between them, touch
    neither field). The v3 defaults moved to 5.2 and "ig2007_tiers", so
    the "NEW" side must pin BOTH back to the pre-items-25-27 values to
    keep isolating what this class actually tests (lb_priority_mode=
    "senior_all" alone). The EXACT, literal 58a1d0ea check, under the
    v3-default "split" mode this class does NOT exercise, is
    TestSplitDefaultBitIdenticalTo58a1d0ea below."""

    _OLD_DEFAULTS = {"lb_non_ag_total_maf": 5.0, "powell_release_mode": "storage_balancing"}

    def test_replay_a_2018_fixed_demand(self, tmp_path):
        head_mod = _load_head_irrigation_env(tmp_path)
        dump_head = _dump_replay(head_mod.IrrigationEnvironment, head_mod.WaterSystemConfig, "2018")
        dump_new = _dump_replay(IrrigationEnvironment, WaterSystemConfig, "2018",
                                 extra_cfg={"lb_priority_mode": "senior_all", **self._OLD_DEFAULTS})
        _assert_dumps_bit_identical(dump_head, dump_new, "replay-A")

    def test_replay_b_099w_fixed_demand(self, tmp_path):
        head_mod = _load_head_irrigation_env(tmp_path)
        dump_head = _dump_replay(head_mod.IrrigationEnvironment, head_mod.WaterSystemConfig, "0.99W")
        dump_new = _dump_replay(IrrigationEnvironment, WaterSystemConfig, "0.99W",
                                 extra_cfg={"lb_priority_mode": "senior_all", **self._OLD_DEFAULTS})
        _assert_dumps_bit_identical(dump_head, dump_new, "replay-B")

    def test_keep_every_year(self, tmp_path):
        head_mod = _load_head_irrigation_env(tmp_path)
        dump_head = _dump_replay(head_mod.IrrigationEnvironment, head_mod.WaterSystemConfig, "keep")
        dump_new = _dump_replay(IrrigationEnvironment, WaterSystemConfig, "keep",
                                 extra_cfg={"lb_priority_mode": "senior_all", **self._OLD_DEFAULTS})
        _assert_dumps_bit_identical(dump_head, dump_new, "keep-every-year")

    def test_in_year_perturbation(self, tmp_path):
        """A Lower Basin agent's request changes MID-YEAR (after
        advance_year's release plan, before settle_year) -- confirms the
        final settlement still matches bit for bit, not just an
        unperturbed replay."""
        head_mod = _load_head_irrigation_env(tmp_path)
        from examples.irrigation_abm.irrigation_personas import create_profiles_from_data

        rng_h = np.random.default_rng(11)
        env_h = head_mod.IrrigationEnvironment(
            head_mod.WaterSystemConfig(seed=11, ub_supply_mode="subbasin")
        )
        env_h.initialize_from_profiles(
            create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng_h)
        )
        rng_n = np.random.default_rng(11)
        env_n = IrrigationEnvironment(
            WaterSystemConfig(seed=11, ub_supply_mode="subbasin", lb_priority_mode="senior_all",
                               **self._OLD_DEFAULTS)
        )
        env_n.initialize_from_profiles(
            create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng_n)
        )
        mismatches = []
        for yi in range(1, 6):
            env_h.advance_year()
            env_n.advance_year()
            for env in (env_h, env_n):
                env._agents[_SENIOR_AGENT]["request"] = min(
                    env._agents[_SENIOR_AGENT]["request"] * 1.15,
                    env._agents[_SENIOR_AGENT]["water_right"],
                )
            st_h = env_h.settle_year()
            st_n = env_n.settle_year()
            for k in st_h:
                if k in ("agents", "ub_subbasin"):
                    continue
                if isinstance(st_h[k], float) and st_h[k] != st_n[k]:
                    mismatches.append(f"year {yi} field {k}: HEAD={st_h[k]!r} NEW={st_n[k]!r}")
            for aid in st_h["agents"]:
                for k in ("delivered", "delivery_ratio", "gap_reason"):
                    if st_h["agents"][aid][k] != st_n["agents"][aid][k]:
                        mismatches.append(f"year {yi} agent {aid} field {k}")
        assert not mismatches, "\n".join(mismatches[:20])


@pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
class TestCeilingDiffersFromLegacyRequestCut:
    """Item 46 deliberately changes split-mode replay and keep delivery.

    The senior_all historical identity tests above continue to require
    every field to match. Split now compares to the actual historical
    source/table and requires the documented agricultural change.
    """
    @pytest.mark.parametrize('target', ['2018', 'keep'])
    def test_entitlement_ceiling_changes_legacy_split_deliveries(self, tmp_path, target):
        head_mod = _load_head_irrigation_env(tmp_path, commit=_PRE_ITEMS_25_27_COMMIT)
        include_ub_subbasin = target == '2018'
        old = _dump_replay(
            head_mod.IrrigationEnvironment, head_mod.WaterSystemConfig, target,
            include_ub_subbasin=include_ub_subbasin,
        )
        new = _dump_replay(IrrigationEnvironment, WaterSystemConfig, target,
            extra_cfg={'lb_non_ag_total_maf': 5.0, 'powell_release_mode': 'storage_balancing'},
            include_ub_subbasin=include_ub_subbasin)
        assert len(old) == len(new) == 42
        assert any(o['agents']['HopiTribe']['delivered'] != n['agents']['HopiTribe']['delivered']
                   for o, n in zip(old, new))
        # Under held requests, V redistribution preserves the reservoir
        # trajectory even though the junior deliveries change. It also leaves
        # every historical field exactly unchanged for the 16 senior-only
        # Lower Basin agents and every Upper Basin agent.
        if target == '2018':
            assert [r['mead_storage_end_maf'] for r in new] == pytest.approx(
                [r['mead_storage_end_maf'] for r in old], abs=1e-9)
            profiles = _real_profiles(seed=7)
            senior_lb_ids = set(_load_lb_priority_split_table()) - set(_SIX_JUNIOR_AGENTS)
            upper_basin_ids = {p.agent_id for p in profiles if p.basin == 'upper_basin'}
            pinned_ids = senior_lb_ids | upper_basin_ids
            assert len(senior_lb_ids) == 16
            assert upper_basin_ids
            mismatches = []
            for yi, (old_year, new_year) in enumerate(zip(old, new), start=1):
                for field, old_value in old_year.items():
                    if field.startswith('ub_') and old_value != new_year.get(field):
                        mismatches.append(
                            f'year {yi} field {field}: '
                            f'legacy={old_value!r} ceiling={new_year.get(field)!r}'
                        )
                for aid in sorted(pinned_ids):
                    old_agent = old_year['agents'][aid]
                    new_agent = new_year['agents'][aid]
                    for field, old_value in old_agent.items():
                        new_value = new_agent.get(field)
                        if old_value != new_value:
                            mismatches.append(
                                f'year {yi} agent {aid} field {field}: '
                                f'legacy={old_value!r} ceiling={new_value!r}'
                            )
            assert not mismatches, '\n'.join(mismatches[:20])


class TestSplitMatchesSeniorAllAggregate:
    """Lighter-weight companions to TestSeniorAllBitIdenticalToHead: these
    do not need git or a fresh module load, only the two REGRESSION pins
    for the 2018-fixed-demand replay (already covered exactly in
    test_v3_water_system.py) restated here for locality, plus the
    keep-every-year DIVERGENCE this review round's request-feedback finding
    predicts."""

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_split_matches_senior_all_under_hold_requests_fixed(self):
        """Aggregate Tier counts and Mead minimum are IDENTICAL between
        "split" and "senior_all" under hold_requests_fixed=True (no
        request feedback across years). junior_cut_total_af is nonzero
        every declared-tier year for MohaveValleyIDD, CibolaValleyIDD,
        GilaMonsterFarms, HopiTribe, NorthBajaLLC (MEDIUM 4: GilaMonsterFarms'
        2018 use, 7,882 AF, now exceeds its PUBLISHED 7,065 AF senior
        entitlement, unlike round 1's larger, water_right-scaled one);
        CocopahIndRes never draws a junior cut in this replay (2018 use,
        550 AF, sits well inside its 8,821 AF senior entitlement).

        Spec items 25/26/27 (2026-09-29): the tier-count and Mead-minimum
        pins moved from {0: 21, 1: 11, 2: 7, 3: 3} / 7.4665 MAF to the
        values below, restating test_v3_water_system.py::
        TestMassBalanceClosureV3.test_real_2018_fixed_demand_42_years
        exactly (lb_non_ag_total_maf 5.0->5.2, powell_release_mode
        storage_balancing->ig2007_tiers); junior_cut_years moves from 21
        (11+7+3) to 32 (10+14+8), since a declared tier -- not the specific
        tier number -- is what triggers a junior cut every year for these
        five agents."""
        from examples.irrigation_abm.irrigation_personas import create_profiles_from_data

        def run(mode):
            rng = np.random.default_rng(7)
            profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
            env = IrrigationEnvironment(WaterSystemConfig(
                seed=7, ub_supply_mode="subbasin", hold_requests_fixed=True,
                lb_priority_mode=mode,
            ))
            env.initialize_from_profiles(profiles)
            tier_counts = {0: 0, 1: 0, 2: 0, 3: 0}
            mead_min_maf = None
            junior_cut_years = 0
            for _ in range(42):
                env.advance_year()
                tier_counts[env._compute_shortage_tier()] += 1
                mead_1jan = env._mead_storage[-1]
                if mead_min_maf is None or mead_1jan < mead_min_maf:
                    mead_min_maf = mead_1jan
                st = env.settle_year()
                if st["lb_junior_cut_total_maf"] > 1e-9:
                    junior_cut_years += 1
            return tier_counts, mead_min_maf, junior_cut_years

        split_tc, split_min, split_cut_years = run("split")
        senior_tc, senior_min, senior_cut_years = run("senior_all")
        # Item 36c (2026-10-05 design-basis audit + fix proposals, spec
        # item 36c): powell_post2026_equalization's default moved from
        # "hold_2026" to "extend_slope", which moves tier counts from
        # {0: 10, 1: 10, 2: 14, 3: 8} to the values below (Mead's own
        # minimum is unchanged -- the mass-balance invariant this test
        # is really about, split == senior_all under a held-fixed
        # replay, is unaffected either way).
        assert split_tc == senior_tc == {0: 7, 1: 11, 2: 16, 3: 8}
        assert split_min == pytest.approx(senior_min, abs=1e-9)
        assert split_min == pytest.approx(7.0652, abs=1e-3)
        assert senior_cut_years == 0
        assert split_cut_years == 35  # every declared-tier year (11 + 16 + 8)

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_keep_every_year_diverges_from_senior_all_with_feedback(self):
        """With request FEEDBACK (each year's "keep" tracks the agent's
        own prior delivery), split and senior_all legitimately diverge --
        the pinned numbers in test_v3_water_system.py::TestKeepEveryYear42Years
        (the v3-default "split" mode) are the authoritative regression for
        that mode; this test pins "senior_all" under the SAME scenario as
        its own independent number, standing in for the pre-item-22 (WP1c)
        behaviour.

        Spec items 25/26/27 (2026-09-29): moved from {0: 29, 1: 7, 2: 4,
        3: 2} / 7.4989 MAF (the pre-item-25/26/27 senior_all/HEAD pin,
        5.0 MAF non-ag bucket + storage_balancing) to {0: 16, 1: 11, 2: 9,
        3: 6} / 7.0652 MAF (5.2 MAF + ig2007_tiers, this file's own
        recipe) -- diverging from "split"'s then-pin of {0: 17, 1: 11,
        2: 8, 3: 6} / 7.1028 MAF exactly as the docstring above describes
        (split lowers the six junior agents' own subsequent requests
        further than senior_all does, once a tier actually cuts them).
        Item 36c (2026-10-05): the post2026 Equalization default move
        (hold_2026 -> extend_slope) moves this to the values below;
        Mead's own minimum is unchanged."""
        from examples.irrigation_abm.irrigation_personas import create_profiles_from_data

        rng = np.random.default_rng(7)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        env = IrrigationEnvironment(WaterSystemConfig(
            seed=7, ub_supply_mode="subbasin", hold_requests_fixed=False,
            lb_priority_mode="senior_all",
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
        assert tier_counts == {0: 13, 1: 16, 2: 8, 3: 5}
        assert mead_min_maf == pytest.approx(7.0652, abs=1e-3)


# ===========================================================================
# Replay with hold_requests_fixed=True at 2018 requests (real 78 agents)
# ===========================================================================

class TestHoldRequestsFixedReplay:
    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_2018_fixed_demand_replay_junior_short_years(self):
        """The v3-default ("split") replay at 2018 requests held fixed:
        Tier counts and Mead minimum are UNCHANGED from item 14 / senior_all
        (TestSplitMatchesSeniorAllAggregate above); the new information is
        the junior-agent short agent-years. Review round 2 (MEDIUM 4)
        moved this count from round 1's 84 to 105: GilaMonsterFarms now
        contributes 21 (its 2018 use, 7,882 AF, exceeds its published
        7,065 AF senior entitlement -- round 1's larger, water_right-scaled
        13,426.28 AF senior figure had hidden this). Dead pool is never
        reached in this replay, so "before dead pool" spans the full 42
        years.

        Spec items 25/26/27 (2026-09-29): tier counts and Mead minimum
        moved to {0: 10, 1: 10, 2: 14, 3: 8} / 7.0652 MAF, the SAME pin as
        TestSplitMatchesSeniorAllAggregate above (5.2 MAF non-ag bucket,
        item 25 + ig2007_tiers, item 26/27); dead pool is still never
        reached. junior_short_years_total moved from 105 to 160 (32 years
        each for the five agents a declared tier always cuts, since 32 was
        then the total declared-tier-year count, 10 + 14 + 8) -- the same
        move test_split_matches_senior_all_under_hold_requests_fixed's
        junior_cut_years made (21 -> 32), read per-agent here instead of
        aggregated.

        Item 36c (2026-10-05 design-basis audit + fix proposals, spec
        item 36c): the post2026 Equalization default move (hold_2026 ->
        extend_slope) moves tier counts to {0: 7, 1: 11, 2: 16, 3: 8}
        (Mead minimum unchanged, 7.0652 MAF) and junior_short_years_total
        to 175 (35 declared-tier years, 11 + 16 + 8, for each of the
        same five agents)."""
        from examples.irrigation_abm.irrigation_personas import create_profiles_from_data

        rng = np.random.default_rng(7)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        env = IrrigationEnvironment(WaterSystemConfig(
            seed=7, ub_supply_mode="subbasin", hold_requests_fixed=True,
        ))
        env.initialize_from_profiles(profiles)
        tier_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        mead_min_maf = None
        dead_pool_reached = False
        junior_short_years_total = 0
        junior_short_years_by_agent = {a: 0 for a in _SIX_JUNIOR_AGENTS}
        for _ in range(42):
            env.advance_year()
            tier_counts[env._compute_shortage_tier()] += 1
            mead_1jan = env._mead_storage[-1]
            if mead_min_maf is None or mead_1jan < mead_min_maf:
                mead_min_maf = mead_1jan
            st = env.settle_year()
            if (st["powell_storage_end_maf"] <= env.config.powell_dead_pool_maf + 1e-6
                    or st["mead_storage_end_maf"] <= env.config.mead_dead_pool_maf + 1e-6):
                dead_pool_reached = True
            for aid in _SIX_JUNIOR_AGENTS:
                if (st["agents"][aid].get("lb_junior_cut_af") or 0.0) > 1e-6:
                    junior_short_years_total += 1
                    junior_short_years_by_agent[aid] += 1

        assert tier_counts == {0: 7, 1: 11, 2: 16, 3: 8}
        assert mead_min_maf == pytest.approx(7.0652, abs=1e-3)
        assert not dead_pool_reached

        assert junior_short_years_total == 70  # item 46: only Hopi and Cibola bind
        assert junior_short_years_by_agent == {
            "MohaveValleyIDD": 0, "CibolaValleyIDD": 35, "GilaMonsterFarms": 0,
            "HopiTribe": 35, "NorthBajaLLC": 0, "CocopahIndRes": 0,
        }


# ===========================================================================
# Agent-facing text (spec item 22 rule 6; review round 2 HIGH 1 / MEDIUM 2)
# ===========================================================================

class TestAgentFacingText:
    @staticmethod
    def _ctx(aid, tier, request):
        from examples.irrigation_abm.irrigation_env import _lb_entitlement_ceiling
        row = _load_lb_priority_split_table()[aid]
        junior, total = (_lb_entitlement_ceiling(row, tier, 'zero')
                         if row['junior_entitlement_af'] > 0 else (None, None))
        delivered = min(request, total) if total is not None else request
        return dict(year=2030, basin='lower_basin', drought_index=.3, precipitation=0,
            lake_mead_level=1060., preceding_factor=1, water_right=1000000.,
            shortage_tier=tier, lb_shortage_volume_maf={1:.333,2:.417,3:.5}[tier],
            shortage_tier_threshold_ft={1:1075.,2:1050.,3:1025.}[tier],
            current_request=request, current_diversion=delivered, delivery_ratio=delivered/request,
            gap_reason='lb_junior_tier_cut' if delivered < request else 'none',
            lb_senior_entitlement_af=row['senior_entitlement_af'],
            lb_junior_entitlement_af=row['junior_entitlement_af'],
            lb_junior_request_af=max(0.,request-(row['senior_entitlement_af'] or request)),
            lb_junior_tier_cut_fraction=_lb_junior_tier_fraction(tier),
            lb_junior_ceiling_af=junior, lb_tier_ceiling_af=total,
            lb_p56_entitlement_af=row['p56_entitlement_af'],lb_p56_in_tier='zero')

    @pytest.mark.parametrize('aid', sorted(_SIX_JUNIOR_AGENTS))
    def test_junior_holders_read_sourced_ceiling_numbers(self, aid):
        ctx = self._ctx(aid,3,100000.)
        text = build_water_situation_text(ctx)
        assert f"about {ctx['lb_junior_ceiling_af']:,.0f} acre-ft" in text
        assert f"your {ctx['lb_tier_ceiling_af']:,.0f} acre-ft tier ceiling" in text
        assert 'at or below' in text
        assert ('Priority-5/6 water is not available' in text) == (ctx['lb_p56_entitlement_af']>0)
        assert 'cuts your junior-priority water by' not in text

    def test_request_within_senior_part_still_reads_junior_ceiling(self):
        ctx = self._ctx('GilaMonsterFarms',1,6000.)
        text = build_water_situation_text(ctx)
        assert 'you can expect full delivery' in text
        assert 'This tier limits your junior-priority water' in text

    def test_senior_agent_is_told_only_physical_shortage_cuts_it(self):
        text = build_water_situation_text(self._ctx('CRIR AZ',2,880000.))
        assert 'Your delivery is reduced only if Lake Mead cannot supply' in text
        assert 'your junior-priority' not in text

    @pytest.mark.parametrize('key', ['lb_junior_request_af','lb_junior_ceiling_af','lb_tier_ceiling_af','lb_senior_entitlement_af'])
    def test_missing_junior_context_keys_raise(self,key):
        ctx=self._ctx('HopiTribe',1,5900.)
        del ctx[key]
        with pytest.raises(ValueError,match=key):
            build_water_situation_text(ctx)


# ===========================================================================
# Supply rule: a junior agent blocked in a Tier-1 year, a senior agent not
# ===========================================================================

class TestSupplyRuleJuniorVsSenior:
    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_junior_and_senior_agents_both_blocked_by_phi(self):
        """HopiTribe (100% junior in BOTH round 1 and round 2 -- published
        senior entitlement 0 either way, so this scenario's numbers are
        UNCHANGED by MEDIUM 4) and CRIR AZ (senior-only) at their own keep
        requests, in a declared Tier 1 year with a modest PHYSICAL Mead
        shortage (phi ~= 0.872) on top. Before WP3 the supply rule's 70%
        cutoff blocked only HopiTribe (phi * (1 - f_1) ~= 0.695 < 0.70 <=
        phi); the v3 rule (WP3, spec 3.3) blocks both on phi and states
        HopiTribe's junior cut in its message. Storage levels found by
        direct search of this environment (recorded here, not re-derived
        by hand)."""
        f_1 = _lb_junior_tier_fraction(1)
        env = _lb_env({"HopiTribe": 5_900.0, _SENIOR_AGENT: 880_000.0})
        tier = 1
        v = env._tier_shortage_volume_maf(tier)
        snap = {
            "powell_storage": 3.75, "mead_storage": 6.0, "natural_flow": 0.3,
            "lb_shortage_volume_maf": v, "lb_shortage_tier": tier, "mexico": 0.1,
            "lb_tributary": 0.05,
            "lb_request_projected_maf": (5_900.0 + 880_000.0) / 1e6,
        }
        snap = _planned_snapshot(env, snap)
        st = env._settle(snap)
        phi = st["lb_phys_ratio"]
        assert 0.70 <= phi < 0.70 / (1 - f_1), "phi must sit strictly between the two thresholds"

        hopi = st["agents"]["HopiTribe"]
        crir = st["agents"][_SENIOR_AGENT]
        assert hopi["delivered"] / hopi["request"] < 0.70
        assert crir["delivered"] / crir["request"] >= 0.70

        assert hopi["gap_reason"] == "lb_junior_tier_cut+lb_mead_availability"
        assert crir["gap_reason"] == "lb_mead_availability"

        # WP3 (2026-09-29, spec 3.3, PI item 2): the supply rule no longer
        # has a 70% cutoff -- it blocks an increase whenever the PHYSICAL
        # share (Lake Mead's phi for the Lower Basin, the declared junior
        # cut taken out) is below FULL_SUPPLY_RATIO. phi ~= 0.872 here, so
        # BOTH agents are blocked; the junior cut changes the message, never
        # whether the rule fires (the junior-cut-alone exemption, phi = 1,
        # is test_v3_governance.py::test_supply_rule_ignores_declared_tier_
        # and_junior_cut).
        from examples.irrigation_abm.validators.irrigation_validators import (
            supply_rule_fields,
        )
        env._write_agent_deliveries(st)

        def ctx(aid):
            state = env.get_agent_state(aid)
            fields = supply_rule_fields(
                {"basin": "lower_basin", "current_request": state["request"],
                 "current_diversion": state["diversion"]}, state)
            return {"basin": "lower_basin", "gap_reason": state["gap_reason"],
                    "lb_junior_tier_cut_fraction": state["lb_junior_tier_cut_fraction"],
                    **{k: state[k] for k in ("lb_junior_ceiling_af", "lb_junior_entitlement_af", "lb_tier_ceiling_af")},
                    **fields}

        hopi_ctx, crir_ctx = ctx("HopiTribe"), ctx(_SENIOR_AGENT)
        assert hopi_ctx["supply_physical_ratio"] == crir_ctx["supply_physical_ratio"] == round(phi, 6)
        assert hopi_ctx["supply_ratio"] < crir_ctx["supply_ratio"]  # the junior cut on top
        hopi_msg = supply_gap_block_increase("increase_demand", [], hopi_ctx)[0].errors[0]
        crir_msg = supply_gap_block_increase("increase_demand", [], crir_ctx)[0].errors[0]
        assert "limits your junior-priority water" in hopi_msg
        assert "tier ceiling would add no deliverable water" in hopi_msg
        assert "junior-priority" not in crir_msg
