#!/usr/bin/env python3
"""
FQL Baseline Runner — Hung & Yang (2021) Q-Learning for Nature Water comparison.

Runs the same 78-agent × 42-year irrigation simulation as run_experiment.py,
but replaces LLM skill selection with FQL Q-learning in the SAME v3
IrrigationEnvironment (irrigation_v3_spec_2026-09-28.md section WP5): the
FQL's own action sets the request directly (env.update_agent_request, no
execute_skill redraw -- FQL and the LLM arms sample their step sizes from
two different distributions and must not share execute_skill's draw), with
the same water-right cap and minimum-use floor the LLM arms use, and
(--no-governance aside) the same v3 supply rule.

This produces the published baseline arm for comparison with with-validators and
no-validator LLM agents in the Nature Water paper. It is built from the source
code and design of Hung & Yang (2021); describe it that way rather than as a
"rule-based" baseline — fuzzy Q-learning is reinforcement learning, and the
paper's own text (Extended Data Table 1, SI Table 11) correctly calls it the
"FQL baseline". Corrected 2026-08-06; only this docstring was wrong.

Usage:
    # Smoke test (5 synthetic agents, 5 years). Synthetic agent ids have no
    # Hung & Yang calibrated Q/count/P_Tran files, so --fql-init zero is
    # required here (the CLI default, --fql-init calibrated, is for --real
    # runs -- see below).
    python run_fql_baseline.py --years 5 --agents 5 --seed 42 --fql-init zero

    # Full production (78 CRSS agents, 42 years, 3 seeds). --fql-init
    # calibrated is the default: each agent's Q/count/P_Tran table is
    # warm-started from Hung & Yang's own end-of-2018 calibrated state
    # (ref/CRSS_DB/CRSS_DB/Initial_Files/All-1109, 2026-09-27 decision --
    # see --fql-init-dir help / create_fql_agents docstring for why this
    # snapshot over the others), not zero-initialised.
    python run_fql_baseline.py --years 42 --real --seed 42 --rebalance-clusters
    python run_fql_baseline.py --years 42 --real --seed 43 --rebalance-clusters
    python run_fql_baseline.py --years 42 --real --seed 44 --rebalance-clusters

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from examples.irrigation_abm.learning.fql import (
    FQLAgent,
    FQLConfig,
    FQLState,
    FQLCalibratedInitError,
    load_calibrated_tables,
    CLUSTER_AGGRESSIVE,
    CLUSTER_FORWARD_LOOKING,
    CLUSTER_MYOPIC,
)
from examples.irrigation_abm.learning.fql_skill_mapper import (
    fql_action_to_skill,
    compute_wsa_label,
    compute_aca_label,
)
from examples.irrigation_abm.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
    hy_threshold_af,
    resolve_step_bin_af,
    HYDROLOGY_V3_SHA256,
    MEAD_CAPACITY_SHA256,
    UB_SUBBASIN_ENVELOPE_SHA256,
    UB_SUBBASIN_VARIANT_MEANS_SHA256,
    LB_PRIORITY_SPLIT_SHA256,
    # WP5 review (item 4, round 3, 2026-09-30): the per-variant {path,
    # sha256} table itself, so the manifest can record the checksum of
    # whichever Upper Basin supply variant this run actually used, not
    # always the "recommended" default -- see _pinned_v3_data_checksums.
    _UB_SUBBASIN_SUPPLY_VARIANT_FILES,
)
from examples.irrigation_abm.irrigation_personas import (
    IrrigationAgentProfile,
    build_simulation_log_row,
    create_profiles_from_data,
    read_lake_mead_level_for_log,
    rebalance_to_target,
    # WP1b re-review (MEDIUM 3, 2026-09-29): _reconstruct_profiles_from_logs'
    # CRSS-group fallback for a log with no ub_subbasin column.
    _build_ub_agent_names,
    _build_ub_state_group_map,
    _UB_HIST_COLUMN_BY_GROUP,
)
from examples.irrigation_abm.validators.irrigation_validators import (
    ALL_IRRIGATION_CHECKS,
    INCREASE_SKILLS,
    DECREASE_SKILLS,
    reset_consecutive_tracker,
    supply_rule_fields,
    update_consecutive_tracker,
)

# ── Constants ──
# FQL has only 2 actions (Hung & Yang 2021): increase and decrease.
# No large/small distinction — that is an LLM-path concept.
FQL_SKILLS = ["increase_demand", "decrease_demand", "maintain_demand"]

CLUSTER_CONFIGS = {
    "aggressive": CLUSTER_AGGRESSIVE,
    "forward_looking_conservative": CLUSTER_FORWARD_LOOKING,
    "myopic_conservative": CLUSTER_MYOPIC,
}


# ─────────────────────────────────────────────────────────────────────
# FQL calibrated-init helpers (Hung & Yang 2021 end-of-2018 warm start)
# ─────────────────────────────────────────────────────────────────────

def _load_ql_div_2017_2018(
    agent_id: str,
    basin: str,
    crss_db_dir: Optional[Path],
) -> Optional[Tuple[float, float]]:
    """Look for Hung & Yang's own per-agent 2017/2018 diversion files.

    ABM_CRSS_coupling.py's yi==0 branch (lines 505-508) reads
    ``<Index>_QL_Div_2017.csv`` / ``<Index>_QL_Div_2018.csv`` (Index =
    "UB" or "LB") from ``<working_dir>/CRSS_to_ABM/Div_Dist/`` -- a
    coupling *working* directory populated by an actual RiverWare/CRSS
    run, not part of the static reference bundle under
    ``ref/CRSS_DB/CRSS_DB``. ``crss_db_dir`` is that CRSS_DB directory;
    ``CRSS_to_ABM`` would be its sibling under the same working_dir. As
    of 2026-09-27 no such directory ships with the reference data, so
    this always returns None and the caller falls back to the historical
    annual series -- kept so a future/complete coupling bundle is picked
    up automatically without further code changes.

    Returns (div_2017, div_2018) if both files exist and both contain a
    column for ``agent_id``, else None.

    (v)/2026-09-27 review: NEITHER file existing (the coupling directory
    itself, or both csvs, absent) is the only allowed "miss" (this is
    Hung & Yang's own coupling *working* directory, never shipped in the
    static ref bundle, so this always misses today by construction).
    Exactly one file present (a partial/broken coupling directory), a
    parse error, or an agent-column absent from an existing file are NOT
    silently swallowed into a None -- each would mean this data source is
    present but broken/incomplete, which is a real defect, not "not yet
    populated"; all three now raise instead of letting
    resolve_prev_action() quietly fall through to the historical series
    without anyone knowing the primary source looked wrong.
    """
    if crss_db_dir is None:
        return None
    index = "UB" if basin == "upper_basin" else "LB"
    div_dist_dir = Path(crss_db_dir).parent / "CRSS_to_ABM" / "Div_Dist"
    f2017 = div_dist_dir / f"{index}_QL_Div_2017.csv"
    f2018 = div_dist_dir / f"{index}_QL_Div_2018.csv"
    exists_2017, exists_2018 = f2017.is_file(), f2018.is_file()
    if not exists_2017 and not exists_2018:
        return None
    if exists_2017 != exists_2018:
        # Exactly one of the pair exists -- a partial/broken coupling
        # directory, not the clean "neither file shipped" miss this
        # function otherwise tolerates. Raising here (2026-09-27 review)
        # closes the same silent-fallback gap as the agent-column check
        # below: a half-written Div_Dist directory must not quietly
        # degrade to the historical series.
        present = f2017 if exists_2017 else f2018
        missing = f2018 if exists_2017 else f2017
        raise FQLCalibratedInitError(
            f"[{agent_id}] {present} exists but its pair {missing} does "
            f"not -- a partial coupling working directory, not a clean "
            f"'neither file shipped' miss, so this is not silently "
            f"treated as a fallback trigger."
        )
    d17 = pd.read_csv(f2017, index_col=False)
    d18 = pd.read_csv(f2018, index_col=False)
    if agent_id not in d17.columns or agent_id not in d18.columns:
        raise FQLCalibratedInitError(
            f"[{agent_id}] {f2017} / {f2018} exist but have no column for "
            f"this agent -- not a 'file missing' condition, so this is not "
            f"silently treated as a fallback trigger. Investigate the "
            f"coupling working directory instead of using --fql-init zero."
        )
    return float(d17[agent_id].iloc[0]), float(d18[agent_id].iloc[0])


def resolve_prev_action(
    profile: IrrigationAgentProfile,
    crss_db_dir: Optional[Path],
) -> Tuple[float, float, str]:
    """Hung & Yang's first-year action bin: a_t = Div_req_y0 - Div_y0.

    At yi == 0, ABM_CRSS_coupling.py sets ``QL_Div_req = QL_Div =
    <Index>_QL_Div_2018.csv`` for BOTH basins (lines 505-508 for LB,
    618-621 for UB). For the Lower Basin, ``QL_Div_y0 =
    <Index>_QL_Div_2017.csv`` (line 507) and ``Div_y0`` always reads that
    2017 file (line 528), so ``a_t = Div_req_y0 - Div_y0`` (lines 532-537)
    is the observed 2017-to-2018 diversion change. The Upper Basin is
    DIFFERENT at yi == 0 (WP5 review, 2026-09-30, lines 642-643): H&Y
    OVERRIDE ``Div_y0 = QL_Div[agt][0]`` -- the SAME 2018 file ``Div_y``
    itself reads, not the 2017 one -- so ``a_t = Div_req_y0 - Div_y0 =
    Div_y - Div_y = 0`` EXACTLY for every Upper Basin agent in year 1,
    regardless of its real 2017-to-2018 change; the 2017 file
    (``QL_Div_y0``) is loaded for the Upper Basin too but is never read at
    yi == 0. This function returns (0.0, the 2018 value, source) for an
    Upper Basin profile and (the observed 2017-to-2018 change, the 2017
    value, source) for a Lower Basin one, matching that asymmetry exactly.

    That value becomes ``prev_action`` for the first FQL step (our
    FQLState.prev_action, used as ``a_t`` in the reward/posterior update
    on year 1); the second return value becomes ``prev_diversion`` (P1-b
    fix, 2026-09-27 review, generalised here for the Upper Basin's own
    yi == 0 rule): H&Y's first Q-update reads
    s_0 = state(Div_y0) and s_deviation = Div_y - (Div_y0 + a_t), which is
    0 in BOTH basins by construction (Lower Basin: 2018 - (2017 +
    (2018-2017)); Upper Basin: 2018 - (2018 + 0)) -- no regret penalty on
    year 1 -- which only holds if the caller sets prev_diversion to the
    SAME value this function returns for the SAME basin, not always 2017.

    Note (v): for the Lower Basin, exact ties (actual_2017_diversion ==
    actual_2018_diversion, 6 of the 78 real agents, all in the NM/New
    Mexico state group) give a_t == 0.0 exactly, same as every Upper Basin
    agent's a_t == 0.0 by construction above. H&Y's own
    ``a_t_i = int(a_t > 0)`` (coupling script line 212) maps a_t == 0.0 to
    the DECREASE index (0) deliberately -- our
    ``a_t_idx = int(state.prev_action > 0)`` in fql.py's step() does the
    same -- this is not a bug to special-case in either basin.

    Tries Hung & Yang's own per-agent QL_Div_2017/2018.csv files first
    (via ``_load_ql_div_2017_2018``); when unavailable (files genuinely
    absent), falls back to the historical annual series already loaded
    by ``create_profiles_from_data`` (``actual_2018_diversion -
    actual_2017_diversion`` for the Lower Basin, 0.0 for the Upper Basin,
    same series the paper's water-right history-anchor uses; for UB
    agents both years are split across a state group by the same
    per-agent ratio, an approximation of H&Y's own ``Within_Group_Dist``
    -- see the ``actual_2017_diversion`` assignment in
    ``create_profiles_from_data``). The Upper Basin's yi == 0 override
    applies to EITHER source identically (it is H&Y's own code, not a
    property of which file happens to be reachable); the precondition
    that both ``actual_2017_diversion``/``actual_2018_diversion`` be
    present is kept for the Upper Basin too even though this function
    then discards the 2017 value, so a real profile missing 2017 data
    (which would be a genuine data-completeness gap) still raises rather
    than silently proceeding on an incomplete series.

    Returns (prev_action, prev_diversion_2017, source) where source is
    one of "ql_div_csv" or "historical_annual_series", and
    ``prev_diversion_2017`` is the 2018 value (not 2017) for an Upper
    Basin profile, per the override above -- the name is kept for the
    Lower Basin case it was written for; init_provenance also records it
    under this same key. Raises FQLCalibratedInitError (v)/2026-09-27
    review) when NEITHER source has data for this agent -- calibrated
    mode never silently defaults prev_action/prev_diversion to 0.0; use
    --fql-init zero for profiles without CRSS historical data (e.g.
    synthetic agents).
    """
    ql = _load_ql_div_2017_2018(profile.agent_id, profile.basin, crss_db_dir)
    if ql is not None:
        div_2017, div_2018 = ql
        if profile.basin == "upper_basin":
            return 0.0, div_2018, "ql_div_csv"
        return div_2018 - div_2017, div_2017, "ql_div_csv"

    div_2018 = profile.actual_2018_diversion
    div_2017 = profile.actual_2017_diversion
    if div_2018 is not None and div_2017 is not None:
        if profile.basin == "upper_basin":
            return 0.0, float(div_2018), "historical_annual_series"
        return float(div_2018) - float(div_2017), float(div_2017), "historical_annual_series"

    raise FQLCalibratedInitError(
        f"[{profile.agent_id}] fql_init='calibrated' could not resolve "
        f"prev_action/prev_diversion: no QL_Div_2017/2018.csv coupling "
        f"files and no historical actual_2017_diversion/"
        f"actual_2018_diversion on the profile. Use --fql-init zero for "
        f"profiles without CRSS historical data (e.g. synthetic agents)."
    )


def _resolve_demand_per_grid_unit(profile: IrrigationAgentProfile) -> float:
    """k = depletion per diversion unit (spec conventions: 0.5 Upper
    Basin, H&Y p. 9; 1.0 Lower Basin). WP5 review (item 8, 2026-09-30): no
    silent ``or 1.0`` fallback here -- k=1.0 IS the correct model value
    for the Lower Basin (its grid already reports consumptive use), but
    for the Upper Basin it is a substantive, wrong value (it would
    understate every request and state-grid position by half), not a
    harmless "no conversion" default. Every profile
    create_profiles_from_data, _create_synthetic_profiles and
    _reconstruct_profiles_from_logs builds sets demand_per_grid_unit
    explicitly (0.5 Upper Basin, 1.0 Lower Basin); a profile that reaches
    here without one is a wiring defect in whichever builder made it, not
    a legitimate "assume no conversion" case.
    """
    if not profile.demand_per_grid_unit:
        raise ValueError(
            f"[{profile.agent_id}] has no demand_per_grid_unit; k must be "
            "set explicitly (0.5 Upper Basin, 1.0 Lower Basin) by whichever "
            "profile builder created it -- see create_profiles_from_data, "
            "_create_synthetic_profiles, _reconstruct_profiles_from_logs. "
            "k=1.0 is never a safe silent default for an Upper Basin "
            "profile (WP5 review item 8)."
        )
    return float(profile.demand_per_grid_unit)


# ─────────────────────────────────────────────────────────────────────
# FQL agent factory
# ─────────────────────────────────────────────────────────────────────

def create_fql_agents(
    profiles: List[IrrigationAgentProfile],
    seed: int = 42,
    fql_init: str = "zero",
    fql_init_dir: Optional[Path] = None,
    crss_db_dir: Optional[Path] = None,
) -> Dict[str, Tuple[FQLAgent, FQLState]]:
    """Create FQL agent + state pairs from irrigation profiles.

    Each agent gets:
    - FQLConfig from its cluster's canonical parameters
    - FQLState.state_bounds: under fql_init="zero", linspace(0,
      grid_top_af, 21) -- the ORIGINAL Hung & Yang discretisation grid
      (not the possibly peak-scaled water_right; see Review P1,
      2026-09-27 water-right history-anchor, for why the capped
      water_right must not shrink the FQL's own state bins). Under
      fql_init="calibrated" (P1-a fix, 2026-09-27 review), state_bounds
      is instead the agent's REAL Div_States column
      (profile.div_states_grid) with state_grid_mode="hy_exact" and
      hy_bin_size=profile.bin_size_af / profile.demand_per_grid_unit --
      19 of 22 LB agents' real columns are NOT a 0-to-top linspace (e.g.
      MohaveValleyIDD = [0, 12000, 14000, ..., 50000]), so treating them
      as one reads the wrong FQL state; see fql.py's _hy_div_to_state for
      the exact ABM_CRSS_coupling.py port. The ``/ demand_per_grid_unit``
      (WP2 spec 2.3, 2026-09-29) undoes the Upper Basin k=0.5 depletion
      conversion create_profiles_from_data now applies to bin_size_af
      itself (for the LLM-agent action model), so this state
      discretisation keeps reading the grid in its ORIGINAL diversion
      units, unchanged from before WP2 -- Lower Basin's
      demand_per_grid_unit is 1.0, a no-op. `grid_top_af`/`div_states_grid` are None
      only for profiles that never went through create_profiles_from_data
      (create_profiles_from_csv, synthetic builders); those must use
      fql_init="zero" (calibrated raises otherwise, no silent fallback).
    - FQLState.action_bin_size (WP5 spec 5.4, calibrated only):
      profile.step_bin_af / demand_per_grid_unit -- the v3 request
      formula's OWN magnitude bin (run_simulation's _fql_agent_decision),
      separate from hy_bin_size above. step_bin_af is bin_size_af UNLESS
      WP2 spec 2.4 rescaled it (8 agents whose raw grid step exceeded 20
      percent of their 2018 use), so this keeps the FQL reference's
      request-size distribution matching the language-model arms' typical
      step for exactly those 8 agents, while hy_bin_size keeps the
      Q-table's OWN state grid on H&Y's original, unrescaled units.
    - prev_diversion: under "zero", actual_2018_diversion (or 80% of
      water_right) -- unchanged from before 2026-09-27. Under
      "calibrated" (P1-b fix, 2026-09-27 review), the OBSERVED 2017
      diversion (resolve_prev_action's prev_diversion_2017), matching
      H&Y's first Q-update, which credits state(2017) and gives an exact
      zero reward deviation on year 1 -- not the 2018 value. WP5 spec 5.4:
      divided by demand_per_grid_unit (k) before being stored, same as
      prev_action just below, so both stay in the diversion units of
      state.state_bounds/hy_bin_size -- resolve_prev_action's OWN return
      value stays real (depletion-equivalent) acre-feet, unconverted, for
      provenance readability (init_provenance["prev_diversion_2017"]).
    - Q/count/P_Tran tables and prev_action: zero-initialised (FQLState
      .initialize()'s untrained defaults; prev_action stays 0.0) under
      fql_init="zero" -- byte-identical to this function's pre-2026-09-27
      behavior. Under fql_init="calibrated", warm-started from Hung &
      Yang's own end-of-2018 calibrated state via load_calibrated_tables()
      + resolve_prev_action() instead -- see
      examples/irrigation_abm/learning/fql.py's calibrated-init section
      for the axis mapping and ABM_CRSS_coupling.py line references. A
      missing/corrupt/wrong-shape/non-finite file, or an unresolvable
      prev_action, raises FQLCalibratedInitError; there is no silent
      zero/default fallback within "calibrated" mode.

    Args:
        profiles: List of IrrigationAgentProfile with cluster and water_right.
        seed: Base random seed (each agent gets seed + index for reproducibility).
        fql_init: "zero" (this function's own default, for backward
            compatibility with existing callers/tests using synthetic
            profiles that have no calibrated files) or "calibrated". The
            CLI (run_fql_baseline.py --fql-init) defaults to "calibrated"
            and passes it through explicitly.
        fql_init_dir: Directory holding Q_Table_<agent>.txt /
            count_<agent>.txt / P_Tran_<agent>.txt. Required when
            fql_init == "calibrated". The CLI defaults this to
            ref/CRSS_DB/CRSS_DB/Initial_Files/All-1109 (2026-09-27
            decision): the per-agent FQL parameters loaded from
            ALL_colorado_ABM_params_cal_1108.csv are dated 2020-11-08,
            and All-1109 is the only Initial_Files snapshot written on
            that same day (all 78 Q tables dated 2020-11-08) -- so
            parameters and learned tables come from one calibration run.
            'All' (Q tables dated 2021-05-28, seven months later, no
            matching parameter file shipped in this release) is what the
            authors' own initialization_ABM_CRSS_v3.py copies; 'All-WRR'
            is a composite of the 2020-09-13 Upper Basin and 2020-10-20
            Lower Basin batches. Item 36j (2026-10-05 design-basis
            audit + fix proposals, PI decision): All-1109 is KEPT, on the
            shared-calibration-date reason above; 'All' is run as a CPU
            sensitivity and reported beside it in the SI, not silently
            dropped.
        crss_db_dir: ref/CRSS_DB/CRSS_DB directory, used by
            resolve_prev_action() to look for Hung & Yang's own
            QL_Div_2017/2018.csv coupling files before falling back to
            the historical annual series. Only used when fql_init ==
            "calibrated"; may be None otherwise.

    Returns:
        Dict mapping agent_id → (FQLAgent, FQLState). Each FQLState's
        ``init_provenance`` dict records fql_init and (under "calibrated")
        the per-agent file hashes and prev_action source.
    """
    if fql_init not in ("calibrated", "zero"):
        raise ValueError(f"fql_init must be 'calibrated' or 'zero', got {fql_init!r}")
    if fql_init == "calibrated" and fql_init_dir is None:
        raise ValueError("fql_init='calibrated' requires fql_init_dir")

    agents: Dict[str, Tuple[FQLAgent, FQLState]] = {}

    # WP5 review (item 5, round 3, 2026-09-30 -- NIT): n independent
    # per-agent streams from one spawn call, NumPy's own documented
    # pattern (SeedSequence.spawn) -- see the per-agent rng construction
    # below for why this replaces np.random.default_rng([seed, i]).
    agent_streams = np.random.SeedSequence(seed).spawn(len(profiles))

    for i, p in enumerate(profiles):
        config = CLUSTER_CONFIGS.get(p.cluster, CLUSTER_FORWARD_LOOKING)

        # Per-agent FQL config using the profile's actual calibrated params
        agent_config = FQLConfig(
            mu=p.mu,
            sigma=p.sigma,
            alpha=p.alpha,
            gamma=p.gamma_param,
            epsilon=p.epsilon,
            regret=p.regret,
            forget=p.forget,
        )

        # WP5 review (item 8a, round 2; item 1, round 3, 2026-09-30): k is
        # needed by BOTH init branches now, not just "calibrated" -- the
        # zero-init grid built below is ALSO in H&Y's diversion units when
        # it falls back to water_right (no real grid_top_af), so it needs
        # the SAME /k conversion as hy_bin_size does in the calibrated
        # branch. Resolved once, up front, via the SAME raising helper
        # (no silent 1.0 for an Upper Basin profile missing it).
        k = _resolve_demand_per_grid_unit(p)

        if fql_init == "calibrated":
            # P1-a fix (2026-09-27 review): use H&Y's OWN Div_States
            # column as state_bounds, not np.linspace(0, grid_top_af, 21)
            # -- 19 of 22 LB agents' real grids are not a 0-to-top
            # linspace (e.g. MohaveValleyIDD = [0, 12000, 14000, ...,
            # 50000]), so the linspace read the wrong FQL state for them.
            # state_grid_mode="hy_exact" + hy_bin_size gate this so the
            # two discretisation rules can never mix (fql.py
            # _div_to_state/_sample_actions).
            if p.div_states_grid is None or p.bin_size_af is None:
                raise ValueError(
                    f"[{p.agent_id}] fql_init='calibrated' requires "
                    f"div_states_grid and bin_size_af on the profile "
                    f"(only set by create_profiles_from_data's --real "
                    f"path); got div_states_grid={p.div_states_grid!r} "
                    f"bin_size_af={p.bin_size_af!r}. Use --fql-init zero "
                    f"for profiles without a real Div_States column "
                    f"(e.g. synthetic agents)."
                )
            # WP2 (spec 2.3): bin_size_af is now UB-converted (k=0.5); undo
            # that here so the FQL grid-state math keeps reading H&Y's
            # original diversion-unit grid, byte-identical to pre-WP2.
            hy_bin_size = float(p.bin_size_af) / k
            # WP5 spec 5.4: action_bin_size = step_bin_af / k -- the v3
            # request formula's OWN bin, separate from hy_bin_size (which
            # stays on H&Y's unconverted grid for state discretisation
            # only). step_bin_af is set by the SAME create_profiles_from_data
            # --real path that guarantees bin_size_af/demand_per_grid_unit
            # (checked above); a profile that reached here without one is a
            # wiring defect, not a legitimate "no step" case -- no silent
            # `or bin_size_af` fallback (spec 2.4's rescaling would be lost).
            if not p.step_bin_af or p.step_bin_af <= 0:
                raise ValueError(
                    f"[{p.agent_id}] fql_init='calibrated' requires "
                    f"step_bin_af on the profile (set by "
                    f"create_profiles_from_data alongside bin_size_af); got "
                    f"{p.step_bin_af!r}."
                )
            action_bin_size = float(p.step_bin_af) / k
            state = FQLState(
                state_bounds=np.asarray(p.div_states_grid, dtype=float),
                state_grid_mode="hy_exact",
                hy_bin_size=hy_bin_size,
                action_bin_size=action_bin_size,
            )

            q_table, count_table, p_transition, file_hashes = load_calibrated_tables(
                agent_id=p.agent_id,
                init_dir=fql_init_dir,
                config=agent_config,
            )
            state.q_table = q_table
            state.count_table = count_table
            state.p_transition = p_transition

            # P1-b fix (2026-09-27 review): prev_action AND the "2017"
            # diversion it was derived from must come from the same
            # resolve_prev_action() call, so prev_diversion (set below,
            # after state.initialize()) and prev_action always agree on
            # which value was used (ql_div_csv vs the historical series
            # can differ slightly if the former ever becomes available).
            #
            # WP5 review (item 5, 2026-09-30): for the Upper Basin,
            # resolve_prev_action returns (0.0, the 2018 value) instead of
            # the observed 2017-to-2018 change, following H&Y's own yi==0
            # override (ABM_CRSS_coupling.py lines 642-643: Div_y0 is set
            # to the 2018 value for the Upper Basin only, so a_t = 0
            # exactly) -- see resolve_prev_action's own docstring for the
            # full derivation. The variable names below keep "2017" for
            # the Lower Basin case they were written for.
            #
            # WP5 spec 5.4: resolve_prev_action returns real (depletion-
            # equivalent, environment-native) acre-feet -- today's only
            # live source (the historical annual series) reads the SAME
            # UB_historical_annual_depletion.csv-derived series as
            # profile.actual_2018_diversion, which is depletion, not
            # diversion, for an Upper Basin agent. Dividing by k here
            # converts to H&Y's diversion-unit grid, matching the /k
            # conversion the per-year loop applies to Div_t (run_simulation
            # / _fql_agent_decision), so state.prev_diversion/prev_action
            # stay in the SAME units as every later current_diversion this
            # agent's step() will ever see (dividing 0.0 by k for an Upper
            # Basin agent is still 0.0 exactly). Disclosed gap: the OTHER
            # source (_load_ql_div_2017_2018, H&Y's own
            # QL_Div_2017/2018.csv) would already be diversion-native if
            # it ever became reachable (it is not today -- see that
            # function's own docstring) and must not be divided by k
            # again; this is not special-cased because there is nothing to
            # test against it.
            prev_action, prev_diversion_2017, prev_action_source = resolve_prev_action(
                p, crss_db_dir
            )
            prev_action_du = prev_action / k
            prev_diversion_2017_du = prev_diversion_2017 / k
            state.prev_action = prev_action_du
            state.init_provenance = {
                "fql_init": "calibrated",
                "fql_init_dir": str(fql_init_dir),
                "q_table_sha256": file_hashes["q_table"],
                "count_sha256": file_hashes["count"],
                "p_transition_sha256": file_hashes["p_transition"],
                # Real (environment-native) acre-feet, as observed --
                # unconverted, for audit/provenance readability.
                "prev_action": prev_action,
                "prev_action_source": prev_action_source,
                "prev_diversion_2017": prev_diversion_2017,
                # WP5 spec 5.4: the SAME two values divided by k, i.e. what
                # state.prev_action/prev_diversion actually hold internally.
                "demand_per_grid_unit": k,
                "prev_action_diversion_units": prev_action_du,
                "prev_diversion_2017_diversion_units": prev_diversion_2017_du,
                "state_grid_mode": "hy_exact",
                "hy_bin_size": hy_bin_size,
                "action_bin_size": action_bin_size,
            }
        else:
            # WP5 review (item 1, round 3, 2026-09-30 -- MEDIUM): when
            # grid_top_af is None (a synthetic or --from-logs profile),
            # the fallback MUST be water_right / k, not water_right alone.
            # The zero-init grid is built in H&Y's diversion units (same
            # convention as the calibrated branch's hy_bin_size); water_right
            # is real, environment-native acre-feet. For an Upper Basin
            # agent (k=0.5) the bare water_right fallback made the grid
            # HALF as wide as it should be, so the agent's own base
            # (base/k = 2x base in diversion units, typically well above a
            # grid topping out at water_right) pinned at the TOP state (20)
            # every year and _sample_actions drew against a bin_size half
            # the correct size. grid_top_af, when present, is ALREADY H&Y's
            # own diversion-unit grid top and needs no /k (same as the
            # calibrated branch never converts it).
            q_grid_top = p.grid_top_af if p.grid_top_af else p.water_right / k
            state = FQLState(
                state_bounds=np.linspace(0, q_grid_top, 21),
            )
            state.init_provenance = {"fql_init": "zero"}

        # FQLState.initialize() only fills fields that are still None, so
        # the calibrated tables set above are left untouched; under
        # fql_init="zero" this is unchanged from before 2026-09-27.
        state.initialize(agent_config)

        init_div = p.actual_2018_diversion if p.actual_2018_diversion else p.water_right * 0.8
        if fql_init == "calibrated":
            # P1-b fix (2026-09-27 review), generalised for the Upper
            # Basin's own yi==0 rule (WP5 review item 5): H&Y's first
            # Q-update credits s_0 = state(Div_y0) and gives a reward
            # deviation of exactly 0 (Div_y - (Div_y0 + a_t); Lower Basin:
            # 2018 - (2017 + (2018-2017)); Upper Basin: 2018 - (2018 + 0))
            # -- both only hold if prev_diversion is the SAME value
            # resolve_prev_action returned for the SAME basin (2017 for
            # the Lower Basin, 2018 for the Upper Basin), never always
            # 2017. The environment's own current_diversion for year 1
            # stays the 2018 value in BOTH basins (env.initialize_from_
            # profiles uses actual_2018_diversion, unchanged), matching
            # H&Y's Div_y.
            state.prev_diversion = prev_diversion_2017_du
        else:
            # WP5 review (item 6, round 2, 2026-09-30): the zero-init grid
            # (np.linspace(0, q_grid_top, 21) above) is ALSO in H&Y's
            # diversion units -- q_grid_top is grid_top_af, the raw,
            # unconverted grid top (or water_right / k when grid_top_af is
            # None, item 1 round 3) -- so init_div (real, environment-
            # native acre-feet) must be divided by k for the SAME reason
            # Div_t is divided by k every year (_fql_agent_decision), or a
            # real Upper Basin profile run under --fql-init zero reads the
            # wrong state just as Div_t would without that fix. k is NEVER
            # a silent 1.0 default here (item 8a, round 2): every profile,
            # synthetic or real, carries its own explicit
            # demand_per_grid_unit (1.0 Lower Basin, 0.5 Upper Basin), so
            # this division is a genuine no-op for Lower Basin agents
            # ONLY because k=1.0 IS their correct model value, not because
            # k was left unset. --fql-init zero is NOT byte-identical to
            # any historical commit (see --fql-init's own help text).
            state.prev_diversion = init_div / k

        # WP5 review (item 8c, 2026-09-30): prev_diversion_request must be
        # the SAME invariant step() itself maintains
        # (prev_diversion + prev_action, fql.py's own convention -- see
        # tests/test_fql.py's explicit assertion of it), not
        # init_div/k + prev_action (the pre-fix formula here double-
        # counted prev_action for the Lower Basin, where prev_action != 0:
        # init_div/k already equals prev_diversion + prev_action by
        # construction, since prev_action = (div_2018-div_2017)/k and
        # prev_diversion = div_2017/k sum to div_2018/k = init_div/k). Set
        # identically for BOTH init modes, after prev_diversion is final.
        state.prev_diversion_request = state.prev_diversion + state.prev_action

        # WP5 review (item 4, round 2, 2026-09-30): seed + i collides
        # across seeds (agent i+1 at seed S draws exactly what agent i
        # draws at seed S+1, e.g. seed 42's agent index 1 == seed 43's
        # agent index 0, both resolving to the same integer 43) -- a real
        # independence defect for the five-seed corpus (42-46), not merely
        # a style preference.
        #
        # WP5 review (item 5, round 3, 2026-09-30 -- NIT): np.random.
        # default_rng([seed, i]) (round 2's fix) does not collide across
        # seeds, but agent 0's own stream aliased env.rng (both built from
        # the SAME two-element entropy [seed, 0] vs however
        # WaterSystemConfig/IrrigationEnvironment seeds its own rng) --
        # np.random.SeedSequence(seed).spawn(n), NumPy's own documented
        # pattern for n independent parallel streams from one seed, avoids
        # this: agent_streams (spawned once below, before this loop) gives
        # each agent index its own child SeedSequence, none of which equal
        # the parent's own stream. Changes every RNG draw downstream of
        # agent construction -- the real and synthetic goldens are
        # regenerated for this (test_fql_v3.py).
        rng = np.random.default_rng(agent_streams[i])
        agent = FQLAgent(agent_config, rng=rng)

        agents[p.agent_id] = (agent, state)

    return agents


# ─────────────────────────────────────────────────────────────────────
# Validator integration
# ─────────────────────────────────────────────────────────────────────

def validate_skill(
    skill_name: str,
    context: Dict[str, Any],
) -> Tuple[bool, str]:
    """Run the dispatched irrigation validators (ALL_IRRIGATION_CHECKS: in
    v3 (WP3, spec 3.2) the supply rule alone -- the cap and the floor are
    YAML identity rules of the LLM arms and, for FQL, the environment's own
    clip; see irrigation_validators.py) on a proposed skill. ``context``
    must carry ``supply_rule_fields``' keys (``run_simulation`` adds them).

    WP5 spec 5.6 ("FQL plus rules", the CPU-sensitivity governed arm; the
    primary FQL reference runs with --no-governance and never calls this):
    a blocked increase falls back to keep (``maintain_demand``) ONLY --
    there is no further "last resort" tier. ``ALL_IRRIGATION_CHECKS`` is
    the v3 supply rule alone (WP3 3.2), which blocks only
    ``increase_demand`` (``supply_gap_block_increase`` returns ``[]`` for
    every other skill, WP3 3.3), so ``maintain_demand`` can never itself be
    blocked here -- a second fallback tier would be dead code, not a real
    safety net. The pre-WP5 "decrease_demand last resort" branch is
    removed for exactly that reason (unreachable under the v3 dispatch).

    Args:
        skill_name: Proposed skill name.
        context: Validation context (from env.get_agent_context + extras).

    Returns:
        (is_valid, final_skill_name) -- if blocked, falls back to
        maintain_demand.
    """
    results = []
    for check in ALL_IRRIGATION_CHECKS:
        results.extend(check(skill_name, [], context))

    blocked = any(not r.valid for r in results)
    if not blocked:
        return True, skill_name

    return True, "maintain_demand"


# ─────────────────────────────────────────────────────────────────────
# FQL decision logic (WP5, irrigation_v3_spec_2026-09-28.md section 5)
# ─────────────────────────────────────────────────────────────────────

def _fql_request_and_prev_action(
    div_t: float,
    k: float,
    action: float,
    water_right: float,
    floor: float,
) -> Tuple[float, float]:
    """WP5 spec 5.2: req = Div_t + k*a, capped at the water right, with the
    2.1 floor rule on decreases (a decrease is a no-op, not floor-anchored,
    when Div_t is already within 1 percent of the floor -- the SAME
    tolerance execute_skill's own decrease branch and
    _reset_requests_to_base use, spec 5.0's "same cap and floor as the
    language-model arms"). ``action`` is the FQL's own sampled action, in
    H&Y diversion units (spec 5.4); ``k`` = demand_per_grid_unit converts
    it back to real (environment-native) acre-feet.

    Returns (req, prev_action_executed), where prev_action_executed =
    (req - Div_t) / k is H&Y's executed-request convention (spec 5.2): at
    the water-right cap this is exactly 0 (Div_t was already at the cap,
    so req - Div_t = 0 regardless of a's sign), which H&Y's own
    ``int(a_t > 0)`` books as the DECREASE index for the next Bayesian
    update -- a known, disclosed quirk of H&Y's own code, not a WAGF bug
    (docs/irrigation_model_caveats.md).
    """
    delta_af = k * action
    if delta_af >= 0:
        req = min(div_t + delta_af, water_right)
    else:
        req = max(div_t + delta_af, floor) if div_t > 1.01 * floor else div_t
    prev_action_executed = (req - div_t) / k
    return req, prev_action_executed


def _fql_agent_decision(
    env: IrrigationEnvironment,
    profile: IrrigationAgentProfile,
    fql_agent: FQLAgent,
    fql_state: FQLState,
    pf_prev: int,
    year_idx: int,
    no_governance: bool,
) -> Dict[str, Any]:
    """One agent's WP5 FQL decision for the current year.

    Spec 5.0-5.7: Div_t is the BASE (last final delivery, spec 5.1, read
    from agent_state["base_af"] -- NOT ctx["current_diversion"], which is
    the PROVISIONAL delivery at the keep request the supply rule reads,
    L1-06); the FQL's OWN action sets the request with no execute_skill
    redraw (spec 5.2, L1-04), written with env.update_agent_request
    directly; the signal pair is (pf_prev, pf_now), not a same-year
    persistence assumption (spec 5.3, L1-05); the FQL state and reward run
    on Div_t/k and the request/k, on H&Y's own diversion-unit grid (spec
    5.4, L1-02); governance (skipped when no_governance), when applied,
    uses the v3 dispatch and falls back a blocked increase to keep only
    (spec 5.6); the logged final_skill is the sign of the executed change
    (spec 5.7).

    Returns a dict with everything run_simulation needs to log the
    decision: final_skill, raw_skill, action (the EXECUTED change, real
    acre-feet, req_final - Div_t -- spec 5.7), was_blocked, pf_now (for
    the caller to carry forward as next year's pf_prev), drought_index
    (from the SAME context read here, so the caller need not re-fetch
    it), and the realised/sampled magnitude diagnostics.
    """
    aid = profile.agent_id
    ctx = env.get_agent_context(aid)
    agent_state = env.get_agent_state(aid)

    # Spec 5.1 (L1-06): the base, not the provisional delivery.
    div_t = float(agent_state["base_af"])
    # Spec 5.4 (L1-02): k = demand_per_grid_unit (0.5 Upper Basin, 1.0
    # Lower Basin). WP5 review (item 8a): raises rather than silently
    # assuming 1.0 -- see _resolve_demand_per_grid_unit's own docstring.
    k = _resolve_demand_per_grid_unit(profile)

    # Spec 5.3 (L1-05): pf_now is this year's OWN flag (UB: the agent's own
    # sub-basin column, ">"; LB: 1 January Mead, ">="), already computed by
    # get_agent_context/_update_preceding_factors (WP1, unchanged by WP5).
    # The caller supplies pf_prev (1 in year 1, per spec 5.3; last year's
    # pf_now every year after).
    pf_now = int(ctx["preceding_factor"])

    action = fql_agent.step(fql_state, div_t / k, (int(pf_prev), pf_now))
    # WP5 review (item 8b, 2026-09-30): the PRE-CAP sampled delta, real
    # acre-feet -- what the FQL agent itself asked for before the
    # water-right cap, the minimum-use floor, OR governance touch it.
    # Logged separately from the executed change (spec 5.7) so a
    # reviewer can see how often/how much clipping actually bites,
    # instead of only ever seeing the post-clip outcome.
    action_precap_af = k * action

    water_right = float(ctx["water_right"])
    floor = water_right * env.config.min_utilisation_fraction
    # WP5 review (item 1, 2026-09-30): the SECOND return value (the
    # not-yet-governance-aware prev_action) is kept, not discarded via
    # ``_`` -- a discarded return value here was exactly why the "/k on
    # prev_action" mutation injection passed every test: nothing observed
    # this function's own prev_action contract, only the DIFFERENT inline
    # formula _fql_agent_decision used to recompute below for the
    # not-blocked case. Reusing it here removes that duplicate formula.
    req_raw, prev_action_raw = _fql_request_and_prev_action(div_t, k, action, water_right, floor)
    raw_skill = fql_action_to_skill(req_raw - div_t)

    if no_governance:
        final_skill = raw_skill
        req_final = req_raw
        was_blocked = False
    else:
        val_context = {
            "agent_id": aid,
            "at_allocation_cap": agent_state.get("at_allocation_cap", False),
            "has_efficient_system": agent_state.get("has_efficient_system", False),
            "below_minimum_utilisation": agent_state.get("below_minimum_utilisation", False),
            "water_right": ctx.get("water_right", 0),
            "current_diversion": ctx.get("current_diversion", 0),
            "current_request": ctx.get("current_request", 0),
            "curtailment_ratio": ctx.get("curtailment_ratio", 0),
            "shortage_tier": ctx.get("shortage_tier", 0),
            "drought_index": ctx.get("drought_index", 0.5),
            "cluster": ctx.get("cluster", "unknown"),
            "basin": ctx.get("basin", "unknown"),
            "total_basin_demand": ctx.get("total_basin_demand", 0),
            "loop_year": year_idx,
            # Re-review 2026-09-29 round 4 (LOW 2 follow-on): without
            # this, curtailment_awareness_check's now-direct-indexed
            # lb_shortage_volume_maf read raises KeyError the first
            # time a governed FQL run declares any shortage tier.
            # get_agent_context always supplies the key, so index it
            # directly: a missing key must raise, not log a 0 acre-ft
            # cut (same rule as run_experiment.py pre_year).
            "lb_shortage_volume_maf": ctx["lb_shortage_volume_maf"],
            # WP3 (spec 3.2/3.3): ALL_IRRIGATION_CHECKS is now the v3
            # supply rule alone, which reads its inputs from the SAME
            # helper the LLM runner's pre_year uses, and the gap code
            # and sharing fields its block message states. WP5 spec 5.6
            # settles the governed-FQL fallback (validate_skill above).
            "gap_reason": ctx["gap_reason"],
            "supply_group": ctx["supply_group"],
            "ub_subbasin_member_count": ctx["ub_subbasin_member_count"],
            "lb_junior_tier_cut_fraction": ctx["lb_junior_tier_cut_fraction"],
            **supply_rule_fields(ctx, agent_state),
        }
        _was_valid, final_skill = validate_skill(raw_skill, val_context)
        was_blocked = final_skill != raw_skill
        # Spec 5.6: a blocked increase falls back to KEEP -- the request
        # itself reverts to Div_t, not just the logged label.
        req_final = div_t if was_blocked else req_raw

    # Spec 5.2: prev_action follows the EXECUTED request (post-cap/floor/
    # governance), overwriting the raw value FQLAgent.step() set
    # internally -- so next year's Bayesian update and reward see what
    # actually happened, not the raw sampled action. Reuses
    # _fql_request_and_prev_action's OWN prev_action_raw for the
    # not-blocked case (req_final == req_raw, so its formula already gives
    # the right answer); a blocked decision reverts to keep, where
    # (Div_t - Div_t) / k is 0.0 exactly for any k != 0, so no second call
    # to the helper is needed.
    prev_action_executed = 0.0 if was_blocked else prev_action_raw
    fql_state.prev_action = prev_action_executed
    # WP5 review (item 8c): the SAME invariant create_fql_agents sets at
    # construction (prev_diversion + prev_action, fql.py's own convention)
    # -- fql_agent.step() already set fql_state.prev_diversion to div_t/k
    # internally, so this is equivalent to (div_t/k) + prev_action_executed,
    # written this way so the invariant is self-evident at both call sites.
    fql_state.prev_diversion_request = fql_state.prev_diversion + fql_state.prev_action

    # Spec 5.2 (L1-04): write the request directly -- no execute_skill
    # redraw. execute_skill's OWN Gaussian magnitude model is for the LLM
    # arms only; the FQL's magnitude is already decided above.
    env.update_agent_request(aid, req_final)

    # Diagnostics: the SAME resolver/threshold the LLM path's
    # execute_skill uses (irrigation_env.resolve_step_bin_af /
    # hy_threshold_af), applied to the FQL's own sampled (pre-governance)
    # magnitude, so "small"/"large" keeps its H&Y meaning (a draw at or
    # below the agent's median step) instead of silently going blank.
    sampled_af = abs(req_raw - div_t)
    realised_af = abs(req_final - div_t)
    magnitude_pct_sampled = (100.0 * sampled_af / div_t) if div_t > 0 else None
    magnitude_pct_applied = (100.0 * realised_af / div_t) if div_t > 0 else None
    magnitude_class = None
    if sampled_af > 0:
        step_bin_for_class = resolve_step_bin_af(
            profile.step_bin_af, profile.bin_size_af, water_right
        )
        threshold = hy_threshold_af(float(profile.mu), float(profile.sigma), step_bin_for_class)
        magnitude_class = "small" if sampled_af <= threshold else "large"

    return {
        "final_skill": final_skill,
        "raw_skill": raw_skill,
        # Spec 5.7: the sign of the EXECUTED change, real acre-feet (not
        # the internal diversion-unit action FQLAgent.step() returned).
        "action": req_final - div_t,
        # WP5 review (item 8b): the PRE-CAP sampled delta (real acre-feet,
        # k*action, before the cap/floor/governance this decision's
        # "action" field above already reflects).
        "action_precap": action_precap_af,
        "was_blocked": was_blocked,
        "pf_now": pf_now,
        "drought_index": ctx["drought_index"],
        "magnitude_pct_applied": magnitude_pct_applied,
        "magnitude_pct_sampled": magnitude_pct_sampled,
        "magnitude_af": realised_af,
        "magnitude_class": magnitude_class,
    }


# ─────────────────────────────────────────────────────────────────────
# Simulation loop
# ─────────────────────────────────────────────────────────────────────

def run_simulation(
    env: IrrigationEnvironment,
    fql_agents: Dict[str, Tuple[FQLAgent, FQLState]],
    profiles: Dict[str, IrrigationAgentProfile],
    n_years: int,
    output_dir: Path,
    seed: int = 42,
    no_governance: bool = False,
    pf_prev_init: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """Run FQL baseline simulation.

    Mirrors the LLM runner's lifecycle:
    1. advance_year() — generate water signals
    2. For each agent: FQL step → skill mapping → (optionally validate) → execute
    3. Log results in identical CSV format

    Args:
        env: Initialized IrrigationEnvironment.
        fql_agents: Dict from create_fql_agents().
        profiles: Dict of agent_id → IrrigationAgentProfile.
        n_years: Number of simulation years.
        output_dir: Directory for output files.
        seed: Random seed.
        no_governance: If True, skip all validators (raw FQL behavior).

    Returns:
        List of log dicts (one per agent per year).
    """
    logs: List[Dict[str, Any]] = []
    agent_ids = env.agent_ids

    reset_consecutive_tracker()

    # Spec 5.3 (L1-05, L1-15): pf_prev = 1 for every agent in year 1
    # (2019) -- H&Y's OWN value in BOTH basins, verified directly against
    # the shipped data, not a WAGF simplification (WP5 review, 2026-09-30,
    # item 7a): the Lower Basin's two inserted Mead anchors
    # (1081.46 -> 1082.52, ABM_CRSS_coupling.py) give f_t_all[0] = 1 by
    # construction; the Upper Basin's own PRISM winter-precipitation data
    # gives a 2018-over-2017 increase in all nine sub-basin columns
    # (checked directly against the shipped CSV), so f_t_all[0] = 1 there
    # too, empirically, settling L1-15.
    # Each agent's own pf_now this year (from get_agent_context, computed
    # by _update_preceding_factors -- UB from its own sub-basin column
    # with ">", LB from 1 January Mead with ">=") becomes next year's
    # pf_prev, carried here across the year loop (fql.py's FQLState is not
    # the right home for it: it is a run-level lag, not per-agent learned
    # state).
    pf_prev: Dict[str, int] = {aid: 1 for aid in agent_ids} if pf_prev_init is None else pf_prev_init

    for year_idx in range(1, n_years + 1):
        # Advance environment (generates precipitation, Mead level, curtailment)
        env.advance_year()
        sim_year = env.current_year

        year_skills = {}
        year_blocked = 0
        year_decisions: Dict[str, Dict[str, Any]] = {}

        for aid in agent_ids:
            if aid not in fql_agents:
                continue

            fql_agent, fql_state = fql_agents[aid]
            profile = profiles.get(aid)
            if profile is None:
                continue

            decision = _fql_agent_decision(
                env=env,
                profile=profile,
                fql_agent=fql_agent,
                fql_state=fql_state,
                pf_prev=pf_prev.get(aid, 1),
                year_idx=year_idx,
                no_governance=no_governance,
            )
            pf_prev[aid] = decision["pf_now"]

            final_skill = decision["final_skill"]
            if decision["was_blocked"]:
                year_blocked += 1

            # ── Update consecutive tracker (same as LLM post_step) ──
            update_consecutive_tracker(aid, final_skill)

            # Stash everything needed to log this agent's row AFTER
            # settle_year() runs for the whole year (below) -- the
            # settlement-derived columns (mead_storage_end_maf,
            # powell_storage_maf, delivered, ...) do not exist yet.
            year_decisions[aid] = {
                "cluster": profile.cluster,
                "basin": profile.basin,
                "final_skill": final_skill,
                "raw_skill": decision["raw_skill"],
                "action": decision["action"],
                "action_precap": decision["action_precap"],
                "was_blocked": decision["was_blocked"],
                "wsa_label": compute_wsa_label(decision["drought_index"]),
                "aca_label": compute_aca_label(profile.cluster),
                "magnitude_pct": decision["magnitude_pct_applied"],
                "magnitude_pct_sampled": decision["magnitude_pct_sampled"],
                "magnitude_af": decision["magnitude_af"],
                "magnitude_class": decision["magnitude_class"],
                # FQL has no magnitude-exploration concept distinct from its
                # own epsilon-greedy DIRECTION choice (fql_skill_mapper.py);
                # always False, unchanged from pre-WP5 (execute_skill's own
                # is_exploration was also unconditionally False for FQL).
                "is_exploration": False,
            }

            year_skills[final_skill] = year_skills.get(final_skill, 0) + 1

        # Supply-side redesign (2026-09-25): settle the year once, after every
        # agent's decision (mirrors the LLM runner's
        # IrrigationLifecycleHooks.post_year, which calls settle_year() before
        # building any row). Only after this call are delivered / *_end_maf /
        # basin_request_af defined for the year.
        settlement = env.settle_year()
        basin_request_af = (
            settlement["ub_request_maf"] + settlement["lb_request_maf"]
        ) * 1e6
        drought_index_year = env.global_state.get("drought_index", 0)
        shortage_tier_year = env.institutions.get("colorado_compact", {}).get("shortage_tier", 0)
        # Guarded read (2026-09-27 fix): same helper as run_experiment.py's
        # IrrigationLifecycleHooks._log_lake_mead_level, so both runners
        # raise the same way instead of this one silently logging 0 when
        # coupling.context_contract is ON and the level is missing.
        lake_mead_level_year = read_lake_mead_level_for_log(env)
        mead_storage_maf_year = env._mead_storage[-1] if env._mead_storage else 0

        # ── Logging (same schema as the LLM run; see build_simulation_log_row) ──
        for aid, dec in year_decisions.items():
            agent_state = env.get_agent_state(aid)
            # Review 2026-09-28 (fix 5): same as run_experiment.py's
            # post_year -- the agent's own precipitation/flag for the
            # year, frozen since advance_year(), for the log columns.
            agent_context = env.get_agent_context(aid)
            row = build_simulation_log_row(
                agent_id=aid,
                year=year_idx,
                cluster=dec["cluster"],
                basin=dec["basin"],
                yearly_decision=dec["final_skill"],
                wsa_label=dec["wsa_label"],
                aca_label=dec["aca_label"],
                agent_state=agent_state,
                drought_index=drought_index_year,
                shortage_tier=shortage_tier_year,
                lake_mead_level=lake_mead_level_year,
                mead_storage_maf=mead_storage_maf_year,
                settlement=settlement,
                basin_request_af=basin_request_af,
                magnitude_pct=dec["magnitude_pct"],
                magnitude_pct_sampled=dec["magnitude_pct_sampled"],
                magnitude_af=dec["magnitude_af"],
                magnitude_class=dec["magnitude_class"],
                magnitude_fallback=False,
                is_exploration=dec["is_exploration"],
                memory="FQL_BASELINE",
                # WP2 (spec 2.1): same keep-request base as the LLM path,
                # set once a year by
                # IrrigationEnvironment._reset_requests_to_base.
                base_af=agent_state.get("base_af"),
                precipitation_mm=agent_context.get("precipitation"),
                precipitation_flag=agent_context.get("precipitation_flag"),
            )
            # FQL-only columns, appended after the full LLM column set.
            row["fql_raw_skill"] = dec["raw_skill"]
            row["fql_action"] = dec["action"]
            # WP5 review (item 8b): the pre-cap/floor/governance sampled
            # delta, real acre-feet -- see _fql_agent_decision's docstring.
            row["fql_action_precap"] = dec["action_precap"]
            row["fql_blocked"] = dec["was_blocked"]
            logs.append(row)

        # Year summary (reuses the same guarded read computed above, so the
        # console line and the logged column never disagree)
        n_agents = len(agent_ids)
        skill_summary = ", ".join(f"{k}={v}" for k, v in sorted(year_skills.items()))
        mead = lake_mead_level_year
        drought = env.global_state.get("drought_index", 0)
        print(
            f"  Year {year_idx:3d} (sim {sim_year}) | "
            f"Mead={mead:.1f}ft | drought={drought:.2f} | "
            f"blocked={year_blocked}/{n_agents} | {skill_summary}"
        )

    return logs


# ─────────────────────────────────────────────────────────────────────
# Synthetic profile builder (for smoke tests without CRSS data)
# ─────────────────────────────────────────────────────────────────────

def _reconstruct_profiles_from_logs(
    log_dir: str,
    seed: int = 42,
    crss_db_dir: str = "ref/CRSS_DB/CRSS_DB",
) -> List[IrrigationAgentProfile]:
    """Reconstruct agent profiles from an existing simulation_log.csv.

    Extracts agent_id, cluster, basin, water_right, and initial diversion
    from year 1 of a governed LLM run. FQL parameters come from cluster
    configs (identical to the original --real path).

    NOT step-comparable with a --real run (2026-09-26): these profiles carry
    no grid step (bin_size_af), so the environment falls back to
    water_right / 25, and mu / sigma are cluster centroids, while --real
    profiles carry each agent's own Hung and Yang mu, sigma and grid step.

    WP1b re-review (MEDIUM 3, 2026-09-29): each Upper Basin profile's
    sub-basin (precip_group) is filled from the logged ``ub_subbasin``
    column (spec 1b.4) when the source log has one and it is non-empty for
    that agent's year-1 row -- a log from a run made after WP1b landed.
    Otherwise it falls back to the same CRSS Group_Agt mapping
    ``create_profiles_from_data`` uses (a log from before WP1b, which never
    wrote that column). Raises if neither source has it: a silent
    ``precip_group=None`` here would make initialize_from_profiles either
    raise later (in subbasin mode) or, worse, silently route a REAL Upper
    Basin agent into the unconstrained pool bucket meant only for
    synthetic profiles (MEDIUM 2).

    Args:
        log_dir: Path to a directory containing simulation_log.csv
            (e.g., results/production_v20_42yr_seed42).
        seed: Random seed for any stochastic profile attributes.
        crss_db_dir: CRSS_DB checkout, used only as the CRSS-group fallback
            when the log predates the ub_subbasin column.
    """
    from examples.irrigation_abm.irrigation_personas import build_narrative_persona

    csv_path = Path(log_dir) / "simulation_log.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"No simulation_log.csv in {log_dir}")

    df = pd.read_csv(csv_path, encoding="utf-8")
    y1 = df[df["year"] == 1].copy()
    rng = np.random.default_rng(seed)
    has_ub_subbasin_column = "ub_subbasin" in y1.columns

    # CRSS group mapping, built lazily (only once, only if some row's
    # logged ub_subbasin is unusable) rather than unconditionally -- a
    # post-WP1b log never needs it and should not require crss_db_dir to
    # exist on disk.
    ub_sg_map: Optional[Dict[str, str]] = None

    def _crss_group_subbasin(agent_id: str) -> Optional[str]:
        nonlocal ub_sg_map
        if ub_sg_map is None:
            group_agt_path = os.path.join(
                crss_db_dir, "Group_Agt", "UB_ABM_Groups_and_Agents.csv"
            )
            if not os.path.isfile(group_agt_path):
                return None
            ub_agent_names = _build_ub_agent_names(group_agt_path)
            ub_sg_map = _build_ub_state_group_map(ub_agent_names)
        state_group = ub_sg_map.get(agent_id)
        if state_group is None:
            return None
        return _UB_HIST_COLUMN_BY_GROUP.get(state_group, state_group)

    profiles = []
    for _, row in y1.iterrows():
        cluster = row["cluster"]
        ref = CLUSTER_CONFIGS.get(cluster, CLUSTER_FORWARD_LOOKING)
        basin = row["basin"]

        precip_group = None
        if basin == "upper_basin":
            logged = row.get("ub_subbasin") if has_ub_subbasin_column else None
            if isinstance(logged, str) and logged.strip():
                precip_group = logged.strip()
            else:
                precip_group = _crss_group_subbasin(row["agent_id"])
            if not precip_group:
                raise ValueError(
                    f"{row['agent_id']}: {csv_path} has no usable ub_subbasin "
                    f"value for this agent (column present: "
                    f"{has_ub_subbasin_column}), and no CRSS group mapping "
                    f"was found under {crss_db_dir!r} either -- cannot "
                    "determine this Upper Basin agent's sub-basin (MEDIUM 3, "
                    "2026-09-29 re-review). Pass crss_db_dir explicitly if "
                    "the CRSS_DB checkout used to build this run lives "
                    "elsewhere."
                )

        profile = IrrigationAgentProfile(
            agent_id=row["agent_id"],
            basin=basin,
            cluster=cluster,
            mu=ref.mu,
            sigma=ref.sigma,
            alpha=ref.alpha,
            gamma_param=ref.gamma,
            epsilon=ref.epsilon,
            regret=ref.regret,
            forget=True,
            farm_size_acres=rng.uniform(200, 2000),
            water_right=row["water_right"],
            crop_type="mixed",
            years_farming=int(rng.integers(5, 40)),
            has_efficient_system=bool(row.get("has_efficient_system", False)),
            actual_2018_diversion=row["diversion"],
            precip_group=precip_group,
            # WP5 review (item 8a, 2026-09-30): k is a MODEL fact, not a
            # "no conversion" placeholder -- explicit here so
            # create_fql_agents/_fql_agent_decision's k resolution never
            # has to guess for a --from-logs profile (this path never sets
            # div_states_grid/bin_size_af, so it can only use
            # --fql-init zero, whose own k lookup now raises rather than
            # silently defaulting to 1.0 for an Upper Basin profile).
            demand_per_grid_unit=(0.5 if basin == "upper_basin" else 1.0),
        )
        profile.narrative_persona = build_narrative_persona(profile, rng)
        profiles.append(profile)

    return profiles


def _create_synthetic_profiles(
    n_agents: int,
    seed: int = 42,
) -> List[IrrigationAgentProfile]:
    """Create synthetic profiles with balanced cluster distribution."""
    from examples.irrigation_abm.irrigation_personas import build_narrative_persona

    rng = np.random.default_rng(seed)
    clusters = ["aggressive", "forward_looking_conservative", "myopic_conservative"]

    profiles = []
    for i in range(n_agents):
        basin = "upper_basin" if i < n_agents // 3 else "lower_basin"
        cluster = clusters[i % 3]
        ref = CLUSTER_CONFIGS[cluster]

        profile = IrrigationAgentProfile(
            agent_id=f"Agent_{i:03d}",
            basin=basin,
            cluster=cluster,
            mu=ref.mu + rng.normal(0, 0.02),
            sigma=ref.sigma + rng.normal(0, 0.1),
            alpha=ref.alpha + rng.normal(0, 0.02),
            gamma_param=ref.gamma + rng.normal(0, 0.02),
            epsilon=ref.epsilon + rng.normal(0, 0.01),
            regret=ref.regret + rng.normal(0, 0.1),
            forget=True,
            farm_size_acres=rng.uniform(200, 2000),
            water_right=rng.uniform(50_000, 200_000),
            crop_type=str(rng.choice(["alfalfa", "cotton", "vegetables", "corn"])),
            years_farming=int(rng.integers(5, 40)),
            # WP1b re-review (MEDIUM 2, 2026-09-29): a mock-smoke-only
            # profile must NOT be assigned a real sub-basin (precip_group
            # stays None) -- an earlier version of this fix round-robinned
            # the nine real ones, which put a synthetic agent inside a REAL
            # sub-basin's request cap (Agent_002 landing in UT2 and getting
            # 29 percent of its request, a number that describes UT2's real
            # farms, not this mock agent). synthetic_no_subbasin=True
            # instead routes it to IrrigationEnvironment.
            # initialize_from_profiles's unconstrained pool bucket (logged
            # once there), the correct "this agent has no real location"
            # treatment.
            precip_group=None,
            synthetic_no_subbasin=(basin == "upper_basin"),
            # WP1c review round 2 (LOW 6): same "no real location/entitlement"
            # treatment as synthetic_no_subbasin above, for the Lower Basin
            # priority-split table; unconditional on basin (harmless/unused
            # for an Upper Basin profile).
            synthetic_no_priority_split=True,
            # WP5 review (item 8a, 2026-09-30): explicit even for a mock
            # profile -- k=0.5/1.0 is the model's own per-basin value, not
            # a "no conversion" guess, so create_fql_agents/
            # _fql_agent_decision's k resolution never has to fall back
            # silently for a synthetic Upper Basin agent either.
            demand_per_grid_unit=(0.5 if basin == "upper_basin" else 1.0),
        )
        profile.narrative_persona = build_narrative_persona(profile, rng)
        profiles.append(profile)

    return profiles


# ─────────────────────────────────────────────────────────────────────
# Manifest provenance (WP5 review item 2, 2026-09-30)
# ─────────────────────────────────────────────────────────────────────

def _git_provenance(repo_root: Path) -> Dict[str, Any]:
    """git HEAD and working-tree dirtiness at launch.

    Best-effort: a git lookup failure is recorded under "git_error", not
    raised -- a missing git binary or a non-repo checkout is a narrower,
    separate concern from whether the manifest write itself succeeds (the
    outer guard in main() that fails a --real run on THAT).
    """
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root),
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=str(repo_root),
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout
        return {"git_head": head, "git_dirty": bool(status.strip())}
    except Exception as e:
        return {"git_head": None, "git_dirty": None, "git_error": str(e)}


def _crss_db_input_checksums(crss_db_dir: Path) -> Dict[str, Optional[str]]:
    """sha256 of the ref/CRSS_DB inputs the FQL reference actually reads:
    the PRISM winter-precipitation CSV, both basins' Div_States grids,
    both basins' historical annual use files (create_profiles_from_data,
    resolve_prev_action's historical-annual-series fallback), and the
    Upper Basin Group_Agt mapping (WP5 review item 4, round 3, 2026-09-30:
    create_profiles_from_data's UB loop reads this to resolve each
    agent's state group -- the same input class as the Div_States/
    historical files above, previously missing from this list).

    None for a file that is not present, rather than raising -- a --real
    run cannot have reached main()'s manifest-writing block without these
    files (create_profiles_from_data/load_crss_precipitation already
    require them), so None here would mean the file vanished mid-run, a
    fact worth recording rather than a reason to add a second raise path
    that duplicates what already happened earlier in the run.
    """
    targets = {
        "prism_winter_precip_csv": crss_db_dir / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv",
        "ub_discrete_states_csv": crss_db_dir / "Div_States" / "UB_discrete_states.csv",
        "lb_discrete_states_csv": crss_db_dir / "Div_States" / "LB_discrete_states.csv",
        "ub_historical_annual_depletion_csv": crss_db_dir / "HistoricalData" / "UB_historical_annual_depletion.csv",
        "lb_historical_annual_diversion_csv": crss_db_dir / "HistoricalData" / "LB_historical_annual_diversion.csv",
        "ub_abm_groups_and_agents_csv": crss_db_dir / "Group_Agt" / "UB_ABM_Groups_and_Agents.csv",
    }
    out: Dict[str, Optional[str]] = {}
    for key, path in targets.items():
        out[key] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return out


def _pinned_v3_data_checksums(ub_subbasin_supply_variant: str) -> Dict[str, str]:
    """The v3 data checksums IrrigationEnvironment itself pins and checks
    at load. Recorded here from the SAME module constants irrigation_env.py
    checks every load against (imported at the top of this file), never
    recomputed from disk, so this can never silently drift from what was
    actually validated when the environment loaded these tables.

    WP5 review (item 4, round 3, 2026-09-30): ``ub_subbasin_supply_v3_csv``
    is the checksum of the variant ACTUALLY IN USE
    (``env.config.ub_subbasin_supply_variant``, passed in by the caller),
    not always the "recommended" default -- a run using a CPU-sensitivity
    variant (rho_0_2, lees_ferry_all, tributary_gauges) previously had its
    manifest record the WRONG table's checksum. ``ub_subbasin_variant_
    means_v3_csv`` (the per-variant mean-flow table get_agent_context
    reads for the sub-basin flow-share text) was previously missing from
    this list entirely.
    """
    _, active_supply_sha256 = _UB_SUBBASIN_SUPPLY_VARIANT_FILES[ub_subbasin_supply_variant]
    return {
        "hydrology_v3_csv": HYDROLOGY_V3_SHA256,
        "mead_capacity_usbr2009_1ft_csv": MEAD_CAPACITY_SHA256,
        "ub_subbasin_supply_v3_csv": active_supply_sha256,
        "ub_subbasin_supply_v3_variant": ub_subbasin_supply_variant,
        "ub_subbasin_envelope_v3_csv": UB_SUBBASIN_ENVELOPE_SHA256,
        "ub_subbasin_variant_means_v3_csv": UB_SUBBASIN_VARIANT_MEANS_SHA256,
        "lb_priority_split_v3_csv": LB_PRIORITY_SPLIT_SHA256,
    }


def _write_reproducibility_manifest(
    manifest: Dict[str, Any], output_dir: Path, is_real: bool
) -> None:
    """Write ``manifest`` to ``output_dir / "reproducibility_manifest.json"``.

    WP5 review (item 2, round 2; item 3, round 3, 2026-09-30): a --real
    run's manifest is the only record of which data/config this reference
    actually used (--fql-init, the data checksums, git HEAD/dirty, the
    resolved water-system config) -- on any write failure, ``is_real=True``
    FAILS (re-raises, after printing a FATAL line) rather than letting a
    scientifically load-bearing run finish looking successful with no
    provenance trail. ``is_real=False`` (a synthetic/smoke run) only warns
    (no raise) -- losing a smoke test's own manifest is not comparable.

    Factored out of main() so this exact behavior is directly testable
    (test_fql_v3.py's TestManifestProvenance) without invoking the whole
    run pipeline: pass a plain dict and an output_dir engineered to fail
    the write (e.g. one whose parent does not exist).
    """
    try:
        with open(output_dir / "reproducibility_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        if is_real:
            print(f"[Provenance] FATAL: could not write reproducibility_manifest.json: {e}")
            raise
        print(f"[Provenance] WARNING: could not write reproducibility_manifest.json: {e}")


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def _append_launch_command_line(output_dir: Path, text: str) -> None:
    """Append one line to LAUNCH_COMMAND.txt in output_dir.

    Creates the file if it does not already exist, or appends to it if an
    external launcher already wrote command/worktree/commit lines before
    invoking this script (as the LAUNCH_COMMAND.txt beside every
    fql_nogov_* results directory records). Restores the run-timing this
    runner's references carried at 431adb5e but lost afterward -- that
    pair was never written by this file itself (git log -p on this file
    across 00654d14 and 044c9fd5 shows neither commit touched it); it
    came from an ad hoc, never-committed launch script, the same pattern
    documented for the LLM runner's own launch_seed.sh in commit
    7c9be94f. Writing RunnerStarted:/RunnerFinished: from inside the
    runner means every future run gets them regardless of which launcher
    is used. The lines are namespaced Runner* (not Started:/Finished:)
    so they never collide with a launcher's own lines of those names,
    and the runner never writes ExitCode: -- only the process that
    invoked this script (the launcher) can know the real exit status;
    claiming it from inside main() would be a lie whenever the launcher
    itself does extra work (e.g. copying output) after main() returns.
    Never fails the run over a provenance write (mirrors the
    reproducibility_manifest.json guard below).
    """
    try:
        with open(output_dir / "LAUNCH_COMMAND.txt", "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception as e:
        print(f"[Provenance] WARNING: could not write LAUNCH_COMMAND.txt: {e}")


def main():
    run_started_at = datetime.now()
    args = parse_args()
    if args.hindcast:
        from examples.irrigation_abm.hindcast_env import (
            HINDCAST_FIRST_YEAR, HINDCAST_LAST_YEAR, HINDCAST_PRECIP_CSV,
            HindcastAgentEnvironment, hindcast_config_kwargs, hindcast_provenance,
            initial_pf_prev, reanchor_profiles,
        )
        expected_years = HINDCAST_LAST_YEAR - HINDCAST_FIRST_YEAR + 1
        if (not args.real or args.years != expected_years or args.from_logs
                or args.rebalance_clusters or args.fql_init != "calibrated"):
            raise SystemExit(
                f"--hindcast requires --real --years {expected_years} --fql-init calibrated, "
                "without --from-logs or --rebalance-clusters."
            )
    if args.rebalance_clusters and args.cluster_method == "hy2021":
        raise SystemExit(
            "--rebalance-clusters cannot be combined with --cluster-method "
            "hy2021: rebalancing reassigns clusters toward a target "
            "distribution by FQL-parameter distance, which would overwrite "
            "Hung & Yang (2021) Figure 7's own published per-entity "
            "assignment (HY2021_CLUSTER_LABELS) that --cluster-method "
            "hy2021 exists to preserve. Pass --cluster-method "
            "legacy_centroid if you want the rebalanced distribution."
        )
    base = Path(__file__).parent
    ref_dir = PROJECT_ROOT / "ref"

    # Random seed
    seed = args.seed
    random.seed(seed)
    np.random.seed(seed)

    # Feature flags. demand_ceiling_stabilizer is retired from dispatch (2026-09-25); this flag only gates a direct call.
    import examples.irrigation_abm.validators.irrigation_validators as irr_validators
    irr_validators.ENABLE_CONSECUTIVE_CAP = False
    irr_validators.ENABLE_ZERO_ESCAPE = False
    irr_validators.ENABLE_DEMAND_CEILING = True

    # Create profiles
    if args.from_logs:
        profiles = _reconstruct_profiles_from_logs(
            args.from_logs, seed, crss_db_dir=str(ref_dir / "CRSS_DB" / "CRSS_DB")
        )
        print(f"[Data] Reconstructed {len(profiles)} agents from existing simulation logs")
    elif args.real:
        params_csv = str(ref_dir / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv")
        crss_db = str(ref_dir / "CRSS_DB" / "CRSS_DB")
        profiles = create_profiles_from_data(
            params_csv_path=params_csv,
            crss_db_dir=crss_db,
            rng=np.random.default_rng(seed),
            paper_water_margin=args.paper_water_margin,
            cluster_method=args.cluster_method,
        )
        print(
            f"[Data] Loaded {len(profiles)} real CRSS agents from paper data "
            f"(paper_water_margin={args.paper_water_margin}, "
            f"cluster_method={args.cluster_method})"
        )
    else:
        profiles = _create_synthetic_profiles(args.agents, seed)
        print(f"[Data] Created {len(profiles)} synthetic agents")

    if args.hindcast:
        profiles = reanchor_profiles(profiles)

    # Optional cluster rebalancing (matches LLM experiment)
    if args.rebalance_clusters:
        from collections import Counter
        before = Counter(p.cluster for p in profiles)

        target_dist = {
            "aggressive": 0.50,
            "forward_looking_conservative": 0.30,
            "myopic_conservative": 0.20,
        }
        rebalance_to_target(profiles, target_dist, rng=np.random.default_rng(seed))

        after = Counter(p.cluster for p in profiles)
        print(f"[Rebalance] Clusters: {dict(before)} → {dict(after)} (target: 50%-30%-20%)")

    # The action magnitude follows Hung and Yang (2021): per-agent mu, sigma
    # and grid step come from the profiles, not from persona config (the
    # former persona_scale / skill_magnitude bands were removed 2026-09-26).
    agent_config_path = base / "config" / "agent_types.yaml"

    # Create environment
    # PR-9 review P1-a: same flag, same getter as run_experiment.py, so both
    # arms of a comparison are guarded or unguarded TOGETHER.
    # run_ungoverned_experiment.py no longer has its own arm (irrigation
    # case-alignment, 2026-09) -- it is a thin wrapper that forwards to
    # run_experiment.py's main(), so it shares that arm's guard rather than
    # needing one of its own here. The .exists() check mirrors this
    # function's own handling of the config a few lines above — this runner
    # tolerates a missing agent_types.yaml, and asking the loader for a path
    # that is not there would fall back to a DIFFERENT file (the packaged
    # default), which must not be allowed to switch a guard on.
    from broker.utils.agent_config import AgentTypeConfig
    coupling_contract_active = (
        AgentTypeConfig.load(str(agent_config_path)).get_coupling_context_contract()
        if agent_config_path.exists() else False
    )
    if coupling_contract_active:
        print("[coupling] context_contract=True — get_agent_context() fails loud on a missing field")
    config_kwargs: Dict[str, Any] = {}
    if args.lb_non_ag_total_maf is not None:
        config_kwargs["lb_non_ag_total_maf"] = args.lb_non_ag_total_maf
    if args.lb_p56_in_tier is not None:
        config_kwargs["lb_p56_in_tier"] = args.lb_p56_in_tier
    if args.lb_return_flow_fraction is not None:
        config_kwargs["lb_return_flow_fraction"] = args.lb_return_flow_fraction
    if args.min_utilisation_fraction is not None:
        config_kwargs["min_utilisation_fraction"] = args.min_utilisation_fraction
    if args.powell_post2026_equalization is not None:
        config_kwargs["powell_post2026_equalization"] = args.powell_post2026_equalization
    if args.hindcast:
        config_kwargs.update(hindcast_config_kwargs())
    config = WaterSystemConfig(seed=seed, **config_kwargs)
    # WP2 review round 2 (LOW 3): hold_requests_fixed is for replays and
    # CPU diagnostics only (WaterSystemConfig's own docstring) -- this
    # runner never exposes a flag for it (test_hold_requests_fixed_
    # never_set_by_a_runner asserts that), so a True value here could only
    # come from a change to THIS line; fail loud rather than let a real
    # FQL run silently skip the WP2 keep-tracks-delivery reset.
    assert config.hold_requests_fixed is False, (
        "run_fql_baseline.py must never construct WaterSystemConfig with "
        "hold_requests_fixed=True -- that switch is for replays and CPU "
        "diagnostics only"
    )
    environment_class = HindcastAgentEnvironment if args.hindcast else IrrigationEnvironment
    env = environment_class(config, coupling_contract_active=coupling_contract_active)
    env.initialize_from_profiles(profiles)

    # Load CRSS precipitation if available
    if args.hindcast:
        env.load_crss_precipitation(str(HINDCAST_PRECIP_CSV))
    elif args.real and not args.from_logs:
        precip_csv = ref_dir / "CRSS_DB" / "CRSS_DB" / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv"
        if precip_csv.exists():
            env.load_crss_precipitation(str(precip_csv))
            print("[Data] Loaded real CRSS precipitation projections (2017-2060)")

    # Create FQL agents
    crss_db_dir_for_init = ref_dir / "CRSS_DB" / "CRSS_DB"
    try:
        fql_agents = create_fql_agents(
            profiles,
            seed=seed,
            fql_init=args.fql_init,
            fql_init_dir=Path(args.fql_init_dir),
            crss_db_dir=crss_db_dir_for_init,
        )
    except FQLCalibratedInitError as exc:
        print(f"[FQL-init] FATAL: {exc}")
        raise
    if args.fql_init == "calibrated":
        from collections import Counter
        src_counts = Counter(
            state.init_provenance.get("prev_action_source")
            for _, state in fql_agents.values()
        )
        if args.hindcast and src_counts != {"historical_annual_series": len(profiles)}:
            raise SystemExit(
                "--hindcast requires historical_annual_series as the previous-action "
                f"source for every agent; resolved sources: {dict(src_counts)}. "
                "QL_Div coupling files contain projection-year values."
            )
        print(
            f"[FQL-init] calibrated warm-start loaded for {len(fql_agents)} agents "
            f"from {args.fql_init_dir} (prev_action source: {dict(src_counts)})"
        )

    # Output directory — per-seed subdirectory under fql_raw/
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = base / "results" / "fql_raw" / f"seed{seed}"
    output_dir.mkdir(parents=True, exist_ok=True)
    _append_launch_command_line(
        output_dir, f"RunnerStarted: {run_started_at.strftime('%Y/%m/%d %H:%M:%S.%f')[:-3]}"
    )

    # Profile dict for fast lookup
    profiles_dict = {p.agent_id: p for p in profiles}

    # Run
    n_real = "real" if args.real else "synthetic"
    gov_mode = "NO governance" if args.no_governance else "WITH governance"
    print(
        f"\n--- FQL Baseline ({gov_mode}) | {len(profiles)} agents ({n_real}) "
        f"| {args.years} years | seed={seed} ---\n"
    )

    logs = run_simulation(
        env=env,
        fql_agents=fql_agents,
        profiles=profiles_dict,
        n_years=args.years,
        output_dir=output_dir,
        seed=seed,
        no_governance=args.no_governance,
        pf_prev_init=initial_pf_prev(profiles) if args.hindcast else None,
    )

    # Save simulation log
    if logs:
        df = pd.DataFrame(logs)
        if "precipitation_flag" in df.columns:
            # Re-review 2026-09-29 (NIT): a mix of int 0/1 (Upper Basin)
            # and None (Lower Basin, MEDIUM 4) upcasts a plain int column
            # to float64, rendering "1.0"/"0.0" in the CSV instead of
            # "1"/"0". pandas' nullable Int64 dtype keeps real values as
            # ints and a missing one blank, matching precipitation_mm's
            # own blank-for-missing behavior.
            df["precipitation_flag"] = df["precipitation_flag"].astype("Int64")
        csv_path = output_dir / "simulation_log.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        print(f"\n[Output] Saved {len(logs)} rows to {csv_path}")

        # Quick summary stats
        n_agents = df["agent_id"].nunique()
        n_years = df["year"].nunique()
        skill_dist = df["yearly_decision"].value_counts()
        block_rate = df["fql_blocked"].mean() * 100
        final_mead = df[df["year"] == df["year"].max()]["lake_mead_level"].iloc[0]
        mean_util = df["utilisation_pct"].mean()
        demand_ratio = (df["request"] / df["water_right"]).mean()

        print(f"\n--- Summary ---")
        print(f"  Agents: {n_agents}, Years: {n_years}")
        print(f"  Block rate: {block_rate:.1f}%")
        print(f"  Final Mead level: {final_mead:.1f} ft")
        print(f"  Mean utilisation: {mean_util:.1f}%")
        print(f"  Mean demand ratio: {demand_ratio:.3f}")
        print(f"  Skill distribution:")
        for skill, count in skill_dist.items():
            print(f"    {skill}: {count} ({count/len(df)*100:.1f}%)")

    # Reproducibility manifest (this runner has no ExperimentRunner/broker
    # behind it, so nothing else writes one). Kept minimal and specific to
    # what a bespoke FQL run needs to reproduce, rather than mirroring
    # run_experiment.py's broker-generated schema field-for-field.
    # paper_water_margin is recorded even for a synthetic (non --real) run,
    # since it is a resolved CLI value either way (create_profiles_from_data
    # only reads it on the --real path).
    #
    # WP5 review (item 3, round 3, 2026-09-30): dict construction below is
    # NOT wrapped in a try/except -- a KeyError/AttributeError there is a
    # programming bug (every field reads an already-computed value), and
    # should surface immediately rather than being laundered into a
    # "provenance write failed" warning. Only the ACTUAL write
    # (_write_reproducibility_manifest, a self-contained, directly
    # testable function) gets the raise-for-real/warn-for-synthetic
    # treatment: a --real run's manifest is the only record of
    # --fql-init, the data checksums, git HEAD/dirty and the resolved
    # water-system config for the run that just happened, so silently
    # continuing on a write failure would strand a scientifically
    # load-bearing artifact and never tell the caller. A synthetic (non
    # --real) run still only warns -- a smoke test losing its own
    # manifest is not comparable.
    manifest = {
        "runner": "run_fql_baseline",
        "seed": seed,
        "years": args.years,
        "real": bool(args.real),
        "from_logs": args.from_logs,
        "n_agents": len(profiles),
        "rebalance_clusters": bool(args.rebalance_clusters),
        "no_governance": bool(args.no_governance),
        "paper_water_margin": args.paper_water_margin,
        "paper_water_margin_applied": bool(args.real and not args.from_logs),
        "cluster_method": args.cluster_method,
        "cluster_method_applied": bool(args.real and not args.from_logs),
        # WP2 review round 2 (LOW 2, spec 7.2): the same per-agent
        # {agent_id: "grid"|"rescaled"} dict run_experiment.py writes,
        # None for a profile create_profiles_from_data never built
        # (synthetic --agents run, or --from-logs).
        "step_bin_source": {p.agent_id: p.step_bin_source for p in profiles},
        "step_bin_source_applied": bool(args.real and not args.from_logs),
        # WP2 review round 2 (LOW 3): the REAL value, read from the
        # environment's own config (asserted False right after
        # construction above) rather than a literal -- if a future
        # change ever threads an override through, the manifest
        # reflects reality instead of a stale hard-coded False.
        "hold_requests_fixed": env.config.hold_requests_fixed,
        # Re-review 2026-09-29 round 4 (MEDIUM 4; spec items 25-27):
        # same treatment as hold_requests_fixed just above -- read from
        # the environment's own config, not a literal, so the manifest
        # reflects whatever WaterSystemConfig actually resolved to.
        "powell_release_mode": env.config.powell_release_mode,
        "powell_post2026_equalization": env.config.powell_post2026_equalization,
        "lb_non_ag_total_maf": env.config.lb_non_ag_total_maf,
        # Item 36e (2026-10-05); Opus review P2-2: 0.0 (default,
        # byte-identical) unless --lb-return-flow-fraction set it.
        "lb_return_flow_fraction": env.config.lb_return_flow_fraction,
        # 2026-10-06 CPU rerun finding: 0.10 (default, byte-identical)
        # unless --min-utilisation-fraction set it. Also present nested
        # under water_system_config below (_FQL_WATER_KEYS reads it from
        # there); recorded top level too for human-readable parity with
        # lb_return_flow_fraction just above.
        "min_utilisation_fraction": env.config.min_utilisation_fraction,
        # WP5 essentials (irrigation_v3_spec_2026-09-28.md section 5,
        # 2026-09-30): "the manifest records everything that identifies
        # the reference: --fql-init, the table directory, the
        # water-system config fields and the seed" -- these three
        # complete that set (hold_requests_fixed/powell_*/lb_non_ag_
        # total_maf above were already there): ub_supply_mode is spec
        # 5.0's own explicit requirement ("the v3 water system of WP1
        # and WP1b, ub_supply_mode = subbasin"), and its variant and
        # the Lower Basin priority mode are the other two config
        # fields that change which v3 water system this run used.
        "ub_supply_mode": env.config.ub_supply_mode,
        "ub_subbasin_supply_variant": env.config.ub_subbasin_supply_variant,
        "lb_priority_mode": env.config.lb_priority_mode,
        "lb_p56_in_tier": env.config.lb_p56_in_tier,
        "fql_init": args.fql_init,
        "fql_init_dir": args.fql_init_dir if args.fql_init == "calibrated" else None,
        # Cheap reproducibility provenance (2026-09-27 review): numpy's
        # RNG/floating-point behavior can shift across versions, and
        # the FQL calibrated warm-start's file parsing depends on
        # numpy's np.loadtxt. sys.executable matters concretely here:
        # this machine has two unrelated Python installs on PATH
        # (`python` -> C:\Python314, 3.14.0, numpy 2.4.2; `python3`
        # -> a different 3.11.9 install, numpy 2.2.4), and re-running
        # a reference under the wrong one reproduces the same
        # simulation at ULP-level-different floating point values
        # (see TestZeroInitRealDataRegressionAgainstPrimaryClone).
        "sys_executable": sys.executable,
        "numpy_version": np.__version__,
        "python_version": sys.version.split()[0],
        # WP5 review (item 2, 2026-09-30): git HEAD/dirty at launch,
        # the sha256 of every ref/CRSS_DB input this run actually
        # read (only meaningful for --real; the dict is still written
        # for a synthetic run, with every value None), the pinned v3
        # data checksums IrrigationEnvironment itself validated at
        # load, and the FULL resolved water-system config -- "the
        # water-system config fields" WP5's own essentials ask for,
        # not just the three named individually above.
        **_git_provenance(PROJECT_ROOT),
        "crss_db_input_checksums": (
            _crss_db_input_checksums(crss_db_dir_for_init)
            if args.real else {}
        ),
        "pinned_v3_data_checksums": _pinned_v3_data_checksums(
            env.config.ub_subbasin_supply_variant
        ),
        "water_system_config": dataclasses.asdict(env.config),
    }
    if args.fql_init == "calibrated":
        from collections import Counter
        from datetime import timezone
        # Directory name + Q-table date range (2026-09-27 decision):
        # the provenance trail for WHICH calibration snapshot was
        # used, since Initial_Files ships several undocumented
        # variants with different Q_Table mtimes (see --fql-init-dir
        # help / create_fql_agents docstring).
        manifest["fql_init_dir_name"] = Path(args.fql_init_dir).name
        q_mtimes = [
            p.stat().st_mtime for p in Path(args.fql_init_dir).glob("Q_Table_*.txt")
        ]
        if q_mtimes:
            manifest["fql_init_dir_q_table_date_range"] = [
                datetime.fromtimestamp(min(q_mtimes), tz=timezone.utc).date().isoformat(),
                datetime.fromtimestamp(max(q_mtimes), tz=timezone.utc).date().isoformat(),
            ]
        manifest["fql_init_agents_loaded"] = len(fql_agents)
        manifest["fql_init_prev_action_source_counts"] = dict(Counter(
            state.init_provenance.get("prev_action_source")
            for _, state in fql_agents.values()
        ))
        # Per-agent sha256 of each loaded Q_Table/count/P_Tran file,
        # plus the resolved prev_action and its source -- see
        # create_fql_agents()/FQLState.init_provenance.
        manifest["fql_init_per_agent"] = {
            aid: state.init_provenance
            for aid, (_, state) in fql_agents.items()
        }
    if args.hindcast:
        git_info = _git_provenance(PROJECT_ROOT)
        manifest["hindcast"] = hindcast_provenance(
            env.config, fql_init=args.fql_init, fql_init_dir=args.fql_init_dir,
            code_commit=git_info["git_head"], git_dirty=git_info["git_dirty"],
        )
    _write_reproducibility_manifest(manifest, output_dir, is_real=bool(args.real))

    run_finished_at = datetime.now()
    _append_launch_command_line(
        output_dir, f"RunnerFinished: {run_finished_at.strftime('%Y/%m/%d %H:%M:%S.%f')[:-3]}"
    )
    _append_launch_command_line(
        output_dir, f"RunnerWallSeconds: {(run_finished_at - run_started_at).total_seconds()}"
    )

    print(f"\n--- FQL Baseline Complete! Results in {output_dir} ---")


def parse_args():
    p = argparse.ArgumentParser(
        description="FQL Baseline Runner — Hung & Yang (2021) for Nature Water comparison"
    )
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--hindcast", action="store_true", help="Use the observed hindcast window and starting state")
    p.add_argument("--agents", type=int, default=5,
                   help="Number of synthetic agents (ignored if --real)")
    p.add_argument("--real", action="store_true",
                   help="Use real 78-agent CRSS data from paper")
    p.add_argument("--paper-water-margin", type=float, default=0.4,
                   help="Water-right history-anchor margin, same meaning and default "
                        "as run_experiment.py --paper-water-margin, on [0, 1]. Item "
                        "36f/36g (2026-10-05): basin-specific since then -- Lower "
                        "Basin water_right = grid_top_af alone; Upper Basin "
                        "water_right = (1 + paper_water_margin) * peak_obs_af alone "
                        "(no grid-top term). Only affects --real profiles. Recorded "
                        "in reproducibility_manifest.json.")
    p.add_argument("--lb-non-ag-total-maf", type=float, default=None,
                   help="LB non-farm total (M&I + tribal + CAP + system losses, MAF/yr). "
                        "Default: WaterSystemConfig's own default (5.2, the record-"
                        "implied value at lb_return_flow_fraction=0.0 -- see "
                        "analysis/hindcast_v3.py (record_implied_non_ag)). A "
                        "--lb-return-flow-fraction sensitivity run (below) MUST pass "
                        "the record-implied value for that SAME fraction here (derived "
                        "first via 'python analysis/hindcast_v3.py "
                        "--lb-return-flow-fraction f'; see the runbook's return-flow "
                        "sensitivity pair) -- the 5.2 default was derived at f=0.0, and "
                        "pairing a non-zero f with the f=0.0 constant double-counts "
                        "water the fraction already credits back to Mead. Recorded in "
                        "reproducibility_manifest.json.")
    p.add_argument("--lb-p56-in-tier", choices=["zero", "proportional"], default=None,
                   help="Item 46: P5/P6 availability in tier years; zero by default, "
                        "proportional for an SI sensitivity, recorded in the manifest.")
    p.add_argument("--lb-return-flow-fraction", type=float, default=None,
                   help="Item 36e (2026-10-05) CPU sensitivity: the share of the LB "
                        "agricultural draw treated as reused downstream (e.g. "
                        "credited toward the Mexico delivery) instead of charged "
                        "against Mead's outflow, on [0, 0.5]. Default: "
                        "WaterSystemConfig's own default (0.0, byte-identical). "
                        "Recorded in reproducibility_manifest.json.")
    p.add_argument("--min-utilisation-fraction", type=float, default=None,
                   help="2026-10-06 CPU rerun finding (spec item 36k): the minimum-use "
                        "floor, as a fraction of each agent's water right, on [0, 1]. "
                        "Default: WaterSystemConfig's own default (0.10, byte-"
                        "identical). CPU sensitivities at 0 and 0.05 (provenance C6b). "
                        "Recorded in reproducibility_manifest.json.")
    p.add_argument("--powell-post2026-equalization", choices=["hold_2026", "extend_slope"], default=None,
                   help="How the Equalization elevation is extended past 2026 (item "
                        "36c), same meaning and default as run_experiment.py's own "
                        "WaterSystemConfig default ('extend_slope'). Default: "
                        "WaterSystemConfig's own default (byte-identical). Recorded "
                        "in reproducibility_manifest.json.")
    p.add_argument("--cluster-method", type=str, default="hy2021",
                   choices=["hy2021", "legacy_centroid"],
                   help="How each real CRSS agent's cluster (aggressive / "
                        "forward_looking_conservative / myopic_conservative) is "
                        "assigned, same meaning and default as run_experiment.py "
                        "--cluster-method. Only affects the --real path "
                        "(create_profiles_from_data): on --real, this baseline's "
                        "FQL Q-learning dynamics use each agent's own calibrated "
                        "mu/sigma/alpha/gamma/epsilon/regret directly and ignore "
                        "cluster, but 'cluster' and 'aca_label' (derived from "
                        "cluster) are still written to simulation_log.csv, so "
                        "--cluster-method=legacy_centroid is needed to reproduce "
                        "those two columns byte-identically against a corpus "
                        "generated before --cluster-method existed (e.g. the "
                        "431adb5e corpus). This flag has NO effect on --from-logs: "
                        "that path reconstructs each profile's cluster from the "
                        "loaded simulation_log.csv's own 'cluster' column (whatever "
                        "cluster_method the ORIGINAL run used), and, unlike --real, "
                        "it has no per-agent calibrated params to read from a log "
                        "file, so it takes its FQL mu/sigma/alpha/gamma/epsilon/"
                        "regret FROM CLUSTER_CONFIGS[cluster] instead -- cluster "
                        "genuinely drives FQL dynamics on that path, just not via "
                        "this flag. Recorded in reproducibility_manifest.json.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", type=str, default=None)
    p.add_argument("--rebalance-clusters", action="store_true",
                   help="Rebalance cluster assignment to 50%%-30%%-20%%")
    p.add_argument("--no-governance", action="store_true",
                   help="Skip all governance validators (raw FQL behavior)")
    p.add_argument("--from-logs", type=str, default=None,
                   help="Reconstruct profiles from existing simulation_log.csv directory "
                        "(e.g., results/production_v20_42yr_seed42). Use when ref/ data is unavailable.")
    p.add_argument("--fql-init", type=str, default="calibrated",
                   choices=["calibrated", "zero"],
                   help="Q/count/P_Tran warm-start. 'calibrated' (default) "
                        "loads each agent's Hung & Yang end-of-2018 "
                        "Q_Table/count/P_Tran tables from --fql-init-dir and "
                        "sets prev_action/prev_diversion from the observed "
                        "2017-to-2018 diversion change for the Lower Basin, "
                        "or ZERO for the Upper Basin (H&Y's own yi==0 "
                        "override -- see resolve_prev_action), converted to "
                        "H&Y's diversion units (WP5 spec 5.4); requires real "
                        "CRSS agent ids (--real or --from-logs against a real "
                        "run) with matching files, and raises rather than "
                        "silently zero-filling a missing/corrupt file. 'zero' "
                        "zero-initialises the Q/count/P_Tran tables "
                        "(FQLState.initialize()'s defaults) and sets "
                        "prev_action=0.0 with prev_diversion = "
                        "actual_2018_diversion (converted the same way) -- "
                        "required for synthetic (non --real) profiles. "
                        "NEITHER mode is byte-identical to any historical "
                        "commit before WP5 (irrigation_v3_spec_2026-09-28.md "
                        "section 5, 2026-09-30): the request-setting "
                        "mechanism itself changed for both init modes (no "
                        "more execute_skill() redraw; Div_t is the base, not "
                        "the provisional delivery) -- see "
                        "docs/irrigation_model_caveats.md item 11.")
    p.add_argument("--fql-init-dir", type=str,
                   default=str(PROJECT_ROOT / "ref" / "CRSS_DB" / "CRSS_DB" / "Initial_Files" / "All-1109"),
                   help="Directory holding Q_Table_<agent>.txt / count_<agent>.txt / "
                        "P_Tran_<agent>.txt for --fql-init calibrated. Default: "
                        "ref/CRSS_DB/CRSS_DB/Initial_Files/All-1109 (2026-09-27 "
                        "decision), resolved against PROJECT_ROOT like the other "
                        "ref/ paths (--real's params_csv / crss_db). Rationale: "
                        "the per-agent FQL parameters loaded from "
                        "ALL_colorado_ABM_params_cal_1108.csv are dated 2020-11-08, "
                        "and All-1109 is the only Initial_Files snapshot written on "
                        "that same calibration day (all 78 Q tables dated "
                        "2020-11-08) -- so parameters and learned tables come from "
                        "one calibration run. 'All' (Q tables dated 2021-05-28, "
                        "seven months later, no matching parameter file shipped in "
                        "this release) is what the authors' own "
                        "initialization_ABM_CRSS_v3.py copies; 'All-WRR' is a "
                        "composite of the 2020-09-13 Upper Basin and 2020-10-20 "
                        "Lower Basin batches. Item 36j (2026-10-05 design-basis audit + fix "
                        "proposals, PI decision): All-1109 is KEPT, on the shared-"
                        "calibration-date reason above; 'All' is run as a CPU sensitivity "
                        "(All-WRR, All-0913, All-1020, All-1022 stay available as further "
                        "sensitivities), not silently dropped.")
    return p.parse_args()


if __name__ == "__main__":
    main()
