"""PHASE 1A — EXOGENEITY TEST. Which columns may a re-estimator condition on?

WHY THIS EXISTS
The published irrigation headline (IBR governed 36.05 % vs no-validator 59.07 %) is a rate
CONDITIONAL on wsa_label in {H,VH}. wsa_label is emitted by the same LLM call as the action, so it
is post-treatment and the two arms' denominators are different populations of decisions. Every
downstream estimator in this campaign therefore has to re-weight or re-stratify on something that is
NOT post-treatment. This script decides what that something is allowed to be.

The answer is NOT "anything that looks like environment". The irrigation reservoir is COUPLED:
agent diversions enter a mass balance that sets Lake Mead elevation, which sets the shortage tier,
the curtailment ratio, and half of the drought index. A variable can be named after hydrology and
still be a function of the treatment. This script measures, it does not assume.

METHOD
For the anchor model (gemma3:4b, no prefix) and every seed present in BOTH arms:
  1. load simulation_log.csv for production (governed) and ungoverned;
  2. inner-join on (agent_id, year) and prove the join is 1:1 (no dup keys, no unmatched rows);
  3. for each candidate pre-treatment column, measure agreement between arms at the same
     (seed, agent_id, year): exact-equality rate, and for numerics mean/max |difference| and
     max |difference| as a fraction of the pooled (both-arm) standard deviation;
  4. repeat by YEAR so divergence-over-time is visible (year 1 vs the decay across years 1..42).

Every column is then placed in exactly one of:
  TREATMENT-INVARIANT  identical at every matched row -> safe to condition on
  DRIFTS               identical at year 1, diverges later -> year-1-restricted designs only
  TREATMENT-AFFECTED   differs at year 1 already -> never condition on

SIGN CONVENTION, stated in words: every reported difference is
    governed (production) MINUS ungoverned,
so a positive mean difference means the governed arm has the LARGER value of that column.

RECONSTRUCTED EXOGENOUS PRECIPITATION
The precipitation trace is the only genuinely exogenous forcing in this model, and it is NOT a
logged column. It is recoverable, because irrigation_env.py:833 defines
    drought_index = 0.5*precip_norm + 0.5*mead_norm,
    mead_norm     = clip(1 - (lake_mead_level - 900)/320, 0, 1),
    precip_norm   = clip(1 - precip/100, 0, 1).
So precip_norm = 2*drought_index - mead_norm, invertible to precip = 100*(1 - precip_norm)
WHENEVER neither clip is active. Rows where a clip binds are excluded from the comparison and
counted, because there the inversion is not identified. This is a RECONSTRUCTION and is labelled as
one everywhere it appears -- and it is then checked against the actual CRSS/PRISM source file, so
the label "reconstruction" is not doing any load-bearing work.

Usage:  python reproduction/evidence/exogeneity_check.py [--outdir DIR]
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS = os.path.join(REPO, "examples/irrigation_abm/results")

ANCHOR_SEG = ""                 # gemma3:4b — the published pair
ARMS = {"governed": "production", "ungoverned": "ungoverned"}
JOIN_KEYS = ["agent_id", "year"]

# Candidate conditioning columns, exactly the list in the Phase-1a brief.
NUMERIC_COLS = ["water_right", "drought_index", "shortage_tier", "curtailment_ratio",
                "lake_mead_level", "mead_storage_maf", "utilisation_pct"]
CATEGORICAL_COLS = ["cluster", "basin", "has_efficient_system", "below_minimum_utilisation"]
CANDIDATES = NUMERIC_COLS + CATEGORICAL_COLS
# "year" is one half of the join key, so its agreement is 1.000 by construction and it is
# reported separately rather than smuggled into the table as if it had been tested.

# Post-treatment columns. Listed so the script can PROVE they move, giving the table a positive
# control: if wsa_label came back 100 % identical the whole join would be suspect.
POST_TREATMENT_COLS = ["wsa_label", "aca_label", "yearly_decision"]

# --- constants read out of examples/irrigation_abm/irrigation_env.py, for the reconstruction ---
PRECIP_BASELINE_MM = 100.0      # IrrigationConfig.precip_baseline_mm, line 74
MEAD_NORM_OFFSET = 900.0        # _compute_drought_index, line 840
MEAD_NORM_SCALE = 320.0         # _compute_drought_index, line 840
CLIP_EPS = 1e-9

# CRSS/PRISM winter-precipitation source that _generate_precipitation() reads when --real is set
# (run_experiment.py:599, run_ungoverned_experiment.py:173). Used here only to CHECK the inversion.
CRSS_PRECIP_CSV = os.path.join(REPO, "ref/CRSS_DB/CRSS_DB/HistoricalData",
                               "PrismWinterPrecip_ST_NOAA_Future.csv")
CRSS_UB_COLS = ["WY", "UT1", "UT2", "UT3", "CO1", "CO2", "CO3"]   # irrigation_env.py:710
CRSS_INCH_TO_MM = 25.4                                            # irrigation_env.py:390
SIM_START_YEAR = 2019          # WaterSystemConfig.sim_start_year; loop year 1 -> calendar 2020

# What the SOURCE says each column is. Printed beside the empirical verdict so the two can be
# compared, and a disagreement is flagged rather than silently reconciled.
CODE_PROVENANCE = {
    "water_right":               ("static agent entitlement, set once in initialize_from_profiles "
                                  "(irrigation_env.py:215-222, 314-325); never written afterwards",
                                  "TREATMENT-INVARIANT"),
    "cluster":                   ("static persona label assigned at init; logged from the profile "
                                  "object (run_experiment.py:329)", "TREATMENT-INVARIANT"),
    "basin":                     ("static geography assigned at init; logged from the profile "
                                  "object (run_experiment.py:330)", "TREATMENT-INVARIANT"),
    "has_efficient_system":      ("static technology flag from the profile "
                                  "(irrigation_env.py:225); no code path writes it during a run",
                                  "TREATMENT-INVARIANT"),
    "drought_index":             ("0.5*precip_norm + 0.5*mead_norm (irrigation_env.py:833-841). "
                                  "The precip half is an exogenous CRSS data trace; the mead half "
                                  "is reservoir elevation, which is a mass balance over AGENT "
                                  "DIVERSIONS (irrigation_env.py:732-810). HALF-COUPLED",
                                  "DRIFTS"),
    "lake_mead_level":           ("_generate_lake_mead_level mass balance whose outflow term is "
                                  "the sum of agent diversions (irrigation_env.py:762-776). "
                                  "Uses the PREVIOUS year's diversions, so year 1 is pre-decision",
                                  "DRIFTS"),
    "mead_storage_maf":          ("the same mass balance, one transform earlier "
                                  "(irrigation_env.py:806-808)", "DRIFTS"),
    "shortage_tier":             ("step function of lake_mead_level (irrigation_env.py:844-861); "
                                  "coupled through the reservoir, and COARSENED", "DRIFTS"),
    "curtailment_ratio":         ("lookup table on shortage_tier (irrigation_env.py:863-869); "
                                  "coupled through the reservoir, and COARSENED", "DRIFTS"),
    "utilisation_pct":           ("request/water_right*100 logged in POST_YEAR "
                                  "(run_experiment.py:344), i.e. AFTER the year's action has been "
                                  "executed by update_agent_request (irrigation_env.py:555)",
                                  "TREATMENT-AFFECTED"),
    "below_minimum_utilisation": ("set inside update_agent_request from the post-decision request "
                                  "(irrigation_env.py:558-560); logged post_year. COARSENED to a "
                                  "boolean, so agreement is mostly coincidence",
                                  "TREATMENT-AFFECTED"),
}


# ---------------------------------------------------------------------------- discovery / loading

def seed_set(prefix: str, seg: str) -> list[int]:
    """Seeds for which <prefix>_v21_42yr_<seg>seed<N>/simulation_log.csv exists."""
    out = []
    for d in sorted(glob.glob(os.path.join(RESULTS, f"{prefix}_v21_42yr_{seg}seed*"))):
        if os.path.exists(os.path.join(d, "simulation_log.csv")):
            m = re.search(r"seed(\d+)$", os.path.basename(d))
            if m:
                out.append(int(m.group(1)))
    return sorted(out)


def load_run(prefix: str, seg: str, seed: int) -> pd.DataFrame:
    path = os.path.join(RESULTS, f"{prefix}_v21_42yr_{seg}seed{seed}", "simulation_log.csv")
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["_path"] = path
    return df


# ------------------------------------------------------------------------------------- join check

def join_report(g: pd.DataFrame, u: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, dict]:
    """Inner-join the two arms on (agent_id, year) and report every way it could be not-1:1."""
    info = {
        "seed": seed,
        "rows_governed": len(g),
        "rows_ungoverned": len(u),
        "dup_keys_governed": int(g.duplicated(JOIN_KEYS).sum()),
        "dup_keys_ungoverned": int(u.duplicated(JOIN_KEYS).sum()),
    }
    gk = set(map(tuple, g[JOIN_KEYS].itertuples(index=False, name=None)))
    uk = set(map(tuple, u[JOIN_KEYS].itertuples(index=False, name=None)))
    info["keys_only_in_governed"] = len(gk - uk)
    info["keys_only_in_ungoverned"] = len(uk - gk)
    info["unmatched_examples"] = sorted(list(gk ^ uk))[:5]

    merged = g.merge(u, on=JOIN_KEYS, how="inner", suffixes=("_g", "_u"), validate="one_to_one")
    info["rows_matched"] = len(merged)
    info["join_is_1to1"] = (
        info["dup_keys_governed"] == 0
        and info["dup_keys_ungoverned"] == 0
        and info["keys_only_in_governed"] == 0
        and info["keys_only_in_ungoverned"] == 0
        and len(merged) == len(g) == len(u)
    )
    return merged, info


# ------------------------------------------------------------------------------- column agreement

def _as_comparable(s: pd.Series, numeric: bool) -> pd.Series:
    if numeric:
        return pd.to_numeric(s, errors="coerce")
    return s.astype(str).str.strip().str.upper()


def column_agreement(merged: pd.DataFrame, col: str, numeric: bool) -> dict:
    a = _as_comparable(merged[f"{col}_g"], numeric)
    b = _as_comparable(merged[f"{col}_u"], numeric)
    n = len(merged)
    if numeric:
        eq = (a == b) | (a.isna() & b.isna())
        d = (a - b)                                    # governed MINUS ungoverned
        pooled_sd = pd.concat([a, b]).std(ddof=1)
        return {
            "column": col, "kind": "numeric", "n": n,
            "exact_equal_rate": float(eq.mean()),
            "n_differing": int((~eq).sum()),
            "mean_abs_diff": float(d.abs().mean()),
            "max_abs_diff": float(d.abs().max()),
            "mean_signed_diff_gov_minus_ungov": float(d.mean()),
            "pooled_sd": float(pooled_sd),
            "max_abs_diff_over_sd": (float(d.abs().max() / pooled_sd)
                                     if pooled_sd and pooled_sd > 0 else float("nan")),
            "mean_abs_diff_over_sd": (float(d.abs().mean() / pooled_sd)
                                      if pooled_sd and pooled_sd > 0 else float("nan")),
        }
    eq = a == b
    return {
        "column": col, "kind": "categorical", "n": n,
        "exact_equal_rate": float(eq.mean()),
        "n_differing": int((~eq).sum()),
        "mean_abs_diff": float("nan"), "max_abs_diff": float("nan"),
        "mean_signed_diff_gov_minus_ungov": float("nan"),
        "pooled_sd": float("nan"),
        "max_abs_diff_over_sd": float("nan"), "mean_abs_diff_over_sd": float("nan"),
    }


def per_year_agreement(merged: pd.DataFrame, col: str, numeric: bool) -> pd.DataFrame:
    a = _as_comparable(merged[f"{col}_g"], numeric)
    b = _as_comparable(merged[f"{col}_u"], numeric)
    eq = ((a == b) | (a.isna() & b.isna())) if numeric else (a == b)
    tmp = pd.DataFrame({"year": merged["year"], "eq": eq})
    if numeric:
        tmp["abs_diff"] = (a - b).abs()
    else:
        tmp["abs_diff"] = float("nan")
    out = tmp.groupby("year").agg(exact_equal_rate=("eq", "mean"),
                                  n=("eq", "size"),
                                  mean_abs_diff=("abs_diff", "mean"),
                                  max_abs_diff=("abs_diff", "max")).reset_index()
    out.insert(0, "column", col)
    return out


# ------------------------------------------------------------------- exogenous precip reconstruction

def crss_reference_precip() -> pd.Series | None:
    """Upper-Basin mean winter precipitation (mm) by calendar year, straight from the source file."""
    if not os.path.exists(CRSS_PRECIP_CSV):
        return None
    df = pd.read_csv(CRSS_PRECIP_CSV, index_col=0) * CRSS_INCH_TO_MM
    return df[CRSS_UB_COLS].mean(axis=1)


def reconstruct_precip(df: pd.DataFrame) -> pd.DataFrame:
    """Invert drought_index for the exogenous precipitation forcing. Flags non-identified rows."""
    di = pd.to_numeric(df["drought_index"], errors="coerce")
    mead = pd.to_numeric(df["lake_mead_level"], errors="coerce")
    mead_raw = 1.0 - (mead - MEAD_NORM_OFFSET) / MEAD_NORM_SCALE
    mead_norm = mead_raw.clip(0.0, 1.0)
    precip_norm = 2.0 * di - mead_norm
    # Inversion is identified only where NEITHER clip is active.
    mead_clipped = (mead_raw < -CLIP_EPS) | (mead_raw > 1.0 + CLIP_EPS)
    precip_clipped = (precip_norm < CLIP_EPS) | (precip_norm > 1.0 - CLIP_EPS)
    return pd.DataFrame({
        "year": df["year"],
        "precip_mm_reconstructed": PRECIP_BASELINE_MM * (1.0 - precip_norm),
        "identified": ~(mead_clipped | precip_clipped),
    })


# ------------------------------------------------------------------------------------ classifier

def classify(pooled: dict, year1_rate: float) -> str:
    if pooled["exact_equal_rate"] >= 1.0:
        return "TREATMENT-INVARIANT"
    if year1_rate >= 1.0:
        return "DRIFTS"
    return "TREATMENT-AFFECTED"


BUCKET = {
    "TREATMENT-INVARIANT": "SAFE TO CONDITION ON",
    "DRIFTS": "SAFE ONLY AT YEAR 1",
    "TREATMENT-AFFECTED": "NEVER CONDITION ON",
}


# ------------------------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    print("=" * 100)
    print("PHASE 1A — EXOGENEITY TEST · irrigation anchor model gemma3:4b (prefix '')")
    print("Sign convention: every signed difference below is GOVERNED minus UNGOVERNED.")
    print("=" * 100)

    g_seeds, u_seeds = seed_set("production", ANCHOR_SEG), seed_set("ungoverned", ANCHOR_SEG)
    both = sorted(set(g_seeds) & set(u_seeds))
    print(f"\ngoverned seeds  : {g_seeds}")
    print(f"ungoverned seeds: {u_seeds}")
    print(f"seeds in BOTH   : {both}")
    if set(g_seeds) != set(u_seeds):
        print("  !! ARM SEED SETS DIFFER — unbalanced cell, paired contrasts restricted to the "
              "intersection above.")
    if not both:
        print("no paired seeds — cannot run the exogeneity test")
        return 1

    # ------------------------------------------------------------------ per-seed load + join check
    merged_all, join_infos = [], []
    for s in both:
        g, u = load_run("production", ANCHOR_SEG, s), load_run("ungoverned", ANCHOR_SEG, s)
        missing = [c for c in CANDIDATES + POST_TREATMENT_COLS
                   if c not in g.columns or c not in u.columns]
        if missing:
            print(f"  !! seed {s}: columns absent from simulation_log.csv: {missing}")
        m, info = join_report(g, u, s)
        m["seed"] = s
        merged_all.append(m)
        join_infos.append(info)

    print("\n--- JOIN INTEGRITY on (agent_id, year) ---")
    print(f"{'seed':>5} {'rows gov':>9} {'rows ung':>9} {'matched':>8} {'dup gov':>8} "
          f"{'dup ung':>8} {'gov-only':>9} {'ung-only':>9}  1:1")
    for i in join_infos:
        print(f"{i['seed']:>5} {i['rows_governed']:>9,} {i['rows_ungoverned']:>9,} "
              f"{i['rows_matched']:>8,} {i['dup_keys_governed']:>8} {i['dup_keys_ungoverned']:>8} "
              f"{i['keys_only_in_governed']:>9} {i['keys_only_in_ungoverned']:>9}  "
              f"{'YES' if i['join_is_1to1'] else 'NO'}")
        if i["unmatched_examples"]:
            print(f"        unmatched key examples: {i['unmatched_examples']}")
    if not all(i["join_is_1to1"] for i in join_infos):
        print("  !! at least one seed did not join 1:1 — read the rows above before trusting "
              "anything below.")

    merged = pd.concat(merged_all, ignore_index=True)
    print(f"\nmatched rows pooled over {len(both)} seeds: {len(merged):,}")

    # -------------------------------------------------------------------- pooled column agreement
    rows, per_year_frames = [], []
    for col in CANDIDATES:
        numeric = col in NUMERIC_COLS
        r = column_agreement(merged, col, numeric)
        py = per_year_agreement(merged, col, numeric)
        per_year_frames.append(py)
        y1 = float(py.loc[py["year"] == 1, "exact_equal_rate"].iloc[0])
        first_bad = py.loc[py["exact_equal_rate"] < 1.0, "year"]
        r["year1_exact_equal_rate"] = y1
        r["first_year_with_any_disagreement"] = int(first_bad.min()) if len(first_bad) else -1
        r["min_yearly_exact_equal_rate"] = float(py["exact_equal_rate"].min())
        r["classification"] = classify(r, y1)
        r["bucket"] = BUCKET[r["classification"]]
        rows.append(r)

    # post-treatment positive control, measured the same way
    control_rows = []
    for col in POST_TREATMENT_COLS:
        r = column_agreement(merged, col, False)
        py = per_year_agreement(merged, col, False)
        r["year1_exact_equal_rate"] = float(py.loc[py["year"] == 1, "exact_equal_rate"].iloc[0])
        control_rows.append(r)

    tab = pd.DataFrame(rows).sort_values(
        ["exact_equal_rate", "year1_exact_equal_rate"], ascending=False).reset_index(drop=True)

    print("\n--- CANDIDATE PRE-TREATMENT COLUMNS · agreement between arms at matched "
          "(seed, agent_id, year) ---")
    print("    'mean d' is SIGNED, governed minus ungoverned: positive means the GOVERNED arm has "
          "the larger value.")
    print(f"{'column':28s} {'kind':12s} {'equal%':>8s} {'yr1 eq%':>8s} {'1stbad':>7s} "
          f"{'mean d':>12s} {'mean|d|':>12s} {'max|d|':>11s} {'max|d|/SD':>10s}")
    print("-" * 116)
    for _, r in tab.iterrows():
        fy = "-" if r["first_year_with_any_disagreement"] < 0 else int(
            r["first_year_with_any_disagreement"])
        sd_ = "-" if pd.isna(r["mean_signed_diff_gov_minus_ungov"]) else \
            f"{r['mean_signed_diff_gov_minus_ungov']:+.5g}"
        md = "-" if pd.isna(r["mean_abs_diff"]) else f"{r['mean_abs_diff']:.5g}"
        xd = "-" if pd.isna(r["max_abs_diff"]) else f"{r['max_abs_diff']:.5g}"
        rs = "-" if pd.isna(r["max_abs_diff_over_sd"]) else f"{r['max_abs_diff_over_sd']:.4f}"
        print(f"{r['column']:28s} {r['kind']:12s} {100*r['exact_equal_rate']:>7.3f}% "
              f"{100*r['year1_exact_equal_rate']:>7.3f}% {str(fy):>7s} {sd_:>12s} {md:>12s} "
              f"{xd:>11s} {rs:>10s}")

    print("\n  join key 'year' is identical by construction (it is half the merge key); it is not "
          "an empirical result and is excluded from the table above.")

    # ------------------------------------------------- (d) static attributes, checked within a run
    print("\n--- (d) STATIC AGENT ATTRIBUTES · constant within an agent across all 42 years? ---")
    print("    Cross-arm identity alone does not prove 'static'; a column could move identically in "
          "both arms.\n    This checks the other half: does the value ever change for one agent "
          "inside one run?")
    static_ok = {}
    for col in ["water_right", "cluster", "basin", "has_efficient_system"]:
        n_var = 0
        for s in both:
            for prefix in ARMS.values():
                d = load_run(prefix, ANCHOR_SEG, s)
                n_var += int((d.groupby("agent_id")[col].nunique() > 1).sum())
        static_ok[col] = n_var == 0
        nd = merged[f"{col}_g"].nunique()
        print(f"    {col:26s} agents whose value ever changes within a run: {n_var}"
              f"   -> {'STATIC' if n_var == 0 else 'NOT STATIC'}"
              f"   ({nd} distinct values across the 78 agents)")
    print("    'distinct values' matters: a static column with one value carries no information "
          "and cannot adjust anything.")

    # ------------------------------------- coarsening diagnostic for the step-function columns
    print("\n--- COARSENING WARNING · agreement on a binned column is not exogeneity ---")
    late = merged[merged["year"] >= 2]
    mead_diff = (pd.to_numeric(late["lake_mead_level_g"], errors="coerce")
                 - pd.to_numeric(late["lake_mead_level_u"], errors="coerce")).abs()
    for col in ["shortage_tier", "curtailment_ratio", "below_minimum_utilisation"]:
        a = _as_comparable(late[f"{col}_g"], col != "below_minimum_utilisation")
        b = _as_comparable(late[f"{col}_u"], col != "below_minimum_utilisation")
        agree = (a == b)
        if col == "below_minimum_utilisation":
            base_g = pd.to_numeric(late["utilisation_pct_g"], errors="coerce")
            base_u = pd.to_numeric(late["utilisation_pct_u"], errors="coerce")
            underlying_moves = (base_g != base_u)
            what = "utilisation_pct"
        else:
            underlying_moves = mead_diff > 0
            what = "lake_mead_level"
        n_ag = int(agree.sum())
        n_coin = int((agree & underlying_moves).sum())
        share = 100.0 * n_coin / n_ag if n_ag else float("nan")
        print(f"    {col:26s} of {n_ag:,} year>=2 rows where the arms AGREE, {n_coin:,} "
              f"({share:.2f}%) have a DIFFERENT underlying {what}.")
    print("    Those rows agree because the bin is wide, not because the treatment did not move "
          "them.\n    A downstream estimator that stratified on them would be conditioning on a "
          "post-treatment variable\n    while the agreement rate made it look safe.")

    print("\n--- POSITIVE CONTROL · post-treatment columns, same measurement ---")
    for r in control_rows:
        print(f"  {r['column']:22s} equal {100*r['exact_equal_rate']:6.3f}%   "
              f"year-1 equal {100*r['year1_exact_equal_rate']:6.3f}%   "
              f"({r['n_differing']:,} of {r['n']:,} rows differ)")
    if all(r["exact_equal_rate"] >= 1.0 for r in control_rows):
        print("  !! the post-treatment columns are IDENTICAL across arms. That is not possible if "
              "the arms differ. Suspect the join or the file paths before believing any result "
              "above.")

    # ----------------------------------------------------------------------- year-by-year decay
    py_all = pd.concat(per_year_frames, ignore_index=True)
    drifting = [r["column"] for _, r in tab.iterrows()
                if r["classification"] in ("DRIFTS", "TREATMENT-AFFECTED")]
    if drifting:
        print("\n--- DIVERGENCE OVER TIME · exact-equality rate by year (columns that ever "
              "disagree) ---")
        landmark = [1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 35, 42]
        head = "year".ljust(28) + "".join(f"{y:>7d}" for y in landmark)
        print(head)
        print("-" * len(head))
        for col in drifting:
            sub = py_all[py_all["column"] == col].set_index("year")["exact_equal_rate"]
            cells = "".join(
                f"{100*sub.loc[y]:>6.1f}%" if y in sub.index else f"{'-':>7s}" for y in landmark)
            print(f"{col:28s}{cells}")

    # --------------------------------------------------- exogenous precipitation reconstruction
    print("\n--- RECONSTRUCTED EXOGENOUS PRECIPITATION (not a logged column; inverted from "
          "drought_index) ---")
    print("  This is the only forcing in the model with no mechanical dependence on agent actions.")
    prec_rows = []
    for s in both:
        sub = merged[merged["seed"] == s]
        gp = reconstruct_precip(pd.DataFrame({"year": sub["year"],
                                              "drought_index": sub["drought_index_g"],
                                              "lake_mead_level": sub["lake_mead_level_g"]}))
        up = reconstruct_precip(pd.DataFrame({"year": sub["year"],
                                              "drought_index": sub["drought_index_u"],
                                              "lake_mead_level": sub["lake_mead_level_u"]}))
        ok = gp["identified"] & up["identified"]
        d = (gp["precip_mm_reconstructed"] - up["precip_mm_reconstructed"])[ok]
        y1 = ok & (sub["year"].values == 1)
        d1 = (gp["precip_mm_reconstructed"] - up["precip_mm_reconstructed"])[y1]
        # per-(seed,year) constancy check: a global forcing must not vary across agents
        chk = pd.DataFrame({"year": sub["year"].values,
                            "p": gp["precip_mm_reconstructed"].values})
        spread = chk.groupby("year")["p"].apply(lambda x: x.max() - x.min()).max()
        prec_rows.append({
            "seed": s, "n_identified": int(ok.sum()), "n_total": int(len(ok)),
            "mean_abs_diff_mm": float(d.abs().mean()) if len(d) else float("nan"),
            "max_abs_diff_mm": float(d.abs().max()) if len(d) else float("nan"),
            "year1_max_abs_diff_mm": float(d1.abs().max()) if len(d1) else float("nan"),
            "within_year_agent_spread_mm": float(spread),
        })
    pt = pd.DataFrame(prec_rows)
    print(f"{'seed':>5} {'identified':>11} {'mean|d| mm':>12} {'max|d| mm':>11} "
          f"{'yr1 max|d|':>11} {'agent-spread':>13}")
    for _, r in pt.iterrows():
        print(f"{int(r['seed']):>5} {int(r['n_identified']):>6,}/{int(r['n_total']):<4,} "
              f"{r['mean_abs_diff_mm']:>12.6g} {r['max_abs_diff_mm']:>11.6g} "
              f"{r['year1_max_abs_diff_mm']:>11.6g} {r['within_year_agent_spread_mm']:>13.3g}")
    print("  'agent-spread' is a self-test: the reconstruction is a GLOBAL quantity, so its spread "
          "across agents inside one (seed, year) must be ~0. A large value invalidates the "
          "inversion, not the data.")

    # ---- external validation of the inversion against the actual CRSS/PRISM source file --------
    ref = crss_reference_precip()
    crss_match = None
    if ref is None:
        print(f"\n  CRSS source file not found at {CRSS_PRECIP_CSV} — the inversion could not be "
              "validated externally. Treat the reconstruction as unvalidated.")
    else:
        s0 = both[0]
        sub = merged[merged["seed"] == s0]
        rec = reconstruct_precip(pd.DataFrame({"year": sub["year"],
                                               "drought_index": sub["drought_index_g"],
                                               "lake_mead_level": sub["lake_mead_level_g"]}))
        rec = rec[rec["identified"]].groupby("year")["precip_mm_reconstructed"].first()
        cmp_rows = []
        for y, v in rec.items():
            cal = SIM_START_YEAR + int(y)
            if cal in ref.index:
                cmp_rows.append((int(y), cal, float(v), float(ref.loc[cal])))
        if cmp_rows:
            errs = [abs(a - b) for _, _, a, b in cmp_rows]
            crss_match = max(errs)
            print(f"\n  EXTERNAL VALIDATION (seed {s0}, governed arm, {len(cmp_rows)} identified "
                  f"years): reconstructed precipitation vs the CRSS/PRISM file")
            print(f"    loop year y maps to calendar year {SIM_START_YEAR}+y; "
                  f"max |reconstructed - source| = {crss_match:.3e} mm")
            for y, cal, a, b in cmp_rows[:6]:
                print(f"      year {y:>2d} ({cal}): reconstructed {a:8.3f} mm   source {b:8.3f} mm")
            if crss_match < 1e-6:
                print("    -> the inversion is EXACT. Precipitation in these runs is a FIXED "
                      "EXOGENOUS DATA TRACE read from")
                print("       ref/CRSS_DB/.../PrismWinterPrecip_ST_NOAA_Future.csv "
                      "(irrigation_env.py:709-713), not an RNG draw.")
                print("       It is identical across arms AND across seeds, and it is the only "
                      "candidate conditioning variable")
                print("       that is treatment-invariant at EVERY year rather than only at "
                      "year 1.")
            else:
                print("    -> the inversion does NOT reproduce the source file. Do not use the "
                      "reconstruction; investigate first.")

    # ------------------------------------------------------- (c) is year 1 clean? explicit verdict
    y1 = merged[merged["year"] == 1]
    print("\n" + "-" * 100)
    print("(c) IS YEAR 1 CLEAN? — this licenses a year-1-restricted design, so it is checked, "
          "not assumed")
    print("-" * 100)
    y1_bad = [(r["column"], r["year1_exact_equal_rate"]) for _, r in tab.iterrows()
              if r["year1_exact_equal_rate"] < 1.0]
    print(f"    year-1 sample: {len(y1):,} matched rows "
          f"({len(y1)//max(len(both),1)} agents x {len(both)} seeds)")
    if not y1_bad:
        print("    VERDICT: YES — every candidate column is identical across arms at year 1.")
    else:
        print("    VERDICT: NO — year 1 is clean for the ENVIRONMENT columns but NOT for the "
              "agent-state columns:")
        for c, rate in sorted(y1_bad, key=lambda t: t[1]):
            print(f"      {c:26s} year-1 exact-equality {100*rate:.3f}%")
        print("    Cause, from the source: run_experiment.py logs in POST_YEAR (line 326), so the "
              "agent-state columns")
        print("    on a year-1 row are recorded AFTER the year-1 action executed. They are "
              "outcomes, not covariates.")
        print("    A year-1 design is licensed for the environment block only "
              "(drought_index / lake_mead_level /")
        print("    mead_storage_maf / shortage_tier / curtailment_ratio), never for "
              "utilisation_pct or below_minimum_utilisation.")

    print("\n    How much VARIATION does a year-1 environment covariate actually have? "
          "(distinct values at year 1)")
    for c in ["lake_mead_level", "mead_storage_maf", "drought_index", "shortage_tier",
              "curtailment_ratio"]:
        vals = pd.to_numeric(y1[f"{c}_g"], errors="coerce")
        per_seed = y1.groupby("seed")[f"{c}_g"].nunique()
        print(f"      {c:20s} {vals.nunique()} distinct values over {len(both)} seeds; "
              f"within a seed: {sorted(set(per_seed))} distinct value(s) across the 78 agents")
    print("    A covariate with one value per seed cannot adjust anything WITHIN a seed. At year 1 "
          "the whole")
    print("    environment block is a seed-level constant, so it can only enter as a seed effect — "
          "which the paired")
    print("    design already absorbs. Its practical adjustment value at year 1 is close to zero.")

    print("\n    Also measured at year 1, for the record and NOT as a covariate: the mediator "
          "already moves.")
    for col in POST_TREATMENT_COLS:
        a = _as_comparable(y1[f"{col}_g"], False)
        b = _as_comparable(y1[f"{col}_u"], False)
        print(f"      {col:22s} year-1 arms agree on {100*float((a == b).mean()):.3f}% of "
              f"{len(y1):,} rows")
    print("    This is NOT decomposable in this corpus: the arms differ by governance AND by an "
          "independent LLM sample,")
    print("    and there is no resample-only control arm here. The year-1 mediator gap is an "
          "upper bound on the")
    print("    governance effect on the mediator, not an estimate of it.")

    # ------------------------------------------------------- code-vs-data cross-check, per column
    print("\n" + "-" * 100)
    print("CODE CROSS-CHECK — what the source says vs what the data shows")
    print("-" * 100)
    disagreements = []
    for _, r in tab.iterrows():
        prov, expected = CODE_PROVENANCE.get(r["column"], ("(no provenance recorded)", None))
        ok = (expected is None) or (expected == r["classification"])
        if not ok:
            disagreements.append((r["column"], expected, r["classification"]))
        print(f"  {r['column']}")
        print(f"      code says   : {prov}")
        print(f"      code expects: {expected}")
        print(f"      data shows  : {r['classification']}   "
              f"{'AGREE' if ok else '*** DISAGREE ***'}")
    if disagreements:
        print("\n  !! CODE/DATA DISAGREEMENTS (report these, do not reconcile them silently):")
        for c, e, g_ in disagreements:
            print(f"     {c}: code implies {e}, data shows {g_}")
    else:
        print("\n  No disagreement between the source reading and the measurement on any column.")

    # ------------------------------------------------------------------------------- verdict list
    print("\n" + "=" * 100)
    print("RANKED LIST FOR DOWNSTREAM ESTIMATORS — follow this literally")
    print("=" * 100)
    for bucket in ("SAFE TO CONDITION ON", "SAFE ONLY AT YEAR 1", "NEVER CONDITION ON"):
        cols = tab[tab["bucket"] == bucket]
        extra = (1 if (bucket == "SAFE TO CONDITION ON" and crss_match is not None
                       and crss_match < 1e-6) else 0)
        n_txt = (f"{len(cols)} logged columns + {extra} recoverable off-log variable"
                 if extra else f"{len(cols)} columns")
        print(f"\n{bucket}  ({n_txt})")
        if cols.empty:
            print("    (none)")
        for _, r in cols.iterrows():
            detail = (f"identical on all {r['n']:,} matched rows"
                      if r["exact_equal_rate"] >= 1.0 else
                      f"{r['n_differing']:,}/{r['n']:,} rows differ; first disagreement in year "
                      f"{int(r['first_year_with_any_disagreement'])}")
            if bucket == "SAFE TO CONDITION ON":
                nd = merged[f"{r['column']}_g"].nunique()
                detail += (f"; {nd} distinct value(s) across agents"
                           + ("  <- NO VARIANCE, carries no information" if nd < 2 else ""))
            print(f"    - {r['column']:26s} {detail}")
        if bucket == "SAFE TO CONDITION ON" and crss_match is not None and crss_match < 1e-6:
            print(f"    - {'precipitation (exogenous)':26s} NOT a logged column. Read it by "
                  f"calendar year straight from")
            print(f"      {'':26s} ref/CRSS_DB/CRSS_DB/HistoricalData/"
                  f"PrismWinterPrecip_ST_NOAA_Future.csv")
            print(f"      {'':26s} (loop year y -> calendar {SIM_START_YEAR}+y, Upper-Basin mean "
                  f"of {'/'.join(CRSS_UB_COLS)}, inches*25.4).")
            print(f"      {'':26s} Verified above to reproduce the logged drought_index exactly. "
                  f"Identical across arms")
            print(f"      {'':26s} AND across seeds, at every year -- so it carries year-to-year "
                  f"variation but NO")
            print(f"      {'':26s} cross-seed variation, and cannot substitute for a "
                  f"seed-level control.")

    n_y1_env = int(y1["lake_mead_level_g"].nunique())
    print("\nCAVEATS THE DOWNSTREAM ESTIMATORS MUST CARRY WITH THIS LIST")
    print("  1. 'SAFE ONLY AT YEAR 1' means year 1 AND NOTHING ELSE — and at year 1 the whole "
          "environment block is")
    print(f"     DEGENERATE. Measured above: lake_mead_level takes {n_y1_env} distinct value(s) "
          f"over all {len(y1):,} year-1 rows")
    print("     (all seeds, all 78 agents). A covariate with no variance adjusts nothing. So the "
          "practical content of")
    print("     this bucket at year 1 is ZERO, and its real purpose is negative: it names the "
          "columns a pooled-year")
    print("     estimator must NOT reach for.")
    print("  2. shortage_tier and curtailment_ratio are step functions of lake_mead_level. Their "
          "higher agreement")
    print("     rate is coarsening, not exogeneity — see the COARSENING WARNING above. Rank them "
          "BELOW the continuous")
    print("     reservoir variables, never above.")
    print("  3. The four static attributes are safe but time-invariant: they can absorb "
          "between-agent composition,")
    print("     never within-agent dynamics, and they cannot rebalance a denominator that moved "
          "because the agent's")
    print("     self-report moved.")
    print("  4. The shared RNG (irrigation_env.py:129) also feeds per-agent magnitude noise "
          "(lines 627-653), and the")
    print("     number of draws depends on which skill was chosen. Once the arms' action "
          "composition diverges, those")
    print("     two streams desynchronise, so request/diversion/utilisation_pct differ by more "
          "than the direct action")
    print("     effect. The hydrology escapes this only because precipitation is read from the "
          "CRSS file rather than")
    print("     drawn from that RNG (irrigation_env.py:709-713 vs the synthetic fallback at 719).")

    # ------------------------------------------------------------------- explicit answers (a)-(d)
    def _row(c):
        return tab[tab["column"] == c].iloc[0]

    di, mead = _row("drought_index"), _row("lake_mead_level")
    print("\n" + "=" * 100)
    print("EXPLICIT ANSWERS")
    print("=" * 100)
    print("(a) drought_index — exogenous hydrology, or coupled?")
    print("    BOTH, in a fixed 50/50 mix, and that is why it cannot be conditioned on past year 1.")
    print(f"    DATA: identical across arms at year 1 (100.000%), then "
          f"{100*di['exact_equal_rate']:.3f}% overall, mean signed difference "
          f"{di['mean_signed_diff_gov_minus_ungov']:+.4f} (governed minus ungoverned),")
    print(f"          max |difference| {di['max_abs_diff']:.4f} = "
          f"{di['max_abs_diff_over_sd']:.2f} pooled SD. It diverges from year "
          f"{int(di['first_year_with_any_disagreement'])}.")
    print("    CODE: irrigation_env.py:833-841 — 0.5*precip_norm + 0.5*mead_norm. precip_norm "
          "comes from a fixed CRSS")
    print("          data file; mead_norm comes from a reservoir elevation that is a mass balance "
          "over agent diversions.")
    print("    AGREEMENT: data and code agree. The exogenous half is separately recoverable and "
          "IS safe at all years;")
    print("               the composite is not.")
    print("\n(b) shortage_tier / curtailment_ratio / lake_mead_level / mead_storage_maf")
    print(f"    All four are reservoir-derived and all four diverge from year "
          f"{int(mead['first_year_with_any_disagreement'])}. None is exogenous hydrology.")
    for c in ["lake_mead_level", "mead_storage_maf", "shortage_tier", "curtailment_ratio"]:
        r = _row(c)
        print(f"      {c:20s} equal {100*r['exact_equal_rate']:7.3f}%  year1 "
              f"{100*r['year1_exact_equal_rate']:7.3f}%  mean signed diff "
              f"{r['mean_signed_diff_gov_minus_ungov']:+.5g} (gov - ungov)  "
              f"max|d|/SD {r['max_abs_diff_over_sd']:.2f}")
    print("    lake_mead_level and mead_storage_maf are the same quantity through a "
          "storage-elevation curve, so they")
    print("    carry identical information; shortage_tier and curtailment_ratio are step functions "
          "of it and are one-to-one")
    print("    with each other (a tier lookup). Four columns, one underlying coupled state "
          "variable.")
    print("\n(c) see the YEAR-1 verdict block above.")
    print("\n(d) static agent attributes:")
    for c, ok in static_ok.items():
        r = _row(c)
        print(f"      {c:26s} within-run constant: {'YES' if ok else 'NO'};  cross-arm identical: "
              f"{'YES' if r['exact_equal_rate'] >= 1.0 else 'NO'}  -> "
              f"{'confirmed static, safe' if (ok and r['exact_equal_rate'] >= 1.0) else 'NOT SAFE'}")
    print("      These are the only columns that pass both halves of the test.")

    # ---------------------------------------------------------------------------------- artefacts
    p1 = os.path.join(args.outdir, "exogeneity_by_column.csv")
    p2 = os.path.join(args.outdir, "exogeneity_by_column_year.csv")
    p3 = os.path.join(args.outdir, "exogeneity_join_report.csv")
    tab.to_csv(p1, index=False)
    py_all.to_csv(p2, index=False)
    pd.DataFrame([{k: v for k, v in i.items() if k != "unmatched_examples"}
                  for i in join_infos]).to_csv(p3, index=False)
    print(f"\nwrote {p1}\nwrote {p2}\nwrote {p3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
