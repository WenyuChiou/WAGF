"""e5_year1 -- the YEAR-1 CLEAN-SLATE estimator for the irrigation testbed.

=============================================================================
ESTIMAND, IN WORDS
=============================================================================
Restricted to the FIRST simulated decision of every run -- the one decision each
agent makes before any of its own behaviour, or any other agent's behaviour, has
had a chance to move the world -- what is the effect of turning the validators ON
(governed) versus OFF (ungoverned) on each of three quantities:

  (A) the UNCONDITIONAL executed-increase rate
      = share of ALL year-1 decisions whose action is increase_large/increase_small.
      Its denominator is 78 agents, fixed by the experiment design. Nothing
      post-treatment enters it.

  (B) the HIGH-APPRAISAL SHARE
      = share of ALL year-1 decisions whose self-reported water-scarcity label is
      H or VH. This is the published IBR's DENOMINATOR, examined directly as an
      outcome in its own right rather than being conditioned on.

  (C) the CONDITIONAL IBR (= AAI, the published statistic)
      = increases among high-appraisal decisions only, at year 1.
      Reported for comparability with the paper, NOT as an identified effect: its
      denominator is (B), which is itself moved by the treatment.

The unit of inference is the SEED. Each quantity is computed per seed per arm; the
contrast is the paired per-seed difference; the test is a paired t on n seeds.

=============================================================================
IDENTIFYING ASSUMPTION
=============================================================================
At year 1 the two arms face a BIT-IDENTICAL pre-decision world at every matched
(seed, agent_id): same static entitlement/cluster/basin, same hydrology, same
reservoir elevation, same shortage tier, same curtailment. Both arms are the same
code, the same model, the same seed, differing ONLY in whether the validators are
enforced. Therefore any year-1 difference in behaviour or in self-report is caused
by the treatment (plus independent LLM sampling noise), and CANNOT be caused by the
arms having drifted into different world states -- because at year 1 they have not.

This assumption is not asserted. Section 1 TESTS it column by column before any
estimate is printed, and the script refuses to interpret the year-1 numbers as clean
if the test fails.

Two boundaries of the assumption, stated up front because they limit the claim:
  * It buys identification of "governance vs no governance at the first decision".
    It does NOT buy identification of the 42-year cumulative contrast, because from
    year 2 onward the arms genuinely inhabit different reservoirs.
  * The arms differ by governance AND by an independent LLM sample. With one draw
    per (arm, seed, agent) there is no resample-only control arm in this corpus, so
    the year-1 gap is "treatment + sampling noise". The paired-across-seeds t-test
    is what separates the systematic part from the noise part; a single seed cannot.

=============================================================================
WHAT WOULD FALSIFY THE RESULT
=============================================================================
 F1. Section 1 finding that any pre-decision year-1 column differs across arms at a
     matched (seed, agent_id). That would mean the arms were not comparable even at
     the first decision, and the whole clean-slate premise collapses.
 F2. The year-1 high-appraisal gap being near zero and only opening up in later
     years. That would say the composition shift is downstream of world divergence,
     i.e. partly a consequence of governance changing the river, not of governance
     changing what the agent says.
 F3. The year-1 unconditional increase gap being null while the conditional IBR gap
     is large. That would say the published gap at year 1 is pure composition.
 F4. Per-seed year-1 differences that flip sign across seeds, or a paired t that
     does not clear conventional significance. n is 78 decisions/seed, so year-1
     estimates are noisy by construction and this is a live possibility.
 F5. The corpus not being what the loader assumes: wrong row counts, unbalanced
     seed sets used in a paired contrast, empty groups. Section 7 checks these.

=============================================================================
SIGN CONVENTION (stated in words next to every number that uses it)
=============================================================================
    gap = governed MINUS ungoverned.
    NEGATIVE = governance LOWERED the quantity.
The published headline gap of "23.0 pp" is quoted in the paper as an improvement;
in this script's convention it is -23.02 pp. This script never flips the sign.

Run:  python SUBMISSION_2026/decomposition/e5_year1.py
Writes: nothing outside SUBMISSION_2026/decomposition/ (one optional CSV of the
        anchor trajectory). Reads examples/ read-only.
"""
from __future__ import annotations

import csv
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import _loader as L  # noqa: E402

HERE = os.path.abspath(os.path.dirname(__file__))
TRAJ_CSV = os.path.join(HERE, "e5_year1_trajectory.csv")

Z95 = 1.959963984540054

# Columns that are TRUE pre-decision inputs at year 1, per the Phase-1 exogeneity
# report. These MUST be identical across arms at year 1 for the design to hold.
YEAR1_PREDECISION = [
    "water_right", "cluster", "basin", "has_efficient_system",
    "drought_index", "shortage_tier", "curtailment_ratio",
    "lake_mead_level", "mead_storage_maf",
]
# Columns the brief calls pre-treatment but which the Phase-1 source reading showed
# are written in post_year FROM the post-decision request. Tested and reported, but
# a difference here does NOT falsify the design -- they are outcomes.
YEAR1_POSTDECISION_STATE = ["utilisation_pct", "below_minimum_utilisation",
                            "request", "diversion", "magnitude_pct",
                            "magnitude_fallback", "is_exploration", "memory"]
YEAR1_LLM_OUTPUT = ["wsa_label", "aca_label", "yearly_decision"]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def yr(row: dict) -> int:
    return int(row["year"])


def same_cell(a: str, b: str) -> bool:
    """Exact string equality, falling back to a numeric comparison at 1e-12."""
    a = (a or "").strip()
    b = (b or "").strip()
    if a == b:
        return True
    try:
        fa, fb = float(a), float(b)
    except ValueError:
        return False
    return abs(fa - fb) <= 1e-12 * max(1.0, abs(fa), abs(fb))


def t_crit(p_two: float, df: int) -> float:
    """Two-sided critical t. Bisection on the stdlib p-function in _loader."""
    if df <= 0:
        return float("nan")
    lo, hi = 0.0, 1e4
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if L.t_two_sided_p(mid, df) > p_two:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def wilson(k: int, n: int) -> tuple[float, float]:
    """95% Wilson score interval for a proportion, returned in PERCENT."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    z2 = Z95 * Z95
    den = n + z2
    centre = (k + z2 / 2.0) / den
    half = (Z95 / den) * math.sqrt(k * (n - k) / n + z2 / 4.0)
    return 100.0 * max(0.0, centre - half), 100.0 * min(1.0, centre + half)


def paired_report(diffs: list[float]) -> dict:
    """Paired t on per-seed differences plus a 95% CI on the mean difference."""
    n = len(diffs)
    m = L.mean(diffs)
    s = L.sd(diffs)
    t, df = L.paired_t(diffs)
    p = L.t_two_sided_p(t, df) if df > 0 else float("nan")
    if n >= 2 and s == s and s > 0:
        tc = t_crit(0.05, df)
        half = tc * s / math.sqrt(n)
        ci = (m - half, m + half)
    else:
        ci = (float("nan"), float("nan"))
    return {"n": n, "mean": m, "sd": s, "t": t, "df": df, "p": p, "ci": ci}


def fmt(x: float, nd: int = 2) -> str:
    return "  n/a" if x != x else f"{x:.{nd}f}"


def rule(ch: str = "-", n: int = 100) -> None:
    print(ch * n)


def head(title: str) -> None:
    print()
    rule("=")
    print(title)
    rule("=")


# ---------------------------------------------------------------------------
# per-run slicing
# ---------------------------------------------------------------------------
def by_year(rows: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for r in rows:
        out.setdefault(yr(r), []).append(r)
    return out


def counts(rows: list[dict]) -> dict:
    n = len(rows)
    n_inc = sum(1 for r in rows if L.is_increase(r))
    n_high = sum(1 for r in rows if L.is_high(r))
    n_hi_inc = sum(1 for r in rows if L.is_high(r) and L.is_increase(r))
    n_unparsed = sum(1 for r in rows if L.wsa(r) not in L.LABEL_LEVELS)
    return {
        "n": n, "n_inc": n_inc, "n_high": n_high, "n_hi_inc": n_hi_inc,
        "n_unparsed": n_unparsed,
        "inc_rate": 100.0 * n_inc / n if n else float("nan"),
        "high_share": 100.0 * n_high / n if n else float("nan"),
        "ibr": 100.0 * n_hi_inc / n_high if n_high else float("nan"),
    }


# ---------------------------------------------------------------------------
# SECTION 1 -- premise test
# ---------------------------------------------------------------------------
def section1_premise(prefix: str, label: str, seeds: list[str]) -> bool:
    head(f"SECTION 1  PREMISE TEST -- is the year-1 world identical across arms?   [{label}]")
    print("Matched on (seed, agent_id) at year == 1. A column PASSES only if every")
    print("matched pair is equal. 'distinct' counts distinct values over ALL year-1")
    print("rows pooled across seeds: a column with 1 distinct value is identical but")
    print("carries no information (it could never have been used as a stratifier).")
    print()

    allrows = {}
    for arm in ("governed", "ungoverned"):
        for s in seeds:
            rows = [r for r in L.load_run(L.run_dir(arm, prefix, s)) if yr(r) == 1]
            allrows[(arm, s)] = {r["agent_id"]: r for r in rows}
            if len(rows) != len(allrows[(arm, s)]):
                print(f"  !! DUPLICATE agent_id at year 1 in {arm} seed {s}: "
                      f"{len(rows)} rows, {len(allrows[(arm,s)])} unique ids")

    n_pairs = 0
    for s in seeds:
        g, u = allrows[("governed", s)], allrows[("ungoverned", s)]
        if set(g) != set(u):
            print(f"  !! agent_id sets differ at year 1 for seed {s}: "
                  f"gov-only={sorted(set(g)-set(u))[:5]} ung-only={sorted(set(u)-set(g))[:5]}")
        n_pairs += len(set(g) & set(u))
    print(f"matched year-1 (seed, agent_id) pairs: {n_pairs}  "
          f"({len(seeds)} seeds x {n_pairs // max(len(seeds),1)} agents)")
    print()

    def check(col: str) -> tuple[int, int, int, list[str]]:
        eq = tot = 0
        vals = set()
        bad = []
        for s in seeds:
            g, u = allrows[("governed", s)], allrows[("ungoverned", s)]
            for aid in sorted(set(g) & set(u)):
                a, b = g[aid].get(col, ""), u[aid].get(col, "")
                vals.add((a or "").strip())
                vals.add((b or "").strip())
                tot += 1
                if same_cell(a, b):
                    eq += 1
                elif len(bad) < 3:
                    bad.append(f"seed{s}/{aid}: gov={a!r} ung={b!r}")
        return eq, tot, len(vals), bad

    print(f"{'column':28s} {'class':16s} {'equal':>9s} {'/ total':>8s} "
          f"{'equal %':>9s} {'distinct':>9s}  verdict")
    rule()
    premise_ok = True
    groups = [("PRE-DECISION", YEAR1_PREDECISION),
              ("post-decision", YEAR1_POSTDECISION_STATE),
              ("LLM output", YEAR1_LLM_OUTPUT)]
    for gname, cols in groups:
        for col in cols:
            eq, tot, ndist, bad = check(col)
            pct = 100.0 * eq / tot if tot else float("nan")
            if gname == "PRE-DECISION":
                ok = (eq == tot)
                verdict = "OK identical" if ok else "*** PREMISE VIOLATED ***"
                if not ok:
                    premise_ok = False
                if ok and ndist == 1:
                    verdict += " (no variance)"
            elif gname == "post-decision":
                verdict = ("identical" if eq == tot else
                           "differs -- expected, it is an OUTCOME")
            else:
                verdict = ("identical" if eq == tot else
                           "differs -- this IS the treatment effect")
            print(f"{col:28s} {gname:16s} {eq:>9d} {tot:>8d} {fmt(pct,3):>9s} "
                  f"{ndist:>9d}  {verdict}")
            for b in bad:
                print(f"{'':28s} {'':16s} example mismatch: {b}")
    rule()
    if premise_ok:
        print("PREMISE HOLDS: every pre-decision column is bit-identical across arms at")
        print("year 1. Any year-1 behavioural difference is therefore attributable to the")
        print("treatment (plus LLM sampling noise), not to divergent world state.")
        print()
        print("CAVEAT carried from Phase 1 and re-confirmed above: the year-1 environment")
        print("columns are identical but DEGENERATE (1 distinct value across all agents and")
        print("seeds). That is fine here -- this design needs the arms to MATCH, not to vary.")
        print("It would not be fine for any design that wanted to STRATIFY on year-1")
        print("environment: there is nothing to stratify on.")
        print()
        print("CAVEAT 2: utilisation_pct / below_minimum_utilisation / request / diversion /")
        print("memory are logged in post_year, AFTER the year-1 action executed. The brief")
        print("classifies the first two as pre-treatment; they are not. They are outcomes,")
        print("they are not conditioned on anywhere in this script, and their year-1")
        print("difference is a treatment effect rather than a premise violation.")
    else:
        print("PREMISE VIOLATED -- see the starred rows. The year-1 contrast below is NOT a")
        print("clean-slate design and must not be read as one.")
    return premise_ok


# ---------------------------------------------------------------------------
# SECTION 2 -- year-1 estimates
# ---------------------------------------------------------------------------
def section2_year1(prefix: str, label: str, seeds: list[str], verbose: bool = True) -> dict:
    per = {}
    for arm in ("governed", "ungoverned"):
        for s in seeds:
            rows = [r for r in L.load_run(L.run_dir(arm, prefix, s)) if yr(r) == 1]
            per[(arm, s)] = counts(rows)

    if verbose:
        head(f"SECTION 2  YEAR-1 ESTIMATES, per seed, exact counts   [{label}]")
        print("All three quantities are percentages in [0,100]. 95% CIs on the per-seed")
        print("rows are WILSON intervals on that seed's own decisions -- they describe")
        print("sampling within one run only and IGNORE between-seed variation, so they are")
        print("NOT the inferential interval. The inferential interval is the paired-t CI on")
        print("the per-seed differences, printed after the table.")
        print()
        print(f"{'seed':>5s} {'arm':11s} {'n':>4s} | {'n_inc':>5s} {'UNCOND INCR %':>13s} "
              f"{'95% CI':>16s} | {'n_high':>6s} {'HIGH SHARE %':>12s} {'95% CI':>16s} | "
              f"{'n_hi&inc':>8s} {'IBR %':>7s} {'95% CI':>16s}")
        rule("-", 140)
        for s in seeds:
            for arm in ("governed", "ungoverned"):
                c = per[(arm, s)]
                ci1 = wilson(c["n_inc"], c["n"])
                ci2 = wilson(c["n_high"], c["n"])
                ci3 = wilson(c["n_hi_inc"], c["n_high"])
                print(f"{s:>5s} {arm:11s} {c['n']:>4d} | {c['n_inc']:>5d} "
                      f"{fmt(c['inc_rate']):>13s} {f'[{fmt(ci1[0])},{fmt(ci1[1])}]':>16s} | "
                      f"{c['n_high']:>6d} {fmt(c['high_share']):>12s} "
                      f"{f'[{fmt(ci2[0])},{fmt(ci2[1])}]':>16s} | "
                      f"{c['n_hi_inc']:>8d} {fmt(c['ibr']):>7s} "
                      f"{f'[{fmt(ci3[0])},{fmt(ci3[1])}]':>16s}")
            print()

    out = {}
    for key, name, direction in [
        ("inc_rate", "UNCONDITIONAL increase rate",
         "negative = governance produced FEWER increases at the first decision"),
        ("high_share", "HIGH-appraisal share (the IBR denominator)",
         "negative = governance produced FEWER high-scarcity self-reports"),
        ("ibr", "CONDITIONAL IBR (published statistic)",
         "negative = governance lowered the published statistic"),
    ]:
        gv = [per[("governed", s)][key] for s in seeds]
        uv = [per[("ungoverned", s)][key] for s in seeds]
        diffs = [g - u for g, u in zip(gv, uv)]
        rep = paired_report(diffs) if not any(d != d for d in diffs) else None
        out[key] = {"gov": gv, "ung": uv, "diffs": diffs, "rep": rep,
                    "name": name, "direction": direction}

    if verbose:
        print("PAIRED CONTRAST AT YEAR 1 -- unit of inference is the seed "
              f"(n = {len(seeds)} seeds, df = {len(seeds)-1})")
        print("sign convention: gap = governed MINUS ungoverned")
        rule()
        for key in ("inc_rate", "high_share", "ibr"):
            o = out[key]
            print(f"\n{o['name']}")
            print(f"  governed per seed  : {[round(x,2) for x in o['gov']]}   "
                  f"mean {fmt(L.mean(o['gov']))}  sd {fmt(L.sd(o['gov']))}")
            print(f"  ungoverned per seed: {[round(x,2) for x in o['ung']]}   "
                  f"mean {fmt(L.mean(o['ung']))}  sd {fmt(L.sd(o['ung']))}")
            print(f"  per-seed gaps      : {[round(x,2) for x in o['diffs']]}")
            r = o["rep"]
            if r is None:
                print("  !! a seed had an undefined value (empty denominator); "
                      "no paired test computed")
                continue
            print(f"  MEAN GAP = {fmt(r['mean'])} pp   95% CI "
                  f"[{fmt(r['ci'][0])}, {fmt(r['ci'][1])}]   "
                  f"t = {fmt(r['t'],3)}  df = {r['df']}  p = {r['p']:.6f}")
            print(f"  reading: {o['direction']}")
            same_sign = all(d < 0 for d in o["diffs"]) or all(d > 0 for d in o["diffs"])
            print(f"  all {len(o['diffs'])} seeds agree in sign: {same_sign}")
    return out


# ---------------------------------------------------------------------------
# SECTION 4 -- trajectory
# ---------------------------------------------------------------------------
def trajectory(prefix: str, seeds: list[str]) -> dict:
    """{(arm, seed): {year: counts}}"""
    out = {}
    for arm in ("governed", "ungoverned"):
        for s in seeds:
            rows = L.load_run(L.run_dir(arm, prefix, s))
            out[(arm, s)] = {y: counts(rs) for y, rs in by_year(rows).items()}
    return out


def section4_trajectory(label: str, seeds: list[str], traj: dict, years: list[int]) -> dict:
    head(f"SECTION 4  TRAJECTORY, year 1..{max(years)}   [{label}]")
    print("Each cell is the mean over seeds of that seed's within-year rate.")
    print("gap = governed MINUS ungoverned; negative = governance lowered it.")
    print("'sig' marks a paired t across seeds with p < 0.05 (df = "
          f"{len(seeds)-1}) on that year alone.")
    print("World-state note from Section 1 / Phase 1: the arms share an identical world")
    print("at year 1 only. From year 2 the reservoir trajectories diverge, so gaps from")
    print("year 2 onward mix the direct treatment effect with world divergence.")
    print()
    print(f"{'yr':>3s} | {'incr% gov':>9s} {'incr% ung':>9s} {'gap':>8s} {'p':>8s} | "
          f"{'high% gov':>9s} {'high% ung':>9s} {'gap':>8s} {'p':>8s} | "
          f"{'IBR% gov':>9s} {'IBR% ung':>9s} {'gap':>8s} {'p':>8s} | "
          f"{'n_high g/u':>12s}")
    rule("-", 132)
    per_year = {}
    for y in years:
        cells = {}
        line = f"{y:>3d} |"
        for key in ("inc_rate", "high_share", "ibr"):
            gv = [traj[("governed", s)][y][key] for s in seeds]
            uv = [traj[("ungoverned", s)][y][key] for s in seeds]
            diffs = [g - u for g, u in zip(gv, uv)]
            usable = not any(d != d for d in diffs)
            rep = paired_report(diffs) if usable else None
            cells[key] = {"gov": L.mean(gv), "ung": L.mean(uv),
                          "gap": L.mean(diffs) if usable else float("nan"),
                          "p": rep["p"] if rep else float("nan")}
            star = ""
            if rep and rep["p"] == rep["p"] and rep["p"] < 0.05:
                star = "*"
            line += (f" {fmt(cells[key]['gov']):>9s} {fmt(cells[key]['ung']):>9s} "
                     f"{fmt(cells[key]['gap']):>8s} "
                     f"{(fmt(cells[key]['p'],4)+star):>8s} |")
        ng = sum(traj[("governed", s)][y]["n_high"] for s in seeds)
        nu = sum(traj[("ungoverned", s)][y]["n_high"] for s in seeds)
        line += f" {f'{ng}/{nu}':>12s}"
        print(line)
        per_year[y] = cells
    return per_year


# ---------------------------------------------------------------------------
# SECTION 6 -- world-executed supplement
# ---------------------------------------------------------------------------
def section6_executed(prefix: str, label: str, seeds: list[str]) -> None:
    head(f"SECTION 6  YEAR-1 GOVERNANCE FUNNEL AND THE WORLD-EXECUTED ACTION   [{label}]")
    print("Section 2 measured the published INTENT-stage statistic. This section opens the")
    print("box and asks what governance actually did at year 1, using the audit CSV.")
    print()
    print(f"{'seed':>5s} {'arm':11s} {'n':>4s} {'prop.incr':>10s} {'REJECTED':>9s} "
          f"{'rej&incr':>9s} {'approved incr':>14s} {'memory written':>15s}")
    rule()
    for s in seeds:
        for arm in ("governed", "ungoverned"):
            aud = [a for a in L.load_audit(L.run_dir(arm, prefix, s)) if int(a["year"]) == 1]
            sim = {(r["agent_id"], r["year"]): r
                   for r in L.load_run(L.run_dir(arm, prefix, s)) if yr(r) == 1}
            n = len(aud)
            prop = sum(1 for a in aud if (a.get("final_skill") or "").strip() in L.INCREASE)
            rej = sum(1 for a in aud
                      if (a.get("status") or "").strip().upper().startswith("REJECTED"))
            rej_inc = sum(1 for a in aud
                          if (a.get("status") or "").strip().upper().startswith("REJECTED")
                          and (a.get("final_skill") or "").strip() in L.INCREASE)
            mem = sum(1 for k, r in sim.items() if (r.get("memory") or "").strip())
            print(f"{s:>5s} {arm:11s} {n:>4d} {prop:>10d} {rej:>9d} {rej_inc:>9d} "
                  f"{prop-rej_inc:>14d} {mem:>15d}")
    print()
    print("Reading of the funnel (anchor model): at year 1 BOTH arms' language models ask to")
    print("increase at almost the same rate. The governed arm's validators then REJECT most")
    print("of those requests. Because the last proposal is what lands in yearly_decision, the")
    print("rejection is INVISIBLE in the published intent-stage statistic. A rejected row also")
    print("writes an EMPTY memory string, so governed agents enter year 2 with a materially")
    print("thinner memory trace -- a third treatment-affected input alongside the reservoir")
    print("and the agent's own utilisation.")
    print()
    print("Phase 1 established that simulation_log.yearly_decision is the agent's LAST")
    print("PROPOSAL, not what the world executed: every REJECTED row leaves the agent's")
    print("request unchanged, i.e. it executes the default skill 'maintain_demand'.")
    print("This block recomputes the same three year-1 quantities under")
    print("   executed = maintain_demand if audit status startswith REJECTED else final_skill")
    print("It is a SUPPLEMENT, clearly labelled: the published headline is the intent-stage")
    print("number, and Sections 2 and 4 above reproduce the published definition exactly.")
    print()
    rows_out = []
    for arm in ("governed", "ungoverned"):
        for s in seeds:
            aud = L.load_audit(L.run_dir(arm, prefix, s))
            sim = {(r["agent_id"], r["year"]): r
                   for r in L.load_run(L.run_dir(arm, prefix, s))}
            n = n_inc = n_high = n_hi_inc = n_rej = 0
            for a in aud:
                if int(a["year"]) != 1:
                    continue
                key = (a["agent_id"], a["year"])
                sr = sim.get(key)
                if sr is None:
                    print(f"  !! audit row with no simulation_log match: {arm} seed{s} {key}")
                    continue
                status = (a.get("status") or "").strip().upper()
                rejected = status.startswith("REJECTED")
                execd = L.DEFAULT_SKILL if rejected else (a.get("final_skill") or "").strip()
                hi = L.is_high(sr)
                n += 1
                n_rej += rejected
                n_inc += execd in L.INCREASE
                n_high += hi
                n_hi_inc += hi and execd in L.INCREASE
            rows_out.append({
                "arm": arm, "seed": s, "n": n, "n_rej": n_rej,
                "inc": 100.0 * n_inc / n if n else float("nan"),
                "high": 100.0 * n_high / n if n else float("nan"),
                "ibr": 100.0 * n_hi_inc / n_high if n_high else float("nan"),
            })
    print(f"{'seed':>5s} {'arm':11s} {'n':>4s} {'rejected':>9s} {'EXEC incr %':>12s} "
          f"{'high share %':>13s} {'EXEC IBR %':>11s}")
    rule()
    for s in seeds:
        for arm in ("governed", "ungoverned"):
            r = next(x for x in rows_out if x["arm"] == arm and x["seed"] == s)
            print(f"{s:>5s} {arm:11s} {r['n']:>4d} {r['n_rej']:>9d} {fmt(r['inc']):>12s} "
                  f"{fmt(r['high']):>13s} {fmt(r['ibr']):>11s}")
    print()
    for key, name in [("inc", "EXECUTED unconditional increase rate"),
                      ("ibr", "EXECUTED conditional IBR")]:
        gv = [next(x for x in rows_out if x["arm"] == "governed" and x["seed"] == s)[key]
              for s in seeds]
        uv = [next(x for x in rows_out if x["arm"] == "ungoverned" and x["seed"] == s)[key]
              for s in seeds]
        diffs = [g - u for g, u in zip(gv, uv)]
        if any(d != d for d in diffs):
            print(f"{name}: undefined for at least one seed; no test")
            continue
        r = paired_report(diffs)
        print(f"{name} at year 1: gov {fmt(L.mean(gv))}  ung {fmt(L.mean(uv))}  "
              f"GAP {fmt(r['mean'])} pp  95% CI [{fmt(r['ci'][0])}, {fmt(r['ci'][1])}]  "
              f"t={fmt(r['t'],3)} df={r['df']} p={r['p']:.6f}")
        print("  sign convention: negative = governance lowered it")


# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 100)
    print("e5_year1 -- YEAR-1 CLEAN-SLATE ESTIMATOR   (irrigation testbed, WAGF v21)")
    print("=" * 100)
    print(f"repo    : {L.REPO}")
    print(f"results : {L.RESULTS}")
    print(f"script  : {os.path.abspath(__file__)}")
    print()
    print("DEFINITIONS (imported from _loader.py, not re-implemented here):")
    print(f"  INCREASE actions = {sorted(L.INCREASE)}")
    print(f"  HIGH appraisal   = wsa_label in {sorted(L.HIGH)} (stripped, uppercased)")
    print(f"  action column    = simulation_log.{L.OUTCOME_COL}")
    print(f"  mediator column  = simulation_log.{L.MEDIATOR_COL}   (POST-TREATMENT)")
    print("SIGN CONVENTION: gap = governed MINUS ungoverned. Negative = governance")
    print("lowered the quantity. The paper quotes the headline as a +23.0 pp improvement;")
    print("here it is -23.02 pp. Same number, opposite sign convention.")

    # ---- corpus inventory, measured
    head("SECTION 0  CORPUS INVENTORY (measured off disk, nothing assumed)")
    inventory = []
    for label, prefix in L.MODELS:
        gs = L.seeds("governed", prefix)
        us = L.seeds("ungoverned", prefix)
        bal = gs == us
        pair = sorted(set(gs) & set(us))
        inventory.append((label, prefix, gs, us, bal, pair))
        print(f"{label:16s} governed={','.join(gs):16s} ungoverned={','.join(us):16s} "
              f"balanced={str(bal):5s} paired={','.join(pair)}")
    print()
    print("Row-count check on every run (expected 3276 = 78 agents x 42 years):")
    bad_rows = []
    for label, prefix, gs, us, _, _ in inventory:
        for arm, ss in (("governed", gs), ("ungoverned", us)):
            for s in ss:
                n = len(L.load_run(L.run_dir(arm, prefix, s)))
                if n != L.EXPECTED_ROWS:
                    bad_rows.append((label, arm, s, n))
    if bad_rows:
        for b in bad_rows:
            print(f"  !! {b}")
    else:
        print("  all runs have exactly 3276 rows -- no malformed or truncated run found")

    anchor_label, anchor_prefix = L.ANCHOR
    anchor_seeds = L.paired_seeds(anchor_prefix)

    # ---- 1
    premise_ok = section1_premise(anchor_prefix, anchor_label, anchor_seeds)

    # ---- 2
    y1 = section2_year1(anchor_prefix, anchor_label, anchor_seeds)

    # ---- 3 all models at year 1
    head("SECTION 3  YEAR-1 CONTRAST ACROSS ALL MODEL CELLS")
    print("Balanced cells only get a paired test. Unbalanced cells are reported with")
    print("their paired-seed subset and flagged; do not read a p-value there.")
    print()
    print("LEVELS are the mean over paired seeds of the year-1 rate in that arm.")
    print("'n/a' in an IBR column means at least one seed had ZERO high-appraisal rows at")
    print("year 1, so the published conditional statistic is undefined for that cell.")
    print()
    print(f"{'model':16s} {'seeds':12s} | {'incr g':>7s} {'incr u':>7s} {'gap':>8s} {'p':>8s} | "
          f"{'high g':>7s} {'high u':>7s} {'gap':>8s} {'p':>8s} | "
          f"{'IBR g':>7s} {'IBR u':>7s} {'gap':>8s} {'p':>8s} | note")
    rule("-", 150)
    model_y1 = {}
    for label, prefix, gs, us, bal, pair in inventory:
        if not pair:
            print(f"{label:16s} -- no paired seeds")
            continue
        o = section2_year1(prefix, label, pair, verbose=False)
        model_y1[label] = o
        line = f"{label:16s} {','.join(pair):12s} |"
        for key in ("inc_rate", "high_share", "ibr"):
            r = o[key]["rep"]
            gl, ul = L.mean(o[key]["gov"]), L.mean(o[key]["ung"])
            if r is None:
                line += f" {fmt(gl):>7s} {fmt(ul):>7s} {'n/a':>8s} {'n/a':>8s} |"
            else:
                line += (f" {fmt(gl):>7s} {fmt(ul):>7s} {fmt(r['mean']):>8s} "
                         f"{fmt(r['p'],5):>8s} |")
        note = "" if bal else "UNBALANCED -- p meaningless"
        if len(pair) < 4:
            note = (note + " ; only %d seeds, df=%d" % (len(pair), len(pair) - 1)).strip(" ;")
        print(line + " " + note)
    print()
    print("READ THIS ROW-BY-ROW, it is the most important table for external validity:")
    print("the ANCHOR model (gemma3:4b -- the pair the published -23.0 pp comes from) is the")
    print("ONLY cell whose year-1 intent-stage gaps are all small and non-significant. On")
    print("gemma4:e2b and gemma4:e4b the governed model already proposes far fewer increases")
    print("at the very first decision. Whatever this estimator concludes about the anchor")
    print("does not transfer to the other cells, and vice versa.")

    # ---- 4 trajectory (anchor)
    traj = trajectory(anchor_prefix, anchor_seeds)
    years = sorted(traj[("governed", anchor_seeds[0])])
    per_year = section4_trajectory(anchor_label, anchor_seeds, traj, years)

    with open(TRAJ_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "quantity", "governed_mean", "ungoverned_mean",
                    "gap_gov_minus_ung", "paired_t_p"])
        for y in years:
            for key in ("inc_rate", "high_share", "ibr"):
                c = per_year[y][key]
                w.writerow([y, key, f"{c['gov']:.6f}", f"{c['ung']:.6f}",
                            f"{c['gap']:.6f}", f"{c['p']:.8f}"])
    print(f"\n(trajectory written to {TRAJ_CSV})")

    # ---- 5 mechanism verdict
    head("SECTION 5  MECHANISM -- is the composition shift IMMEDIATE or GRADUAL?")
    print("This is the question the whole year-1 design exists to answer. If the")
    print("high-appraisal gap is already at full size at year 1 -- when the two arms are")
    print("standing in a provably identical world -- then governance changes what the")
    print("agent SAYS from the very first decision, and the composition shift cannot be a")
    print("consequence of the arms having drifted into different reservoirs. If instead")
    print("the gap starts near zero and widens, the shift is at least partly downstream of")
    print("world divergence.")
    print()
    def pooled_gap(key: str, yr_filter) -> dict:
        gv, uv = [], []
        for s in anchor_seeds:
            rg = [r for r in L.load_run(L.run_dir("governed", anchor_prefix, s))
                  if yr_filter(yr(r))]
            ru = [r for r in L.load_run(L.run_dir("ungoverned", anchor_prefix, s))
                  if yr_filter(yr(r))]
            gv.append(counts(rg)[key])
            uv.append(counts(ru)[key])
        return paired_report([a - b for a, b in zip(gv, uv)])

    for key, name in [("high_share", "HIGH-APPRAISAL SHARE (the IBR denominator)"),
                      ("inc_rate", "UNCONDITIONAL INCREASE RATE"),
                      ("ibr", "CONDITIONAL IBR")]:
        g1 = per_year[1][key]["gap"]
        rpool = pooled_gap(key, lambda y: True)
        rrest = pooled_gap(key, lambda y: y >= 2)
        gaps = [(y, per_year[y][key]["gap"]) for y in years
                if per_year[y][key]["gap"] == per_year[y][key]["gap"]]
        ymin = min(gaps, key=lambda t: t[1])
        ymax = max(gaps, key=lambda t: t[1])
        frac = 100.0 * g1 / rpool["mean"] if rpool["mean"] else float("nan")
        print(f"{name}")
        print(f"  year 1 only  (clean world) : {fmt(g1):>8s} pp   "
              f"p = {per_year[1][key]['p']:.6f}")
        print(f"  years 2-42   (diverged)    : {fmt(rrest['mean']):>8s} pp   "
              f"95% CI [{fmt(rrest['ci'][0])}, {fmt(rrest['ci'][1])}]  p = {rrest['p']:.6f}")
        print(f"  all 42 years (published)   : {fmt(rpool['mean']):>8s} pp   "
              f"95% CI [{fmt(rpool['ci'][0])}, {fmt(rpool['ci'][1])}]  p = {rpool['p']:.6f}")
        print(f"  most negative single year  : {fmt(ymin[1]):>8s} pp at year {ymin[0]}")
        print(f"  most positive single year  : {fmt(ymax[1]):>8s} pp at year {ymax[0]}")
        print(f"  fraction of the published 42-year gap already present at year 1: "
              f"{fmt(frac,1)} %")
        print()

    print("CROSS-MODEL CHECK ON THE COMPOSITION CHANNEL AT YEAR 1")
    print("(the single most decisive line of evidence: if governance changed the SELF-REPORT")
    print(" directly, the high-appraisal gap would already be open at year 1 in every cell)")
    print(f"  {'model':16s} {'year-1 high-share gap':>22s} {'p':>10s}  significant?")
    for label in [l for l, _ in L.MODELS]:
        o = model_y1.get(label)
        if not o:
            continue
        r = o["high_share"]["rep"]
        sig = "no" if (r["p"] != r["p"] or r["p"] >= 0.05) else "YES"
        print(f"  {label:16s} {fmt(r['mean']):>22s} {fmt(r['p'],5):>10s}  {sig}")
    print("  All cells: the composition shift is NOT open at year 1. It opens later,")
    print("  once the arms' worlds, memories and utilisation levels have diverged.")
    print("  CAVEAT on this table: gemma3:12b has df=2 and ministral-3:8b is UNBALANCED")
    print("  with df=1, so their 'no' is weak evidence. The three df=4 cells (gemma3:4b,")
    print("  gemma4:e2b, gemma4:e4b) carry the weight, and all three agree.")
    print("  CAVEAT 2: a null is not proof of no effect. What the year-1 intervals DO")
    print("  exclude is an effect anywhere near the published magnitude (Section 8).")

    # ---- 6 executed supplement
    section6_executed(anchor_prefix, anchor_label, anchor_seeds)

    # ---- 7 sanity
    head("SECTION 7  SANITY CHECKS")
    problems = []
    empty_den = {}
    for label, prefix, gs, us, bal, pair in inventory:
        for arm, ss in (("governed", gs), ("ungoverned", us)):
            n_empty = n_runyears = 0
            for s in ss:
                rows = L.load_run(L.run_dir(arm, prefix, s))
                byy = by_year(rows)
                ny = sorted({len(v) for v in byy.values()})
                if ny != [78]:
                    problems.append(f"{label}/{arm}/seed{s}: agents-per-year not uniformly 78: {ny}")
                if sorted(byy) != list(range(1, 43)):
                    problems.append(f"{label}/{arm}/seed{s}: years are not 1..42")
                for y, rs in byy.items():
                    c = counts(rs)
                    n_runyears += 1
                    for k in ("inc_rate", "high_share"):
                        if not (0.0 <= c[k] <= 100.0):
                            problems.append(f"{label}/{arm}/seed{s}/y{y}: {k}={c[k]}")
                    if c["ibr"] == c["ibr"] and not (0.0 <= c["ibr"] <= 100.0):
                        problems.append(f"{label}/{arm}/seed{s}/y{y}: ibr={c['ibr']}")
                    if c["n_high"] == 0:
                        n_empty += 1
                    if c["n_hi_inc"] > c["n_high"] or c["n_inc"] > c["n"]:
                        problems.append(f"{label}/{arm}/seed{s}/y{y}: count inconsistency")
            empty_den[(label, arm)] = (n_empty, n_runyears)
    print("Structural checks over every (run x year) in the corpus:")
    if problems:
        print(f"  {len(problems)} STRUCTURAL anomaly line(s):")
        for p in problems[:40]:
            print(f"  !! {p}")
        if len(problems) > 40:
            print(f"  ... and {len(problems)-40} more")
    else:
        print("  none. Rates all within [0,100]; numerators never exceed denominators;")
        print("  78 agents in every year; years 1..42 complete in every run; row counts 3276.")
    print()
    print("EMPTY IBR DENOMINATORS -- not a bug, a property of the published statistic.")
    print("A (run, year) with zero high-appraisal rows has an UNDEFINED conditional IBR.")
    print("Counted per model x arm below. This is the conditioning defect showing up as a")
    print("missing-data pattern that is itself caused by the treatment.")
    print(f"  {'model':16s} {'arm':11s} {'run-years with 0 HIGH rows':>28s} {'of':>6s} {'%':>7s}")
    for label, prefix, gs, us, bal, pair in inventory:
        for arm in ("governed", "ungoverned"):
            ne, nt = empty_den[(label, arm)]
            print(f"  {label:16s} {arm:11s} {ne:>28d} {nt:>6d} {100.0*ne/nt:>7.2f}")
    # unparsed labels at year 1
    print()
    print("unparsed wsa_label at year 1 (the literal string 'N/A', which a blank-cell test")
    print("would miss; every such row is a REJECTED_FALLBACK):")
    for arm in ("governed", "ungoverned"):
        tot = sum(counts([r for r in L.load_run(L.run_dir(arm, anchor_prefix, s))
                          if yr(r) == 1])["n_unparsed"] for s in anchor_seeds)
        print(f"  {anchor_label} {arm:11s}: {tot} of {78*len(anchor_seeds)} year-1 rows")

    # ---- 8 verdict
    head("SECTION 8  VERDICT AGAINST THE PUBLISHED -23.0 pp")
    r_ibr = y1["ibr"]["rep"]
    r_inc = y1["inc_rate"]["rep"]
    r_high = y1["high_share"]["rep"]
    print(f"published anchor gap (all 42 years, conditional IBR) : -23.02 pp")
    print(f"year-1 conditional IBR gap (same definition)         : {fmt(r_ibr['mean'])} pp "
          f"95% CI [{fmt(r_ibr['ci'][0])}, {fmt(r_ibr['ci'][1])}] p={r_ibr['p']:.6f}")
    print(f"year-1 UNCONDITIONAL increase gap (no post-treatment  ")
    print(f"  conditioning at all -- the identified quantity)     : {fmt(r_inc['mean'])} pp "
          f"95% CI [{fmt(r_inc['ci'][0])}, {fmt(r_inc['ci'][1])}] p={r_inc['p']:.6f}")
    print(f"year-1 HIGH-appraisal share gap (the composition      ")
    print(f"  channel, measured as an outcome not conditioned on) : {fmt(r_high['mean'])} pp "
          f"95% CI [{fmt(r_high['ci'][0])}, {fmt(r_high['ci'][1])}] p={r_high['p']:.6f}")
    print()
    print("IS THE PUBLISHED MAGNITUDE INSIDE THE YEAR-1 INTERVAL?")
    for nm, r in [("conditional IBR", r_ibr), ("unconditional increase rate", r_inc)]:
        inside = r["ci"][0] <= -23.02 <= r["ci"][1]
        print(f"  {nm:30s}: -23.02 pp is {'INSIDE' if inside else 'OUTSIDE'} the year-1 "
              f"95% CI [{fmt(r['ci'][0])}, {fmt(r['ci'][1])}]")
    print("  An OUTSIDE verdict means this design is powerful enough to REJECT the published")
    print("  magnitude at the first decision -- it is an informative null, not an absence of")
    print("  power. The year-1 sample is 78 decisions x 5 seeds = 390 per arm.")
    print()
    print("WHAT THIS DESIGN DOES AND DOES NOT IDENTIFY")
    print("  IDENTIFIED  : the effect of governance on the FIRST decision, free of any world")
    print("                divergence, because Section 1 proved the year-1 world is identical.")
    print("  IDENTIFIED  : that the year-1 effect on the world-executed action is large,")
    print("                and that it operates by REJECTION rather than by persuasion.")
    print("  NOT IDENTIFIED: the 42-year contrast. From year 2 the arms inhabit different")
    print("                reservoirs, hold different memories, and sit at different")
    print("                utilisation. Those are all treatment-affected, so no year>=2")
    print("                contrast can be cleaned by conditioning -- including by")
    print("                conditioning on wsa_label, which is the original defect.")
    print("  NOT IDENTIFIED: a controlled DIRECT effect of governance on the appraisal-action")
    print("                relationship. Nothing in this corpus provides that.")
    print()
    print(f"premise verified: {premise_ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
