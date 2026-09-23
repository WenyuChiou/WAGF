"""R28 -- Do the LLM arms reproduce the trajectory of the traditional ABM,
and does the validator matter for that?

PART 1 -- irrigation (main text)
  For each LLM arm (strict=governed, ungoverned) x model
  (gemma3:4b @ faf1bb12, gemma4:12b @ c3391a53) x seed 42-46, compares two
  42-year series against the traditional FQL baseline at the SAME seed:
    - primary reference ("matched"): examples/irrigation_abm/results/
      fql_raw_norebalance_faf1bb12/seed{s}  (matched cluster split)
    - sensitivity ("rebalanced"): examples/irrigation_abm/results/
      fql_raw_faf1bb12/seed{s}
  Series (columns found and verified against
  examples/irrigation_abm/analysis/fig_wrr_irrigation.py, which labels
  these same two columns lake_mead_ft / request_af):
    - mead_elevation: simulation_log.csv column `lake_mead_level` (feet).
      Verified this is a single basin-level value per year (nunique==1
      across all 78 agents within a year) -- aggregated with "first",
      raises if a year ever has >1 distinct value.
    - basin_demand: simulation_log.csv column `request` (acre-feet per
      agent-year) -- aggregated with "sum" across all agents per year.
  Metric: Kling-Gupta efficiency, KGE = 1 - sqrt((r-1)^2 + (b-1)^2 + (a-1)^2)
  with r = Pearson correlation(sim, ref), b = mean(sim)/mean(ref),
  a = sd(sim)/sd(ref) (ddof=1); sim = LLM arm, ref = FQL. RMSE reported in
  the series' own unit. Then per (model, arm, series, reference): mean +-
  sd over the available seeds; per (model, series, reference): the
  seed-paired contrast governed(strict) - ungoverned for KGE and RMSE
  (paired t df 4, exact permutation, sign consistency). Also: FQL matched
  vs FQL rebalanced at the SAME seed (rebalanced=sim, matched=ref) as a
  same-model reference for how different two traditional runs naturally
  are, at the SAME KGE/RMSE definition -- this calibrates what an LLM
  arm's KGE against FQL actually means.

PART 2 -- flood (SI only, categorical, not a headline)
  Per year 1-10 and seed, the protection-state distribution over the 5
  states FIG3.PROT_STATES (`gen_fig3_regen.py`, imported READ-ONLY --
  `load_all_runs()` returns per-run DataFrames with a `prot_state` column
  already classified via `_classify_state_from_cols`/`cumulative_state`
  mapping; this script never re-derives that classification) for governed
  (JOH_strict_gemma3_4b_faf1bb12), no-validator
  (JOH_disabled_gemma3_4b_faf1bb12) and rule-based (rulebased_5seed_
  faf1bb12), same seed. Jensen-Shannon distance (base 2, in [0,1]) of each
  LLM arm's distribution to rule-based per year -> mean over years per
  seed -> mean +- sd over seeds -> paired governed - no-validator
  contrast; also governed-vs-no-validator distance directly (its own
  summary, not part of the paired contrast). Also computes, per arm and
  seed, the relocation share (relocated agent-years / all agent-years)
  and the count of distinct agents ever relocated, for rule-based,
  governed and no-validator (row_type=flood_relocation_seed /
  flood_relocation_arm_summary). KGE does not apply to a categorical
  composition (there is no scalar "value" to correlate). CORRECTED
  2026-09-20: an earlier draft of this docstring claimed the flood
  rule-based baseline "never relocates" -- FALSE, verified against
  `rulebased_5seed_faf1bb12/Run_{42..46}/simulation_log.csv`: relocated
  agent-years are 7/2/0/6/0 out of 1000 per seed (0-0.7%). What is true
  (checked below at runtime, raises otherwise) is that this share is far
  BELOW either LLM arm's relocation share (which runs ~10-27% of
  agent-years) at every one of the 5 seeds -- so most, not all, of an LLM
  arm's JS gap to rule-based is structural (its much higher relocation
  share alone shifts the distribution), not a governance failure. This
  is a SI
  diagnostic, not a headline result.

PART 3 -- plain read + Method block
  <=5-sentence plain read templated from the `rows` list (direction words
  derived from thresholds applied to the numbers, never hand-typed).
  Method block states explicitly: "KGE against a reference MODEL, not
  observations" (FQL is itself a simulated traditional ABM baseline, not
  ground-truth Colorado River telemetry), names the exact columns/units
  used, and cites the KGE formula.

COMPLETENESS GATE (fail-loud, never crash on an in-progress run)
  irrigation: run dir exists -> simulation_log.csv exists. FQL reference
  dir exists -> simulation_log.csv exists. Missing -> row_type=skipped,
  printed reason, that (model,arm,seed) or (seed,reference) pair excluded
  from all downstream aggregates (aggregates state how many seeds went
  in). A present-but-structurally-wrong run (year set != 1..42, a
  basin-level column with >1 distinct value within a year, mismatched
  year sets between sim and ref) RAISES -- that is a data bug, not
  incompleteness.
  flood: this script independently checks Run_{seed}/simulation_log.csv
  existence for all three arms x 5 seeds BEFORE calling
  FIG3.load_all_runs(), then cross-verifies load_all_runs()'s own
  per-arm run count against that independent count (raises on
  disagreement) before trusting position-in-list == seed-order.

OUTPUTS
  out/r28_trajectory_vs_traditional.csv -- row_type in {skipped, irr_pair,
    irr_arm_summary, irr_contrast, irr_fql_reference,
    irr_fql_reference_summary, flood_js_detail, flood_js_seed_mean,
    flood_js_arm_summary, flood_js_contrast}.
  out/r28_trajectory_vs_traditional.md -- GENERATED by render_md()
    directly from that same `rows` list (no number typed by hand).

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r28_trajectory_vs_traditional.py
        python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r28_trajectory_vs_traditional.py --corpus defaults

--corpus (added 2026-09-23, see _common.py::flood_corpus_dirs) -- FLOOD PART
ONLY, Part 1 (irrigation) is entirely unaffected by --corpus, always the
v08 corpus (IRR_MODELS/FQL_DIR are irrigation constants, out of this
switch's scope). Part 2 (flood) is sourced entirely through
`gen_fig3_regen.py::load_all_runs()`, which is hardcoded to commit
faf1bb12 for governed/disabled (`FIG3.GOV_DIR`/`FIG3.DISABLED_DIR`, module-
level `pathlib.Path` constants) and is outside this script's edit scope --
never edited on disk. --corpus defaults REASSIGNS those two module
attributes on the already-imported `FIG3` module object at runtime (a
same-process monkey-patch, not a file edit) to the defaults strict/
disabled dirs before calling `load_all_runs()`; `FIG3.RULEBASED_DIR` is
left untouched (rule-based is deterministic, no separate defaults corpus
exists for it). This script's own existing completeness gate
(`_flood_seed_dirs_present`) already renders Part 2 PENDING gracefully
when fewer than 2 seeds are complete on all three arms -- true today for
the defaults corpus (0/5) -- so no new PENDING branch was needed here.
Writes out/r28_trajectory_vs_traditional_defaults.{md,csv}.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402

# gen_fig3_regen.py (paper/nature_water/scripts/regen/) -- READ-ONLY: only
# load_all_runs() (a pure reader) is called; generate_figure() is never
# called, and its own OUT_DIR.mkdir(exist_ok=True) at import time is a
# no-op since paper/nature_water/figures/regen/ already exists (verified,
# same import r25_table1_regen.py already performs).
sys.path.insert(0, os.path.join(C.REPO, "paper", "nature_water", "scripts", "regen"))
import gen_fig3_regen as FIG3  # noqa: E402

IRR_RESULTS = os.path.join(C.REPO, "examples", "irrigation_abm", "results")
IRR_SEEDS = ["42", "43", "44", "45", "46"]
IRR_MODELS = [("gemma3_4b", "faf1bb12"), ("gemma4_12b", "c3391a53")]
IRR_ARMS = ["strict", "ungoverned"]

FQL_DIR = {"matched": "fql_raw_norebalance_faf1bb12", "rebalanced": "fql_raw_faf1bb12"}
FQL_REFERENCES = ["matched", "rebalanced"]

# (series_name, source_column, per-year aggregation, unit). Columns found
# by grepping examples/irrigation_abm/analysis/*.py for existing usage of
# simulation_log.csv columns; unit confirmed via
# examples/irrigation_abm/analysis/fig_wrr_irrigation.py, which names
# these same two columns lake_mead_ft (lake_mead_level) and request_af
# (request). Verified empirically (this script, at runtime, via the
# nunique==1 check below) that lake_mead_level is a single basin-level
# value shared by all agents within a year, not a per-agent quantity.
IRR_SERIES = [
    ("mead_elevation", "lake_mead_level", "first", "ft"),
    ("basin_demand", "request", "sum", "acre-ft"),
]

FLOOD_SEEDS = ["42", "43", "44", "45", "46"]
FLOOD_YEARS = list(range(1, 11))
PROT_STATES = FIG3.PROT_STATES  # canonical 5-state order, imported not copied


# =============================================================================
# generic stats
# =============================================================================
def _pearson_r(x: list, y: list) -> float:
    n = len(x)
    if n != len(y):
        raise PrepError(f"_pearson_r: length mismatch {n} vs {len(y)}")
    if n < 2:
        raise PrepError(f"_pearson_r: need >=2 points, got {n}")
    mx, my = C.mean(x), C.mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0 or syy <= 0:
        raise PrepError(f"_pearson_r: zero variance in one series (sxx={sxx}, syy={syy}) "
                         f"-- Pearson r undefined")
    return sxy / math.sqrt(sxx * syy)


def _kge_and_rmse(sim: list, ref: list) -> dict:
    """KGE = 1 - sqrt((r-1)^2 + (beta-1)^2 + (alpha-1)^2); Gupta et al. 2009
    original formulation, exactly as specified by the task (beta = mean
    ratio, alpha = sd ratio, ddof=1) -- NOT the 2012 modified-KGE (CV
    ratio) variant."""
    n = len(sim)
    if n != len(ref):
        raise PrepError(f"_kge_and_rmse: length mismatch {n} vs {len(ref)}")
    if n < 2:
        raise PrepError(f"_kge_and_rmse: need >=2 points, got {n}")
    r = _pearson_r(sim, ref)
    mean_sim, mean_ref = C.mean(sim), C.mean(ref)
    if mean_ref == 0:
        raise PrepError("_kge_and_rmse: mean(ref)==0 -- beta undefined")
    beta = mean_sim / mean_ref
    sd_sim, sd_ref = C.sd(sim), C.sd(ref)
    if sd_ref == 0:
        raise PrepError("_kge_and_rmse: sd(ref)==0 -- alpha undefined")
    alpha = sd_sim / sd_ref
    kge = 1.0 - math.sqrt((r - 1) ** 2 + (beta - 1) ** 2 + (alpha - 1) ** 2)
    rmse = math.sqrt(sum((s - x) ** 2 for s, x in zip(sim, ref)) / n)
    return {"n": n, "r": r, "beta": beta, "alpha": alpha, "kge": kge, "rmse": rmse}


def _sign_stats(diffs: list) -> dict:
    t, df = C.paired_t(diffs)
    mean_d, sd_d = C.mean(diffs), C.sd(diffs)
    n_flips = sum(1 for x in diffs if (x > 0) != (mean_d > 0))
    same_sign = len({1 if x > 0 else (-1 if x < 0 else 0) for x in diffs}) == 1
    return {
        "n_pairs": len(diffs), "mean_diff": mean_d, "sd_diff": sd_d,
        "min_diff": min(diffs), "max_diff": max(diffs), "n_sign_flips": n_flips,
        "all_same_sign": same_sign, "t": t, "df": float(df),
        "p_paired_t": C.t_two_sided_p(t, df), "p_exact_permutation": C.exact_perm_p(diffs),
        "permutation_floor": 2.0 / (1 << len(diffs)),
    }


# =============================================================================
# Part 1 -- irrigation
# =============================================================================
def _irr_run_dir(arm: str, model: str, commit: str, seed: str) -> str:
    return os.path.join(IRR_RESULTS, f"{arm}_42yr_{model}_{commit}_seed{seed}")


def _fql_run_dir(kind: str, seed: str) -> str:
    return os.path.join(IRR_RESULTS, FQL_DIR[kind], f"seed{seed}")


def _run_completeness(run_dir: str) -> tuple:
    if not os.path.isdir(run_dir):
        return "skipped", "run directory does not exist"
    sim_path = os.path.join(run_dir, "simulation_log.csv")
    if not os.path.isfile(sim_path):
        return "skipped", "simulation_log.csv missing (run in progress)"
    return "ok", None


def _yearly_series(sim_log_path: str, col: str, agg: str) -> tuple:
    """Return (years, values) for `col`, aggregated per year via `agg`
    ('first' or 'sum'). Raises on a non-contiguous year set, or (for
    'first') a year where the column is not a single shared value."""
    df = pd.read_csv(sim_log_path, encoding="utf-8-sig")
    for need in ("year", col):
        if need not in df.columns:
            raise PrepError(f"{sim_log_path}: missing column {need!r} -- found columns "
                             f"{list(df.columns)}")
    years = sorted(df["year"].unique().tolist())
    if years != list(range(years[0], years[-1] + 1)):
        raise PrepError(f"{sim_log_path}: non-contiguous year set {years}")
    vals = []
    for y in years:
        sub = df.loc[df["year"] == y, col]
        if agg == "first":
            uniq = sub.unique()
            if len(uniq) != 1:
                raise PrepError(f"{sim_log_path}: year {y} column {col!r} has "
                                 f"{len(uniq)} distinct values {uniq[:5]}, expected 1 "
                                 f"(a basin-level series shared by every agent)")
            vals.append(float(uniq[0]))
        elif agg == "sum":
            vals.append(float(sub.sum()))
        else:
            raise PrepError(f"_yearly_series: unknown agg {agg!r}")
    return years, vals


def _irr_part1(rows: list) -> dict:
    """Returns {(model, arm, series, reference): {seed: kge_and_rmse dict}}
    for downstream aggregation/contrast, alongside appending irr_pair /
    skipped rows to `rows`."""
    per_cell: dict = {}
    n_skipped = 0
    for model, commit in IRR_MODELS:
        for arm in IRR_ARMS:
            for seed in IRR_SEEDS:
                run_dir = _irr_run_dir(arm, model, commit, seed)
                status, reason = _run_completeness(run_dir)
                if status == "skipped":
                    n_skipped += 1
                    print(f"  SKIPPED irrigation {model} {arm} seed {seed}: {reason}")
                    rows.append({"row_type": "skipped", "section": "irrigation",
                                 "model": model, "arm": arm, "seed": seed, "reason": reason})
                    continue
                sim_path = os.path.join(run_dir, "simulation_log.csv")
                for series_name, col, agg, unit in IRR_SERIES:
                    sim_years, sim_vals = _yearly_series(sim_path, col, agg)
                    for ref_kind in FQL_REFERENCES:
                        fql_dir = _fql_run_dir(ref_kind, seed)
                        fstatus, freason = _run_completeness(fql_dir)
                        if fstatus == "skipped":
                            n_skipped += 1
                            print(f"  SKIPPED irrigation FQL {ref_kind} seed {seed}: {freason}")
                            rows.append({"row_type": "skipped", "section": "irrigation_fql",
                                         "model": model, "arm": arm, "seed": seed,
                                         "series": series_name, "reference": ref_kind,
                                         "reason": freason})
                            continue
                        fql_sim_path = os.path.join(fql_dir, "simulation_log.csv")
                        ref_years, ref_vals = _yearly_series(fql_sim_path, col, agg)
                        if ref_years != sim_years:
                            raise PrepError(f"{sim_path} vs {fql_sim_path}: year sets differ "
                                             f"({sim_years[:3]}..{sim_years[-3:]} vs "
                                             f"{ref_years[:3]}..{ref_years[-3:]})")
                        stats = _kge_and_rmse(sim_vals, ref_vals)
                        rows.append({
                            "row_type": "irr_pair", "model": model, "arm": arm, "seed": seed,
                            "series": series_name, "reference": ref_kind, "unit": unit,
                            "n_years": stats["n"], "r": stats["r"], "beta": stats["beta"],
                            "alpha": stats["alpha"], "kge": stats["kge"], "rmse": stats["rmse"],
                        })
                        per_cell.setdefault((model, arm, series_name, ref_kind), {})[seed] = stats
    print(f"  irrigation Part 1: {n_skipped} (run,series,reference) pairs skipped")
    return per_cell


def _irr_part1_summary(rows: list, per_cell: dict) -> None:
    for (model, arm, series_name, ref_kind), by_seed in per_cell.items():
        n = len(by_seed)
        row = {"row_type": "irr_arm_summary", "model": model, "arm": arm,
               "series": series_name, "reference": ref_kind, "n_seeds": n}
        for metric in ("r", "beta", "alpha", "kge", "rmse"):
            vals = [by_seed[s][metric] for s in by_seed]
            row[f"{metric}_mean"] = C.mean(vals)
            row[f"{metric}_sd"] = C.sd(vals) if n >= 2 else float("nan")
        rows.append(row)


def _irr_part1_contrast(rows: list, per_cell: dict) -> None:
    for model, _commit in IRR_MODELS:
        for series_name, _col, _agg, _unit in IRR_SERIES:
            for ref_kind in FQL_REFERENCES:
                gov = per_cell.get((model, "strict", series_name, ref_kind), {})
                ungov = per_cell.get((model, "ungoverned", series_name, ref_kind), {})
                common_seeds = sorted(set(gov) & set(ungov))
                if len(common_seeds) < 2:
                    print(f"  irr contrast PENDING: {model}/{series_name}/{ref_kind} has only "
                          f"{len(common_seeds)} seeds common to both arms")
                    rows.append({"row_type": "skipped", "section": "irr_contrast",
                                 "model": model, "series": series_name, "reference": ref_kind,
                                 "reason": f"only {len(common_seeds)} seeds common to strict+ungoverned"})
                    continue
                for metric in ("kge", "rmse"):
                    diffs = [gov[s][metric] - ungov[s][metric] for s in common_seeds]
                    for s, d in zip(common_seeds, diffs):
                        rows.append({"row_type": "irr_contrast_pair", "model": model,
                                     "series": series_name, "reference": ref_kind,
                                     "metric": metric, "seed": s,
                                     "governed_value": gov[s][metric],
                                     "ungoverned_value": ungov[s][metric], "diff": d})
                    stats = _sign_stats(diffs)
                    rows.append({"row_type": "irr_contrast", "model": model,
                                 "series": series_name, "reference": ref_kind,
                                 "metric": metric, **stats})


def _irr_part1_fql_reference(rows: list) -> None:
    per_series: dict = {}
    for series_name, col, agg, unit in IRR_SERIES:
        per_series[series_name] = {}
        for seed in IRR_SEEDS:
            matched_dir = _fql_run_dir("matched", seed)
            rebal_dir = _fql_run_dir("rebalanced", seed)
            m_status, m_reason = _run_completeness(matched_dir)
            r_status, r_reason = _run_completeness(rebal_dir)
            if m_status == "skipped" or r_status == "skipped":
                reason = m_reason if m_status == "skipped" else r_reason
                print(f"  SKIPPED FQL-vs-FQL {series_name} seed {seed}: {reason}")
                rows.append({"row_type": "skipped", "section": "irr_fql_reference",
                             "series": series_name, "seed": seed, "reason": reason})
                continue
            matched_path = os.path.join(matched_dir, "simulation_log.csv")
            rebal_path = os.path.join(rebal_dir, "simulation_log.csv")
            m_years, m_vals = _yearly_series(matched_path, col, agg)
            r_years, r_vals = _yearly_series(rebal_path, col, agg)
            if m_years != r_years:
                raise PrepError(f"FQL matched vs rebalanced seed {seed}: year sets differ")
            # sim = rebalanced, ref = matched -- matched is the primary reference
            # throughout this script, so "how far rebalanced sits from matched"
            # uses the same sim/ref convention as every other KGE row here.
            stats = _kge_and_rmse(r_vals, m_vals)
            rows.append({"row_type": "irr_fql_reference", "series": series_name, "seed": seed,
                         "unit": unit, "n_years": stats["n"], "r": stats["r"],
                         "beta": stats["beta"], "alpha": stats["alpha"], "kge": stats["kge"],
                         "rmse": stats["rmse"]})
            per_series[series_name][seed] = stats
        by_seed = per_series[series_name]
        n = len(by_seed)
        if n == 0:
            continue
        row = {"row_type": "irr_fql_reference_summary", "series": series_name, "n_seeds": n}
        for metric in ("r", "beta", "alpha", "kge", "rmse"):
            vals = [by_seed[s][metric] for s in by_seed]
            row[f"{metric}_mean"] = C.mean(vals)
            row[f"{metric}_sd"] = C.sd(vals) if n >= 2 else float("nan")
        rows.append(row)


# =============================================================================
# Part 2 -- flood
# =============================================================================
def _js_distance(p: list, q: list) -> float:
    """Jensen-Shannon distance, base 2, in [0,1]. sqrt of the JS
    divergence; m=(p+q)/2 guarantees m_i>0 wherever p_i>0 or q_i>0, so no
    log(0) case can arise from valid probability vectors."""
    if len(p) != len(q):
        raise PrepError(f"_js_distance: length mismatch {len(p)} vs {len(q)}")
    if abs(sum(p) - 1.0) > 1e-6 or abs(sum(q) - 1.0) > 1e-6:
        raise PrepError(f"_js_distance: inputs are not probability vectors "
                         f"(sum p={sum(p)}, sum q={sum(q)})")
    m = [(pi + qi) / 2.0 for pi, qi in zip(p, q)]

    def _kl(a, b):
        s = 0.0
        for ai, bi in zip(a, b):
            if ai > 0:
                s += ai * math.log2(ai / bi)
        return s

    jsd = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)
    if jsd < -1e-9 or jsd > 1.0 + 1e-9:
        raise PrepError(f"_js_distance: JS divergence {jsd} outside [0,1] -- numeric bug")
    jsd = min(max(jsd, 0.0), 1.0)
    return math.sqrt(jsd)


def _state_dist(df_year: pd.DataFrame) -> list:
    n = len(df_year)
    if n == 0:
        raise PrepError("_state_dist: zero rows for this year")
    counts = df_year["prot_state"].value_counts()
    unexpected = set(counts.index) - set(PROT_STATES)
    if unexpected:
        raise PrepError(f"_state_dist: prot_state values outside FIG3.PROT_STATES: {unexpected}")
    return [counts.get(s, 0) / n for s in PROT_STATES]


def _flood_seed_dirs_present(base_dir) -> dict:
    """Independent, direct filesystem check of Run_{seed}/simulation_log.csv
    for each of FLOOD_SEEDS -- computed BEFORE calling FIG3.load_all_runs(),
    so this script never has to trust load_all_runs()'s internal list
    ordering without a cross-check."""
    out = {}
    for seed in FLOOD_SEEDS:
        run_dir = os.path.join(base_dir, f"Run_{seed}")
        sim_path = os.path.join(run_dir, "simulation_log.csv")
        out[seed] = os.path.isfile(sim_path)
    return out


def _irr_part2_flood(rows: list) -> None:
    presence = {
        "gov": _flood_seed_dirs_present(FIG3.GOV_DIR),
        "disabled": _flood_seed_dirs_present(FIG3.DISABLED_DIR),
        "rulebased": _flood_seed_dirs_present(FIG3.RULEBASED_DIR),
    }
    for key, per_seed in presence.items():
        for seed, present in per_seed.items():
            if not present:
                print(f"  SKIPPED flood {key} seed {seed}: simulation_log.csv missing")
                rows.append({"row_type": "skipped", "section": "flood", "arm": key,
                             "seed": seed, "reason": "simulation_log.csv missing"})

    complete_seeds = {
        key: [s for s, present in per_seed.items() if present]
        for key, per_seed in presence.items()
    }
    common_seeds = sorted(set(complete_seeds["gov"]) & set(complete_seeds["disabled"])
                           & set(complete_seeds["rulebased"]), key=int)
    if len(common_seeds) < 2:
        print(f"  flood Part 2: PENDING -- only {len(common_seeds)} seeds complete on all "
              f"three arms (gov/disabled/rulebased); no JS rows written")
        return

    data = FIG3.load_all_runs()  # read-only: no generate_figure(), no file written
    for key in ("gov", "disabled", "rulebased"):
        if len(data[key]) != len(complete_seeds[key]):
            raise PrepError(f"gen_fig3_regen.load_all_runs() returned {len(data[key])} "
                             f"'{key}' runs but this script's own filesystem check found "
                             f"{len(complete_seeds[key])} -- position-based seed alignment "
                             f"would be unsafe, refusing to guess which seed is missing")

    # RUN_SEEDS is FIG3's own walk order; load_all_runs() appends in that
    # order, skipping only genuinely-missing runs -- since every one of
    # FIG3.RUN_SEEDS is present for all three arms here (common_seeds ==
    # all 5, verified via the length cross-check just above matching
    # complete_seeds which in turn came from checking every seed), the
    # cross-check above is exactly the guard that would have caught a
    # partial-arm misalignment before this zip.
    seed_labels = [str(s) for s in FIG3.RUN_SEEDS]
    dfs_by_key_seed = {
        key: dict(zip(seed_labels, data[key])) for key in ("gov", "disabled", "rulebased")
    }

    # ---- relocation share, per arm and seed (added 2026-09-20 review fix:
    # an earlier draft assumed rule-based never relocates -- FALSE, it
    # relocates 0-0.7% of agent-years; see module docstring). Reuses the
    # same DataFrames already loaded above -- no extra file reads. Raises
    # if the premise this whole Part 2 caveat rests on (rule-based
    # relocates far LESS than either LLM arm, at every seed) is ever
    # violated -- a same-seed comparison, the strictest reading of "ever".
    relocation_by_key_seed: dict = {"gov": {}, "disabled": {}, "rulebased": {}}
    for key in ("gov", "disabled", "rulebased"):
        for seed in common_seeds:
            df = dfs_by_key_seed[key][seed]
            if "relocated" not in df.columns or "agent_id" not in df.columns:
                raise PrepError(f"flood relocation share: {key} seed {seed} is missing "
                                 f"'relocated' or 'agent_id' column")
            reloc_mask = (df["relocated"].astype(str).str.strip().str.lower()
                          .isin({"true", "1", "1.0", "yes"}))
            n_reloc = int(reloc_mask.sum())
            n_total = len(df)
            if n_total == 0:
                raise PrepError(f"flood relocation share: {key} seed {seed} has 0 rows")
            share_pct = 100.0 * n_reloc / n_total
            n_agents_ever = int(df.loc[reloc_mask, "agent_id"].nunique())
            n_agents_total = int(df["agent_id"].nunique())
            relocation_by_key_seed[key][seed] = {
                "n_reloc": n_reloc, "n_total": n_total, "share_pct": share_pct,
                "n_agents_ever": n_agents_ever, "n_agents_total": n_agents_total,
            }
            rows.append({"row_type": "flood_relocation_seed", "arm": key, "seed": seed,
                         "n_relocated_agent_years": n_reloc, "n_total_agent_years": n_total,
                         "relocation_share_pct": share_pct,
                         "n_agents_ever_relocated": n_agents_ever,
                         "n_agents_total": n_agents_total})

    for seed in common_seeds:
        rb_share = relocation_by_key_seed["rulebased"][seed]["share_pct"]
        gov_share = relocation_by_key_seed["gov"][seed]["share_pct"]
        dis_share = relocation_by_key_seed["disabled"][seed]["share_pct"]
        if rb_share >= gov_share:
            raise PrepError(f"flood relocation premise violated at seed {seed}: rule-based "
                             f"share {rb_share:.3f}% >= governed share {gov_share:.3f}% -- "
                             f"the 'JS gap is mostly structural' framing does not hold, do "
                             f"not report it without revisiting this")
        if rb_share >= dis_share:
            raise PrepError(f"flood relocation premise violated at seed {seed}: rule-based "
                             f"share {rb_share:.3f}% >= no-validator share {dis_share:.3f}% -- "
                             f"the 'JS gap is mostly structural' framing does not hold, do "
                             f"not report it without revisiting this")

    for key in ("gov", "disabled", "rulebased"):
        by_seed = relocation_by_key_seed[key]
        shares = [by_seed[s]["share_pct"] for s in common_seeds]
        agents_ever = [by_seed[s]["n_agents_ever"] for s in common_seeds]
        n = len(shares)
        rows.append({"row_type": "flood_relocation_arm_summary", "arm": key, "n_seeds": n,
                     "share_min": min(shares), "share_max": max(shares),
                     "share_mean": C.mean(shares), "share_sd": C.sd(shares) if n >= 2 else float("nan"),
                     "agents_ever_relocated_mean": C.mean(agents_ever)})
    print(f"  flood relocation share: rulebased={[round(relocation_by_key_seed['rulebased'][s]['share_pct'], 2) for s in common_seeds]}% "
          f"gov={[round(relocation_by_key_seed['gov'][s]['share_pct'], 2) for s in common_seeds]}% "
          f"disabled={[round(relocation_by_key_seed['disabled'][s]['share_pct'], 2) for s in common_seeds]}%")

    comparisons = [("gov_vs_rb", "gov", "rulebased"), ("dis_vs_rb", "disabled", "rulebased"),
                   ("gov_vs_dis", "gov", "disabled")]

    per_seed_year_mean: dict = {c: {} for c, _, _ in comparisons}
    for seed in common_seeds:
        df_gov = dfs_by_key_seed["gov"][seed]
        df_dis = dfs_by_key_seed["disabled"][seed]
        df_rb = dfs_by_key_seed["rulebased"][seed]
        per_year_js = {c: [] for c, _, _ in comparisons}
        for year in FLOOD_YEARS:
            dist = {}
            n_by_key = {}
            for key, df in (("gov", df_gov), ("disabled", df_dis), ("rulebased", df_rb)):
                df_y = df[df["year"] == year]
                dist[key] = _state_dist(df_y)
                n_by_key[key] = len(df_y)
            for comp_name, key_a, key_b in comparisons:
                js = _js_distance(dist[key_a], dist[key_b])
                per_year_js[comp_name].append(js)
                rows.append({"row_type": "flood_js_detail", "seed": seed,
                             "comparison": comp_name, "year": year, "js": js,
                             "n_gov": n_by_key["gov"], "n_dis": n_by_key["disabled"],
                             "n_rb": n_by_key["rulebased"]})
        for comp_name, _, _ in comparisons:
            year_mean = C.mean(per_year_js[comp_name])
            per_seed_year_mean[comp_name][seed] = year_mean
            rows.append({"row_type": "flood_js_seed_mean", "seed": seed,
                         "comparison": comp_name, "mean_over_years": year_mean,
                         "n_years": len(per_year_js[comp_name])})

    for comp_name, _, _ in comparisons:
        by_seed = per_seed_year_mean[comp_name]
        n = len(by_seed)
        vals = list(by_seed.values())
        rows.append({"row_type": "flood_js_arm_summary", "comparison": comp_name,
                     "n_seeds": n, "mean_over_years_mean": C.mean(vals),
                     "mean_over_years_sd": C.sd(vals) if n >= 2 else float("nan")})

    diffs = [per_seed_year_mean["gov_vs_rb"][s] - per_seed_year_mean["dis_vs_rb"][s]
             for s in common_seeds]
    for s, d in zip(common_seeds, diffs):
        rows.append({"row_type": "flood_js_contrast_pair", "seed": s,
                     "governed_value": per_seed_year_mean["gov_vs_rb"][s],
                     "ungoverned_value": per_seed_year_mean["dis_vs_rb"][s], "diff": d})
    stats = _sign_stats(diffs)
    rows.append({"row_type": "flood_js_contrast", **stats})
    print(f"  flood Part 2: JS distances computed for {len(common_seeds)}/5 seeds, "
          f"comparisons={[c for c, _, _ in comparisons]}")


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "section", "model", "arm", "seed", "series", "reference", "unit",
    "n_years", "r", "beta", "alpha", "kge", "rmse", "reason", "n_seeds",
    "r_mean", "r_sd", "beta_mean", "beta_sd", "alpha_mean", "alpha_sd",
    "kge_mean", "kge_sd", "rmse_mean", "rmse_sd", "metric",
    "governed_value", "ungoverned_value", "diff",
    "n_pairs", "mean_diff", "sd_diff", "min_diff", "max_diff", "n_sign_flips",
    "all_same_sign", "t", "df", "p_paired_t", "p_exact_permutation", "permutation_floor",
    "comparison", "year", "js", "n_gov", "n_dis", "n_rb", "mean_over_years", "n_years",
    "mean_over_years_mean", "mean_over_years_sd",
    "n_relocated_agent_years", "n_total_agent_years", "relocation_share_pct",
    "n_agents_ever_relocated", "n_agents_total",
    "share_min", "share_max", "share_mean", "share_sd", "agents_ever_relocated_mean",
]
# n_years appears twice in the prose above (irr_pair vs flood_js_seed_mean) --
# de-duplicate while preserving first-seen order for csv.DictWriter.
_seen = set()
FIELDNAMES = [c for c in FIELDNAMES if not (c in _seen or _seen.add(c))]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="R28 -- LLM arms vs traditional-ABM trajectory (flood part is "
                     "--corpus-aware; irrigation is not)")
    C.add_corpus_arg(parser)
    args = parser.parse_args()
    corpus = args.corpus
    suffix = C.corpus_suffix(corpus)

    C.banner(f"R28  Do the LLM arms reproduce the traditional-ABM trajectory, "
             f"and does the validator matter? (flood corpus={corpus})")
    rows: list = []

    print("\n-- Part 1: irrigation KGE/RMSE vs FQL baseline (always v08, unaffected "
          "by --corpus) --")
    per_cell = _irr_part1(rows)
    _irr_part1_summary(rows, per_cell)
    _irr_part1_contrast(rows, per_cell)
    _irr_part1_fql_reference(rows)

    print(f"\n-- Part 2: flood protection-state JS distance vs rule-based (SI), "
          f"corpus={corpus} --")
    if corpus != "v08":
        # Monkey-patch the already-imported gen_fig3_regen module's own
        # directory constants (module attributes, not a file edit -- see
        # --corpus docstring) so load_all_runs() reads the defaults
        # strict/disabled dirs instead of faf1bb12. RULEBASED_DIR is left
        # untouched: rule-based is deterministic, no defaults variant exists.
        import pathlib
        gov_root, _ = C.flood_corpus_dirs(corpus)["strict"]
        dis_root, _ = C.flood_corpus_dirs(corpus)["disabled"]
        orig_gov_dir, orig_dis_dir = FIG3.GOV_DIR, FIG3.DISABLED_DIR
        FIG3.GOV_DIR = pathlib.Path(C.FLOOD_RESULTS) / gov_root
        FIG3.DISABLED_DIR = pathlib.Path(C.FLOOD_RESULTS) / dis_root
        print(f"  FIG3.GOV_DIR -> {FIG3.GOV_DIR}")
        print(f"  FIG3.DISABLED_DIR -> {FIG3.DISABLED_DIR}")
        try:
            _irr_part2_flood(rows)
        finally:
            FIG3.GOV_DIR, FIG3.DISABLED_DIR = orig_gov_dir, orig_dis_dir
    else:
        _irr_part2_flood(rows)

    # Render the .md FIRST, fully in memory, before touching either output
    # file -- if render_md() raises, neither file is written/replaced, so a
    # crash never leaves a stale CSV paired with a fresh .md or vice versa.
    md_text = render_md(rows, corpus)

    csv_final = f"r28_trajectory_vs_traditional{suffix}.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, f"r28_trajectory_vs_traditional{suffix}.md")
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
# .md rendering -- built entirely from the `rows` list above.
# =============================================================================
_cp = lambda x: float(C.fmt(x))  # noqa: E731  route every display number through the
                                  # CSV's own 4dp text first (same double-rounding
                                  # guard r23 introduced as _csv_precision).


def _find(rows, row_type, **kw):
    out = []
    for r in rows:
        if r.get("row_type") != row_type:
            continue
        if all(r.get(k) == v for k, v in kw.items()):
            out.append(r)
    return out


def _kge_word(k: float) -> str:
    if k != k:
        return "undefined for"
    if k > 0.75:
        return "closely reproduces"
    if k > 0.5:
        return "reasonably reproduces"
    if k > 0.0:
        return "only loosely tracks"
    return "does not reproduce"


def _sign_word(mean_diff: float) -> str:
    if mean_diff > 0:
        return "governed scores HIGHER than ungoverned"
    if mean_diff < 0:
        return "governed scores LOWER than ungoverned"
    return "governed and ungoverned tie exactly"


def _sig_word(p: float) -> str:
    if p != p:
        return "undefined"
    if p < 0.0625 + 1e-9:
        return "at the n=5 exact-permutation floor (as significant as this design can show)"
    if p < 0.05:
        return "nominally significant (p<0.05)"
    return "not significant at p<0.05"


def render_md(rows: list, corpus: str = "v08") -> str:
    lines = []
    lines.append("# R28 -- LLM arms vs traditional-ABM trajectory, and does the validator matter")
    lines.append("")
    lines.append("Source: `r28_trajectory_vs_traditional.py`. Every number below is read live "
                 "from the `rows` list this script writes to the paired CSV -- nothing here is "
                 "hand-typed.")
    lines.append("")
    if corpus != "v08":
        lines.append(
            f"> **Flood corpus: {corpus}.** {C.flood_sampling_method_text(corpus)}. Part 1 "
            f"(irrigation) is UNCHANGED (always v08). Part 2's `FIG3.GOV_DIR`/"
            f"`FIG3.DISABLED_DIR` are monkey-patched at runtime to the {corpus} strict/"
            f"disabled dirs (never faf1bb12); `FIG3.RULEBASED_DIR` is unchanged "
            f"(deterministic, no defaults variant)."
        )
        lines.append("")

    # ---- Part 1a: per-arm KGE/RMSE summary table ---------------------------
    lines.append("## Part 1 -- irrigation: per-arm KGE / RMSE vs FQL baseline")
    lines.append("")
    for series_name, _col, _agg, unit in IRR_SERIES:
        lines.append(f"### Series: `{series_name}` (unit: {unit})")
        lines.append("")
        lines.append("| model | arm | reference | n_seeds | r_mean | beta_mean | alpha_mean | "
                     "KGE mean +- sd | RMSE mean +- sd |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for model, _commit in IRR_MODELS:
            for arm in IRR_ARMS:
                for ref_kind in FQL_REFERENCES:
                    recs = _find(rows, "irr_arm_summary", model=model, arm=arm,
                                 series=series_name, reference=ref_kind)
                    if not recs:
                        lines.append(f"| {model} | {arm} | {ref_kind} | 0 | -- | -- | -- | "
                                     f"no complete seeds | no complete seeds |")
                        continue
                    rec = recs[0]
                    lines.append(
                        f"| {model} | {arm} | {ref_kind} | {rec['n_seeds']} | "
                        f"{_cp(rec['r_mean']):.4f} | {_cp(rec['beta_mean']):.4f} | "
                        f"{_cp(rec['alpha_mean']):.4f} | "
                        f"{_cp(rec['kge_mean']):.4f} +- {_cp(rec['kge_sd']):.4f} | "
                        f"{_cp(rec['rmse_mean']):.2f} +- {_cp(rec['rmse_sd']):.2f} |"
                    )
        lines.append("")

    # ---- Part 1b: governed-ungoverned contrast -----------------------------
    lines.append("## Part 1 -- irrigation: governed (strict) minus ungoverned contrast")
    lines.append("")
    lines.append("Paired over the seeds common to both arms (n=5 unless a seed was skipped; "
                 "see `skipped` rows), df = n-1, exact sign-flip permutation "
                 f"(floor 2/32 = 0.0625 at n=5).")
    lines.append("")
    lines.append("| model | series | reference | metric | n_pairs | mean_diff | sd_diff | "
                 "t | df | p (paired t) | p (exact perm) | all_same_sign |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for model, _commit in IRR_MODELS:
        for series_name, _col, _agg, _unit in IRR_SERIES:
            for ref_kind in FQL_REFERENCES:
                for metric in ("kge", "rmse"):
                    recs = _find(rows, "irr_contrast", model=model, series=series_name,
                                 reference=ref_kind, metric=metric)
                    if not recs:
                        pend = _find(rows, "skipped", section="irr_contrast", model=model,
                                      series=series_name, reference=ref_kind)
                        reason = pend[0]["reason"] if pend else "no data"
                        lines.append(f"| {model} | {series_name} | {ref_kind} | {metric} | "
                                     f"-- | -- | -- | -- | -- | -- | -- | PENDING ({reason}) |")
                        continue
                    rec = recs[0]
                    lines.append(
                        f"| {model} | {series_name} | {ref_kind} | {metric} | "
                        f"{rec['n_pairs']} | {_cp(rec['mean_diff']):.4f} | "
                        f"{_cp(rec['sd_diff']):.4f} | {_cp(rec['t']):.3f} | {int(rec['df'])} | "
                        f"{_cp(rec['p_paired_t']):.4f} | {_cp(rec['p_exact_permutation']):.4f} | "
                        f"{rec['all_same_sign']} |"
                    )
    lines.append("")

    # ---- Part 1c: FQL-vs-FQL reference --------------------------------------
    lines.append("## Part 1 -- FQL matched vs FQL rebalanced (same-model reference)")
    lines.append("")
    lines.append("How different two runs of the SAME traditional FQL baseline are from each "
                 "other (rebalanced=sim, matched=ref), at the identical seed and the identical "
                 "KGE/RMSE definition used for every LLM-vs-FQL row above -- a calibration "
                 "point for what an LLM arm's KGE against FQL actually means.")
    lines.append("")
    lines.append("| series | n_seeds | r_mean | beta_mean | alpha_mean | KGE mean +- sd | "
                 "RMSE mean +- sd |")
    lines.append("|---|---|---|---|---|---|---|")
    for series_name, _col, _agg, unit in IRR_SERIES:
        recs = _find(rows, "irr_fql_reference_summary", series=series_name)
        if not recs:
            lines.append(f"| {series_name} | 0 | -- | -- | -- | no complete seeds | "
                         f"no complete seeds |")
            continue
        rec = recs[0]
        lines.append(
            f"| {series_name} | {rec['n_seeds']} | {_cp(rec['r_mean']):.4f} | "
            f"{_cp(rec['beta_mean']):.4f} | {_cp(rec['alpha_mean']):.4f} | "
            f"{_cp(rec['kge_mean']):.4f} +- {_cp(rec['kge_sd']):.4f} | "
            f"{_cp(rec['rmse_mean']):.2f} +- {_cp(rec['rmse_sd']):.2f} |"
        )
    lines.append("")

    # ---- Part 2: flood JS table ---------------------------------------------
    lines.append("## Part 2 -- flood: protection-state Jensen-Shannon distance (SI diagnostic, "
                 "not a headline)")
    lines.append("")
    rb_reloc = _find(rows, "flood_relocation_arm_summary", arm="rulebased")
    gov_reloc = _find(rows, "flood_relocation_arm_summary", arm="gov")
    dis_reloc = _find(rows, "flood_relocation_arm_summary", arm="disabled")
    if rb_reloc and gov_reloc and dis_reloc:
        rb, gv, ds = rb_reloc[0], gov_reloc[0], dis_reloc[0]
        reloc_sentence = (
            f"Categorical composition over the 5 protection states; KGE does not apply. "
            f"`gov_vs_rb`/`dis_vs_rb` = each LLM arm's distance to the rule-based baseline; "
            f"`gov_vs_dis` = governed vs no-validator distance directly (not part of the "
            f"paired contrast below). The rule-based baseline is NOT relocation-free: it "
            f"relocates {_cp(rb['share_min']):.1f}-{_cp(rb['share_max']):.1f}% of agent-years "
            f"across the 5 seeds, but that is far below the governed arm's "
            f"{_cp(gv['share_mean']):.1f}% and the no-validator arm's "
            f"{_cp(ds['share_mean']):.1f}% mean relocation share (verified at every seed "
            f"individually, not just on average) -- so part of the JS gap to rule-based "
            f"below is this relocation-share gap, not a governance difference."
        )
    else:
        reloc_sentence = (
            "Categorical composition over the 5 protection states; KGE does not apply. "
            "`gov_vs_rb`/`dis_vs_rb` = each LLM arm's distance to the rule-based baseline; "
            "`gov_vs_dis` = governed vs no-validator distance directly (not part of the "
            "paired contrast below). Relocation-share rows pending."
        )
    lines.append(reloc_sentence)
    lines.append("")
    lines.append("### Relocation share by arm (relocated agent-years / all agent-years)")
    lines.append("")
    lines.append("| arm | n_seeds | share_min % | share_max % | share_mean +- sd % | "
                 "agents_ever_relocated_mean |")
    lines.append("|---|---|---|---|---|---|")
    for arm_key in ("rulebased", "gov", "disabled"):
        recs = _find(rows, "flood_relocation_arm_summary", arm=arm_key)
        if not recs:
            lines.append(f"| {arm_key} | 0 | -- | -- | pending | -- |")
            continue
        rec = recs[0]
        lines.append(
            f"| {arm_key} | {rec['n_seeds']} | {_cp(rec['share_min']):.2f} | "
            f"{_cp(rec['share_max']):.2f} | {_cp(rec['share_mean']):.2f} +- "
            f"{_cp(rec['share_sd']):.2f} | {_cp(rec['agents_ever_relocated_mean']):.1f} |"
        )
    lines.append("")
    lines.append("| comparison | n_seeds | mean_over_years mean +- sd |")
    lines.append("|---|---|---|")
    for comp in ("gov_vs_rb", "dis_vs_rb", "gov_vs_dis"):
        recs = _find(rows, "flood_js_arm_summary", comparison=comp)
        if not recs:
            lines.append(f"| {comp} | 0 | pending |")
            continue
        rec = recs[0]
        lines.append(f"| {comp} | {rec['n_seeds']} | "
                     f"{_cp(rec['mean_over_years_mean']):.4f} +- "
                     f"{_cp(rec['mean_over_years_sd']):.4f} |")
    lines.append("")
    contrast_recs = _find(rows, "flood_js_contrast")
    if contrast_recs:
        rec = contrast_recs[0]
        lines.append(f"**Paired contrast (governed-to-rulebased minus no-validator-to-rulebased "
                     f"JS distance), n={rec['n_pairs']}:** mean_diff={_cp(rec['mean_diff']):.4f}, "
                     f"sd_diff={_cp(rec['sd_diff']):.4f}, t={_cp(rec['t']):.3f}, "
                     f"df={int(rec['df'])}, p(paired t)={_cp(rec['p_paired_t']):.4f}, "
                     f"p(exact perm)={_cp(rec['p_exact_permutation']):.4f}, "
                     f"all_same_sign={rec['all_same_sign']}.")
    else:
        lines.append("**Paired contrast: PENDING** (fewer than 5 seeds complete on all three "
                     "flood arms).")
    lines.append("")

    # ---- Part 3: plain read (<=5 sentences, direction words from values) ---
    lines.append("## Plain read")
    lines.append("")
    sentences = []

    kge_summaries = _find(rows, "irr_arm_summary", reference="matched")
    if kge_summaries:
        best = max(kge_summaries, key=lambda r: r["kge_mean"] if r["kge_mean"] == r["kge_mean"] else -999)
        worst = min(kge_summaries, key=lambda r: r["kge_mean"] if r["kge_mean"] == r["kge_mean"] else 999)
        sentences.append(
            f"Against the primary (matched) FQL reference, LLM-arm KGE against the traditional "
            f"trajectory ranges from {_kge_word(worst['kge_mean'])} it "
            f"({worst['model']}/{worst['arm']}/{worst['series']}, KGE={_cp(worst['kge_mean']):.2f}) "
            f"to {_kge_word(best['kge_mean'])} it "
            f"({best['model']}/{best['arm']}/{best['series']}, KGE={_cp(best['kge_mean']):.2f})."
        )

    fql_ref = _find(rows, "irr_fql_reference_summary")
    if fql_ref:
        parts = ", ".join(f"{r['series']} KGE={_cp(r['kge_mean']):.2f}" for r in fql_ref)
        sentences.append(
            f"As a calibration point, two runs of the SAME traditional FQL baseline "
            f"(rebalanced vs matched cluster split) already disagree with each other at "
            f"{parts} -- an LLM arm's KGE has to be read against that non-zero baseline "
            f"disagreement, not against a KGE=1 expectation."
        )

    contrast_recs_irr = _find(rows, "irr_contrast", metric="kge")
    if contrast_recs_irr:
        signs = [_sign_word(r["mean_diff"]) for r in contrast_recs_irr]
        sigs = [_sig_word(r["p_exact_permutation"]) for r in contrast_recs_irr]
        # majority direction across the (model, series, reference) cells
        n_higher = sum(1 for r in contrast_recs_irr if r["mean_diff"] > 0)
        n_lower = sum(1 for r in contrast_recs_irr if r["mean_diff"] < 0)
        if n_higher > n_lower:
            direction = "governed (strict) tends to score a HIGHER KGE than ungoverned"
        elif n_lower > n_higher:
            direction = "governed (strict) tends to score a LOWER KGE than ungoverned"
        else:
            direction = "governed and ungoverned split evenly on KGE direction"
        any_sig = any("floor" in s or "nominally" in s for s in sigs)
        sentences.append(
            f"On the irrigation KGE contrast across the {len(contrast_recs_irr)} "
            f"(model x series x reference) cells, {direction}"
            f"{', with at least one cell reaching the strongest evidence n=5 permits' if any_sig else ', though none of these cells reaches even nominal significance'}."
        )

    flood_contrast = _find(rows, "flood_js_contrast")
    rb_reloc = _find(rows, "flood_relocation_arm_summary", arm="rulebased")
    gov_reloc = _find(rows, "flood_relocation_arm_summary", arm="gov")
    dis_reloc = _find(rows, "flood_relocation_arm_summary", arm="disabled")
    if flood_contrast:
        rec = flood_contrast[0]
        d = rec["mean_diff"]
        word = ("closer to" if d < 0 else ("farther from" if d > 0 else "equally far from"))
        sentences.append(
            f"For flood (SI only, categorical, KGE not applicable), the governed arm sits "
            f"{word} the rule-based trajectory than the no-validator arm "
            f"(JS-distance mean_diff={_cp(d):.4f}, {_sig_word(rec['p_exact_permutation'])})."
        )
    else:
        sentences.append("Flood JS-distance contrast is pending (fewer than 5 seeds complete "
                         "on all three flood arms).")
    if rb_reloc and gov_reloc and dis_reloc:
        rb, gv, ds = rb_reloc[0], gov_reloc[0], dis_reloc[0]
        sentences.append(
            f"The rule-based baseline relocates {_cp(rb['share_min']):.1f}-"
            f"{_cp(rb['share_max']):.1f}% of agent-years versus {_cp(gv['share_mean']):.1f}% / "
            f"{_cp(ds['share_mean']):.1f}% in the LLM arms, so most of the LLM arms' JS gap to "
            f"rule-based is structural (relocation share), not governance."
        )
    else:
        sentences.append("Flood relocation-share comparison is pending.")

    for s in sentences[:5]:
        lines.append(s)
        lines.append("")

    # ---- Method block --------------------------------------------------------
    lines.append("## Method")
    lines.append("")
    lines.append(
        "KGE here is computed against a REFERENCE MODEL (the traditional FQL agent-based "
        "baseline), not against field observations -- FQL is itself a simulated policy, so a "
        "high KGE means \"tracks the traditional ABM's trajectory,\" not \"matches reality.\" "
        "Series and columns: `mead_elevation` from `simulation_log.csv` column "
        "`lake_mead_level` (feet; a single basin-level value shared by all agents within a "
        "year, aggregated with `first`, verified via a nunique==1 check per year); "
        "`basin_demand` from column `request` (acre-feet per agent-year, aggregated with "
        "`sum` across all 78 agents per year). Units verified against "
        "`examples/irrigation_abm/analysis/fig_wrr_irrigation.py`, which labels these same "
        "columns `lake_mead_ft` and `request_af`. Formula: "
        "KGE = 1 - sqrt((r-1)^2 + (beta-1)^2 + (alpha-1)^2), with r = Pearson correlation("
        "sim, ref), beta = mean(sim)/mean(ref), alpha = sd(sim)/sd(ref) (ddof=1); sim = LLM "
        "arm (or FQL-rebalanced, for the FQL-vs-FQL reference row), ref = FQL (or "
        "FQL-matched). RMSE reported in the series' own unit. For flood, `prot_state` is "
        "read from `gen_fig3_regen.py::load_all_runs()` (imported read-only, not "
        "re-implemented) over the 5 states "
        + ", ".join(PROT_STATES) + "; Jensen-Shannon distance is base-2 (bounded [0,1] by "
        "construction) between two per-year state-share vectors."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
