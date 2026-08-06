"""INDEPENDENT re-derivation of e5_year1's headline. Deliberately structured
differently from e5_year1.py: pandas groupby instead of dict-of-dicts, scipy
instead of the hand-rolled betainc, and it re-reads the CSVs from scratch with
its OWN definitions (no import of _loader).

Sign convention: gap = governed MINUS ungoverned. Negative = governance lowered it.
"""
import glob
import os
import re

import numpy as np
import pandas as pd
from scipy import stats

REPO = r"C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
RES = os.path.join(REPO, "examples/irrigation_abm/results")

INCREASE = {"increase_large", "increase_small"}
HIGH = {"H", "VH"}
PREFIX = {"gemma3:4b": "", "gemma3:12b": "gemma3_12b_", "gemma4:e2b": "gemma4_e2b_",
          "gemma4:e4b": "gemma4_e4b_", "ministral-3:8b": "ministral3_8b_"}


def load(model, arm):
    """Long frame of every run for (model, arm), with a seed column."""
    armdir = {"governed": "production", "ungoverned": "ungoverned"}[arm]
    pat = os.path.join(RES, f"{armdir}_v21_42yr_{PREFIX[model]}seed*")
    frames = []
    for d in sorted(glob.glob(pat)):
        if not os.path.isdir(d):
            continue
        seed = re.search(r"seed(\d+)$", os.path.basename(d)).group(1)
        df = pd.read_csv(os.path.join(d, "simulation_log.csv"), encoding="utf-8-sig",
                         dtype=str, keep_default_na=False)
        df["seed"] = seed
        df["arm"] = arm
        frames.append(df)
    if not frames:
        raise RuntimeError(f"nothing matched {pat}")
    out = pd.concat(frames, ignore_index=True)
    out["year"] = out["year"].astype(int)
    out["inc"] = out["yearly_decision"].str.strip().isin(INCREASE)
    out["hi"] = out["wsa_label"].str.strip().str.upper().isin(HIGH)
    return out


def per_seed(df):
    """seed -> (uncond incr %, high share %, conditional IBR %). NaN IBR if no HIGH."""
    g = df.groupby("seed")
    res = pd.DataFrame({
        "n": g.size(),
        "inc_rate": 100 * g["inc"].mean(),
        "high_share": 100 * g["hi"].mean(),
    })
    ibr = df[df["hi"]].groupby("seed")["inc"].agg(["size", "mean"])
    res["n_high"] = ibr["size"].reindex(res.index)
    res["ibr"] = (100 * ibr["mean"]).reindex(res.index)
    return res


def paired(gov, ung, seeds):
    d = np.array([gov.loc[s] - ung.loc[s] for s in seeds], dtype=float)
    if np.isnan(d).any():
        return dict(mean=np.nan, ci=(np.nan, np.nan), t=np.nan, df=len(d) - 1, p=np.nan)
    t, p = stats.ttest_rel(np.array([gov.loc[s] for s in seeds], dtype=float),
                           np.array([ung.loc[s] for s in seeds], dtype=float))
    n = len(d)
    se = d.std(ddof=1) / np.sqrt(n)
    tc = stats.t.ppf(0.975, n - 1)
    return dict(mean=d.mean(), ci=(d.mean() - tc * se, d.mean() + tc * se),
                t=t, df=n - 1, p=p, diffs=d)


print("=" * 96)
print("INDEPENDENT VERIFICATION OF e5_year1  (pandas/scipy, no _loader import)")
print("gap = governed MINUS ungoverned; negative = governance LOWERED the quantity")
print("=" * 96)

for model in PREFIX:
    G, U = load(model, "governed"), load(model, "ungoverned")
    gs, us = sorted(G.seed.unique()), sorted(U.seed.unique())
    seeds = sorted(set(gs) & set(us))
    print(f"\n### {model}   gov seeds={gs}  ung seeds={us}  paired={seeds}"
          f"  balanced={gs == us}")
    for _, arm_df, nm in ((0, G, "gov"), (1, U, "ung")):
        cnt = arm_df.groupby("seed").size().unique()
        print(f"    rows/run {nm}: {cnt}")
    g1, u1 = per_seed(G[G.year == 1]), per_seed(U[U.year == 1])
    print(f"    {'metric':12s} {'gov mean':>9s} {'ung mean':>9s} {'GAP':>9s} "
          f"{'95% CI':>20s} {'t':>8s} {'df':>3s} {'p':>10s}")
    for k in ("inc_rate", "high_share", "ibr"):
        r = paired(g1[k], u1[k], seeds)
        ci = f"[{r['ci'][0]:.2f},{r['ci'][1]:.2f}]" if r['ci'][0] == r['ci'][0] else "n/a"
        print(f"    {k:12s} {g1[k].loc[seeds].mean():>9.2f} {u1[k].loc[seeds].mean():>9.2f} "
              f"{r['mean']:>9.2f} {ci:>20s} {r['t']:>8.3f} {r['df']:>3d} {r['p']:>10.6f}")
    if model == "gemma3:4b":
        print("    per-seed year-1 counts (gov | ung): "
              "n_inc, n_high, n_hi&inc")
        for s in seeds:
            gg, uu = G[(G.year == 1) & (G.seed == s)], U[(U.year == 1) & (U.seed == s)]
            print(f"      seed {s}: gov {gg.inc.sum():3d} {gg.hi.sum():3d} "
                  f"{(gg.hi & gg.inc).sum():3d} | ung {uu.inc.sum():3d} {uu.hi.sum():3d} "
                  f"{(uu.hi & uu.inc).sum():3d}")

# ---------------------------------------------------------------- anchor deep dive
print("\n" + "=" * 96)
print("ANCHOR gemma3:4b -- extra checks e5_year1 does NOT do")
print("=" * 96)
G, U = load("gemma3:4b", "governed"), load("gemma3:4b", "ungoverned")
seeds = sorted(set(G.seed.unique()) & set(U.seed.unique()))

# (1) full 42-year published statistic, per seed
gall, uall = per_seed(G), per_seed(U)
r = paired(gall["ibr"], uall["ibr"], seeds)
print(f"\n[1] published 42-yr conditional IBR: gov {gall.ibr.mean():.2f}  "
      f"ung {uall.ibr.mean():.2f}  GAP {r['mean']:.2f} pp  "
      f"CI [{r['ci'][0]:.2f},{r['ci'][1]:.2f}]  t={r['t']:.3f} p={r['p']:.6f}")

# (2) year 1 vs years 2-42: the WITHIN-SEED test e5 never runs
g1, u1 = per_seed(G[G.year == 1]), per_seed(U[U.year == 1])
gr, ur = per_seed(G[G.year >= 2]), per_seed(U[U.year >= 2])
print("\n[2] IS THE YEAR-1 GAP GENUINELY DIFFERENT FROM THE LATER-YEAR GAP?")
for k in ("inc_rate", "high_share", "ibr"):
    d1 = np.array([g1[k][s] - u1[k][s] for s in seeds])
    dr = np.array([gr[k][s] - ur[k][s] for s in seeds])
    t, p = stats.ttest_rel(d1, dr)
    dd = d1 - dr
    se = dd.std(ddof=1) / np.sqrt(len(dd))
    tc = stats.t.ppf(0.975, len(dd) - 1)
    print(f"    {k:12s} yr1 gap {d1.mean():>8.2f}   yr2-42 gap {dr.mean():>8.2f}   "
          f"difference {dd.mean():>8.2f}  CI [{dd.mean()-tc*se:.2f},{dd.mean()+tc*se:.2f}]"
          f"  t={t:.3f} p={p:.6f}")

# (3) AGENT-LEVEL pairing at year 1 -- the more powerful test e5 leaves on the table
print("\n[3] AGENT-LEVEL PAIRED TEST AT YEAR 1 (390 matched (seed, agent) pairs)")
m = G[G.year == 1].merge(U[U.year == 1], on=["seed", "agent_id"], suffixes=("_g", "_u"),
                         validate="one_to_one")
print(f"    matched pairs: {len(m)}")
for lab, a, b in (("increase", m.inc_g, m.inc_u), ("high appraisal", m.hi_g, m.hi_u)):
    b01 = int((a & ~b).sum())
    b10 = int((~a & b).sum())
    res = stats.binomtest(b01, b01 + b10, 0.5) if (b01 + b10) else None
    print(f"    {lab:15s} gov-only {b01:4d}  ung-only {b10:4d}  "
          f"McNemar exact p = {res.pvalue:.4f}" if res else f"    {lab}: no discordant pairs")

# (4) late-year composition collapse the report's prose does not mention
print("\n[4] YEARS 37-42: does the composition gap close while the IBR gap stays open?")
print(f"    {'yr':>3s} {'high gap':>9s} {'IBR gap':>9s} {'n_high g':>9s} {'n_high u':>9s}")
for y in range(35, 43):
    gy, uy = per_seed(G[G.year == y]), per_seed(U[U.year == y])
    hd = np.mean([gy.high_share[s] - uy.high_share[s] for s in seeds])
    idl = [gy.ibr[s] - uy.ibr[s] for s in seeds]
    idv = np.nan if any(np.isnan(idl)) else np.mean(idl)
    print(f"    {y:>3d} {hd:>9.2f} {idv:>9.2f} {gy.n_high.sum():>9.0f} {uy.n_high.sum():>9.0f}")

# (5) does the year-1 IBR still condition on a post-treatment variable? show the
#     denominator sets are NOT the same agents even at year 1
print("\n[5] YEAR-1 IBR DENOMINATOR OVERLAP (is the conditioning defect actually gone?)")
both = int((m.hi_g & m.hi_u).sum())
gonly = int((m.hi_g & ~m.hi_u).sum())
uonly = int((~m.hi_g & m.hi_u).sum())
print(f"    HIGH in both arms: {both}   HIGH in governed only: {gonly}   "
      f"HIGH in ungoverned only: {uonly}")
print(f"    Jaccard overlap of the two year-1 IBR denominators: "
      f"{both / (both + gonly + uonly):.3f}")
print("    -> even at year 1 the two conditional statistics are computed on")
print("       DIFFERENT sets of agents. Year 1 removes world divergence, NOT the")
print("       post-treatment conditioning.")

# (6) IBR restricted to the agents HIGH in BOTH arms (a matched-denominator year-1 check)
sub = m[m.hi_g & m.hi_u]
gg = sub.groupby("seed")["inc_g"].mean() * 100
uu = sub.groupby("seed")["inc_u"].mean() * 100
r = paired(gg, uu, seeds)
print(f"\n[6] year-1 IBR on the {len(sub)} agents HIGH in BOTH arms (denominator matched):")
print(f"    gov {gg.mean():.2f}  ung {uu.mean():.2f}  GAP {r['mean']:.2f} pp  "
      f"CI [{r['ci'][0]:.2f},{r['ci'][1]:.2f}]  t={r['t']:.3f} p={r['p']:.6f}")

# (7) executed-action recode at year 1, from the audit, re-derived independently
print("\n[7] EXECUTED (world) recode at year 1, re-derived from the audit CSV")
rows = []
for arm, armdir in (("governed", "production"), ("ungoverned", "ungoverned")):
    for s in seeds:
        d = os.path.join(RES, f"{armdir}_v21_42yr_seed{s}")
        a = pd.read_csv(os.path.join(d, "irrigation_farmer_governance_audit.csv"),
                        encoding="utf-8-sig", dtype=str, keep_default_na=False)
        a["year"] = a["year"].astype(int)
        a = a[a.year == 1]
        sim = (G if arm == "governed" else U)
        sim = sim[(sim.year == 1) & (sim.seed == s)][["agent_id", "hi"]]
        mm = a.merge(sim, on="agent_id", validate="one_to_one")
        rej = mm.status.str.strip().str.upper().str.startswith("REJECTED")
        execd = np.where(rej, "maintain_demand", mm.final_skill.str.strip())
        ex_inc = pd.Series(execd).isin(INCREASE).values
        hi = mm.hi.values
        rows.append(dict(arm=arm, seed=s, n=len(mm), rej=int(rej.sum()),
                         exec_inc=100 * ex_inc.mean(),
                         exec_ibr=100 * ex_inc[hi].mean() if hi.sum() else np.nan,
                         prop_inc=100 * mm.final_skill.str.strip().isin(INCREASE).mean()))
R = pd.DataFrame(rows).set_index(["arm", "seed"])
print(R.round(2).to_string())
for k in ("exec_inc", "exec_ibr"):
    r = paired(R.loc["governed"][k], R.loc["ungoverned"][k], seeds)
    print(f"    {k}: gov {R.loc['governed'][k].mean():.2f}  "
          f"ung {R.loc['ungoverned'][k].mean():.2f}  GAP {r['mean']:.2f} pp  "
          f"CI [{r['ci'][0]:.2f},{r['ci'][1]:.2f}]  t={r['t']:.3f} p={r['p']:.8f}")

# (8) fraction-of-published-gap ratio, with an interval
print("\n[8] 'fraction of the published gap present at year 1' -- with uncertainty")
for k in ("ibr", "high_share", "inc_rate"):
    d1 = np.array([g1[k][s] - u1[k][s] for s in seeds])
    dall = np.array([gall[k][s] - uall[k][s] for s in seeds])
    n = len(d1)
    se = d1.std(ddof=1) / np.sqrt(n)
    tc = stats.t.ppf(0.975, n - 1)
    lo, hi_ = d1.mean() - tc * se, d1.mean() + tc * se
    den = dall.mean()
    print(f"    {k:12s} point {100*d1.mean()/den:>7.1f} %   "
          f"interval implied by the year-1 CI: "
          f"[{100*min(lo/den, hi_/den):.1f} %, {100*max(lo/den, hi_/den):.1f} %]")

# (9) is 'year 1' the first decision? check for a year 0 / initial row
print("\n[9] year range in the anchor corpus:",
      sorted(G.year.unique())[:3], "...", sorted(G.year.unique())[-2:])
print("    agents per (seed, year):",
      sorted(G.groupby(["seed", "year"]).size().unique()))

# (10) DOES governance change the year-1 STATED action beyond the published binary?
print("\n[10] YEAR-1 STATED ACTION BEYOND THE BINARY INCREASE COLLAPSE")
rows = []
for s in seeds:
    r = {}
    for nm, df in (("gov", G), ("ung", U)):
        a = df[(df.year == 1) & (df.seed == s)].yearly_decision.str.strip()
        r[nm + "_large"] = 100 * a.eq("increase_large").mean()
        r[nm + "_small"] = 100 * a.eq("increase_small").mean()
        r[nm + "_inc"] = 100 * a.isin(INCREASE).mean()
    rows.append(r)
D = pd.DataFrame(rows, index=seeds)
for k in ("large", "small", "inc"):
    r = paired(D["gov_" + k], D["ung_" + k], seeds)
    print(f"     increase_{k:6s}: gov {D['gov_'+k].mean():6.2f}  ung {D['ung_'+k].mean():6.2f}  "
          f"GAP {r['mean']:7.2f} pp  CI [{r['ci'][0]:6.2f},{r['ci'][1]:6.2f}]  "
          f"t={r['t']:7.3f} p={r['p']:.6f}")
tab = []
for df in (G, U):
    c = df[df.year == 1].yearly_decision.str.strip().value_counts()
    tab.append([int(c.get(k, 0)) for k in ["increase_large", "increase_small",
                                           "maintain_demand", "decrease_small",
                                           "decrease_large"]])
chi2, p, dof, _ = stats.chi2_contingency(np.array(tab))
print(f"     pooled 5-category year-1 action distribution: chi2={chi2:.1f} df={dof} p={p:.3e}")
print(f"     gov {tab[0]}   ung {tab[1]}")
print("     -> the binary collapse hides a large, significant year-1 effect on the")
print("        STATED action (increase_large -> increase_small).")

# (11) rejection vs persuasion inside the year-1 retry loop
print("\n[11] REJECTION vs PERSUASION INSIDE THE YEAR-1 RETRY LOOP (governed arm)")
tot_r = tot_p = tot_n = 0
for s in seeds:
    d = os.path.join(RES, f"production_v21_42yr_seed{s}")
    a = pd.read_csv(os.path.join(d, "irrigation_farmer_governance_audit.csv"),
                    encoding="utf-8-sig", dtype=str, keep_default_na=False)
    a = a[a.year.astype(int) == 1]
    rc = a.retry_count.astype(int)
    ap = a.status.str.upper() == "APPROVED"
    pers = a[(rc > 0) & ap]
    n_non = int((~pers.final_skill.str.strip().isin(INCREASE)).sum())
    tot_r += int((rc > 0).sum()); tot_p += len(pers); tot_n += n_non
    print(f"     seed {s}: retry>0 {int((rc>0).sum()):3d}  eventually APPROVED {len(pers):3d}"
          f"  of which non-increase {n_non:3d}  (all rejected rows have retry_count=3:"
          f" {bool((rc[(~ap)] == 3).all())})")
print(f"     TOTAL {tot_r}/390 governed year-1 rows got >=1 validator rejection+retry;")
print(f"     {tot_p} ({100*tot_p/tot_r:.1f}%) were eventually APPROVED -- the model DID change")
print(f"     its proposal under feedback. Persuasion is present, just small on the binary.")
