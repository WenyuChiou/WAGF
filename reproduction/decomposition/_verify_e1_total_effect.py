"""INDEPENDENT adversarial re-derivation of e1_total_effect.

Written from the raw CSVs with pandas + scipy, deliberately structured differently
from e1_total_effect.py (long dataframe -> groupby -> pivot, instead of dict-of-dicts).
It imports NOTHING from _loader.py, on purpose: agreement between two independent
implementations is the evidence; agreement of a script with itself is not.

Sign convention, in words: gap = governed minus ungoverned. NEGATIVE means the
governed (validators ON) arm has the LOWER increase rate.

Writes nothing except stdout.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

import pandas as pd
from scipy import stats

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RES = os.path.join(REPO, "examples", "irrigation_abm", "results")

INCREASE = {"increase_large", "increase_small"}
HIGH = {"H", "VH"}
PREFIX = {"gemma3:4b": "", "gemma3:12b": "gemma3_12b_", "gemma4:e2b": "gemma4_e2b_",
          "gemma4:e4b": "gemma4_e4b_", "ministral-3:8b": "ministral3_8b_"}
ARMDIR = {"governed": "production", "ungoverned": "ungoverned"}


def discover() -> pd.DataFrame:
    """One long dataframe of every decision row in the irrigation corpus."""
    frames = []
    for model, pref in PREFIX.items():
        for arm, ad in ARMDIR.items():
            pat = os.path.join(RES, f"{ad}_v21_42yr_{pref}seed*")
            for d in sorted(glob.glob(pat)):
                if not os.path.isdir(d):
                    continue
                base = os.path.basename(d)
                # guard: the anchor prefix "" would otherwise swallow every model
                m = re.fullmatch(rf"{ad}_v21_42yr_{re.escape(pref)}seed(\d+)", base)
                if not m:
                    continue
                p = os.path.join(d, "simulation_log.csv")
                if not os.path.isfile(p):
                    print(f"  !! MISSING simulation_log.csv in {base}")
                    continue
                df = pd.read_csv(p, encoding="utf-8-sig", dtype=str, keep_default_na=False)
                df["model"] = model
                df["arm"] = arm
                df["seed"] = m.group(1)
                df["_dir"] = base
                frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    print("INDEPENDENT VERIFICATION of e1_total_effect (pandas/scipy, no _loader import)")
    print(f"results root: {RES}\n")

    df = discover()
    print(f"rows loaded corpus-wide: {len(df)}  from {df['_dir'].nunique()} run dirs")

    # ---- raw-string hygiene on the outcome column ------------------------
    raw = df["yearly_decision"]
    print("\nyearly_decision RAW value inventory (no strip, no case-fold):")
    for v, n in raw.value_counts().items():
        print(f"   {v!r:22s} {n}")
    stripped = raw.str.strip()
    print(f"  rows where strip() changes the value ....... {(stripped != raw).sum()}")
    print(f"  rows where lower() changes the value ....... {(stripped.str.lower() != stripped).sum()}")
    print(f"  blank after strip .......................... {(stripped == '').sum()}")

    wraw = df["wsa_label"]
    wstr = wraw.str.strip().str.upper()
    print("\nwsa_label RAW value inventory:")
    for v, n in wraw.value_counts().items():
        print(f"   {v!r:8s} {n}")
    print(f"  rows where strip/upper changes the value ... {(wstr != wraw).sum()}")

    df["is_incr"] = stripped.isin(INCREASE)
    df["is_high"] = wstr.isin(HIGH)

    # ---- duplicate key check --------------------------------------------
    dups = df.duplicated(subset=["_dir", "agent_id", "year"]).sum()
    print(f"\nduplicate (run, agent_id, year) keys corpus-wide ... {dups}")
    rc = df.groupby("_dir").size()
    print(f"rows per run: min={rc.min()} max={rc.max()} unique={sorted(rc.unique())}")
    print(f"agents per run: {sorted(df.groupby('_dir')['agent_id'].nunique().unique())}"
          f"   years per run: {sorted(df.groupby('_dir')['year'].nunique().unique())}")

    # ---- per-run rates ---------------------------------------------------
    g = df.groupby(["model", "arm", "seed"]).agg(
        n=("is_incr", "size"),
        n_incr=("is_incr", "sum"),
        n_high=("is_high", "sum"),
        n_incr_high=("is_incr", lambda s: (s & df.loc[s.index, "is_high"]).sum()),
    ).reset_index()
    g["E1"] = 100.0 * g["n_incr"] / g["n"]
    g["IBR"] = 100.0 * g["n_incr_high"] / g["n_high"]
    g["HIGHshare"] = 100.0 * g["n_high"] / g["n"]

    print("\n" + "=" * 90)
    print("ANCHOR gemma3:4b -- per-seed, computed independently")
    print("=" * 90)
    a = g[g["model"] == "gemma3:4b"]
    piv = a.pivot(index="seed", columns="arm", values="E1")
    piv["diff"] = piv["governed"] - piv["ungoverned"]
    ip = a.pivot(index="seed", columns="arm", values="IBR")
    ip["diff"] = ip["governed"] - ip["ungoverned"]
    print(f"  {'seed':>5s} {'gov E1':>8s} {'ung E1':>8s} {'diff':>8s} | "
          f"{'gov IBR':>8s} {'ung IBR':>8s} {'IBRdiff':>8s} {'ratio %':>8s}")
    for s in piv.index:
        r = 100.0 * piv.loc[s, "diff"] / ip.loc[s, "diff"]
        print(f"  {s:>5s} {piv.loc[s,'governed']:>8.4f} {piv.loc[s,'ungoverned']:>8.4f} "
              f"{piv.loc[s,'diff']:>8.4f} | {ip.loc[s,'governed']:>8.4f} "
              f"{ip.loc[s,'ungoverned']:>8.4f} {ip.loc[s,'diff']:>8.4f} {r:>8.2f}")

    d = piv["diff"].values
    t, p = stats.ttest_rel(piv["governed"].values, piv["ungoverned"].values)
    n = len(d)
    se = d.std(ddof=1) / n ** 0.5
    tc = stats.t.ppf(0.975, n - 1)
    print(f"\n  MEAN gov E1 = {piv['governed'].mean():.4f}   "
          f"MEAN ung E1 = {piv['ungoverned'].mean():.4f}")
    print(f"  E1 GAP      = {d.mean():+.4f} pp   sd(diff)={d.std(ddof=1):.4f}  se={se:.4f}")
    print(f"  paired t (scipy ttest_rel) t={t:.6f}  df={n-1}  p={p:.9f}")
    print(f"  95% CI  {d.mean()-tc*se:+.4f} .. {d.mean()+tc*se:+.4f}   (tcrit={tc:.6f})")
    print(f"  Wilcoxon signed-rank p = {stats.wilcoxon(d).pvalue:.5f} "
          f"(supplementary; n=5 floor is 0.0625)")
    print(f"  sd(gov)={piv['governed'].std(ddof=1):.4f}  "
          f"sd(ung)={piv['ungoverned'].std(ddof=1):.4f}")

    print(f"\n  recomputed conditional IBR: gov {ip['governed'].mean():.4f}  "
          f"ung {ip['ungoverned'].mean():.4f}  gap {ip['diff'].mean():+.4f}")
    it, ip_ = stats.ttest_rel(ip["governed"].values, ip["ungoverned"].values)
    print(f"  conditional paired t={it:.4f} p={ip_:.8f}")

    # ---- the "% surviving" ratio, WITH uncertainty (the report gives none)
    ratios = 100.0 * piv["diff"].values / ip["diff"].values
    rm, rsd = ratios.mean(), ratios.std(ddof=1)
    rse = rsd / n ** 0.5
    print(f"\n  'fraction surviving' as a RATIO OF MEANS  = "
          f"{100.0*d.mean()/ip['diff'].mean():.2f}%   (what the script reports)")
    print(f"  'fraction surviving' as MEAN OF PER-SEED RATIOS = {rm:.2f}% "
          f"(sd {rsd:.2f}, se {rse:.2f})")
    print(f"     -> 95% CI on the per-seed ratio: {rm-tc*rse:.1f}% .. {rm+tc*rse:.1f}%")
    print("     The script's SURVIVES/WEAKENED cut sits at 85%. That threshold is INSIDE")
    print("     this interval, so the verdict label is not robust to sampling error.")

    # ---- all models ------------------------------------------------------
    print("\n" + "=" * 90)
    print("ALL MODELS -- paired on the intersection of seed sets")
    print("=" * 90)
    print(f"  {'model':16s} {'gov seeds':16s} {'ung seeds':16s} {'pairs':>5s} "
          f"{'E1 gov':>7s} {'E1 ung':>7s} {'GAP':>8s} {'t':>9s} {'p':>10s}")
    for model in PREFIX:
        sub = g[g["model"] == model]
        gs = sorted(sub[sub["arm"] == "governed"]["seed"])
        us = sorted(sub[sub["arm"] == "ungoverned"]["seed"])
        ps = sorted(set(gs) & set(us))
        pv = sub[sub["seed"].isin(ps)].pivot(index="seed", columns="arm", values="E1")
        dd = pv["governed"] - pv["ungoverned"]
        if len(ps) >= 2:
            tt, pp = stats.ttest_rel(pv["governed"].values, pv["ungoverned"].values)
        else:
            tt = pp = float("nan")
        bal = "" if gs == us else "   <-- UNBALANCED, paired test not valid"
        print(f"  {model:16s} {','.join(gs):16s} {','.join(us):16s} {len(ps):>5d} "
              f"{pv['governed'].mean():>7.2f} {pv['ungoverned'].mean():>7.2f} "
              f"{dd.mean():>+8.2f} {tt:>9.3f} {pp:>10.6f}{bal}")

    # ---- E1-world, independent join -------------------------------------
    print("\n" + "=" * 90)
    print("E1-world (executed action) -- independent join, anchor only")
    print("=" * 90)
    out = {}
    statuses = {}
    for arm, ad in ARMDIR.items():
        for s in ["42", "43", "44", "45", "46"]:
            dpath = os.path.join(RES, f"{ad}_v21_42yr_seed{s}")
            sim = pd.read_csv(os.path.join(dpath, "simulation_log.csv"),
                              encoding="utf-8-sig", dtype=str, keep_default_na=False)
            aud = pd.read_csv(os.path.join(dpath, "irrigation_farmer_governance_audit.csv"),
                              encoding="utf-8-sig", dtype=str, keep_default_na=False)
            aud = aud.loc[:, ~aud.columns.duplicated()]
            for st in aud["status"].str.strip().str.upper():
                statuses[st] = statuses.get(st, 0) + 1
            j = sim.merge(aud[["agent_id", "year", "status", "final_skill", "proposed_skill"]],
                          on=["agent_id", "year"], how="outer", indicator=True,
                          validate="one_to_one")
            assert (j["_merge"] == "both").all(), f"join gap in {dpath}"
            st = j["status"].str.strip().str.upper()
            fs = j["final_skill"].str.strip()
            ex = fs.where(~st.str.startswith("REJECTED"), "maintain_demand")
            out[(arm, s)] = 100.0 * ex.isin(INCREASE).mean()
            # cross-check: yearly_decision vs final_skill
            if arm == "governed" and s == "42":
                agree = (j["yearly_decision"].str.strip() == fs).mean()
                print(f"  [gov seed42] yearly_decision == final_skill on {100*agree:.2f}% of rows")
    gw = [out[("governed", s)] for s in ["42", "43", "44", "45", "46"]]
    uw = [out[("ungoverned", s)] for s in ["42", "43", "44", "45", "46"]]
    tw, pw = stats.ttest_rel(gw, uw)
    print(f"  audit status inventory (anchor, both arms): {statuses}")
    print(f"  gov {sum(gw)/5:.2f}%   ung {sum(uw)/5:.2f}%   "
          f"GAP {(sum(gw)-sum(uw))/5:+.2f} pp   t={tw:.3f} p={pw:.8f}")

    # ---- ARM EXCHANGEABILITY AUDIT (the caveat the report admits it skipped)
    print("\n" + "=" * 90)
    print("ARM EXCHANGEABILITY AUDIT -- reproducibility manifests (caveat 7, unaudited)")
    print("=" * 90)
    keys = ["git_commit", "commit", "git_sha", "code_version", "model", "llm_model",
            "seed", "timestamp", "run_timestamp", "framework_version", "python_version"]
    for arm, ad in ARMDIR.items():
        for s in ["42", "43", "44", "45", "46"]:
            mp = os.path.join(RES, f"{ad}_v21_42yr_seed{s}", "reproducibility_manifest.json")
            if not os.path.isfile(mp):
                print(f"  {ad}/seed{s}: NO reproducibility_manifest.json")
                continue
            with open(mp, encoding="utf-8") as fh:
                man = json.load(fh)
            flat = {}

            def walk(o, pre=""):
                if isinstance(o, dict):
                    for k, v in o.items():
                        walk(v, f"{pre}{k}.")
                else:
                    flat[pre[:-1]] = o
            walk(man)
            picked = {k: v for k, v in flat.items()
                      if any(t in k.lower() for t in
                             ("commit", "sha", "dirty", "branch", "model", "version",
                              "timestamp", "started", "seed"))}
            print(f"  --- {ad}/seed{s}")
            for k in sorted(picked):
                print(f"        {k} = {picked[k]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
