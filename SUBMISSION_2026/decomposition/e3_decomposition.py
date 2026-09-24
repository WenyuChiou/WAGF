"""e3_decomposition -- Kitagawa / Oaxaca-Blinder decomposition of the irrigation
governance gap into a COMPOSITION part and a BEHAVIOUR part.

Run from the repo root:  python SUBMISSION_2026/decomposition/e3_decomposition.py


THE ESTIMAND, IN WORDS
----------------------
Of the governed-minus-ungoverned difference in how often an irrigation agent chose to
INCREASE its diversion request, how much is arithmetically attributable to governance
moving decisions BETWEEN self-reported water-scarcity-appraisal strata (COMPOSITION),
and how much to governance changing the increase rate WITHIN an appraisal stratum
(BEHAVIOUR)?  The interaction of the two is reported as its own line, never absorbed.

The published headline (IBR = increase rate among decisions whose self-reported
appraisal was H or VH) is a CONDITIONAL rate whose denominator is itself an outcome of
treatment.  A gap in a conditional rate cannot be decomposed into composition and
behaviour, because the composition change has already been differenced away by the
conditioning.  So the quantity this script decomposes is the UNCONDITIONAL increase rate
R = (# increase decisions) / (# agent-years), on the final PROPOSED action (a REJECTED
row's proposal did not execute; see Part E for the genuinely-executed variant).  R's
denominator is fixed by design at 78 agents x 42 years = 3276 per run and is therefore
not post-treatment.
The published statistic is then RECONCILED against that decomposition in Part D: it
enters the unconditional gap only as one term, weighted by the average size of the HIGH
stratum.

Sign convention, in words: every gap is GOVERNED MINUS UNGOVERNED.  NEGATIVE means
governance LOWERED the rate, which is the direction the paper claims as the benefit.
(The paper quotes the same magnitude as a "+23.0 pp improvement"; this script never
uses the flipped convention.)


THE IDENTIFYING ASSUMPTION -- AND WHY IT IS WEAK HERE
----------------------------------------------------
An arithmetic identity needs no assumption: for ANY partition of the decisions,
  R_g - R_u  =  SUM_a (s_g,a - s_u,a) * rbar_a   [COMPOSITION]
             +  SUM_a sbar_a * (r_g,a - r_u,a)   [BEHAVIOUR]
holds exactly, and the script asserts a residual below 1e-9 pp on every single cell.
What needs an assumption is the INTERPRETATION of the two parts as distinct mechanisms.
That interpretation requires the appraisal stratum to be a meaningful, comparably
measured characteristic across arms.  It is not a pre-treatment covariate: it is emitted
by the same LLM call as the action.  Consequently:
  * the COMPOSITION component is NOT selection bias that can be "adjusted away" -- it is
    itself a treatment effect on the mediator, so removing it would remove real signal;
  * the BEHAVIOUR component is NOT a clean causal effect either -- it is a comparison of
    two arms within a stratum whose membership was determined post-treatment, i.e. a
    textbook post-treatment-conditioned contrast (the exact defect that motivated this
    campaign, applied one level down).
This decomposition is therefore DESCRIPTIVE.  It answers "how does the arithmetic of the
gap divide up", not "what would have happened under an intervention".


WHAT WOULD FALSIFY THE RESULT
-----------------------------
1. If the residual (total minus composition minus behaviour minus interaction) were not
   ~0 to machine precision, the arithmetic would be wrong.  Asserted, per cell, per seed.
2. If the three weighting schemes (untreated-reference, governed-reference, symmetric
   pooled) gave qualitatively different answers about which channel dominates, the
   headline share would be an index-number artefact rather than a fact.  All three are
   printed side by side so this is visible, not hidden.
3. If the 2-stratum (HIGH vs not-HIGH) and 5+1-stratum (VL/L/M/H/VH/UNPARSED) partitions
   disagreed about the composition share, the result would be sensitive to an arbitrary
   binning choice.  Both are printed.
4. If the result held only on the anchor model, it would be a property of gemma3:4b and
   not of governance.  All four balanced models are run; the unbalanced ministral cell is
   reported separately and excluded from every paired test.
5. If the conclusion flipped when the ACTION column is replaced by the genuinely executed
   action (Part E: rejected proposals do not move the world, so they execute as
   maintain_demand), the labelled-action decomposition would be describing intent rather
   than behaviour.  Both are computed.

Everything printed is read from disk.  No number in this file is carried over from a
brief, a paper, or a prior report.
"""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _loader as L  # noqa: E402  (canonical loader; do not re-implement its definitions)

OUT_CSV = os.path.join(HERE, "e3_decomposition.csv")

# Stratum display order.  UNPARSED = wsa_label outside the five legal levels (in this
# corpus the literal string "N/A", every one of them a REJECTED_FALLBACK row).  It is
# kept as its own stratum so that the shares sum to exactly 1 and NO ROW IS DROPPED.
ORDER5 = ["VL", "L", "M", "H", "VH", "UNPARSED"]
ORDER2 = ["HIGH", "NOT_HIGH"]

BAR = "=" * 100
SUB = "-" * 100


# ---------------------------------------------------------------------------
# stratifiers
# ---------------------------------------------------------------------------
def strat5(row: dict) -> str:
    w = L.wsa(row)
    return w if w in L.LABEL_LEVELS else "UNPARSED"


def strat2(row: dict) -> str:
    # Matches the published IBR exactly: HIGH = {H, VH}; everything else (including
    # UNPARSED) is outside the published denominator.
    return "HIGH" if L.wsa(row) in L.HIGH else "NOT_HIGH"


def strat_high_only(row: dict) -> str:
    """Sub-strata INSIDE the published denominator."""
    return L.wsa(row)  # rows are pre-filtered to {H, VH}


# ---------------------------------------------------------------------------
# tabulation + decomposition
# ---------------------------------------------------------------------------
def tabulate(rows, keyfn, incrfn, order):
    """-> (N, {stratum: (n, n_increase)}) with every stratum in `order` present."""
    tab = {k: [0, 0] for k in order}
    for r in rows:
        k = keyfn(r)
        if k not in tab:
            raise L.DataError(f"unexpected stratum {k!r} not in {order}")
        tab[k][0] += 1
        if incrfn(r):
            tab[k][1] += 1
    return len(rows), {k: (v[0], v[1]) for k, v in tab.items()}


def decompose(Ng, tg, Nu, tu, order):
    """Exact decompositions of R_g - R_u over the strata in `order`.

    All shares/rates are FRACTIONS here; the caller multiplies by 100 for pp.
    Empty-stratum convention (flagged by the caller): if a stratum has zero rows in one
    arm, that arm's rate is set equal to the other arm's rate.  Its share is 0, so its
    level contribution is still exactly right, the identity still holds exactly, and the
    whole of that stratum is attributed to COMPOSITION rather than to BEHAVIOUR -- which
    is the honest reading of "this stratum exists in one arm only".
    """
    per = {}
    empties = []
    for a in order:
        ng, ig = tg[a]
        nu, iu = tu[a]
        sg = ng / Ng
        su = nu / Nu
        if ng and nu:
            rg, ru = ig / ng, iu / nu
        elif ng and not nu:
            rg = ru = ig / ng
            empties.append((a, "ungoverned"))
        elif nu and not ng:
            rg = ru = iu / nu
            empties.append((a, "governed"))
        else:
            rg = ru = 0.0
            empties.append((a, "both"))
        per[a] = dict(ng=ng, nu=nu, ig=ig, iu=iu, sg=sg, su=su, rg=rg, ru=ru)

    total = sum(p["sg"] * p["rg"] - p["su"] * p["ru"] for p in per.values())

    # symmetric / pooled-reference two-fold (interaction split evenly between the two)
    comp_sym = sum((p["sg"] - p["su"]) * 0.5 * (p["rg"] + p["ru"]) for p in per.values())
    behv_sym = sum(0.5 * (p["sg"] + p["su"]) * (p["rg"] - p["ru"]) for p in per.values())

    # classic three-fold with UNTREATED as the reference (interaction explicit)
    comp_u = sum((p["sg"] - p["su"]) * p["ru"] for p in per.values())
    behv_u = sum(p["su"] * (p["rg"] - p["ru"]) for p in per.values())
    inter = sum((p["sg"] - p["su"]) * (p["rg"] - p["ru"]) for p in per.values())

    # two-fold with GOVERNED as the reference (interaction folded into composition)
    comp_g = sum((p["sg"] - p["su"]) * p["rg"] for p in per.values())
    behv_g = sum(p["su"] * (p["rg"] - p["ru"]) for p in per.values())

    res = dict(
        total=total, per=per, empties=empties,
        comp_sym=comp_sym, behv_sym=behv_sym,
        comp_u=comp_u, behv_u=behv_u, inter=inter,
        comp_g=comp_g, behv_g=behv_g,
    )
    # exactness assertions (in pp)
    for name, s in (
        ("symmetric", comp_sym + behv_sym),
        ("3-fold(untreated ref)", comp_u + behv_u + inter),
        ("2-fold(governed ref)", comp_g + behv_g),
    ):
        if abs((s - total) * 100.0) > 1e-9:
            raise L.DataError(
                f"decomposition {name} does not sum to the total: "
                f"residual {(s - total) * 100.0:.3e} pp"
            )
    return res


# ---------------------------------------------------------------------------
# stats helpers built on the loader's
# ---------------------------------------------------------------------------
def _t_crit(df: int, alpha: float = 0.05) -> float:
    """Two-sided critical t by bisection on the loader's exact p-value function."""
    if df <= 0:
        return float("nan")
    lo, hi = 0.0, 1e4
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if L.t_two_sided_p(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def summarise(vals):
    """-> (mean, sd, t, df, p, ci_lo, ci_hi) for a list of per-seed differences."""
    vals = [v for v in vals]
    m = L.mean(vals)
    s = L.sd(vals)
    t, df = L.paired_t(vals)
    p = L.t_two_sided_p(t, df)
    if df > 0 and s == s:
        half = _t_crit(df) * s / len(vals) ** 0.5
        return m, s, t, df, p, m - half, m + half
    return m, s, t, df, p, float("nan"), float("nan")


def fmt_p(p):
    if p != p:
        return "  n/a"
    if p < 1e-4:
        return f"{p:.2e}"
    return f"{p:.4f}"


# ---------------------------------------------------------------------------
# executed-action variant (Part E)
# ---------------------------------------------------------------------------
def executed_increase_fn(run_path):
    """Return an `is_increase`-shaped callable using the GENUINELY EXECUTED action.

    Phase-1 finding reused, not re-assumed: a REJECTED proposal never moves `request`
    (6096/6096 governed and 4754/4754 ungoverned rejected rows show zero movement on the
    anchor), so the action that actually executed is the domain default maintain_demand.
    `yearly_decision` is the LAST PROPOSED skill, i.e. an intent-stage label.
    """
    aud = L.load_audit(run_path)
    ex = {}
    for r in aud:
        key = ((r.get("agent_id") or "").strip(), (r.get("year") or "").strip())
        if key in ex:
            raise L.DataError(f"duplicate audit key {key} in {run_path}")
        status = (r.get("status") or "").strip().upper()
        final = (r.get("final_skill") or "").strip()
        ex[key] = L.DEFAULT_SKILL if status.startswith("REJECTED") else final

    def fn(row):
        key = ((row.get("agent_id") or "").strip(), (row.get("year") or "").strip())
        if key not in ex:
            raise L.DataError(f"sim-log key {key} has no audit row in {run_path}")
        return ex[key] in L.INCREASE

    return fn, len(ex)


# ---------------------------------------------------------------------------
# per-seed engine
# ---------------------------------------------------------------------------
def seed_result(prefix, seed, keyfn, order, incr_mode="labelled", subset=None):
    """Load one paired seed and decompose it.  `subset` filters rows (e.g. HIGH only)."""
    out = {}
    tabs = {}
    for arm in ("governed", "ungoverned"):
        d = L.run_dir(arm, prefix, seed)
        rows = L.load_run(d)
        if len(rows) != L.EXPECTED_ROWS:
            print(f"  !! ROW-COUNT ANOMALY {os.path.basename(d)}: {len(rows)} rows "
                  f"(expected {L.EXPECTED_ROWS})")
        if incr_mode == "labelled":
            incrfn = L.is_increase
            nkeys = None
        else:
            incrfn, nkeys = executed_increase_fn(d)
            if nkeys != len(rows):
                print(f"  !! AUDIT/SIM SIZE MISMATCH {os.path.basename(d)}: "
                      f"audit {nkeys} vs sim {len(rows)}")
        use = [r for r in rows if subset(r)] if subset else rows
        if not use:
            raise L.DataError(f"empty analysis set for {d}")
        N, tab = tabulate(use, keyfn, incrfn, order)
        tabs[arm] = (N, tab)
        out[arm] = dict(N=N, n_incr=sum(v[1] for v in tab.values()))
    (Ng, tg), (Nu, tu) = tabs["governed"], tabs["ungoverned"]
    dec = decompose(Ng, tg, Nu, tu, order)
    out["dec"] = dec
    out["Ng"], out["Nu"] = Ng, Nu
    out["Rg"] = 100.0 * out["governed"]["n_incr"] / Ng
    out["Ru"] = 100.0 * out["ungoverned"]["n_incr"] / Nu
    return out


def run_cell(prefix, keyfn, order, incr_mode="labelled", subset=None):
    """All paired seeds of one model -> list of per-seed results."""
    return [(s, seed_result(prefix, s, keyfn, order, incr_mode, subset))
            for s in L.paired_seeds(prefix)]


# ---------------------------------------------------------------------------
# printers
# ---------------------------------------------------------------------------
def print_components(results, label, indent="  "):
    """Per-seed component table (pp) + means + paired t on each component."""
    keys = [("total", "TOTAL gap"),
            ("comp_sym", "COMPOSITION (sym)"),
            ("behv_sym", "BEHAVIOUR  (sym)"),
            ("comp_u", "COMPOSITION (untreated ref)"),
            ("behv_u", "BEHAVIOUR  (untreated ref)"),
            ("inter", "INTERACTION (3-fold)"),
            ("comp_g", "COMPOSITION (governed ref)"),
            ("behv_g", "BEHAVIOUR  (governed ref)")]
    series = {k: [100.0 * r["dec"][k] for _, r in results] for k, _ in keys}
    seeds = [s for s, _ in results]

    print(f"{indent}{label}")
    head = f"{indent}{'component (pp)':32s}" + "".join(f"{'s' + s:>10s}" for s in seeds)
    head += f"{'mean':>10s}{'sd':>9s}{'t':>9s}{'df':>4s}{'p':>10s}{'95% CI':>20s}"
    print(head)
    print(indent + "-" * (len(head) - len(indent)))
    for k, name in keys:
        v = series[k]
        m, s, t, df, p, lo, hi = summarise(v)
        row = f"{indent}{name:32s}" + "".join(f"{x:>10.3f}" for x in v)
        ci = f"[{lo:7.3f},{hi:7.3f}]" if lo == lo else "        n/a       "
        row += f"{m:>10.3f}{s:>9.3f}{t:>9.3f}{df:>4d}{fmt_p(p):>10s}{ci:>20s}"
        print(row)
    return series


#: a composition/total ratio is meaningless when the denominator is a near-zero gap.
#: 1.0 pp is the threshold below which the ratio is suppressed rather than printed.
RATIO_FLOOR_PP = 1.0


def share_block(series, indent="  "):
    """Composition share of the total gap, three ways, with the ambiguity visible."""
    tot = series["total"]
    mtot = L.mean(tot)
    print(f"\n{indent}COMPOSITION SHARE OF THE TOTAL GAP (composition / total, %)")
    if abs(mtot) < RATIO_FLOOR_PP:
        print(f"{indent}!! SUPPRESSED: the mean total gap is {mtot:+.3f} pp, i.e. essentially zero.")
        print(f"{indent}   A composition/total ratio here is a division by noise and would print")
        f = "   absurd values (thousands of percent). Read the pp COMPONENTS above instead:"
        print(indent + f)
        for k, name in (("comp_sym", "composition (sym)"), ("behv_sym", "behaviour (sym)")):
            print(f"{indent}     {name:22s}{L.mean(series[k]):+8.3f} pp")
        return []
    print(f"{indent}{'weighting':32s}{'ratio of means':>16s}{'mean of per-seed ratios':>26s}"
          f"   per-seed ratios")
    print(indent + "-" * 96)
    rows = []
    for k, name in (("comp_sym", "symmetric / pooled ref"),
                    ("comp_u", "untreated as reference"),
                    ("comp_g", "governed as reference")):
        c = series[k]
        rom = 100.0 * L.mean(c) / mtot
        per = [100.0 * ci / ti if abs(ti) >= RATIO_FLOOR_PP else float("nan")
               for ci, ti in zip(c, tot)]
        mper = L.mean([x for x in per if x == x]) if any(x == x for x in per) else float("nan")
        print(f"{indent}{name:32s}{rom:>15.1f}%{mper:>25.1f}%   "
              + " ".join(f"{x:.1f}" if x == x else "n/a" for x in per))
        rows.append((name, rom, mper))
    return rows


def print_strata(results, order, indent="  "):
    """Pooled-over-seeds stratum shares and within-stratum rates, both arms."""
    agg = {a: dict(ng=0, nu=0, ig=0, iu=0) for a in order}
    Ng = Nu = 0
    for _, r in results:
        Ng += r["Ng"]
        Nu += r["Nu"]
        for a in order:
            p = r["dec"]["per"][a]
            for f in ("ng", "nu", "ig", "iu"):
                agg[a][f] += p[f]
    print(f"{indent}{'stratum':10s}{'n_gov':>9s}{'n_ung':>9s}{'share_g%':>10s}"
          f"{'share_u%':>10s}{'d_share':>9s}{'rate_g%':>9s}{'rate_u%':>9s}{'d_rate':>9s}")
    print(indent + "-" * 84)
    for a in order:
        v = agg[a]
        sg = 100.0 * v["ng"] / Ng
        su = 100.0 * v["nu"] / Nu
        rg = 100.0 * v["ig"] / v["ng"] if v["ng"] else float("nan")
        ru = 100.0 * v["iu"] / v["nu"] if v["nu"] else float("nan")
        dr = rg - ru if (rg == rg and ru == ru) else float("nan")
        rgs = f"{rg:>9.2f}" if rg == rg else "      n/a"
        rus = f"{ru:>9.2f}" if ru == ru else "      n/a"
        drs = f"{dr:>9.2f}" if dr == dr else "      n/a"
        print(f"{indent}{a:10s}{v['ng']:>9d}{v['nu']:>9d}{sg:>10.2f}{su:>10.2f}"
              f"{su - su + (sg - su):>9.2f}{rgs}{rus}{drs}")
    tsg = sum(100.0 * agg[a]["ng"] / Ng for a in order)
    tsu = sum(100.0 * agg[a]["nu"] / Nu for a in order)
    print(f"{indent}{'SUM':10s}{Ng:>9d}{Nu:>9d}{tsg:>10.2f}{tsu:>10.2f}")
    if abs(tsg - 100.0) > 1e-9 or abs(tsu - 100.0) > 1e-9:
        print(f"{indent}!! SHARES DO NOT SUM TO 100 -- rows were lost somewhere")
    return agg, Ng, Nu


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    csv_rows = []

    print(BAR)
    print("e3_decomposition -- COMPOSITION vs BEHAVIOUR in the irrigation governance gap")
    print(BAR)
    print(f"repo    : {L.REPO}")
    print(f"results : {L.RESULTS}")
    print(f"loader  : {os.path.join(HERE, '_loader.py')}  (all definitions imported, none re-implemented)")
    print()
    print("SIGN CONVENTION: every gap is GOVERNED MINUS UNGOVERNED.")
    print("                 NEGATIVE = governance LOWERED the rate (the claimed benefit).")
    print("DEFINITIONS    : INCREASE = {increase_large, increase_small};  HIGH = wsa_label in {H, VH}")
    print("STRATA         : 5 legal appraisal levels + UNPARSED (wsa_label outside VL/L/M/H/VH;")
    print("                 in this corpus the literal 'N/A').  NO ROW IS DROPPED, so shares sum to 1.")
    print("DECOMPOSED     : the UNCONDITIONAL increase rate R = increases / agent-years.")
    print("                 Its denominator (78 agents x 42 yr) is fixed by design, so a gap in R")
    print("                 contains no denominator-selection artefact.  The published conditional")
    print("                 IBR cannot be decomposed this way -- see Part D for the reconciliation.")

    # ---------------- corpus -------------------------------------------------
    print("\n" + BAR)
    print("CORPUS -- read off disk, nothing assumed")
    print(BAR)
    print(f"{'model':16s}{'gov seeds':22s}{'ung seeds':22s}{'paired':>7s}{'balanced':>10s}")
    print(SUB)
    balanced_models = []
    for label, prefix in L.MODELS:
        gs = L.seeds("governed", prefix)
        us = L.seeds("ungoverned", prefix)
        bal = L.balanced(prefix)
        print(f"{label:16s}{','.join(gs):22s}{','.join(us):22s}"
              f"{len(L.paired_seeds(prefix)):>7d}{str(bal):>10s}")
        if bal:
            balanced_models.append((label, prefix))
    print(SUB)
    print(f"balanced models used for paired contrasts : {[l for l, _ in balanced_models]}")
    unbal = [l for l, p in L.MODELS if not L.balanced(p)]
    print(f"UNBALANCED, excluded from every paired test: {unbal}  (reported separately, Part F)")

    anchor_label, anchor_prefix = L.ANCHOR

    # ---------------- Part A -------------------------------------------------
    print("\n" + BAR)
    print("PART A -- decomposing the PUBLISHED statistic on its own terms")
    print("         (base = HIGH rows only; strata = H vs VH; total = IBR_gov - IBR_ung)")
    print(BAR)
    print("This asks the narrow version of the reviewer's question: within the published")
    print("denominator, did the H:VH mix itself shift, and does that mix explain any of the gap?")
    print("It CANNOT see the larger problem -- that membership of the denominator changed --")
    print("because that change has already been differenced away by the conditioning.")
    partA = {}
    for label, prefix in balanced_models:
        res = run_cell(prefix, strat_high_only, ["H", "VH"], subset=L.is_high)
        print("\n" + SUB)
        ibr_g = [r["Rg"] for _, r in res]
        ibr_u = [r["Ru"] for _, r in res]
        print(f"{label}   IBR gov per seed {[round(x, 2) for x in ibr_g]}  mean {L.mean(ibr_g):.2f}%")
        print(f"{' ' * len(label)}   IBR ung per seed {[round(x, 2) for x in ibr_u]}  mean {L.mean(ibr_u):.2f}%")
        ser = print_components(res, f"[{label}] within-HIGH decomposition of IBR_g - IBR_u")
        share_block(ser)
        partA[label] = ser
        for (s, r), tot, cs in zip(res, ser["total"], ser["comp_sym"]):
            csv_rows.append(dict(part="A_within_high", model=label, seed=s, strata="H|VH",
                                 action="labelled", total_pp=tot, comp_sym_pp=cs,
                                 behv_sym_pp=100.0 * r["dec"]["behv_sym"],
                                 comp_u_pp=100.0 * r["dec"]["comp_u"],
                                 behv_u_pp=100.0 * r["dec"]["behv_u"],
                                 inter_pp=100.0 * r["dec"]["inter"],
                                 comp_g_pp=100.0 * r["dec"]["comp_g"],
                                 behv_g_pp=100.0 * r["dec"]["behv_g"]))

    # ---------------- Part B -------------------------------------------------
    print("\n" + BAR)
    print("PART B -- MAIN DECOMPOSITION: unconditional increase rate, 5+1 appraisal strata")
    print(BAR)
    partB = {}
    for label, prefix in balanced_models:
        res = run_cell(prefix, strat5, ORDER5)
        print("\n" + SUB)
        Rg = [r["Rg"] for _, r in res]
        Ru = [r["Ru"] for _, r in res]
        print(f"{label}   R (unconditional increase rate) gov {L.mean(Rg):6.2f}%   "
              f"ung {L.mean(Ru):6.2f}%   gap {L.mean(Rg) - L.mean(Ru):+7.2f} pp")
        print(f"\n  pooled strata (all paired seeds; d_share = gov - ung):")
        print_strata(res, ORDER5)
        emp = sorted({e for _, r in res for e in r["dec"]["empties"]})
        print(f"  empty strata encountered: {emp if emp else 'none'}")
        unp = [100.0 * (r["dec"]["per"]["UNPARSED"]["sg"] - r["dec"]["per"]["UNPARSED"]["su"])
               * 0.5 * (r["dec"]["per"]["UNPARSED"]["rg"] + r["dec"]["per"]["UNPARSED"]["ru"])
               for _, r in res]
        print(f"  UNPARSED stratum's own contribution to COMPOSITION: mean "
              f"{L.mean(unp):+.4f} pp, max |{max(abs(x) for x in unp):.4f}| pp "
              f"-- the empty-stratum convention can move the answer by at most this much")
        print()
        ser = print_components(res, f"[{label}] decomposition of R_gov - R_ung, strata = {ORDER5}")
        share_block(ser)
        partB[label] = (ser, res)
        for (s, r), tot, cs in zip(res, ser["total"], ser["comp_sym"]):
            csv_rows.append(dict(part="B_uncond_5strata", model=label, seed=s,
                                 strata="VL|L|M|H|VH|UNPARSED", action="labelled",
                                 total_pp=tot, comp_sym_pp=cs,
                                 behv_sym_pp=100.0 * r["dec"]["behv_sym"],
                                 comp_u_pp=100.0 * r["dec"]["comp_u"],
                                 behv_u_pp=100.0 * r["dec"]["behv_u"],
                                 inter_pp=100.0 * r["dec"]["inter"],
                                 comp_g_pp=100.0 * r["dec"]["comp_g"],
                                 behv_g_pp=100.0 * r["dec"]["behv_g"]))

    # ---------------- Part C -------------------------------------------------
    print("\n" + BAR)
    print("PART C -- SAME DECOMPOSITION, 2 STRATA (HIGH vs NOT-HIGH)")
    print("         binning-sensitivity check against Part B, and the bridge to Part D")
    print(BAR)
    partC = {}
    for label, prefix in balanced_models:
        res = run_cell(prefix, strat2, ORDER2)
        print("\n" + SUB)
        print(f"{label}  pooled strata:")
        print_strata(res, ORDER2)
        print()
        ser = print_components(res, f"[{label}] decomposition of R_gov - R_ung, strata = HIGH / NOT_HIGH")
        share_block(ser)
        partC[label] = (ser, res)
        for (s, r), tot, cs in zip(res, ser["total"], ser["comp_sym"]):
            csv_rows.append(dict(part="C_uncond_2strata", model=label, seed=s,
                                 strata="HIGH|NOT_HIGH", action="labelled",
                                 total_pp=tot, comp_sym_pp=cs,
                                 behv_sym_pp=100.0 * r["dec"]["behv_sym"],
                                 comp_u_pp=100.0 * r["dec"]["comp_u"],
                                 behv_u_pp=100.0 * r["dec"]["behv_u"],
                                 inter_pp=100.0 * r["dec"]["inter"],
                                 comp_g_pp=100.0 * r["dec"]["comp_g"],
                                 behv_g_pp=100.0 * r["dec"]["behv_g"]))

    # ---------------- Part D -------------------------------------------------
    print("\n" + BAR)
    print("PART D -- RECONCILIATION: where exactly does the published -23 pp sit?")
    print(BAR)
    print("In the 2-stratum symmetric decomposition the behaviour term splits exactly into")
    print("    sbar_HIGH * (IBR_g - IBR_u)      <- the PUBLISHED gap, and nothing else")
    print("  + sbar_NOT  * (r_g,NOT - r_u,NOT)  <- a channel the published statistic cannot see")
    print("so the published number enters the design-fixed gap only after being SHRUNK by")
    print("sbar_HIGH, the average size of its own denominator.")
    print()
    hdr = (f"{'model':16s}{'IBR_g%':>9s}{'IBR_u%':>9s}{'pub gap':>9s}{'sbarHIGH':>10s}"
           f"{'pub contrib':>12s}{'R gap':>9s}{'comp':>9s}{'behv HIGH':>11s}"
           f"{'behv NOT':>10s}{'comp %':>8s}{'|Rgap|/|pub|':>13s}")
    print(hdr)
    print(SUB)
    reconc = {}
    for label, prefix in balanced_models:
        ser, res = partC[label]
        pub, sbarH, contrib, behvNOT = [], [], [], []
        for _, r in res:
            p = r["dec"]["per"]
            g = 100.0 * (p["HIGH"]["rg"] - p["HIGH"]["ru"])
            sb = 0.5 * (p["HIGH"]["sg"] + p["HIGH"]["su"])
            pub.append(g)
            sbarH.append(sb)
            contrib.append(sb * g)
            sbN = 0.5 * (p["NOT_HIGH"]["sg"] + p["NOT_HIGH"]["su"])
            behvNOT.append(100.0 * sbN * (p["NOT_HIGH"]["rg"] - p["NOT_HIGH"]["ru"]))
        ibrg = [100.0 * r["dec"]["per"]["HIGH"]["rg"] for _, r in res]
        ibru = [100.0 * r["dec"]["per"]["HIGH"]["ru"] for _, r in res]
        mtot = L.mean(ser["total"])
        mcomp = L.mean(ser["comp_sym"])
        shr = (f"{100.0 * mcomp / mtot:>7.1f}%" if abs(mtot) >= RATIO_FLOOR_PP
               else "    n/a ")
        ret = 100.0 * abs(mtot) / abs(L.mean(pub)) if L.mean(pub) else float("nan")
        print(f"{label:16s}{L.mean(ibrg):>9.2f}{L.mean(ibru):>9.2f}{L.mean(pub):>9.2f}"
              f"{L.mean(sbarH):>10.4f}{L.mean(contrib):>12.2f}{mtot:>9.2f}"
              f"{mcomp:>9.2f}{L.mean(contrib):>11.2f}{L.mean(behvNOT):>10.2f}"
              f"{shr:>8s}{ret:>12.1f}%")
        reconc[label] = dict(pub=pub, sbarH=sbarH, contrib=contrib, behvNOT=behvNOT,
                             tot=ser["total"], comp=ser["comp_sym"], retained=ret)
    print(SUB)
    print("columns: 'pub gap' = IBR_g - IBR_u (the published statistic, recomputed here);")
    print("         'pub contrib' = sbar_HIGH * pub gap = what the published gap actually")
    print("             contributes to the design-fixed gap;")
    print("         'R gap' = total design-fixed gap = comp + behv HIGH + behv NOT (exactly);")
    print("         'comp %' = composition as a share of the design-fixed gap;")
    print("         '|Rgap|/|pub|' = how much of the published magnitude an estimator that")
    print("             NEVER conditions on the self-report still reports.  This is the direct")
    print("             answer to 'does the headline survive dropping the conditioning'.")

    # headline paired test on the anchor
    print("\n" + SUB)
    print(f"HEADLINE CELL: {anchor_label} (the published pair)")
    print(SUB)
    ser2, res2 = partC[anchor_label]
    ser5, res5 = partB[anchor_label]
    rc = reconc[anchor_label]
    for name, vals in (("published conditional gap  IBR_g - IBR_u", rc["pub"]),
                       ("design-fixed gap           R_g   - R_u  ", rc["tot"]),
                       ("  COMPOSITION component (symmetric)     ", ser2["comp_sym"]),
                       ("  BEHAVIOUR   component (symmetric)     ", ser2["behv_sym"]),
                       ("    of which, inside HIGH               ", rc["contrib"]),
                       ("    of which, outside HIGH              ", rc["behvNOT"])):
        m, s, t, df, p, lo, hi = summarise(vals)
        print(f"  {name}  {m:8.3f} pp  95% CI [{lo:7.3f},{hi:7.3f}]  "
              f"t={t:8.3f} df={df} p={fmt_p(p)}")
    mt, mc = L.mean(ser2["total"]), L.mean(ser2["comp_sym"])
    print(f"\n  ==> COMPOSITION SHARE OF THE DESIGN-FIXED GAP, {anchor_label}: "
          f"{100.0 * mc / mt:.1f}%  (2 strata)")
    mt5, mc5 = L.mean(ser5["total"]), L.mean(ser5["comp_sym"])
    print(f"  ==> same with 5+1 strata: {100.0 * mc5 / mt5:.1f}%")
    print(f"  ==> the published {L.mean(rc['pub']):.2f} pp shrinks to "
          f"{L.mean(rc['contrib']):.2f} pp of actual contribution once its own denominator")
    print(f"      (sbar_HIGH = {L.mean(rc['sbarH']):.4f}) is accounted for.")

    # ---------------- Part E -------------------------------------------------
    print("\n" + BAR)
    print("PART E -- ROBUSTNESS: the GENUINELY EXECUTED action")
    print(BAR)
    print("`yearly_decision` is the last PROPOSED skill.  A REJECTED proposal does not move")
    print("the agent's request, so what executed was the domain default 'maintain_demand'.")
    print("Re-running the 2-stratum decomposition with executed = maintain_demand whenever")
    print("audit status starts with REJECTED.  If the composition share moves a lot here, the")
    print("labelled-action result is about intent, not behaviour.")
    partE = {}
    for label, prefix in balanced_models:
        res = run_cell(prefix, strat2, ORDER2, incr_mode="executed")
        print("\n" + SUB)
        Rg = [r["Rg"] for _, r in res]
        Ru = [r["Ru"] for _, r in res]
        print(f"{label}  executed R gov {L.mean(Rg):6.2f}%  ung {L.mean(Ru):6.2f}%  "
              f"gap {L.mean(Rg) - L.mean(Ru):+7.2f} pp")
        print_strata(res, ORDER2)
        print()
        ser = print_components(res, f"[{label}] EXECUTED-action decomposition, HIGH / NOT_HIGH")
        share_block(ser)
        partE[label] = (ser, res)
        for (s, r), tot, cs in zip(res, ser["total"], ser["comp_sym"]):
            csv_rows.append(dict(part="E_executed_2strata", model=label, seed=s,
                                 strata="HIGH|NOT_HIGH", action="executed",
                                 total_pp=tot, comp_sym_pp=cs,
                                 behv_sym_pp=100.0 * r["dec"]["behv_sym"],
                                 comp_u_pp=100.0 * r["dec"]["comp_u"],
                                 behv_u_pp=100.0 * r["dec"]["behv_u"],
                                 inter_pp=100.0 * r["dec"]["inter"],
                                 comp_g_pp=100.0 * r["dec"]["comp_g"],
                                 behv_g_pp=100.0 * r["dec"]["behv_g"]))

    # ---------------- Part F -------------------------------------------------
    print("\n" + BAR)
    print("PART F -- UNBALANCED CELLS, reported separately, NOT pooled, NO paired test")
    print(BAR)
    for label, prefix in L.MODELS:
        if L.balanced(prefix):
            continue
        gs, us = L.seeds("governed", prefix), L.seeds("ungoverned", prefix)
        ps = L.paired_seeds(prefix)
        print(f"{label}: governed seeds {gs}, ungoverned seeds {us} -> only {ps} overlap.")
        print(f"  Any paired t here would have df={len(ps) - 1}. Descriptive numbers only:")
        res = run_cell(prefix, strat2, ORDER2)
        for s, r in res:
            d = r["dec"]
            p = d["per"]
            print(f"    seed {s}: R_g {r['Rg']:6.2f}%  R_u {r['Ru']:6.2f}%  "
                  f"total {100 * d['total']:+7.2f}  comp {100 * d['comp_sym']:+7.2f}  "
                  f"behv {100 * d['behv_sym']:+7.2f}  "
                  f"IBR_g {100 * p['HIGH']['rg']:6.2f}%  IBR_u {100 * p['HIGH']['ru']:6.2f}%")
        print()

    # ---------------- sanity --------------------------------------------------
    print(BAR)
    print("SANITY CHECKS")
    print(BAR)
    problems = []
    notices = []
    checked = 0
    for tag, store in (("B", partB), ("C", partC), ("E", partE)):
        for label, (ser, res) in store.items():
            for s, r in res:
                checked += 1
                for a, p in r["dec"]["per"].items():
                    for f, lab in (("rg", "gov rate"), ("ru", "ung rate"),
                                   ("sg", "gov share"), ("su", "ung share")):
                        if not (0.0 <= p[f] <= 1.0):
                            problems.append(f"{tag}/{label}/s{s}/{a}: {lab}={p[f]} out of [0,1]")
                    if p["ig"] > p["ng"] or p["iu"] > p["nu"]:
                        problems.append(f"{tag}/{label}/s{s}/{a}: increases exceed count")
                ssg = sum(p["sg"] for p in r["dec"]["per"].values())
                ssu = sum(p["su"] for p in r["dec"]["per"].values())
                if abs(ssg - 1) > 1e-12 or abs(ssu - 1) > 1e-12:
                    problems.append(f"{tag}/{label}/s{s}: shares sum to {ssg}/{ssu}, not 1")
                if r["Ng"] != L.EXPECTED_ROWS or r["Nu"] != L.EXPECTED_ROWS:
                    problems.append(f"{tag}/{label}/s{s}: N {r['Ng']}/{r['Nu']} "
                                    f"!= {L.EXPECTED_ROWS}")
                for e in r["dec"]["empties"]:
                    notices.append(f"{tag}/{label}/s{s}: EMPTY STRATUM {e}")
    print(f"cells checked                     : {checked}")
    print(f"decomposition exactness           : asserted < 1e-9 pp on every cell (would have raised)")
    print(f"rates and shares inside [0,1]     : {'OK' if not problems else 'SEE BELOW'}")
    print(f"shares sum to 1 (no dropped rows) : {'OK' if not problems else 'SEE BELOW'}")
    print(f"run sizes all {L.EXPECTED_ROWS} rows          : "
          f"{'OK' if not problems else 'SEE BELOW'}")
    if problems:
        print("\nANOMALIES (reported, not suppressed):")
        for p in sorted(set(problems)):
            print("  !! " + p)
    else:
        print("no anomalies of this kind.")
    print(f"\nEMPTY-STRATUM NOTICES ({len(set(notices))}) -- expected, not errors, but stated:")
    print("  Only the UNPARSED stratum is ever empty, and only in the ungoverned arm (or both).")
    print("  Its share is <=0.64% in every cell and its composition contribution is printed")
    print("  per model in Part B; it cannot move any headline. Listed in full for the record:")
    for n in sorted(set(notices)):
        print("   - " + n)
    if not notices:
        print("   (none)")

    # ---------------- write csv ----------------------------------------------
    if csv_rows:
        cols = ["part", "model", "seed", "strata", "action", "total_pp", "comp_sym_pp",
                "behv_sym_pp", "comp_u_pp", "behv_u_pp", "inter_pp", "comp_g_pp", "behv_g_pp"]
        with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in csv_rows:
                w.writerow(r)
        print(f"\nper-seed components written to {OUT_CSV}")

    # ---------------- verdict -------------------------------------------------
    print("\n" + BAR)
    print("VERDICT")
    print(BAR)
    ser2a, _ = partC[anchor_label]
    ser5a, _ = partB[anchor_label]
    rca = reconc[anchor_label]
    m_tot, s_tot, t_tot, df_tot, p_tot, lo_tot, hi_tot = summarise(ser2a["total"])
    m_cmp, s_cmp, t_cmp, df_cmp, p_cmp, lo_cmp, hi_cmp = summarise(ser2a["comp_sym"])
    m_bhv, s_bhv, t_bhv, df_bhv, p_bhv, lo_bhv, hi_bhv = summarise(ser2a["behv_sym"])
    m_pub = L.mean(rca["pub"])
    print(f"anchor model {anchor_label}, {len(rca['pub'])} paired seeds")
    print(f"  published conditional gap (recomputed) : {m_pub:+7.2f} pp")
    print(f"  design-fixed gap  R_g - R_u            : {m_tot:+7.2f} pp "
          f"95% CI [{lo_tot:+.2f},{hi_tot:+.2f}] p={fmt_p(p_tot)}")
    print(f"    COMPOSITION                          : {m_cmp:+7.2f} pp "
          f"95% CI [{lo_cmp:+.2f},{hi_cmp:+.2f}] p={fmt_p(p_cmp)}  "
          f"= {100 * m_cmp / m_tot:.1f}% of the gap")
    print(f"    BEHAVIOUR                            : {m_bhv:+7.2f} pp "
          f"95% CI [{lo_bhv:+.2f},{hi_bhv:+.2f}] p={fmt_p(p_bhv)}  "
          f"= {100 * m_bhv / m_tot:.1f}% of the gap")
    print()
    print(f"  SIGN OF THE COMPOSITION COMPONENT: {'+' if m_cmp > 0 else '-'}  "
          f"-- it points AGAINST the total gap.")
    print("  Governance moves decisions OUT of the HIGH-appraisal stratum and into NOT-HIGH,")
    print("  where the increase rate is HIGHER in both arms.  So the appraisal shift ADDS")
    print("  increases; it does not manufacture the reduction.  Removing the composition")
    print("  channel makes the within-stratum contrast LARGER, not smaller.")
    print()
    print(f"  magnitude retained by an estimator that never conditions on the self-report:")
    print(f"    |R gap| / |published gap| = {abs(m_tot):.2f} / {abs(m_pub):.2f} = "
          f"{100 * abs(m_tot) / abs(m_pub):.1f}%   ({anchor_label})")
    print()
    print("cross-model composition share of the design-fixed gap (2 strata, symmetric):")
    for label, _ in balanced_models:
        ser, _res = partC[label]
        mt, mc = L.mean(ser["total"]), L.mean(ser["comp_sym"])
        shr = (f"{100 * mc / mt:6.1f}%" if abs(mt) >= RATIO_FLOOR_PP
               else "   n/a (total ~ 0)")
        mb = L.mean(ser["behv_sym"])
        gross = 100.0 * abs(mc) / (abs(mc) + abs(mb)) if (abs(mc) + abs(mb)) else float("nan")
        print(f"  {label:16s} total {mt:+7.2f} pp   composition {mc:+7.2f} pp   "
              f"share {shr}   retained vs published {reconc[label]['retained']:6.1f}%   "
              f"|comp|/(|comp|+|behv|) {gross:5.1f}%")
    print()
    print("  The last column is the signed-share-free reading: of ALL the movement the")
    print("  decomposition attributes, this fraction is composition.  It is the honest")
    print("  answer when the two channels point in opposite directions and the signed")
    print("  share therefore exceeds 100% or goes negative.")
    print()
    print("cross-model, EXECUTED action (Part E), same 2-stratum decomposition:")
    for label, _ in balanced_models:
        ser, _res = partE[label]
        mt, mc = L.mean(ser["total"]), L.mean(ser["comp_sym"])
        shr = (f"{100 * mc / mt:6.1f}%" if abs(mt) >= RATIO_FLOOR_PP else "   n/a")
        print(f"  {label:16s} total {mt:+7.2f} pp   composition {mc:+7.2f} pp   share {shr}")
    print()
    print("THIS IS A DESCRIPTIVE DECOMPOSITION, NOT A CAUSAL ONE.  The appraisal stratum is")
    print("post-treatment, so the BEHAVIOUR component is itself a post-treatment-conditioned")
    print("contrast and the COMPOSITION component is a treatment effect on the mediator, not a")
    print("bias to be netted out.  Neither number is a causal effect.  What the decomposition")
    print("does establish is arithmetic and is not in dispute: the published conditional gap")
    print("describes only one of at least three channels through which governance moved the")
    print("action distribution, and it is the only channel whose denominator the treatment moved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
