"""R29 -- constant-demand KGE null + basin-demand descriptive stats + carried
basin-demand KGE. CPU-only, existing runs only, no LLM calls.

PART (a) -- constant-demand null for the Mead-elevation KGE
  For each seed 42-46 and each "source" (fql_matched, governed -- gemma3:4b
  strict, faf1bb12): seed a fresh `IrrigationEnvironment`
  (examples/irrigation_abm/irrigation_env.py, imported read-only) with the
  TRUE pre-simulation diversion baseline (`actual_2018_diversion` per agent
  -- see INIT_DIVERSION below, NOT year-1's already-decided request; static
  water_right/basin/cluster read from that source's year-1
  simulation_log.csv row), load the SAME real CRSS winter-precipitation
  file the production runs used
  (`ref/CRSS_DB/CRSS_DB/HistoricalData/PrismWinterPrecip_ST_NOAA_Future.csv`
  -- CORRECTION (2026-09-21 review round): an earlier draft of this
  docstring claimed both LAUNCH_COMMAND.txt logs carry a SHA256
  verification block; false, checked exactly. fql_raw_norebalance_
  faf1bb12/seed42/LAUNCH_COMMAND.txt is 3 lines only (the command +
  Started/Finished timestamps), no hash block at all.
  strict_42yr_gemma3_4b_faf1bb12/seed42/LAUNCH_COMMAND.txt DOES carry a
  SHA256 block, and its logged hash for this file (`3094b4c5...`)
  matches the live file's own SHA256 (`3094b4c5...`, computed directly,
  not assumed) -- so the precip-file identity is confirmed via the
  strict run's hash plus both runs' `--real` flag (which is what
  actually selects this code path in `run_fql_baseline.py`/
  `run_experiment.py`; the hash is corroborating evidence for the
  strict run specifically, not proof for the FQL run, which has no hash
  to check), then step 42 years, holding every agent's
  request at ITS OWN recorded year-1 value (from the CSV) for the ENTIRE
  horizon via `env.update_agent_request(agent_id, year1_value)` called
  every year (NOT `env.execute_skill()` -- see the replayability finding
  below).

  REPLAYABILITY FINDING (why this is safe, verified by reading the source
  AND by empirical test, not assumed): `IrrigationEnvironment.__init__`
  gives itself its OWN `np.random.default_rng(config.seed)` instance
  (`self.rng`), separate from the global `random`/`np.random` state the
  CLI runners seed. Grepping the whole file for `self.rng.` shows exactly
  3 call sites: (1) `initialize_synthetic()`'s one-time cluster shuffle --
  unused here, this script never calls `initialize_synthetic()`; (2)
  `execute_skill()`'s Gaussian magnitude sampling for every skill EXCEPT
  `maintain_demand`; (3) `_generate_precipitation()`'s SYNTHETIC FALLBACK
  noise, dead code whenever real CRSS data is loaded (`self._crss_precip
  is not None`). `_generate_lake_mead_level()` (the mass-balance function)
  never touches `self.rng` at all -- it is a pure deterministic function
  of the PRIOR year's agent diversions and the precip history. Since this
  script drives demand via `update_agent_request()` directly (never
  `execute_skill()`), and loads real CRSS precip, `self.rng` is NEVER
  consumed on this code path.

  A first attempt seeded the environment's pre-simulation diversion state
  with year-1's RECORDED (already-decided) request instead of the true
  pre-simulation `actual_2018_diversion` baseline -- this produced a
  0.7-3.4 ft year-1 Mead-elevation error that does NOT fully wash out for
  roughly 10 years (caught by the validation check below, which failed
  8/10 (source, seed) pairs; not silently accepted). Root cause: year 1's
  Mead level is a function of PRE-simulation diversions
  (`initialize_from_profiles()`'s `actual_2018_diversion`), not year 1's
  own decision -- using the decided value instead was simply the wrong
  input. Fix: `INIT_DIVERSION` calls the SAME production function,
  `examples/irrigation_abm/irrigation_personas.py::create_profiles_from_data()`,
  with the SAME calibrated-params/CRSS_DB paths the real runs used, to
  recover the exact `actual_2018_diversion` per agent (`rng` only affects
  crop-type/persona/cluster assignment, never used by this script, so it
  is not seed-dependent and is computed once, cached, for all 5 seeds).
  With this fix, replaying FQL-matched seed 42's own ACTUAL year-by-year
  requests through this harness reproduced its recorded lake_mead_level
  to EXACT float equality for every one of the 10 years spot-checked
  before this script was finalized (diff=0.0000 ft) -- not an
  approximation, a byte-exact replay.

  EMPIRICAL VALIDATION (still run every time, not just checked once by
  hand): before trusting any null number, this script replays each
  source's OWN ACTUAL recorded year-by-year requests (not held constant
  -- literally each year's real value from its simulation_log.csv)
  through the SAME harness and compares the resulting Lake Mead trajectory
  to that source's own recorded `lake_mead_level` column, per seed. If the
  RMSE of that replay-vs-actual check exceeds 0.5 ft for a given (source,
  seed), this script prints exactly why, writes a `row_type=skipped`
  record, and does NOT compute or report any null-KGE number for that
  pair -- never an approximated one.

PART (b) -- basin-demand descriptive stats
  Per (arm, model, seed) for all 4 LLM arms (both models) plus FQL matched/
  rebalanced: mean/sd/min/max of yearly total basin demand (sum of
  `request` across all agents, per year, over the 42 years), the share of
  years with demand > `DEMAND_CEILING_AF` (imported from
  examples/irrigation_abm/validators/irrigation_validators.py, not
  hardcoded: 6,000,000 acre-ft), and the mean signed distance to that
  ceiling (demand - ceiling, acre-ft; negative = under the ceiling).

PART (c) -- basin-demand KGE carried from r28 (not recomputed)
  Per-seed (row_type=irr_pair) and per-arm (row_type=irr_arm_summary) basin-
  demand KGE/RMSE rows, read VERBATIM from
  out/r28_trajectory_vs_traditional.csv (series=basin_demand), so a future
  Table 1 pass can cite this script for the basin-demand KGE column without
  re-deriving it.

COMPLETENESS GATE
  Missing run dir/simulation_log.csv -> row_type=skipped, printed reason,
  excluded from aggregates. The null-replay validation check (part a) is
  its own gate, separate from file-completeness: a run can be file-complete
  and still fail the replay-fidelity check, in which case part (a) is
  skipped for that (source, seed) with the RMSE reported, never masked.

OUTPUTS
  out/r29_kge_null_and_demand.csv -- row_type in {skipped,
    null_replay_validation, null_series, null_kge, null_kge_summary,
    demand_stats, demand_stats_summary, basin_demand_kge,
    basin_demand_kge_summary}.
  out/r29_kge_null_and_demand.md -- GENERATED by render_md() directly from
    that same `rows` list.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r29_kge_null_and_demand.py
"""
from __future__ import annotations

import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r28_trajectory_vs_traditional as R28  # noqa: E402  READ-ONLY: reuses its
                                              # KGE/yearly-series helpers, never modified.

sys.path.insert(0, C.REPO)
import numpy as np  # noqa: E402
from examples.irrigation_abm.irrigation_env import (  # noqa: E402
    IrrigationEnvironment, WaterSystemConfig,
)
from examples.irrigation_abm.irrigation_personas import (  # noqa: E402
    create_profiles_from_data,
)
from examples.irrigation_abm.validators.irrigation_validators import (  # noqa: E402
    DEMAND_CEILING_AF,
)

PRECIP_CSV = os.path.join(C.REPO, "ref", "CRSS_DB", "CRSS_DB", "HistoricalData",
                           "PrismWinterPrecip_ST_NOAA_Future.csv")
PARAMS_CSV = os.path.join(C.REPO, "ref", "RL-ABM-CRSS", "ALL_colorado_ABM_params_cal_1108.csv")
CRSS_DB_DIR = os.path.join(C.REPO, "ref", "CRSS_DB", "CRSS_DB")
N_YEARS = 42

# True pre-simulation initial diversion per agent (actual_2018_diversion,
# Hung & Yang 2021 historical baseline -- falls back to water_right*0.8
# where 2018 data is missing, exactly as `initialize_from_profiles()`
# does). Computed ONCE, cached: `create_profiles_from_data()`'s `rng`
# argument only affects crop-type/persona/cluster assignment, which this
# script never uses (it bypasses execute_skill() entirely) -- so this is
# NOT seed-dependent and a fixed rng is fine to reuse across all 5 seeds.
# THIS is the piece that makes the replay exact: seeding with year-1's
# already-DECIDED request (what an earlier draft of this script did)
# instead of the true pre-simulation baseline produced a 0.7-3.4 ft
# year-1 Mead-level error that does not fully wash out for ~10 years --
# caught by the fidelity check below, not assumed away.
def _load_init_diversion() -> dict:
    if not (os.path.isfile(PARAMS_CSV) and os.path.isdir(CRSS_DB_DIR)):
        raise PrepError(f"missing calibrated params CSV ({PARAMS_CSV}) or CRSS_DB dir "
                         f"({CRSS_DB_DIR}) -- cannot reconstruct the true pre-simulation "
                         f"diversion baseline; the environment cannot be faithfully "
                         f"replayed offline without this data")
    profiles = create_profiles_from_data(
        params_csv_path=PARAMS_CSV, crss_db_dir=CRSS_DB_DIR,
        rng=np.random.default_rng(0),
    )
    out = {}
    for p in profiles:
        wr = getattr(p, "water_right", 100_000.0)
        actual = getattr(p, "actual_2018_diversion", None)
        out[p.agent_id] = float(actual) if actual is not None else float(wr) * 0.8
    return out


INIT_DIVERSION = _load_init_diversion()

# "governed" source for the null = gemma3:4b strict (faf1bb12) -- the
# original/main corpus, matching r28.IRR_MODELS[0].
GOVERNED_MODEL, GOVERNED_COMMIT = R28.IRR_MODELS[0]
NULL_SOURCES = [
    ("fql_matched", lambda seed: R28._fql_run_dir("matched", seed)),
    ("governed", lambda seed: R28._irr_run_dir("strict", GOVERNED_MODEL, GOVERNED_COMMIT, seed)),
]

REQUIRED_COLS = ["agent_id", "year", "basin", "water_right", "request", "diversion",
                  "curtailment_ratio"]


# =============================================================================
# environment replay harness
# =============================================================================
def _seed_environment(seed: str, year1_rows: list) -> IrrigationEnvironment:
    """Build a fresh IrrigationEnvironment matching the TRUE pre-simulation
    state: water_right/basin/cluster read from year1_rows (that source
    run's year==1 simulation_log rows -- these are static per-agent
    attributes, unaffected by any decision), but request/diversion seeded
    from INIT_DIVERSION (the true actual_2018_diversion baseline, NOT
    year-1's already-decided request -- see the module-level comment on
    INIT_DIVERSION for why this distinction is exact-match-critical),
    curtailment_ratio=0.0 (nothing has been curtailed before year 1).
    Real CRSS precip loaded. No rng-consuming initializer path used."""
    if not os.path.isfile(PRECIP_CSV):
        raise PrepError(f"missing {PRECIP_CSV} -- cannot load the real CRSS precipitation "
                         f"data both production runs used")
    env = IrrigationEnvironment(WaterSystemConfig(seed=int(seed)))
    env.load_crss_precipitation(PRECIP_CSV)
    for r in year1_rows:
        aid = r["agent_id"]
        if aid not in INIT_DIVERSION:
            raise PrepError(f"_seed_environment: agent {aid} (seed {seed}) has no "
                             f"actual_2018_diversion / water_right*0.8 fallback in "
                             f"INIT_DIVERSION -- profile data does not cover this agent")
        init_div = INIT_DIVERSION[aid]
        env._agents[aid] = {
            "basin": r["basin"],
            "water_right": float(r["water_right"]),
            "request": init_div,
            "diversion": init_div,
            "curtailment_ratio": 0.0,
            "at_allocation_cap": False,
            "below_minimum_utilisation": False,
            "has_efficient_system": False,
            "cluster": r.get("cluster", "unknown"),
        }
    if not env._agents:
        raise PrepError(f"_seed_environment: seed {seed}, zero agents seeded from year1_rows")
    return env


def _replay(env: IrrigationEnvironment, request_schedule: dict) -> tuple:
    """Step env for N_YEARS years. request_schedule[agent_id][year_idx] ->
    the request to apply that year (via update_agent_request(), never
    execute_skill() -- see module docstring on why this never touches
    self.rng). Returns (years, mead_levels, total_demands)."""
    agent_ids = list(env._agents.keys())
    for aid in agent_ids:
        if aid not in request_schedule:
            raise PrepError(f"_replay: agent {aid} missing from request_schedule")
    years, mead_levels, total_demands = [], [], []
    for year_idx in range(1, N_YEARS + 1):
        env.advance_year()
        for aid in agent_ids:
            if year_idx not in request_schedule[aid]:
                raise PrepError(f"_replay: agent {aid} missing year {year_idx} in schedule")
            env.update_agent_request(aid, request_schedule[aid][year_idx])
        mead = env.get_local("lower_basin", "lake_mead_level", None)
        if mead is None:
            raise PrepError(f"_replay: year {year_idx} produced no lake_mead_level")
        total_demand = sum(env._agents[aid]["request"] for aid in agent_ids)
        years.append(year_idx)
        mead_levels.append(float(mead))
        total_demands.append(float(total_demand))
    return years, mead_levels, total_demands


def _read_source_rows(source_dir: str) -> list:
    sim_path = os.path.join(source_dir, "simulation_log.csv")
    if not os.path.isfile(sim_path):
        return None
    rows = C.read_csv(sim_path)
    C.require_cols(rows, REQUIRED_COLS, sim_path)
    return rows


def _year1_rows(all_rows: list) -> list:
    return [r for r in all_rows if int(r["year"]) == 1]


def _actual_schedule(all_rows: list) -> dict:
    """{agent_id: {year_idx: real recorded request}} -- every year's REAL
    recorded value, for the replay-fidelity validation."""
    out: dict = {}
    for r in all_rows:
        aid, y = r["agent_id"], int(r["year"])
        out.setdefault(aid, {})[y] = float(r["request"])
    return out


def _constant_schedule(year1_rows: list) -> dict:
    """{agent_id: {year_idx: year-1 request, same value for all 42 years}}."""
    out: dict = {}
    for r in year1_rows:
        aid = r["agent_id"]
        v = float(r["request"])
        out[aid] = {y: v for y in range(1, N_YEARS + 1)}
    return out


# =============================================================================
# Part (a) -- constant-demand null
# =============================================================================
def _part_a(rows: list) -> None:
    for label, dir_fn in NULL_SOURCES:
        for seed in R28.IRR_SEEDS:
            source_dir = dir_fn(seed)
            all_rows = _read_source_rows(source_dir)
            if all_rows is None:
                print(f"  SKIPPED null[{label}] seed {seed}: simulation_log.csv missing "
                      f"under {source_dir}")
                rows.append({"row_type": "skipped", "section": "null_env_replay",
                             "arm": label, "seed": seed,
                             "reason": "simulation_log.csv missing"})
                continue
            y1 = _year1_rows(all_rows)
            if len(y1) == 0:
                raise PrepError(f"{source_dir}: zero year==1 rows in simulation_log.csv")

            # ---- fidelity validation: replay ACTUAL history, compare to
            # the source's own recorded lake_mead_level ----
            env_val = _seed_environment(seed, y1)
            actual_sched = _actual_schedule(all_rows)
            v_years, v_mead, _v_demand = _replay(env_val, actual_sched)
            actual_mead_by_year = {int(r["year"]): float(r["lake_mead_level"])
                                    for r in all_rows}
            ref_mead = [actual_mead_by_year[y] for y in v_years]
            if len(ref_mead) != len(v_mead):
                raise PrepError(f"{source_dir}: replay produced {len(v_mead)} years, "
                                 f"source recorded {len(ref_mead)}")
            resid = [a - b for a, b in zip(v_mead, ref_mead)]
            rmse_val = math.sqrt(sum(x * x for x in resid) / len(resid))
            max_abs_val = max(abs(x) for x in resid)
            passed = rmse_val <= 0.5
            rows.append({"row_type": "null_replay_validation", "arm": label, "seed": seed,
                         "n_years": len(v_years), "rmse": rmse_val, "max_abs": max_abs_val,
                         "passed": passed})
            status_word = "PASS" if passed else "FAIL"
            print(f"  null_replay_validation[{label}] seed {seed}: rmse={rmse_val:.4f} ft "
                  f"max_abs={max_abs_val:.4f} ft -> {status_word}")
            if not passed:
                print(f"  SKIPPED null[{label}] seed {seed}: replay-vs-actual RMSE "
                      f"{rmse_val:.4f} ft > 0.5 ft threshold -- this environment cannot be "
                      f"faithfully replayed offline for this run, refusing to report an "
                      f"approximated null KGE")
                rows.append({"row_type": "skipped", "section": "null_env_replay",
                             "arm": label, "seed": seed,
                             "reason": f"replay-vs-actual RMSE {rmse_val:.4f} ft exceeds "
                                       f"0.5 ft fidelity threshold"})
                continue

            # ---- the actual null: hold year-1 request constant for 42 yrs ----
            env_null = _seed_environment(seed, y1)
            const_sched = _constant_schedule(y1)
            n_years, n_mead, n_demand = _replay(env_null, const_sched)
            for y, m, d in zip(n_years, n_mead, n_demand):
                rows.append({"row_type": "null_series", "arm": label, "seed": seed,
                             "year": y, "mead_level": m, "total_demand": d})

            # ---- KGE of the null vs FQL matched (r28's exact function) ----
            fql_dir = R28._fql_run_dir("matched", seed)
            fql_sim_path = os.path.join(fql_dir, "simulation_log.csv")
            if not os.path.isfile(fql_sim_path):
                raise PrepError(f"missing FQL matched simulation_log.csv for seed {seed}: "
                                 f"{fql_sim_path}")
            ref_years, ref_vals = R28._yearly_series(fql_sim_path, "lake_mead_level", "first")
            if ref_years != n_years:
                raise PrepError(f"null[{label}] seed {seed}: year sets differ from FQL "
                                 f"matched ({n_years[:3]}..{n_years[-3:]} vs "
                                 f"{ref_years[:3]}..{ref_years[-3:]})")
            stats = R28._kge_and_rmse(n_mead, ref_vals)
            rows.append({"row_type": "null_kge", "arm": label, "seed": seed,
                         "series": "mead_elevation", "reference": "matched", "unit": "ft",
                         "n_years": stats["n"], "r": stats["r"], "beta": stats["beta"],
                         "alpha": stats["alpha"], "kge": stats["kge"], "rmse": stats["rmse"]})

    for label, _ in NULL_SOURCES:
        kge_recs = [r for r in rows if r["row_type"] == "null_kge" and r["arm"] == label]
        n = len(kge_recs)
        if n == 0:
            print(f"  null_kge_summary[{label}]: 0 seeds passed validation -- no summary")
            continue
        for metric in ("r", "beta", "alpha", "kge", "rmse"):
            vals = [r[metric] for r in kge_recs]
            mean_v, sd_v = C.mean(vals), (C.sd(vals) if n >= 2 else float("nan"))
            rows.append({"row_type": "null_kge_summary", "arm": label, "n_seeds": n,
                         "metric": metric, "mean": mean_v, "sd": sd_v})


# =============================================================================
# Part (b) -- basin-demand descriptive stats
# =============================================================================
DEMAND_ARM_SPECS = [
    ("irrigation_strict_gemma3_4b", lambda s: R28._irr_run_dir("strict", "gemma3_4b", "faf1bb12", s)),
    ("irrigation_ungoverned_gemma3_4b", lambda s: R28._irr_run_dir("ungoverned", "gemma3_4b", "faf1bb12", s)),
    ("irrigation_strict_gemma4_12b", lambda s: R28._irr_run_dir("strict", "gemma4_12b", "c3391a53", s)),
    ("irrigation_ungoverned_gemma4_12b", lambda s: R28._irr_run_dir("ungoverned", "gemma4_12b", "c3391a53", s)),
    ("fql_matched", lambda s: R28._fql_run_dir("matched", s)),
    ("fql_rebalanced", lambda s: R28._fql_run_dir("rebalanced", s)),
]


def _part_b(rows: list) -> None:
    per_arm_series: dict = {}
    for arm_label, dir_fn in DEMAND_ARM_SPECS:
        per_arm_series[arm_label] = []
        for seed in R28.IRR_SEEDS:
            source_dir = dir_fn(seed)
            sim_path = os.path.join(source_dir, "simulation_log.csv")
            if not os.path.isfile(sim_path):
                print(f"  SKIPPED demand_stats[{arm_label}] seed {seed}: "
                      f"simulation_log.csv missing")
                rows.append({"row_type": "skipped", "section": "demand_stats",
                             "arm": arm_label, "seed": seed,
                             "reason": "simulation_log.csv missing"})
                continue
            years, demand_vals = R28._yearly_series(sim_path, "request", "sum")
            n = len(demand_vals)
            mean_d, sd_d = C.mean(demand_vals), C.sd(demand_vals)
            min_d, max_d = min(demand_vals), max(demand_vals)
            n_over = sum(1 for v in demand_vals if v > DEMAND_CEILING_AF)
            over_share = 100.0 * n_over / n
            dist_to_ceiling = [v - DEMAND_CEILING_AF for v in demand_vals]
            mean_dist = C.mean(dist_to_ceiling)
            rows.append({"row_type": "demand_stats", "arm": arm_label, "seed": seed,
                         "n_years": n, "demand_mean": mean_d, "demand_sd": sd_d,
                         "demand_min": min_d, "demand_max": max_d,
                         "share_years_over_ceiling_pct": over_share,
                         "mean_distance_to_ceiling": mean_dist})
            per_arm_series[arm_label].append({
                "seed": seed, "demand_mean": mean_d, "demand_sd": sd_d,
                "demand_min": min_d, "demand_max": max_d,
                "share_years_over_ceiling_pct": over_share, "mean_distance_to_ceiling": mean_dist,
            })

    for arm_label, per_seed in per_arm_series.items():
        n = len(per_seed)
        if n == 0:
            continue
        row = {"row_type": "demand_stats_summary", "arm": arm_label, "n_seeds": n}
        for metric in ("demand_mean", "demand_sd", "demand_min", "demand_max",
                       "share_years_over_ceiling_pct", "mean_distance_to_ceiling"):
            vals = [r[metric] for r in per_seed]
            row[f"{metric}_avg"] = C.mean(vals)
            row[f"{metric}_across_seed_sd"] = C.sd(vals) if n >= 2 else float("nan")
        rows.append(row)


# =============================================================================
# Part (c) -- basin-demand KGE, carried verbatim from r28
# =============================================================================
def _part_c(rows: list) -> None:
    r28_path = os.path.join(C.OUT, "r28_trajectory_vs_traditional.csv")
    if not os.path.isfile(r28_path):
        raise PrepError(f"missing {r28_path} -- run r28_trajectory_vs_traditional.py first")
    r28_rows = C.read_csv(r28_path)
    n_pair, n_summary = 0, 0
    for r in r28_rows:
        if r["row_type"] == "irr_pair" and r["series"] == "basin_demand":
            rows.append({"row_type": "basin_demand_kge", "model": r["model"], "arm": r["arm"],
                         "seed": r["seed"], "reference": r["reference"], "unit": r["unit"],
                         "n_years": r["n_years"], "r": float(r["r"]), "beta": float(r["beta"]),
                         "alpha": float(r["alpha"]), "kge": float(r["kge"]),
                         "rmse": float(r["rmse"]),
                         "note": "read verbatim from out/r28_trajectory_vs_traditional.csv "
                                 "(row_type=irr_pair, series=basin_demand), not recomputed"})
            n_pair += 1
        elif r["row_type"] == "irr_arm_summary" and r["series"] == "basin_demand":
            rows.append({"row_type": "basin_demand_kge_summary", "model": r["model"],
                         "arm": r["arm"], "reference": r["reference"], "n_seeds": r["n_seeds"],
                         "r": float(r["r_mean"]), "r_sd": float(r["r_sd"]),
                         "beta": float(r["beta_mean"]), "beta_sd": float(r["beta_sd"]),
                         "alpha": float(r["alpha_mean"]), "alpha_sd": float(r["alpha_sd"]),
                         "kge": float(r["kge_mean"]), "kge_sd": float(r["kge_sd"]),
                         "rmse": float(r["rmse_mean"]), "rmse_sd": float(r["rmse_sd"]),
                         "note": "read verbatim from out/r28_trajectory_vs_traditional.csv "
                                 "(row_type=irr_arm_summary, series=basin_demand), not "
                                 "recomputed"})
            n_summary += 1
    if n_pair == 0 or n_summary == 0:
        raise PrepError(f"r28_trajectory_vs_traditional.csv: found {n_pair} basin_demand "
                         f"irr_pair rows and {n_summary} irr_arm_summary rows -- expected "
                         f"nonzero of both")
    print(f"  Part (c): carried {n_pair} basin_demand irr_pair rows + {n_summary} "
          f"irr_arm_summary rows from r28, verbatim")


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "section", "arm", "seed", "model", "series", "reference", "unit",
    "n_years", "r", "beta", "alpha", "kge", "rmse", "rmse_sd", "reason",
    "passed", "max_abs", "year", "mead_level", "total_demand",
    "n_seeds", "metric", "mean", "sd",
    "demand_mean", "demand_sd", "demand_min", "demand_max",
    "share_years_over_ceiling_pct", "mean_distance_to_ceiling",
    "demand_mean_avg", "demand_mean_across_seed_sd",
    "demand_sd_avg", "demand_sd_across_seed_sd",
    "demand_min_avg", "demand_min_across_seed_sd",
    "demand_max_avg", "demand_max_across_seed_sd",
    "share_years_over_ceiling_pct_avg", "share_years_over_ceiling_pct_across_seed_sd",
    "mean_distance_to_ceiling_avg", "mean_distance_to_ceiling_across_seed_sd",
    "r_sd", "beta_sd", "alpha_sd", "kge_sd", "note",
]
_seen = set()
FIELDNAMES = [c for c in FIELDNAMES if not (c in _seen or _seen.add(c))]


def main() -> int:
    C.banner("R29  Constant-demand KGE null + basin-demand descriptive stats "
             "+ carried basin-demand KGE")
    rows: list = []

    print("\n-- Part (a): constant-demand null for Mead-elevation KGE --")
    _part_a(rows)

    print("\n-- Part (b): basin-demand descriptive stats --")
    _part_b(rows)

    print("\n-- Part (c): basin-demand KGE carried from r28 --")
    _part_c(rows)

    md_text = render_md(rows)

    csv_final = "r29_kge_null_and_demand.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, "r29_kge_null_and_demand.md")
    md_tmp = md_final + ".tmp"

    csv_tmp_path = C.write_csv(csv_tmp, FIELDNAMES, rows)
    with open(md_tmp, "w", encoding="utf-8") as fh:
        fh.write(md_text)

    os.replace(csv_tmp_path, os.path.join(C.OUT, csv_final))
    os.replace(md_tmp, md_final)
    print(f"\n  wrote {os.path.relpath(os.path.join(C.OUT, csv_final), C.REPO).replace(chr(92), '/')}"
          f"  ({len(rows)} rows)")
    print(f"  wrote {os.path.relpath(md_final, C.REPO).replace(chr(92), '/')}  "
          f"({len(md_text.splitlines())} lines)")
    return 0


# =============================================================================
# .md rendering
# =============================================================================
_cp = lambda x: float(C.fmt(x))  # noqa: E731


def _find(rows, row_type, **kw):
    out = []
    for r in rows:
        if r.get("row_type") != row_type:
            continue
        if all(r.get(k) == v for k, v in kw.items()):
            out.append(r)
    return out


def render_md(rows: list) -> str:
    lines = []
    lines.append("# R29 -- constant-demand KGE null + basin-demand descriptive stats")
    lines.append("")
    lines.append("Source: `r29_kge_null_and_demand.py`. Every number below is read live from "
                 "the `rows` list this script writes to the paired CSV.")
    lines.append("")

    # ---- Part (a): replay validation + null KGE ----------------------------
    lines.append("## Part (a) -- constant-demand null for the Mead-elevation KGE")
    lines.append("")
    lines.append("### Replay-fidelity validation (replay ACTUAL history vs the source's own "
                 "recorded Lake Mead trajectory; must pass before any null KGE is trusted)")
    lines.append("")
    lines.append("| source | seed | rmse (ft) | max abs (ft) | status |")
    lines.append("|---|---|---|---|---|")
    for r in _find(rows, "null_replay_validation"):
        status = "PASS" if r["passed"] == "True" or r["passed"] is True else "FAIL"
        lines.append(f"| {r['arm']} | {r['seed']} | {_cp(r['rmse']):.4f} | "
                     f"{_cp(r['max_abs']):.4f} | {status} |")
    lines.append("")

    lines.append("### Null Mead-elevation KGE vs FQL matched (mean +/- sd over validated seeds)")
    lines.append("")
    lines.append("| source | n_seeds | r | beta | alpha | KGE | RMSE (ft) |")
    lines.append("|---|---|---|---|---|---|---|")
    for label, _ in NULL_SOURCES:
        recs = {r["metric"]: r for r in _find(rows, "null_kge_summary", arm=label)}
        if not recs:
            lines.append(f"| {label} | 0 | -- | -- | -- | no seeds passed validation | -- |")
            continue
        n = recs["kge"]["n_seeds"]
        def cell(m):
            r = recs[m]
            return f"{_cp(r['mean']):.4f} +/- {_cp(r['sd']):.4f}"
        lines.append(f"| {label} | {n} | {cell('r')} | {cell('beta')} | {cell('alpha')} | "
                     f"{cell('kge')} | {cell('rmse')} |")
    lines.append("")
    lines.append("For comparison, the actual LLM/FQL-rebalanced Mead-elevation KGE against "
                 "FQL-matched (from r28, not recomputed here): governed(strict)/gemma3:4b "
                 "KGE=0.9456, ungoverned/gemma3:4b KGE=0.2823 (see out/"
                 "r28_trajectory_vs_traditional.md for the full table).")
    lines.append("")

    # ---- Part (b): demand stats ---------------------------------------------
    lines.append("## Part (b) -- basin-demand descriptive stats")
    lines.append("")
    lines.append(f"Ceiling = `DEMAND_CEILING_AF` = {DEMAND_CEILING_AF:,} acre-ft/yr, imported "
                 f"from `examples/irrigation_abm/validators/irrigation_validators.py`, not "
                 f"hardcoded.")
    lines.append("")
    lines.append("| arm | n_seeds | demand mean (AF) | demand sd (AF) | min (AF) | max (AF) | "
                 "% years over ceiling | mean distance to ceiling (AF) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for arm_label, _ in DEMAND_ARM_SPECS:
        recs = _find(rows, "demand_stats_summary", arm=arm_label)
        if not recs:
            lines.append(f"| {arm_label} | 0 | pending | pending | pending | pending | "
                         f"pending | pending |")
            continue
        r = recs[0]
        lines.append(
            f"| {arm_label} | {r['n_seeds']} | "
            f"{_cp(r['demand_mean_avg']):.0f} +/- {_cp(r['demand_mean_across_seed_sd']):.0f} | "
            f"{_cp(r['demand_sd_avg']):.0f} | "
            f"{_cp(r['demand_min_avg']):.0f} | {_cp(r['demand_max_avg']):.0f} | "
            f"{_cp(r['share_years_over_ceiling_pct_avg']):.1f}% | "
            f"{_cp(r['mean_distance_to_ceiling_avg']):.0f} |"
        )
    lines.append("")

    # ---- Part (c): carried basin-demand KGE ----------------------------------
    lines.append("## Part (c) -- basin-demand KGE (carried verbatim from r28, not recomputed)")
    lines.append("")
    lines.append("| model | arm | reference | n_seeds | r | beta | alpha | KGE | RMSE (AF) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in _find(rows, "basin_demand_kge_summary"):
        lines.append(
            f"| {r['model']} | {r['arm']} | {r['reference']} | {r['n_seeds']} | "
            f"{_cp(r['r']):.4f} +/- {_cp(r['r_sd']):.4f} | "
            f"{_cp(r['beta']):.4f} +/- {_cp(r['beta_sd']):.4f} | "
            f"{_cp(r['alpha']):.4f} +/- {_cp(r['alpha_sd']):.4f} | "
            f"{_cp(r['kge']):.4f} +/- {_cp(r['kge_sd']):.4f} | "
            f"{_cp(r['rmse']):.0f} +/- {_cp(r['rmse_sd']):.0f} |"
        )
    lines.append("")

    # ---- Plain read -----------------------------------------------------------
    lines.append("## Plain read")
    lines.append("")
    sentences = []
    n_pass = len([r for r in _find(rows, "null_replay_validation")
                  if r["passed"] == "True" or r["passed"] is True])
    n_total = len(_find(rows, "null_replay_validation"))
    sentences.append(f"The environment-replay fidelity check passed {n_pass}/{n_total} "
                     f"(source, seed) pairs (RMSE <= 0.5 ft vs the source's own recorded "
                     f"Lake Mead trajectory), so the null-KGE numbers below are reported "
                     f"only where this held.")
    null_summ = {label: {r["metric"]: r for r in _find(rows, "null_kge_summary", arm=label)}
                 for label, _ in NULL_SOURCES}
    if null_summ.get("fql_matched") and null_summ.get("governed"):
        fm_kge = null_summ["fql_matched"].get("kge")
        gv_kge = null_summ["governed"].get("kge")
        if fm_kge and gv_kge:
            sentences.append(
                f"Holding demand at its year-1 level for 42 years (the constant-demand null) "
                f"yields a Mead-elevation KGE of {_cp(fm_kge['mean']):.2f} against FQL-matched "
                f"when seeded from FQL-matched's own year-1 requests, and "
                f"{_cp(gv_kge['mean']):.2f} when seeded from governed-LLM's year-1 requests -- "
                f"context for how much of any arm's real KGE against FQL reflects tracking "
                f"the DEMAND trajectory specifically, versus just tracking the shared "
                f"precipitation forcing that drives Mead regardless of demand."
            )
    over_ceiling = _find(rows, "demand_stats_summary")
    if over_ceiling:
        worst = max(over_ceiling, key=lambda r: float(r["share_years_over_ceiling_pct_avg"]))
        sentences.append(
            f"Of the arms compared, {worst['arm']} spends the most years over the "
            f"{DEMAND_CEILING_AF:,} acre-ft ceiling "
            f"({_cp(worst['share_years_over_ceiling_pct_avg']):.1f}% of years)."
        )
    for s in sentences[:5]:
        lines.append(s)
        lines.append("")

    # ---- Method -----------------------------------------------------------------
    lines.append("## Method")
    lines.append("")
    lines.append(
        "Constant-demand null: `examples/irrigation_abm/irrigation_env.py`'s "
        "`IrrigationEnvironment` is seeded with the TRUE pre-simulation diversion baseline "
        "(`actual_2018_diversion` per agent, via `irrigation_personas.py::"
        "create_profiles_from_data()`, the same production function/paths the real runs use "
        "-- NOT year-1's already-decided request, which was tried first and produced a "
        "provable year-1-onward Mead error, see module docstring) plus static "
        "water_right/basin/cluster (read from the source's own year-1 `simulation_log.csv` "
        "row, never regenerated), then stepped 42 years via `update_agent_request(agent_id, "
        "year1_request)` called every year to hold demand at that source's OWN year-1 "
        "recorded request (never `execute_skill()`, which is the only rng-consuming path "
        "besides the unused synthetic-precipitation fallback -- see module docstring). "
        "Real CRSS winter precipitation is loaded from `ref/CRSS_DB/CRSS_DB/HistoricalData/"
        "PrismWinterPrecip_ST_NOAA_Future.csv`, the same file both fql_raw_norebalance_faf1bb12 "
        "and strict_42yr_gemma3_4b_faf1bb12 used (both ran with `--real`); only the strict "
        "run's LAUNCH_COMMAND.txt carries a SHA256 block for this file (matches the live "
        "file's own hash, `3094b4c5...`) -- the FQL run's LAUNCH_COMMAND.txt is 3 lines only "
        "(command + timestamps), no hash to check, not claimed otherwise. Fidelity is "
        "verified empirically per seed (replay actual "
        "history, compare to the source's own recorded lake_mead_level), not assumed. KGE "
        "formula and sim/ref convention: identical to r28 "
        "(`r28_trajectory_vs_traditional.py::_kge_and_rmse`, imported, not re-derived). "
        f"Demand ceiling = `DEMAND_CEILING_AF` "
        f"(`examples/irrigation_abm/validators/irrigation_validators.py`), imported, not "
        f"hardcoded."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
