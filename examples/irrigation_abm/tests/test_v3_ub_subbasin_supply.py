"""Irrigation case study v3, Work Package 1b (Upper Basin supply per
sub-basin, item 20).

Spec: .research/design_specs/irrigation_v3_spec_2026-09-28.md (WP1b) and
.research/design_specs/irrigation_v3_ub_subbasin_supply_2026-09-29.md (the
sub-basin memo: recommendation section 1, gauge/envelope table section 5,
formula section 6, methods sentences section 7, WP1 implementation notes
and this file's own test list section 10).

Most tests here fail on the pre-WP1b code (the WP1 commit, single Lees
Ferry pool): ``UB_SUBBASINS``, ``WaterSystemConfig.ub_supply_mode``, the
two committed sub-basin data tables, the ``ub_subbasin_supply`` gap
reason and ``irrigation_validators._sharing_sentence`` do not exist
there.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pytest

from examples.irrigation_abm.irrigation_env import (
    UB_SUBBASIN_ENVELOPE_PATH,
    UB_SUBBASIN_ENVELOPE_SHA256,
    UB_SUBBASIN_SUPPLY_PATH,
    UB_SUBBASIN_SUPPLY_SHA256,
    UB_SUBBASINS,
    IrrigationEnvironment,
    WaterSystemConfig,
    _load_ub_subbasin_envelope,
    _load_ub_subbasin_supply_table,
)
from examples.irrigation_abm.irrigation_personas import (
    IrrigationAgentProfile,
    create_profiles_from_data,
)
from examples.irrigation_abm.tools import build_v3_data
from examples.irrigation_abm.validators.irrigation_validators import (
    _sharing_sentence,
    supply_gap_block_increase,
)

CRSS_PARAMS_CSV = Path("ref/RL-ABM-CRSS/ALL_colorado_ABM_params_cal_1108.csv")
CRSS_DB_DIR = Path("ref/CRSS_DB/CRSS_DB")
_REAL_REF_AVAILABLE = CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir()

# The USBR workbook is a large external download, never committed (see
# build_v3_data.py's module docstring). Only test_recorded_use_feasible
# needs it directly (to check feasibility over the FULL 1971-2018 fit
# window; the committed ub_subbasin_supply_v3.csv only carries the 42
# simulation years, most of which lie outside that window) -- it is
# skipped, like the _REAL_REF_AVAILABLE-gated tests elsewhere in this
# suite, when no local copy can be found. LOW 7 (2026-09-29 re-review):
# no session-specific scratchpad path -- only a portable env var and the
# repo's own ref/ convention, so this test degrades to a clear skip on any
# machine (including the one that authored it) once that path is gone,
# instead of a silent pass that stops meaning anything.
_USBR_XLSX_CANDIDATES = [
    os.environ.get("WAGF_USBR_NATURALFLOW_XLSX", ""),
    "ref/NaturalFlows1906-2020_20221215.xlsx",
]


def _find_usbr_xlsx() -> Optional[Path]:
    for candidate in _USBR_XLSX_CANDIDATES:
        if not candidate:
            continue
        p = Path(candidate)
        if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == build_v3_data.SOURCE_XLSX_SHA256:
            return p
    return None


_USBR_XLSX = _find_usbr_xlsx()


# ===========================================================================
# Shared synthetic-settlement helpers (agents built directly, not through
# initialize_from_profiles -- see IrrigationEnvironment._settle's docstring
# for why an agent with no supply_group is a legitimate, unconstrained
# "pool" case, distinct from a real Upper Basin profile lacking one).
# ===========================================================================

def _agent(request: float, water_right: float = 2_000_000.0,
           supply_group: Optional[str] = None, basin: str = "upper_basin") -> Dict[str, Any]:
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
        "supply_group": supply_group,
        "ub_subbasin_member_count": None,
    }


def _snapshot(available_af: Dict[str, float], **overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "powell_storage": 15.0,
        "mead_storage": 12.0,
        "natural_flow": 12.0,
        "lb_shortage_volume_maf": 0.0,
        "mexico": 1.5,
        "lb_tributary": 0.8,
        "lb_request_projected_maf": 1.0,
        "powell_release_planned_maf": 8.0,
        "ub_subbasin_available_af": dict(available_af),
        "calendar_year": 2020,
    }
    base.update(overrides)
    return base


def _large_available_af(**overrides_af: float) -> Dict[str, float]:
    """Every sub-basin unconstrained (1e12 AF) except the named overrides
    -- isolates whichever sub-basin(s) a test cares about."""
    out = {s: 1.0e12 for s in UB_SUBBASINS}
    out.update(overrides_af)
    return out


# ===========================================================================
# 1. test_supply_tables_checksum
# ===========================================================================

class TestSupplyTablesChecksum:
    def test_supply_tables_checksum(self):
        supply_bytes = Path(UB_SUBBASIN_SUPPLY_PATH).read_bytes()
        envelope_bytes = Path(UB_SUBBASIN_ENVELOPE_PATH).read_bytes()
        assert hashlib.sha256(supply_bytes).hexdigest() == UB_SUBBASIN_SUPPLY_SHA256
        assert hashlib.sha256(envelope_bytes).hexdigest() == UB_SUBBASIN_ENVELOPE_SHA256
        # LF only, no CRLF (spec 1b.1: "whole AF, LF").
        assert b"\r" not in supply_bytes
        assert b"\r" not in envelope_bytes

        table = _load_ub_subbasin_supply_table()
        assert len(table) == 42
        assert set(table) == set(range(2019, 2061))
        for sim_year, row in table.items():
            for s in UB_SUBBASINS:
                assert row[f"q_{s}_af"] > 0
                assert row[f"a_{s}_af"] > 0

        envelope = _load_ub_subbasin_envelope()
        assert set(envelope) == set(UB_SUBBASINS)


# ===========================================================================
# 2. test_envelope_constants
# ===========================================================================

# Sub-basin memo section 5's table: c_s (binding year; runner-up c_s
# (runner-up year)).
_EXPECTED_ENVELOPE = {
    "WY": (0.30758, 1994, 2002, 0.30306),
    "UT1": (0.17771, 1994, 2013, 0.17497),
    "UT2": (0.00688, 2013, 2012, 0.00616),
    "UT3": (0.02148, 2007, 2012, 0.02113),
    "NM": (0.44127, 2018, 2002, 0.43882),
    "CO1": (0.22445, 2002, 2012, 0.22101),
    "CO2": (0.37015, 2002, 2012, 0.31834),
    "CO3": (0.42818, 2018, 2002, 0.41315),
    "AZ": (0.00070, 1977, 1981, 0.00051),
}


class TestEnvelopeConstants:
    def test_envelope_constants(self):
        envelope = _load_ub_subbasin_envelope()
        for s, (c_s, binding_year, runner_up_year, runner_up_c_s) in _EXPECTED_ENVELOPE.items():
            row = envelope[s]
            assert row["c_s"] == pytest.approx(c_s, abs=1e-5), s
            assert row["binding_year"] == binding_year, s
            assert row["runner_up_year"] == runner_up_year, s
            assert row["runner_up_c_s"] == pytest.approx(runner_up_c_s, abs=1e-5), s


# ===========================================================================
# 3. test_recorded_use_feasible
# ===========================================================================

def _skip_reason_recorded_use_feasible() -> str:
    missing = []
    if _USBR_XLSX is None:
        missing.append(
            "the USBR NaturalFlows1906-2020_20221215.xlsx workbook (checked "
            "$WAGF_USBR_NATURALFLOW_XLSX and ref/NaturalFlows1906-2020_20221215.xlsx)"
        )
    if not _REAL_REF_AVAILABLE:
        missing.append(f"{CRSS_DB_DIR} (H&Y's CRSS_DB data release)")
    return "not found locally: " + "; ".join(missing)


class TestRecordedUseFeasible:
    @pytest.mark.skipif(
        _USBR_XLSX is None or not _REAL_REF_AVAILABLE,
        reason=_skip_reason_recorded_use_feasible(),
    )
    def test_recorded_use_feasible(self):
        """c_s Q_s(y) >= D_s(y) for every sub-basin and every year
        1971-2018 (memo section 6 check: "every recorded year is
        feasible"), with equality (to floating-point tolerance) in the
        binding year c_s was fit to -- true by construction (c_s is the
        MAX of D_s(y)/Q_s(y) over the period), so this is a property test
        of build_v3_data.compute_ub_subbasin_envelope's own max-fit logic,
        not a re-derivation."""
        envelope, flow_by_gauge = build_v3_data.compute_ub_subbasin_envelope(_USBR_XLSX, CRSS_DB_DIR)
        depletion = build_v3_data._read_ub_historical_depletion(CRSS_DB_DIR)
        for s in UB_SUBBASINS:
            c_s = envelope[s]["c_s"]
            binding_year = envelope[s]["binding_year"]
            for y in range(
                build_v3_data.UB_SUBBASIN_FIT_START_YEAR,
                build_v3_data.UB_SUBBASIN_FIT_END_YEAR + 1,
            ):
                q_y = build_v3_data._subbasin_flow_af(flow_by_gauge, s, y)
                d_y = 1000.0 * float(depletion.loc[y, s])
                assert c_s * q_y >= d_y - 1e-6, (s, y, c_s * q_y, d_y)
                if y == binding_year:
                    assert c_s * q_y == pytest.approx(d_y, rel=1e-9), (s, y)


# ===========================================================================
# 4. test_pro_rata_within_independent_across (synthetic)
# ===========================================================================

class TestProRataWithinIndependentAcross:
    def test_pro_rata_within_independent_across(self):
        """Agent i in sub-basin s receives r_i x min(1, A_s / sum r_j)
        (memo section 6 step 5): shared BY REQUEST within a short
        sub-basin, and a shortage in one sub-basin does not touch another
        (sub-basins are independent, memo section 7's fourth ASSUMPTION)."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env._agents = {
            "WY_a": _agent(600_000.0, water_right=2_000_000.0, supply_group="WY"),
            "WY_b": _agent(400_000.0, water_right=2_000_000.0, supply_group="WY"),
            "NM_a": _agent(100_000.0, water_right=2_000_000.0, supply_group="NM"),
            "NM_b": _agent(100_000.0, water_right=2_000_000.0, supply_group="NM"),
        }
        # WY requests 1,000,000 AF combined against 500,000 AF available
        # (short); NM requests 200,000 AF combined against 1,000,000 AF
        # available (plenty) -- and every other sub-basin is effectively
        # unconstrained, so the basin-wide backstop never binds either.
        available_af = _large_available_af(WY=500_000.0, NM=1_000_000.0)
        st = env._settle(_snapshot(available_af, natural_flow=12.0))

        assert st["agents"]["WY_a"]["delivered"] == pytest.approx(300_000.0)
        assert st["agents"]["WY_b"]["delivered"] == pytest.approx(200_000.0)
        assert st["agents"]["WY_a"]["gap_reason"] == "ub_subbasin_supply"
        assert st["agents"]["WY_b"]["gap_reason"] == "ub_subbasin_supply"
        assert st["ub_subbasin"]["WY"]["ratio"] == pytest.approx(0.5)

        # Independent across sub-basins: NM is fully served despite WY's
        # shortage, and its own ratio is 1 (never touched by WY's cut).
        assert st["agents"]["NM_a"]["delivered"] == pytest.approx(100_000.0)
        assert st["agents"]["NM_b"]["delivered"] == pytest.approx(100_000.0)
        assert st["agents"]["NM_a"]["gap_reason"] == "none"
        assert st["ub_subbasin"]["NM"]["ratio"] == pytest.approx(1.0)


# ===========================================================================
# 5. test_2018_use_shortage_years
# ===========================================================================

# UB_historical_annual_depletion.csv, 2018 row (AF; memo section 5's own
# "2018 use" column x 1000).
_USE_2018_AF = {
    "WY": 345_100, "UT1": 686_400, "UT2": 11_400, "UT3": 79_200,
    "NM": 235_100, "CO1": 201_200, "CO2": 1_148_900, "CO3": 346_100, "AZ": 1_000,
}

# Memo section 6: "the short sub-basin-years are UT1 in 2020, 2021, 2023,
# 2025, 2032-2035, 2038, 2043, 2044, 2047, 2048, 2053 ...; WY and CO1 in
# 2047; UT3, CO2 and CO3 in 2033" (19 total).
_EXPECTED_SHORT_YEARS = {
    "WY": [2047],
    "UT1": [2020, 2021, 2023, 2025, 2032, 2033, 2034, 2035, 2038, 2043, 2044, 2047, 2048, 2053],
    "UT2": [],
    "UT3": [2033],
    "NM": [],
    "CO1": [2047],
    "CO2": [2033],
    "CO3": [2033],
    "AZ": [],
}


class TestUse2018ShortageYears:
    def test_2018_use_shortage_years(self):
        table = _load_ub_subbasin_supply_table()
        short: Dict[str, List[int]] = {s: [] for s in UB_SUBBASINS}
        for sim_year in sorted(table):
            row = table[sim_year]
            for s in UB_SUBBASINS:
                if row[f"a_{s}_af"] < _USE_2018_AF[s]:
                    short[s].append(sim_year)
        assert short == _EXPECTED_SHORT_YEARS
        assert sum(len(v) for v in short.values()) == 19


# ===========================================================================
# 6. test_checkpoints_2033_2047
# ===========================================================================

# Memo section 5's table, "A_s 2033 / 2047, kaf" column.
_A_2033_KAF = {"WY": 355.3, "UT1": 462.7, "UT2": 17.4, "UT3": 70.1, "NM": 239.8,
               "CO1": 215.1, "CO2": 1006.9, "CO3": 328.7, "AZ": 4.2}
_A_2047_KAF = {"WY": 234.4, "UT1": 344.7, "UT2": 12.9, "UT3": 86.5, "NM": 377.3,
               "CO1": 185.9, "CO2": 1173.6, "CO3": 466.1, "AZ": 4.3}


class TestCheckpoints20332047:
    def test_checkpoints_2033_2047(self):
        table = _load_ub_subbasin_supply_table()
        assert table[2033]["source_calendar_year"] == 2002
        assert table[2047]["source_calendar_year"] == 1934
        for s in UB_SUBBASINS:
            a_2033_kaf = table[2033][f"a_{s}_af"] / 1000.0
            a_2047_kaf = table[2047][f"a_{s}_af"] / 1000.0
            assert a_2033_kaf == pytest.approx(_A_2033_KAF[s], abs=0.05), s
            assert a_2047_kaf == pytest.approx(_A_2047_KAF[s], abs=0.05), s


# ===========================================================================
# 7. test_backstop_scales_and_closes (synthetic low NF) + mass balance
# ===========================================================================

class TestBackstopScalesAndCloses:
    def test_backstop_scales_and_closes(self):
        """Every sub-basin has ample supply of its OWN (ratio_s = 1 for
        both), but natural flow net of non-farm use is far below the
        combined 6 MAF request, so the basin-wide backstop (memo section 6
        step 6) must bind instead: every UB d_i scaled by the SAME factor,
        gap_reason becomes the backstop code (never ub_subbasin_supply)
        for every Upper Basin agent, and Powell's inflow still closes the
        NF_net = D_U + inflow_p identity."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env._agents = {
            "WY_a": _agent(3_000_000.0, water_right=5_000_000.0, supply_group="WY"),
            "NM_a": _agent(3_000_000.0, water_right=5_000_000.0, supply_group="NM"),
        }
        available_af = _large_available_af()  # every sub-basin unconstrained
        snap = _snapshot(available_af, natural_flow=2.0)
        st = env._settle(snap)

        cfg = env.config
        ub_non_farm = min(2.0, cfg.ub_non_farm_depletion_maf)
        nf_net = 2.0 - ub_non_farm
        bound_maf = min(cfg.ub_infrastructure_cap_maf, nf_net)
        assert nf_net < cfg.ub_infrastructure_cap_maf  # confirms which reason should fire
        assert st["ub_delivered_maf"] == pytest.approx(bound_maf)
        for aid in ("WY_a", "NM_a"):
            assert st["agents"][aid]["gap_reason"] == "ub_natural_flow"
        # Requested equally and each sub-basin's own ratio_s was 1, so the
        # basin-wide scale-down lands on both equally.
        assert st["agents"]["WY_a"]["delivered"] == pytest.approx(st["agents"]["NM_a"]["delivered"])
        total_delivered_maf = (st["agents"]["WY_a"]["delivered"] + st["agents"]["NM_a"]["delivered"]) / 1e6
        assert total_delivered_maf == pytest.approx(bound_maf, rel=1e-6)

        inflow_p = st["natural_flow_maf"] - st["ub_non_farm_maf"] - st["ub_delivered_maf"]
        assert inflow_p == pytest.approx(nf_net - bound_maf)

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    @pytest.mark.parametrize("ub_supply_mode", ["subbasin", "lees_ferry_pool"])
    def test_mass_balance_closure_v3(self, ub_supply_mode):
        """A short real-agent replay (5 years, 2018 requests fixed) closes
        the conservation identity in BOTH ub_supply_mode values -- the
        WP1 identity (dS_P + dS_M = NF - ub_non_farm + T - D_U - E_P - E_M
        - phi(r_LB + non_ag + X) - spill_M) does not change shape under
        WP1b, only how D_U itself is computed."""
        import numpy as np

        rng = np.random.default_rng(11)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        env = IrrigationEnvironment(WaterSystemConfig(seed=11, ub_supply_mode=ub_supply_mode))
        env.initialize_from_profiles(profiles)
        for _ in range(5):
            env.advance_year()
            st = env.settle_year()
            lhs = (st["powell_storage_end_maf"] - st["powell_storage_maf"]) + (
                st["mead_storage_end_maf"] - st["mead_storage_maf"])
            withdrawals = st["lb_delivered_maf"] + st["lb_non_ag_delivered_maf"] + st["mexico_delivered_maf"]
            rhs = (st["natural_flow_maf"] + st["lb_tributary_maf"] - st["ub_non_farm_maf"]
                   - st["ub_delivered_maf"] - st["powell_evap_maf"] - st["mead_evap_maf"]
                   - withdrawals - st["mead_spill_maf"])
            assert abs(lhs - rhs) < 1e-9
            for aid, rec in st["agents"].items():
                assert rec["delivered"] <= rec["request"] + 1e-6


# ===========================================================================
# 8. test_supply_rule_by_subbasin
# ===========================================================================

class TestSupplyRuleBySubbasin:
    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_supply_rule_by_subbasin(self):
        """At 2018 keep requests through sim year 2033 (loop year 15),
        UT1's own sub-basin is short (0.674 of its 2018 use, memo section
        6) and so is CO2's (0.876), so the supply rule blocks an increase
        in both, while NM (never short at 2018 use, memo section 6) is
        unaffected -- the supply rule's Upper Basin side is no longer idle
        (item 17's finding: under the single pool it never fires at 2018
        use). This is the memo's own "a CO2 increase blocked, an NM
        increase allowed" example, which needed WP3's FULL_SUPPLY_RATIO
        rule (any physical shortfall blocks); under the pre-WP3 0.70
        cutoff only UT1 crossed.
        """
        import numpy as np

        rng = np.random.default_rng(7)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        # WP2 review round 1 (HIGH 1): WaterSystemConfig.hold_requests_fixed
        # holds every agent's request at its 2018 use for the whole
        # replay. Without it, IrrigationEnvironment._reset_requests_to_base
        # (spec 2.1) runs unconditionally inside advance_year() and would
        # let a cut sub-basin's request decay below 2018 use after its
        # first short year (2020, per the memo) -- exactly the H&Y
        # `keep`-tracks-delivery semantics WP2 fixes, but not what THIS
        # test means by "2018 keep requests": every agent explicitly held
        # at its fixed 2018 use, every year, so 2033's comparison is
        # against the SAME 2018 request the memo's own numbers assume.
        env = IrrigationEnvironment(WaterSystemConfig(seed=7, hold_requests_fixed=True))
        env.initialize_from_profiles(profiles)

        ut1_agent = next(p.agent_id for p in profiles if p.precip_group == "UT1")
        nm_agent = next(p.agent_id for p in profiles if p.precip_group == "NM")

        # 2019 is loop year 1; 2033 is loop year 15. No DECISION is ever
        # applied, and hold_requests_fixed keeps every request at its
        # initial (2018 use) value throughout.
        for _ in range(15):
            env.advance_year()
            env.settle_year()
        assert env._current_year == 2033

        ut1_context = env.get_agent_context(ut1_agent)
        nm_context = env.get_agent_context(nm_agent)
        assert ut1_context["gap_reason"] == "ub_subbasin_supply"
        assert nm_context["gap_reason"] == "none"

        # WP3 (2026-09-29, spec 3.3): the v3 rule reads its inputs from
        # supply_rule_fields (as IrrigationLifecycleHooks.pre_year writes
        # them) and blocks below FULL_SUPPLY_RATIO -- so the memo's own
        # example now holds as written: CO2 (2033 ratio 0.876) is blocked
        # as well as UT1 (0.674), and NM is allowed.
        from examples.irrigation_abm.validators.irrigation_validators import (
            supply_rule_fields,
        )

        def rule_ctx(aid):
            ctx = env.get_agent_context(aid)
            return {**ctx, **supply_rule_fields(ctx, env.get_agent_state(aid))}

        co2_agent = next(p.agent_id for p in profiles if p.precip_group == "CO2")
        ut1_result = supply_gap_block_increase("increase_demand", [], rule_ctx(ut1_agent))
        co2_result = supply_gap_block_increase("increase_demand", [], rule_ctx(co2_agent))
        nm_result = supply_gap_block_increase("increase_demand", [], rule_ctx(nm_agent))
        assert ut1_result, "UT1 agent's increase should be blocked in 2033"
        assert co2_result, "CO2 agent's increase should be blocked in 2033"
        assert not nm_result, "NM agent's increase should be allowed in 2033"


# ===========================================================================
# 9. test_pool_mode_bitwise_unchanged
# ===========================================================================

class TestPoolModeBitwiseUnchanged:
    def test_pool_mode_bitwise_unchanged(self):
        """lees_ferry_pool mode ignores sub-basin structure entirely,
        reproducing WP1's single-pool formula bit for bit: two agents in
        DIFFERENT sub-basins (one of which is given a starvation-level
        availability that would cut it hard under subbasin mode) receive
        the exact SAME delivery ratio, driven only by the basin-wide
        NF_net / capacity bound, never by ub_subbasin_available_af."""
        cfg = WaterSystemConfig(seed=42, ub_supply_mode="lees_ferry_pool")
        env = IrrigationEnvironment(cfg)
        env._agents = {
            "UT1_agent": _agent(4_900_000.0, water_right=6_000_000.0, supply_group="UT1"),
            "NM_agent": _agent(2_000_000.0, water_right=3_000_000.0, supply_group="NM"),
        }
        # UT1 = 1 AF: would starve UT1_agent under subbasin mode; pool
        # mode must never even look at this dict.
        available_af = _large_available_af(UT1=1.0)
        st = env._settle(_snapshot(available_af, natural_flow=6.0))

        assert st["ub_subbasin"] is None  # no per-sub-basin record in pool mode
        r_ub = (4_900_000.0 + 2_000_000.0) / 1e6
        nf_net = 6.0 - min(6.0, cfg.ub_non_farm_depletion_maf)
        expected_ratio = min(r_ub, cfg.ub_infrastructure_cap_maf, nf_net) / r_ub
        assert expected_ratio < 0.999  # confirms this scenario is a real cut, not vacuous
        assert st["agents"]["UT1_agent"]["delivery_ratio"] == pytest.approx(expected_ratio)
        assert st["agents"]["NM_agent"]["delivery_ratio"] == pytest.approx(expected_ratio)
        assert st["agents"]["UT1_agent"]["gap_reason"] == st["agents"]["NM_agent"]["gap_reason"]
        assert st["agents"]["UT1_agent"]["gap_reason"] == "ub_natural_flow"
        for aid in ("UT1_agent", "NM_agent"):
            assert st["agents"][aid].get("ub_subbasin_ratio") is None

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_pool_mode_reproduces_wp1_regression_pin(self):
        """The heavier real-78-agent regression check: see
        test_v3_water_system.py
        (TestMassBalanceClosureV3.test_real_2018_fixed_demand_42_years_pool_mode),
        which pins ub_supply_mode="lees_ferry_pool" to the EXACT WP1
        tier_counts / Mead-minimum values. Re-asserted narrowly here (one
        year, tier only) as a fast cross-file guard that this file's own
        WaterSystemConfig(ub_supply_mode="lees_ferry_pool") wiring agrees
        with that file's."""
        import numpy as np

        rng = np.random.default_rng(7)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        env = IrrigationEnvironment(WaterSystemConfig(seed=7, ub_supply_mode="lees_ferry_pool"))
        env.initialize_from_profiles(profiles)
        env.advance_year()
        st = env.settle_year()
        assert st["ub_subbasin"] is None
        cfg = env.config
        r_ub = sum(
            min(a["request"], a["water_right"]) for a in env._agents.values()
            if a["basin"] == "upper_basin"
        ) / 1e6
        nf_net = st["natural_flow_maf"] - st["ub_non_farm_maf"]
        assert st["ub_delivered_maf"] == pytest.approx(min(r_ub, cfg.ub_infrastructure_cap_maf, nf_net))


# ===========================================================================
# 10. test_sharing_sentence_single_member (UT2)
# ===========================================================================

class TestSharingSentenceSingleMember:
    def test_sharing_sentence_single_member(self):
        # UT2 (the lone member of its sub-basin) short by its OWN supply:
        # no one else's request shares the shortfall.
        ut2_alone = {"basin": "upper_basin", "gap_reason": "ub_subbasin_supply",
                     "ub_subbasin_member_count": 1}
        assert _sharing_sentence(ut2_alone) == (
            "When water is short, a larger request would not add water."
        )

        # A normal (more than one member) sub-basin short by its own
        # supply: scoped to "your sub-basin".
        multi_member = {"basin": "upper_basin", "gap_reason": "ub_subbasin_supply",
                         "ub_subbasin_member_count": 5}
        sentence = _sharing_sentence(multi_member)
        assert "other users in your sub-basin" in sentence
        assert "not add water" in sentence  # still ends with the shared clause

        # UT2 under the BASIN-WIDE backstop (not its own sub-basin): it
        # really does share with the whole Upper Basin here, so the
        # "would not add water" short-circuit must NOT fire even though
        # it is still the lone member of its own sub-basin.
        ut2_backstop = {"basin": "upper_basin", "gap_reason": "ub_natural_flow",
                         "ub_subbasin_member_count": 1}
        # WP4 review, spec item 29c: "other users in <pool>".
        assert "other users in the Upper Basin" in _sharing_sentence(ut2_backstop)

        # lees_ferry_pool mode (or any context with no member count at
        # all): the whole Upper Basin, exactly as before WP1b.
        pool_mode = {"basin": "upper_basin", "gap_reason": "ub_natural_flow"}
        assert "other users in the Upper Basin" in _sharing_sentence(pool_mode)

        # Lower Basin is unaffected by any of this.
        lb_context = {"basin": "lower_basin", "gap_reason": "lb_mead_availability"}
        assert "other users in the Lower Basin" in _sharing_sentence(lb_context)


# ===========================================================================
# MEDIUM 2 / MEDIUM 3 (2026-09-29 re-review): synthetic_no_subbasin marker,
# mode-gated raise
# ===========================================================================

class TestSyntheticNoSubbasinMarker:
    def test_synthetic_marker_routes_to_unconstrained_pool(self):
        """MEDIUM 2: a profile explicitly marked synthetic_no_subbasin
        does not raise in subbasin mode, and lands in the unconstrained
        pool bucket (supply_group stays None), not inside a real
        sub-basin's cap."""
        profile = IrrigationAgentProfile(
            agent_id="MockAgent", basin="upper_basin", cluster="aggressive",
            water_right=1_000_000.0, synthetic_no_subbasin=True,
        )
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env.initialize_from_profiles([profile])  # must not raise
        assert env._agents["MockAgent"]["supply_group"] is None
        assert env._agents["MockAgent"]["ub_subbasin_member_count"] is None

        # It really is unconstrained: give it a huge request against a
        # starved real sub-basin's availability and confirm it is NOT cut
        # by any single sub-basin's cap (only the basin-wide backstop
        # could touch it, and natural_flow here is generous).
        env._agents["MockAgent"]["request"] = 900_000.0
        available_af = {s: 1.0 for s in UB_SUBBASINS}  # every REAL sub-basin starved
        st = env._settle(_snapshot(available_af, natural_flow=12.0))
        assert st["agents"]["MockAgent"]["delivered"] == pytest.approx(900_000.0)
        assert st["agents"]["MockAgent"]["gap_reason"] == "none"

    def test_real_profile_without_marker_still_raises(self):
        """The pre-existing case (a REAL profile that forgot to set
        precip_group) must still raise -- the marker is an explicit
        opt-in, never a blanket relaxation."""
        profile = IrrigationAgentProfile(
            agent_id="RealLookingAgent", basin="upper_basin", cluster="aggressive",
            water_right=1_000_000.0,
        )
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        with pytest.raises(ValueError, match="precip_group"):
            env.initialize_from_profiles([profile])

    def test_pool_mode_never_raises_regardless_of_marker(self):
        """MEDIUM 3: initialize_from_profiles only checks for a missing
        sub-basin in ub_supply_mode="subbasin" -- lees_ferry_pool mode
        never partitions by sub-basin, so a profile with neither a
        precip_group nor the synthetic marker still does not raise there."""
        profile = IrrigationAgentProfile(
            agent_id="RealLookingAgent", basin="upper_basin", cluster="aggressive",
            water_right=1_000_000.0,
        )
        env = IrrigationEnvironment(WaterSystemConfig(seed=42, ub_supply_mode="lees_ferry_pool"))
        env.initialize_from_profiles([profile])  # must not raise in pool mode
        assert env._agents["RealLookingAgent"]["supply_group"] is None


# ===========================================================================
# MEDIUM 4 (2026-09-29 re-review, spec 1b.6): CPU-sensitivity variants
# ===========================================================================

class TestSupplyVariants:
    def test_variant_validated_at_construction(self):
        WaterSystemConfig(seed=42, ub_subbasin_supply_variant="recommended")
        WaterSystemConfig(seed=42, ub_subbasin_supply_variant="rho_0_2")
        WaterSystemConfig(seed=42, ub_subbasin_supply_variant="lees_ferry_all")
        WaterSystemConfig(seed=42, ub_subbasin_supply_variant="tributary_gauges")
        with pytest.raises(ValueError, match="ub_subbasin_supply_variant"):
            WaterSystemConfig(seed=42, ub_subbasin_supply_variant="not_a_real_variant")

    def test_each_variant_table_loads_and_differs_from_recommended(self):
        """Each of the three CPU-sensitivity tables is a real, distinct,
        checksum-verified 42-row table -- not a copy of the recommended
        one under a different name."""
        from examples.irrigation_abm.irrigation_env import _load_ub_subbasin_supply_table

        recommended = _load_ub_subbasin_supply_table("recommended")
        for variant in ("rho_0_2", "lees_ferry_all", "tributary_gauges"):
            table = _load_ub_subbasin_supply_table(variant)
            assert len(table) == 42
            assert table != recommended, variant

    def test_env_uses_configured_variant(self):
        """IrrigationEnvironment actually reads
        config.ub_subbasin_supply_variant, not always "recommended"."""
        env_recommended = IrrigationEnvironment(
            WaterSystemConfig(seed=42, ub_subbasin_supply_variant="recommended")
        )
        env_rho02 = IrrigationEnvironment(
            WaterSystemConfig(seed=42, ub_subbasin_supply_variant="rho_0_2")
        )
        a_recommended = env_recommended._ub_subbasin_available_maf_for_year(2033)
        a_rho02 = env_rho02._ub_subbasin_available_maf_for_year(2033)
        assert a_rho02["WY"] == pytest.approx(a_recommended["WY"] * 1.2, rel=1e-6)

    def test_flow_share_uses_variant_own_mean_not_recommended(self):
        """LOW 1 (2026-09-29, third re-review): get_agent_context divided
        every variant's flow by the RECOMMENDED envelope's 1971-2018 mean,
        so the flow-share sentence was comparing two different physical
        quantities for a variant with a different gauge map. Proven under
        "lees_ferry_all", where every sub-basin shares the SAME single
        gauge: two agents in DIFFERENT sub-basins must get the IDENTICAL
        flow share (both numerator and the correct denominator are the
        same Lees Ferry series) -- before this fix they would have
        differed, since the recommended envelope's mean differs by
        sub-basin."""
        from examples.irrigation_abm.irrigation_env import (
            _load_ub_subbasin_supply_table,
            _load_ub_subbasin_variant_means,
        )

        env = IrrigationEnvironment(
            WaterSystemConfig(seed=42, ub_subbasin_supply_variant="lees_ferry_all")
        )
        env._agents = {
            "WY_agent": _agent(100_000.0, supply_group="WY"),
            "CO2_agent": _agent(100_000.0, supply_group="CO2"),
        }
        # _agent() defaults ub_subbasin_member_count to None (its hand-built
        # agents normally never reach _write_agent_deliveries); set it here
        # since this test calls advance_year(), which does.
        env._agents["WY_agent"]["ub_subbasin_member_count"] = 5
        env._agents["CO2_agent"]["ub_subbasin_member_count"] = 14
        env.advance_year()
        ctx_wy = env.get_agent_context("WY_agent")
        ctx_co2 = env.get_agent_context("CO2_agent")
        assert ctx_wy["ub_subbasin_flow_share"] is not None
        assert ctx_wy["ub_subbasin_flow_share"] == pytest.approx(ctx_co2["ub_subbasin_flow_share"])

        means = _load_ub_subbasin_variant_means()
        recommended_mean_wy = means["recommended"]["WY"]
        lees_ferry_all_mean_wy = means["lees_ferry_all"]["WY"]
        assert recommended_mean_wy != pytest.approx(lees_ferry_all_mean_wy)
        supply_row = _load_ub_subbasin_supply_table("lees_ferry_all")[env._current_year]
        q_wy = supply_row["q_WY_af"]
        expected_share = q_wy / lees_ferry_all_mean_wy
        assert ctx_wy["ub_subbasin_flow_share"] == pytest.approx(expected_share)
        # And NOT what the pre-fix bug (divide by the recommended
        # envelope's WY mean regardless of variant) would have given.
        buggy_share = q_wy / recommended_mean_wy
        assert ctx_wy["ub_subbasin_flow_share"] != pytest.approx(buggy_share)

    def test_rho_and_recommended_share_the_same_mean(self):
        """rho_0_2 reuses the recommended gauges (only c_s is scaled), so
        its mean must be identical to "recommended"'s, not a coincidence
        of the fit."""
        from examples.irrigation_abm.irrigation_env import _load_ub_subbasin_variant_means

        means = _load_ub_subbasin_variant_means()
        assert means["rho_0_2"] == means["recommended"]


# ===========================================================================
# MEDIUM 4 (2026-09-29 re-review): test_release_plan_uses_subbasin_projection
# ===========================================================================

class TestReleasePlanUsesSubbasinProjection:
    def test_release_plan_uses_subbasin_projection(self):
        """The Powell release plan's projected Upper Basin delivery
        (_ub_delivery_for_planning, called from _plan_powell_release) uses
        the SUB-BASIN breakdown in subbasin mode, not the plain aggregate
        -- a starved sub-basin lowers the projected delivery (and so
        raises the projected Powell inflow / the planned release) even
        when the basin-wide aggregate alone would not have been cut."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env._agents = {
            "WY_a": _agent(2_000_000.0, water_right=3_000_000.0, supply_group="WY"),
            "NM_a": _agent(2_000_000.0, water_right=3_000_000.0, supply_group="NM"),
        }
        # Aggregate request 4 MAF, comfortably under the 5.0 MAF capacity
        # and nf_net (nf=12 -> nf_net ~10.78): the AGGREGATE alone would
        # never cut Upper Basin planning delivery. But WY's own supply is
        # starved, so the per-sub-basin projection must still cut WY's
        # contribution and thus the total projected delivery.
        ub_by_subbasin = env._ub_request_projected_by_subbasin_maf()
        assert ub_by_subbasin["WY"] == pytest.approx(2.0)
        assert ub_by_subbasin["NM"] == pytest.approx(2.0)
        available_af = _large_available_af(WY=500_000.0)  # WY starved to 0.5 MAF
        planned_d_u = env._ub_delivery_for_planning(
            ub_requested_maf=4.0, nf_net=10.78,
            ub_requested_by_subbasin_maf=ub_by_subbasin,
            ub_available_by_subbasin_maf={s: v / 1e6 for s, v in available_af.items()},
        )
        # WY contributes only 0.5 (its own cap), NM its full 2.0 -> 2.5,
        # not the naive min(4.0, 5.0, 10.78) = 4.0 an aggregate-only
        # projection would have returned.
        assert planned_d_u == pytest.approx(2.5)
        assert planned_d_u < 4.0

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
    def test_release_plan_reflects_real_subbasin_shortfall(self):
        """End-to-end, WP1b re-review (LOW 2, 2026-09-29, third round): the
        stored plan (env._snapshot["powell_release_planned_maf"], as
        advance_year actually computes it every year of a real 78-agent
        fixed-2018-request replay) must always equal _plan_powell_release
        recomputed from the SAME frozen 1 January inputs WITH the
        per-sub-basin breakdown, and must differ, in at least one year,
        from the same recomputation WITHOUT it (the plain aggregate a
        planning step blind to sub-basins would have used).

        An earlier version of this test instead ran the SAME 15-year
        replay twice, once per ub_supply_mode, and compared the two runs'
        year-15 plans -- by year 15 the two runs' storages have already
        diverged (their actual deliveries differ from loop year 2 on,
        since UT1 is short at 2018 use starting sim year 2020, memo
        section 6), so ANY difference in the compared plan could come from
        the accumulated storage difference rather than from the planning
        formula itself; it did not isolate what it claimed to. Comparing
        two recomputations against the SAME stored plan, within one run,
        removes that confound."""
        rng = np.random.default_rng(7)
        profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=rng)
        env = IrrigationEnvironment(WaterSystemConfig(seed=7))  # ub_supply_mode="subbasin"
        env.initialize_from_profiles(profiles)

        found_divergence = False
        for _ in range(42):
            env.advance_year()
            snap = env._snapshot
            ub_by_subbasin = env._ub_request_projected_by_subbasin_maf()
            ub_aggregate_maf = sum(ub_by_subbasin.values())
            common_kwargs = dict(
                nf=snap["natural_flow"], s_p=snap["powell_storage"], s_m=snap["mead_storage"],
                trib=snap["lb_tributary"], shortage_volume=snap["lb_shortage_volume_maf"],
                mexico=snap["mexico"], ub_requested_maf=ub_aggregate_maf,
                lb_requested_maf=snap["lb_request_projected_maf"],
                year=env._current_year,
            )

            recomputed_with_subbasin = env._plan_powell_release(
                ub_requested_by_subbasin_maf=ub_by_subbasin,
                ub_available_by_subbasin_maf=env._ub_subbasin_available_maf_for_year(env._current_year),
                **common_kwargs,
            )
            assert recomputed_with_subbasin == pytest.approx(
                snap["powell_release_planned_maf"], abs=1e-9
            ), env._current_year

            # WITHOUT the sub-basin breakdown: force _ub_delivery_for_planning
            # down its aggregate-only (lees_ferry_pool) branch for this one
            # recomputation, restored immediately after.
            env.config.ub_supply_mode = "lees_ferry_pool"
            try:
                recomputed_aggregate_only = env._plan_powell_release(**common_kwargs)
            finally:
                env.config.ub_supply_mode = "subbasin"

            if recomputed_aggregate_only != pytest.approx(
                snap["powell_release_planned_maf"], abs=1e-9
            ):
                found_divergence = True

            env.settle_year()

        assert found_divergence, (
            "expected at least one year where the sub-basin projection "
            "changed the planned release from what an aggregate-only "
            "projection would have given"
        )
