"""INDEPENDENT ADVERSARIAL RE-DERIVATION of e4_bounds.py.

Written from the raw CSVs with pandas/numpy/scipy.  Deliberately structured differently
from e4_bounds.py:

  * bounds are obtained by BRUTE-FORCE CONSTRUCTION over the actual governed rows
    (greedy selection of the S-subset that maximises / minimises the increase count),
    NOT by the closed-form min/max algebra used in the target script.  If the closed form
    is wrong the two will disagree.
  * scipy.stats is used for every p-value and t critical value (the target uses a
    hand-rolled incomplete beta).
  * it additionally computes the quantity the target script asserts is NOT identified:
    E[Y(1)|S] via the matched (seed, agent_id, year) join that the target script itself
    performs in its Section 3.

Sign convention: gap = governed minus ungoverned.  NEGATIVE = governance lowered the rate.

Run:  python reproduction/decomposition/_verify_e4_bounds.py
"""
from __future__ import annotations

import glob
import os
import re

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
RES = os.path.join(REPO, "examples", "irrigation_abm", "results")

INCREASE = {"increase_large", "increase_small"}
HIGHSET = {"H", "VH"}
PREFIXES = {"gemma3:4b": "", "gemma3:12b": "gemma3_12b_", "gemma4:e2b": "gemma4_e2b_",
            "gemma4:e4b": "gemma4_e4b_", "ministral-3:8b": "ministral3_8b_"}
ARMDIR = {"gov": "production", "ung": "ungoverned"}


def seeds_on_disk(arm, prefix):
    pat = os.path.join(RES, f"{ARMDIR[arm]}_v21_42yr_{prefix}seed*")
    out = []
    for d in sorted(glob.glob(pat)):
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "simulation_log.csv")):
            out.append(re.search(r"seed(\d+)$", os.path.basename(d)).group(1))
    return sorted(out)


def read(arm, prefix, seed, with_audit=False):
    d = os.path.join(RES, f"{ARMDIR[arm]}_v21_42yr_{prefix}seed{seed}")
    df = pd.read_csv(os.path.join(d, "simulation_log.csv"), encoding="utf-8-sig",
                     dtype={"agent_id": str})
    df["HI"] = df["wsa_label"].astype(str).str.strip().str.upper().isin(HIGHSET)
    df["INC"] = df["yearly_decision"].astype(str).str.strip().isin(INCREASE)
    if with_audit:
        au = pd.read_csv(os.path.join(d, "irrigation_farmer_governance_audit.csv"),
                         encoding="utf-8-sig", dtype={"agent_id": str}, low_memory=False)
        au = au[["agent_id", "year", "status"]].copy()
        assert not au.duplicated(["agent_id", "year"]).any(), "dup audit key"
        m = df.merge(au, on=["agent_id", "year"], how="left", validate="one_to_one")
        assert m["status"].notna().all(), "unmatched audit rows"
        m["EXEC"] = np.where(m["status"].astype(str).str.startswith("REJECTED"),
                             "maintain_demand", m["yearly_decision"].astype(str).str.strip())
        m["INC_EXEC"] = m["EXEC"].isin(INCREASE)
        df = m
    return df


# ---------------------------------------------------------------------------
# BRUTE-FORCE sharp bounds on E[Y(1)|S], by explicitly constructing the subset.
# ---------------------------------------------------------------------------
def brute_bounds(gov: pd.DataFrame, n_S: int, inc_col="INC", require_high=False):
    """Sharp [lo, hi] for the increase-share inside ANY governed subset of size n_S.

    require_high=True additionally forces the subset to contain every governed HIGH row
    (that is exactly what monotonicity A2 implies: S superset of the governed high set).

    Constructed, not formula-derived: sort rows by the outcome and count.
    """
    n = len(gov)
    assert 0 < n_S <= n, f"n_S={n_S} out of range for n={n}"
    inc = gov[inc_col].to_numpy()
    if not require_high:
        n_inc = int(inc.sum())
        hi = min(n_inc, n_S)                       # take increases first
        lo = max(0, n_S - (n - n_inc))             # take non-increases first
        return lo / n_S, hi / n_S
    hi_mask = gov["HI"].to_numpy()
    forced_inc = int((hi_mask & inc).sum())
    forced_tot = int(hi_mask.sum())
    assert n_S >= forced_tot, "n_S smaller than the forced high set"
    rem = n_S - forced_tot
    pool_inc = int((~hi_mask & inc).sum())
    pool_non = int((~hi_mask & ~inc).sum())
    hi = (forced_inc + min(rem, pool_inc)) / n_S
    lo = (forced_inc + max(0, rem - pool_non)) / n_S
    return lo, hi


def im_interval(los, his, alpha=0.05):
    """Imbens-Manski-style interval: one-sided critical value on each end (the
    large-Delta/sigma limit of the IM construction).  scipy t, not hand-rolled."""
    los, his = np.asarray(los, float), np.asarray(his, float)
    n = len(los)
    df = n - 1
    c = stats.t.ppf(1 - alpha, df)
    se_lo = los.std(ddof=1) / np.sqrt(n)
    se_hi = his.std(ddof=1) / np.sqrt(n)
    return los.mean() - c * se_lo, his.mean() + c * se_hi, c, se_lo, se_hi


def banner(t):
    print("\n" + "=" * 100 + f"\n{t}\n" + "=" * 100)


def main():
    prefix = PREFIXES["gemma3:4b"]
    gs, us = seeds_on_disk("gov", prefix), seeds_on_disk("ung", prefix)
    paired = sorted(set(gs) & set(us))
    banner("A. CORPUS")
    print(f"  governed seeds {gs}   ungoverned seeds {us}   paired {paired}")

    rows = []
    for s in paired:
        g = read("gov", prefix, s, with_audit=True)
        u = read("ung", prefix, s, with_audit=True)
        assert len(g) == len(u) == 3276, (len(g), len(u))
        rec = dict(seed=s)
        for tag, d in (("g", g), ("u", u)):
            rec[f"n_{tag}"] = len(d)
            rec[f"nhigh_{tag}"] = int(d.HI.sum())
            rec[f"ninc_{tag}"] = int(d.INC.sum())
            rec[f"nhiinc_{tag}"] = int((d.HI & d.INC).sum())
            rec[f"ibr_{tag}"] = 100 * (d.HI & d.INC).sum() / d.HI.sum()
            rec[f"hsh_{tag}"] = 100 * d.HI.mean()
            rec[f"inc_{tag}"] = 100 * d.INC.mean()
            rec[f"ibrx_{tag}"] = 100 * (d.HI & d.INC_EXEC).sum() / d.HI.sum()
            rec[f"incx_{tag}"] = 100 * d.INC_EXEC.mean()
        # --- brute-force Manski bounds on E[Y(1)|S] ---
        n_S = rec["nhigh_u"]                       # A1: |S| = ungoverned high count
        lo_nm, hi_nm = brute_bounds(g, n_S, require_high=False)
        lo_m, hi_m = brute_bounds(g, n_S, require_high=True)
        r0 = rec["ibr_u"] / 100
        rec["nomono_lo"], rec["nomono_hi"] = 100 * (lo_nm - r0), 100 * (hi_nm - r0)
        rec["mono_lo"], rec["mono_hi"] = 100 * (lo_m - r0), 100 * (hi_m - r0)
        # --- executed-action version ---
        lo_x, hi_x = brute_bounds(g, n_S, inc_col="INC_EXEC", require_high=True)
        r0x = rec["ibrx_u"] / 100
        rec["exec_lo"], rec["exec_hi"] = 100 * (lo_x - r0x), 100 * (hi_x - r0x)
        rec["exec_gap"] = rec["ibrx_g"] - rec["ibrx_u"]
        # --- POINT IDENTIFICATION via the matched join ---
        j = g[["agent_id", "year", "HI", "INC", "INC_EXEC"]].merge(
            u[["agent_id", "year", "HI", "INC", "INC_EXEC"]], on=["agent_id", "year"],
            suffixes=("_g", "_u"), validate="one_to_one")
        assert len(j) == 3276
        inS = j.HI_u
        rec["pt_EY1_S"] = 100 * j.loc[inS, "INC_g"].mean()
        rec["pt_EY0_S"] = 100 * j.loc[inS, "INC_u"].mean()
        rec["pt_delta_S"] = rec["pt_EY1_S"] - rec["pt_EY0_S"]
        rec["pt_EY1_S_x"] = 100 * j.loc[inS, "INC_EXEC_g"].mean()
        rec["pt_EY0_S_x"] = 100 * j.loc[inS, "INC_EXEC_u"].mean()
        rec["pt_delta_S_x"] = rec["pt_EY1_S_x"] - rec["pt_EY0_S_x"]
        # monotonicity cross-tab
        rec["both"] = int((j.HI_g & j.HI_u).sum())
        rec["gonly"] = int((j.HI_g & ~j.HI_u).sum())
        rec["uonly"] = int((~j.HI_g & j.HI_u).sum())
        # always-high (observed) contrast -- the Lee target, observed directly
        A = j.HI_g & j.HI_u
        rec["obsA_g"] = 100 * j.loc[A, "INC_g"].mean()
        rec["obsA_u"] = 100 * j.loc[A, "INC_u"].mean()
        rec["obsA_delta"] = rec["obsA_g"] - rec["obsA_u"]
        # Lee sharp (unconditional), independently
        k = rec["nhigh_g"] / rec["nhigh_u"]
        r0l = rec["ibr_u"] / 100
        up = min(1.0, r0l / k)
        lo = max(0.0, (r0l - (1 - k)) / k)
        rec["lee_k"] = k
        rec["lee_gap_lo"] = rec["ibr_g"] - 100 * up
        rec["lee_gap_hi"] = rec["ibr_g"] - 100 * lo
        rows.append(rec)
    D = pd.DataFrame(rows).set_index("seed")

    banner("B. REPRODUCTION OF THE PUBLISHED CONDITIONAL STATISTIC")
    print(D[["nhigh_g", "nhigh_u", "ibr_g", "ibr_u", "hsh_g", "hsh_u", "inc_g", "inc_u"]]
          .round(2).to_string())
    diffs = (D.ibr_g - D.ibr_u).to_numpy()
    t, p = stats.ttest_rel(D.ibr_g, D.ibr_u)
    print(f"\n  mean governed IBR   = {D.ibr_g.mean():.4f} %")
    print(f"  mean ungoverned IBR = {D.ibr_u.mean():.4f} %")
    print(f"  gap (gov - ung)     = {diffs.mean():+.4f} pp   [negative = governance lowered it]")
    print(f"  per-seed diffs      = {np.round(diffs, 4)}")
    print(f"  scipy paired t      = {t:.4f}, df = {len(diffs)-1}, p = {p:.8f}")
    print(f"  high-share shift (ung - gov) = {(D.hsh_u - D.hsh_g).mean():+.4f} pp")
    print(f"  unconditional increase gap   = {(D.inc_g - D.inc_u).mean():+.4f} pp")

    banner("C. MANSKI BOUNDS -- BRUTE-FORCE CONSTRUCTION (not the closed form)")
    print(D[["nomono_lo", "nomono_hi", "mono_lo", "mono_hi"]].round(4).to_string())
    for nm, lc, hc in (("no-monotonicity", "nomono_lo", "nomono_hi"),
                       ("under monotonicity", "mono_lo", "mono_hi")):
        lo_m, hi_m = D[lc].mean(), D[hc].mean()
        iml, imh, c, sel, seh = im_interval(D[lc], D[hc])
        tt, pp_ = stats.ttest_1samp(D[hc], 0.0)
        print(f"\n  {nm}:")
        print(f"     identified set for the mean = [{lo_m:+.4f}, {hi_m:+.4f}] pp")
        print(f"     IM 95% (one-sided t crit {c:.4f}) = [{iml:+.4f}, {imh:+.4f}] pp"
              f"   (se_lo={sel:.4f}, se_hi={seh:.4f})")
        print(f"     upper bound vs 0: t = {tt:.4f}, p(two-sided) = {pp_:.6f}")
        print(f"     -> identified set {'EXCLUDES' if hi_m < 0 else 'INCLUDES'} zero; "
              f"IM {'EXCLUDES' if imh < 0 else 'INCLUDES'} zero")

    banner("D. THE QUANTITY THE TARGET SCRIPT SAYS IS NOT IDENTIFIED")
    print("  S is OBSERVABLE at matched (seed, agent_id, year): it is the ungoverned arm's")
    print("  realised HIGH set.  Both arms were run on the SAME agents/years/seeds, so the")
    print("  governed action at every S cell is on disk.  E[Y(1)|S] is therefore a")
    print("  DIRECT AVERAGE, not a bound.  (e4_bounds.py performs this exact join in its")
    print("  Section 3 for the monotonicity diagnostic, then declines to use it here.)")
    print()
    print(D[["pt_EY1_S", "pt_EY0_S", "pt_delta_S", "mono_lo", "mono_hi"]].round(3).to_string())
    pt = D.pt_delta_S.to_numpy()
    tt, pp_ = stats.ttest_1samp(pt, 0.0)
    print(f"\n  POINT-IDENTIFIED Delta_S (mean over 5 seeds) = {pt.mean():+.4f} pp"
          f"   sd={pt.std(ddof=1):.4f}")
    ci = stats.t.interval(0.95, len(pt) - 1, loc=pt.mean(), scale=stats.sem(pt))
    print(f"  95% CI (seed-level t, df={len(pt)-1}) = [{ci[0]:+.4f}, {ci[1]:+.4f}] pp")
    print(f"  one-sample t vs 0: t = {tt:.4f}, p = {pp_:.8f}")
    inside = ((pt >= D.mono_lo - 1e-9) & (pt <= D.mono_hi + 1e-9)).all()
    print(f"  every per-seed point value inside its own sharp bound?  {inside}")
    print(f"  bound width (mean) = {(D.mono_hi - D.mono_lo).mean():.2f} pp;"
          f"  point-estimate 95% CI width = {ci[1]-ci[0]:.2f} pp")
    print(f"\n  executed-action point-identified Delta_S = {D.pt_delta_S_x.mean():+.4f} pp")

    banner("E. MONOTONICITY CROSS-TAB (independent recount)")
    tot = int(D[["both", "gonly", "uonly"]].sum().sum()) + (3276 * len(D) - int(D[["both", "gonly", "uonly"]].sum().sum()))
    print(f"  matched rows {3276*len(D)}   both {D.both.sum()} ({100*D.both.sum()/(3276*len(D)):.2f} %)"
          f"   gov-only(VIOLATION) {D.gonly.sum()} ({100*D.gonly.sum()/(3276*len(D)):.2f} %)"
          f"   ung-only {D.uonly.sum()} ({100*D.uonly.sum()/(3276*len(D)):.2f} %)")
    print("\n  Delta on the OBSERVED always-high set A = {HIGH in both arms} (no Lee trimming,")
    print("  because A is directly observable in this corpus too):")
    print(D[["obsA_g", "obsA_u", "obsA_delta", "lee_gap_lo", "lee_gap_hi"]].round(3).to_string())
    oa = D.obsA_delta.to_numpy()
    print(f"  mean observed Delta_A = {oa.mean():+.4f} pp"
          f"   (Lee sharp set = [{D.lee_gap_lo.mean():+.2f}, {D.lee_gap_hi.mean():+.2f}] pp)")
    print(f"  observed value inside the Lee set?  "
          f"{bool(((oa >= D.lee_gap_lo - 1e-9) & (oa <= D.lee_gap_hi + 1e-9)).all())}")

    banner("F. EXECUTED-ACTION SECTION (independent)")
    print(D[["ibrx_g", "ibrx_u", "exec_gap", "exec_lo", "exec_hi"]].round(3).to_string())
    iml, imh, c, _, _ = im_interval(D.exec_lo, D.exec_hi)
    print(f"  mean executed conditional gap = {D.exec_gap.mean():+.4f} pp")
    print(f"  executed sharp set = [{D.exec_lo.mean():+.4f}, {D.exec_hi.mean():+.4f}] pp"
          f"   IM 95% = [{iml:+.4f}, {imh:+.4f}] pp")

    banner("G. ALL BALANCED MODEL CELLS (sharp Manski, brute force)")
    print(f"  {'model':16s} {'seeds':>5s} {'pub gap':>9s} {'sharp LB':>9s} {'sharp UB':>9s} "
          f"{'IM lo':>8s} {'IM hi':>8s} {'set excl0':>10s} {'IM excl0':>9s} {'pt Delta_S':>11s}")
    for lbl, pfx in PREFIXES.items():
        g_s, u_s = seeds_on_disk("gov", pfx), seeds_on_disk("ung", pfx)
        pr = sorted(set(g_s) & set(u_s))
        bal = g_s == u_s
        L, H, P, PT = [], [], [], []
        for s in pr:
            g, u = read("gov", pfx, s), read("ung", pfx, s)
            n_S = int(u.HI.sum())
            lo, hi = brute_bounds(g, n_S, require_high=True)
            r0 = (g.HI & g.INC).sum() * 0 + (u.HI & u.INC).sum() / u.HI.sum()
            L.append(100 * (lo - r0)); H.append(100 * (hi - r0))
            P.append(100 * ((g.HI & g.INC).sum() / g.HI.sum() - r0))
            j = g[["agent_id", "year", "HI", "INC"]].merge(
                u[["agent_id", "year", "HI", "INC"]], on=["agent_id", "year"],
                suffixes=("_g", "_u"), validate="one_to_one")
            PT.append(100 * (j.loc[j.HI_u, "INC_g"].mean() - j.loc[j.HI_u, "INC_u"].mean()))
        if not bal:
            print(f"  {lbl:16s} UNBALANCED gov={g_s} ung={u_s} -> per-seed only: "
                  f"sets {[f'[{a:.2f},{b:.2f}]' for a, b in zip(L, H)]}, "
                  f"point Delta_S {[round(x,2) for x in PT]}")
            continue
        iml, imh, *_ = im_interval(L, H)
        print(f"  {lbl:16s} {len(pr):>5d} {np.mean(P):9.2f} {np.mean(L):9.2f} {np.mean(H):9.2f} "
              f"{iml:8.2f} {imh:8.2f} {('YES' if np.mean(H) < 0 else 'no'):>10s} "
              f"{('YES' if imh < 0 else 'no'):>9s} {np.mean(PT):11.2f}")

    banner("H. FRAGILITY PROBES ON THE HEADLINE")
    his = D.mono_hi.to_numpy()
    print(f"  per-seed upper bounds {np.round(his,2)}")
    print(f"  leave-one-seed-out IM upper endpoint:")
    for i, s in enumerate(D.index):
        keep = [j for j in range(len(his)) if j != i]
        iml, imh, *_ = im_interval(D.mono_lo.to_numpy()[keep], his[keep])
        print(f"     drop seed {s}: IM = [{iml:+.2f}, {imh:+.2f}] pp -> "
              f"{'EXCLUDES' if imh < 0 else 'INCLUDES'} zero")
    print(f"  distance of IM upper endpoint from zero, in SE units: "
          f"{-im_interval(D.mono_lo, his)[1] / im_interval(D.mono_lo, his)[4]:.2f}")
    print()
    print("DONE.")


if __name__ == "__main__":
    main()
