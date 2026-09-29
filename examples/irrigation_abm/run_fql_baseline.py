#!/usr/bin/env python3
"""
FQL Baseline Runner — Hung & Yang (2021) Q-Learning for Nature Water comparison.

Runs the same 78-agent × 42-year irrigation simulation as run_experiment.py,
but replaces LLM skill selection with FQL Q-learning.  Everything else is
identical: same IrrigationEnvironment, same execute_skill() Hung and Yang step
sampling, same 12 governance validators.

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
import json
import os
import random
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
    update_consecutive_tracker,
)
from broker.interfaces.skill_types import ApprovedSkill

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
    <Index>_QL_Div_2018.csv`` and ``QL_Div_y0 = <Index>_QL_Div_2017.csv``
    (lines 505-508 for LB, 618-621 for UB), then computes
    ``a_t = Div_req_y0 - Div_y0`` per agent (lines 532-537, 640-647) --
    i.e. the observed 2017-to-2018 diversion change. That value becomes
    ``prev_action`` for the first FQL step (our FQLState.prev_action,
    used as ``a_t`` in the reward/posterior update on year 1). The same
    2017 value also becomes ``prev_diversion`` (P1-b fix, 2026-09-27
    review): H&Y's first Q-update reads s_0 = state(Div_y0) = state(2017)
    and s_deviation = Div_y - (Div_y0 + a_t) = 2018 - (2017 + (2018 -
    2017)) = 0 exactly -- no regret penalty on year 1 -- which only
    holds if the caller sets prev_diversion to the 2017 value returned
    here, not 2018.

    Note (v): exact ties (actual_2017_diversion == actual_2018_diversion,
    6 of the 78 real agents, all in the NM/New Mexico state group) give
    a_t == 0.0 exactly. H&Y's own ``a_t_i = int(a_t > 0)`` (coupling
    script line 212) maps that to the DECREASE index (0) deliberately --
    our ``a_t_idx = int(state.prev_action > 0)`` in fql.py's step() does
    the same -- this is not a bug to special-case.

    Tries Hung & Yang's own per-agent QL_Div_2017/2018.csv files first
    (via ``_load_ql_div_2017_2018``); when unavailable (files genuinely
    absent), falls back to the historical annual series already loaded
    by ``create_profiles_from_data`` (``actual_2018_diversion -
    actual_2017_diversion``, same series the paper's water-right
    history-anchor uses; for UB agents both years are split across a
    state group by the same per-agent ratio, an approximation of H&Y's
    own ``Within_Group_Dist`` -- see the ``actual_2017_diversion``
    assignment in ``create_profiles_from_data``).

    Returns (prev_action, prev_diversion_2017, source) where source is
    one of "ql_div_csv" or "historical_annual_series". Raises
    FQLCalibratedInitError (v)/2026-09-27 review) when NEITHER source has
    data for this agent -- calibrated mode never silently defaults
    prev_action/prev_diversion to 0.0; use --fql-init zero for profiles
    without CRSS historical data (e.g. synthetic agents).
    """
    ql = _load_ql_div_2017_2018(profile.agent_id, profile.basin, crss_db_dir)
    if ql is not None:
        div_2017, div_2018 = ql
        return div_2018 - div_2017, div_2017, "ql_div_csv"

    div_2018 = profile.actual_2018_diversion
    div_2017 = profile.actual_2017_diversion
    if div_2018 is not None and div_2017 is not None:
        return float(div_2018) - float(div_2017), float(div_2017), "historical_annual_series"

    raise FQLCalibratedInitError(
        f"[{profile.agent_id}] fql_init='calibrated' could not resolve "
        f"prev_action/prev_diversion: no QL_Div_2017/2018.csv coupling "
        f"files and no historical actual_2017_diversion/"
        f"actual_2018_diversion on the profile. Use --fql-init zero for "
        f"profiles without CRSS historical data (e.g. synthetic agents)."
    )


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
    - prev_diversion: under "zero", actual_2018_diversion (or 80% of
      water_right) -- unchanged from before 2026-09-27. Under
      "calibrated" (P1-b fix, 2026-09-27 review), the OBSERVED 2017
      diversion (resolve_prev_action's prev_diversion_2017), matching
      H&Y's first Q-update, which credits state(2017) and gives an exact
      zero reward deviation on year 1 -- not the 2018 value.
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
            Lower Basin batches. To be confirmed with the model's
            authors; the other snapshots are reported as a sensitivity
            in the SI, not silently dropped.
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
            # WP2 review round 1 (LOW 8): demand_per_grid_unit is set by
            # the SAME create_profiles_from_data --real path as
            # div_states_grid/bin_size_af just checked above, so a
            # profile that passed that check but has no
            # demand_per_grid_unit is a wiring defect, not a legitimate
            # "assume no conversion" case -- no silent `or 1.0` default.
            if not p.demand_per_grid_unit:
                raise ValueError(
                    f"[{p.agent_id}] fql_init='calibrated' requires "
                    f"demand_per_grid_unit on the profile (set by "
                    f"create_profiles_from_data alongside bin_size_af); "
                    f"got {p.demand_per_grid_unit!r}."
                )
            # WP2 (spec 2.3): bin_size_af is now UB-converted (k=0.5); undo
            # that here so the FQL grid-state math keeps reading H&Y's
            # original diversion-unit grid, byte-identical to pre-WP2.
            hy_bin_size = float(p.bin_size_af) / float(p.demand_per_grid_unit)
            state = FQLState(
                state_bounds=np.asarray(p.div_states_grid, dtype=float),
                state_grid_mode="hy_exact",
                hy_bin_size=hy_bin_size,
            )

            q_table, count_table, p_transition, file_hashes = load_calibrated_tables(
                agent_id=p.agent_id,
                init_dir=fql_init_dir,
                config=agent_config,
            )
            state.q_table = q_table
            state.count_table = count_table
            state.p_transition = p_transition

            # P1-b fix (2026-09-27 review): prev_action AND the 2017
            # diversion it was derived from must come from the same
            # resolve_prev_action() call, so prev_diversion (set below,
            # after state.initialize()) and prev_action always agree on
            # which "2017" value was used (ql_div_csv vs the historical
            # series can differ slightly if the former ever becomes
            # available).
            prev_action, prev_diversion_2017, prev_action_source = resolve_prev_action(
                p, crss_db_dir
            )
            state.prev_action = prev_action
            state.init_provenance = {
                "fql_init": "calibrated",
                "fql_init_dir": str(fql_init_dir),
                "q_table_sha256": file_hashes["q_table"],
                "count_sha256": file_hashes["count"],
                "p_transition_sha256": file_hashes["p_transition"],
                "prev_action": prev_action,
                "prev_action_source": prev_action_source,
                "prev_diversion_2017": prev_diversion_2017,
                "state_grid_mode": "hy_exact",
                "hy_bin_size": hy_bin_size,
            }
        else:
            q_grid_top = p.grid_top_af if p.grid_top_af else p.water_right
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
            # P1-b fix (2026-09-27 review): H&Y's first Q-update credits
            # s_0 = state(Div_y0) = state(2017 diversion) and gives a
            # reward deviation of exactly 0 (Div_y - (Div_y0 + a_t) =
            # 2018 - (2017 + (2018-2017)) = 0) -- both only hold if
            # prev_diversion is the 2017 value, not 2018. The
            # environment's own current_diversion for year 1 stays the
            # 2018 value (env.initialize_from_profiles uses
            # actual_2018_diversion, unchanged), matching H&Y's Div_y.
            state.prev_diversion = prev_diversion_2017
            state.prev_diversion_request = init_div + state.prev_action
        else:
            # Unchanged from before 2026-09-27 (legacy "zero" behavior).
            state.prev_diversion = init_div

        rng = np.random.default_rng(seed + i)
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
    """Run the dispatched irrigation validators (ALL_IRRIGATION_CHECKS,
    7 as of the 2026-09-25 supply-side redesign -- drought_severity_check,
    magnitude_cap_check and compact_allocation_check were removed by F04, and
    demand_floor_stabilizer and demand_ceiling_stabilizer were retired from
    dispatch; see irrigation_validators.py)
    on a proposed skill.

    NOTE: The LLM path uses broker's RejectionHandler which re-invokes the LLM
    on rejection. Since FQL has no LLM, we use a deterministic 2-tier fallback:
    1. maintain_demand (neutral fallback, matches LLM REJECTED default)
    2. decrease_demand (last resort, always physically valid)

    Args:
        skill_name: Proposed skill name.
        context: Validation context (from env.get_agent_context + extras).

    Returns:
        (is_valid, final_skill_name) — if blocked, tries fallback.
    """
    results = []
    for check in ALL_IRRIGATION_CHECKS:
        results.extend(check(skill_name, [], context))

    blocked = any(not r.valid for r in results)
    if not blocked:
        return True, skill_name

    # Fallback 1: maintain_demand (always valid except at zero escape)
    results2 = []
    for check in ALL_IRRIGATION_CHECKS:
        results2.extend(check("maintain_demand", [], context))
    if all(r.valid for r in results2):
        return True, "maintain_demand"

    # Last resort: decrease_demand (should always pass)
    return True, "decrease_demand"


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

            # Get agent context (same as LLM pre_year hook)
            ctx = env.get_agent_context(aid)
            agent_state = env.get_agent_state(aid)
            current_diversion = ctx["current_diversion"]

            # ── FQL step: get continuous action ──
            # Preceding factor: use persistence assumption f_next = f_t
            pf = ctx["preceding_factor"]
            preceding = (pf, pf)

            action = fql_agent.step(fql_state, current_diversion, preceding)

            # ── Map to 2-action model (faithful to FQL) ──
            raw_skill = fql_action_to_skill(action)

            # ── Validate and fallback (skip if --no-governance) ──
            if no_governance:
                final_skill = raw_skill
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
                }
                was_valid, final_skill = validate_skill(raw_skill, val_context)
                was_blocked = (final_skill != raw_skill)
                if was_blocked:
                    year_blocked += 1

            # ── Execute skill via environment (same Gaussian magnitude) ──
            approved = ApprovedSkill(
                skill_name=final_skill,
                agent_id=aid,
                approval_status="APPROVED",
            )
            exec_result = env.execute_skill(approved)
            state_changes = exec_result.state_changes if exec_result else {}

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
                "raw_skill": raw_skill,
                "action": action,
                "was_blocked": was_blocked,
                "wsa_label": compute_wsa_label(ctx["drought_index"]),
                "aca_label": compute_aca_label(profile.cluster),
                "magnitude_pct": state_changes.get("magnitude_pct_applied"),
                "magnitude_pct_sampled": state_changes.get("magnitude_pct_sampled"),
                "magnitude_af": state_changes.get("magnitude_af"),
                "magnitude_class": state_changes.get("magnitude_class"),
                "is_exploration": state_changes.get("is_exploration", False),
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
        )
        profile.narrative_persona = build_narrative_persona(profile, rng)
        profiles.append(profile)

    return profiles


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
    config = WaterSystemConfig(seed=seed)
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
    env = IrrigationEnvironment(config, coupling_contract_active=coupling_contract_active)
    env.initialize_from_profiles(profiles)

    # Load CRSS precipitation if available
    if args.real and not args.from_logs:
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
    # only reads it on the --real path). Never fails the run over a
    # provenance write.
    try:
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
        with open(output_dir / "reproducibility_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"[Provenance] WARNING: could not write reproducibility_manifest.json: {e}")

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
    p.add_argument("--agents", type=int, default=5,
                   help="Number of synthetic agents (ignored if --real)")
    p.add_argument("--real", action="store_true",
                   help="Use real 78-agent CRSS data from paper")
    p.add_argument("--paper-water-margin", type=float, default=0.4,
                   help="Water-right history-anchor margin, same meaning and default "
                        "as run_experiment.py --paper-water-margin, on [0, 1]: "
                        "water_right = min(grid_top_af, (1 + paper_water_margin) * "
                        "peak_obs_af). Only affects --real profiles. Recorded in "
                        "reproducibility_manifest.json.")
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
                   help="Q/count/P_Tran warm-start (fidelity fix, 2026-09-27). "
                        "'calibrated' (default) loads each agent's Hung & Yang "
                        "end-of-2018 Q_Table/count/P_Tran tables from "
                        "--fql-init-dir and sets prev_action from the observed "
                        "2017-to-2018 diversion change, matching "
                        "ABM_CRSS_coupling.py's Q_learning(); requires real "
                        "CRSS agent ids (--real or --from-logs against a real "
                        "run) with matching files, and raises rather than "
                        "silently zero-filling a missing/corrupt file. 'zero' "
                        "reproduces the pre-fix behavior byte for byte "
                        "(FQLState.initialize()'s zero tables, prev_action=0.0) "
                        "-- required for synthetic (non --real) profiles.")
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
                        "Lower Basin batches. This choice is to be confirmed with "
                        "the model's authors; the other snapshots (All, All-WRR, "
                        "All-0913, All-1020, All-1022) are reported as a "
                        "sensitivity in the SI, not silently dropped.")
    return p.parse_args()


if __name__ == "__main__":
    main()
