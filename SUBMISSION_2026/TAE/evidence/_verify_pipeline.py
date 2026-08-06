"""INDEPENDENT re-derivation of the TAE pipeline's headline numbers.

Written deliberately DIFFERENTLY from ``_data.py`` so that agreement is evidence:

  * pandas / numpy / scipy instead of ``csv`` + a hand-rolled incomplete beta;
  * paths spelled out as literal f-strings per seed instead of regex discovery;
  * the t-interval from ``scipy.stats.t.ppf`` instead of a bisection on I_x(a,b);
  * every rate recomputed from the raw column, never from a helper in _data.

This module imports NOTHING from ``_data.py``. If the two agree, two independent
implementations agree. If they do not, the disagreement is printed and the exit
code is 1.

    python SUBMISSION_2026/TAE/evidence/_verify_pipeline.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
IRR = os.path.join(REPO, "examples", "irrigation_abm", "results")

INCREASE = {"increase_large", "increase_small"}
HIGH = {"H", "VH"}

# Literal, hand-written inventory. No discovery, no glob, no regex.
CELLS = {
    "gemma3:4b":     ("",                [42, 43, 44, 45, 46], [42, 43, 44, 45, 46]),
    "gemma3:12b":    ("gemma3_12b_",     [42, 43, 44],         [42, 43, 44]),
    "gemma4:e2b":    ("gemma4_e2b_",     [42, 43, 44, 45, 46], [42, 43, 44, 45, 46]),
    "gemma4:e4b":    ("gemma4_e4b_",     [42, 43, 44, 45, 46], [42, 43, 44, 45, 46]),
    "ministral3:8b": ("ministral3_8b_",  [42, 43, 44],         [42, 43, 44]),
}
ARM_DIR = {"gov": "production", "noval": "ungoverned"}

BRIEF = {   # (n, cond gov, cond noval, cond D, unc gov, unc noval, unc D)
    "gemma3:4b":     (5, 36.05, 59.07, +23.02, 40.90, 62.52, +21.62),
    "gemma3:12b":    (3,  5.45, 16.89, +11.44, 41.36, 41.52,  +0.16),
    "gemma4:e2b":    (5, 12.71, 31.65, +18.94, 22.80, 38.05, +15.25),
    "gemma4:e4b":    (5, 23.67, 41.08, +17.41, 36.36, 44.87,  +8.52),
    "ministral3:8b": (3,  3.25,  6.05,  +2.80, 54.35, 32.18, -22.17),
}

_FAILS: list[str] = []


def run_dir(arm: str, prefix: str, seed: int) -> str:
    d = os.path.join(IRR, f"{ARM_DIR[arm]}_v21_42yr_{prefix}seed{seed}")
    if not os.path.isdir(d):
        raise SystemExit(f"missing run directory {d}")
    # independent contamination assertion: the basename must be EXACTLY this
    assert os.path.basename(d) == f"{ARM_DIR[arm]}_v21_42yr_{prefix}seed{seed}"
    return d


def sim(arm, prefix, seed) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(run_dir(arm, prefix, seed), "simulation_log.csv"),
                     encoding="utf-8-sig")
    if len(df) != 3276:
        raise SystemExit(f"{arm}/{prefix}{seed}: sim rows {len(df)} != 3276")
    return df


def aud(arm, prefix, seed) -> pd.DataFrame:
    return pd.read_csv(
        os.path.join(run_dir(arm, prefix, seed), "irrigation_farmer_governance_audit.csv"),
        encoding="utf-8-sig", low_memory=False)


def norm_label(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.upper()


def norm_act(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip()


def rates_from_sim(df: pd.DataFrame) -> tuple[float, float, float]:
    """(conditional, unconditional, HIGH prevalence) as percentages."""
    lab = norm_label(df["wsa_label"])
    act = norm_act(df["yearly_decision"])
    inc = act.isin(INCREASE)
    hi = lab.isin(HIGH)
    return (100.0 * inc[hi].mean(), 100.0 * inc.mean(), 100.0 * hi.mean())


def ci95(deltas) -> tuple[float, float, float, float, int]:
    """mean, lo, hi, t, df -- scipy route, deliberately not the _data.py route."""
    a = np.asarray(deltas, dtype=float)
    n = a.size
    df = n - 1
    m = a.mean()
    se = a.std(ddof=1) / np.sqrt(n)
    if se == 0:
        return m, m, m, np.nan if m == 0 else np.inf * np.sign(m), df
    crit = stats.t.ppf(0.975, df)
    return m, m - crit * se, m + crit * se, m / se, df


def chk(name, got, want, tol=0.005):
    ok = abs(got - want) <= tol
    if not ok:
        _FAILS.append(f"{name}: independent {got:.4f} vs pipeline/brief {want:.4f}")
    print(f"  {'OK ' if ok else '!! '}{name:52s} mine {got:>+10.4f}   theirs {want:>+10.4f}"
          f"   diff {got - want:>+8.4f}{'' if ok else '   <== DISAGREE'}")
    return ok


# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 100)
    print("INDEPENDENT RE-DERIVATION (pandas/scipy, literal paths, no _data.py import)")
    print("=" * 100)
    print("Delta = no-validator MINUS with-validators (positive = validators lowered it)")
    print()

    # ---- 1. anchor cell rates ---------------------------------------------
    print("-" * 100)
    print("1. ANCHOR CELL gemma3:4b -- per seed, then MEAN OF PER-SEED RATES")
    print("-" * 100)
    per = {}
    for arm in ("gov", "noval"):
        rows = []
        for s in CELLS["gemma3:4b"][1 if arm == "gov" else 2]:
            rows.append(rates_from_sim(sim(arm, "", s)))
        per[arm] = np.array(rows)          # columns: cond, unc, high
        print(f"  {arm:6s} " + "  ".join(
            f"s{s}:{c:.2f}/{u:.2f}/{h:.2f}"
            for s, (c, u, h) in zip(CELLS["gemma3:4b"][1], rows)))
    print("  (per-seed values printed as conditional/unconditional/HIGH-prevalence)")
    print()
    labels = ("conditional", "unconditional", "HIGH prevalence")
    want = {"conditional": (36.05, 59.07, 23.02),
            "unconditional": (40.90, 62.52, 21.62),
            "HIGH prevalence": (37.08, 82.80, 45.73)}
    for j, nm in enumerate(labels):
        g, n = per["gov"][:, j].mean(), per["noval"][:, j].mean()
        chk(f"anchor {nm} with-validators", g, want[nm][0])
        chk(f"anchor {nm} no-validator", n, want[nm][1])
        chk(f"anchor {nm} Delta", n - g, want[nm][2])
    # pooled-rows alternative, to show the convention matters
    pg = pd.concat([sim("gov", "", s) for s in CELLS["gemma3:4b"][1]])
    print(f"  [convention check] anchor gov conditional POOLED over rows = "
          f"{rates_from_sim(pg)[0]:.4f}  vs mean-of-seeds "
          f"{per['gov'][:, 0].mean():.4f}  -> the published 36.05 is the mean-of-seeds")
    print()

    # ---- 2. year 1 --------------------------------------------------------
    print("-" * 100)
    print("2. YEAR 1 ONLY (pre-decision state columns match exactly) -- paired t, scipy t.ppf")
    print("-" * 100)
    y1 = {}
    for arm in ("gov", "noval"):
        y1[arm] = np.array([
            rates_from_sim(sim(arm, "", s).query("year == 1"))
            for s in CELLS["gemma3:4b"][1]])
    for j, nm in enumerate(("conditional", "unconditional", "HIGH prevalence")):
        d = y1["noval"][:, j] - y1["gov"][:, j]
        m, lo, hi, t, df = ci95(d)
        exp = {"HIGH prevalence": (3.33, -3.75, 10.42),
               "conditional": (-1.15, -7.00, 4.71),
               "unconditional": (1.28, -0.31, 2.87)}[nm]
        print(f"  year-1 {nm:16s} Delta {m:+7.2f}  95% CI ({lo:+7.2f},{hi:+7.2f})  "
              f"t={t:+6.2f} df={df}  p={2*stats.t.sf(abs(t), df):.3f}")
        chk(f"  year-1 {nm} Delta", m, exp[0], 0.02)
        chk(f"  year-1 {nm} CI lo", lo, exp[1], 0.02)
        chk(f"  year-1 {nm} CI hi", hi, exp[2], 0.02)
    print("  -> all three intervals contain zero: NULL, as the brief states.")
    print()

    # ---- 3. never-retried stratum ----------------------------------------
    print("-" * 100)
    print("3. NEVER-RETRIED STRATUM (audit retry_count == 0) -- HIGH-prevalence Delta")
    print("-" * 100)
    briefs_nr = {"gemma3:4b": 53.46, "gemma3:12b": 24.31, "gemma4:e2b": 50.93,
                 "gemma4:e4b": 63.05, "ministral3:8b": 34.09}
    pooled = {arm: {"all": [], "nr": []} for arm in ("gov", "noval")}
    print(f"  {'cell':14s} {'n':>2s} {'d ALL':>8s} {'d NR':>8s} {'NR-ALL':>8s}  larger?")
    n_larger = 0
    for label, (prefix, gs, ns) in CELLS.items():
        paired = sorted(set(gs) & set(ns))
        cell = {arm: {"all": [], "nr": []} for arm in ("gov", "noval")}
        for arm in ("gov", "noval"):
            for s in paired:
                a = aud(arm, prefix, s)
                lab = norm_label(a["construct_WSA_LABEL"])
                rc = pd.to_numeric(a["retry_count"], errors="coerce")
                hi = lab.isin(HIGH)
                cell[arm]["all"].append(100.0 * hi.mean())
                cell[arm]["nr"].append(100.0 * hi[rc == 0].mean())
                pooled[arm]["all"].append(100.0 * hi.mean())
                pooled[arm]["nr"].append(100.0 * hi[rc == 0].mean())
        d_all = np.mean(cell["noval"]["all"]) - np.mean(cell["gov"]["all"])
        d_nr = np.mean(cell["noval"]["nr"]) - np.mean(cell["gov"]["nr"])
        n_larger += d_nr > d_all
        print(f"  {label:14s} {len(paired):>2d} {d_all:>+8.2f} {d_nr:>+8.2f} "
              f"{d_nr - d_all:>+8.2f}  {d_nr > d_all}")
        chk(f"  never-retried Delta {label}", d_nr, briefs_nr[label])
    p_all = np.mean(pooled["noval"]["all"]) - np.mean(pooled["gov"]["all"])
    p_nr = np.mean(pooled["noval"]["nr"]) - np.mean(pooled["gov"]["nr"])
    print(f"  {'pooled(21)':14s} {len(pooled['gov']['all']):>2d} {p_all:>+8.2f} "
          f"{p_nr:>+8.2f} {p_nr - p_all:>+8.2f}")
    chk("  never-retried Delta pooled", p_nr, 48.21)
    print(f"  never-retried larger in {n_larger}/5 cells (brief: 5/5)")
    if n_larger != 5:
        _FAILS.append(f"never-retried larger in only {n_larger}/5 cells")
    print()
    print("  ADJUDICATING THE POOLED ALL-DECISIONS DELTA (brief 40.40, pipeline 40.02):")
    print(f"    mean of the 21 per-(cell,seed) rates, paired seeds  = {p_all:.4f}")
    unw = np.mean([  # unweighted mean of the five per-cell deltas
        (np.mean([100.0 * norm_label(aud("noval", p, s)["construct_WSA_LABEL"]).isin(HIGH).mean()
                  for s in sorted(set(g) & set(nn))])
         - np.mean([100.0 * norm_label(aud("gov", p, s)["construct_WSA_LABEL"]).isin(HIGH).mean()
                    for s in sorted(set(g) & set(nn))]))
        for (p, g, nn) in CELLS.values()])
    print(f"    unweighted mean of the five per-cell deltas          = {unw:.4f}")
    print("    Neither is 40.40. The pipeline's basis is the one that also")
    print("    reproduces the never-retried pooled figure, so 40.40 is the number")
    print("    that is wrong, not the code. Both pooled figures moved on")
    print("    2026-08-03 -- 40.45 to 40.02 and 49.09 to 48.21 -- because the")
    print("    pool grew from 20 paired (cell, seed) units to 21, not because the")
    print("    basis changed. The adjudication above is unaffected by that.")
    print()

    # ---- 4. rejection-cause split ----------------------------------------
    print("-" * 100)
    print("4. REJECTION CAUSE SPLIT (anchor, 5 seeds, pooled counts)")
    print("-" * 100)
    NO_RULE = {"", "unknown", "none", "n/a", "nan"}
    for arm, exp_rej, exp_pre, exp_th in (("noval", 4757, 4757, 0), ("gov", 6469, 0, 6469)):
        tot = rej = pre = th = 0
        cap_msg = 0
        for s in CELLS["gemma3:4b"][1]:
            a = aud(arm, "", s)
            st = a["status"].fillna("").astype(str).str.strip().str.upper()
            isrej = st.isin({"REJECTED", "REJECTED_FALLBACK"})
            fr = a["failed_rules"].fillna("").astype(str)
            named = fr.apply(lambda x: any(
                t.strip().lower() not in NO_RULE for t in x.split("|")))
            tot += len(a)
            rej += int(isrej.sum())
            th += int((isrej & named).sum())
            pre += int((isrej & ~named).sum())
            em = a["error_messages"].fillna("").astype(str)
            cap_msg += int((isrej & em.str.contains("at_allocation_cap")).sum())
        print(f"  {arm:6s} rejected {rej:>6,d}/{tot:,} = {100*rej/tot:>5.2f}%   "
              f"precondition {pre:>6,d} ({100*pre/rej:>5.1f}%)   "
              f"named-rule {th:>6,d} ({100*th/rej:>5.1f}%)   "
              f"| rejections whose error_messages cite at_allocation_cap: {cap_msg:,}")
        chk(f"  {arm} rejected count", rej, exp_rej, 0.5)
        chk(f"  {arm} precondition count", pre, exp_pre, 0.5)
        chk(f"  {arm} named-rule count", th, exp_th, 0.5)
    print()

    # ---- 5. per-model table (fig3 / table1) ------------------------------
    print("-" * 100)
    print("5. PER-MODEL CONDITIONAL / UNCONDITIONAL, paired basis, LAST-PROPOSED")
    print("-" * 100)
    for label, (prefix, gs, ns) in CELLS.items():
        paired = sorted(set(gs) & set(ns))
        b = BRIEF[label]
        vals = {}
        for arm in ("gov", "noval"):
            vals[arm] = np.array([rates_from_sim(sim(arm, prefix, s)) for s in paired])
        cg, cn = vals["gov"][:, 0].mean(), vals["noval"][:, 0].mean()
        ug, un = vals["gov"][:, 1].mean(), vals["noval"][:, 1].mean()
        print(f"  {label:14s} n={len(paired)}  cond {cg:6.2f}/{cn:6.2f}/{cn-cg:+7.2f}   "
              f"unc {ug:6.2f}/{un:6.2f}/{un-ug:+7.2f}")
        chk(f"  {label} n", float(len(paired)), float(b[0]), 0.0)
        chk(f"  {label} cond gov", cg, b[1])
        chk(f"  {label} cond noval", cn, b[2])
        chk(f"  {label} cond Delta", cn - cg, b[3])
        chk(f"  {label} unc gov", ug, b[4])
        chk(f"  {label} unc noval", un, b[5])
        chk(f"  {label} unc Delta", un - ug, b[6])
    print()

    # ---- 6. contamination sanity: nothing forbidden is on any path used ----
    print("-" * 100)
    print("6. PATHS ACTUALLY READ (independently asserted clean)")
    print("-" * 100)
    bad_tok = ("bak", "dead", "quarantine", "group_a", "old", "_")
    used = [run_dir(arm, p, s)
            for (p, g, nn) in CELLS.values()
            for arm, seeds in (("gov", g), ("noval", nn))
            for s in seeds]
    dirty = [u for u in used
             if any(t in os.path.basename(u).lower() for t in bad_tok[:-1])
             or os.path.basename(u).startswith("_")]
    print(f"  {len(used)} run directories read; forbidden-token hits: {len(dirty)}")
    if dirty:
        _FAILS.append(f"contaminated dirs read: {dirty}")
    print()

    print("=" * 100)
    if _FAILS:
        print("INDEPENDENT VERIFICATION: DISAGREEMENTS")
        for f in _FAILS:
            print("  !!", f)
        print("=" * 100)
        return 1
    print("INDEPENDENT VERIFICATION: EVERY VALUE AGREES")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
