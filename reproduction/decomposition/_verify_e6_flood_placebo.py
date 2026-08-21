"""INDEPENDENT ADVERSARIAL RE-DERIVATION of estimator e6 (flood placebo / negative control).

Written from the raw CSVs, NOT from e6_flood_placebo.py. Deliberately structured differently:

  * pandas long-format frame instead of per-run dict counting
  * run discovery by os.walk over results/, seed pulled out of the manifest with an
    independent parser
  * the Kitagawa split computed by the COUNTERFACTUAL route
        COMP = 0.5 * [ (U_g - U_g(s<-s_u)) + (U_u(s<-s_g) - U_u) ]
    which is algebraically the same quantity as e6's  ds*(rbar_H - rbar_L)  but a different
    code path, so agreement is real evidence
  * scipy.stats.ttest_1samp / scipy.stats.t for every test and CI (e6 uses its own stdlib
    betainc + a bisection for t_crit)

It also runs four checks e6 does NOT run, all of which are adversarial:

  A. Is `yearly_decision == 'relocated'` really disjoint from a parsed appraisal label?
     (If not, e6's "active" filter and its "parsed" filter are not interchangeable.)
  B. ENFORCEMENT PRESSURE measured as "the governance stack blocked at least one proposal",
     from audit `failed_rules`, instead of e6's terminal-status REJECTED rate. e6's Section 5
     is the basis for the report's claim that the flood rules "almost never bind".
  C. How many ERROR-level thinking rules in the flood config condition on TP_LABEL?
     e6's header says "the ONLY ERROR-level appraisal-conditioned flood thinking rule".
  D. Sign of dr_low per cell, against the claim that governance "leaves the low-appraisal
     rate alone".

Sign convention, in words: every gap is GOVERNED minus UNGOVERNED. The counted action is the
FORBIDDEN one (flood do_nothing, irrigation increase_*), so a NEGATIVE gap means governance
lowered the violation rate -- the direction the paper claims as its benefit.

Usage:  python reproduction/decomposition/_verify_e6_flood_placebo.py
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FLOOD = os.path.join(REPO, "examples", "single_agent", "results")
IRRIG = os.path.join(REPO, "examples", "irrigation_abm", "results")

LEVELS = ["VL", "L", "M", "H", "VH"]
HIGH = ["H", "VH"]
FLOOD_FORBIDDEN = ["do_nothing"]
IRRIG_FORBIDDEN = ["increase_large", "increase_small"]

ARM_ROOTS = {  # family -> (governed root/group, ungoverned root/group)
    "v1": (("JOH_FINAL", "Group_C"), ("JOH_ABLATION_DISABLED", "Group_C_disabled")),
    "v2": (("JOH_FINAL_v2", "Group_C"), ("JOH_ABLATION_DISABLED_v2", "Group_C_disabled")),
}


def seed_of(run_dir: str) -> str:
    """Independent manifest parser: regex the raw JSON text for a seed field."""
    p = os.path.join(run_dir, "reproducibility_manifest.json")
    txt = open(p, encoding="utf-8").read()
    hits = set(re.findall(r'"seed"\s*:\s*"?(\d+)"?', txt))
    if len(hits) != 1:
        # fall back to a structured walk if the flat regex is ambiguous
        obj = json.loads(txt)
        found = []
        stack = [obj]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                for k, v in o.items():
                    if k.lower() == "seed":
                        found.append(str(v))
                    else:
                        stack.append(v)
            elif isinstance(o, list):
                stack.extend(o)
        hits = set(found)
    if len(hits) != 1:
        raise RuntimeError(f"ambiguous seed {hits} in {p}")
    return hits.pop()


def flood_runs() -> pd.DataFrame:
    """One row per flood run directory, discovered by walking the results tree."""
    recs = []
    for fam, ((groot, ggrp), (uroot, ugrp)) in ARM_ROOTS.items():
        for arm, (root, grp) in (("gov", (groot, ggrp)), ("ung", (uroot, ugrp))):
            base = os.path.join(FLOOD, root)
            if not os.path.isdir(base):
                raise RuntimeError(f"missing {base}")
            for model in sorted(os.listdir(base)):
                d = os.path.join(base, model, grp)
                if not os.path.isdir(d):
                    continue
                for run in sorted(os.listdir(d)):
                    rd = os.path.join(d, run)
                    if not os.path.isfile(os.path.join(rd, "simulation_log.csv")):
                        continue
                    recs.append({"cell": f"{fam} {model}", "arm": arm, "run": run,
                                 "seed": seed_of(rd), "dir": rd})
    return pd.DataFrame(recs)


def load_flood(run_dir: str) -> pd.DataFrame:
    df = pd.read_csv(os.path.join(run_dir, "simulation_log.csv"), encoding="utf-8-sig",
                     dtype=str, keep_default_na=False)
    df["tp"] = df["threat_appraisal"].str.strip().str.upper()
    df["act"] = df["yearly_decision"].str.strip()
    return df


def rates(df: pd.DataFrame, forbidden) -> dict:
    """R (conditional on HIGH), r_low, U (unconditional over parsed), s (HIGH share)."""
    parsed = df[df["tp"].isin(LEVELS)]
    hi = parsed[parsed["tp"].isin(HIGH)]
    lo = parsed[~parsed["tp"].isin(HIGH)]
    f = lambda d: float("nan") if len(d) == 0 else 100.0 * d["act"].isin(forbidden).sum() / len(d)
    return {"n_parsed": len(parsed), "n_high": len(hi), "n_low": len(lo),
            "R": f(hi), "rL": f(lo), "U": f(parsed),
            "s": float("nan") if len(parsed) == 0 else 100.0 * len(hi) / len(parsed)}


def split(g: dict, u: dict) -> dict:
    """Counterfactual-route Kitagawa split. Different code path from e6's closed form."""
    sg, su = g["s"] / 100.0, u["s"] / 100.0
    U = lambda s, rH, rL: s * rH + (1 - s) * rL
    Ug, Uu = U(sg, g["R"], g["rL"]), U(su, u["R"], u["rL"])
    # composition = average of the two one-sided share-swap counterfactuals
    comp = 0.5 * ((Ug - U(su, g["R"], g["rL"])) + (U(sg, u["R"], u["rL"]) - Uu))
    # behaviour = average of the two one-sided rate-swap counterfactuals
    beh = 0.5 * ((Ug - U(sg, u["R"], u["rL"])) + (U(su, g["R"], g["rL"]) - Uu))
    return {"dR": g["R"] - u["R"], "dU": g["U"] - u["U"], "ds": g["s"] - u["s"],
            "dr_high": g["R"] - u["R"], "dr_low": g["rL"] - u["rL"],
            "COMP": comp, "BEH": beh,
            "Ug_from_strata": Ug, "Uu_from_strata": Uu,
            "cond_minus_uncond": (g["R"] - u["R"]) - (g["U"] - u["U"])}


def ci95(vals):
    v = np.asarray([x for x in vals], float)
    n = len(v)
    m = v.mean()
    if n < 2:
        return m, np.nan, np.nan
    se = v.std(ddof=1) / np.sqrt(n)
    h = stats.t.ppf(0.975, n - 1) * se
    return m, m - h, m + h


def main() -> int:
    pd.set_option("display.width", 200)
    print("=" * 100)
    print("INDEPENDENT RE-DERIVATION OF e6 (pandas + scipy, counterfactual decomposition route)")
    print("=" * 100)

    runs = flood_runs()

    # ---- CHECK A: is the 'relocated' filter interchangeable with the parsed filter? ----
    cross = []
    for _, r in runs.iterrows():
        df = load_flood(r["dir"])
        cross.append({
            "reloc_and_parsed": int(((df["act"] == "relocated") & df["tp"].isin(LEVELS)).sum()),
            "notreloc_and_unparsed": int(((df["act"] != "relocated") & ~df["tp"].isin(LEVELS)).sum()),
            "rows": len(df),
        })
    cx = pd.DataFrame(cross)
    print("\nCHECK A  'relocated' rows carrying a PARSED appraisal, corpus-wide : "
          f"{cx['reloc_and_parsed'].sum()}")
    print(f"         non-relocated rows with an UNPARSED appraisal            : "
          f"{cx['notreloc_and_unparsed'].sum()}")
    print(f"         total flood rows                                          : {cx['rows'].sum()} "
          f"over {len(runs)} runs (all 1000?  {set(cx['rows']) == {1000}})")
    print("         -> if the first is 0 the two filters coincide and e6's 'active' step is a no-op")

    # ---- per-run measurement -------------------------------------------------
    recs = []
    for _, r in runs.iterrows():
        df = load_flood(r["dir"])
        m = rates(df, FLOOD_FORBIDDEN)
        m.update(cell=r["cell"], arm=r["arm"], seed=r["seed"], dir=r["dir"])
        recs.append(m)
    per = pd.DataFrame(recs)

    # ---- seed matching -------------------------------------------------------
    print("\nSECTION 1  seed sets, read from reproducibility_manifest.json")
    inv = []
    for cell, sub in per.groupby("cell"):
        gs = sorted(sub[sub.arm == "gov"].seed, key=int)
        us = sorted(sub[sub.arm == "ung"].seed, key=int)
        match = sorted(set(gs) & set(us), key=int)
        inv.append({"cell": cell, "gov": ",".join(gs), "ung": ",".join(us),
                    "matched": len(match), "balanced": gs == us})
    inv = pd.DataFrame(inv)
    print(inv.to_string(index=False))

    # ---- per seed decomposition ---------------------------------------------
    rows = []
    for cell, sub in per.groupby("cell"):
        g = sub[sub.arm == "gov"].set_index("seed")
        u = sub[sub.arm == "ung"].set_index("seed")
        for s in sorted(set(g.index) & set(u.index), key=int):
            d = split(g.loc[s].to_dict(), u.loc[s].to_dict())
            d.update(cell=cell, seed=s,
                     R_g=g.loc[s, "R"], R_u=u.loc[s, "R"], U_g=g.loc[s, "U"], U_u=u.loc[s, "U"],
                     s_g=g.loc[s, "s"], s_u=u.loc[s, "s"],
                     nhi_g=g.loc[s, "n_high"], nhi_u=u.loc[s, "n_high"])
            rows.append(d)
    seedlvl = pd.DataFrame(rows)

    # identity checks on my own arithmetic
    resid = (seedlvl["dU"] - (seedlvl["BEH"] + seedlvl["COMP"])).abs().max()
    resid_u = (seedlvl["U_g"] - seedlvl["Ug_from_strata"]).abs().max()
    print(f"\n  my own identity residuals: |dU-(BEH+COMP)| max {resid:.2e} pp ; "
          f"|U - (s*rH+(1-s)*rL)| max {resid_u:.2e} pp")

    cellavg = seedlvl.groupby("cell").agg(
        n=("seed", "size"), R_g=("R_g", "mean"), R_u=("R_u", "mean"), dR=("dR", "mean"),
        U_g=("U_g", "mean"), U_u=("U_u", "mean"), dU=("dU", "mean"),
        s_g=("s_g", "mean"), s_u=("s_u", "mean"), ds=("ds", "mean"),
        BEH=("BEH", "mean"), COMP=("COMP", "mean"), dr_low=("dr_low", "mean"),
        cmu=("cond_minus_uncond", "mean"),
        min_nhi=("nhi_g", "min"),
    )
    min_nhi_u = seedlvl.groupby("cell")["nhi_u"].min()
    cellavg["min_nhi"] = np.minimum(cellavg["min_nhi"], min_nhi_u)
    cellavg = cellavg.join(inv.set_index("cell")[["balanced"]])
    print("\nSECTION 4  per-cell placebo table (seed-matched runs only, gaps = gov - ung, pp)")
    print(cellavg.round(2).to_string())

    # ---- irrigation anchor through the identical arithmetic ------------------
    irr_rows = []
    for s in ["42", "43", "44", "45", "46"]:
        per_arm = {}
        for arm, pfx in (("gov", "production"), ("ung", "ungoverned")):
            p = os.path.join(IRRIG, f"{pfx}_v21_42yr_seed{s}", "simulation_log.csv")
            df = pd.read_csv(p, encoding="utf-8-sig", dtype=str, keep_default_na=False)
            df["tp"] = df["wsa_label"].str.strip().str.upper()
            df["act"] = df["yearly_decision"].str.strip()
            per_arm[arm] = rates(df, IRRIG_FORBIDDEN)
        d = split(per_arm["gov"], per_arm["ung"])
        d.update(seed=s, R_g=per_arm["gov"]["R"], R_u=per_arm["ung"]["R"],
                 U_g=per_arm["gov"]["U"], U_u=per_arm["ung"]["U"],
                 s_g=per_arm["gov"]["s"], s_u=per_arm["ung"]["s"])
        irr_rows.append(d)
    irr = pd.DataFrame(irr_rows)
    print("\nSECTION 6  irrigation anchor gemma3:4b, same arithmetic, per seed")
    print(irr[["seed", "R_g", "R_u", "dR", "U_g", "U_u", "dU", "s_g", "s_u", "ds",
               "BEH", "COMP", "dr_low", "cond_minus_uncond"]].round(2).to_string(index=False))

    # ---- headline aggregates + CIs ------------------------------------------
    MIN_HIGH = 30
    primary = cellavg[(cellavg["balanced"]) & (cellavg["min_nhi"] >= MIN_HIGH)].index.tolist()
    usable = cellavg[cellavg["min_nhi"] >= MIN_HIGH].index.tolist()
    print(f"\n  PRIMARY cells (balanced AND min n_high >= {MIN_HIGH}) : {primary}")
    print(f"  ALL USABLE cells                                     : {usable}")

    print("\nSECTION 9b  headline numbers with 95% CI (scipy t)")
    tests = [
        ("flood  ds  (PRIMARY cells)", cellavg.loc[primary, "ds"]),
        ("flood  COMPOSITION (PRIMARY)", cellavg.loc[primary, "COMP"]),
        ("flood  ds  (ALL usable cells)", cellavg.loc[usable, "ds"]),
        ("flood  COMPOSITION (ALL usable)", cellavg.loc[usable, "COMP"]),
        ("irrig  ds  (5 seeds)", irr["ds"]),
        ("irrig  COMPOSITION (5 seeds)", irr["COMP"]),
        ("irrig  dR conditional (5 seeds)", irr["dR"]),
        ("irrig  dU unconditional (5 seeds)", irr["dU"]),
    ]
    for name, vals in tests:
        m, lo, hi = ci95(vals)
        t, p = stats.ttest_1samp(np.asarray(vals, float), 0.0)
        flag = "excludes 0" if (lo > 0 or hi < 0) else "INCLUDES 0"
        print(f"  {name:34s} n={len(vals)}  {m:+8.2f} pp  95% CI [{lo:+7.2f},{hi:+7.2f}]  "
              f"t={t:+7.3f} p={p:.5f}  <- {flag}")

    # ---- CHECK B: enforcement pressure, blocked-attempt rate not terminal status ----
    print("\nCHECK B  ENFORCEMENT PRESSURE -- terminal REJECTED rate vs 'a rule blocked at least")
    print("         one proposal' (audit failed_rules non-empty). e6 Section 5 reports only the")
    print("         first, and the e6 report calls the flood rules 'almost never binding'.")
    press = []
    for _, r in runs.iterrows():
        ap = os.path.join(r["dir"], "household_governance_audit.csv")
        if not os.path.isfile(ap):
            continue
        a = pd.read_csv(ap, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        fr = a["failed_rules"].fillna("").str.strip()
        press.append({"cell": r["cell"], "arm": r["arm"], "seed": r["seed"], "n": len(a),
                      "pct_terminal_rej": 100.0 * a["status"].str.startswith("REJECTED").sum() / len(a),
                      "pct_any_rule_fired": 100.0 * (fr != "").sum() / len(a),
                      "pct_etb_fired": 100.0 * fr.str.contains("extreme_threat_block").sum() / len(a)})
    pr = pd.DataFrame(press)
    matched_seeds = {c: set(seedlvl[seedlvl.cell == c].seed) for c in seedlvl.cell.unique()}
    pr = pr[[s in matched_seeds.get(c, set()) for c, s in zip(pr.cell, pr.seed)]]
    print(pr.groupby(["cell", "arm"])[["pct_terminal_rej", "pct_any_rule_fired", "pct_etb_fired"]]
          .mean().round(2).to_string())

    print("\n         same measure on the IRRIGATION anchor, for scale:")
    ipress = []
    for arm, pfx in (("gov", "production"), ("ung", "ungoverned")):
        for s in ["42", "43", "44", "45", "46"]:
            ap = os.path.join(IRRIG, f"{pfx}_v21_42yr_seed{s}",
                              "irrigation_farmer_governance_audit.csv")
            a = pd.read_csv(ap, encoding="utf-8-sig", dtype=str, keep_default_na=False)
            fr = a["failed_rules"].fillna("").str.strip().replace("Unknown", "")
            ipress.append({"arm": arm, "seed": s,
                           "pct_terminal_rej": 100.0 * a["status"].str.startswith("REJECTED").sum() / len(a),
                           "pct_any_rule_fired": 100.0 * (fr != "").sum() / len(a)})
    ip = pd.DataFrame(ipress)
    print(ip.groupby("arm")[["pct_terminal_rej", "pct_any_rule_fired"]].mean().round(2).to_string())
    print("         (irrigation failed_rules == 'Unknown' is the ungoverned-arm precondition")
    print("          failure, NOT a validator; it is mapped to empty above)")

    # ---- CHECK C: how many ERROR thinking rules condition on TP_LABEL? -------
    print("\nCHECK C  ERROR-level thinking rules that condition on TP_LABEL, from config_snapshot")
    import yaml
    p = os.path.join(FLOOD, "JOH_FINAL", "gemma3_4b", "Group_C", "Run_1", "config_snapshot.yaml")
    cfg = yaml.safe_load(open(p, encoding="utf-8"))
    for rule in cfg["household"]["governance"]["strict"]["thinking_rules"]:
        constructs = {rule.get("construct")} | {c.get("construct")
                                                for c in rule.get("conditions", []) or []}
        vals = rule.get("when_above") or [v for c in (rule.get("conditions") or [])
                                          for v in (c.get("values") or [])]
        print(f"    id={rule.get('id'):24s} level={rule.get('level'):8s} "
              f"constructs={sorted(x for x in constructs if x)} when={vals} "
              f"blocks={rule.get('blocked_skills')}")

    # ---- CHECK D: sign of dr_low ------------------------------------------
    print("\nCHECK D  dr_low per cell (governed - ungoverned do_nothing rate WITHIN the LOW stratum)")
    print(cellavg[["dr_low", "dR"]].round(2).to_string())
    pos = (cellavg["dr_low"] > 0).sum()
    print(f"         cells with dr_low > 0 (governance RAISED do_nothing at low appraisal): "
          f"{pos}/{len(cellavg)}")
    print(f"         irrigation anchor dr_low = {irr['dr_low'].mean():+.2f} pp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
