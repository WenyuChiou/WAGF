"""
Irrigation Environment: water system simulation for the Colorado River Basin.

Implements the TieredEnvironmentProtocol for the Hung & Yang (2021) RL-ABM
irrigation experiment.  Provides:

- Global water system state (total allocation, drought index)
- Basin-level state (Upper Basin precipitation, Lower Basin lake level)
- Agent-level water requests and deliveries
- Preceding factor computation (binary signal from water level changes)
- A two-reservoir annual water balance (Lake Powell, Lake Mead) that
  limits deliveries on the SUPPLY side: what an agent receives is what the
  reservoirs can physically deliver, shared pro-rata, never more.

Annual balance (MAF/yr; see ``IrrigationEnvironment._settle`` and
docs/irrigation_physics.md)::

    Powell:  S_P' = S_P + (NF - UB_non_farm - UB_delivered) - Evap_P - Release
    Mead:    S_M' = S_M + Release + LB_trib - Evap_M - LB_withdrawals - Spill_M

Upper Basin deliveries have PRIORITY: they are limited only by the 5.0 MAF
delivery capacity and by (non-farm-net) natural flow itself, never by what
Powell needs for its own release. Lake Powell releases R to keep its and
Lake Mead's end-of-year live-storage fractions as equal as possible
(a simplification of the 2007 Interim Guidelines' balancing tiers),
bounded to [7.0, 9.5] MAF. The declared Lower Basin shortage tier's volume
is borne entirely by the 5.0 MAF non-agricultural bucket, never by the 22
Lower Basin agricultural agents' own requests; those are scaled down only
when Mead cannot physically supply all Lower Basin withdrawals, pro-rata to
what is available above the dead pool. Hung and Yang (2021) take the
delivered diversion from CRSS in the same way: the basin total is limited
by the water system, not by a demand-side rule.

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
"""

from __future__ import annotations

import csv
import functools
import hashlib
import os
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# WP1b re-review (MEDIUM 4, spec 1b.6): the four ub_subbasin_supply_variant
# values WaterSystemConfig accepts -- referenced by its __post_init__.
_UB_SUBBASIN_SUPPLY_VARIANTS = (
    "recommended", "rho_0_2", "lees_ferry_all", "tributary_gauges",
)

# Minimum utilisation floor: agents cannot reduce demand below this fraction
# of their water right.  Prevents "economic hallucination" spiral to zero.
MIN_UTIL = 0.10

# CRSS 2019-2060 aggregate agricultural demand target for the 78 agents
# (5.86 MAF/yr; see initialize_synthetic's calibration note). Used only as
# the denominator of the logged basin_request_over_target ratio.
CRSS_DEMAND_TARGET_AF = 5_860_000.0


@dataclass
class WaterSystemConfig:
    """Colorado River Basin water system parameters."""

    # Compact allocations (acre-ft/year)
    upper_basin_allocation: float = 7_500_000
    lower_basin_allocation: float = 7_500_000
    mexico_allocation: float = 1_500_000

    # Simulation timeline
    sim_start_year: int = 2019
    sim_end_year: int = 2060
    hist_start_year: int = 1971
    hist_end_year: int = 2018

    # Climate scenario: resampling windows for "drier-than-normal"
    dry_resample_windows: List[Tuple[int, int]] = field(
        default_factory=lambda: [(1988, 2015), (1934, 1947)]
    )

    # Lake Mead thresholds (feet above sea level)
    # Reverted to v12 values: Stage 3 analysis showed shifting tiers down doubled
    # Tier 2 hard-block frequency (2.4%→4.8%) and collapsed Tier 1 warnings by 86%.
    mead_normal: float = 1100.0
    mead_shortage_tier1: float = 1075.0  # Tier 0→1 warning threshold
    mead_shortage_tier2: float = 1050.0  # Tier 1→2 hard-block threshold
    mead_shortage_tier3: float = 1025.0  # Tier 2→3 severe-block threshold

    # Lake Mead simplified mass balance coupling parameters
    # Storage(t+1) = Storage(t) + PowellRelease + LB_trib - LB_withdrawals - Evap
    mead_initial_elevation: float = 1081.46   # Dec 2018 observed (ft) -- VERIFIED
    # (USBR Lake Mead at Hoover Dam end-of-month elevation page,
    # https://www.usbr.gov/lc/region/g4000/hourly/mead-elv.html; cross-checked
    # against the USBR Feb 2019 24-Month Study,
    # https://www.usbr.gov/lc/region/g4000/24mo/2019/FEB19.pdf;
    # 2026-09-26 verification pass)
    evaporation_maf: float = 0.541            # Mead evaporation AT the reference storage (MAF/yr)
    # v3 (PI decision 5, 2026-09-28, supersedes the earlier 0.8 MAF at
    # 1,100 ft relation, S7): calibrated so that evaporation at the WY2018
    # Mead condition (mead_evap_ref_storage_maf below) equals the February
    # 2019 24-Month Study's reported WY2018 Mead evaporation, about
    # 541 thousand acre-ft (irrigation_v3_design_provenance_2026-09-28.md
    # row E11; .research/powell_constants_verification_2026-09-26.md).
    # See _mead_evaporation_maf.
    mead_evap_ref_storage_maf: float = 12.679  # WY2018 total storage (MAF): 10.132 (USBR 2009 curve
    # at 1,081.46 ft, available capacity above 895 ft) + 2.547 (dead
    # storage) -- both from the February 2019 24-Month Study (Dec 2018
    # observed elevation) and the USBR Lake Mead Area and Capacity Tables
    # (Tighi and Callejo, 2011) respectively. This IS the calibration
    # point: _mead_evaporation_maf(mead_evap_ref_storage_maf) == exactly
    # evaporation_maf.
    mexico_treaty_maf: float = 1.5            # Treaty delivery to Mexico (MAF/yr) -- VERIFIED (canonical)
    # (1944 US-Mexico Water Treaty, Treaty Series 994: canonical, uncontested
    # figure, restated throughout the 2007 ROD and the 24-Month Study
    # letters; not independently re-derived from a primary treaty PDF in
    # this pass, given how uncontested it is. 2026-09-26 verification pass)
    lb_non_ag_total_maf: float = 5.0           # LB non-ag: M&I + tribal + CAP + system losses (MAF/yr)
    # Calibrated aggregate, not a single quoted figure -- no primary document
    # names a "5.0 MAF" bucket. Partial USBR Feb 2019 24-Month Study
    # components (CAP 1.559 + Nevada 0.291 + MWD 0.886 = ~2.7 MAF) are
    # consistent with 5.0 MAF once tribal deliveries and lower-river system
    # losses are added, but this stays a modelling aggregate without a
    # single primary table (2026-09-26 verification pass).
    lb_tributary_maf: float = 1.0             # LB tributary inflow (MAF/yr) -- the "constant" fallback
    # Calibrated aggregate: a plausible order of magnitude for the ungauged
    # Lower Basin inflow between Powell and Mead (Virgin River, Muddy River,
    # ...), but no primary CRSS/USBR table was opened to pin this figure
    # down (2026-09-26 verification pass). v3 (spec 1.3, sign-off S1):
    # used only when lb_tributary_source == "constant"; the default reads
    # the hydrology table's own intervening-flow column instead (mean
    # 0.793 MAF over the mapped years) -- see _lb_tributary_for_year.
    lb_tributary_source: str = "usbr_intervening"  # "usbr_intervening" or "constant"
    ub_non_farm_depletion_maf: float = 1.2213  # UB non-farm consumptive use (MAF/yr), taken first
    # v3 (spec 1.2, L2 H2). USBR "Upper Colorado River Basin Consumptive
    # Uses and Losses 2016-2020" (Provisional, Feb 2022), Table UC-4, 2018:
    # Upper Basin total (excluding main-stem reservoir evaporation)
    # 4,300.6 kaf minus irrigation 3,079.3 kaf = 1,221.3 kaf (M&I, exports,
    # energy, stock-pond and livestock use). Subtracted from natural flow
    # before Upper Basin agriculture and Lake Powell in _settle; held
    # constant at the 2018 value every year and never curtailed (disclosed,
    # provenance row D6).
    # Re-review 2026-09-29 (LOW 7): the retired "natural_flow_base_maf"
    # field (the precipitation-to-flow proxy's coefficient, 12.0 MAF at the
    # post-2000 average precipitation, L2 H1) is removed outright rather
    # than kept as a dead placeholder -- natural flow is computed by
    # _natural_flow_for_year from the committed USBR hydrology table only,
    # never from this field, and the one other reader
    # (broker/tests/test_coupling_retrofit_pr9.py) tested its own
    # re-derivation of the retired formula, not any current code path (now
    # removed there too). A caller that still needs it gets a normal
    # AttributeError, not a silently-present, silently-unused constant.
    precip_baseline_mm: float = 100.0         # CRSS avg UB winter precip (mm); still used by the
    # synthetic (mock, no --real data) precipitation fallback and by
    # _compute_drought_index's legacy proxy -- NOT by natural flow (v3).
    # Powell release rule (PI decision 2026-09-28, replaces the pass-through-
    # with-target-fill rule, option e, 2026-09-26): a storage-BALANCING rule,
    # a simplification of the 2007 Interim Guidelines' balancing tiers (ROD
    # Section 6: "the Secretary shall determine the operation of Lake Powell
    # and Lake Mead ... to, to the extent practicable ... balance the
    # contents of Lake Powell and Lake Mead"). Each year Powell releases R
    # bounded to [min_powell_release_maf, max_powell_release_maf] and never
    # more than its own inflow plus usable storage (pass-through at dead
    # pool), chosen so the two reservoirs' end-of-year LIVE-storage
    # fractions (storage above dead pool / live capacity; Mead's live
    # capacity runs to the conservation-pool top, mead_conservation_pool_maf,
    # not mead_capacity_maf) are as equal as possible -- see _settle. The
    # four named tiers (equalization, Upper Elevation Balancing, Mid-
    # Elevation Release, Lower Elevation Balancing) collapse into this one
    # rule; the release band itself IS the Lower Elevation Balancing Tier's
    # own bound (ROD p. 52: "not more than 9.5 maf and not less than 7.0
    # maf"), re-verified 2026-09-26
    # (.research/powell_constants_verification_2026-09-26.md):
    #   * 7.0 MAF is also quotable as the FLOOR of that same tier, not the
    #     "minimum objective release" (that name belongs to a different,
    #     higher figure: 8.23 MAF/yr under the historical Upper Elevation
    #     Balancing Tier, 2007 Record of Decision, p.15,
    #     https://www.usbr.gov/lc/region/programs/strategies/RecordofDecision.pdf;
    #     also the INITIAL water year 2019 release volume -- the water year
    #     2019 release actually realised was 8.91 MAF). The Mid-Elevation
    #     Release Tier releases 7.48 MAF/yr below a Mead-elevation threshold
    #     in the Guidelines' own tier table (8.23 MAF above it).
    #   * 9.5 MAF is the Lower Elevation Balancing Tier's own ceiling (ROD
    #     p. 52, quoted above); the model's earlier 9.0 MAF ceiling (option
    #     d/e, 2026-09-26) was a narrower modelling choice, replaced here by
    #     the Guidelines' own number now that a balancing rule is in use.
    min_powell_release_maf: float = 7.0       # Powell release floor (MAF/yr)
    max_powell_release_maf: float = 9.5       # Powell release ceiling (MAF/yr); Lower Elevation
    # Balancing Tier bound (ROD p. 52), not a modelling choice.
    ub_infrastructure_cap_maf: float = 5.0   # UB infrastructure-limited ceiling (MAF/yr)
    # WP1b (item 20): "subbasin" (v3 default) gives each of the nine H&Y
    # Upper Basin sub-basins its own available water A_s(t) = c_s x
    # Q_s(m(t)) (see _load_ub_subbasin_supply_table / IrrigationEnvironment.
    # _settle), with agents in a sub-basin sharing any shortfall by request
    # (memo section 6). "lees_ferry_pool" is the WP1 single-pool behaviour
    # (min(5.0 MAF, NF - ub_non_farm_depletion_maf) shared pro-rata across
    # all 56 Upper Basin agents), kept for the SI. Either way,
    # ub_infrastructure_cap_maf and non-farm-net natural flow stay a
    # basin-wide BACKSTOP the recommended formula's own envelope never
    # binds (irrigation_v3_ub_subbasin_supply_2026-09-29.md section 5).
    ub_supply_mode: str = "subbasin"
    # WP1b re-review (MEDIUM 4, spec 1b.6, memo sections 8 and 11): which
    # per-sub-basin supply TABLE to load in "subbasin" mode -- the
    # recommended formula (default) or one of three CPU sensitivities,
    # each its own committed, checksum-pinned 42-row table built by
    # build_v3_data.py's ub_supply target: "rho_0_2" (the envelope with a
    # 20% margin, A_s = 1.2 c_s Q_s, H&Y's own rho), "lees_ferry_all" (the
    # basin-wide Lees Ferry gauge standing in for every sub-basin's own
    # flow), and "tributary_gauges" (a single upstream/headwater gauge per
    # sub-basin in place of the recommended downstream/confluence set --
    # this repo's own disclosed choice, memo section 11: "the WP1b author
    # lists them"). Ignored in "lees_ferry_pool" mode.
    ub_subbasin_supply_variant: str = "recommended"

    # WP2 review round 1, HIGH 1 (2026-09-29): a "held-fixed" replay (every
    # agent's request set once, at initialisation, to a target such as
    # 2018 use or 0.99 W, and never touched again -- the water-system-only
    # diagnostics of design record section 3 / spec 1.9's acceptance
    # replays) needs advance_year() to leave ``request`` alone.
    # _reset_requests_to_base (spec 2.1) runs UNCONDITIONALLY otherwise --
    # correct for every real run (LLM or FQL), where "the keep request
    # tracks last year's delivery" is the fix WP2 makes -- so a caller
    # that wants a genuinely fixed target must say so explicitly here.
    # Default False (every real run's actual behaviour, unaffected).
    # Diagnostic/replay use ONLY: no runner (run_experiment.py,
    # run_fql_baseline.py) ever sets this to True --
    # test_hold_requests_fixed_never_set_by_a_runner asserts it.
    hold_requests_fixed: bool = False
    # Lake Mead physical bounds (total storage, MAF), the end points of the
    # USBR storage-elevation curve loaded by IrrigationEnvironment from
    # data/mead_capacity_usbr2009_1ft.csv (v3, spec 1.4, L2 H4). Water
    # below the dead pool cannot be released; deliveries are limited to
    # storage above it plus the year's inflow.
    mead_dead_pool_maf: float = 2.547         # 895 ft (USBR Lake Mead Area and Capacity Tables,
    # Tighi and Callejo, 2011, p. 5: "Dead storage capacity (below the
    # lowest outlet structure at elevation 895.0 feet) is 2,547 KAF").
    # Replaces the earlier calibrated-aggregate 2.0 MAF.
    mead_capacity_maf: float = 30.167         # 1,229 ft: 27.620 MAF available above 895 ft (same
    # source, p. 1) plus the 2.547 MAF dead storage above. TOTAL storage at
    # the curve's true endpoint, INCLUDING the flood-control space above
    # the conservation pool (1,219.6-1,229 ft); the curve is interpolated
    # up to here so elevation stays defined for any storage this far.
    # Replaces the earlier 26.1 MAF (which used a different, non-physical
    # curve, L2 H4). Not the operational ceiling -- see
    # mead_conservation_pool_maf.
    mead_conservation_pool_maf: float = 28.647  # 2.547 dead storage + 26.1 MAF conservation
    # pool (about 1,219.6 ft on the USBR 2009 curve). Review 2026-09-28:
    # real operations do not fill the flood-control space above this
    # (1,219.6-1,229 ft, 26.1-27.620 MAF available); storage above it is
    # treated as spill (``_settle``'s ``mead_spill_maf``), not retained up
    # to mead_capacity_maf. Total versus live/operational storage: this
    # field and mead_dead_pool_maf are both TOTAL storage (the convention
    # every Mead quantity in this module uses); "26.1 MAF" in the name
    # refers to the live conservation-pool depth above the dead pool, per
    # the review's own wording.
    # The former +/-3.5 MAF annual storage-change clamp on Mead
    # ("mead_max_storage_delta_maf", a proxy for Glen Canyon buffering) is
    # RETIRED: Lake Powell storage below now does the buffering, and the
    # clamp broke mass conservation (water was created or destroyed
    # whenever it bound).

    # Lake Powell storage buffer (total storage, MAF): the release itself
    # is the storage-BALANCING rule described above min_powell_release_maf
    # (bounded to [7.0, 9.5] MAF, not [7.0, 9.0] and not a plain
    # pass-through -- PI decision 2026-09-28 superseded that); a
    # simplification of the four named 2007 Interim Guidelines tiers, not
    # the full operating rules. RE-VERIFIED 2026-09-26 against primary
    # USBR/USGS sources (.research/powell_constants_verification_2026-09-26.md).
    # powell_capacity_maf is VERIFIED outright; the RAW inputs behind
    # powell_initial_storage_maf (live storage) and powell_evaporation_maf
    # (WY2018 evaporation) are VERIFIED, but each stored field also folds in
    # a modelling step -- the dead-pool split, or a 0.55 storage-fraction
    # scale-up -- that is NOT itself independently confirmed;
    # powell_dead_pool_maf remains a calibrated aggregate with no single
    # primary table opened. Sources:
    #   * powell_capacity_maf: VERIFIED. Total storage at full pool
    #     (3,700 ft) in the 1986 area-capacity table USBR operations used
    #     through 2019. USGS (2022, "Lake Powell's storage capacity updated
    #     for first time since 1986,"
    #     https://www.usgs.gov/news/national-news-release/lake-powells-storage-capacity-updated-first-time-1986;
    #     full report, USGS SIR 2022-5017,
    #     https://pubs.usgs.gov/sir/2022/5017/sir20225017.pdf) gives
    #     25.160 MAF for 2018 and a 1.048 MAF loss since 1986, so
    #     1986 = 26.21 MAF.
    #   * powell_dead_pool_maf: a CALIBRATED AGGREGATE, not read off a single
    #     primary table. Storage below the 3,370 ft dead pool (river outlet
    #     works) is commonly reported as "roughly 2 million acre-feet"; the
    #     26.21 MAF total minus 24.322 MAF live capacity split that gives
    #     1.89 MAF is a widely repeated operational convention (secondary
    #     sources only), not a figure independently confirmed against the
    #     primary 1986 USBR area-capacity table (USBR RISE catalog item
    #     11372, https://data.usbr.gov/catalog/4575/item/11372, not opened).
    #     Order of magnitude (~1.9-2.0 MAF) is corroborated.
    #   * powell_initial_storage_maf: live storage (10.099 MAF) VERIFIED;
    #     the 11.99 MAF TOTAL stored here is contingent on the calibrated
    #     1.89 MAF dead-pool split above, not independently verified. Live
    #     storage at the end of December 2018 = 10,099 thousand acre-ft at
    #     3,581.85 ft (USBR Lower Colorado Region, February 2019 24-Month
    #     Study, Most Probable, Lake Powell table --
    #     https://www.usbr.gov/lc/region/g4000/24mo/2019/FEB19.pdf).
    #   * powell_evaporation_maf: the RAW water year 2018 input (386
    #     thousand acre-ft of Lake Powell evaporation) is VERIFIED against
    #     the same 24-Month Study, recorded when live storage averaged about
    #     12.5 MAF (14.4 MAF total, 0.55 of capacity). The stored 0.70 MAF
    #     full-pool figure (0.386 / 0.55) is the model's own scale-up, not
    #     itself quoted anywhere. Scaled by the storage fraction (a
    #     surface-area proxy), floored at evap_min_frac, the same shape as
    #     the Mead evaporation term.
    powell_capacity_maf: float = 26.21
    powell_dead_pool_maf: float = 1.89
    powell_initial_storage_maf: float = 11.99
    powell_evaporation_maf: float = 0.70
    evap_min_frac: float = 0.15               # on [0, 1]; same floor as Mead's evaporation term

    def __post_init__(self) -> None:
        if not 0.0 <= self.evap_min_frac <= 1.0:
            raise ValueError(f"evap_min_frac must be on [0, 1], got {self.evap_min_frac}")
        if not (0.0 <= self.powell_dead_pool_maf < self.powell_initial_storage_maf
                <= self.powell_capacity_maf):
            raise ValueError(
                "Powell storages must satisfy 0 <= dead pool < initial storage <= capacity, got "
                f"{self.powell_dead_pool_maf} / {self.powell_initial_storage_maf} / "
                f"{self.powell_capacity_maf}"
            )
        if not 0.0 < self.min_powell_release_maf <= self.max_powell_release_maf:
            raise ValueError("Powell release band must satisfy 0 < floor <= ceiling")
        if not 0.0 <= self.mead_dead_pool_maf < self.mead_capacity_maf:
            raise ValueError("Mead dead pool must be below capacity")
        if not self.mead_dead_pool_maf < self.mead_conservation_pool_maf <= self.mead_capacity_maf:
            raise ValueError(
                "Mead storages must satisfy dead pool < conservation pool <= "
                f"capacity, got {self.mead_dead_pool_maf} / "
                f"{self.mead_conservation_pool_maf} / {self.mead_capacity_maf}"
            )
        # Review 2026-09-28 (fix 12): the dead-pool config field and the
        # USBR table's dead storage must never drift apart -- a caller
        # changing one without the other would silently make the curve and
        # the mass balance disagree about what "empty" means.
        if abs(self.mead_dead_pool_maf - _MEAD_DEAD_STORAGE_AF / 1e6) > 1e-9:
            raise ValueError(
                f"mead_dead_pool_maf ({self.mead_dead_pool_maf}) must equal "
                f"the USBR table's dead storage ({_MEAD_DEAD_STORAGE_AF / 1e6} "
                "MAF, data/mead_capacity_usbr2009_1ft.csv); the config and "
                "the curve must stay in sync."
            )
        if self.lb_tributary_source not in ("usbr_intervening", "constant"):
            raise ValueError(
                "lb_tributary_source must be 'usbr_intervening' or 'constant', "
                f"got {self.lb_tributary_source!r}"
            )
        if self.ub_non_farm_depletion_maf < 0.0:
            raise ValueError(
                f"ub_non_farm_depletion_maf must be >= 0, got {self.ub_non_farm_depletion_maf}"
            )
        if self.mead_evap_ref_storage_maf <= 0.0:
            raise ValueError(
                f"mead_evap_ref_storage_maf must be > 0, got {self.mead_evap_ref_storage_maf}"
            )
        if self.ub_supply_mode not in ("subbasin", "lees_ferry_pool"):
            raise ValueError(
                "ub_supply_mode must be 'subbasin' or 'lees_ferry_pool', "
                f"got {self.ub_supply_mode!r}"
            )
        if self.ub_subbasin_supply_variant not in _UB_SUBBASIN_SUPPLY_VARIANTS:
            raise ValueError(
                "ub_subbasin_supply_variant must be one of "
                f"{_UB_SUBBASIN_SUPPLY_VARIANTS}, got "
                f"{self.ub_subbasin_supply_variant!r}"
            )
        if not isinstance(self.hold_requests_fixed, bool):
            raise ValueError(
                f"hold_requests_fixed must be a bool, got {self.hold_requests_fixed!r}"
            )

    # Number of Monte Carlo runs
    n_monte_carlo: int = 100

    # Random seed
    seed: int = 42


# ---------------------------------------------------------------------
# v3 water-system data files (spec 2026-09-28 WP1): committed, small,
# checksum-pinned at load. See examples/irrigation_abm/tools/build_v3_data.py
# for how each is generated and its full source provenance.
# ---------------------------------------------------------------------
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
HYDROLOGY_V3_PATH = os.path.join(_DATA_DIR, "hydrology_v3.csv")
MEAD_CAPACITY_PATH = os.path.join(_DATA_DIR, "mead_capacity_usbr2009_1ft.csv")
UB_SUBBASIN_SUPPLY_PATH = os.path.join(_DATA_DIR, "ub_subbasin_supply_v3.csv")
UB_SUBBASIN_ENVELOPE_PATH = os.path.join(_DATA_DIR, "ub_subbasin_envelope_v3.csv")
# WP1b re-review (MEDIUM 4, spec 1b.6): the three CPU-sensitivity variant
# supply tables (memo sections 8, 11); no separate envelope files (spec
# 1b.6 names only "the supply-table path", not an envelope one).
UB_SUBBASIN_SUPPLY_RHO02_PATH = os.path.join(_DATA_DIR, "ub_subbasin_supply_v3_rho02.csv")
UB_SUBBASIN_SUPPLY_LEES_FERRY_ALL_PATH = os.path.join(
    _DATA_DIR, "ub_subbasin_supply_v3_lees_ferry_all.csv"
)
UB_SUBBASIN_SUPPLY_TRIBUTARY_PATH = os.path.join(
    _DATA_DIR, "ub_subbasin_supply_v3_tributary.csv"
)
# WP1b re-review (LOW 1): each variant's own 1971-2018 mean flow.
UB_SUBBASIN_VARIANT_MEANS_PATH = os.path.join(_DATA_DIR, "ub_subbasin_variant_means_v3.csv")

# USBR Colorado River Basin natural flow data,
# NaturalFlows1906-2020_20221215.xlsx, sheet AnnualCYTotalNaturalFlow,
# columns "Colorado R At Lees Ferry, AZ" and "Colorado River Below Hoover
# Dam, AZ-NV" (retrieved 2026-09-28). 42 rows, sim_year 2019-2060 mapped to
# calendar years 1988-2015 / 1934-1947 (Hung and Yang 2021, p. 15 of 21).
HYDROLOGY_V3_SHA256 = "9951f2224334a859a7adbc9d55914e6505bbce38ea0424f26f10f7c8d51a04b5"
# USBR Lake Mead Area and Capacity Tables (Tighi and Callejo, 2011,
# 2001/2009 surveys; retrieved 2026-09-28). 335 rows, 1-ft steps, 895-1,229 ft.
MEAD_CAPACITY_SHA256 = "7f233bd8149cc9416612991c27ed130c22842e93bbbbdd121d7716d5f8d9c8d6"
# WP1b (item 20): Upper Basin supply per sub-basin. Built by
# examples/irrigation_abm/tools/build_v3_data.py (--target ub_supply) from
# the same USBR workbook and CRSS_DB/HistoricalData/
# UB_historical_annual_depletion.csv (H&Y 2021 p. 9); formula and gauge
# table in .research/design_specs/irrigation_v3_ub_subbasin_supply_2026-09-29.md
# sections 5-6. 42 rows (sim_year 2019-2060), q_{s}_af / a_{s}_af for each
# of the nine sub-basins.
UB_SUBBASIN_SUPPLY_SHA256 = "ac0a17639488e4d4e7e4cba6ae876ff4a7930a8e9012b5487e2a920189662d48"
# 9 rows: one per sub-basin -- its gauges, c_s (and its binding/runner-up
# year), and the 1971-2018 mean flow (the denominator of the agent-facing
# sub-basin flow-share sentence, memo section 9).
UB_SUBBASIN_ENVELOPE_SHA256 = "7f38c4dbfe5a57dc897ef9c2b7983c504fa71dd7ad86b82799a448848e618ca2"
# WP1b re-review (MEDIUM 4, spec 1b.6): the three CPU-sensitivity variant
# supply tables (memo sections 8, 11), same 42-row shape as the
# recommended table above, built by build_v3_data.py's ub_supply target.
UB_SUBBASIN_SUPPLY_RHO02_SHA256 = "0e65b6fa6d23e209b5c0c1425f73a2f51218fb2a59d6e7a803a7ee5d37a33048"
UB_SUBBASIN_SUPPLY_LEES_FERRY_ALL_SHA256 = "228099d21019e458241ea1ea216e3f46d33f6563c5a8e644960711db25029589"
UB_SUBBASIN_SUPPLY_TRIBUTARY_SHA256 = "f1b4b2379ba6091ac1667f734ab008d38fd4019320f0c1fdf203d127f954b394"
UB_SUBBASIN_VARIANT_MEANS_SHA256 = "c79ac70bad3db3f9fc22dec572740e0e29d74d67c3c7ac573ffbba86d693f288"

# The nine Hung and Yang (2021) Upper Basin sub-basins, in the same order
# irrigation_personas.py (_UB_STATE_GROUPS) and the two CSVs above use
# (AZ_UB there == AZ here -- see _UB_HIST_COLUMN_BY_GROUP).
UB_SUBBASINS: Tuple[str, ...] = ("WY", "UT1", "UT2", "UT3", "NM", "CO1", "CO2", "CO3", "AZ")

# WP1b re-review (MEDIUM 4): ub_subbasin_supply_variant -> (path, sha256).
_UB_SUBBASIN_SUPPLY_VARIANT_FILES: Dict[str, Tuple[str, str]] = {
    "recommended": (UB_SUBBASIN_SUPPLY_PATH, UB_SUBBASIN_SUPPLY_SHA256),
    "rho_0_2": (UB_SUBBASIN_SUPPLY_RHO02_PATH, UB_SUBBASIN_SUPPLY_RHO02_SHA256),
    "lees_ferry_all": (
        UB_SUBBASIN_SUPPLY_LEES_FERRY_ALL_PATH, UB_SUBBASIN_SUPPLY_LEES_FERRY_ALL_SHA256
    ),
    "tributary_gauges": (
        UB_SUBBASIN_SUPPLY_TRIBUTARY_PATH, UB_SUBBASIN_SUPPLY_TRIBUTARY_SHA256
    ),
}
# USBR Lake Mead Area and Capacity Tables, p. 5: "Dead storage capacity
# (below the lowest outlet structure at elevation 895.0 feet) is
# 2,547 KAF" -- the fixed physical constant the checked-in table's
# "available capacity above 895 ft" column is converted to TOTAL storage
# with. Independent of WaterSystemConfig.mead_dead_pool_maf (a config
# field a caller could in principle mis-set); the two are expected to
# agree, and review fix 12 (2026-09-28) made WaterSystemConfig.__post_init__
# ENFORCE that agreement (raises if mead_dead_pool_maf drifts from this
# constant by more than 1e-9 MAF) -- this constant itself stays a property
# of the data file, set here rather than read from the config, since it is
# never a runtime knob.
_MEAD_DEAD_STORAGE_AF = 2_547_000.0


def _sha256_checked_bytes(path: str, expected_sha256: str, label: str) -> bytes:
    """Read ``path`` and raise if its sha256 does not match
    ``expected_sha256`` -- a hand-edited, truncated, or stale data file
    must never silently feed a different water system into a run."""
    data = open(path, "rb").read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            f"{label} at {path} has sha256 {actual}, expected {expected_sha256}. "
            "Refusing to load a water-system data file that does not match "
            "the checksum this codebase (tests, docs, manifests) is pinned "
            "to. Regenerate it with "
            "examples/irrigation_abm/tools/build_v3_data.py if the change "
            "is intentional, and update the expected constant alongside it."
        )
    return data


@functools.lru_cache(maxsize=1)
def _load_hydrology_table() -> Dict[int, Dict[str, Any]]:
    """The committed 42-row USBR hydrology table (spec 1.1), keyed by
    simulation year (2019-2060). Cached process-wide: the file is
    immutable for the lifetime of one Python process, and every
    ``IrrigationEnvironment`` reads the same rows."""
    data = _sha256_checked_bytes(HYDROLOGY_V3_PATH, HYDROLOGY_V3_SHA256, "hydrology_v3.csv")
    reader = csv.DictReader(data.decode("utf-8").splitlines())
    table: Dict[int, Dict[str, Any]] = {}
    for row in reader:
        sim_year = int(row["sim_year"])
        table[sim_year] = {
            "source_calendar_year": int(row["source_calendar_year"]),
            "lees_ferry_cy_natural_flow_af": float(row["lees_ferry_cy_natural_flow_af"]),
            "lees_ferry_to_below_hoover_cy_intervening_af": float(
                row["lees_ferry_to_below_hoover_cy_intervening_af"]
            ),
        }
    if len(table) != 42:
        raise ValueError(
            f"{HYDROLOGY_V3_PATH} has {len(table)} rows after parsing, expected 42"
        )
    return table


@functools.lru_cache(maxsize=1)
def _load_mead_capacity_table() -> Tuple[np.ndarray, np.ndarray]:
    """The committed USBR 2009 Mead area-capacity table (spec 1.4), as
    ``(elevation_ft, storage_maf)``, both strictly ascending, ready for
    ``np.interp``. ``storage_maf`` is TOTAL storage (available capacity
    above 895 ft plus the 2.547 MAF dead storage below it), matching the
    convention the rest of this module uses (dead pool is a non-zero
    storage floor, never 0)."""
    data = _sha256_checked_bytes(
        MEAD_CAPACITY_PATH, MEAD_CAPACITY_SHA256, "mead_capacity_usbr2009_1ft.csv"
    )
    reader = csv.DictReader(data.decode("utf-8").splitlines())
    elevations: List[float] = []
    storages_af: List[float] = []
    for row in reader:
        elevations.append(float(row["elevation_ft"]))
        storages_af.append(float(row["available_capacity_above_895ft_af"]))
    if len(elevations) != 335:
        raise ValueError(
            f"{MEAD_CAPACITY_PATH} has {len(elevations)} rows after parsing, expected 335"
        )
    elevation_ft = np.array(elevations)
    storage_maf = (np.array(storages_af) + _MEAD_DEAD_STORAGE_AF) / 1e6
    if np.any(np.diff(elevation_ft) <= 0):
        raise ValueError(f"{MEAD_CAPACITY_PATH} elevation_ft is not strictly ascending")
    if np.any(np.diff(storage_maf) <= 0):
        raise ValueError(f"{MEAD_CAPACITY_PATH} storage is not strictly monotone")
    return elevation_ft, storage_maf


@functools.lru_cache(maxsize=1)
def _mead_area_proxy_table() -> Tuple[np.ndarray, np.ndarray]:
    """Surface-area PROXY at each grid elevation (review 2026-09-28, fix
    10): the local slope dStorage/dElevation (MAF per ft) of the USBR 2009
    curve, via central differences on its 1-ft grid. The table has no
    direct area column; for a smoothly-varying basin, incremental storage
    per unit elevation rise is proportional to surface area at that
    elevation, so a RATIO of this proxy at two elevations approximates the
    same ratio of true surface areas (the proportionality constant --
    whatever it is -- cancels). Used only by ``_mead_evaporation_maf``,
    always as a ratio, never as an absolute area."""
    elevation_ft, storage_maf = _load_mead_capacity_table()
    area = np.gradient(storage_maf, elevation_ft)
    return elevation_ft, area


@functools.lru_cache(maxsize=4)
def _load_ub_subbasin_supply_table(variant: str = "recommended") -> Dict[int, Dict[str, float]]:
    """The committed 42-row per-sub-basin Upper Basin supply table (WP1b,
    item 20), keyed by simulation year: ``source_calendar_year`` and, for
    each of the nine ``UB_SUBBASINS``, ``q_{s}_af`` (USBR calendar-year
    natural flow at the sub-basin's gauges) and ``a_{s}_af`` (= c_s x
    q_{s}_af, the sub-basin's available water). Cached process-wide (once
    per distinct ``variant``), same rationale as :func:`_load_hydrology_table`.

    ``variant`` (WP1b re-review, MEDIUM 4, spec 1b.6) selects one of the
    four tables in ``_UB_SUBBASIN_SUPPLY_VARIANT_FILES``: the recommended
    formula (default) or one of the three CPU sensitivities. Every caller
    should pass ``self.config.ub_subbasin_supply_variant`` explicitly
    rather than relying on the default, which exists only so this
    function's signature stays backward compatible."""
    if variant not in _UB_SUBBASIN_SUPPLY_VARIANT_FILES:
        raise ValueError(
            f"_load_ub_subbasin_supply_table: unknown variant {variant!r}, "
            f"expected one of {tuple(_UB_SUBBASIN_SUPPLY_VARIANT_FILES)}"
        )
    path, sha256 = _UB_SUBBASIN_SUPPLY_VARIANT_FILES[variant]
    data = _sha256_checked_bytes(
        path, sha256, f"ub_subbasin_supply_v3 (variant={variant})"
    )
    reader = csv.DictReader(data.decode("utf-8").splitlines())
    table: Dict[int, Dict[str, float]] = {}
    for row in reader:
        sim_year = int(row["sim_year"])
        entry: Dict[str, float] = {"source_calendar_year": int(row["source_calendar_year"])}
        for s in UB_SUBBASINS:
            entry[f"q_{s}_af"] = float(row[f"q_{s}_af"])
            entry[f"a_{s}_af"] = float(row[f"a_{s}_af"])
        table[sim_year] = entry
    if len(table) != 42:
        raise ValueError(
            f"{path} has {len(table)} rows after parsing, expected 42"
        )
    return table


@functools.lru_cache(maxsize=1)
def _load_ub_subbasin_envelope() -> Dict[str, Dict[str, Any]]:
    """The committed 9-row Upper Basin sub-basin envelope table (WP1b,
    item 20): gauges, c_s (and its binding/runner-up year), and the
    1971-2018 mean flow, keyed by sub-basin."""
    data = _sha256_checked_bytes(
        UB_SUBBASIN_ENVELOPE_PATH, UB_SUBBASIN_ENVELOPE_SHA256, "ub_subbasin_envelope_v3.csv"
    )
    reader = csv.DictReader(data.decode("utf-8").splitlines())
    table: Dict[str, Dict[str, Any]] = {}
    for row in reader:
        table[row["subbasin"]] = {
            "gauges": row["gauges"],
            "c_s": float(row["c_s"]),
            "binding_year": int(row["binding_year"]),
            "runner_up_year": int(row["runner_up_year"]),
            "runner_up_c_s": float(row["runner_up_c_s"]),
            "q_s_mean_1971_2018_af": float(row["q_s_mean_1971_2018_af"]),
        }
    missing = [s for s in UB_SUBBASINS if s not in table]
    if missing:
        raise ValueError(f"{UB_SUBBASIN_ENVELOPE_PATH} has no row(s) for {missing}")
    return table


@functools.lru_cache(maxsize=1)
def _load_ub_subbasin_variant_means() -> Dict[str, Dict[str, float]]:
    """WP1b re-review (LOW 1): each ``ub_subbasin_supply_variant`` value's
    own 1971-2018 mean flow per sub-basin -- ``UB_SUBBASIN_ENVELOPE_PATH``'s
    mean is fit to the RECOMMENDED gauge map only, so a variant with a
    DIFFERENT gauge map ("lees_ferry_all", "tributary_gauges") needs its
    own mean here, or the agent-facing sub-basin flow-share sentence
    (``get_agent_context``) divides that variant's flow by the wrong
    sub-basin's average flow entirely. "recommended" and "rho_0_2" share
    the recommended gauges (rho only scales c_s), so their rows are
    identical by construction, not a coincidence."""
    data = _sha256_checked_bytes(
        UB_SUBBASIN_VARIANT_MEANS_PATH, UB_SUBBASIN_VARIANT_MEANS_SHA256,
        "ub_subbasin_variant_means_v3.csv",
    )
    reader = csv.DictReader(data.decode("utf-8").splitlines())
    table: Dict[str, Dict[str, float]] = {}
    for row in reader:
        table[row["variant"]] = {s: float(row[f"q_{s}_mean_af"]) for s in UB_SUBBASINS}
    missing = [v for v in _UB_SUBBASIN_SUPPLY_VARIANTS if v not in table]
    if missing:
        raise ValueError(f"{UB_SUBBASIN_VARIANT_MEANS_PATH} has no row(s) for {missing}")
    return table


# Hung and Yang (2021) action model, used for synthetic (mock) agents that
# have no CRSS data: the medians of mu and sigma over the calibrated
# parameter file (ref/RL-ABM-CRSS/ALL_colorado_ABM_params_cal_1108.csv) and a
# step of water_right / 25. Fallback for mock runs only; real agents carry
# their own per-agent mu, sigma and bin size (create_profiles_from_data).
SYNTHETIC_HY_MU = 0.218
SYNTHETIC_HY_SIGMA = 0.923
SYNTHETIC_BIN_DIVISOR = 25

# Median of |N(0, 1)|: Phi^-1(0.75). A small step is a draw at or below the
# agent's median step (mu + 0.6745 sigma) x bin_size, a large step above it.
HALF_NORMAL_MEDIAN_Z = 0.6744897501960817

_SMALL_SKILLS = ("increase_small", "decrease_small")
_LARGE_SKILLS = ("increase_large", "decrease_large")


def resolve_step_bin_af(
    step_bin_af: Optional[float],
    bin_size_af: Optional[float],
    water_right: float,
) -> float:
    """ONE shared step-bin resolver (WP2 review round 1, LOW 8): the same
    precedence, used by ``execute_skill``, ``irrigation_personas.
    build_option_texts`` and ``irrigation_personas.build_simulation_log_row``,
    so the value drawn against, the value shown in the option text and the
    value logged can never silently disagree.

    Prefers ``step_bin_af`` (spec 2.3/2.4: the UB-converted, possibly
    rescaled bin ``create_profiles_from_data`` computes); falls back to
    the legacy ``bin_size_af`` for an older hand-built agent dict or
    profile that only ever set that; falls back to ``water_right / 25``
    (``SYNTHETIC_BIN_DIVISOR``) only when NEITHER real value is set -- a
    synthetic/mock profile with no calibrated Hung and Yang grid at all,
    the one case this is a deliberate, disclosed placeholder rather than
    missing data (see ``SYNTHETIC_BIN_DIVISOR``'s own definition)."""
    if step_bin_af and step_bin_af > 0:
        return float(step_bin_af)
    if bin_size_af and bin_size_af > 0:
        return float(bin_size_af)
    return float(water_right) / SYNTHETIC_BIN_DIVISOR


def hy_step_af(rng: np.random.Generator, mu: float, sigma: float,
               bin_size_af: float, size_class: str) -> float:
    """One action magnitude of the Hung and Yang (2021) model, in acre-ft.

    ``ref/RL-ABM-CRSS/ABM_CRSS_coupling.py (Q_learning)``:
    ``actions = (mu + abs(np.random.normal(0, sigma))) * bin_size``, with
    ``bin_size = agt_states[2] - agt_states[1]`` (the step of the agent's
    discretised diversion grid). |N(0, sigma)| is drawn by inverse CDF from
    one uniform u: |z| = sigma * Phi^-1((1 + q) / 2), a half-normal quantile
    at level q. ``size_class`` "small" restricts q to [0, 0.5), i.e. |z| at
    or below the half-normal median 0.6745 sigma; "large" to (0.5, 1), above
    it; anything else uses the whole distribution. So small and large are
    the lower and upper halves of the same H&Y distribution, and pooled
    50/50 they reproduce it exactly. One uniform per call keeps the
    per-(seed, year, agent, skill) stream deterministic.
    """
    from statistics import NormalDist

    u = float(rng.random())
    mu = max(0.0, float(mu))  # a negative mu would flip the step's direction
    if size_class == "small":
        q = 0.5 * u
    elif size_class == "large":
        q = 0.5 + 0.5 * max(u, 1e-12)
    else:
        q = u
    q = min(q, 1.0 - 1e-15)
    z = sigma * NormalDist().inv_cdf((1.0 + q) / 2.0) if sigma > 0 else 0.0
    return (mu + z) * bin_size_af


def hy_threshold_af(mu: float, sigma: float, bin_size_af: float) -> float:
    """T = (max(0, mu) + 0.6745 sigma) x bin_size: the median H&Y step
    (WP2 spec 2.5 -- the same ``max(0, mu)`` clamp ``hy_step_af`` applies
    to the draw itself, so the threshold a "small"/"large" draw is judged
    against, and the "typical step" shown to the agent, never disagree
    with the draw for a negative-mu agent)."""
    return (max(0.0, float(mu)) + HALF_NORMAL_MEDIAN_Z * sigma) * bin_size_af


def _set_realised_magnitude(
    state_changes: Dict[str, Any],
    action_context: Dict[str, Any],
    step_af: float,
    size_class: str,
    current: float,
    new_req: float,
) -> None:
    """Report the change actually applied (F07 follow-up, spec E9, H6).

    An increase is capped at the water right and a decrease at the 10
    percent floor, so the drawn step can overstate the change. The memory
    line ("(by N%)"), ``magnitude_pct_applied`` and ``magnitude_af`` carry
    the realised change; ``magnitude_pct_sampled`` is the drawn step as a
    percent of the current request; ``magnitude_class`` is small or large."""
    realised_af = abs(new_req - current)
    # From a zero request a percent is undefined: log None (the memory line
    # then omits "(by N%)") rather than a misleading 0.
    sampled_pct = (100.0 * step_af / current) if current > 0 else None
    realised = (100.0 * realised_af / current) if current > 0 else None
    state_changes["magnitude_pct_sampled"] = sampled_pct
    state_changes["magnitude_pct_applied"] = realised
    state_changes["magnitude_af"] = realised_af
    state_changes["magnitude_class"] = size_class
    action_context["magnitude_pct"] = realised


class IrrigationEnvironment:
    """Water system environment for irrigation ABM experiments.

    Annual two-reservoir balance at the resolution of Hung and Yang (2021),
    rewritten for the v3 water system (2026-09-28 spec, PI decisions
    2026-09-28/29): natural flow is the committed USBR hydrology table's
    value for the year (no clamp). Lake Powell releases R, planned once at
    the 1 January snapshot from PROJECTED end-of-year contents (before
    agents decide), to keep its and Lake Mead's end-of-year live-storage
    fractions (storage above dead pool / live capacity) as close as
    possible after that year's projected Lower Basin withdrawals -- a
    simplification of the 2007 Interim Guidelines' balancing tiers (ROD
    Section 6), bounded to the Guidelines' own Lower Elevation Balancing
    Tier band [7.0, 9.5] MAF and never more than physically available
    (pass-through at dead pool); excess above Powell's own capacity spills
    into the release. Lake Mead's withdrawals cannot exceed the water above
    its dead pool plus the year's inflow; the declared Lower Basin shortage
    tier's volume (2007 ROD Section 2.D.1) is borne entirely by the 5.0 MAF
    non-agricultural bucket, never by the 22 Lower Basin agricultural
    agents' own requests. Not the full operating rules: the four named
    2007 Interim Guidelines tiers (equalization, Upper Elevation
    Balancing, Mid-Elevation Release, Lower Elevation Balancing) collapse
    into this one balancing rule, and the Lake Mead protection levels are
    deliberately not modelled. See ``_settle`` for the full derivation and
    docs/irrigation_physics.md for the equations.

    Timing (one loop year, decisions at the start of the year)::

        advance_year()  commit last year's settlement (end storages become
                        this year's 1 January storages), draw precipitation,
                        declare the Lower Basin shortage tier from the
                        1 January Mead level, run a PROVISIONAL settlement at
                        the carried requests (what agents see as expected
                        delivery), freeze the 1 January snapshot.
        decisions       execute_skill -> update_agent_request
        settle_year()   FINAL settlement at this year's requests, rebuilt
                        from the frozen snapshot (idempotent); storage is
                        committed only by the next advance_year().

    Constraints: Powell release band [7.0, 9.5] MAF, UB delivery capacity
    5.0 MAF, natural flow uncapped (no clamp, v3), dead pools and full
    pools at both reservoirs. Evaporation scales with surface area
    (a storage-elevation-curve proxy); Mexico follows Minute 323 / the
    Binational Water Scarcity Contingency Plan.

    Usage::

        config = WaterSystemConfig()
        env = IrrigationEnvironment(config)

        # Initialise with historical data or synthetic
        env.initialize_synthetic(n_agents=31)

        # Each simulation year:
        env.advance_year()
        context = env.get_agent_context("MohaveValleyIDD")
        # → dict with water signals for LLM prompt injection
        # ... agents decide (execute_skill) ...
        env.settle_year()
    """

    # Lake Mead elevation-storage relationship: USBR 2009 area-capacity
    # table (Tighi and Callejo, 2011), 1-ft steps from 895 to 1,229 ft,
    # loaded and checksum-verified from data/mead_capacity_usbr2009_1ft.csv
    # (v3, spec 1.4, L2 H4; replaces the earlier 10-point curve, which did
    # not match this table and was non-physical between 1,000 and 1,050 ft).
    _ELEVATION_FT, _STORAGE_MAF = _load_mead_capacity_table()

    def __init__(
        self,
        config: Optional[WaterSystemConfig] = None,
        *,
        coupling_contract_active: bool = False,
    ):
        self.config = config or WaterSystemConfig()
        # ENV-LEVEL generator — MAIN THREAD ONLY.
        #
        # Everything that draws from this one runs on the main thread:
        # `initialize_synthetic`'s cluster shuffle (setup) and
        # `_generate_precipitation`'s noise (called from `advance_year`,
        # once per year, before any agent decides).  The per-agent DECISION
        # phase must NOT touch it — `ExperimentRunner._run_agents_parallel`
        # runs that phase in a ThreadPoolExecutor under `--workers N`, and a
        # shared stream there hands out draws in thread-completion order.
        # Decision-phase draws go through `_decision_rng()` instead.
        self.rng = np.random.default_rng(self.config.seed)

        # PR-9 coupling-retrofit (F1): default OFF so every existing caller
        # (positional `IrrigationEnvironment(config)`) is byte-identical.
        # See examples/irrigation_abm/irrigation_coupling.py for what the
        # guard checks and why it is not a plain EnvironmentCouplingAdapter
        # wrap. Import is local to __init__ (not module-level) so a
        # flag-OFF run never even imports broker.coupling.
        self._coupling_contract_active = bool(coupling_contract_active)
        self._irrigation_contract = None
        # Review P2: "the flag was on" is an INTENT; "the guard ran N times"
        # is the EVIDENCE. A run whose flag is true but whose guard never
        # fired (a runner that builds the env but never reads a context, an
        # agent set that is empty) looks in the manifest exactly like a run
        # the guard protected end to end, unless the count is recorded too.
        self._coupling_guard_calls = 0
        if self._coupling_contract_active:
            from examples.irrigation_abm.irrigation_coupling import (
                build_irrigation_agent_context_contract,
            )
            self._irrigation_contract = build_irrigation_agent_context_contract()

        # Timeline
        # F12 follow-up (2026-09-25 code review): pre-loop _current_year must
        # NOT equal loop year 1's value (sim_start_year, 2019), or the first
        # advance_year() call re-keys nothing and _decision_rng repeats its
        # draw (a real regression the review caught in
        # tests/test_irrigation_execute_skill_thread_safety.py). sim_start_year
        # - 1 (2018) is also the semantically right pre-loop label: initial
        # conditions (Mead's Dec-2018 observed elevation, 2018 diversions)
        # are dated 2018, one year before loop year 1 begins. This value is
        # always overwritten by the first advance_year() call before any
        # hook or validator reads it, so no production output depends on it.
        self._current_year: int = self.config.sim_start_year - 1
        self._year_index: int = 0

        # Global state
        self._global: Dict[str, Any] = {
            "year": self._current_year,
            "total_available_water": (
                self.config.upper_basin_allocation
                + self.config.lower_basin_allocation
            ),
            "drought_index": 0.0,
        }

        # Basin-level state
        self._basins: Dict[str, Dict[str, Any]] = {
            "upper_basin": {
                "allocation": self.config.upper_basin_allocation,
                "precipitation": 0.0,
                "preceding_factor": 0,
            },
            "lower_basin": {
                "allocation": self.config.lower_basin_allocation,
                "lake_mead_level": 1080.0,
                "preceding_factor": 0,
            },
        }

        # Agent-level state: agent_id → {diversion, request, water_right, basin}
        self._agents: Dict[str, Dict[str, Any]] = {}

        # History for preceding factor computation. Each entry is a dict
        # {state_group: mm} (spec 1.6, v3); _precip_group_flags is this
        # year's per-group strict ">" flag, keyed the same way, computed
        # by _update_preceding_factors and read by get_agent_context.
        self._precip_history: List[Dict[str, float]] = []
        self._precip_group_flags: Dict[str, int] = {}
        # 1 January Lake Mead levels, one per loop year (F17 history, then
        # the 2026-09-25 supply-side redesign). Seeded with the level on
        # 1 January 2018 (1082.52 ft, the observed end-of-2017 value);
        # advance_year() appends each loop year's 1 January level BEFORE
        # _update_preceding_factors reads it, so loop year 1 (2019) compares
        # 1081.46 ft (1 January 2019 = Dec 2018 observed) against 1082.52 ft,
        # a real one-year comparison. Before the redesign the level for year
        # t was generated from year t-1 withdrawals inside advance_year, so
        # the list mixed start- and end-of-year values.
        self._mead_history: List[float] = [1082.52]  # 1 Jan 2018

        # Reservoir storage (MAF, total storage). _mead_storage holds one
        # 1 January value per loop year (index 0 = 1 January 2019);
        # _powell_storage is the current 1 January value.
        _init_elev = self.config.mead_initial_elevation
        _init_storage = float(np.interp(
            _init_elev, self._ELEVATION_FT, self._STORAGE_MAF
        ))
        self._mead_storage: List[float] = [_init_storage]
        self._powell_storage: float = float(self.config.powell_initial_storage_maf)
        # Settlement bookkeeping (see settle_year): the frozen 1 January
        # snapshot of the current year, the final settlement not yet
        # committed, and every committed settlement (one per loop year).
        self._snapshot: Optional[Dict[str, float]] = None
        self._pending_settlement: Optional[Dict[str, Any]] = None
        self._settlement_history: List[Dict[str, Any]] = []

        # Real CRSS precipitation data (None = use synthetic)
        self._crss_precip: Optional[Any] = None  # pandas DataFrame when loaded
        # Review P2: years for which real CRSS data was LOADED but did not
        # cover the simulated year, so _generate_precipitation fell back to
        # the synthetic drying trend. Warned about once per run (see there):
        # a run that believes it used real projections and silently used
        # synthetic numbers for part of its span is a provenance claim the
        # artifacts cannot otherwise contradict.
        self._precip_synthetic_fallback_years: List[int] = []

    # -----------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------

    def initialize_from_csv(self, params_csv_path: str) -> None:
        """Load agent configuration from the calibrated parameters CSV.

        Args:
            params_csv_path: Path to ALL_colorado_ABM_params_cal_1108.csv
        """
        import pandas as pd

        df = pd.read_csv(params_csv_path, index_col=0)
        for agent_name in df.columns:
            self._agents[agent_name] = {
                "basin": "lower_basin" if not agent_name.startswith(
                    ("WY", "UT", "NM", "CO", "AZ_UB")
                ) else "upper_basin",
                "diversion": 0.0,
                "request": 0.0,
                "water_right": 100_000.0,  # Default; override from data
                "curtailment_ratio": 0.0,
                "delivery_ratio": 1.0,
                "gap_reason": "none",
                "at_allocation_cap": False,
                "has_efficient_system": False,
                "below_minimum_utilisation": False,
                "cluster": "unknown",
                "mu": float(df.loc["mu", agent_name]) if "mu" in df.index else SYNTHETIC_HY_MU,
                "sigma": float(df.loc["sigma", agent_name]) if "sigma" in df.index else SYNTHETIC_HY_SIGMA,
                "bin_size_af": 100_000.0 / SYNTHETIC_BIN_DIVISOR,
            }

    def initialize_from_profiles(self, profiles) -> None:
        """Initialise agents from IrrigationAgentProfile list.

        This is the production initialisation path that uses real data
        (water_right, basin, cluster) from the paper's calibrated files.

        Args:
            profiles: List of IrrigationAgentProfile objects created by
                ``create_profiles_from_data()`` or ``create_profiles_from_csv()``.
        """
        # WP1b re-review (MEDIUM 2, 2026-09-29): collected across the loop
        # so mock-smoke runs (often dozens of synthetic Upper Basin
        # profiles) get ONE aggregate log line, not one per agent.
        _synthetic_no_subbasin_ids: List[str] = []
        for p in profiles:
            wr = getattr(p, "water_right", 100_000.0)
            _actual = getattr(p, "actual_2018_diversion", None)
            _init_div = _actual if _actual is not None else wr * 0.8
            precip_group = getattr(p, "precip_group", None)
            # WP1b (item 20, spec 1b.3): supply_group carries precip_group
            # forward as the agent's sub-basin for the water-SUPPLY side
            # (IrrigationEnvironment._settle in "subbasin" mode), distinct
            # in name from precip_group (the agent's own-sub-basin winter
            # precipitation INFORMATION, spec 1.6) even though every real
            # create_profiles_from_data profile sets both to the same
            # value -- they answer different questions and a future
            # profile could set one without the other. A real Upper Basin
            # profile ALWAYS has one (precip_group is set for every state
            # group create_profiles_from_data builds); a profile built
            # another way (synthetic/mock, initialize_synthetic,
            # initialize_from_csv) that never sets it is a legitimate,
            # different case -- _settle treats such an agent as its own
            # unconstrained pool, bound only by the basin-wide backstop,
            # never by a sub-basin cap it was never assigned to (see
            # _settle's docstring). What must never happen silently is a
            # REAL profile missing it: create_profiles_from_data's own bug
            # (an unmapped state group) must fail loudly here, not
            # manufacture a plausible-looking pool agent instead.
            #
            # MEDIUM 3 (2026-09-29 re-review): only checked in "subbasin"
            # mode -- "lees_ferry_pool" never partitions by sub-basin, so a
            # missing one there is not a defect worth raising over.
            #
            # MEDIUM 2 (2026-09-29 re-review): a profile explicitly marked
            # ``synthetic_no_subbasin`` (run_experiment.py /
            # run_fql_baseline.py's mock-smoke-only _create_synthetic_
            # profiles) is NOT the "real profile forgot to set one" case --
            # it is routed to the unconstrained pool on purpose, logged
            # once below, and does not raise. Before this flag existed,
            # such a profile would either raise (if it also had no
            # precip_group) or silently land inside a REAL sub-basin's cap
            # if it happened to collide with one by chance -- neither is
            # correct for a profile that was never meant to represent a
            # real Upper Basin diverter.
            if (
                p.basin == "upper_basin"
                and not precip_group
                and self.config.ub_supply_mode == "subbasin"
            ):
                if getattr(p, "synthetic_no_subbasin", False):
                    _synthetic_no_subbasin_ids.append(p.agent_id)
                else:
                    raise ValueError(
                        f"{p.agent_id}: Upper Basin profile has no precip_group; "
                        "IrrigationEnvironment.initialize_from_profiles needs "
                        "every Upper Basin agent's sub-basin (supply_group) to "
                        "compute its v3 per-sub-basin water supply in "
                        "ub_supply_mode='subbasin' (WP1b, item 20). "
                        "create_profiles_from_data sets precip_group for "
                        "every real Upper Basin profile; a profile built "
                        "another way must set it explicitly, set "
                        "synthetic_no_subbasin=True if it is intentionally a "
                        "mock/smoke profile, or use "
                        "ub_supply_mode='lees_ferry_pool'."
                    )
            self._agents[p.agent_id] = {
                "basin": p.basin,
                "diversion": _init_div,
                "request": _init_div,
                "water_right": wr,
                "curtailment_ratio": 0.0,
                "delivery_ratio": 1.0,
                "gap_reason": "none",
                "at_allocation_cap": False,
                "has_efficient_system": getattr(p, "has_efficient_system", False),
                "below_minimum_utilisation": False,
                "cluster": p.cluster,
                # Own sub-basin winter precipitation column (v3, spec 1.6);
                # None for Lower Basin agents and any profile that never
                # set it (get_agent_context falls back to the basin mean).
                "precip_group": precip_group,
                # WP1b (item 20, spec 1b.3): this agent's sub-basin for the
                # water-supply step (see the comment above); None for Lower
                # Basin agents and any profile without one.
                "supply_group": precip_group,
                # Per-settlement sub-basin diagnostics (WP1b): None/0.0
                # until the first settlement writes them (_write_agent_
                # deliveries); log columns and the yaml dashboard warning
                # read these, not a settlement dict, so a year-1 read
                # before any settlement gets a defined, disclosed value.
                "ub_subbasin_ratio": None,
                "ub_subbasin_sole_bound": 0.0,
                # Hung and Yang (2021) action model: per-agent mu, sigma
                # (calibrated parameters) and the step of the agent's
                # discretised diversion grid. Profiles without a grid step
                # (synthetic) fall back to water_right / 25.
                "mu": float(getattr(p, "mu", SYNTHETIC_HY_MU)),
                "sigma": float(getattr(p, "sigma", SYNTHETIC_HY_SIGMA)),
                "bin_size_af": float(
                    getattr(p, "bin_size_af", None) or wr / SYNTHETIC_BIN_DIVISOR
                ),
                # WP2 (spec 2.3/2.4): the FINAL step bin execute_skill
                # draws against -- None for a profile that never computed
                # one (pre-WP2 builder, synthetic/mock), in which case
                # execute_skill itself falls back to bin_size_af, then to
                # water_right / 25.
                "step_bin_af": getattr(p, "step_bin_af", None),
                "step_bin_source": getattr(p, "step_bin_source", None),
                "demand_per_grid_unit": getattr(p, "demand_per_grid_unit", None),
            }

        # WP1b: each Upper Basin agent's sub-basin member count (the
        # structural fact the "UT2's request would not add water" wording
        # needs, memo section 9) -- a second pass, after every profile is
        # in self._agents, so it counts the FINAL active agent set (56),
        # not the 58 CRSS slots create_profiles_from_data started from.
        _group_counts: Dict[str, int] = {}
        for a in self._agents.values():
            sg = a.get("supply_group")
            if sg:
                _group_counts[sg] = _group_counts.get(sg, 0) + 1
        for a in self._agents.values():
            sg = a.get("supply_group")
            a["ub_subbasin_member_count"] = _group_counts.get(sg) if sg else None

        if _synthetic_no_subbasin_ids:
            from broker.utils.logging import logger as _logger
            _logger.info(
                "[irrigation_env] %d synthetic Upper Basin profile(s) with no "
                "sub-basin (synthetic_no_subbasin=True) routed to the "
                "unconstrained pool bucket under ub_supply_mode='subbasin' "
                "(mock-smoke only, MEDIUM 2, 2026-09-29 re-review): %s",
                len(_synthetic_no_subbasin_ids), _synthetic_no_subbasin_ids,
            )

    def initialize_synthetic(
        self,
        n_agents: int = 31,
        basin_split: Tuple[int, int] = (9, 22),
        base_water_right: float = 100_000.0,
    ) -> None:
        """Create synthetic agents for testing.

        Args:
            n_agents: Total number of agents.
            basin_split: (n_upper, n_lower) agent counts.
            base_water_right: Default annual allocation per agent (acre-ft).
        """
        n_ub, n_lb = basin_split

        # Mix of aggressive, forward-looking, and myopic clusters (50%-30%-20%);
        # the cluster is a label here, the action model is the Hung and Yang
        # draw with the synthetic fallback parameters (SYNTHETIC_HY_*).
        clusters = (
            ["aggressive"] * (n_agents // 2) +
            ["forward_looking_conservative"] * (n_agents * 3 // 10) +
            ["myopic_conservative"] * (n_agents * 2 // 10)
        )
        # Pad to exact n_agents if needed
        while len(clusters) < n_agents:
            clusters.append("myopic_conservative")
        # Shuffle for random assignment
        self.rng.shuffle(clusters)

        agent_index = 0
        for i in range(n_ub):
            aid = f"UB_Agent_{i:03d}"
            cluster = clusters[agent_index] if agent_index < len(clusters) else "myopic_conservative"

            # CRSS Calibration Layer: Scale water_right to match CRSS 2019-2060 aggregate demand
            # Derivation (from per-agent trajectory analysis):
            #   - v12 uncalibrated mean: 6.31 MAF/yr (80.87 KAF/agent × 78 agents)
            #   - CRSS baseline target:  5.86 MAF/yr (75.10 KAF/agent × 78 agents)
            #   - Required scaling:      75.10 / 80.87 = 0.9286 (-7.1% adjustment)
            # Result: Brings aggregate demand from 1.077x CRSS to 1.00x CRSS
            calibrated_wr = base_water_right * 0.9286
            self._agents[aid] = {
                "basin": "upper_basin",
                "diversion": calibrated_wr * 0.8,
                "request": calibrated_wr * 0.8,
                "water_right": calibrated_wr,
                "curtailment_ratio": 0.0,
                "delivery_ratio": 1.0,
                "gap_reason": "none",
                "at_allocation_cap": False,
                "has_efficient_system": False,
                "below_minimum_utilisation": False,
                "cluster": cluster,
                # Hung and Yang action model, synthetic fallback (mock runs)
                "mu": SYNTHETIC_HY_MU,
                "sigma": SYNTHETIC_HY_SIGMA,
                "bin_size_af": calibrated_wr / SYNTHETIC_BIN_DIVISOR,
            }
            agent_index += 1

        for i in range(n_lb):
            aid = f"LB_Agent_{i:03d}"
            cluster = clusters[agent_index] if agent_index < len(clusters) else "myopic_conservative"

            # CRSS Calibration Layer: Scale water_right to match CRSS 2019-2060 aggregate demand
            calibrated_wr = base_water_right * 0.9286
            self._agents[aid] = {
                "basin": "lower_basin",
                "diversion": calibrated_wr * 0.8,
                "request": calibrated_wr * 0.8,
                "water_right": calibrated_wr,
                "curtailment_ratio": 0.0,
                "delivery_ratio": 1.0,
                "gap_reason": "none",
                "at_allocation_cap": False,
                "has_efficient_system": False,
                "below_minimum_utilisation": False,
                "cluster": cluster,
                # Hung and Yang action model, synthetic fallback (mock runs)
                "mu": SYNTHETIC_HY_MU,
                "sigma": SYNTHETIC_HY_SIGMA,
                "bin_size_af": calibrated_wr / SYNTHETIC_BIN_DIVISOR,
            }
            agent_index += 1

    def load_crss_precipitation(self, csv_path: str) -> None:
        """Load real CRSS/PRISM winter precipitation projections.

        Loads the PrismWinterPrecip_ST_NOAA_Future.csv file which contains
        annual winter precipitation (inches) for 9 state-groups from
        2017-2060.  Values are converted to mm and stored for use by
        ``_generate_precipitation()``.

        Columns: WY, UT1, UT2, UT3, NM, CO1, CO2, CO3, AZ
        Upper Basin average: WY, UT1-3, CO1-3
        Lower Basin average: NM, AZ

        A blank cell FAILS THE LOAD, naming the year and column (PR-9 review
        P1-e). ``pandas`` reads a blank as ``NaN``, and nothing downstream
        ever reports one — it is laundered into a plausible number twice
        over:

        * A FEW blank cells in a year: ``_generate_precipitation`` takes
          ``.mean()`` over the seven Upper Basin columns, and pandas' mean
          SKIPS NaN, so the year silently becomes the average of whichever
          stations reported. No error, no NaN, just a different number than
          the file was supposed to give.
        * A WHOLE blank Upper Basin row: the mean of nothing is ``NaN``, and
          the clamps then convert it into the most extreme legal value in
          each direction, because every comparison with NaN is False.
          ``max(6.0, min(17.0, NaN))`` returns ``17.0`` — the operational
          CEILING on natural flow — while
          ``max(0.0, min(1.0, 1.0 - NaN/baseline))`` in
          ``_compute_drought_index`` returns ``1.0``, MAXIMUM drought. One
          missing row thus reaches the agent as "wettest possible inflow,
          worst possible drought", and no artifact anywhere records that a
          cell was blank.

        Refusing at LOAD time is the only point where the year and the column
        are still known.

        This check runs only when real CRSS data is loaded, which the
        ``--model mock`` byte-identity runs never do (they leave
        ``_crss_precip`` as ``None`` and take the synthetic path), so no
        frozen corpus is affected.

        Args:
            csv_path: Path to PrismWinterPrecip_ST_NOAA_Future.csv

        Raises:
            ValueError: if any cell in the file is blank / non-numeric.
        """
        import pandas as pd

        df = pd.read_csv(csv_path, index_col=0)
        # Convert inches to mm (1 inch = 25.4 mm)
        mm = df * 25.4
        nan_mask = mm.isna()
        if bool(nan_mask.to_numpy().any()):
            bad = [
                f"{index_label}/{column}"
                for column in mm.columns
                for index_label in mm.index[nan_mask[column]]
            ]
            raise ValueError(
                f"load_crss_precipitation: {len(bad)} blank/non-numeric cell(s) in "
                f"{csv_path} at year/column {bad[:20]}"
                f"{' (first 20 shown)' if len(bad) > 20 else ''}. A blank precipitation "
                f"cell becomes NaN, and the min/max clamps downstream turn NaN into "
                f"maximum inflow and maximum drought rather than an error. Fix the "
                f"source file, or drop the affected year(s) deliberately."
            )
        self._crss_precip = mm

        # Review 2026-09-28 (fix 2): seed _precip_history with the
        # sim_start_year - 1 (2018) row BEFORE the first advance_year()
        # call, so loop year 1's (2019) per-group flag compares 2019
        # against 2018 (H&Y's own convention, spec 1.6) instead of
        # defaulting every group to 0 for lack of a prior year on record.
        # Only when _precip_history is still empty (this must run before
        # any advance_year() call to mean anything; a caller that has
        # already advanced does not get retroactively reseeded).
        seed_year = self.config.sim_start_year - 1
        if not self._precip_history and seed_year in mm.index:
            groups = ("WY", "UT1", "UT2", "UT3", "NM", "CO1", "CO2", "CO3", "AZ")
            self._precip_history.append({g: float(mm.loc[seed_year, g]) for g in groups})

    # -----------------------------------------------------------------
    # TieredEnvironmentProtocol interface
    # -----------------------------------------------------------------

    @property
    def global_state(self) -> Dict[str, Any]:
        return self._global.copy()

    @property
    def local_states(self) -> Dict[str, Dict[str, Any]]:
        return {k: v.copy() for k, v in self._basins.items()}

    @property
    def institutions(self) -> Dict[str, Dict[str, Any]]:
        return {
            "colorado_compact": {
                "upper_allocation": self.config.upper_basin_allocation,
                "lower_allocation": self.config.lower_basin_allocation,
                "shortage_tier": self._compute_shortage_tier(),
            },
            "reservoirs": {
                "powell_storage_maf": self._powell_storage,
                "mead_storage_maf": self._mead_storage[-1],
                "powell_capacity_maf": self.config.powell_capacity_maf,
                "powell_dead_pool_maf": self.config.powell_dead_pool_maf,
                "min_powell_release_maf": self.config.min_powell_release_maf,
            },
        }

    @property
    def social_states(self) -> Dict[str, Dict[str, Any]]:
        return {}  # Irrigation agents don't have social state in this model

    def get_observable(self, path: str, default: Any = None) -> Any:
        """Safe dot-notation access to environment state."""
        parts = path.split(".")
        if not parts:
            return default

        if parts[0] == "global":
            return self._global.get(parts[1], default) if len(parts) > 1 else default
        if parts[0] == "local" and len(parts) > 1:
            basin = self._basins.get(parts[1], {})
            return basin.get(parts[2], default) if len(parts) > 2 else basin or default
        if parts[0] == "agent" and len(parts) > 1:
            agent = self._agents.get(parts[1], {})
            return agent.get(parts[2], default) if len(parts) > 2 else agent or default

        return default

    def set_global(self, key: str, value: Any) -> None:
        self._global[key] = value

    def set_local(self, location_id: str, key: str, value: Any) -> None:
        if location_id in self._basins:
            self._basins[location_id][key] = value

    def get_local(self, location_id: str, key: str, default: Any = None) -> Any:
        return self._basins.get(location_id, {}).get(key, default)

    def set_social(self, agent_id: str, key: str, value: Any) -> None:
        pass  # No social state in current model

    def to_dict(self) -> Dict[str, Any]:
        return {
            "global": self._global.copy(),
            "basins": {k: v.copy() for k, v in self._basins.items()},
            "institutions": self.institutions,
            "n_agents": len(self._agents),
            "year": self._current_year,
        }

    # -----------------------------------------------------------------
    # Simulation control
    # -----------------------------------------------------------------

    def advance_year(self) -> Dict[str, Any]:
        """Advance to next simulation year and generate water signals.

        Returns:
            Updated global state dict.
        """
        self._year_index += 1
        # F12 (2026-09-25 audit): using _year_index as a straight offset made
        # loop year 1 calendar year 2020 (one year late) and loop year 42
        # calendar year 2061, one year past the CRSS PRISM CSV's real
        # 2017-2060 coverage, so the LAST year of every 42-year run silently
        # used the synthetic drying-trend fallback instead of a real CRSS
        # row. The "- 1" makes loop year 1 = sim_start_year (2019) and loop
        # year 42 = 2060, matching docs/irrigation_physics.md ("Y1 =
        # calendar year 2019"), DATA.md and README.md (already documented as
        # 2019-2060), and keeps every loop year inside real CRSS coverage.
        self._current_year = self.config.sim_start_year + self._year_index - 1
        self._global["year"] = self._current_year

        # 1. Commit last year's final settlement: its end-of-year storages
        #    become this year's 1 January storages. A caller that never
        #    called settle_year() (the FQL baseline, unit tests driving
        #    advance_year() directly) gets it here, at last year's final
        #    requests, so storage always evolves exactly once per year.
        #    Always recomputed here (settle_year is idempotent), so a request
        #    changed after an earlier settle_year() call in the same year is
        #    still what the committed storage reflects.
        # L2 N4 (2026-09-28): the settlement being committed here is last
        # loop year's (self._current_year is about to be, or on the FIRST
        # commit already was, bumped past it), so it is labelled with
        # ``self._current_year - 1``, not whatever _current_year holds when
        # _commit_settlement actually runs.
        if self._snapshot is not None:
            self._commit_settlement(self.settle_year(), year=self._current_year - 1)

        # 2. Water signals for this year. Natural flow no longer depends on
        #    precipitation (v3, spec 1.1): it is the committed USBR
        #    hydrology table's value for this simulation year, no clamp,
        #    raising if the year is outside the table (removes the
        #    precipitation-to-flow proxy and its [6, 17] MAF clamp, L2 H1,
        #    D5). Precipitation survives only as Upper Basin agents' own
        #    information (spec 1.6) and the legacy drought_index input.
        precip_by_group = self._generate_precipitation()
        natural_flow = self._natural_flow_for_year(self._current_year)
        mead_level = self._storage_to_elevation(self._mead_storage[-1])
        self._mead_history.append(mead_level)

        # Legacy 7-column (WY, UT1-3, CO1-3) mean: kept ONLY as the
        # drought_index input (spec 1.6: "no prompt, rule or metric reads"
        # it) and as the basin-level fallback for an agent with no
        # precip_group (synthetic/mock profiles) -- see get_agent_context.
        legacy_cols = ("WY", "UT1", "UT2", "UT3", "CO1", "CO2", "CO3")
        legacy_precip_mean = float(np.mean([precip_by_group.get(c, 0.0) for c in legacy_cols]))
        self._basins["upper_basin"]["precipitation"] = legacy_precip_mean
        self._basins["lower_basin"]["lake_mead_level"] = mead_level

        # Compute preceding factors (per-UB-group, spec 1.6; LB unchanged)
        self._update_preceding_factors(precip_by_group, mead_level)

        # Compute drought index (0 = no drought, 1 = severe) -- legacy
        # proxy, disclosed as unread by any prompt, rule or metric.
        self._global["drought_index"] = self._compute_drought_index(legacy_precip_mean, mead_level)

        # Compute total available water with some variability
        base = self.config.upper_basin_allocation + self.config.lower_basin_allocation
        variability = 1.0 - self._global["drought_index"] * 0.3
        self._global["total_available_water"] = base * variability

        # 3. Declarations from the 1 January Mead level: the tier and its
        #    shortage VOLUME (2007 ROD, spec 1.5; replaces the flat
        #    0/5/10/20 percent cuts). PI decision 2026-09-28: the volume
        #    is borne entirely by the non-agricultural bucket, a fixed
        #    computation independent of any agent's request -- _settle
        #    derives it (and the informational curtailment_ratio) from V
        #    directly, so no carried-request sum is needed here.
        tier = self._compute_shortage_tier()
        shortage_volume = self._tier_shortage_volume_maf(tier)
        lb_tributary = self._lb_tributary_for_year(self._current_year)
        mexico = self._mexico_delivery_maf(mead_level)

        # WP2 (spec 2.1; WP1 re-review ordering requirement): every agent's
        # request is reset to its base -- the delivered amount from the
        # last COMMITTED settlement (step 1 above; 2019 starts from
        # actual_2018_diversion, already the year-1 request/diversion
        # initialize_from_profiles sets) -- BEFORE anything below sums
        # this year's projected requests or plans the Powell release, so
        # the plan, the provisional settlement and the supply rule all see
        # the keep request, never last year's carried (pre-reset) ask.
        # WP2 review round 1 (HIGH 1): skipped when
        # config.hold_requests_fixed is True -- a held-fixed replay (every
        # agent's request set once, at initialisation, and never touched
        # again) needs THIS year's projected sums and Powell plan to see
        # that fixed target too, which they cannot if it is overwritten
        # here. No real run (LLM or FQL) ever sets the flag.
        if not self.config.hold_requests_fixed:
            self._reset_requests_to_base()

        # Re-review 2026-09-29 (HIGH 1, then HIGH A round 3): the Powell
        # release must be planned ONCE for the whole year BEFORE agents
        # decide, exactly as the 2007 Guidelines set the annual release
        # target from PROJECTED end-of-year contents (the 24-Month Study),
        # not from whatever agents end up requesting. Both basins' request
        # totals are frozen here, at each agent's CURRENT request -- WP2's
        # _reset_requests_to_base() above (spec 2.1) has already reset
        # that to last year's receipt, so "current" and "keep request"
        # coincide by the time this sum runs. HIGH A: the
        # first pass only froze the Lower Basin total, so a mid-year Upper
        # Basin request change still moved the release (the reviewer's
        # probe: a 15 percent Upper Basin raise after advance_year moved
        # the release in 16 of 42 years, by up to 0.237 MAF) -- both totals
        # are frozen now, and the release itself (not just its inputs) is
        # computed here and stored, so _settle only ever APPLIES it.
        # Re-review 2026-09-29 round 4 (LOW 1): the sum-with-water-right-cap
        # formula is factored into _basin_request_projected_maf so test
        # helpers can call the SAME method instead of re-deriving it, and
        # cannot silently drift from what production actually does.
        ub_request_projected_maf = self._basin_request_projected_maf(is_upper_basin=True)
        lb_request_projected_maf = self._basin_request_projected_maf(is_upper_basin=False)
        # WP1b (item 20): A_s(t) is known on 1 January (memo section 6 step
        # 4), computed here so it can be frozen into the snapshot below and
        # so _settle stays pure (it only ever reads the snapshot, never
        # this table directly). Computed unconditionally (cheap: one
        # dict-of-9-floats lookup) -- only actually USED downstream when
        # ub_supply_mode is "subbasin", but always available for the
        # agent-facing sub-basin flow-share text (get_agent_context),
        # which is true regardless of mode.
        ub_subbasin_available_maf = self._ub_subbasin_available_maf_for_year(self._current_year)
        ub_request_projected_by_subbasin_maf = self._ub_request_projected_by_subbasin_maf()
        powell_release_planned_maf = self._plan_powell_release(
            nf=natural_flow,
            s_p=float(self._powell_storage),
            s_m=float(self._mead_storage[-1]),
            trib=lb_tributary,
            shortage_volume=shortage_volume,
            mexico=mexico,
            ub_requested_maf=ub_request_projected_maf,
            lb_requested_maf=lb_request_projected_maf,
            ub_requested_by_subbasin_maf=ub_request_projected_by_subbasin_maf,
            ub_available_by_subbasin_maf=ub_subbasin_available_maf,
        )

        # 4. Freeze this year's 1 January snapshot, then the PROVISIONAL
        #    settlement at the carried requests: what each agent can expect
        #    this year at its current request (the value its prompt and the
        #    governance checks read). settle_year() redoes it at the final
        #    requests after every decision.
        self._snapshot = {
            "powell_storage": float(self._powell_storage),
            "mead_storage": float(self._mead_storage[-1]),
            "natural_flow": float(natural_flow),
            "lb_shortage_volume_maf": float(shortage_volume),
            "mexico": float(mexico),
            "lb_tributary": float(lb_tributary),
            "lb_request_projected_maf": float(lb_request_projected_maf),
            # WP2 review round 1 (MEDIUM 3): the Upper Basin counterpart of
            # lb_request_projected_maf above -- frozen so a test (or any
            # other caller) can read what advance_year() actually summed,
            # rather than re-deriving it and risking exactly the drift
            # _basin_request_projected_maf was factored out to prevent.
            "ub_request_projected_maf": float(ub_request_projected_maf),
            "powell_release_planned_maf": float(powell_release_planned_maf),
            # WP1b (item 20): known on 1 January (memo section 6 step 4),
            # so _settle (both the provisional call below and settle_year's
            # final call) reads it from here and stays pure.
            "ub_subbasin_available_af": {s: v * 1e6 for s, v in ub_subbasin_available_maf.items()},
            "calendar_year": self._calendar_year_for(self._current_year),
        }
        self._pending_settlement = None
        provisional = self._settle(self._snapshot)
        self._write_agent_deliveries(provisional)
        # spec 1.5: curtailment_ratio is written from each settlement,
        # provisional (here) then final (settle_year) -- see _apply_curtailment.
        self._apply_curtailment(provisional["lb_cut"])

        self._global["natural_flow_maf"] = float(natural_flow)
        self._global["powell_storage_maf"] = float(self._powell_storage)
        self._global["mead_storage_maf"] = float(self._mead_storage[-1])

        # Basin-level aggregate request: a logged metric (the retired
        # demand ceiling used to block on it); basin_request_over_target is
        # the request total over the 5.86 MAF CRSS 2019-2060 demand target.
        self._global["total_basin_demand"] = sum(
            a["request"] for a in self._agents.values()
        )
        self._global["basin_request_over_target"] = (
            self._global["total_basin_demand"] / CRSS_DEMAND_TARGET_AF
        )

        return self._global.copy()

    def _reset_requests_to_base(self) -> None:
        """WP2 spec 2.1: reset every agent's request to its BASE -- the
        delivered amount from the last COMMITTED settlement (``diversion``,
        just written by step 1's commit block above; 2019 starts from
        ``actual_2018_diversion``, the year-1 request/diversion
        ``initialize_from_profiles`` sets, so this is a no-op the first
        time ``advance_year`` ever runs). This function itself applies NO
        clipping -- ``request`` is simply set equal to ``diversion``,
        never raised toward the minimum-use floor F. It never needs to
        clip to ``[0, W]`` either, because a committed delivery already
        satisfies ``0 <= delivered <= request <= W`` (the settlement that
        produced ``diversion`` enforces that bound), so the water-right
        cap cannot bind on the value this function assigns.

        Skipped entirely when ``config.hold_requests_fixed`` is True (WP2
        review round 1, HIGH 1): a held-fixed replay (every agent's
        request set once, at initialisation, and never touched again)
        needs this year's projected sums and Powell plan to see that
        fixed value, not last year's delivery.

        MUST run before anything sums this year's projected requests (the
        Powell release plan, ``_basin_request_projected_maf``) or takes
        the provisional settlement -- the ordering requirement from the
        WP1 re-review (2026-09-29), pinned by
        ``test_v3_action_model.py::test_reset_precedes_release_plan``.

        Sets ``at_allocation_cap`` / ``below_minimum_utilisation`` FROM
        THE BASE (spec 2.1's "flags are set from the base"), with the
        same 1-percent tolerances ``update_agent_request`` uses, so the
        registry preconditions that filter this year's menu (built from
        this state, before the agent decides) see the base's limits, not
        whatever an earlier decision temporarily left behind.
        """
        for agent in self._agents.values():
            base_af = float(agent["diversion"])
            wr = float(agent["water_right"])
            agent["base_af"] = base_af
            agent["request"] = base_af
            agent["at_allocation_cap"] = base_af >= 0.99 * wr
            agent["below_minimum_utilisation"] = base_af <= 1.01 * wr * MIN_UTIL

    def get_agent_context(self, agent_id: str) -> Dict[str, Any]:
        """Build context dict for a specific agent's LLM prompt.

        Returns:
            Dictionary with all water signals and agent state suitable
            for prompt template injection.
        """
        agent = self._agents.get(agent_id, {})
        basin_key = agent.get("basin", "lower_basin")
        basin = self._basins.get(basin_key, {})
        # Re-review 2026-09-29 (LOW E): computed here, BEFORE the guard
        # call below, so the guard can check presence of the REAL
        # per-agent sub-basin value the Upper Basin branch below actually
        # reads, not just the basin-level legacy mean.
        current_precip_by_group = self._precip_history[-1] if self._precip_history else {}

        # PR-9 coupling-retrofit (F1): with the flag ON, fail loud on a
        # genuinely missing field INSTEAD of the .get(key, 0) defaults
        # below silently manufacturing a plausible-looking zero. No-op
        # (and no output change) when every field below is actually
        # present — see irrigation_coupling.guard_agent_context_sources.
        if self._coupling_contract_active:
            from examples.irrigation_abm.irrigation_coupling import (
                guard_agent_context_sources,
            )
            guard_agent_context_sources(
                self._irrigation_contract,
                agent=agent, basin_key=basin_key, basin=basin,
                global_state=self._global,
                precip_by_group=current_precip_by_group,
            )
            # Counted AFTER the guard returns, so the number means "calls
            # that passed", not "calls attempted" — a run that raised is
            # reported by the exception, not by this tally.
            self._coupling_guard_calls += 1

        # Upper Basin own-sub-basin precipitation and flag (spec 1.6,
        # L1-03): an agent whose profile set precip_group (every real
        # create_profiles_from_data profile) reads ITS OWN group's value
        # and strict ">" flag for the current year; an agent with no
        # precip_group (synthetic/mock profiles) falls back to the
        # basin-level legacy value (7-column mean, ">="), exactly as
        # before this change -- so a mock run's context shape is
        # unaffected. preceding_factor keeps its name (read by
        # irrigation_personas.build_water_situation_text, unchanged in
        # WP1) but now carries the per-group flag for a real UB agent,
        # not the legacy basin mean.
        precip_group = agent.get("precip_group")
        if basin_key == "upper_basin" and precip_group:
            # Review 2026-09-28 (fix 8): a SET precip_group that is not
            # among this year's known columns is a real data-shape defect
            # (a typo, a stale group label), not a legitimate "no group"
            # case -- refuse to launder it into the basin-level fallback.
            if precip_group not in current_precip_by_group:
                raise ValueError(
                    f"{agent_id}: precip_group={precip_group!r} is not among "
                    f"this year's precipitation columns "
                    f"({sorted(current_precip_by_group) or 'none loaded'}); "
                    "refusing to silently fall back to the basin-level mean "
                    "for an agent whose profile explicitly set a group."
                )
            own_precip = float(current_precip_by_group[precip_group])
            own_precip_flag = int(self._precip_group_flags.get(precip_group, 0))
        elif basin_key == "upper_basin":
            # No precip_group at all (synthetic/mock profiles): the
            # legitimate fallback to the basin-level legacy mean.
            own_precip = basin.get("precipitation", 0)
            own_precip_flag = int(basin.get("preceding_factor", 0))
        else:
            # Re-review 2026-09-29 (MEDIUM 4): the Lower Basin has no
            # precipitation signal in this model at all -- Upper Basin
            # winter precipitation is not even observed at a Lower Basin
            # location (F15, irrigation_personas.py:_build_trend_text).
            # The pre-fix code returned 0 for precipitation_mm and
            # self._basins["lower_basin"]["preceding_factor"] (a REAL,
            # correctly-named Lake Mead level-change flag) relabelled as
            # "precipitation_flag" -- a fabricated reading and a real
            # signal wearing the wrong name. That real signal is already
            # exposed correctly below under its own "preceding_factor"
            # key; None here says plainly that this basin has no
            # precipitation reading, rather than manufacturing one.
            own_precip = None
            own_precip_flag = None

        # WP1b (item 20, spec 1b.4): the sub-basin flow share p = Q_s(m(t))
        # / mean over 1971-2018 of Q_s, and the sub-basin's member count --
        # TRUE regardless of ub_supply_mode (a descriptive fact about the
        # sub-basin's own hydrology, not about which rule currently
        # governs deliveries, spec item 20 text: "every sentence must be
        # true in both supply modes"), so computed here unconditionally
        # for any Upper Basin agent with a supply_group. None for a Lower
        # Basin agent or an Upper Basin agent without one (synthetic/mock
        # profile) -- build_water_situation_text falls back to the
        # pre-WP1b absolute-flow sentence in that case.
        supply_group = agent.get("supply_group")
        ub_subbasin_flow_share = None
        if basin_key == "upper_basin" and supply_group:
            supply_row = _load_ub_subbasin_supply_table(
                self.config.ub_subbasin_supply_variant
            ).get(self._current_year)
            if supply_row is None:
                raise ValueError(
                    f"{agent_id}: no ub_subbasin_supply_v3.csv row for simulation "
                    f"year {self._current_year}."
                )
            # WP1b re-review (LOW 1, 2026-09-29, third round): the mean
            # flow must come from THIS agent's own ub_subbasin_supply_
            # variant, not always the recommended envelope's -- a variant
            # with a different gauge map ("lees_ferry_all",
            # "tributary_gauges") has a genuinely different Q_s(y), so
            # dividing its flow by the recommended envelope's mean compared
            # two different physical quantities (the bug this fixes).
            variant = self.config.ub_subbasin_supply_variant
            variant_means = _load_ub_subbasin_variant_means().get(variant)
            if variant_means is None:
                raise ValueError(
                    f"{agent_id}: ub_subbasin_supply_variant={variant!r} is not "
                    f"among the rows in ub_subbasin_variant_means_v3.csv."
                )
            q_s_mean = variant_means.get(supply_group)
            if q_s_mean is None:
                raise ValueError(
                    f"{agent_id}: supply_group={supply_group!r} is not among the "
                    f"sub-basins in ub_subbasin_variant_means_v3.csv ({UB_SUBBASINS})."
                )
            # WP1b re-review (LOW 6, 2026-09-29): a non-positive mean flow
            # is a real data defect in the checksum-verified means file,
            # not a legitimate "cannot compute a share" case -- raise
            # rather than silently leaving ub_subbasin_flow_share None,
            # which build_water_situation_text would read as "no sub-basin
            # data available" and fall back to the pre-WP1b Lees Ferry
            # sentence for an agent that DOES have a real sub-basin.
            if q_s_mean <= 0:
                raise ValueError(
                    f"{agent_id}: ub_subbasin_variant_means_v3.csv "
                    f"q_{supply_group}_mean_af for variant={variant!r} is "
                    f"{q_s_mean}, not positive; refusing to silently fall "
                    "back to the Lees Ferry sentence for a real sub-basin."
                )
            ub_subbasin_flow_share = supply_row[f"q_{supply_group}_af"] / q_s_mean

        return {
            # Agent state
            "agent_id": agent_id,
            "basin": basin_key,
            "current_diversion": agent.get("diversion", 0),
            "current_request": agent.get("request", 0),
            "water_right": agent.get("water_right", 0),
            "curtailment_ratio": agent.get("curtailment_ratio", 0),
            # Expected share of the request delivered this year, and why it
            # is below 1 (a settlement code, see _settle). Provisional until
            # settle_year() runs; after it, the final values for the year.
            "delivery_ratio": agent.get("delivery_ratio", 1.0),
            "gap_reason": agent.get("gap_reason", "none"),
            "at_allocation_cap": agent.get("at_allocation_cap", False),
            "has_efficient_system": agent.get("has_efficient_system", False),
            "below_minimum_utilisation": agent.get("below_minimum_utilisation", False),
            "cluster": agent.get("cluster", "unknown"),
            # WP1b (item 20): this agent's sub-basin (None for Lower Basin
            # / no-sub-basin agents), its member count, its own sub-basin
            # ratio_s from the last settlement (None until one has run, or
            # outside subbasin mode / no sub-basin -- see _settle), and its
            # flow share p (computed above, true in both supply modes).
            "supply_group": supply_group,
            "ub_subbasin_member_count": agent.get("ub_subbasin_member_count"),
            "ub_subbasin_ratio": agent.get("ub_subbasin_ratio"),
            "ub_subbasin_flow_share": ub_subbasin_flow_share,
            # Basin signals
            "precipitation": own_precip,
            "precipitation_flag": own_precip_flag,
            "lake_mead_level": basin.get("lake_mead_level", 0),
            "preceding_factor": (
                own_precip_flag if basin_key == "upper_basin" else basin.get("preceding_factor", 0)
            ),
            # Global signals
            "year": self._current_year,
            "drought_index": self._global.get("drought_index", 0),
            "total_available_water": self._global.get("total_available_water", 0),
            "shortage_tier": self._compute_shortage_tier(),
            # Re-review 2026-09-29 (HIGH 2): the declared tier's own
            # shortage volume (2007 ROD Section 2.D.1: 0 / 0.333 / 0.417 /
            # 0.500 MAF), so build_water_situation_text can state the real
            # acre-feet cut to the non-agricultural bucket instead of
            # implying curtailment_ratio (V / N) is applied to this
            # agent's own delivery.
            "lb_shortage_volume_maf": self._tier_shortage_volume_maf(
                self._compute_shortage_tier()
            ),
            "total_basin_demand": self._global.get("total_basin_demand", 0),
            "basin_request_over_target": self._global.get("basin_request_over_target", 0),
            "natural_flow_maf": self._global.get("natural_flow_maf", 0),
            "powell_storage_maf": self._global.get("powell_storage_maf", 0),
            # N7 (2026-09-26 regression audit): read by
            # irrigation_personas.py (build_water_situation_text) to render
            # the dead-pool sentence instead of "Lake Powell holds N million
            # acre-ft" when storage is at or below the floor.
            "powell_dead_pool_maf": self.config.powell_dead_pool_maf,
        }

    def update_agent_request(
        self,
        agent_id: str,
        new_request: float,
    ) -> None:
        """Apply agent's decision (new diversion request).

        The environment computes the actual diversion received based on
        water availability and compact rules.
        """
        if agent_id not in self._agents:
            return

        agent = self._agents[agent_id]
        # Cap at water right
        new_request = max(0.0, min(new_request, agent["water_right"]))
        agent["request"] = new_request
        agent["at_allocation_cap"] = new_request >= agent["water_right"] * 0.99
        # WP2 spec 2.1/C7: "at the floor" uses the SAME 1-percent tolerance
        # as the cap (<= 1.01 F, not < F) -- so a request within 1 percent
        # of the floor is treated as AT it, matching execute_skill's own
        # decrease no-op guard below and _reset_requests_to_base's flag.
        agent["below_minimum_utilisation"] = (
            new_request <= agent["water_right"] * MIN_UTIL * 1.01
        )

        # Provisional delivery at the new request: this year's expected
        # delivery ratio (from the provisional settlement advance_year ran,
        # which already includes the shortage tier and any physical limit).
        # The authoritative value is written by settle_year() once every
        # decision for the year has executed.
        agent["diversion"] = new_request * agent.get("delivery_ratio", 1.0)

    def _decision_rng(self, agent_id: str, skill: str) -> np.random.Generator:
        """A generator private to one ``(seed, year, agent, skill)``.

        The decision phase runs inside
        ``ExperimentRunner._run_agents_parallel``'s ThreadPoolExecutor, so
        any draw taken from the shared env-level ``self.rng`` is handed out
        in thread-completion order rather than agent order.  The same seed
        then yields a different agent -> magnitude assignment under
        ``--workers 4`` than under ``--workers 1``, and a different one again
        between two ``--workers 4`` runs at that seed (measured 2026-09-15:
        13 of 16 agents diverged).  The distribution stays correct; which
        agent receives which sample does not, which is what an audit trace
        and every per-agent analysis read.

        Deriving a fresh generator per call removes the shared stream
        entirely, so no amount of thread interleaving can reach the draw:
        the value depends only on the four keys below.  Creation is cheap
        relative to one governed LLM step, and stateless, so no lock is
        needed and none is taken.

        ``zlib.crc32`` hashes the string keys, NOT the builtin ``hash``:
        the builtin is salted per process (``PYTHONHASHSEED``), which would
        trade a thread-order dependence for a process-launch dependence.

        INVARIANT this leans on: calling it twice with the same key returns
        the same value, so a domain that draws twice per ``(agent, year,
        skill)`` would get the same magnitude both times. That is safe here
        only because the engine executes at most one magnitude-drawing skill
        per key — ``broker/core/skill_broker_engine.py:716-718`` rejects a
        secondary skill whose name equals the primary's, the
        rejected-fallback execution lives in an ``elif`` arm that cannot run
        alongside the approved one, and ``advance_year`` increments
        ``_current_year`` unconditionally so a year never repeats. A future
        multi-decision-per-year domain must add a fifth key component (an
        attempt index) rather than assume this still holds.
        """
        return np.random.default_rng([
            int(self.config.seed) & 0xFFFF_FFFF,
            int(self._current_year) & 0xFFFF_FFFF,
            zlib.crc32(agent_id.encode("utf-8")),
            zlib.crc32(skill.encode("utf-8")),
        ])

    def execute_skill(self, approved_skill) -> "ExecutionResult":
        """Execute an approved irrigation skill.

        This satisfies the ``sim_engine.execute_skill()`` interface expected
        by ``ExperimentRunner`` for the broker pipeline.

        Args:
            approved_skill: An ``ApprovedSkill`` instance with
                ``.skill_name``, ``.agent_id``, and ``.parameters``.

        Returns:
            ExecutionResult with success status and state changes.
        """
        from broker.interfaces.skill_types import ExecutionResult

        aid = approved_skill.agent_id
        skill = approved_skill.skill_name
        agent = self._agents.get(aid)
        if agent is None:
            return ExecutionResult(success=False, error=f"Unknown agent: {aid}")

        wr = agent["water_right"]
        # v21 FIX: Use request (paper demand) as base for all skills.
        # Previously used diversion (physical delivery), which is compressed
        # by curtailment + Powell constraints.  This created an asymmetry:
        # maintain_demand preserved request while increase/decrease operated
        # on the much-lower diversion.  Using request ensures a consistent
        # base across all skill types.  A request is bounded by the water
        # right (min(current + change, wr) below); what the agent actually
        # receives is bounded by the supply-side settlement (_settle).
        # WP2 (spec 2.1): ``request`` is reset to the WP2 base (last year's
        # committed delivery, ``_reset_requests_to_base``) before any agent
        # decides, so ``current`` below already IS that base. Review round
        # 1, MEDIUM 4 correction: this is NOT limited to the LLM path --
        # ``_reset_requests_to_base`` runs inside ``advance_year()``
        # unconditionally (``config.hold_requests_fixed`` aside), and the
        # FQL baseline calls the SAME ``advance_year()``, so its carried
        # request is reset the same way. That is Div_t becoming "last
        # final delivery" a WP2 commit early, ahead of WP5 5.1's own
        # explicit statement of it and 5.4's UB-unit follow-up -- WP5
        # still owns removing this function's OWN redraw for FQL (L1-04)
        # and the state/reward unit conversion, neither of which has
        # happened yet.
        current = agent["request"]
        meta = getattr(approved_skill, "parameters", {}) or {}

        # Hung and Yang (2021) action model (ref/RL-ABM-CRSS/ABM_CRSS_coupling.py
        # (Q_learning)): step = (mu + |N(0, sigma)|) x bin_size, per-agent mu,
        # sigma and grid step. The LLM picks the direction and the class; a
        # small step is a draw at or below the agent's median step
        # T = (mu + 0.6745 sigma) x bin_size, a large step a draw above it
        # (hy_step_af). Drawn from the per-(seed, year, agent, skill) stream
        # (_decision_rng), so thread scheduling cannot reach it. H&Y explore
        # with epsilon-greedy over the DIRECTION, not the magnitude; the
        # former 2 percent magnitude exploration had no analogue there and is
        # dropped (is_exploration stays in the logs, always False).
        mu = float(agent.get("mu", SYNTHETIC_HY_MU))
        sigma = float(agent.get("sigma", SYNTHETIC_HY_SIGMA))
        # WP2 (spec 2.3/2.4): the agent's FINAL step bin -- the UB-converted,
        # possibly-rescaled value ``create_profiles_from_data`` computes as
        # ``profile.step_bin_af`` -- is what the LLM path draws against, NOT
        # the raw ``bin_size_af`` (which WP5 still needs unconverted for the
        # FQL grid-state discretisation). ``resolve_step_bin_af`` (review
        # round 1, LOW 8) is the ONE shared resolver, also used by
        # ``build_option_texts`` and ``build_simulation_log_row``, so the
        # drawn, shown and logged values can never silently disagree.
        _raw_step_bin_af = agent.get("step_bin_af") or agent.get("bin_size_af")
        if not _raw_step_bin_af or _raw_step_bin_af <= 0:
            from broker.utils.logging import logger as _logger
            _logger.warning("[irrigation_env] %s has step_bin_af=%r; using water_right / %d",
                            aid, _raw_step_bin_af, SYNTHETIC_BIN_DIVISOR)
        step_bin_af = resolve_step_bin_af(agent.get("step_bin_af"), agent.get("bin_size_af"), wr)
        step_af = 0.0
        size_class = ""
        is_exploration = False
        if skill != "maintain_demand":
            if skill in _SMALL_SKILLS:
                size_class = "small"
            elif skill in _LARGE_SKILLS:
                size_class = "large"
            else:
                size_class = "any"
            rng = self._decision_rng(aid, skill)
            step_af = hy_step_af(rng, mu, sigma, step_bin_af, size_class)
            if size_class == "any":
                size_class = (
                    "small" if step_af <= hy_threshold_af(mu, sigma, step_bin_af) else "large"
                )

        state_changes: Dict[str, Any] = {}
        state_changes["is_exploration"] = is_exploration

        # F07 (2026-09-25 audit): the applied magnitude never reached memory
        # because ``_apply_state_changes`` (broker/core/experiment_runner.py)
        # reads ``params["magnitude_pct"]`` (the LLM's proposal, not what was
        # actually applied) or ``result.execution_result.action_context``,
        # and this method only ever set ``state_changes["magnitude_pct_applied"]``,
        # never ``action_context``. Populated below for every skill that
        # actually samples a magnitude, so build_action_outcome_feedback's
        # "(by N%)" reflects the Gaussian-sampled value the environment used,
        # not the LLM's discrete request.
        action_context: Dict[str, Any] = {}

        if skill in ("increase_large", "increase_small", "increase_demand"):
            # H&Y step added to the request, capped at the water right;
            # deliveries are limited by _settle, not here.
            new_req = min(current + step_af, wr)
            self.update_agent_request(aid, new_req)
            state_changes["request"] = new_req
            _set_realised_magnitude(state_changes, action_context, step_af, size_class,
                                    current, new_req)

        elif skill in ("decrease_large", "decrease_small", "decrease_demand"):
            # H&Y step subtracted from the request, floored at the 10
            # percent minimum utilisation. The former taper near the floor
            # (an invented diminishing-returns rule) is removed: H&Y bound the
            # decision by the grid, not by a taper.
            # WP2 spec 2.1: max(base - s, F) only when base > 1.01 F; at or
            # below that tolerance the request is already treated as AT the
            # floor (below_minimum_utilisation, same 1.01 tolerance as
            # update_agent_request/_reset_requests_to_base) and a decrease
            # is a NO-OP -- never floor-anchored back UP to F. Without this
            # branch, an agent whose base already sits below F (4 LB agents
            # start there, spec/provenance C6) would have its "decrease"
            # RAISE its request to F, which spec 2.1 explicitly forbids
            # ("never raised to F").
            floor = wr * MIN_UTIL
            if current > 1.01 * floor:
                new_req = max(current - step_af, floor)
            else:
                new_req = current
            self.update_agent_request(aid, new_req)
            state_changes["request"] = new_req
            _set_realised_magnitude(state_changes, action_context, step_af, size_class,
                                    current, new_req)

        elif skill == "maintain_demand":
            # Preserve existing *request* (not diversion which includes
            # curtailment). Using diversion would cause double-curtailment
            # because update_agent_request re-applies the curtailment ratio.
            existing_request = agent["request"]
            self.update_agent_request(aid, existing_request)
            state_changes["request"] = existing_request

        else:
            return ExecutionResult(
                success=False, error=f"Unknown skill: {skill}"
            )

        return ExecutionResult(
            success=True, state_changes=state_changes, action_context=action_context
        )

    # -----------------------------------------------------------------
    # Internal: water signal generation
    # -----------------------------------------------------------------

    def _generate_precipitation(self) -> Dict[str, float]:
        """Winter precipitation (mm) for each of the 9 Upper Basin
        sub-basin state-groups (WY, UT1-3, NM, CO1-3, AZ; spec 1.6,
        L1-03): AZ_UB agents read the "AZ" column. When real CRSS data is
        loaded, returns the current simulation year's row in full.  Falls
        back to the synthetic drying trend, replicated across all 9
        groups, when no real data is available -- this keeps a mock run's
        agent-facing numbers identical across groups (as they always
        were) while giving every consumer the same dict shape either way.
        No longer used to compute natural flow (see
        _natural_flow_for_year); the legacy 7-column mean survives only
        as the drought_index input (advance_year).
        """
        groups = ("WY", "UT1", "UT2", "UT3", "NM", "CO1", "CO2", "CO3", "AZ")
        if self._crss_precip is not None:
            if self._current_year in self._crss_precip.index:
                row = self._crss_precip.loc[self._current_year]
                precip = {g: float(row[g]) for g in groups}
                self._precip_history.append(precip)
                return precip
            # Review P2: real data was loaded but does not reach this year, so
            # the synthetic trend below produces it. Said ONCE per run, naming
            # the year(s) and the span the file actually covers — silently
            # mixing synthetic years into a run labelled "real CRSS
            # projections" is a provenance defect no output artifact records.
            self._precip_synthetic_fallback_years.append(self._current_year)
            if len(self._precip_synthetic_fallback_years) == 1:
                from broker.utils.logging import logger as _logger

                index = self._crss_precip.index
                _logger.warning(
                    "[irrigation_env] real CRSS precipitation is loaded but does "
                    "not cover year %s (file covers %s-%s); this year and any "
                    "later uncovered year use the SYNTHETIC drying trend instead. "
                    "Read self._precip_synthetic_fallback_years for the full list.",
                    self._current_year,
                    min(index) if len(index) else "?",
                    max(index) if len(index) else "?",
                )

        # Synthetic fallback: drying trend matching CRSS winter precip range,
        # the SAME value in every group (a mock run has no per-sub-basin
        # signal to differ by; this reproduces the old single-number
        # behaviour exactly for anything that reads the legacy mean).
        base = self.config.precip_baseline_mm
        trend = -0.2 * self._year_index  # Gradual drying
        noise = self.rng.normal(0, 12)
        value = max(20.0, base + trend + noise)
        precip = {g: value for g in groups}
        self._precip_history.append(precip)
        return precip

    def _storage_to_elevation(self, storage_maf: float) -> float:
        """Convert Lake Mead storage (MAF) to elevation (ft) via the USBR
        2009 area-capacity curve."""
        return float(np.interp(storage_maf, self._STORAGE_MAF, self._ELEVATION_FT))

    def _elevation_to_storage(self, elevation_ft: float) -> float:
        """Convert Lake Mead elevation (ft) to storage (MAF) via the USBR
        2009 area-capacity curve."""
        return float(np.interp(elevation_ft, self._ELEVATION_FT, self._STORAGE_MAF))

    def _natural_flow_for_year(self, year: int) -> float:
        """USBR calendar-year naturalized flow at Lees Ferry (MAF/yr) for
        the historical year this simulation year is mapped to (spec 1.1;
        Hung and Yang 2021, p. 15 of 21: 2019-2046 <- 1988-2015, 2047-2060
        <- 1934-1947). No clamp -- replaces the precipitation-to-flow
        proxy and its [6, 17] MAF clamp (L2 H1, D5). Raises if ``year`` is
        outside the committed 42-row table: there is no meaningful
        fallback for a year the source data does not cover."""
        table = _load_hydrology_table()
        if year not in table:
            raise ValueError(
                f"No USBR natural-flow row for simulation year {year} in "
                f"{HYDROLOGY_V3_PATH} (covers {min(table)}-{max(table)}); "
                "the irrigation v3 hydrology table has no fallback for a "
                "year outside its 42-year range."
            )
        return table[year]["lees_ferry_cy_natural_flow_af"] / 1e6

    def _lb_tributary_for_year(self, year: int) -> float:
        """Lower Basin tributary inflow (MAF/yr), Lees Ferry to below
        Hoover Dam, for this simulation year (spec 1.3, sign-off S1).
        ``config.lb_tributary_source == "usbr_intervening"`` (default)
        reads the hydrology table's own intervening-flow column for the
        mapped historical year (natural, not depleted, intervening flow);
        ``"constant"`` returns ``config.lb_tributary_maf`` unconditionally
        (the CPU sensitivity)."""
        if self.config.lb_tributary_source == "constant":
            return float(self.config.lb_tributary_maf)
        table = _load_hydrology_table()
        if year not in table:
            raise ValueError(
                f"No USBR intervening-flow row for simulation year {year} in "
                f"{HYDROLOGY_V3_PATH} (covers {min(table)}-{max(table)})."
            )
        return table[year]["lees_ferry_to_below_hoover_cy_intervening_af"] / 1e6

    def _calendar_year_for(self, year: int) -> Optional[int]:
        """The historical calendar year ``year`` is mapped to (spec 1.1),
        for log columns (spec 1.7). ``None`` outside the table's range."""
        row = _load_hydrology_table().get(year)
        return row["source_calendar_year"] if row else None

    def _mexico_delivery_maf(self, mead_level: float) -> float:
        """Treaty delivery to Mexico after the Minute 323 / Binational
        Water Scarcity Contingency Plan (BWSCP) reductions keyed to the
        1 January Lake Mead level (PI decision 6, 2026-09-28: adds the
        four 5-ft bands between 1,045 and 1,025 ft the pre-v3 code
        collapsed into one, L2 N2). Review 2026-09-28 (fix 3): each band's
        reduction is the 70 kaf Minute 323 base reduction below 1,045 ft
        (DOI 2022: the 104 kaf total reduction at 1,050-1,045 ft minus its
        34 kaf BWSCP saving = 70 kaf Minute 323 base) plus that band's own
        BWSCP saving (IBWC 2019 Joint Report, Binational Water Scarcity
        Contingency Plan: 76 / 84 / 92 / 101 kaf for 1,045-1,040 /
        1,040-1,035 / 1,035-1,030 / 1,030-1,025 ft), giving 146 / 154 /
        162 / 171 kaf -- replacing the earlier single 158.5 kaf midpoint
        (which was a stand-in pending this derivation, not a quoted
        figure)."""
        cfg = self.config
        if mead_level < 1025:
            return cfg.mexico_treaty_maf - 0.275
        if mead_level < 1030:
            return cfg.mexico_treaty_maf - 0.171
        if mead_level < 1035:
            return cfg.mexico_treaty_maf - 0.162
        if mead_level < 1040:
            return cfg.mexico_treaty_maf - 0.154
        if mead_level < 1045:
            return cfg.mexico_treaty_maf - 0.146
        if mead_level < 1050:
            return cfg.mexico_treaty_maf - 0.104
        if mead_level < 1075:
            return cfg.mexico_treaty_maf - 0.080
        if mead_level < 1090:
            return cfg.mexico_treaty_maf - 0.041
        return cfg.mexico_treaty_maf

    def _mead_evaporation_maf(self, storage_maf: float) -> float:
        """Lake Mead evaporation, scaling with SURFACE AREA (review
        2026-09-28, fix 10 -- a lake evaporates from its surface, not its
        volume, and the two are not proportional for a natural basin):
        ``evaporation_maf`` (0.541 MAF) x A(h) / A(h_2018), where h is the
        elevation for ``storage_maf`` and h_2018 = 1,081.46 ft (the
        ``mead_evap_ref_storage_maf`` reference storage, the WY2018 Mead
        condition), floored at evap_min_frac of that. A(h) is a
        surface-area PROXY: the USBR 2009 curve has no area column, so the
        local slope dStorage/dElevation on its 1-ft grid
        (``_mead_area_proxy_table``) stands in for it -- proportional to
        true surface area for a reasonably smooth basin, and exact where
        it matters most: A(h_2018) / A(h_2018) = 1, so this function still
        returns exactly 0.541 MAF at the calibration point (PI decision 5,
        2026-09-28), the February 2019 24-Month Study's reported WY2018
        Mead evaporation. Replaces the WP1 volume-ratio version
        (storage_maf / mead_evap_ref_storage_maf), which scaled
        evaporation with volume instead of area.

        Re-review 2026-09-29 (LOW 8): the earlier ``min(1.5, frac)`` upper
        cap on the area ratio is dropped -- no source was ever cited for
        1.5x specifically, and near Mead's full pool the real area ratio
        can legitimately exceed it (a wide, shallow reservoir's surface
        area grows faster than its storage near the top); only the floor,
        which exists to keep evaporation from vanishing entirely near the
        dead pool, is sourced (the same shape as the Powell term)."""
        cfg = self.config
        elevation_ft = self._storage_to_elevation(storage_maf)
        elevation_ref_ft = self._storage_to_elevation(cfg.mead_evap_ref_storage_maf)
        area_elev, area_vals = _mead_area_proxy_table()
        area_h = float(np.interp(elevation_ft, area_elev, area_vals))
        area_ref = float(np.interp(elevation_ref_ft, area_elev, area_vals))
        frac = (area_h / area_ref) if area_ref > 0 else 0.0
        return cfg.evaporation_maf * max(cfg.evap_min_frac, frac)

    def _powell_evaporation_maf(self, storage_maf: float) -> float:
        """Lake Powell evaporation: powell_evaporation_maf at full pool,
        scaled by the storage fraction and floored at evap_min_frac (the
        Mead term's shape, expressed on [0, 1])."""
        cfg = self.config
        frac = storage_maf / cfg.powell_capacity_maf
        return cfg.powell_evaporation_maf * max(cfg.evap_min_frac, min(1.0, frac))

    def _basin_request_projected_maf(self, is_upper_basin: bool) -> float:
        """One basin's PROJECTED (carried, pre-decision, water-right-capped)
        request total, in MAF -- the SAME formula ``advance_year`` freezes
        into ``ub_request_projected_maf`` / ``lb_request_projected_maf``
        every year, factored out here (re-review 2026-09-29 round 4, LOW
        1) so nothing else -- test helpers included -- has to re-derive
        it. Two call sites re-deriving this independently, even
        approximately (the earlier test helpers summed plain
        ``request`` with no water-right cap at all), is exactly the kind
        of drift a shared method exists to close off."""
        return sum(
            max(0.0, min(float(a["request"]), float(a["water_right"])))
            for a in self._agents.values()
            if (a["basin"] == "upper_basin") == is_upper_basin
        ) / 1e6

    def _ub_request_projected_by_subbasin_maf(self) -> Dict[Optional[str], float]:
        """The SAME projected, water-right-capped, carried Upper Basin
        request total :meth:`_basin_request_projected_maf` sums in
        aggregate, broken down by sub-basin (WP1b, item 20) -- the
        per-sub-basin input :meth:`_ub_delivery_for_planning` needs in
        ``subbasin`` mode. Keyed by ``supply_group``; ``None`` collects
        any Upper Basin agent with no sub-basin (never a real
        create_profiles_from_data profile -- initialize_from_profiles
        raises for those -- only a synthetic/hand-built one), which
        :meth:`_ub_delivery_for_planning` and :meth:`_settle` both treat
        as its own unconstrained pool (see their docstrings)."""
        out: Dict[Optional[str], float] = {}
        for a in self._agents.values():
            if a["basin"] != "upper_basin":
                continue
            s = a.get("supply_group")
            r = max(0.0, min(float(a["request"]), float(a["water_right"])))
            out[s] = out.get(s, 0.0) + r
        return {k: v / 1e6 for k, v in out.items()}

    def _ub_subbasin_available_maf_for_year(self, year: int) -> Dict[str, float]:
        """A_s(t) for every sub-basin (WP1b, item 20), MAF, for simulation
        year ``year``: the committed per-sub-basin supply table's value
        (``self.config.ub_subbasin_supply_variant``, MEDIUM 4), raising if
        the year is outside its 42-row range (same contract as
        :meth:`_natural_flow_for_year`)."""
        table = _load_ub_subbasin_supply_table(self.config.ub_subbasin_supply_variant)
        row = table.get(year)
        if row is None:
            raise ValueError(
                f"No Upper Basin sub-basin supply row for simulation year {year} in "
                f"{UB_SUBBASIN_SUPPLY_PATH} (covers {min(table)}-{max(table)})."
            )
        return {s: row[f"a_{s}_af"] / 1e6 for s in UB_SUBBASINS}

    def _ub_delivery_for_planning(
        self,
        ub_requested_maf: float,
        nf_net: float,
        *,
        ub_requested_by_subbasin_maf: Optional[Dict[Optional[str], float]] = None,
        ub_available_by_subbasin_maf: Optional[Dict[str, float]] = None,
    ) -> float:
        """Upper Basin PROJECTED delivery, for Powell release planning
        ONLY (re-review 2026-09-29, HIGH A round 3): the same bound
        :meth:`_settle` applies to the ACTUAL delivery, evaluated here at
        frozen planning-time inputs instead of whatever an agent's live
        request happens to be when a particular ``_settle`` call runs.

        WP1b (per-sub-basin Upper Basin supply, spec item 20): in
        ``ub_supply_mode == "subbasin"``, the projected delivery is the
        sum over sub-basins of ``min(that sub-basin's projected requests,
        its own availability A_s)`` -- ``ub_requested_by_subbasin_maf``
        and ``ub_available_by_subbasin_maf`` (both REQUIRED in that mode;
        :meth:`advance_year` always supplies them) -- then the SAME
        basin-wide backstop as ``lees_ferry_pool`` mode: capped at the 5.0
        MAF delivery capacity and non-farm-net natural flow. In
        ``lees_ferry_pool`` mode (the WP1 behaviour, kept for the SI):
        min(requested, the 5.0 MAF delivery capacity, non-farm-net
        natural flow) on the single aggregate ``ub_requested_maf``, as
        before WP1b.

        This is the one seam WP1b touches: nothing else in
        :meth:`_plan_powell_release` needs to know the Upper Basin has
        sub-basins."""
        cfg = self.config
        if cfg.ub_supply_mode == "subbasin":
            if ub_requested_by_subbasin_maf is None or ub_available_by_subbasin_maf is None:
                raise ValueError(
                    "_ub_delivery_for_planning: ub_supply_mode is 'subbasin' "
                    "but ub_requested_by_subbasin_maf / ub_available_by_subbasin_maf "
                    "were not supplied; advance_year always computes both."
                )
            d_u_prebackstop = sum(
                min(ub_requested_by_subbasin_maf.get(s, 0.0), a_s)
                for s, a_s in ub_available_by_subbasin_maf.items()
            )
            # Any Upper Basin agent with no sub-basin (see
            # _ub_request_projected_by_subbasin_maf) is its own
            # unconstrained pool: nothing caps it before the basin-wide
            # backstop below.
            d_u_prebackstop += ub_requested_by_subbasin_maf.get(None, 0.0)
            return min(d_u_prebackstop, cfg.ub_infrastructure_cap_maf, nf_net)
        return min(ub_requested_maf, cfg.ub_infrastructure_cap_maf, nf_net)

    def _plan_powell_release(
        self,
        nf: float,
        s_p: float,
        s_m: float,
        trib: float,
        shortage_volume: float,
        mexico: float,
        ub_requested_maf: float,
        lb_requested_maf: float,
        *,
        ub_requested_by_subbasin_maf: Optional[Dict[Optional[str], float]] = None,
        ub_available_by_subbasin_maf: Optional[Dict[str, float]] = None,
    ) -> float:
        """Plan the year's Powell release ONCE (re-review 2026-09-29, HIGH
        A round 3), from PROJECTED inputs only -- never a live agent
        request. The previous version of the storage-balancing rule
        recomputed the release target inside :meth:`_settle` itself from
        THAT CALL's own actual Upper Basin requests, so a mid-year Upper
        Basin request change moved the release (the reviewer's probe: a
        15 percent Upper Basin raise after ``advance_year`` moved the
        release in 16 of 42 years, by up to 0.237 MAF -- the Lower Basin
        half of this same bug was fixed in the previous round,
        ``lb_request_projected_maf``; this closes the Upper Basin half
        with the matching ``ub_requested_maf``).

        ``nf``, ``s_p``, ``s_m``, ``trib``, ``shortage_volume`` and
        ``mexico`` are already fixed at the 1 January snapshot regardless
        (natural flow for the year, the two storages, the tributary
        series, the declared tier's volume, and the Mexico schedule from
        last year's end-of-year Mead elevation); ``ub_requested_maf`` and
        ``lb_requested_maf`` are the carried, pre-decision request totals
        ``advance_year`` freezes before this year's decisions run.
        ``ub_requested_by_subbasin_maf`` / ``ub_available_by_subbasin_maf``
        (WP1b, item 20) are the same projected Upper Basin request total,
        broken down by sub-basin, and that year's A_s(t) per sub-basin --
        passed straight through to :meth:`_ub_delivery_for_planning`,
        which is the only place that reads them (REQUIRED there in
        ``ub_supply_mode == "subbasin"``; unused in ``lees_ferry_pool``
        mode, where ``ub_requested_maf`` alone still drives the plan).

        Returns the planned release, bounded to
        [``min_powell_release_maf``, ``max_powell_release_maf``] and to
        what the PROJECTED inflow and storage can physically support.
        :meth:`_settle` applies a SECOND, independent physical cap from
        the ACTUAL inflow and storage it is settling (which may
        legitimately differ from the plan -- review fix HIGH A), so a
        planned release the year turns out unable to support never
        creates water; that physical cap is the only thing allowed to
        move the release actually applied."""
        cfg = self.config
        ub_non_farm = min(nf, cfg.ub_non_farm_depletion_maf)
        nf_net = max(0.0, nf - ub_non_farm)
        d_u_plan = self._ub_delivery_for_planning(
            ub_requested_maf, nf_net,
            ub_requested_by_subbasin_maf=ub_requested_by_subbasin_maf,
            ub_available_by_subbasin_maf=ub_available_by_subbasin_maf,
        )
        inflow_plan = nf_net - d_u_plan
        p_usable = max(0.0, s_p - cfg.powell_dead_pool_maf)
        e_p_plan = min(self._powell_evaporation_maf(s_p), p_usable + inflow_plan)
        available_p_plan = max(0.0, inflow_plan + p_usable - e_p_plan)

        non_ag_plan = max(0.0, cfg.lb_non_ag_total_maf - shortage_volume)
        powell_live_cap = cfg.powell_capacity_maf - cfg.powell_dead_pool_maf
        mead_live_cap = cfg.mead_conservation_pool_maf - cfg.mead_dead_pool_maf
        e_m_estimate = self._mead_evaporation_maf(s_m)
        o_projected = lb_requested_maf + non_ag_plan + mexico
        powell_live_position = s_p + inflow_plan - e_p_plan - cfg.powell_dead_pool_maf
        mead_live_position = s_m + trib - e_m_estimate - o_projected - cfg.mead_dead_pool_maf
        if (powell_live_cap + mead_live_cap) > 0:
            balancing_release = (
                mead_live_cap * powell_live_position
                - powell_live_cap * mead_live_position
            ) / (powell_live_cap + mead_live_cap)
        else:
            balancing_release = cfg.min_powell_release_maf
        release_plan = min(max(balancing_release, cfg.min_powell_release_maf),
                            cfg.max_powell_release_maf)
        return min(release_plan, available_p_plan)

    def _settle(
        self,
        snapshot: Dict[str, float],
        requests: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """One year's two-reservoir settlement. PURE: reads only its
        arguments, the agents' basin / request / water_right and the
        config; writes nothing.

        ``snapshot`` is the frozen 1 January state (see advance_year):
        ``powell_storage``, ``mead_storage`` (total storage, MAF),
        ``natural_flow`` (MAF), ``lb_shortage_volume_maf`` (V, the
        declared tier's 2007 ROD shortage volume, MAF), ``mexico`` (MAF),
        ``lb_tributary`` (MAF -- REQUIRED when config.lb_tributary_source
        is "usbr_intervening"; only the "constant" source may omit it,
        review 2026-09-28 fix 8), ``lb_request_projected_maf`` (re-review
        2026-09-29, HIGH 1: the Lower Basin CARRIED request total, frozen
        by advance_year at each agent's then-current, pre-decision request
        -- MEDIUM B: this is the carried request, not last year's actual
        receipt; WP2 resets a carried request to last year's receipt
        before this sum runs, so the two coincide there, but WP1 has no
        such reset -- REQUIRED, always set by advance_year, used only in
        :meth:`_plan_powell_release`, never the actual delivery),
        ``powell_release_planned_maf`` (re-review 2026-09-29, HIGH A round
        3: the Powell release, ALREADY DECIDED by
        :meth:`_plan_powell_release` inside advance_year, from that same
        projected Lower Basin total AND a projected Upper Basin total --
        REQUIRED, always set by advance_year; ``_settle`` itself no longer
        derives any release target, see step P), ``ub_subbasin_available_af``
        (WP1b, item 20: A_s(t) AF for each of the nine ``UB_SUBBASINS`` --
        REQUIRED when ``config.ub_supply_mode == "subbasin"``, always set
        by advance_year then; unused in ``lees_ferry_pool`` mode) and
        ``calendar_year`` (passed through to the return dict for logging
        only). ``requests`` maps agent id to request (AF); default = every
        agent's current request.

        Steps (MAF/yr):

        NF_net  Upper Basin non-farm consumptive use is taken first and
           never curtailed (spec 1.2, PI a): ub_non_farm = min(NF,
           ub_non_farm_depletion_maf) -- the ACTUAL amount consumed,
           never more than NF itself even in an extremely dry year
           (review fix 12); NF_net = NF - ub_non_farm.
        U  Upper Basin (WP1b, item 20). In ``ub_supply_mode ==
           "subbasin"`` (v3 default), each of the nine H&Y sub-basins gets
           its own A_s(t); agent i in sub-basin s with request r_i
           receives d_i = r_i x min(1, A_s(t) / sum over j in s of r_j)
           (memo section 6 step 5) -- shortage shared by request WITHIN a
           sub-basin, sub-basins independent of each other. D_U = sum of
           d_i; if D_U exceeds min(C_UB, NF_net), every d_i is scaled by
           that bound / D_U (the same basin-wide backstop as
           ``lees_ferry_pool`` mode, below, which the recommended
           envelope never actually binds at requests within the rights,
           memo section 5). In ``lees_ferry_pool`` mode (WP1, kept for the
           SI): D_U = min(r_U, C_UB, NF_net), shared pro-rata across all
           Upper Basin agents together. Either way, PI decision 4
           (2026-09-28): the Upper Basin has PRIORITY and is NEVER cut to
           protect Powell's release -- Hung and Yang's CRSS gives the
           Upper Basin "priority access to the water until its
           consumption reaches the sub-basin allowance" (Hung, Son and
           Yang 2022, p. 11). ``gap_reason`` distinguishes which bound
           actually bound
           (review fix 9): ``ub_natural_flow`` when NF_net < C_UB (flow
           is the tighter constraint; the 5.0 MAF capacity never
           mattered), ``ub_capacity`` otherwise.
        P  Lake Powell. Inflow I = NF_net - D_U (D_U is THIS call's ACTUAL
           Upper Basin delivery, from step U above). Evaporation E_P is
           capped at usable storage PLUS THIS INFLOW (review fix 1: not
           the pre-Upper-Basin NF_net -- the old cap let Powell "evaporate"
           water the Upper Basin had already taken, which could push
           storage below the dead pool). Release R = min(planned, I plus
           usable storage minus E_P) -- pass-through at dead pool (review
           fix HIGH A, 2026-09-29 round 3): the release TARGET itself is
           no longer decided here. It was PLANNED ONCE in
           :meth:`_plan_powell_release`, called from advance_year before
           this year's decisions ran, from PROJECTED Upper and Lower Basin
           request totals (not this call's own D_U/r_LB), a
           storage-BALANCING rule (a simplification of the 2007 Interim
           Guidelines' balancing tiers, ROD Section 6) that chooses R so
           Powell's and Mead's end-of-year LIVE-storage fractions are as
           close as possible AFTER that year's projected Lower Basin
           withdrawals, bounded to [min_powell_release_maf,
           max_powell_release_maf] = [7.0, 9.5] MAF (the Lower Elevation
           Balancing Tier's own band, ROD p. 52) and to what the
           PROJECTED inflow/storage can support. The FIRST re-review
           (HIGH 1) froze only the Lower Basin projection and still let
           this call's own ACTUAL Upper Basin delivery move the release
           via inflow_p, so a mid-year Upper Basin request change still
           moved it (the reviewer's probe: 16 of 42 years, up to 0.237
           MAF) -- this round freezes the Upper Basin total too, and
           ``_settle`` now applies ONLY a physical cap here (this call's
           own ACTUAL inflow_p/E_P, which may legitimately differ from the
           plan's projected values), never re-derives the target. If the
           capped release still leaves Powell above its own capacity, the
           excess spills into the release (reaches Mead) -- computed from
           the ACTUAL end storage, so that physical cap may legitimately
           move even though the plan itself does not.
        L  Lake Mead (PI decision 2026-09-28, replacing the pro-rata-
           across-all-Lower-Basin-use rule: the declared shortage volume
           V (2007 ROD Section 2.D.1: 0 / 0.333 / 0.417 / 0.500 MAF by
           tier) is borne ENTIRELY by the 5.0 MAF non-agricultural bucket
           N -- the model's stand-in for CAP and Southern Nevada, the
           Guidelines' actual juniors (ROD Section 2.D, p. 36-37: shortage
           reduces Arizona and Nevada, California stays at 4.4 MAF;
           Colorado River Compact Decree Art. II(B)(3) priority order):
           non_ag = max(0, N - V). The 22 Lower Basin agricultural agents
           are treated as senior mainstem or California entitlement
           holders and are NOT reduced by the declared tier -- a
           simplification disclosed in the docs (a few Arizona fourth-
           priority mainstem contracts in reality share shortages with
           CAP; all 22 are modelled as senior here). They are reduced
           only when Lake Mead cannot physically supply all Lower Basin
           withdrawals, same as everyone else: available A = (S_M -
           S_M,dead) + R + T - E_M; when (r_LB + non_ag + X) > A every
           withdrawal is scaled by phi = A / (r_LB + non_ag + X). New
           storage = S_M + R + T - E_M - phi (r_LB + non_ag + X); storage
           above the conservation pool (review fix 11 -- not the curve's
           full 1,229 ft flood-control endpoint) spills below Hoover
           (logged).

        Evaporation is taken on the 1 January storage and can never draw a
        reservoir below its dead pool. Conservation, checked by the tests:
        dS_P + dS_M = NF - ub_non_farm + T - D_U - E_P - E_M
        - phi (r_LB + non_ag + X) - spill_M.

        Each agent's ``gap_reason`` names the binding limit: Upper Basin
        ``none``, ``ub_subbasin_supply`` (WP1b, ``subbasin`` mode only:
        this agent's OWN sub-basin's A_s(t) bound, the basin-wide backstop
        did not), ``ub_natural_flow`` or ``ub_capacity`` (the basin-wide
        backstop bound -- in ``subbasin`` mode this overrides
        ``ub_subbasin_supply`` for every Upper Basin agent, even one whose
        own sub-basin was not itself short); Lower Basin (agricultural)
        ``none`` or ``lb_mead_availability`` only --
        ``lb_shortage_tier`` no longer occurs for an agricultural agent
        (PI decision 2026-09-28: the declared tier no longer reduces
        their own delivery), and ``ub_powell_release`` no longer occurs
        either (PI decision 4). The declared tier stays visible as
        INFORMATION via ``curtailment_ratio`` (written by
        ``_apply_curtailment`` from this method's ``lb_cut`` output, V/N,
        the share of the non-agricultural bucket the tier removed -- NOT
        a ratio applied to agricultural deliveries).
        """
        cfg = self.config
        if requests is None:
            requests = {aid: a["request"] for aid, a in self._agents.items()}

        ub_ids = [aid for aid, a in self._agents.items() if a["basin"] == "upper_basin"]
        lb_ids = [aid for aid, a in self._agents.items() if a["basin"] != "upper_basin"]
        req = {
            aid: max(0.0, min(float(requests.get(aid, self._agents[aid]["request"])),
                              float(self._agents[aid]["water_right"])))
            for aid in self._agents
        }
        r_ub = sum(req[a] for a in ub_ids) / 1e6
        r_lb = sum(req[a] for a in lb_ids) / 1e6

        nf = snapshot["natural_flow"]
        s_p = snapshot["powell_storage"]
        s_m = snapshot["mead_storage"]
        # Re-review 2026-09-29 (LOW 6): direct index, not .get(..., 0.0) --
        # a missing shortage volume is a real defect in the caller's
        # snapshot, not a legitimate "no shortage" case to guess at.
        shortage_volume = snapshot["lb_shortage_volume_maf"]
        mexico = snapshot["mexico"]
        # Review 2026-09-28 (fix 8): no silent fallback -- the constant is
        # a legitimate substitute only when the config itself says
        # "constant"; a real (usbr_intervening) run's snapshot must carry
        # its own value (advance_year always sets it).
        if "lb_tributary" in snapshot:
            trib = snapshot["lb_tributary"]
        elif cfg.lb_tributary_source == "constant":
            trib = cfg.lb_tributary_maf
        else:
            raise ValueError(
                "_settle: snapshot has no 'lb_tributary' and "
                "config.lb_tributary_source is 'usbr_intervening' -- "
                "refusing to silently substitute the constant fallback "
                "for a real run's missing tributary value. Pass "
                "lb_tributary explicitly (advance_year always does), or "
                "set lb_tributary_source='constant' if a constant is "
                "intended."
            )

        # Upper Basin non-farm consumptive use, taken first (spec 1.2);
        # review fix 12: the ACTUAL amount, never more than NF itself.
        ub_non_farm = min(nf, cfg.ub_non_farm_depletion_maf)
        nf_net = max(0.0, nf - ub_non_farm)

        # --- U: Upper Basin (priority, PI decision 4) ---
        # WP1b (item 20): per-sub-basin supply is the v3 default
        # (ub_supply_mode == "subbasin"); the single Lees Ferry pool (WP1)
        # is kept for the SI (ub_supply_mode == "lees_ferry_pool"). Both
        # branches produce the SAME three things the rest of _settle and
        # the per-agent loop below need: d_u (this call's actual aggregate
        # Upper Basin delivery, MAF -- feeds Powell's inflow exactly as
        # before), ub_ratio_by_agent (each Upper Basin agent's own
        # delivered/request ratio) and ub_reason_by_agent (its gap_reason).
        ub_subbasin_result: Optional[Dict[str, Dict[str, float]]] = None
        if cfg.ub_supply_mode == "subbasin":
            available_af = snapshot.get("ub_subbasin_available_af")
            if available_af is None:
                raise ValueError(
                    "_settle: ub_supply_mode is 'subbasin' but the snapshot "
                    "has no 'ub_subbasin_available_af' -- advance_year "
                    "always sets it; a hand-built snapshot for a "
                    "subbasin-mode call must supply it (see "
                    "_ub_subbasin_available_maf_for_year)."
                )
            missing_s = [s for s in UB_SUBBASINS if s not in available_af]
            if missing_s:
                raise ValueError(
                    f"_settle: ub_subbasin_available_af is missing sub-basin(s) "
                    f"{missing_s}"
                )

            # Group requests by sub-basin (agent.supply_group); an agent
            # with none at all -- never a real create_profiles_from_data
            # profile, initialize_from_profiles raises for those; only a
            # synthetic/hand-built one -- falls into the None bucket, which
            # memo section 6 never describes because it never arises for a
            # real Upper Basin agent: treated as its own pool with no
            # sub-basin cap of its own, bound only by the basin-wide
            # backstop below. This reproduces exactly the pre-WP1b (single
            # pool) delivery such an agent got, since d_u's final min(...,
            # cap, nf_net) is unchanged (irrigation_v3_ub_subbasin_supply
            # memo section 10).
            ids_by_group: Dict[Optional[str], List[str]] = {}
            for aid in ub_ids:
                s_id = self._agents[aid].get("supply_group")
                if s_id is not None and s_id not in UB_SUBBASINS:
                    # A SET supply_group that names no real sub-basin is a
                    # real data-shape defect (a typo, a stale label) --
                    # refuse to silently drop this agent into either a real
                    # sub-basin's bucket or the "no sub-basin" pool (review
                    # fix 8's precip_group precedent, get_agent_context).
                    raise ValueError(
                        f"{aid}: supply_group={s_id!r} is not one of the nine "
                        f"sub-basins ({UB_SUBBASINS}); refusing to silently "
                        "treat it as either a real sub-basin or as having none."
                    )
                ids_by_group.setdefault(s_id, []).append(aid)

            pre_backstop_af: Dict[str, float] = {}
            ub_subbasin_result = {}
            for s in UB_SUBBASINS:
                ids_s = ids_by_group.get(s, [])
                r_s_af = sum(req[aid] for aid in ids_s)
                a_s_af = float(available_af[s])
                ratio_s = 1.0 if r_s_af <= 0 else min(1.0, a_s_af / r_s_af)
                for aid in ids_s:
                    pre_backstop_af[aid] = req[aid] * ratio_s
                ub_subbasin_result[s] = {
                    "available_af": a_s_af,
                    "request_af": r_s_af,
                    "delivered_af": r_s_af * ratio_s,  # backstop-scaled below if it binds
                    "ratio": ratio_s,
                }
            for aid in ids_by_group.get(None, []):
                pre_backstop_af[aid] = req[aid]  # unconstrained pool, see above

            d_u_prebackstop = sum(pre_backstop_af.values()) / 1e6
            d_u = min(d_u_prebackstop, cfg.ub_infrastructure_cap_maf, nf_net)
            backstop_factor = (
                1.0 if d_u_prebackstop <= 0 else min(1.0, d_u / d_u_prebackstop)
            )
            if backstop_factor < 1.0 - 1e-9:
                # Basin-wide backstop bound (memo section 6 step 6): names
                # the same reason WP1's single pool would, for EVERY Upper
                # Basin agent, regardless of its own sub-basin's ratio_s --
                # the memo's own gauge/depletion envelope keeps this from
                # binding at requests within the rights (section 5).
                backstop_reason = (
                    "ub_natural_flow" if nf_net < cfg.ub_infrastructure_cap_maf
                    else "ub_capacity"
                )
            else:
                backstop_reason = None
            for s in UB_SUBBASINS:
                ub_subbasin_result[s]["delivered_af"] *= backstop_factor

            ub_ratio_by_agent: Dict[str, float] = {}
            ub_reason_by_agent: Dict[str, str] = {}
            ub_subbasin_ratio_by_agent: Dict[str, Optional[float]] = {}
            for aid in ub_ids:
                pre = pre_backstop_af.get(aid, 0.0)
                ratio_i = (pre / req[aid] * backstop_factor) if req[aid] > 0 else backstop_factor
                ub_ratio_by_agent[aid] = ratio_i
                s = self._agents[aid].get("supply_group")
                ub_subbasin_ratio_by_agent[aid] = (
                    ub_subbasin_result[s]["ratio"] if s in UB_SUBBASINS else None
                )
                if backstop_reason is not None:
                    ub_reason_by_agent[aid] = backstop_reason
                elif ratio_i < 1.0 - 1e-9:
                    ub_reason_by_agent[aid] = "ub_subbasin_supply"
                else:
                    ub_reason_by_agent[aid] = "none"
        else:
            d_u = min(r_ub, cfg.ub_infrastructure_cap_maf, nf_net)
            if d_u >= r_ub:
                pool_reason = "none"
            elif nf_net < cfg.ub_infrastructure_cap_maf:
                # Review fix 9: natural flow (net of non-farm use), not the
                # 5.0 MAF capacity, is the tighter constraint -- the
                # capacity never bound.
                pool_reason = "ub_natural_flow"
            else:
                pool_reason = "ub_capacity"
            pool_ratio = (d_u / r_ub) if r_ub > 0 else 1.0
            ub_ratio_by_agent = {aid: pool_ratio for aid in ub_ids}
            ub_reason_by_agent = {aid: pool_reason for aid in ub_ids}
            ub_subbasin_ratio_by_agent = {aid: None for aid in ub_ids}
        inflow_p = nf_net - d_u

        # PI decision 2026-09-28: the declared shortage volume V is borne
        # entirely by the non-agricultural bucket; computed here (needs
        # only the ALREADY-frozen shortage_volume, not any per-call
        # request) so the actual Lake Mead settlement further down has it.
        non_ag = max(0.0, cfg.lb_non_ag_total_maf - shortage_volume)

        # --- P: Lake Powell (apply the PRE-PLANNED release) ---
        # Re-review 2026-09-29 (HIGH A round 3): the release target itself
        # is no longer computed here at all -- it was PLANNED ONCE in
        # advance_year (_plan_powell_release), from projected inputs,
        # before this year's decisions ran. The first HIGH-1 fix froze
        # only the Lower Basin side of the projection and left the Upper
        # Basin's actual (live) delivery (d_u, above) feeding into
        # inflow_p, so the release still moved whenever a decision changed
        # an Upper Basin request mid-year (the reviewer's probe: 16 of 42
        # years, up to 0.237 MAF). _settle now applies ONLY the physical
        # cap, from THIS call's own actual inflow_p/e_p (which may
        # legitimately differ from the plan's projected values) -- that
        # physical cap, not the release target, is the only thing allowed
        # to move the release actually delivered.
        p_usable = max(0.0, s_p - cfg.powell_dead_pool_maf)
        # Review fix 1: capped at usable storage plus THIS YEAR'S INFLOW
        # (post-Upper-Basin), not the pre-Upper-Basin nf_net.
        e_p = min(self._powell_evaporation_maf(s_p), p_usable + inflow_p)
        available_p = max(0.0, inflow_p + p_usable - e_p)
        release = min(snapshot["powell_release_planned_maf"], available_p)

        s_p_end = s_p + inflow_p - e_p - release
        # If the bounded release still leaves Powell above its own
        # capacity (a very wet year, or a snapshot already above
        # capacity), the excess spills into the release, reaching Mead.
        powell_spill = max(0.0, s_p_end - cfg.powell_capacity_maf)
        release += powell_spill
        s_p_end -= powell_spill

        # --- L: Lake Mead ---
        m_usable = max(0.0, s_m - cfg.mead_dead_pool_maf)
        e_m = min(self._mead_evaporation_maf(s_m), m_usable + release + trib)
        # non_ag (the 22 agricultural agents are senior and cut only by
        # physical availability) was already computed above, from the
        # ALREADY-frozen shortage_volume -- reused here unchanged, and
        # combined with the REAL (not projected) r_lb, since this is the
        # actual delivery this settlement call is computing, not the
        # release-planning projection.
        outflow = r_lb + non_ag + mexico
        available = max(0.0, m_usable + release + trib - e_m)
        phi = 1.0 if (outflow <= 0 or outflow <= available) else available / outflow
        s_m_end = s_m + release + trib - e_m - phi * outflow
        mead_spill = max(0.0, s_m_end - cfg.mead_conservation_pool_maf)
        s_m_end -= mead_spill

        lb_reason = "lb_mead_availability" if phi < 1.0 else "none"
        # Informational only (the declared tier stays visible without
        # implying it was applied to agricultural deliveries): the share
        # of the non-agricultural bucket the tier removed. Feeds
        # curtailment_ratio (_apply_curtailment) and the
        # supply_gap_block_increase / curtailment_awareness_check
        # governance skip condition (unchanged: nonzero exactly when a
        # tier > 0 is declared).
        g_informational = (
            shortage_volume / cfg.lb_non_ag_total_maf
            if cfg.lb_non_ag_total_maf > 0 else 0.0
        )

        lb_ratio = phi
        agents: Dict[str, Dict[str, Any]] = {}
        for aid in ub_ids:
            agents[aid] = {
                "request": req[aid],
                "delivered": req[aid] * ub_ratio_by_agent[aid],
                "delivery_ratio": ub_ratio_by_agent[aid],
                "gap_reason": ub_reason_by_agent[aid],
                # WP1b (item 20): this agent's own sub-basin ratio_s,
                # BEFORE the basin-wide backstop (None in lees_ferry_pool
                # mode, or for an Upper Basin agent with no sub-basin) --
                # feeds the ub_subbasin_ratio log column and the agent's
                # persistent ub_subbasin_ratio state (_write_agent_deliveries).
                "ub_subbasin_ratio": ub_subbasin_ratio_by_agent[aid],
            }
        for aid in lb_ids:
            agents[aid] = {
                "request": req[aid],
                "delivered": req[aid] * lb_ratio,
                "delivery_ratio": lb_ratio,
                "gap_reason": lb_reason,
            }

        result = {
            "agents": agents,
            "natural_flow_maf": nf,
            "ub_non_farm_maf": ub_non_farm,
            "ub_request_maf": r_ub,
            "ub_delivered_maf": d_u,
            # WP1b (item 20): the per-sub-basin record (available, request,
            # delivered, ratio -- spec 1b.3), None in lees_ferry_pool mode
            # (there is no sub-basin structure to report).
            "ub_subbasin": ub_subbasin_result,
            "lb_request_maf": r_lb,
            "lb_delivered_maf": r_lb * phi,
            "lb_non_ag_delivered_maf": non_ag * phi,
            "mexico_delivered_maf": mexico * phi,
            "lb_cut": g_informational,
            "lb_shortage_volume_maf": shortage_volume,
            "lb_phys_ratio": phi,
            "powell_storage_maf": s_p,
            "powell_storage_end_maf": s_p_end,
            "powell_evap_maf": e_p,
            "powell_release_maf": release,
            "powell_spill_maf": powell_spill,
            "mead_storage_maf": s_m,
            "mead_storage_end_maf": s_m_end,
            "mead_evap_maf": e_m,
            "mead_spill_maf": mead_spill,
            "lb_tributary_maf": trib,
        }
        if snapshot.get("calendar_year") is not None:
            result["calendar_year"] = snapshot["calendar_year"]
        return result

    def _write_agent_deliveries(self, settlement: Dict[str, Any]) -> None:
        """Write a settlement's per-agent delivery onto the agent dicts
        (``diversion`` = delivered, plus ``delivery_ratio``/``gap_reason``).

        WP1b (item 20): also ``ub_subbasin_ratio`` (this agent's own
        sub-basin ratio_s, pre-backstop; ``None`` outside ``subbasin``
        mode or for a Lower Basin / no-sub-basin agent -- see ``_settle``)
        and the derived ``ub_subbasin_sole_bound`` flag (1.0 only when
        this agent is the SOLE member of a sub-basin whose OWN supply,
        not the basin-wide backstop, is what bound -- see
        ``agent_types.yaml (irrigation_farmer.feedback)``'s UT2-specific
        dashboard message, and ``_sharing_sentence`` in
        irrigation_validators.py for the analogous, more precise check
        the governance rule message makes). Both are ``agent_state``
        fields (not settlement fields) because ``run_experiment.py``'s
        feedback-dashboard tracked-metrics loop reads a NAMED field off
        ``env.get_agent_state(aid)``, not off the settlement dict."""
        for aid, rec in settlement["agents"].items():
            agent = self._agents[aid]
            agent["diversion"] = rec["delivered"]
            agent["delivery_ratio"] = rec["delivery_ratio"]
            agent["gap_reason"] = rec["gap_reason"]
            sub_ratio = rec.get("ub_subbasin_ratio")
            agent["ub_subbasin_ratio"] = sub_ratio
            # WP1b re-review (LOW 6, 2026-09-29): sub_ratio is not None only
            # for a real UB agent in a real sub-basin (see _settle), which
            # initialize_from_profiles always gives a computed
            # ub_subbasin_member_count -- a missing one here is a wiring
            # defect, not a legitimate "unknown" case (unlike a Lower Basin
            # or no-sub-basin agent, where sub_ratio is itself None and this
            # flag is simply 0.0, no count needed at all).
            member_count = agent.get("ub_subbasin_member_count")
            if sub_ratio is not None and member_count is None:
                raise ValueError(
                    f"{aid}: ub_subbasin_ratio is set ({sub_ratio}) but "
                    "ub_subbasin_member_count is missing; "
                    "initialize_from_profiles should have computed it for "
                    "every agent with a supply_group (LOW 6, 2026-09-29 "
                    "re-review)."
                )
            agent["ub_subbasin_sole_bound"] = (
                1.0 if (sub_ratio is not None and sub_ratio < 1.0 - 1e-9
                        and member_count <= 1)
                else 0.0
            )

    def settle_year(self) -> Dict[str, Any]:
        """FINAL settlement of the current year at the agents' current
        requests, after every decision has executed.

        Keeps the F11b contract (2026-09-25): it rebuilds every agent's
        delivery from ``request`` and the frozen 1 January snapshot, never
        from ``diversion``, so an agent whose decision did not execute
        (ABORTED, no fallback, inactive) is treated exactly like one that
        executed ``maintain_demand``, and a second call with no decision in
        between is bitwise identical. Storage is NOT committed here; the
        next ``advance_year()`` commits the pending settlement once.

        Call exactly once per year, after the full decision loop and before
        anything logs or snapshots the year's deliveries
        (``IrrigationLifecycleHooks.post_year``). Returns the settlement.
        """
        if self._snapshot is None:
            raise RuntimeError(
                "settle_year() called before the first advance_year(): there "
                "is no 1 January snapshot to settle against."
            )
        settlement = self._settle(self._snapshot)
        settlement["year"] = self._current_year
        self._write_agent_deliveries(settlement)
        # spec 1.5: curtailment_ratio is written from each settlement,
        # provisional (advance_year) then final (here) -- g itself never
        # changes within a year (frozen at the 1 January snapshot), so
        # this re-asserts the same value rather than changing it.
        self._apply_curtailment(settlement["lb_cut"])
        self._pending_settlement = settlement
        return settlement

    def apply_powell_cap_to_executed_diversions(self) -> None:
        """Deprecated alias of :meth:`settle_year` (the F11b name, kept so
        older call sites and tests keep working)."""
        self.settle_year()

    def _commit_settlement(self, settlement: Dict[str, Any], year: Optional[int] = None) -> None:
        """End-of-year storages become the next 1 January storages.

        ``year`` (L2 N4, 2026-09-28) labels the committed record with the
        loop year it actually settles. Without it, ``advance_year`` used
        to call this with ``self._current_year`` already bumped to the
        NEXT loop year, so the committed settlement for year t carried the
        label t+1 -- harmless (no consumer read the mislabeled field) but
        wrong. Left ``None`` (any external caller) keeps that historical,
        mislabeled behaviour rather than guessing a year that may not be
        the caller's intent."""
        if year is not None:
            settlement = dict(settlement)
            settlement["year"] = year
        self._powell_storage = float(settlement["powell_storage_end_maf"])
        self._mead_storage.append(float(settlement["mead_storage_end_maf"]))
        self._settlement_history.append(settlement)
        self._pending_settlement = None

    @property
    def last_settlement(self) -> Optional[Dict[str, Any]]:
        """The current year's final settlement if settle_year() ran this
        year, else the last committed one (None before any)."""
        if self._pending_settlement is not None:
            return self._pending_settlement
        return self._settlement_history[-1] if self._settlement_history else None

    def _update_preceding_factors(self, precip: Dict[str, float], mead_level: float) -> None:
        """Compute binary preceding factors from signal changes.

        Upper Basin (spec 1.6, L1-03): a PER-STATE-GROUP flag,
        ``self._precip_group_flags[g] = int(P_g(t) > P_g(t-1))`` -- H&Y's
        strict ">" (Hung and Yang 2021, code: ``d_f > 0``) -- read by
        ``get_agent_context`` for any agent whose ``precip_group`` is set.
        ``self._basins["upper_basin"]["preceding_factor"]`` keeps the
        LEGACY 7-column-mean, ">=" comparison this field used before v3:
        it is the fallback for an agent with no ``precip_group``
        (synthetic/mock profiles) and what the coupling contract's
        presence check reads (``irrigation_coupling.py``, not touched by
        WP1); nothing else reads it once every real profile carries a
        ``precip_group``. ``precip`` (this year's per-group dict) is not
        itself used below -- as before this change, the comparison reads
        ``self._precip_history``, which ``_generate_precipitation``
        already appended ``precip`` onto.

        Lower Basin: unchanged, 1 January Lake Mead level, ">=".
        """
        if len(self._precip_history) >= 2:
            prev, curr = self._precip_history[-2], self._precip_history[-1]
            self._precip_group_flags = {
                g: int(curr.get(g, 0.0) > prev.get(g, 0.0)) for g in curr
            }
            legacy_cols = ("WY", "UT1", "UT2", "UT3", "CO1", "CO2", "CO3")
            legacy_prev = float(np.mean([prev.get(c, 0.0) for c in legacy_cols]))
            legacy_curr = float(np.mean([curr.get(c, 0.0) for c in legacy_cols]))
            ub_pf = int(legacy_curr >= legacy_prev)
        else:
            curr = self._precip_history[-1] if self._precip_history else {}
            self._precip_group_flags = {g: 0 for g in curr}
            ub_pf = 0
        self._basins["upper_basin"]["preceding_factor"] = ub_pf

        # Lower Basin: Lake Mead level change
        if len(self._mead_history) >= 2:
            lb_pf = int(self._mead_history[-1] >= self._mead_history[-2])
        else:
            lb_pf = 0
        self._basins["lower_basin"]["preceding_factor"] = lb_pf

    def _compute_drought_index(self, precip: float, mead_level: float) -> float:
        """Compute composite drought severity index [0, 1]."""
        # Precipitation component (lower = more drought)
        # Normal precip → 0.0 (not dry), zero precip → 1.0 (max drought)
        precip_norm = max(0.0, min(1.0, 1.0 - precip / self.config.precip_baseline_mm))

        # Lake Mead component (lower level = more drought)
        mead_norm = max(0.0, min(1.0, 1.0 - (mead_level - 900) / 320.0))

        return 0.5 * precip_norm + 0.5 * mead_norm

    def _compute_shortage_tier(self) -> int:
        """Compute Bureau of Reclamation shortage tier from Lake Mead level.

        Returns:
            0 = Normal, 1 = Tier 1, 2 = Tier 2, 3 = Tier 3 (most severe).

        Raises:
            KeyError: when the coupling context contract is active and
                ``lake_mead_level`` is absent. Review P2: the legacy default
                of 1100 ft is above ``mead_shortage_tier1``, so a MISSING
                reservoir level silently produced tier 0 — "no shortage, no
                curtailment" — which is both the most consequential answer
                this function can give and indistinguishable from a real
                healthy reservoir. Under the flag whose whole purpose is to
                refuse manufactured physical state, it must fail instead.
        """
        lower = self._basins["lower_basin"]
        if self._coupling_contract_active and "lake_mead_level" not in lower:
            raise KeyError(
                "lake_mead_level is missing from lower_basin and "
                "coupling.context_contract is ON: refusing to fall back to the "
                "1100 ft default, which would report shortage tier 0 (no "
                "curtailment) for a reservoir whose level was never set."
            )
        mead = lower.get("lake_mead_level", 1100)
        cfg = self.config
        if mead >= cfg.mead_shortage_tier1:
            return 0
        elif mead >= cfg.mead_shortage_tier2:
            return 1
        elif mead >= cfg.mead_shortage_tier3:
            return 2
        else:
            return 3

    @staticmethod
    def _tier_shortage_volume_maf(tier: int) -> float:
        """Lower Basin shortage volume by declared tier (2007 Interim
        Guidelines Record of Decision, Section 2.D.1, p. 36): 0 / 0.333 /
        0.417 / 0.500 MAF for tiers 0-3 (PI decision (f), 2026-09-28;
        replaces the earlier flat 0/5/10/20 percent cuts,
        ``_tier_curtailment_ratio``). PI decision 2026-09-28: borne
        entirely by the 5.0 MAF non-agricultural bucket N (not shared
        pro rata across agricultural use), in ``_settle``: non_ag =
        max(0, N - V).

        Re-review 2026-09-29 (LOW 6): direct index, not ``.get(tier, 0.0)``
        -- ``_compute_shortage_tier`` only ever returns 0-3, so any other
        value reaching here is a real caller defect, not a legitimate
        "no shortage" case to guess at."""
        return {0: 0.0, 1: 0.333, 2: 0.417, 3: 0.500}[tier]

    def _apply_curtailment(self, ratio: Optional[float] = None) -> None:
        """Record the declared shortage's INFORMATIONAL ratio on each
        Lower Basin agent (0 for Upper Basin -- the 2007 Interim
        Guidelines shortage volumes bind Lower Basin users only). PI
        decision 2026-09-28: this ratio is V / N (the share of the 5.0
        MAF non-agricultural bucket the declared tier removed), NOT a
        ratio applied to agricultural deliveries -- agricultural agents
        are reduced only by physical Mead availability (:meth:`_settle`'s
        ``phi``). Kept as an agent-visible signal (e.g. the
        ``supply_gap_block_increase`` / ``curtailment_awareness_check``
        governance skip condition reads it to know a tier is declared)
        without implying it was multiplied into their own delivery.

        ``ratio`` is normally :meth:`_settle`'s own ``lb_cut`` output;
        ``advance_year`` and ``settle_year`` always pass it explicitly.
        Left as ``None`` (a caller with no snapshot -- e.g. a test that
        pokes the 1 January Mead level directly) it is recomputed here
        from the CURRENT declared tier, reproducing the pre-v3
        zero-argument convenience call."""
        if ratio is None:
            tier = self._compute_shortage_tier()
            volume = self._tier_shortage_volume_maf(tier)
            n = self.config.lb_non_ag_total_maf
            ratio = volume / n if n > 0 else 0.0
        for agent in self._agents.values():
            agent["curtailment_ratio"] = (
                0.0 if agent["basin"] == "upper_basin" else ratio
            )

    # -----------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------

    def get_coupling_retrofit_metadata(self) -> Dict[str, Any]:
        """PR-9 coupling-retrofit provenance (F1): reports whether the
        ``coupling.context_contract`` fail-loud guard is active on this
        run's ``get_agent_context()`` physical-state handoff, WHICH CHECK
        each covered field actually got, which returned keys it does NOT
        cover, and how many times the guard actually ran. Read generically
        (by method name only — no irrigation-specific code in broker/) by
        ``ExperimentRunner._collect_reproducibility_metadata`` and merged
        into ``run_integrity.json`` as a side artifact; never touches the
        audit CSV. Distinct from ``EnvironmentCouplingAdapter.get_provenance``
        on purpose: this hook covers the ``coupling.context_contract``
        guard on ``get_agent_context()`` (a per-agent accessor reading
        several source dicts lazily), never the ``coupling.enable`` /
        ``EnvironmentCouplingAdapter`` boundary (the ``advance_step()`` /
        ``execute_skill()`` single-flat-dict model) - the two flags compose
        independently (see ``irrigation_coupling.py``'s module docstring for
        why one guard does not substitute for the other).

        UPDATE (v0.6 coupling-layer wiring, ``examples/irrigation_abm/
        coupling_modules.py``): this environment CAN now also be wrapped in
        ``EnvironmentCouplingAdapter`` (via ``--coupling`` /
        ``global_config.coupling.enable``). When it is, this method is
        still reachable - ``EnvironmentCouplingAdapter.__getattr__``
        forwards ``get_coupling_retrofit_metadata`` to the wrapped real
        engine when the real engine defines it - so a coupled run's
        manifest carries BOTH this method's keys (the context_contract
        guard's own status) AND ``coupling_adapter: True`` /
        ``coupling_provenance`` (the adapter's own hook) side by side,
        truthfully: two independent, simultaneously-active guards, not one
        falsely standing in for the other.

        ``coupling_contract_fields`` is a MAPPING (field -> check kind), not
        a bare list: five of the fifteen fields are bool/str and get a
        presence+type check rather than a range one, and a flat list read as
        though all fifteen were range-guarded (review P1-c).
        ``coupling_guard_calls`` separates intent from evidence - flag true
        with zero calls is a run the guard never touched.

        Review 2026-09-28 (fix 12, "record lb_tributary_source and both
        data sha256 values in the manifest"): ``water_system_*`` keys ride
        along on this SAME hook because it is the one
        ``_collect_reproducibility_metadata`` already reads unconditionally
        (unlike ``get_provenance``, only populated when ``--coupling`` is
        enabled) -- they are general water-system provenance, not part of
        the coupling-retrofit guard this method is otherwise about.
        """
        from examples.irrigation_abm.irrigation_coupling import (
            IRRIGATION_CONTEXT_UNCOVERED_KEYS,
            irrigation_contract_field_checks,
        )
        return {
            "coupling_contract_active": self._coupling_contract_active,
            "coupling_contract_fields": irrigation_contract_field_checks(),
            "coupling_contract_uncovered_keys": list(IRRIGATION_CONTEXT_UNCOVERED_KEYS),
            "coupling_guard_calls": self._coupling_guard_calls,
            "water_system_lb_tributary_source": self.config.lb_tributary_source,
            "water_system_hydrology_v3_sha256": HYDROLOGY_V3_SHA256,
            "water_system_mead_capacity_sha256": MEAD_CAPACITY_SHA256,
        }

    @property
    def current_year(self) -> int:
        return self._current_year

    @property
    def agent_ids(self) -> List[str]:
        return list(self._agents.keys())

    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        return self._agents.get(agent_id, {}).copy()
