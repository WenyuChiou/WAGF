"""Build the irrigation v3 water-system data files (WP1).

Regenerates two committed, checksum-pinned CSVs under
``examples/irrigation_abm/data/``:

1. ``hydrology_v3.csv`` -- USBR calendar-year naturalized flow at Lees
   Ferry (and the Lees-Ferry-to-below-Hoover intervening flow) for the
   1988-2015 / 1934-1947 resampled years, mapped to simulation years
   2019-2060 exactly as Hung and Yang (2021, p. 15 of 21) resample CRSS's
   default hydrology. Source: U.S. Bureau of Reclamation (2022), Colorado
   River Basin natural flow data,
   ``NaturalFlows1906-2020_20221215.xlsx``, sheet
   ``AnnualCYTotalNaturalFlow``, columns "Colorado R At Lees Ferry, AZ"
   and "Colorado River Below Hoover Dam, AZ-NV".
   https://www.usbr.gov/lc/region/g4000/NaturalFlow/current.html
   (retrieved 2026-09-28). The source file is NOT committed to this repo
   (a large USBR download, not framework or paper data); pass its path
   with ``--source-xlsx``. Its sha256 is verified against
   ``SOURCE_XLSX_SHA256`` before any row is read, and the output CSV's
   sha256 is verified against ``HYDROLOGY_V3_SHA256`` after it is
   written -- both raise on mismatch, so a stale or wrong download can
   never silently produce a different table than the one the spec, the
   tests and the paper cite.

2. ``mead_capacity_usbr2009_1ft.csv`` -- USBR Lake Mead Area and Capacity
   Tables (Tighi and Callejo, 2011, 2001/2009 surveys), available storage
   capacity above 895 ft at 1-ft steps from 895 to 1,229 ft. Source:
   https://www.usbr.gov/lc/region/g4000/LM_AreaCapacityTables2009.pdf
   (retrieved 2026-09-28). This table comes from a scanned/typeset PDF,
   not a machine-readable spreadsheet, so it is not re-derived from the
   PDF programmatically here; ``MEAD_CAPACITY_TABLE_KAF`` below is a
   literal transcription, cross-checked against the nine checkpoints
   quoted independently in both
   ``.research/design_specs/irrigation_v3_design_provenance_2026-09-28.md``
   (row E9) and
   ``.ai/irrigation_prerun_audit_2026-09-28/L2_water_system.md`` (Q3):
   950 ft 2,006; 1,000 ft 4,475; 1,025 ft 5,981; 1,050 ft 7,683;
   1,075 ft 9,601; 1,100 ft 11,735; 1,150 ft 16,733; 1,200 ft 23,144;
   1,220 ft 26,177 kaf -- all nine match exactly. Re-run with
   ``--target mead`` to REBUILD the checked-in CSV from
   ``MEAD_CAPACITY_TABLE_KAF`` and OVERWRITE it (this re-derives the file
   from the literal transcription above, then verifies the freshly
   written bytes against ``MEAD_CAPACITY_SHA256`` -- it does not merely
   check the existing file in place), without touching the hydrology
   table.

3. ``ub_subbasin_supply_v3.csv`` / ``ub_subbasin_envelope_v3.csv`` (WP1b,
   item 20) -- Upper Basin supply per sub-basin, replacing the single
   Lees Ferry pool. Formula and gauge table:
   ``.research/design_specs/irrigation_v3_ub_subbasin_supply_2026-09-29.md``
   sections 5-6. ``ub_subbasin_supply_v3.csv`` has 42 rows (sim_year
   2019-2060), ``q_{s}_af`` (USBR calendar-year total natural flow, sheet
   ``AnnualCYTotalNaturalFlow``, summed over the sub-basin's gauges) and
   ``a_{s}_af`` (= ``c_s x q_{s}_af``) for each of the nine sub-basins
   (WY, UT1, UT2, UT3, NM, CO1, CO2, CO3, AZ). ``ub_subbasin_envelope_v3.csv``
   has 9 rows: each sub-basin's gauges, ``c_s`` = max over 1971-2018 of
   recorded depletion / natural flow (H&Y, 2021, p.8-9; source:
   ``CRSS_DB/HistoricalData/UB_historical_annual_depletion.csv``, sha256
   097fc2cbf48529b8f691f0cc76002e84b7ca9140cdf202ef797326d5d1910542,
   passed with ``--crss-db``), its binding and runner-up year, and the
   1971-2018 mean flow (the denominator of the agent-facing sub-basin
   flow-share sentence). Re-run with ``--target ub_supply --source-xlsx
   <path> --crss-db <path to a checkout of the CRSS_DB data release>``.

4. ``ub_subbasin_supply_v3_{rho02,lees_ferry_all,tributary}.csv`` (WP1b
   re-review, MEDIUM 4, spec 1b.6) -- the three CPU-sensitivity variants
   named in the sub-basin memo sections 8 and 11: the recommended
   envelope's own c_s scaled by 1.2 (H&Y's own rho = 0.2 margin), the
   Lees Ferry gauge standing in for every sub-basin's own flow, and a
   per-sub-basin upstream/headwater gauge in place of the recommended
   downstream/confluence set (the memo's own named gauges, MAP_TRIB in
   the session scratchpad's ``ub_subbasin/s3_options.py``, adopted
   exactly as ``UB_SUBBASIN_GAUGES_TRIBUTARY``). Same 42-row shape as
   ``ub_subbasin_supply_v3.csv``, no separate envelope files. Re-run with
   ``--target ub_supply_variants --source-xlsx <path> --crss-db <path>``.
   Selected via ``WaterSystemConfig.ub_subbasin_supply_variant`` at
   runtime ("recommended" default, or "rho_0_2" / "lees_ferry_all" /
   "tributary_gauges"). ``ub_subbasin_variant_means_v3.csv`` (WP1b
   re-review, LOW 1) is generated alongside them: each variant's own
   1971-2018 mean flow, since a variant with a different gauge map needs
   its own mean for the agent-facing sub-basin flow-share sentence, not
   the recommended envelope's.

5. ``lb_priority_split_v3.csv`` (WP1c, item 22; method revised review
   round 2, MEDIUM 4, 2026-09-29) -- Lower Basin priority split. 22 rows,
   one per Lower Basin agricultural agent: ``water_right_af`` (its live
   water right, read by calling ``irrigation_personas.create_profiles_from_data``
   directly -- informational only, no longer used to derive the split),
   ``senior_entitlement_af`` / ``junior_entitlement_af`` (the AGENT'S OWN
   PUBLISHED USBR figures, in whatever basis that listing gives them --
   NOT a share of ``water_right_af``, a separate, unrelated request
   ceiling; 0 junior for the 16 agents H&Y modelled as a single priority
   class, who are not split at all), ``basis`` (diversion or consumptive
   use, as the listing states it), ``priority_classes`` and ``source`` --
   every one hand-entered and cited in ``_LB_PRIORITY_SOURCE_TABLE`` from
   ``.research/design_specs/irrigation_v3_lb_rights_check_2026-09-29.md``
   (itself cross-checked here against the USBR AZ Priority 4 listing's own
   footnotes). A leading ``#`` comment line records the AZ priority-4 total
   (CAP's statutory 1,415,000 AF ceiling, Public Law 108-451 Sec.
   104(c)(1)(A), plus the 164,652 AF on-river ceiling, USBR's "Water
   Priorities Within the State of Arizona") and its source. The build
   function asserts the table's agent ids equal the Lower Basin profiles'
   own ids exactly, raising on any mismatch. Re-run with
   ``--target lb_priority`` (only ``--params-csv`` / ``--crss-db``, both
   defaulted to the in-repo ``ref/`` paths, are needed -- not the large
   USBR workbook the other targets require).

Usage::

    python examples/irrigation_abm/tools/build_v3_data.py --source-xlsx <path> [--target all|hydrology|mead]
    python examples/irrigation_abm/tools/build_v3_data.py --target ub_supply --source-xlsx <path> --crss-db <path>
    python examples/irrigation_abm/tools/build_v3_data.py --target ub_supply_variants --source-xlsx <path> --crss-db <path>
    python examples/irrigation_abm/tools/build_v3_data.py --target lb_priority

Never imported by ``irrigation_env.py`` at runtime -- it is a one-off data
generator; the environment loads the checked-in CSVs directly (see
``_load_hydrology_table`` / ``_load_mead_capacity_table`` there) and
raises if either file's sha256 does not match, independent of whether
this script still runs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
HYDROLOGY_CSV = DATA_DIR / "hydrology_v3.csv"
MEAD_CSV = DATA_DIR / "mead_capacity_usbr2009_1ft.csv"
UB_SUBBASIN_SUPPLY_CSV = DATA_DIR / "ub_subbasin_supply_v3.csv"
UB_SUBBASIN_ENVELOPE_CSV = DATA_DIR / "ub_subbasin_envelope_v3.csv"
# WP1b re-review (MEDIUM 4, spec 1b.6): the three CPU-sensitivity variant
# supply tables (memo sections 8, 11) -- no separate envelope files.
UB_SUBBASIN_SUPPLY_RHO02_CSV = DATA_DIR / "ub_subbasin_supply_v3_rho02.csv"
UB_SUBBASIN_SUPPLY_LEES_FERRY_ALL_CSV = DATA_DIR / "ub_subbasin_supply_v3_lees_ferry_all.csv"
UB_SUBBASIN_SUPPLY_TRIBUTARY_CSV = DATA_DIR / "ub_subbasin_supply_v3_tributary.csv"
# WP1b re-review (LOW 1): each variant's own 1971-2018 mean flow.
UB_SUBBASIN_VARIANT_MEANS_CSV = DATA_DIR / "ub_subbasin_variant_means_v3.csv"

# sha256 of NaturalFlows1906-2020_20221215.xlsx as retrieved 2026-09-28
# (spec irrigation_v3_spec_2026-09-28.md, WP1 item 1.1).
SOURCE_XLSX_SHA256 = "b586fa1aa4e6e82c7ba0a0dc0184f1b3ac5cfb53c30ef14b248127c12d7fc3cd"
# sha256 of the 42-row, 4-column derived table (this script's output),
# LF line endings (spec WP1 acceptance).
HYDROLOGY_V3_SHA256 = "9951f2224334a859a7adbc9d55914e6505bbce38ea0424f26f10f7c8d51a04b5"
# sha256 of the 335-row Mead capacity CSV this script writes.
MEAD_CAPACITY_SHA256 = "7f233bd8149cc9416612991c27ed130c22842e93bbbbdd121d7716d5f8d9c8d6"
# sha256 of the 42-row ub_subbasin_supply_v3.csv / 9-row
# ub_subbasin_envelope_v3.csv this script writes (WP1b, item 20).
UB_SUBBASIN_SUPPLY_SHA256 = "ac0a17639488e4d4e7e4cba6ae876ff4a7930a8e9012b5487e2a920189662d48"
UB_SUBBASIN_ENVELOPE_SHA256 = "7f38c4dbfe5a57dc897ef9c2b7983c504fa71dd7ad86b82799a448848e618ca2"
# WP1b re-review (MEDIUM 4): filled in after the first --target
# ub_supply_variants run below verifies the freshly built bytes (same
# bootstrap procedure as the two sha256 values above).
UB_SUBBASIN_SUPPLY_RHO02_SHA256 = "0e65b6fa6d23e209b5c0c1425f73a2f51218fb2a59d6e7a803a7ee5d37a33048"
UB_SUBBASIN_SUPPLY_LEES_FERRY_ALL_SHA256 = "228099d21019e458241ea1ea216e3f46d33f6563c5a8e644960711db25029589"
UB_SUBBASIN_SUPPLY_TRIBUTARY_SHA256 = "f1b4b2379ba6091ac1667f734ab008d38fd4019320f0c1fdf203d127f954b394"
UB_SUBBASIN_VARIANT_MEANS_SHA256 = "c79ac70bad3db3f9fc22dec572740e0e29d74d67c3c7ac573ffbba86d693f288"
# sha256 of CRSS_DB/HistoricalData/UB_historical_annual_depletion.csv (H&Y's
# own historical Upper Basin depletion series, 1971-2018, kaf, one column
# per sub-basin), as pinned by irrigation_v3_spec_2026-09-28.md item 1b.1
# and the sub-basin memo section 10.
UB_HISTORICAL_DEPLETION_SHA256 = "097fc2cbf48529b8f691f0cc76002e84b7ca9140cdf202ef797326d5d1910542"

# WP1c (irrigation_v3_spec_2026-09-28.md item 22, PI-approved 2026-09-29):
# Lower Basin priority split. Restores Hung and Yang's/CRSS's senior-then-
# junior fill order (ref/RL-ABM-CRSS/ABM_CRSS_coupling.py,
# Calculate_Annual_Div_QL_LB / multi_priority_agts: "fills the senior slot
# up to its upper bound first and sends the rest to the junior slot") for
# the 22 Lower Basin agricultural agents, refining item 14 (all 22 modelled
# as uniformly senior).
LB_PRIORITY_SPLIT_CSV = DATA_DIR / "lb_priority_split_v3.csv"
# Filled in after the first --target lb_priority run verifies the freshly
# built bytes (same bootstrap procedure as every other *_SHA256 constant
# in this module).
LB_PRIORITY_SPLIT_SHA256 = "0b4462d7ea5a3364f433bc84847232d1a42a17e36329e8dbfa2143b6d195d165"

# Arizona's Fourth Priority (USBR, "Water Priorities Within the State of
# Arizona", https://www.usbr.gov/lc/region/g4000/contracts/entitlements/AZpriorities.pdf,
# read in full 2026-09-29) is defined there as TWO coequal components --
# quoted verbatim:
#   (i) "contracts, Secretarial Reservations, Perfected Rights, and other
#       arrangements ... entered into or established subsequent to
#       September 30, 1968 ... (for a total quantity of not to exceed
#       164,652 acre-feet of diversions annually)" -- the on-river
#       (non-CAP) fourth-priority contracts. USBR's
#       Entitlements_AZ_Priority_4.pdf (read in full 2026-09-29) lists them
#       individually (Domestic and Agricultural Section 5 contracts) but
#       states no summary total itself, so the ceiling comes from this
#       definitional document, not a sum of the individual listing (which
#       can be below the ceiling: unused/unallocated capacity, e.g. the
#       "RECOMMENDED SECTION 5 CONTRACT (Not Completed)" rows).
#   (ii) "Contract No. 14-06-W-245 ... between the United States and the
#       Central Arizona Water Conservation District for the delivery of
#       Mainstream Water for the Central Arizona Project" -- CAP. The AZ4
#       listing gives CAP itself no acre-foot figure ("Balance of
#       Arizona's apportionment" -- CAP is legally a RESIDUAL claimant, not
#       a fixed quantity); the number below is the STATUTORY CEILING on
#       CAP's total long-term contract entitlement, Public Law 108-451
#       (Arizona Water Settlements Act of 2004), Sec. 104(c)(1)(A), 118
#       Stat. 3490 (read in full 2026-09-29, congress.gov/108/plaws/
#       publ451/PLAW-108publ451.pdf): "The total amount of entitlements
#       under long-term contracts ... for the delivery of Central Arizona
#       Project water in the State shall not exceed 1,415,000 acre-feet".
# "Entitlements having a fourth-priority as defined in (i) and (ii) herein
# are coequal. Reductions in Entitlements having a fourth priority shall be
# borne by each Entitlement holder in the same proportion as its
# Entitlement" (AZpriorities.pdf) is the legal basis for spec item 22's
# f_g = AZ tier volume / AZ_PRIORITY_4_TOTAL_AF, applied uniformly to CAP
# and to every on-river fourth-priority (or coequal fifth/sixth-priority
# rider) holder alike.
AZ_ON_RIVER_PRIORITY_4_ENTITLEMENT_AF = 164_652.0
AZ_CAP_PRIORITY_4_ENTITLEMENT_AF = 1_415_000.0
# 1,579,652.0 AF.
AZ_PRIORITY_4_TOTAL_AF = AZ_ON_RIVER_PRIORITY_4_ENTITLEMENT_AF + AZ_CAP_PRIORITY_4_ENTITLEMENT_AF

# 2007 Interim Guidelines Record of Decision, Section 2.D.1 (p. 36): the
# ARIZONA share of the Lower Basin declared-shortage volumes (spec item 22;
# WaterSystemConfig._tier_shortage_volume_maf's LB totals are 333/417/500
# kaf, with Nevada bearing 13/17/20 kaf of each -- both already verified in
# .research/design_specs/irrigation_v3_lb_rights_check_2026-09-29.md's
# companion documents).
AZ_LB_TIER_VOLUME_AF = {0: 0.0, 1: 320_000.0, 2: 400_000.0, 3: 480_000.0}

# Hand-entered, per-agent source table (spec item 22's "pinned CSV ... with
# every value cited"): agent_id -> (published entitlement AF, published
# JUNIOR component AF, basis, priority classes, source). Every figure is
# read directly from a primary USBR entitlement listing or a document that
# VERIFIED against one --
# .research/design_specs/irrigation_v3_lb_rights_check_2026-09-29.md's
# per-agent table -- and, for the six fourth-priority-or-junior agents,
# independently cross-checked here against the AZ4 PDF's own footnotes
# (read in full 2026-09-29): MohaveValleyIDD's footnote 6 ("the 41,000
# acre-feet includes 5,940 acre-feet of Priority 1 water ... and 35,060
# acre-feet of priority 4 water"), CibolaValleyIDD's footnote 5 and its
# 7,442.52 AF Priority 4 line (plus 1,500 AF Priority 5 / 2,000 AF Priority
# 6 from Entitlements_AZ_Priority_5_and_6.pdf), GilaMonsterFarms' own line
# ("1,435 (also has a PPR for 780 afy, 6,285 afy of 3rd priority water, and
# 656 afy of 5th priority water)"), CocopahIndRes' own line ("2,026 (also
# has PPR No. 1 for 7,681 afy and U.S. PPR No. 8 for 1,140 afy)"),
# HopiTribe's own line ("4,278 (also has 750 afy of 5th priority water and
# 1,000 afy of 6th priority water)") and NorthBajaLLC's own line ("480",
# no other priority).
#
# WP1c review round 2 (MEDIUM 4, PI instruction "follow H&Y", 2026-09-29):
# the two entitlement figures below are the PUBLISHED USBR figures
# THEMSELVES, in the SAME units and basis the listing gives (diversion or
# consumptive use -- see the ``basis`` column of the built CSV), never
# derived from or scaled by the model's water_right W (min(grid_top, 1.4 x
# peak diversion) -- a modelling proxy for a DIFFERENT purpose, the request
# ceiling, unrelated to which priority class a unit of water falls in).
# H&Y's own coupling code (ABM_CRSS_coupling.py, Calculate_Annual_Div_QL_LB)
# fills each priority slot up to an ABSOLUTE bound (``QL_UpperBounds``),
# not a share of some other ceiling -- this restores that shape exactly.
# Consequence: senior_entitlement_af + junior_entitlement_af does NOT
# generally equal the agent's water_right_af (the published total can sit
# anywhere relative to W -- see the rights-check memo's own W/Ent ratios,
# 0.18 to 8.40x); at runtime (_settle) the split applies ONLY up to
# whichever of the two is reached first as the request grows, capped
# overall by W as always.
#   * The three 100%-junior agents (CibolaValleyIDD, HopiTribe,
#     NorthBajaLLC) have senior_entitlement_af = 0.0 -- their published
#     entitlement is entirely 4th/5th/6th priority, no Priority 1-3
#     component at all.
#   * The three partly-junior agents (MohaveValleyIDD, GilaMonsterFarms,
#     CocopahIndRes) split their OWN published total between a senior
#     component (their Priority 1 and/or 3 lines) and a junior one (their
#     Priority 4, plus 5 and/or 6 where the same contract carries them --
#     LOW 7: the spec words the cut as landing on "junior water", not
#     "priority-4 water specifically", and 5th/6th priority is junior to
#     4th, so it is cut by the SAME f_g here, disclosed in the caveats as
#     a simplification: in reality 5th/6th priority water would likely see
#     zero delivery outright in any shortage, ahead of a 4th-priority cut).
#   * The other 16 agents are NOT split at all -- H&Y's own single-priority
#     agents were never divided into a senior and a junior part, so
#     ``junior_entitlement_af`` is 0.0 for every one of them and
#     ``senior_entitlement_af`` is informational only (the agent's own
#     published entitlement where USBR gives one; ``None`` for
#     PVIDDiversionAG and Bard Unit, whose figure is an undivided shared
#     California Priority block with no individual total) -- IrrigationEnvironment._settle
#     never caps their delivery against this number; the water-right cap
#     upstream is what limits their request, exactly as for every other
#     single-priority agent H&Y modelled.
# Agent ids match ref/CRSS_DB/CRSS_DB/Div_States/LB_discrete_states.csv's
# column headers exactly (irrigation_personas.py: create_profiles_from_data
# reads this same file 1:1 for its 22 Lower Basin agents) -- build_lb_
# priority_split_csv asserts this set equality, raising on any mismatch.
_LB_PRIORITY_SOURCE_TABLE: Dict[str, Tuple[Optional[float], float, str, str, str]] = {
    "PVIDDiversionAG": (
        None, 0.0, "diversion", "CA-1(+3b)",
        "USBR Entitlements_State_of_CA.pdf p.5 (Seven Party Agreement: PVID shares the undivided "
        "3.85 MAF CU Priority 1-3 block with IID/CVWD/Bard Unit, PPR 219,780 AF for 33,604 ac; no "
        "individual total)",
    ),
    "CRIR AZ": (
        662_402.0, 0.0, "diversion", "AZ-1 (PPR)",
        "USBR Entitlements_AZ_Priority_1.pdf p.1, PPR#2",
    ),
    "CRIR CA": (
        56_846.0, 0.0, "diversion", "CA-1 (PPR)",
        "USBR Entitlements_State_of_CA.pdf p.1, PPR#24",
    ),
    "YumaCountyWUA": (
        254_200.0, 0.0, "diversion", "AZ-1 (PPR)",
        "USBR Entitlements_AZ_Priority_1.pdf p.1 / Entitlements_AZ_Priority_3.pdf p.1, PPR#4, 1901",
    ),
    "WelltonMohawkIDD": (
        278_000.0, 0.0, "consumptive_use", "AZ-3",
        "USBR Entitlements_AZ_Priority_3.pdf p.1, 1952",
    ),
    "YumaMesaIDD": (
        141_519.0, 0.0, "consumptive_use", "AZ-3",
        "USBR Entitlements_AZ_Priority_3.pdf p.1 (shares a 250,000 AF CU project)",
    ),
    "Fort Mohave Ind Res AZ": (
        103_535.0, 0.0, "diversion", "AZ-1 (PPR)",
        "USBR Entitlements_AZ_Priority_1.pdf p.1, PPR#3",
    ),
    "YumaIrrDist": (
        67_278.0, 0.0, "consumptive_use", "AZ-3",
        "USBR Entitlements_AZ_Priority_3.pdf p.1 (shares a project)",
    ),
    "Bard Unit": (
        None, 0.0, "diversion", "CA-2",
        "USBR Entitlements_State_of_CA.pdf p.5 (Seven Party Agreement, CA Priority 2 block, "
        "<=25,000 gross ac, PPR#28; no individual acre-feet total)",
    ),
    "NorthGilaValleyIDD": (
        41_203.0, 0.0, "consumptive_use", "AZ-3",
        "USBR Entitlements_AZ_Priority_3.pdf p.1 (shares a project)",
    ),
    "Quechan Res Unit": (
        71_616.0, 0.0, "diversion", "CA-1 (PPR)",
        "USBR Entitlements_State_of_CA.pdf p.1, PPR#23 (CA side of Fort Yuma Reservation)",
    ),
    "UnitBIDD": (
        6_800.0, 0.0, "diversion", "AZ-1 (PPR)",
        "USBR Entitlements_AZ_Priority_1.pdf p.1 / Entitlements_AZ_Priority_3.pdf p.1, PPR#5, 1905",
    ),
    # senior = 5,940 AF Priority 1; junior = 35,060 AF Priority 4 (footnote 6).
    "MohaveValleyIDD": (
        5_940.0, 35_060.0, "diversion", "AZ-1+4",
        "USBR Entitlements_AZ_Priority_4.pdf p.5, Contract 14-06-W-204, footnote 6: 41,000 AF total "
        "= 5,940 AF Priority 1 (senior) + 35,060 AF Priority 4 (junior)",
    ),
    # senior = 0 (no Priority 1-3 component at all); junior = 7,442.52 AF
    # Priority 4 + 1,500 AF Priority 5 + 2,000 AF Priority 6 = 10,942.52 AF.
    "CibolaValleyIDD": (
        0.0, 10_942.52, "diversion", "AZ-4/5/6",
        "USBR Entitlements_AZ_Priority_4.pdf p.4, Contract 2-07-30-W0028 (7,442.52 AF Priority 4) "
        "+ Entitlements_AZ_Priority_5_and_6.pdf p.1 (1,500 AF Priority 5 + 2,000 AF Priority 6, "
        "same contract) = 10,942.52 AF, all junior (no Priority 1-3 component)",
    ),
    "Fort Mohave Ind Res CA": (
        16_720.0, 0.0, "diversion", "CA-1 (PPR)",
        "USBR Entitlements_State_of_CA.pdf p.1, PPR#25",
    ),
    # senior = 780 AF Priority 1 + 6,285 AF Priority 3 = 7,065 AF;
    # junior = 1,435 AF Priority 4 + 656 AF Priority 5 = 2,091 AF.
    "GilaMonsterFarms": (
        7_065.0, 2_091.0, "diversion", "AZ-1/3/4/5",
        "USBR Entitlements_AZ_Priority_4.pdf p.5, Contract 6-07-30-W0337: 9,156 AF total = "
        "780 AF PPR Priority 1 + 6,285 AF Priority 3 (senior, 7,065 AF) + 1,435 AF Priority 4 + "
        "656 AF Priority 5 (junior, 2,091 AF)",
    ),
    # senior = 7,681 AF PPR#1 + 1,140 AF US PPR#8 = 8,821 AF; junior = 2,026
    # AF Priority 4.
    "CocopahIndRes": (
        8_821.0, 2_026.0, "diversion", "AZ-1+4",
        "USBR Entitlements_AZ_Priority_4.pdf p.4, Consolidated Decree: 10,847 AF total = 7,681 AF "
        "PPR#1 + 1,140 AF US PPR#8 (senior, 8,821 AF) + 2,026 AF Priority 4 (junior)",
    ),
    # senior = 0 (no Priority 1-3 component at all); junior = 4,278 AF
    # Priority 4 + 750 AF Priority 5 + 1,000 AF Priority 6 = 6,028 AF.
    "HopiTribe": (
        0.0, 6_028.0, "diversion", "AZ-4/5/6",
        "USBR Entitlements_AZ_Priority_4.pdf p.5, Contract 04-XX-30-W0432 (4,278 AF Priority 4) "
        "+ Entitlements_AZ_Priority_5_and_6.pdf p.1 (750 AF Priority 5 + 1,000 AF Priority 6, same "
        "contract) = 6,028 AF, all junior (no Priority 1-3 component)",
    ),
    "Powers": (
        960.0, 0.0, "diversion", "AZ-1 (PPR)",
        "USBR Entitlements_AZ_Priority_1.pdf p.2, PPR#7, 1915",
    ),
    "FtYumaReservation": (
        6_350.0, 0.0, "diversion", "AZ-1 (PPR)",
        "USBR Entitlements_AZ_Priority_1.pdf p.1, PPR#3a, 1884 (AZ side of Fort Yuma Reservation)",
    ),
    "Chemehuevi Ind Res": (
        11_340.0, 0.0, "diversion", "CA-1 (PPR)",
        "USBR Entitlements_State_of_CA.pdf p.1, PPR#22, 1907",
    ),
    # senior = 0 (no Priority 1-3 component at all); junior = 480 AF
    # Priority 4, its only entitlement line.
    "NorthBajaLLC": (
        0.0, 480.0, "diversion", "AZ-4",
        "USBR Entitlements_AZ_Priority_4.pdf p.5, Contract 04-XX-30-W0433, 2005: 480 AF Priority 4, "
        "no other priority, all junior",
    ),
}
DEFAULT_PARAMS_CSV = Path("ref/RL-ABM-CRSS/ALL_colorado_ABM_params_cal_1108.csv")
DEFAULT_CRSS_DB_DIR = Path("ref/CRSS_DB/CRSS_DB")

LEES_FERRY_COL = "Colorado R At Lees Ferry, AZ"
BELOW_HOOVER_COL = "Colorado River Below Hoover Dam, AZ-NV"
SHEET_NAME = "AnnualCYTotalNaturalFlow"

# irrigation_v3_ub_subbasin_supply_2026-09-29.md section 5: each of Hung
# and Yang's (2021) nine Upper Basin sub-basins and the USGS gauge(s)
# below which every one of its CRSS water-user groups diverts, matched
# against irrigation_personas.py (_UB_STATE_GROUPS, _UB_GROUP_AGENT_COUNTS)
# and H&Y Fig. 2. Order matches _UB_STATE_GROUPS (AZ_UB there == AZ here,
# the same PrismWinterPrecip_ST_NOAA_Future.csv / UB_historical_annual_
# depletion.csv column both already use, via _UB_HIST_COLUMN_BY_GROUP).
UB_SUBBASIN_GAUGES: "OrderedDict[str, List[str]]" = OrderedDict([
    ("WY", ["09234500", "09260000"]),
    ("UT1", ["09315000", "09328500"]),
    ("UT2", ["09315000"]),
    ("UT3", ["09180500", "09379500"]),
    ("NM", ["09379500"]),
    ("CO1", ["09251000", "09260000", "09306500"]),
    ("CO2", ["09180500"]),
    ("CO3", ["09379500", "09180000"]),
    ("AZ", ["09380000"]),
])
UB_SUBBASINS: Tuple[str, ...] = tuple(UB_SUBBASIN_GAUGES)

# c_s fit period: H&Y's own Upper Basin training-data period (p. 9).
UB_SUBBASIN_FIT_START_YEAR = 1971
UB_SUBBASIN_FIT_END_YEAR = 2018

# WP1b re-review (MEDIUM 4, spec 1b.6; gauge map corrected in the third
# re-review round, 2026-09-29): the two gauge-map CPU sensitivities (memo
# sections 8, 11; the third sensitivity, rho = 0.2, reuses
# UB_SUBBASIN_GAUGES with compute_ub_subbasin_envelope's rho parameter, no
# separate gauge map). "lees_ferry_all" is the basin-wide gauge standing
# in for every sub-basin's own flow, named directly in the memo;
# "tributary_gauges" is the memo's OWN named gauge set, MAP_TRIB in the
# session scratchpad's analysis script (``ub_subbasin/s3_options.py``,
# read-only cross-check, never imported) -- not this repo's own choice
# (the memo text says only "the WP1b author lists them", which an earlier
# round of this file read as an open choice; MAP_TRIB was already the
# memo's own answer).
UB_SUBBASIN_GAUGES_LEES_FERRY_ALL: "OrderedDict[str, List[str]]" = OrderedDict(
    (s, ["09380000"]) for s in UB_SUBBASINS
)

# WP1b re-review (2026-09-29, third round): this IS the sub-basin memo's
# own tributary-gauge variant, ``MAP_TRIB`` in the session scratchpad's
# ``ub_subbasin/s3_options.py`` (the memo's own analysis script, read-only
# cross-check, never imported) -- adopted exactly, not this repo's own
# choice. An earlier version of this constant picked a different,
# self-reasoned upstream gauge per sub-basin; recomputed, MAP_TRIB gives
# the memo's own recorded short-sub-basin-year count at 2018 use, 12
# (``s3_results.json``, key ``bTRIB``); the earlier self-reasoned version
# gave 23 and, on inspection, gauged UT3 on the Colorado (it is a San Juan
# and Colorado sub-basin, but its own CRSS groups are on the San Juan) and
# left the Gunnison out of CO2 (whose groups include Grand Junction and
# Cameo, both below the Gunnison confluence).
UB_SUBBASIN_GAUGES_TRIBUTARY: "OrderedDict[str, List[str]]" = OrderedDict([
    # Green R nr Greendale + Little Snake R nr Lily: same as recommended.
    ("WY", ["09234500", "09260000"]),
    # Duchesne R nr Randlett + White R nr Watson + San Rafael R nr Green
    # River: the three named tributaries, not the Green mainstem +
    # San Rafael the recommended gauges sum together.
    ("UT1", ["09302000", "09306500", "09328500"]),
    # Green R at Green River UT: same as recommended (UT2's only gauge).
    ("UT2", ["09315000"]),
    # San Juan R nr Bluff: UT3's own CRSS groups (the Utah anticipated-
    # depletion group and San Juan Utah uses) are on the San Juan, not the
    # Colorado; drops the recommended Colorado R nr Cisco gauge.
    ("UT3", ["09379500"]),
    # San Juan R nr Archuleta: upstream of Bluff, at NM's own group names
    # (Archuleta-to-Farmington etc).
    ("NM", ["09355500"]),
    # Yampa R nr Maybell + Little Snake R nr Lily + White R nr Watson:
    # same as recommended (already headwater gauges).
    ("CO1", ["09251000", "09260000", "09306500"]),
    # Colorado R nr Cameo + Gunnison R nr Grand Junction + Dolores R nr
    # Cisco: CO2's groups (Glenwood Springs, Cameo, Blue Mesa, Crystal,
    # Grand Junction, Dallas Creek, below Cameo, Dolores, San Miguel)
    # include the Gunnison and Dolores tributaries the recommended
    # single Colorado R nr Cisco gauge (below both confluences) omits.
    ("CO2", ["09095500", "09152500", "09180000"]),
    # San Juan R nr Archuleta (upstream of Bluff) + Dolores R nr Cisco:
    # same as recommended.
    ("CO3", ["09355500", "09180000"]),
    # Colorado R at Lees Ferry: same as recommended (AZ Misc Uses sit at
    # Lees Ferry itself).
    ("AZ", ["09380000"]),
])

# sim_year -> source calendar year (H&Y 2021 p. 15 of 21: 2019-2046 repeats
# 1988-2015, 2047-2060 repeats 1934-1947 -- CRSS's own default resample).
YEAR_MAP = {y: 1988 + (y - 2019) for y in range(2019, 2047)}
YEAR_MAP.update({y: 1934 + (y - 2047) for y in range(2047, 2061)})

# USBR Lake Mead Area and Capacity Tables (Tighi and Callejo, 2011):
# available capacity above 895 ft (kaf), 1-ft steps, 895-1229 ft. Literal
# transcription -- see the module docstring for the cross-check.
MEAD_CAPACITY_TABLE_KAF = {
    895: 0, 896: 30, 897: 61, 898: 91, 899: 122, 900: 153, 901: 185,
    902: 216, 903: 248, 904: 280, 905: 312, 906: 345, 907: 377, 908: 410,
    909: 443, 910: 477, 911: 511, 912: 544, 913: 579, 914: 613, 915: 648,
    916: 683, 917: 718, 918: 753, 919: 789, 920: 824, 921: 860, 922: 897,
    923: 933, 924: 970, 925: 1007, 926: 1044, 927: 1081, 928: 1119,
    929: 1157, 930: 1195, 931: 1233, 932: 1272, 933: 1311, 934: 1350,
    935: 1389, 936: 1428, 937: 1468, 938: 1508, 939: 1548, 940: 1589,
    941: 1629, 942: 1670, 943: 1711, 944: 1753, 945: 1794, 946: 1836,
    947: 1878, 948: 1920, 949: 1963, 950: 2006, 951: 2049, 952: 2092,
    953: 2135, 954: 2179, 955: 2223, 956: 2267, 957: 2312, 958: 2357,
    959: 2402, 960: 2447, 961: 2493, 962: 2539, 963: 2585, 964: 2631,
    965: 2678, 966: 2724, 967: 2771, 968: 2819, 969: 2866, 970: 2914,
    971: 2962, 972: 3010, 973: 3059, 974: 3107, 975: 3156, 976: 3206,
    977: 3255, 978: 3305, 979: 3355, 980: 3406, 981: 3456, 982: 3507,
    983: 3559, 984: 3610, 985: 3662, 986: 3714, 987: 3767, 988: 3819,
    989: 3872, 990: 3926, 991: 3980, 992: 4033, 993: 4088, 994: 4142,
    995: 4197, 996: 4252, 997: 4307, 998: 4363, 999: 4419, 1000: 4475,
    1001: 4532, 1002: 4589, 1003: 4646, 1004: 4703, 1005: 4761, 1006: 4819,
    1007: 4878, 1008: 4936, 1009: 4995, 1010: 5055, 1011: 5114, 1012: 5174,
    1013: 5234, 1014: 5295, 1015: 5356, 1016: 5417, 1017: 5478, 1018: 5540,
    1019: 5602, 1020: 5665, 1021: 5727, 1022: 5790, 1023: 5854, 1024: 5917,
    1025: 5981, 1026: 6045, 1027: 6110, 1028: 6175, 1029: 6240, 1030: 6305,
    1031: 6371, 1032: 6437, 1033: 6504, 1034: 6570, 1035: 6638, 1036: 6705,
    1037: 6773, 1038: 6841, 1039: 6909, 1040: 6978, 1041: 7047, 1042: 7116,
    1043: 7186, 1044: 7256, 1045: 7326, 1046: 7397, 1047: 7468, 1048: 7539,
    1049: 7611, 1050: 7683, 1051: 7755, 1052: 7828, 1053: 7901, 1054: 7975,
    1055: 8048, 1056: 8123, 1057: 8197, 1058: 8272, 1059: 8347, 1060: 8423,
    1061: 8499, 1062: 8575, 1063: 8652, 1064: 8729, 1065: 8807, 1066: 8885,
    1067: 8963, 1068: 9041, 1069: 9120, 1070: 9200, 1071: 9279, 1072: 9359,
    1073: 9439, 1074: 9520, 1075: 9601, 1076: 9682, 1077: 9764, 1078: 9846,
    1079: 9928, 1080: 10011, 1081: 10094, 1082: 10177, 1083: 10261,
    1084: 10345, 1085: 10430, 1086: 10514, 1087: 10600, 1088: 10685,
    1089: 10771, 1090: 10857, 1091: 10944, 1092: 11030, 1093: 11118,
    1094: 11205, 1095: 11293, 1096: 11381, 1097: 11469, 1098: 11557,
    1099: 11646, 1100: 11735, 1101: 11825, 1102: 11914, 1103: 12005,
    1104: 12095, 1105: 12186, 1106: 12277, 1107: 12369, 1108: 12461,
    1109: 12554, 1110: 12647, 1111: 12741, 1112: 12835, 1113: 12929,
    1114: 13024, 1115: 13119, 1116: 13215, 1117: 13311, 1118: 13408,
    1119: 13504, 1120: 13601, 1121: 13699, 1122: 13797, 1123: 13895,
    1124: 13993, 1125: 14092, 1126: 14192, 1127: 14292, 1128: 14392,
    1129: 14493, 1130: 14594, 1131: 14696, 1132: 14798, 1133: 14901,
    1134: 15004, 1135: 15107, 1136: 15211, 1137: 15316, 1138: 15422,
    1139: 15529, 1140: 15635, 1141: 15743, 1142: 15851, 1143: 15959,
    1144: 16068, 1145: 16178, 1146: 16288, 1147: 16398, 1148: 16509,
    1149: 16621, 1150: 16733, 1151: 16845, 1152: 16959, 1153: 17072,
    1154: 17187, 1155: 17302, 1156: 17417, 1157: 17533, 1158: 17649,
    1159: 17766, 1160: 17884, 1161: 18002, 1162: 18121, 1163: 18241,
    1164: 18361, 1165: 18482, 1166: 18603, 1167: 18725, 1168: 18848,
    1169: 18971, 1170: 19096, 1171: 19221, 1172: 19346, 1173: 19473,
    1174: 19600, 1175: 19728, 1176: 19857, 1177: 19986, 1178: 20117,
    1179: 20247, 1180: 20379, 1181: 20511, 1182: 20644, 1183: 20777,
    1184: 20911, 1185: 21046, 1186: 21181, 1187: 21317, 1188: 21453,
    1189: 21591, 1190: 21728, 1191: 21867, 1192: 22006, 1193: 22146,
    1194: 22287, 1195: 22428, 1196: 22570, 1197: 22712, 1198: 22855,
    1199: 22999, 1200: 23144, 1201: 23289, 1202: 23435, 1203: 23581,
    1204: 23729, 1205: 23877, 1206: 24026, 1207: 24175, 1208: 24326,
    1209: 24477, 1210: 24628, 1211: 24781, 1212: 24934, 1213: 25087,
    1214: 25241, 1215: 25396, 1216: 25551, 1217: 25707, 1218: 25863,
    1219: 26020, 1220: 26177, 1221: 26335, 1222: 26494, 1223: 26653,
    1224: 26813, 1225: 26973, 1226: 27134, 1227: 27296, 1228: 27458,
    1229: 27620,
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_hydrology_csv(source_xlsx: Path) -> bytes:
    """Read the USBR natural-flow workbook and return the 43-line (header
    + 42 rows) hydrology_v3.csv content as bytes (LF endings)."""
    import pandas as pd  # local import: this tool is not on the runtime path

    xlsx_bytes = source_xlsx.read_bytes()
    actual = _sha256_bytes(xlsx_bytes)
    if actual != SOURCE_XLSX_SHA256:
        raise ValueError(
            f"{source_xlsx} sha256 {actual} does not match the expected "
            f"{SOURCE_XLSX_SHA256} (NaturalFlows1906-2020_20221215.xlsx as "
            "retrieved 2026-09-28); refusing to build the hydrology table "
            "from an unverified or different source file."
        )

    xl = pd.ExcelFile(source_xlsx)
    raw = xl.parse(SHEET_NAME, header=None)
    names = raw.iloc[3, 3:].tolist()
    body = raw.iloc[6:, 2:].copy()
    body.columns = ["year"] + names
    body = body[pd.to_numeric(body["year"], errors="coerce").notna()]
    body["year"] = body["year"].astype(int)
    body = body.set_index("year").apply(pd.to_numeric, errors="coerce")

    buf = io.StringIO()
    buf.write(
        "sim_year,source_calendar_year,lees_ferry_cy_natural_flow_af,"
        "lees_ferry_to_below_hoover_cy_intervening_af\n"
    )
    for sim_year in range(2019, 2061):
        cal_year = YEAR_MAP[sim_year]
        if cal_year not in body.index:
            raise ValueError(
                f"{source_xlsx} sheet {SHEET_NAME!r} has no row for calendar "
                f"year {cal_year} (mapped from sim year {sim_year})."
            )
        lf = int(round(body.loc[cal_year, LEES_FERRY_COL]))
        hoover = int(round(body.loc[cal_year, BELOW_HOOVER_COL]))
        buf.write(f"{sim_year},{cal_year},{lf},{hoover - lf}\n")
    return buf.getvalue().encode("utf-8")


def _norm_gauge(value: Any) -> str:
    """A USGS gauge number as an 8-digit, zero-padded string, whether the
    workbook's gauge-number row (spec 1b.2) came through openpyxl/pandas as
    text (``"09234500"``) or a number (``9234500.0``)."""
    if isinstance(value, str):
        s = value.strip()
    else:
        s = str(int(value))
    return s.zfill(8)


def _read_natural_flow_by_gauge(source_xlsx: Path):
    """``AnnualCYTotalNaturalFlow`` sheet (spec 1b.2), indexed by calendar
    year, one column per USGS gauge number. Same sha256-checked workbook
    and row/column layout as :func:`build_hydrology_csv` (name row 4, data
    from row 7, year in column 3) but keyed by the GAUGE NUMBER row (row 3)
    instead of the site-name row: the sub-basin memo's gauge table
    (section 5) is written in gauge numbers, the stable, unique key -- two
    site names in the workbook are not guaranteed unique or stable."""
    import pandas as pd  # local import: this tool is not on the runtime path

    xlsx_bytes = source_xlsx.read_bytes()
    actual = _sha256_bytes(xlsx_bytes)
    if actual != SOURCE_XLSX_SHA256:
        raise ValueError(
            f"{source_xlsx} sha256 {actual} does not match the expected "
            f"{SOURCE_XLSX_SHA256} (NaturalFlows1906-2020_20221215.xlsx); "
            "refusing to build the sub-basin supply table from an "
            "unverified or different source file."
        )

    xl = pd.ExcelFile(source_xlsx)
    raw = xl.parse(SHEET_NAME, header=None)
    # The sheet has one blank spacer column with no gauge number (between
    # the Lees Ferry and Paria columns -- the Upper/Lower Basin reach
    # boundary); skip it rather than fail normalising a NaN gauge id.
    raw_gauges = raw.iloc[2, 3:].tolist()
    keep_cols = [i for i, g in enumerate(raw_gauges) if pd.notna(g)]
    gauges = [_norm_gauge(raw_gauges[i]) for i in keep_cols]
    body = raw.iloc[6:, [2] + [3 + i for i in keep_cols]].copy()
    body.columns = ["year"] + gauges
    body = body[pd.to_numeric(body["year"], errors="coerce").notna()]
    body["year"] = body["year"].astype(int)
    body = body.set_index("year").apply(pd.to_numeric, errors="coerce")
    return body


def _read_ub_historical_depletion(crss_db_dir: Path):
    """``HistoricalData/UB_historical_annual_depletion.csv`` (kaf,
    1971-2018, one column per sub-basin: WY, UT1, UT2, UT3, NM, CO1, CO2,
    CO3, AZ -- the same nine labels as ``UB_SUBBASINS``), sha256-checked
    (spec 1b.1)."""
    import pandas as pd

    path = crss_db_dir / "HistoricalData" / "UB_historical_annual_depletion.csv"
    if not path.is_file():
        raise ValueError(
            f"{path} not found; --crss-db must point at a directory "
            "containing HistoricalData/UB_historical_annual_depletion.csv "
            "(H&Y's CRSS_DB data release)."
        )
    raw_bytes = path.read_bytes()
    actual = _sha256_bytes(raw_bytes)
    if actual != UB_HISTORICAL_DEPLETION_SHA256:
        raise ValueError(
            f"{path} sha256 {actual} does not match the expected "
            f"{UB_HISTORICAL_DEPLETION_SHA256} (UB_historical_annual_depletion.csv); "
            "refusing to compute sub-basin envelope constants from an "
            "unverified or different depletion file."
        )
    df = pd.read_csv(path, index_col=0)
    missing = [s for s in UB_SUBBASINS if s not in df.columns]
    if missing:
        raise ValueError(f"{path} has no column(s) {missing} (expected {UB_SUBBASINS}).")
    return df


def _subbasin_flow_af(
    flow_by_gauge, subbasin: str, year: int,
    gauge_map: Optional[Dict[str, List[str]]] = None,
) -> float:
    """Q_s(year) = sum over the sub-basin's gauges of USBR calendar-year
    total natural flow (memo section 6, step 1), AF.

    ``gauge_map`` (WP1b re-review, MEDIUM 4, spec 1b.6) overrides
    ``UB_SUBBASIN_GAUGES`` -- the CPU-sensitivity variants (rho aside) swap
    in a different gauge assignment, never a different formula."""
    gauges = (gauge_map or UB_SUBBASIN_GAUGES)[subbasin]
    missing = [g for g in gauges if g not in flow_by_gauge.columns]
    if missing:
        raise ValueError(
            f"AnnualCYTotalNaturalFlow has no column for gauge(s) {missing} "
            f"(sub-basin {subbasin!r}); update the gauge map or check "
            "the workbook's gauge-number row."
        )
    if year not in flow_by_gauge.index:
        raise ValueError(f"AnnualCYTotalNaturalFlow has no row for calendar year {year}.")
    return float(flow_by_gauge.loc[year, gauges].sum())


def compute_ub_subbasin_envelope(
    source_xlsx: Path, crss_db_dir: Path, *,
    gauge_map: Optional[Dict[str, List[str]]] = None,
    rho: float = 0.0,
) -> Tuple[Dict[str, Dict[str, Any]], Any]:
    """Sub-basin memo sections 5-6: c_s (and its binding/runner-up year)
    and the 1971-2018 mean flow, for each of the nine sub-basins.

    c_s = max over 1971-2018 of recorded depletion D_s(y) / natural flow
    Q_s(y) -- derived, not tuned (memo section 6 step 3), THEN scaled by
    ``1 + rho`` (default rho = 0, no margin; WP1b re-review, MEDIUM 4, spec
    1b.6: rho = 0.2 is H&Y's own envelope margin, memo sections 8 and 11).
    ``gauge_map`` overrides which gauges each sub-basin's Q_s sums over
    (default: the recommended ``UB_SUBBASIN_GAUGES``) -- the
    "lees_ferry_all" and "tributary_gauges" CPU sensitivities. Returns
    ``({subbasin: {"c_s", "binding_year", "runner_up_year",
    "runner_up_c_s", "q_mean_1971_2018_af"}}, flow_by_gauge)``; the second
    element is returned too so :func:`build_ub_subbasin_supply_csv` does
    not re-read and re-verify the workbook a second time.
    """
    gauge_map = gauge_map or UB_SUBBASIN_GAUGES
    flow_by_gauge = _read_natural_flow_by_gauge(source_xlsx)
    depletion = _read_ub_historical_depletion(crss_db_dir)

    years = range(UB_SUBBASIN_FIT_START_YEAR, UB_SUBBASIN_FIT_END_YEAR + 1)
    envelope: Dict[str, Dict[str, Any]] = {}
    for s in UB_SUBBASINS:
        ratios: Dict[int, float] = {}
        flows: Dict[int, float] = {}
        for y in years:
            q_y = _subbasin_flow_af(flow_by_gauge, s, y, gauge_map=gauge_map)
            flows[y] = q_y
            if y not in depletion.index:
                raise ValueError(f"UB_historical_annual_depletion.csv has no row for {y}.")
            d_y = 1000.0 * float(depletion.loc[y, s])
            if q_y <= 0:
                raise ValueError(f"Sub-basin {s} has non-positive flow {q_y} AF in {y}.")
            ratios[y] = d_y / q_y
        ranked = sorted(ratios.items(), key=lambda kv: kv[1], reverse=True)
        binding_year, c_s_base = ranked[0]
        runner_up_year, runner_up_c_s = ranked[1]
        envelope[s] = {
            "c_s": c_s_base * (1.0 + rho),
            "binding_year": binding_year,
            "runner_up_year": runner_up_year,
            "runner_up_c_s": runner_up_c_s,
            "q_mean_1971_2018_af": sum(flows.values()) / len(flows),
        }
    return envelope, flow_by_gauge


def build_ub_subbasin_supply_csv(
    source_xlsx: Path, crss_db_dir: Path, *,
    gauge_map: Optional[Dict[str, List[str]]] = None,
    rho: float = 0.0,
) -> bytes:
    """``ub_subbasin_supply_v3.csv`` (spec 1b.1/1b.2): 42 rows, sim_year
    2019-2060, Q_s(m(t)) and A_s(t) = c_s x Q_s(m(t)) for each of the nine
    sub-basins, whole AF, LF endings. ``gauge_map`` / ``rho`` (MEDIUM 4)
    select a CPU-sensitivity variant; the recommended table is the
    ``gauge_map=None, rho=0.0`` default."""
    envelope, flow_by_gauge = compute_ub_subbasin_envelope(
        source_xlsx, crss_db_dir, gauge_map=gauge_map, rho=rho
    )

    header = ["sim_year", "source_calendar_year"]
    for s in UB_SUBBASINS:
        header += [f"q_{s}_af", f"a_{s}_af"]
    buf = io.StringIO()
    buf.write(",".join(header) + "\n")
    for sim_year in range(2019, 2061):
        cal_year = YEAR_MAP[sim_year]
        row = [str(sim_year), str(cal_year)]
        for s in UB_SUBBASINS:
            q_af = _subbasin_flow_af(flow_by_gauge, s, cal_year, gauge_map=gauge_map)
            a_af = envelope[s]["c_s"] * q_af
            row += [str(int(round(q_af))), str(int(round(a_af)))]
        buf.write(",".join(row) + "\n")
    return buf.getvalue().encode("utf-8")


def build_ub_subbasin_envelope_csv(source_xlsx: Path, crss_db_dir: Path) -> bytes:
    """``ub_subbasin_envelope_v3.csv`` (spec 1b.1): 9 rows, one per
    sub-basin -- its gauges, c_s and the year it binds in (plus the
    runner-up year and c_s, memo section 11's reproducibility note), and
    the 1971-2018 mean flow (the denominator of the agent-facing sub-basin
    flow-share sentence, memo section 9)."""
    envelope, _ = compute_ub_subbasin_envelope(source_xlsx, crss_db_dir)
    buf = io.StringIO()
    buf.write(
        "subbasin,gauges,c_s,binding_year,runner_up_year,runner_up_c_s,"
        "q_s_mean_1971_2018_af\n"
    )
    for s in UB_SUBBASINS:
        gauges = "+".join(UB_SUBBASIN_GAUGES[s])
        e = envelope[s]
        buf.write(
            f"{s},{gauges},{e['c_s']:.5f},{e['binding_year']},"
            f"{e['runner_up_year']},{e['runner_up_c_s']:.5f},"
            f"{e['q_mean_1971_2018_af']:.2f}\n"
        )
    return buf.getvalue().encode("utf-8")


# WP1b re-review (LOW 1, 2026-09-29, third round): the variant name ->
# gauge map (None = the recommended UB_SUBBASIN_GAUGES) every non-rho
# variant needs its OWN 1971-2018 mean flow for -- "rho_0_2" reuses the
# recommended gauges (only c_s is scaled), so its mean is identical to
# "recommended"'s and is included only so the loader needs no special
# case, not because the two could differ.
UB_SUBBASIN_SUPPLY_VARIANT_GAUGE_MAPS: Dict[str, Optional[Dict[str, List[str]]]] = {
    "recommended": None,
    "rho_0_2": None,
    "lees_ferry_all": UB_SUBBASIN_GAUGES_LEES_FERRY_ALL,
    "tributary_gauges": UB_SUBBASIN_GAUGES_TRIBUTARY,
}


def build_ub_subbasin_variant_means_csv(source_xlsx: Path, crss_db_dir: Path) -> bytes:
    """``ub_subbasin_variant_means_v3.csv`` (WP1b re-review, LOW 1): one
    row per ``ub_subbasin_supply_variant`` value, the SAME 1971-2018 mean
    flow ``compute_ub_subbasin_envelope`` already computes per sub-basin,
    for that variant's own gauge map.

    Without this, ``IrrigationEnvironment.get_agent_context`` divided a
    variant table's flow (say, "lees_ferry_all"'s Lees Ferry gauge) by the
    RECOMMENDED envelope's mean (each sub-basin's own downstream gauge) --
    two different physical quantities -- so the agent-facing sub-basin
    flow-share sentence was comparing apples to oranges for any variant
    whose gauge map differs from the recommended one. "recommended" and
    "rho_0_2" share the recommended gauges (rho only scales c_s), so their
    rows are identical; "lees_ferry_all" and "tributary_gauges" genuinely
    differ.
    """
    buf = io.StringIO()
    header = ["variant"] + [f"q_{s}_mean_af" for s in UB_SUBBASINS]
    buf.write(",".join(header) + "\n")
    for variant, gauge_map in UB_SUBBASIN_SUPPLY_VARIANT_GAUGE_MAPS.items():
        envelope, _ = compute_ub_subbasin_envelope(source_xlsx, crss_db_dir, gauge_map=gauge_map)
        row = [variant] + [f"{envelope[s]['q_mean_1971_2018_af']:.2f}" for s in UB_SUBBASINS]
        buf.write(",".join(row) + "\n")
    return buf.getvalue().encode("utf-8")


def build_mead_capacity_csv() -> bytes:
    """Return the 336-line (header + 335 rows) mead_capacity_usbr2009_1ft.csv
    content as bytes (LF endings), converting the literal kaf table above
    to whole acre-feet."""
    buf = io.StringIO()
    buf.write("elevation_ft,available_capacity_above_895ft_af\n")
    for ft in range(895, 1230):
        buf.write(f"{ft},{MEAD_CAPACITY_TABLE_KAF[ft] * 1000}\n")
    return buf.getvalue().encode("utf-8")


def build_lb_priority_split_csv(
    params_csv: Path = DEFAULT_PARAMS_CSV,
    crss_db_dir: Path = DEFAULT_CRSS_DB_DIR,
    *,
    paper_water_margin: float = 0.4,
    cluster_method: str = "hy2021",
) -> bytes:
    """``lb_priority_split_v3.csv`` (spec item 22): for each of the 22
    Lower Basin agricultural agents, its senior and junior entitlement
    (AF) and the basis (diversion or consumptive use) that figure is
    published in.

    WP1c review round 2 (MEDIUM 4, PI instruction "follow H&Y",
    2026-09-29): ``senior_entitlement_af`` / ``junior_entitlement_af`` are
    the ABSOLUTE, PUBLISHED USBR figures themselves (``_LB_PRIORITY_SOURCE_TABLE``,
    hand-entered and cited), NEVER derived from or scaled by the agent's
    ``water_right`` (the SEPARATE ``min(grid_top_af, (1 + paper_water_margin)
    * peak_obs_af)`` value -- a modelling proxy for the request ceiling,
    unrelated to which priority class a unit of water falls in; round 1's
    "senior_entitlement_af = (1 - junior_share) * water_right_af" coupled
    the two together, so a paper_water_margin change alone would have
    silently moved the priority split -- MEDIUM 5). H&Y's own coupling
    code fills each priority slot up to an ABSOLUTE bound (``QL_UpperBounds``
    in ``ABM_CRSS_coupling.py``), not a share of some other quantity, and
    this restores that shape. ``water_right_af`` is still read here (by
    calling ``create_profiles_from_data`` directly, never re-derived) and
    written to the CSV for information and for the agent-id equality check
    below, but no longer used to compute the split. For the 16 agents H&Y
    modelled as a single priority class, ``junior_entitlement_af`` is 0.0
    and ``senior_entitlement_af`` is informational only (the agent's own
    published figure where one exists; blank for the two agents -- PVID,
    Bard -- whose figure is an undivided shared California block); at
    runtime (``irrigation_env.py._settle``) neither is used as a cap for
    those 16 -- the water-right cap alone still limits their request, as
    for every H&Y single-priority agent.

    Agent ids in ``_LB_PRIORITY_SOURCE_TABLE`` must equal the Lower Basin
    profiles' own agent ids exactly (both read
    ``ref/CRSS_DB/CRSS_DB/Div_States/LB_discrete_states.csv``'s column
    list, one directly and one via ``create_profiles_from_data``) --
    checked below, raising on any mismatch in EITHER direction (a table
    agent with no matching profile, or a profile with no matching table
    row) rather than silently building a table that has quietly drifted
    from what the environment will actually load.

    A leading ``#``-prefixed comment line records the AZ priority-4 total
    (the f_g denominator) and its two-part source; loaders must skip it
    before handing the remaining lines to ``csv.DictReader`` (see
    ``irrigation_env.py (_load_lb_priority_split_table)``).
    """
    import sys as _sys

    import numpy as np  # local import: not needed by this tool's other targets

    # Local import (mirrors the pattern of every other function here that
    # needs a heavier dependency): irrigation_personas pulls in numpy and
    # pandas, not needed by this tool's other targets.
    _repo_root = Path(__file__).resolve().parents[3]
    if str(_repo_root) not in _sys.path:
        _sys.path.insert(0, str(_repo_root))
    from examples.irrigation_abm.irrigation_personas import create_profiles_from_data

    if not params_csv.is_file():
        raise ValueError(
            f"{params_csv} not found; --params-csv must point at "
            "ALL_colorado_ABM_params_cal_1108.csv (Hung and Yang's calibrated parameter file)."
        )
    if not crss_db_dir.is_dir():
        raise ValueError(
            f"{crss_db_dir} not found; --crss-db must point at a directory containing "
            "Div_States/LB_discrete_states.csv and "
            "HistoricalData/LB_historical_annual_diversion.csv (H&Y's CRSS_DB data release)."
        )
    profiles = create_profiles_from_data(
        str(params_csv), str(crss_db_dir),
        rng=np.random.default_rng(0),
        paper_water_margin=paper_water_margin, cluster_method=cluster_method,
    )
    lb_profiles = {p.agent_id: p for p in profiles if p.basin == "lower_basin"}
    missing = [a for a in _LB_PRIORITY_SOURCE_TABLE if a not in lb_profiles]
    if missing:
        raise ValueError(
            f"create_profiles_from_data produced no Lower Basin agent(s) {missing}; "
            "_LB_PRIORITY_SOURCE_TABLE and LB_discrete_states.csv have drifted apart."
        )
    extra = [a for a in lb_profiles if a not in _LB_PRIORITY_SOURCE_TABLE]
    if extra:
        raise ValueError(
            f"create_profiles_from_data produced Lower Basin agent(s) {extra} with no row in "
            "_LB_PRIORITY_SOURCE_TABLE; every one of the 22 must be hand-entered and cited "
            "before it can be split."
        )

    buf = io.StringIO()
    buf.write(
        "# AZ priority-4 total (denominator of f_g = AZ tier volume / AZ priority-4 total) = "
        f"{AZ_PRIORITY_4_TOTAL_AF:,.1f} AF = CAP {AZ_CAP_PRIORITY_4_ENTITLEMENT_AF:,.1f} AF "
        "(Public Law 108-451, Arizona Water Settlements Act of 2004, Sec. 104(c)(1)(A), "
        "118 Stat. 3490: total CAP long-term contract entitlements 'shall not exceed "
        "1,415,000 acre-feet') + on-river fourth-priority contracts "
        f"{AZ_ON_RIVER_PRIORITY_4_ENTITLEMENT_AF:,.1f} AF (USBR, Water Priorities Within the "
        "State of Arizona, Fourth Priority (i): 'not to exceed 164,652 acre-feet of "
        "diversions annually'). AZ tier volumes (2007 ROD Sec. 2.D.1, p.36): "
        f"{AZ_LB_TIER_VOLUME_AF[1]:,.0f} / {AZ_LB_TIER_VOLUME_AF[2]:,.0f} / "
        f"{AZ_LB_TIER_VOLUME_AF[3]:,.0f} AF for tiers 1-3. WP1c review round 2 (MEDIUM 4, "
        "PI instruction 'follow H&Y'): senior_entitlement_af / junior_entitlement_af below "
        "are the PUBLISHED USBR figures themselves (not derived from or scaled by "
        "water_right_af, the model's separate 1.4x-peak-diversion request ceiling); "
        "junior_entitlement_af is 0 for the 16 agents H&Y modelled as a single priority "
        "class (no split applies to them at all -- see irrigation_env.py's docstring and "
        "docs/irrigation_model_caveats.md for the units/method caveat).\n"
    )
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([
        "agent_id", "water_right_af", "senior_entitlement_af", "junior_entitlement_af",
        "basis", "priority_classes", "source",
    ])
    for agent_id in sorted(_LB_PRIORITY_SOURCE_TABLE):
        senior_af, junior_af, basis, priority_classes, source = _LB_PRIORITY_SOURCE_TABLE[agent_id]
        if junior_af < 0.0 or (senior_af is not None and senior_af < 0.0):
            raise ValueError(
                f"{agent_id}: senior_entitlement_af={senior_af!r} / "
                f"junior_entitlement_af={junior_af!r} must both be >= 0; check "
                "_LB_PRIORITY_SOURCE_TABLE."
            )
        water_right_af = float(lb_profiles[agent_id].water_right)
        writer.writerow([
            agent_id,
            f"{water_right_af:.2f}",
            "" if senior_af is None else f"{senior_af:.2f}",
            f"{junior_af:.2f}",
            basis,
            priority_classes,
            source,
        ])
    return buf.getvalue().encode("utf-8")


def _write_checked(path: Path, data: bytes, expected_sha256: str, label: str) -> None:
    actual = _sha256_bytes(data)
    if actual != expected_sha256:
        raise ValueError(
            f"{label}: freshly built content hashes to {actual}, expected "
            f"{expected_sha256}. Not writing {path} -- either the source "
            "data changed or the expected constant in this script is stale; "
            "resolve the discrepancy before committing a new checksum."
        )
    path.write_bytes(data)
    print(f"wrote {path} ({len(data)} bytes, sha256={actual})")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source-xlsx", type=Path, default=None,
        help="Path to NaturalFlows1906-2020_20221215.xlsx (required for "
             "--target hydrology/all)",
    )
    parser.add_argument(
        "--crss-db", type=Path, default=None,
        help="Path to a checkout of the CRSS_DB data release (H&Y 2021), "
             "i.e. the directory containing HistoricalData/"
             "UB_historical_annual_depletion.csv (required for --target "
             "ub_supply).",
    )
    parser.add_argument(
        "--params-csv", type=Path, default=DEFAULT_PARAMS_CSV,
        help="Path to ALL_colorado_ABM_params_cal_1108.csv (required for "
             f"--target lb_priority; default {DEFAULT_PARAMS_CSV}).",
    )
    parser.add_argument(
        "--target",
        choices=("all", "hydrology", "mead", "ub_supply", "ub_supply_variants", "lb_priority"),
        default="all",
    )
    args = parser.parse_args(argv)

    if args.target in ("all", "mead"):
        _write_checked(MEAD_CSV, build_mead_capacity_csv(), MEAD_CAPACITY_SHA256,
                        "mead_capacity_usbr2009_1ft.csv")

    if args.target in ("all", "hydrology"):
        if args.source_xlsx is None:
            print(
                "--source-xlsx is required to (re)build hydrology_v3.csv "
                "(the raw USBR workbook is not committed to this repo); "
                "skipping. Download it from "
                "https://www.usbr.gov/lc/region/g4000/NaturalFlow/current.html",
                file=sys.stderr,
            )
            if args.target == "hydrology":
                return 2
        else:
            _write_checked(HYDROLOGY_CSV, build_hydrology_csv(args.source_xlsx),
                            HYDROLOGY_V3_SHA256, "hydrology_v3.csv")

    # WP1b (item 20): not part of "all" -- it needs a SECOND external input
    # (--crss-db, H&Y's CRSS_DB data release) not committed to this repo,
    # on top of the USBR workbook every other target already needs.
    if args.target == "ub_supply":
        if args.source_xlsx is None or args.crss_db is None:
            print(
                "--source-xlsx and --crss-db are both required to (re)build "
                "ub_subbasin_supply_v3.csv / ub_subbasin_envelope_v3.csv "
                "(neither the USBR workbook nor the CRSS_DB data release is "
                "committed to this repo).",
                file=sys.stderr,
            )
            return 2
        _write_checked(
            UB_SUBBASIN_SUPPLY_CSV,
            build_ub_subbasin_supply_csv(args.source_xlsx, args.crss_db),
            UB_SUBBASIN_SUPPLY_SHA256, "ub_subbasin_supply_v3.csv",
        )
        _write_checked(
            UB_SUBBASIN_ENVELOPE_CSV,
            build_ub_subbasin_envelope_csv(args.source_xlsx, args.crss_db),
            UB_SUBBASIN_ENVELOPE_SHA256, "ub_subbasin_envelope_v3.csv",
        )

    # WP1b re-review (MEDIUM 4, spec 1b.6): the three CPU-sensitivity
    # variant supply tables (memo sections 8, 11). Also not part of "all"
    # (same two external inputs as --target ub_supply).
    if args.target == "ub_supply_variants":
        if args.source_xlsx is None or args.crss_db is None:
            print(
                "--source-xlsx and --crss-db are both required to (re)build "
                "the CPU-sensitivity variant supply tables.",
                file=sys.stderr,
            )
            return 2
        _write_checked(
            UB_SUBBASIN_SUPPLY_RHO02_CSV,
            build_ub_subbasin_supply_csv(args.source_xlsx, args.crss_db, rho=0.2),
            UB_SUBBASIN_SUPPLY_RHO02_SHA256, "ub_subbasin_supply_v3_rho02.csv",
        )
        _write_checked(
            UB_SUBBASIN_SUPPLY_LEES_FERRY_ALL_CSV,
            build_ub_subbasin_supply_csv(
                args.source_xlsx, args.crss_db, gauge_map=UB_SUBBASIN_GAUGES_LEES_FERRY_ALL
            ),
            UB_SUBBASIN_SUPPLY_LEES_FERRY_ALL_SHA256, "ub_subbasin_supply_v3_lees_ferry_all.csv",
        )
        _write_checked(
            UB_SUBBASIN_SUPPLY_TRIBUTARY_CSV,
            build_ub_subbasin_supply_csv(
                args.source_xlsx, args.crss_db, gauge_map=UB_SUBBASIN_GAUGES_TRIBUTARY
            ),
            UB_SUBBASIN_SUPPLY_TRIBUTARY_SHA256, "ub_subbasin_supply_v3_tributary.csv",
        )
        # WP1b re-review (LOW 1): each variant's own 1971-2018 mean flow,
        # generated alongside the tables above from the same two inputs.
        _write_checked(
            UB_SUBBASIN_VARIANT_MEANS_CSV,
            build_ub_subbasin_variant_means_csv(args.source_xlsx, args.crss_db),
            UB_SUBBASIN_VARIANT_MEANS_SHA256, "ub_subbasin_variant_means_v3.csv",
        )

    # WP1c (spec item 22): needs only the already-in-repo RL-ABM-CRSS
    # calibrated-parameter file and CRSS_DB checkout (--params-csv /
    # --crss-db, both with repo-relative defaults) -- neither is the large
    # USBR workbook the other targets need, so this one is not part of
    # "all".
    if args.target == "lb_priority":
        crss_db = args.crss_db or DEFAULT_CRSS_DB_DIR
        _write_checked(
            LB_PRIORITY_SPLIT_CSV,
            build_lb_priority_split_csv(args.params_csv, crss_db),
            LB_PRIORITY_SPLIT_SHA256, "lb_priority_split_v3.csv",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
