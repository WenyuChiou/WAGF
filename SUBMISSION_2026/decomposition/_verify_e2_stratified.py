"""INDEPENDENT adversarial re-derivation of e2_stratified.

Deliberately structured differently from e2_stratified.py:
  * pandas/numpy/scipy instead of stdlib csv + hand-rolled betainc
  * strata built by pandas rank/qcut instead of hand-written cut loops
  * standardization written as an explicit weighted dot product on a tidy frame
  * paired test via scipy.stats.ttest_rel on the two ARM VECTORS (not on
    pre-differenced values), which is a different code path to the same quantity
  * loop-year -> calendar mapping tested at THREE offsets, not asserted
Nothing is imported from _loader.py on purpose: shared code would make agreement
meaningless.

SIGN CONVENTION: every difference is GOVERNED minus UNGOVERNED. Negative = the
governed arm asked for more water LESS often.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RES = os.path.join(REPO, "examples", "irrigation_abm", "results")
PRECIP = os.path.join(REPO, "ref", "CRSS_DB", "CRSS_DB", "HistoricalData",
                      "PrismWinterPrecip_ST_NOAA_Future.csv")
UB = ["WY", "UT1", "UT2", "UT3", "CO1", "CO2", "CO3"]
INC = {"increase_large", "increase_small"}
HIGHSET = {"H", "VH"}
MODELS = {"gemma3:4b": "", "gemma3:12b": "gemma3_12b_", "gemma4:e2b": "gemma4_e2b_",
          "gemma4:e4b": "gemma4_e4b_", "ministral-3:8b": "ministral3_8b_"}
ARMDIR = {"gov": "production", "ung": "ungoverned"}


def sep(t):
    print("\n" + "=" * 96 + f"\n{t}\n" + "=" * 96)


def load(arm, pref, seed):
    d = os.path.join(RES, f"{ARMDIR[arm]}_v21_42yr_{pref}seed{seed}")
    # float_precision='round_trip' is MANDATORY here. pandas' default C float parser is
    # off by 1 ULP on lake_mead_level (0x1.061f6f371e6e1p+10 vs the correctly-rounded
    # 0x1.061f6f371e6e0p+10 that stdlib float() returns). That single ULP flips
    # precip_norm from exactly 0.0 to 6.66e-16, which sneaks a CLIPPED row past the
    # `0 < precip_norm < 1` invertibility guard and fabricates a 100.0 mm reading.
    df = pd.read_csv(os.path.join(d, "simulation_log.csv"), encoding="utf-8-sig",
                     float_precision="round_trip")
    df["_dir"] = d
    return df


def seeds_of(arm, pref):
    out = []
    for n in os.listdir(RES):
        p = f"{ARMDIR[arm]}_v21_42yr_{pref}seed"
        if n.startswith(p) and os.path.isdir(os.path.join(RES, n)):
            tail = n[len(p):]
            if tail.isdigit():
                out.append(tail)
    return sorted(out)


# --------------------------------------------------------------------------
sep("V1  precipitation: independent read + THREE candidate loop-year offsets")
pr = pd.read_csv(PRECIP, encoding="utf-8-sig")
pr = pr.rename(columns={pr.columns[0]: "cal"}).set_index("cal")
precip_mm = (pr[UB].mean(axis=1) * 25.4)
print(f"CRSS calendar coverage {precip_mm.index.min()}..{precip_mm.index.max()} "
      f"({len(precip_mm)} rows)")

anchor_seeds = sorted(set(seeds_of("gov", "")) & set(seeds_of("ung", "")))
print("anchor paired seeds:", anchor_seeds)

g42 = load("gov", "", anchor_seeds[0])
print("logged `year` column range:", g42["year"].min(), "..", g42["year"].max(),
      " n distinct agents:", g42["agent_id"].nunique())

# invert precip from the two logged hydrology columns
def invert(df):
    mn = 1.0 - (df["lake_mead_level"] - 900.0) / 320.0
    pn = 2.0 * df["drought_index"] - mn
    ok = (mn > 0) & (mn < 1) & (pn > 0) & (pn < 1)
    return df.loc[ok, ["year"]].assign(precip=100.0 * (1.0 - pn[ok]))

rec = pd.concat([invert(load(a, "", s)) for a in ("gov", "ung") for s in anchor_seeds])
per_year = rec.groupby("year")["precip"].agg(["min", "max", "count"])
print(f"loop years invertible: {len(per_year)}; "
      f"max within-year spread across ALL 10 runs: "
      f"{(per_year['max'] - per_year['min']).max():.3e} mm")

for off in (2018, 2019, 2020):
    errs = []
    for y, row in per_year.iterrows():
        cal = off + y
        if cal in precip_mm.index:
            errs.append(abs(row["min"] - precip_mm.loc[cal]))
    e = max(errs) if errs else float("nan")
    print(f"  offset {off}+y : max |recovered - CRSS| = {e:.4e} mm  "
          f"{'<== MATCH' if e < 1e-6 else ''}")

OFF = 2019
year_precip = {y: precip_mm.loc[OFF + y] for y in range(1, 43) if OFF + y in precip_mm.index}
WINDOW = sorted(year_precip)
print(f"\nexogenous window = loop years {min(WINDOW)}..{max(WINDOW)} (n={len(WINDOW)}); "
      f"years with no CRSS row: {[y for y in range(1,43) if y not in year_precip]}")

# --------------------------------------------------------------------------
sep("V2  strata built independently (pandas rank), incl. a DIFFERENT tie rule")
ps = pd.Series(year_precip).sort_index()
# rank-based tercile on years: identical intent, different implementation
yb = pd.Series(pd.qcut(ps.rank(method="first"), 3, labels=[0, 1, 2]).astype(int),
               index=ps.index)
print("precip tercile sizes:", yb.value_counts().sort_index().to_dict())
for b in (0, 1, 2):
    v = ps[yb == b]
    print(f"  band {b}: {v.min():.2f} .. {v.max():.2f} mm, years {sorted(v.index)}")

wr = g42.drop_duplicates("agent_id").set_index("agent_id")["water_right"]
# verify static + cross-arm identical, independently
for a in ("gov", "ung"):
    for s in anchor_seeds:
        d = load(a, "", s)
        assert d.groupby("agent_id")["water_right"].nunique().max() == 1, "wr not static"
        assert (d.drop_duplicates("agent_id").set_index("agent_id")["water_right"]
                .reindex(wr.index) == wr).all(), "wr differs across arm/seed"
print("water_right: static within run AND identical across all 10 anchor runs  OK")

ab_first = pd.Series(pd.qcut(wr.rank(method="first"), 3, labels=[0, 1, 2]).astype(int),
                     index=wr.index)
ab_dense = pd.Series(pd.qcut(wr.rank(method="dense"), 3, labels=[0, 1, 2],
                             duplicates="drop").astype(int), index=wr.index)
print("water_right tercile sizes (rank=first):", ab_first.value_counts().sort_index().to_dict())
print("water_right tercile sizes (rank=dense):", ab_dense.value_counts().sort_index().to_dict())
ties = wr.value_counts()
boundary_vals = []
for b in (0, 1):
    hi = wr[ab_first == b].max()
    lo = wr[ab_first == b + 1].min()
    if hi == lo:
        boundary_vals.append((b, hi, int(ties[hi])))
print("TIE-SPLIT AT A TERCILE BOUNDARY (value, n agents sharing it):", boundary_vals or "none")
print(f"agents reassigned between the two tie rules: {(ab_first != ab_dense).sum()} / {len(wr)}")

# --------------------------------------------------------------------------
sep("V3  directly standardized increase rate, anchor -- weighted dot product")


def tidy(arm, pref, seed, ybmap, abmap, executed=False):
    d = load(arm, pref, seed)
    d = d[d["year"].isin(ybmap.index)].copy()
    d["yb"] = d["year"].map(ybmap)
    d["ab"] = d["agent_id"].map(abmap)
    act = d["yearly_decision"].astype(str).str.strip()
    if executed:
        au = pd.read_csv(os.path.join(d["_dir"].iloc[0],
                                      "irrigation_farmer_governance_audit.csv"),
                         encoding="utf-8-sig", usecols=["agent_id", "year", "status"])
        m = d.merge(au, on=["agent_id", "year"], how="left", validate="one_to_one")
        assert len(m) == len(d)
        miss = m["status"].isna().sum()
        if miss:
            print(f"   !! {arm} seed{seed}: {miss} rows failed the audit join")
        act = np.where(m["status"].astype(str).str.startswith("REJECTED"),
                       "maintain_demand", act)
        act = pd.Series(act, index=d.index)
    d["inc"] = act.isin(INC).astype(int)
    d["high"] = d["wsa_label"].astype(str).str.strip().str.upper().isin(HIGHSET).astype(int)
    return d


def std_rate(d, weights, keys=("yb", "ab")):
    """Directly standardized % = sum_s w_s * rate_s, weights normalised."""
    g = d.groupby(list(keys))["inc"].agg(["sum", "size"])
    r = (g["sum"] / g["size"]).reindex(weights.index)
    assert not r.isna().any(), "empty stratum under these weights"
    w = weights / weights.sum()
    return 100.0 * float((r * w).sum())


rows = {}
for a in ("gov", "ung"):
    for s in anchor_seeds:
        rows[(a, s)] = tidy(a, "", s, yb, ab_first)

allg = pd.concat([rows[("gov", s)] for s in anchor_seeds])
allu = pd.concat([rows[("ung", s)] for s in anchor_seeds])
cg = allg.groupby(["yb", "ab"]).size()
cu = allu.groupby(["yb", "ab"]).size()
print("per-stratum counts identical across arms:", bool((cg == cu).all()))
print("stratum counts (gov):", cg.to_dict())

W = cg + cu
sg, su = std_rate(allg, W), std_rate(allu, W)
print(f"\nPOOLED standardized: gov {sg:.4f} %  ung {su:.4f} %  diff {sg-su:+.4f} pp")
print(f"POOLED crude       : gov {100*allg['inc'].mean():.4f} %  "
      f"ung {100*allu['inc'].mean():.4f} %  diff "
      f"{100*(allg['inc'].mean()-allu['inc'].mean()):+.4f} pp")

per = []
for s in anchor_seeds:
    dg, du = rows[("gov", s)], rows[("ung", s)]
    w = dg.groupby(["yb", "ab"]).size() + du.groupby(["yb", "ab"]).size()
    per.append((s, std_rate(dg, w), std_rate(du, w)))
pf = pd.DataFrame(per, columns=["seed", "gov", "ung"])
pf["diff"] = pf["gov"] - pf["ung"]
print("\nper-seed standardized (unit of inference = seed):")
print(pf.to_string(index=False, float_format=lambda v: f"{v:9.4f}"))

t, p = stats.ttest_rel(pf["gov"], pf["ung"])
m, sdv, n = pf["diff"].mean(), pf["diff"].std(ddof=1), len(pf)
tc = stats.t.ppf(0.975, n - 1)
ci = (m - tc * sdv / np.sqrt(n), m + tc * sdv / np.sqrt(n))
print(f"\nscipy ttest_rel(gov, ung): t = {t:.4f}, df = {n-1}, p = {p:.6f}")
print(f"mean diff {m:+.4f} pp   sd {sdv:.4f}   95% CI {ci[0]:+.4f} .. {ci[1]:+.4f}")
print(f"CLAIMED: -21.21 pp, CI -26.23 .. -16.18, t = -11.71, df = 4, p = 0.000304")
print(f"wilcoxon (supplementary, n=5): p = "
      f"{stats.wilcoxon(pf['gov'], pf['ung']).pvalue:.4f}  <- floor 0.0625, cannot reach .05")

# alternate tie rule
per2 = []
for s in anchor_seeds:
    dg = tidy("gov", "", s, yb, ab_dense)
    du = tidy("ung", "", s, yb, ab_dense)
    w = dg.groupby(["yb", "ab"]).size() + du.groupby(["yb", "ab"]).size()
    per2.append(std_rate(dg, w) - std_rate(du, w))
print(f"\nSAME estimator with the DENSE-rank water_right tie rule: "
      f"{np.mean(per2):+.4f} pp (primary {m:+.4f})")

# leave-one-seed-out
print("\nleave-one-seed-out on the per-seed differences:")
for i, s in enumerate(anchor_seeds):
    d4 = pf["diff"].drop(pf.index[i])
    tt, pp = stats.ttest_1samp(d4, 0)
    print(f"  drop seed {s}: mean {d4.mean():+.3f} pp  t {tt:.2f}  df {len(d4)-1}  p {pp:.5f}")

# --------------------------------------------------------------------------
sep("V4  does standardization do ANY work?  weights sweep incl. adversarial ones")
crude_d = 100 * (allg["inc"].mean() - allu["inc"].mean())
sweep = {"pooled": W, "gov-only": cg, "ung-only": cu,
         "uniform": pd.Series(1.0, index=W.index),
         "dry-heavy 100:1": pd.Series([100 if k[0] == 0 else 1 for k in W.index], index=W.index),
         "wet-heavy 1:100": pd.Series([100 if k[0] == 2 else 1 for k in W.index], index=W.index)}
for nm, w in sweep.items():
    a, b = std_rate(allg, w), std_rate(allu, w)
    print(f"  {nm:16s} gov {a:8.4f}  ung {b:8.4f}  diff {a-b:+9.4f}  "
          f"(crude {crude_d:+.4f}, delta {a-b-crude_d:+.2e})")
print("  -> pooled/gov/ung/uniform are algebraically identical to crude when counts match;")
print("     the DELIBERATELY SKEWED weights are NOT, and they move the estimate.")

# --------------------------------------------------------------------------
sep("V5  published statistic, window decomposition, and where the mass went")
def ibr(d):
    h = d[d["high"] == 1]
    return 100.0 * h["inc"].mean() if len(h) else np.nan


full = {(a, s): load(a, "", s) for a in ("gov", "ung") for s in anchor_seeds}
for k, v in full.items():
    v["inc"] = v["yearly_decision"].astype(str).str.strip().isin(INC).astype(int)
    v["high"] = v["wsa_label"].astype(str).str.strip().str.upper().isin(HIGHSET).astype(int)
w42 = [ibr(full[("gov", s)]) - ibr(full[("ung", s)]) for s in anchor_seeds]
w41 = [ibr(full[("gov", s)][full[("gov", s)]["year"] <= 41])
       - ibr(full[("ung", s)][full[("ung", s)]["year"] <= 41]) for s in anchor_seeds]
only42 = [ibr(full[("gov", s)][full[("gov", s)]["year"] == 42])
          - ibr(full[("ung", s)][full[("ung", s)]["year"] == 42]) for s in anchor_seeds]
print(f"published IBR gap, 42-yr : {np.mean(w42):+.4f} pp "
      f"(gov {np.mean([ibr(full[('gov',s)]) for s in anchor_seeds]):.4f}, "
      f"ung {np.mean([ibr(full[('ung',s)]) for s in anchor_seeds]):.4f})")
print(f"published IBR gap, 41-yr : {np.mean(w41):+.4f} pp   <- e2 quotes -21.84")
print(f"published IBR gap, yr 42 alone: {np.mean(only42):+.4f} pp "
      f"(one year of 42 moves the headline by {np.mean(w42)-np.mean(w41):+.3f} pp)")

print("\naction distribution on the 41-yr window (where did the 21 pp go?), pooled:")
dist = pd.DataFrame({
    "gov %": 100 * allg["yearly_decision"].value_counts(normalize=True),
    "ung %": 100 * allu["yearly_decision"].value_counts(normalize=True)}).fillna(0)
dist["gov-ung pp"] = dist["gov %"] - dist["ung %"]
print(dist.round(2).to_string())

# --------------------------------------------------------------------------
sep("V6  executed-action variant + audit-join integrity")
eg = pd.concat([tidy("gov", "", s, yb, ab_first, executed=True) for s in anchor_seeds])
eu = pd.concat([tidy("ung", "", s, yb, ab_first, executed=True) for s in anchor_seeds])
We = eg.groupby(["yb", "ab"]).size() + eu.groupby(["yb", "ab"]).size()
print(f"EXECUTED standardized: gov {std_rate(eg, We):.4f} %  ung {std_rate(eu, We):.4f} %  "
      f"diff {std_rate(eg, We)-std_rate(eu, We):+.4f} pp   (claimed 3.69 / 33.90 / -30.21)")

# --------------------------------------------------------------------------
sep("V7  all five model cells, balance measured")
out = []
for lab, pref in MODELS.items():
    gs, us = seeds_of("gov", pref), seeds_of("ung", pref)
    ps_ = sorted(set(gs) & set(us))
    bal = gs == us
    dd, ig = [], []
    for s in ps_:
        dg = tidy("gov", pref, s, yb, ab_first)
        du = tidy("ung", pref, s, yb, ab_first)
        w = dg.groupby(["yb", "ab"]).size() + du.groupby(["yb", "ab"]).size()
        dd.append(std_rate(dg, w) - std_rate(du, w))
        ig.append(ibr(dg) - ibr(du))
    if bal and len(ps_) >= 2:
        tt, pp = stats.ttest_1samp(dd, 0)
    else:
        tt = pp = np.nan
    out.append([lab, f"gov{gs}/ung{us}", bal, np.mean(dd), np.mean(ig), tt, len(dd) - 1, pp])
print(pd.DataFrame(out, columns=["model", "seeds", "balanced", "std_diff",
                                 "published_style_41yr", "t", "df", "p"])
      .to_string(index=False, float_format=lambda v: f"{v:9.4f}"))
print("\nNOTE on the report's 'share retained' column: it is 100*|std|/|published|, which")
print("      REPORTS A SIGN FLIP AS A SMALL POSITIVE SHARE (gemma3:12b: published -10.99,")
print("      standardized +0.24 -> printed as '2.2 % retained' rather than 'sign reversed').")
sys.exit(0)
