"""INDEPENDENT adversarial re-derivation of e3_decomposition's headline.

Deliberately NOT importing _loader.py: this script re-reads the CSVs with pandas,
re-implements every definition from the brief, and computes the Kitagawa /
Oaxaca-Blinder split by a DIFFERENT algebraic route (long-format groupby +
outer-product weighting) so that agreement is evidence, not tautology.

Sign convention, in words: every gap is GOVERNED minus UNGOVERNED. A NEGATIVE gap
means the governed arm has the LOWER rate (the direction the paper claims as benefit).
A POSITIVE composition component means the appraisal re-sorting ADDS increases to the
governed arm, i.e. it pushes against the observed reduction.

Run:  python reproduction/decomposition/_verify_e3_decomposition.py
"""
from __future__ import annotations

import glob
import os
import re

import pandas as pd

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
RES = os.path.join(REPO, "examples", "irrigation_abm", "results")

INCREASE = {"increase_large", "increase_small"}
HIGH = {"H", "VH"}
MODELS = [("gemma3:4b", ""), ("gemma3:12b", "gemma3_12b_"),
          ("gemma4:e2b", "gemma4_e2b_"), ("gemma4:e4b", "gemma4_e4b_"),
          ("ministral-3:8b", "ministral3_8b_")]
ARM_DIR = {"gov": "production", "ung": "ungoverned"}


# ---------------------------------------------------------------- corpus
def seed_map(prefix):
    out = {}
    for arm, ad in ARM_DIR.items():
        ss = []
        for d in sorted(glob.glob(os.path.join(RES, f"{ad}_v21_42yr_{prefix}seed*"))):
            if not os.path.isdir(d):
                continue
            if not os.path.isfile(os.path.join(d, "simulation_log.csv")):
                raise RuntimeError(f"no simulation_log.csv in {d}")
            ss.append(re.search(r"seed(\d+)$", os.path.basename(d)).group(1))
        out[arm] = sorted(ss)
    return out


def load(prefix, arm, seed):
    d = os.path.join(RES, f"{ARM_DIR[arm]}_v21_42yr_{prefix}seed{seed}")
    df = pd.read_csv(os.path.join(d, "simulation_log.csv"), encoding="utf-8-sig",
                     dtype=str, keep_default_na=False)
    df["_wsa"] = df["wsa_label"].str.strip().str.upper()
    df["_act"] = df["yearly_decision"].str.strip()
    df["_inc"] = df["_act"].isin(INCREASE).astype(int)
    df["_hi"] = df["_wsa"].isin(HIGH)
    df["_s2"] = df["_hi"].map({True: "HIGH", False: "NOT_HIGH"})
    df["_dir"] = d
    return df


def load_exec(prefix, arm, seed, df):
    """Executed action: REJECTED* -> maintain_demand (Phase-1 finding)."""
    d = os.path.join(RES, f"{ARM_DIR[arm]}_v21_42yr_{prefix}seed{seed}")
    a = pd.read_csv(os.path.join(d, "irrigation_farmer_governance_audit.csv"),
                    encoding="utf-8-sig", dtype=str, keep_default_na=False)
    a = a[["agent_id", "year", "status", "final_skill"]].copy()
    a["agent_id"] = a["agent_id"].str.strip()
    a["year"] = a["year"].str.strip()
    if a.duplicated(["agent_id", "year"]).any():
        raise RuntimeError("duplicate audit key")
    a["_exec"] = a["final_skill"].str.strip().where(
        ~a["status"].str.strip().str.upper().str.startswith("REJECTED"), "maintain_demand")
    m = df.copy()
    m["agent_id"] = m["agent_id"].str.strip()
    m["year"] = m["year"].str.strip()
    m = m.merge(a[["agent_id", "year", "_exec"]], on=["agent_id", "year"],
                how="left", validate="one_to_one")
    if m["_exec"].isna().any():
        raise RuntimeError("unmatched sim row")
    m["_inc"] = m["_exec"].isin(INCREASE).astype(int)
    return m


# ---------------------------------------------- decomposition, own route
def kitagawa(dg, du, col):
    """Long-format route: build a per-stratum frame, then vector-multiply.

    Returns dict of components as FRACTIONS of 1 (caller x100).
    """
    def tab(d):
        g = d.groupby(col, dropna=False)["_inc"].agg(["size", "sum"])
        return g
    tg, tu = tab(dg), tab(du)
    strata = sorted(set(tg.index) | set(tu.index))
    Ng, Nu = len(dg), len(du)
    rows = []
    for s in strata:
        ng = int(tg["size"].get(s, 0)); ig = int(tg["sum"].get(s, 0))
        nu = int(tu["size"].get(s, 0)); iu = int(tu["sum"].get(s, 0))
        if ng and nu:
            rg, ru = ig / ng, iu / nu
        elif ng:
            rg = ru = ig / ng          # same convention as e3
        elif nu:
            rg = ru = iu / nu
        else:
            rg = ru = 0.0

        rows.append(dict(stratum=s, ng=ng, nu=nu, ig=ig, iu=iu,
                         sg=ng / Ng, su=nu / Nu, rg=rg, ru=ru))
    f = pd.DataFrame(rows)
    # DIFFERENT algebraic route: build the four cross-products explicitly and
    # combine, rather than summing four hand-written expressions.
    A = (f.sg * f.rg).sum()        # R_g
    B = (f.su * f.ru).sum()        # R_u
    C = (f.sg * f.ru).sum()        # governed shares, untreated rates
    D = (f.su * f.rg).sum()        # untreated shares, governed rates
    total = A - B
    comp_u = C - B                 # sum (sg-su)*ru
    behv_u = D - B                 # sum su*(rg-ru)
    inter = A - C - D + B          # sum (sg-su)*(rg-ru)
    comp_g = A - D                 # sum (sg-su)*rg
    comp_sym = 0.5 * (comp_u + comp_g)
    behv_sym = 0.5 * ((D - B) + (A - C))
    return dict(total=total, comp_sym=comp_sym, behv_sym=behv_sym,
                comp_u=comp_u, behv_u=behv_u, inter=inter, comp_g=comp_g,
                behv_g=behv_u, table=f, Rg=A, Ru=B)


# ------------------------------------------------------------------ stats
def paired(vals):
    import statistics as st
    n = len(vals)
    m = sum(vals) / n
    s = st.stdev(vals) if n > 1 else float("nan")
    t = m / (s / n ** 0.5) if (n > 1 and s) else float("nan")
    try:
        from scipy import stats as sps
        p = float(sps.t.sf(abs(t), n - 1) * 2)
        tc = float(sps.t.ppf(0.975, n - 1))
    except Exception:
        p = float("nan"); tc = float("nan")
    half = tc * s / n ** 0.5 if tc == tc else float("nan")
    return m, s, t, n - 1, p, m - half, m + half


def line(name, vals):
    m, s, t, df, p, lo, hi = paired(vals)
    per = " ".join(f"{v:+8.3f}" for v in vals)
    print(f"  {name:44s} {per}  | mean {m:+8.3f}  sd {s:6.3f}  "
          f"t {t:+8.3f}  df {df}  p {p:.6f}  CI [{lo:+.3f},{hi:+.3f}]")
    return m


# ------------------------------------------------------------------- main
def main():
    print("=" * 118)
    print("INDEPENDENT RE-DERIVATION of e3_decomposition (pandas; no _loader import)")
    print("sign: GOVERNED minus UNGOVERNED; negative = governance lowered the rate")
    print("=" * 118)

    inv = {}
    for lab, pre in MODELS:
        sm = seed_map(pre)
        inv[lab] = sm
        print(f"{lab:16s} gov {sm['gov']}  ung {sm['ung']}  "
              f"balanced={sm['gov'] == sm['ung']}")
    print()

    for lab, pre in MODELS:
        sm = inv[lab]
        paired_seeds = sorted(set(sm["gov"]) & set(sm["ung"]))
        bal = sm["gov"] == sm["ung"]
        print("-" * 118)
        print(f"MODEL {lab}   paired seeds {paired_seeds}   balanced={bal}"
              + ("" if bal else "   <-- NO PAIRED TEST REPORTED"))
        ibr_g, ibr_u, pubgap, tot, comp, behv, comp5, tot5 = ([] for _ in range(8))
        etot, ecomp = [], []
        rowcounts = set()
        for s in paired_seeds:
            dg, du = load(pre, "gov", s), load(pre, "ung", s)
            rowcounts.add((len(dg), len(du)))
            # published conditional statistic, computed directly, no strata machinery
            hg, hu = dg[dg._hi], du[du._hi]
            ig = 100.0 * hg._inc.mean()
            iu = 100.0 * hu._inc.mean()
            ibr_g.append(ig); ibr_u.append(iu); pubgap.append(ig - iu)
            k2 = kitagawa(dg, du, "_s2")
            tot.append(100 * k2["total"]); comp.append(100 * k2["comp_sym"])
            behv.append(100 * k2["behv_sym"])
            # 5+1 strata
            for d in (dg, du):
                d["_s5"] = d["_wsa"].where(d["_wsa"].isin(["VL", "L", "M", "H", "VH"]),
                                           "UNPARSED")
            k5 = kitagawa(dg, du, "_s5")
            tot5.append(100 * k5["total"]); comp5.append(100 * k5["comp_sym"])
            # identity check
            for k in (k2, k5):
                assert abs((k["comp_sym"] + k["behv_sym"] - k["total"]) * 100) < 1e-10
                assert abs((k["comp_u"] + k["behv_u"] + k["inter"] - k["total"]) * 100) < 1e-10
                assert abs((k["comp_g"] + k["behv_g"] - k["total"]) * 100) < 1e-10
            # executed variant
            eg = load_exec(pre, "gov", s, dg)
            eu = load_exec(pre, "ung", s, du)
            ke = kitagawa(eg, eu, "_s2")
            etot.append(100 * ke["total"]); ecomp.append(100 * ke["comp_sym"])
        print(f"  row counts (gov,ung) per seed: {sorted(rowcounts)}")
        if not bal:
            print("  descriptive only:")
            for s, a, b, c, d in zip(paired_seeds, pubgap, tot, comp, behv):
                print(f"    seed {s}: pub gap {a:+7.2f}  R gap {b:+7.2f}  "
                      f"comp {c:+7.2f}  behv {d:+7.2f}")
            print()
            continue
        line("published conditional gap IBR_g - IBR_u", pubgap)
        line("design-fixed gap  R_g - R_u (2 strata)", tot)
        line("COMPOSITION (symmetric, 2 strata)", comp)
        line("BEHAVIOUR   (symmetric, 2 strata)", behv)
        line("COMPOSITION (symmetric, 5+1 strata)", comp5)
        line("EXECUTED-action total gap", etot)
        line("EXECUTED-action composition", ecomp)
        # THE TEST THE ORIGINAL DOES NOT RUN: does conditioning inflate the headline?
        infl = [abs(p) - abs(t) for p, t in zip(pubgap, tot)]
        line("|published gap| - |design-fixed gap|  (>0 = conditioning INFLATES)", infl)
        mt, mp = sum(tot) / len(tot), sum(pubgap) / len(pubgap)
        print(f"  retained |Rgap|/|pub| = {100*abs(mt)/abs(mp):.1f}%   "
              f"composition share of R gap = "
              + (f"{100*(sum(comp)/len(comp))/mt:.1f}%" if abs(mt) >= 1.0 else "n/a (gap~0)"))
        print()

    # ---- what does a "seed" actually vary?  (relevant to the inferential unit)
    print("=" * 118)
    print("WHAT THE SEED REPLICATE ACTUALLY VARIES (checks the inferential unit)")
    print("=" * 118)
    base = None
    for s in inv["gemma3:4b"]["gov"]:
        d = load("", "gov", s)[["agent_id", "water_right", "cluster", "basin",
                                "has_efficient_system"]].drop_duplicates()
        d = d.sort_values("agent_id").reset_index(drop=True)
        if base is None:
            base = d
            print(f"  seed {s}: reference agent-attribute table ({len(d)} agents)")
        else:
            same = base.equals(d)
            print(f"  seed {s}: agent attribute table identical to seed "
                  f"{inv['gemma3:4b']['gov'][0]}? {same}")
    y1 = {}
    for s in inv["gemma3:4b"]["gov"]:
        d = load("", "gov", s)
        y1[s] = sorted(d[d.year == "1"]["drought_index"].unique())
    print(f"  year-1 drought_index by seed: {y1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
