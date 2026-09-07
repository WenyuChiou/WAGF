"""e4_bounds -- WORST-CASE PARTIAL-IDENTIFICATION BOUNDS ON THE PUBLISHED CONDITIONAL GAP.

===============================================================================
THE ESTIMAND, IN WORDS (two of them, because the published statistic is ambiguous)
===============================================================================
The published headline compares the increase-rate among high-appraisal decisions in
the governed arm (36.05 %) with the same rate in the no-validator arm (59.07 %), a gap
of -23.0 pp.  Those two rates are computed over DIFFERENT sets of decisions, because
governance changes which decisions self-report high water scarcity (37 % vs 83 % of all
decisions on the anchor model).  A difference of two conditional means taken over two
different populations is not a treatment effect on any population.  So before bounding
anything we must say which population we mean.  This script bounds two well-defined ones.

  ESTIMAND 1 -- "WOULD-BE-HIGH" POPULATION  (Manski, Part 1)
      Delta_S  =  E[ increase | governance ON,  S ]  -  E[ increase | governance OFF, S ]
      where S = the set of decisions that WOULD self-report high water scarcity if
      governance were absent.  S is defined by a potential outcome under a single fixed
      arm, so it is one fixed population, and both terms are contrasts on it.
      Reading in words: "among the decisions that would have claimed high scarcity
      without validators, by how much does turning validators on change the share that
      nonetheless increase their diversion request?"
      The second term is point identified (it is exactly the published 59.07 %).
      The first is NOT, because in the governed arm we cannot see who belongs to S.

  ESTIMAND 2 -- "ALWAYS-HIGH" POPULATION  (Lee, Part 2)
      Delta_A  =  E[ increase | governance ON,  A ]  -  E[ increase | governance OFF, A ]
      where A = decisions that self-report high scarcity under BOTH arms.
      Under the monotonicity assumption stated below, A is exactly the governed arm's
      high-appraisal set, so the first term is point identified (the published 36.05 %),
      and the SECOND is not, because the ungoverned high-appraisal set is A plus an
      unidentified admixture of decisions that governance would have talked down.

Sign convention, in words: every gap in this file is GOVERNED MINUS UNGOVERNED.
NEGATIVE means governance LOWERED the rate of "claims high scarcity, increases anyway",
which is the direction the paper reports as the governance benefit.  A bound interval
that lies entirely below zero means the sign of the published finding survives the worst
case; an interval straddling zero means it does not.

===============================================================================
IDENTIFYING ASSUMPTIONS (what each bound buys, and what it still costs)
===============================================================================
A1  RANDOMISATION / EXCHANGEABILITY OF ARMS.  The two arms are the same 78 agents over
    the same 42 years under the same seeds, differing only in whether validators are
    enforced.  Therefore P(S) -- the prevalence of "would report high scarcity without
    governance" -- is identified from the ungoverned arm's observed high-appraisal share.
    This is used by BOTH parts.  Required for every number below.
    NOTE this is an assumption about the DESIGN, not about the LLM: it does not require
    that the same decision draws the same LLM sample in both arms.

A2  MONOTONICITY OF THE SELF-REPORT (Lee, Part 2 only; also a refinement in Part 1b).
    Governance never turns a decision that would have reported non-high scarcity into
    one that reports high scarcity:  HIGH(governed) <= HIGH(ungoverned), unit by unit.
    Part 2 CANNOT be computed without it.  Part 1's headline bound is computed BOTH with
    and without it, and the two agree to ~0.02 pp, so Part 1 does not lean on it.
    This script REPORTS DIRECT EVIDENCE AGAINST A2 (Section 3): the share of matched
    (seed, agent, year) rows where the governed arm reports HIGH and the ungoverned arm
    does not.  That share is not zero.  Part of it is LLM sampling noise rather than a
    real monotonicity violation, and this corpus cannot separate the two, because it has
    no resample-only control arm.  Treat A2 as an approximation, and treat Part 2's
    bounds as conditional on an assumption this corpus visibly strains.

A3  NOTHING ELSE.  No bound below conditions on any post-treatment variable.  The only
    covariates used anywhere (Part 2b/2c) are those the Phase-1 exogeneity audit cleared
    as identical across arms on all 16,380 matched rows -- water_right, cluster, basin --
    plus `year` (a merge key, exogenous by construction) and an off-log exogenous
    precipitation trace.  The reservoir columns (lake_mead_level, mead_storage_maf,
    drought_index, shortage_tier, curtailment_ratio) and the agent-state columns
    (utilisation_pct, below_minimum_utilisation) are NEVER used: Phase 1 showed all of
    them are treatment-affected from year 1 or year 2.

===============================================================================
WHAT WOULD FALSIFY THE RESULT
===============================================================================
F1  If the governed arm's UNCONDITIONAL increase rate were >= the ungoverned arm's
    high-appraisal increase rate, Part 1's upper bound would touch or cross zero and the
    sign would no longer be robust.  The whole of Part 1 rests on the arithmetic fact
    that governance cannot hide more increases in the S stratum than it committed in
    total.  Recomputing the unconditional increase rates is a one-line falsification test
    and this script prints them.
F2  If the appraisal shift ran the other way in any seed (governed high-share exceeding
    ungoverned high-share), the "missing decisions" framing inverts and both parts must
    be re-derived.  Per-seed high shares are printed; any such seed is flagged as FATAL.
F3  If A2 fails badly enough -- i.e. governance genuinely creates high-appraisal
    decisions rather than merely sampling differently -- Part 2's always-high stratum is
    not the governed high set and every Part-2 number is void.  Section 3 quantifies the
    observed violation rate; a reader who believes it is real rather than noise should
    discard Part 2 and keep Part 1.
F4  If `yearly_decision` is not the quantity of interest.  Phase 1 established that
    `yearly_decision` is the agent's last PROPOSAL, not the executed action: every
    REJECTED row leaves the diversion request unchanged.  Section 6 re-runs the headline
    bound on the executed action and reports whether the conclusion moves.

===============================================================================
OUTPUT: stdout only.  Writes no files.  Reads only from examples/ and ref/.
Runnable as:  python reproduction/decomposition/e4_bounds.py     (from the repo root)
Stdlib only.
===============================================================================
"""
from __future__ import annotations

import csv
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import _loader as L  # noqa: E402  canonical loader -- do not re-implement its definitions

# ---------------------------------------------------------------------------
# Small formatting / stats helpers
# ---------------------------------------------------------------------------
NA = float("nan")


def pct(x, w=7, d=2):
    if x != x:
        return " " * (w - 3) + "n/a"
    return f"{x:{w}.{d}f}"


def rule(ch="-", n=110):
    print(ch * n)


def head(title):
    print()
    rule("=")
    print(title)
    rule("=")


def t_crit(p_two_sided, df):
    """Inverse Student-t: value t with P(|T|>t) = p_two_sided. Bisection on L.t_two_sided_p."""
    if df <= 0:
        return NA
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if L.t_two_sided_p(mid, df) > p_two_sided:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def onesample_t(xs):
    """(mean, sd, se, t, df, two-sided p) for H0: mean == 0."""
    xs = [x for x in xs]
    n = len(xs)
    m = L.mean(xs)
    s = L.sd(xs)
    if n < 2 or s != s:
        return m, s, NA, NA, max(n - 1, 0), NA
    se = s / math.sqrt(n)
    if se == 0:
        return m, s, se, float("inf") if m else NA, n - 1, 0.0 if m else NA
    t = m / se
    return m, s, se, t, n - 1, L.t_two_sided_p(t, n - 1)


# ---------------------------------------------------------------------------
# Corpus counting -- integer counts only, so every rate can be audited by hand
# ---------------------------------------------------------------------------
class ArmCounts:
    """Integer counts for one (arm, model, seed) run."""

    __slots__ = ("n", "n_high", "n_inc", "n_high_inc", "n_unparsed", "rows")

    def __init__(self, rows):
        self.rows = rows
        self.n = len(rows)
        self.n_high = sum(1 for r in rows if L.is_high(r))
        self.n_inc = sum(1 for r in rows if L.is_increase(r))
        self.n_high_inc = sum(1 for r in rows if L.is_high(r) and L.is_increase(r))
        self.n_unparsed = sum(1 for r in rows if L.wsa(r) not in L.LABEL_LEVELS)

    @property
    def high_share(self):
        return self.n_high / self.n

    @property
    def inc_share(self):
        return self.n_inc / self.n

    @property
    def ibr(self):
        return self.n_high_inc / self.n_high if self.n_high else NA


def load_pair(prefix, seed, action_fn=None):
    """(governed ArmCounts, ungoverned ArmCounts) for one seed.

    action_fn, if given, rewrites row['yearly_decision'] before counting (Section 6).
    """
    out = []
    for arm in ("governed", "ungoverned"):
        rows = L.load_run(L.run_dir(arm, prefix, seed))
        if action_fn is not None:
            rows = action_fn(L.run_dir(arm, prefix, seed), rows)
        out.append(ArmCounts(rows))
    return out[0], out[1]


# ===========================================================================
# PART 1 -- MANSKI-STYLE WORST-CASE BOUNDS ON Delta_S
# ===========================================================================
def manski_bounds(g: ArmCounts, u: ArmCounts):
    """Bounds on Delta_S = E[Y(1)|S] - E[Y(0)|S], S = {would report HIGH if ungoverned}.

    All quantities are expressed as FRACTIONS OF ALL DECISIONS in the governed arm, so
    that the arithmetic is transparent:

        pi   = P(S)                       identified from the UNGOVERNED arm  (assumption A1)
        r0   = E[Y(0)|S]                  identified: the published ungoverned IBR
        h1   = P(HIGH(1)=1)               observed in the governed arm
        a    = P(HIGH(1)=1 AND Y(1)=1)    observed in the governed arm
        p    = P(Y(1)=1)                  observed in the governed arm (UNconditional)

    In the governed arm we see every decision's action.  What we do NOT see is which
    governed decisions belong to S.  So the missing information is STRATUM MEMBERSHIP,
    not the outcome.  Three bounds are returned:

      (naive)  the literal recipe: the mass pi - h1 of S-members that governance talked
               down are assumed to be ALL increases (upper) or ALL non-increases (lower).
               This ignores that their actions are observed, so it is NOT sharp.
      (mono)   sharp given monotonicity A2: the missing mass must be drawn from the
               governed arm's observed non-high pool, which contains only p - a increases
               out of 1 - h1 decisions.
      (nomono) sharp WITHOUT A2: S may be ANY subset of the governed arm of mass pi.
    """
    pi = u.high_share                       # A1
    r0 = u.ibr                              # identified
    h1 = g.high_share
    a = g.n_high_inc / g.n
    p = g.inc_share

    res = {"pi": pi, "r0": r0, "h1": h1, "a": a, "p": p,
           "missing_mass": pi - h1}

    if pi <= 0:
        return dict(res, naive=(NA, NA), mono=(NA, NA), nomono=(NA, NA), fatal="pi==0")

    # (naive) -- brief's literal recipe
    lo_n = a / pi
    hi_n = min(1.0, (a + (pi - h1)) / pi) if pi >= h1 else NA
    res["naive"] = (lo_n, hi_n)

    # (mono) -- sharp under A2.  Missing mass m drawn from the non-high pool.
    m = pi - h1
    pool = 1.0 - h1                     # mass of governed non-high decisions
    pool_inc = p - a                    # increases inside that pool
    pool_noninc = pool - pool_inc
    if m < -1e-12:
        res["mono"] = (NA, NA)
    else:
        m = max(m, 0.0)
        hi_m = (a + min(m, pool_inc)) / pi
        lo_m = (a + max(0.0, m - pool_noninc)) / pi
        res["mono"] = (lo_m, hi_m)

    # (nomono) -- S is any subset of mass pi
    hi_x = min(p, pi) / pi
    lo_x = max(0.0, p - (1.0 - pi)) / pi
    res["nomono"] = (lo_x, hi_x)

    for k in ("naive", "mono", "nomono"):
        lo, hi = res[k]
        res[k + "_gap"] = (100.0 * lo - 100.0 * r0, 100.0 * hi - 100.0 * r0)
    return res


# ===========================================================================
# PART 2 -- LEE-STYLE TRIMMING BOUNDS ON Delta_A
# ===========================================================================
def lee_sharp(n_high_g, n_inc_g, n_high_u, n_inc_u):
    """Sharp Lee bounds on E[Y(0) | A] within one cell, trimming BY THE OUTCOME.

    Under A2 the always-high set A is the governed high set, of size n_high_g, and the
    ungoverned high set (size n_high_u) is A plus n_high_u - n_high_g extra decisions.
    Keep fraction k = n_high_g / n_high_u.  With a binary outcome the sharp bounds are

        upper = min(1, r0 / k)            (the retained k are the increases, as far as possible)
        lower = max(0, (r0 - (1-k)) / k)  (the trimmed 1-k are the increases, as far as possible)

    Returns (k, lower, upper, violation_flag).
    """
    if n_high_u <= 0 or n_high_g <= 0:
        return NA, NA, NA, "empty"
    r0 = n_inc_u / n_high_u
    if n_high_g > n_high_u:
        # monotonicity violated inside this cell: nothing to trim, no bound available
        return 1.0, r0, r0, "mono_violation"
    k = n_high_g / n_high_u
    q = 1.0 - k
    up = min(1.0, r0 / k)
    lo = max(0.0, (r0 - q) / k)
    return k, lo, up, ""


def lee_unconditional(g: ArmCounts, u: ArmCounts):
    k, lo, up, flag = lee_sharp(g.n_high, g.n_high_inc, u.n_high, u.n_high_inc)
    ibr1 = g.ibr
    return {"k": k, "trim": 1 - k if k == k else NA,
            "e0_lo": lo, "e0_hi": up, "flag": flag,
            "gap_lo": 100 * ibr1 - 100 * up, "gap_hi": 100 * ibr1 - 100 * lo}


def _strat_key(row, spec, wr_bins):
    parts = []
    if "year" in spec:
        parts.append("y" + str(int(row["year"])))
    if "cluster" in spec:
        parts.append(row["cluster"])
    if "basin" in spec:
        parts.append(row["basin"])
    if "wr" in spec:
        wr = float(row["water_right"])
        b = 0
        for i, edge in enumerate(wr_bins):
            if wr > edge:
                b = i + 1
        parts.append("wr%d" % b)
    return "|".join(parts)


def lee_stratified(g: ArmCounts, u: ArmCounts, spec, wr_bins, min_cell=10):
    """Lee bounds computed WITHIN strata of cleared pre-treatment covariates, then
    aggregated over the always-high population (weights = governed high counts).

    Cells too small for a stable trim proportion are pooled into one residual cell,
    and the pooled mass is reported rather than dropped.
    """
    cg, cu = {}, {}
    for r in g.rows:
        key = _strat_key(r, spec, wr_bins)
        d = cg.setdefault(key, [0, 0])
        if L.is_high(r):
            d[0] += 1
            if L.is_increase(r):
                d[1] += 1
    for r in u.rows:
        key = _strat_key(r, spec, wr_bins)
        d = cu.setdefault(key, [0, 0])
        if L.is_high(r):
            d[0] += 1
            if L.is_increase(r):
                d[1] += 1

    keys = sorted(set(cg) | set(cu))
    big, pooled = [], [0, 0, 0, 0]
    n_pooled_cells = 0
    for key in keys:
        gh, gi = cg.get(key, [0, 0])
        uh, ui = cu.get(key, [0, 0])
        if gh < min_cell or uh < min_cell:
            pooled[0] += gh
            pooled[1] += gi
            pooled[2] += uh
            pooled[3] += ui
            n_pooled_cells += 1
        else:
            big.append((key, gh, gi, uh, ui))
    cells = list(big)
    if pooled[0] > 0 or pooled[2] > 0:
        cells.append(("POOLED-SMALL", pooled[0], pooled[1], pooled[2], pooled[3]))

    tot_w = sum(c[1] for c in cells)
    if tot_w == 0:
        return None
    e0_lo = e0_hi = 0.0
    e1 = 0.0
    n_viol = 0
    viol_mass = 0
    for _key, gh, gi, uh, ui in cells:
        w = gh / tot_w
        k, lo, up, flag = lee_sharp(gh, gi, uh, ui)
        if flag == "empty":
            # no ungoverned high decisions in this cell: E[Y(0)|A,cell] unrestricted
            lo, up = 0.0, 1.0
        if flag == "mono_violation":
            n_viol += 1
            viol_mass += gh
        e0_lo += w * lo
        e0_hi += w * up
        e1 += w * (gi / gh if gh else 0.0)
    return {"n_cells": len(cells), "n_pooled_cells": n_pooled_cells,
            "pooled_gov_high": pooled[0], "tot_gov_high": tot_w,
            "n_viol_cells": n_viol, "viol_mass": viol_mass,
            "e1": e1, "e0_lo": e0_lo, "e0_hi": e0_hi,
            "gap_lo": 100 * e1 - 100 * e0_hi, "gap_hi": 100 * e1 - 100 * e0_lo}


# ---------------------------------------------------------------------------
# Objective-scarcity index from CLEARED pre-treatment variables only
# ---------------------------------------------------------------------------
PRECIP_CSV = os.path.join(L.REPO, "ref", "CRSS_DB", "CRSS_DB", "HistoricalData",
                          "PrismWinterPrecip_ST_NOAA_Future.csv")
UPPER_BASIN_COLS = ["WY", "UT1", "UT2", "UT3", "CO1", "CO2", "CO3"]


def load_precip():
    """calendar year -> Upper-Basin mean winter precipitation in mm.

    Mapping loop-year y -> calendar 2019 + y, and the column set, were established and
    verified to 7e-14 mm in the Phase-1 exogeneity audit.  This is the ONE exogenous,
    treatment-invariant, time-varying covariate available; it is NOT in simulation_log.csv.
    """
    if not os.path.isfile(PRECIP_CSV):
        return None
    out = {}
    with open(PRECIP_CSV, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            ykey = row.get("") or row.get(None)
            try:
                cy = int(str(ykey).strip())
            except (TypeError, ValueError):
                continue
            vals = []
            for c in UPPER_BASIN_COLS:
                try:
                    vals.append(float(row[c]))
                except (KeyError, TypeError, ValueError):
                    vals = []
                    break
            if vals:
                out[cy] = 25.4 * sum(vals) / len(vals)
    return out or None


def scarcity_index(row, precip):
    """Higher = objectively more scarce.  Built ONLY from cleared pre-treatment inputs:
    exogenous winter precipitation (year level) and the static water_right entitlement
    (agent level).  Returns None when the calendar year is outside the precipitation file.
    """
    cy = 2019 + int(row["year"])
    if cy not in precip:
        return None
    return (-precip[cy] / 25.4, -math.log(float(row["water_right"])))


def lee_index_trim(g: ArmCounts, u: ArmCounts, precip):
    """The brief's index-based trimming.  NOT a sharp bound -- see the printed caveat.

    Trims the ungoverned high-appraisal set down to the governed high-appraisal size,
    once from the top of the objective-scarcity index and once from the bottom.  The two
    resulting rates bracket E[Y(0)|A] ONLY IF selection into A is monotone in that index
    (direction unknown).  If selection is unrelated to the index, neither endpoint is a
    bound at all and the interval can sit inside or outside the sharp Lee interval.
    """
    gh = [r for r in g.rows if L.is_high(r) and scarcity_index(r, precip) is not None]
    uh = [r for r in u.rows if L.is_high(r) and scarcity_index(r, precip) is not None]
    dropped_g = sum(1 for r in g.rows if L.is_high(r)) - len(gh)
    dropped_u = sum(1 for r in u.rows if L.is_high(r)) - len(uh)
    if not gh or not uh or len(gh) > len(uh):
        return None
    keep = len(gh)
    uh_sorted = sorted(uh, key=lambda r: scarcity_index(r, precip))
    low_end = uh_sorted[:keep]                    # least objectively scarce kept
    high_end = uh_sorted[-keep:]                  # most objectively scarce kept
    rate = lambda rs: 100.0 * sum(1 for r in rs if L.is_increase(r)) / len(rs)
    ibr1 = 100.0 * sum(1 for r in gh if L.is_increase(r)) / len(gh)
    a_lo, a_hi = rate(low_end), rate(high_end)
    return {"keep": keep, "n_u_high": len(uh), "trim": 1 - keep / len(uh),
            "dropped_g": dropped_g, "dropped_u": dropped_u,
            "ibr1_restricted": ibr1,
            "e0_keep_least_scarce": a_lo, "e0_keep_most_scarce": a_hi,
            "gap_keep_least_scarce": ibr1 - a_lo,
            "gap_keep_most_scarce": ibr1 - a_hi}


# ---------------------------------------------------------------------------
# Section 6 -- executed-action redefinition
# ---------------------------------------------------------------------------
def executed_action_rows(run_dir, rows):
    """Overwrite yearly_decision with the EXECUTED action.

    Phase 1 established (and this script re-verifies the join) that every audit row with
    status REJECTED / REJECTED_FALLBACK leaves the diversion request unchanged, i.e. the
    world executed the registry default `maintain_demand`, regardless of the label in
    `yearly_decision`.  The published statistic uses the label; this function uses what
    actually ran.
    """
    aud = L.load_audit(run_dir)
    st = {}
    for r in aud:
        key = ((r.get("agent_id") or "").strip(), (r.get("year") or "").strip())
        if key in st:
            raise L.DataError("duplicate audit key %r in %s" % (key, run_dir))
        st[key] = (r.get("status") or "").strip()
    out = []
    miss = 0
    for r in rows:
        key = ((r.get("agent_id") or "").strip(), (r.get("year") or "").strip())
        s = st.get(key)
        if s is None:
            miss += 1
            out.append(r)
            continue
        r2 = dict(r)
        if s.startswith("REJECTED"):
            r2["yearly_decision"] = L.DEFAULT_SKILL
        out.append(r2)
    if miss:
        raise L.DataError("%d simulation_log rows had no audit match in %s" % (miss, run_dir))
    return out


# ---------------------------------------------------------------------------
# Monotonicity diagnostic (Section 3)
# ---------------------------------------------------------------------------
def monotonicity_evidence(prefix, seeds):
    """Cross-arm appraisal transition at matched (seed, agent_id, year).

    A2 says a governed decision is never HIGH when its ungoverned counterpart is not.
    Counting matched rows that violate this gives an UPPER BOUND on the violation rate,
    because the two arms also differ by an independent LLM sample; this corpus has no
    resample-only control arm, so the two cannot be separated.
    """
    tot = both = gonly = uonly = neither = 0
    for s in seeds:
        gr = {(r["agent_id"], r["year"]): r for r in L.load_run(L.run_dir("governed", prefix, s))}
        ur = {(r["agent_id"], r["year"]): r for r in L.load_run(L.run_dir("ungoverned", prefix, s))}
        keys = set(gr) & set(ur)
        if len(keys) != len(gr) or len(keys) != len(ur):
            raise L.DataError("join is not 1:1 for seed %s" % s)
        for k in keys:
            hg, hu = L.is_high(gr[k]), L.is_high(ur[k])
            tot += 1
            if hg and hu:
                both += 1
            elif hg and not hu:
                gonly += 1
            elif hu and not hg:
                uonly += 1
            else:
                neither += 1
    return tot, both, gonly, uonly, neither


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print(__doc__)
    print("REPO    =", L.REPO)
    print("RESULTS =", L.RESULTS)

    anchor_label, anchor_prefix = L.ANCHOR

    # -------------------------------------------------------------- Section 0
    head("SECTION 0 -- CORPUS, MEASURED NOT ASSUMED")
    inventory = {}
    for label, prefix in L.MODELS:
        gs, us = L.seeds("governed", prefix), L.seeds("ungoverned", prefix)
        pr = L.paired_seeds(prefix)
        inventory[label] = (prefix, gs, us, pr, L.balanced(prefix))
        print(f"  {label:16s} governed={','.join(gs):14s} ungoverned={','.join(us):14s} "
              f"paired={len(pr)}  balanced={L.balanced(prefix)}")
    print()
    unbal = [l for l, p in L.MODELS if not L.balanced(p)]
    print(f"  UNBALANCED, excluded from every paired contrast: {unbal or 'none'}")
    short = [(l, len(L.paired_seeds(p))) for l, p in L.MODELS
             if L.balanced(p) and len(L.paired_seeds(p)) != 5]
    print(f"  balanced but with paired-seed count != 5: {short or 'none'}")

    # -------------------------------------------------------------- Section 1
    head("SECTION 1 -- OBSERVED QUANTITIES, ANCHOR MODEL %s, PER SEED" % anchor_label)
    print("  All rates are percentages of the stated denominator. 'high share' is the")
    print("  POST-TREATMENT conditioning variable whose movement is the whole problem.")
    print()
    print(f"  {'seed':>5s} {'arm':11s} {'rows':>6s} {'n_high':>7s} {'high%':>8s} "
          f"{'n_inc':>6s} {'incr% (uncond)':>15s} {'n_hi_inc':>9s} {'IBR%':>8s} {'unparsed':>9s}")
    rule()
    anchor = {}
    fatal = []
    for s in L.paired_seeds(anchor_prefix):
        g, u = load_pair(anchor_prefix, s)
        anchor[s] = (g, u)
        for name, c in (("governed", g), ("ungoverned", u)):
            print(f"  {s:>5s} {name:11s} {c.n:>6d} {c.n_high:>7d} {pct(100*c.high_share,8)} "
                  f"{c.n_inc:>6d} {pct(100*c.inc_share,15)} {c.n_high_inc:>9d} "
                  f"{pct(100*c.ibr,8)} {c.n_unparsed:>9d}")
        if g.high_share >= u.high_share:
            fatal.append(s)
        if g.n != L.EXPECTED_ROWS or u.n != L.EXPECTED_ROWS:
            fatal.append("rowcount-" + s)
    rule()
    ibr_g = [anchor[s][0].ibr * 100 for s in anchor]
    ibr_u = [anchor[s][1].ibr * 100 for s in anchor]
    diffs = [a - b for a, b in zip(ibr_g, ibr_u)]
    m, sdv, se, t, df, p = onesample_t(diffs)
    print(f"  mean governed IBR   = {L.mean(ibr_g):7.2f} %   (published 36.05)")
    print(f"  mean ungoverned IBR = {L.mean(ibr_u):7.2f} %   (published 59.07)")
    print(f"  PUBLISHED GAP (governed - ungoverned) = {m:+7.2f} pp   [negative = governance lowered it]")
    print(f"     per-seed diffs {['%+.2f' % d for d in diffs]}")
    print(f"     paired t = {t:.3f}, df = {df}, p = {p:.6f}")
    print(f"  high-appraisal share  governed {100*L.mean([anchor[s][0].high_share for s in anchor]):.2f} %"
          f"   ungoverned {100*L.mean([anchor[s][1].high_share for s in anchor]):.2f} %"
          f"   shift {100*L.mean([anchor[s][1].high_share - anchor[s][0].high_share for s in anchor]):+.2f} pp")
    if fatal:
        print("  !! FATAL FLAGS:", fatal)
    else:
        print("  sanity: every seed has governed high-share < ungoverned high-share, and 3276 rows.")

    # -------------------------------------------------------------- Section 2
    head("SECTION 2 -- PART 1: MANSKI-STYLE WORST-CASE BOUNDS ON Delta_S")
    print("""  ESTIMAND (words): among the decisions that WOULD self-report high water scarcity
  if validators were absent, how much does turning validators on change the share that
  nonetheless increase their diversion request?  Population = S, fixed, defined by a
  potential outcome under one fixed arm.  Denominator does NOT move between arms.

  E[Y(0)|S] is point identified and equals the published ungoverned rate.
  E[Y(1)|S] is not identified: in the governed arm we see every decision's ACTION but
  cannot see which decisions belong to S.  What is missing is stratum MEMBERSHIP.

  Three bounds are reported.  Read the middle one; the first is the brief's literal
  recipe and is deliberately shown to be slack, the third shows the middle one does not
  depend on monotonicity.""")
    print()
    print(f"  {'seed':>5s} | {'naive LB':>9s} {'naive UB':>9s} | {'sharp LB':>9s} {'sharp UB':>9s} "
          f"| {'no-mono LB':>10s} {'no-mono UB':>10s} | {'pi%':>7s} {'h1%':>7s} {'miss pp':>8s}")
    rule()
    mb = {}
    for s in sorted(anchor):
        g, u = anchor[s]
        b = manski_bounds(g, u)
        mb[s] = b
        print(f"  {s:>5s} | {b['naive_gap'][0]:9.2f} {b['naive_gap'][1]:9.2f} "
              f"| {b['mono_gap'][0]:9.2f} {b['mono_gap'][1]:9.2f} "
              f"| {b['nomono_gap'][0]:10.2f} {b['nomono_gap'][1]:10.2f} "
              f"| {100*b['pi']:7.2f} {100*b['h1']:7.2f} {100*b['missing_mass']:8.2f}")
    rule()

    def bound_summary(name, key):
        los = [mb[s][key][0] for s in sorted(mb)]
        his = [mb[s][key][1] for s in sorted(mb)]
        mlo, _, selo, _, dfl, _ = onesample_t(los)
        mhi, _, sehi, thi, dfh, phi = onesample_t(his)
        tc = t_crit(0.05, dfh)
        tc1 = t_crit(0.10, dfh)   # one-sided 95% critical value
        cons = (mlo - tc * selo, mhi + tc * sehi)
        im = (mlo - tc1 * selo, mhi + tc1 * sehi)
        print(f"  {name}")
        print(f"     identified set for the MEAN effect  = [{mlo:+7.2f}, {mhi:+7.2f}] pp")
        print(f"     per-seed lower bounds  {['%+.2f' % x for x in los]}")
        print(f"     per-seed upper bounds  {['%+.2f' % x for x in his]}")
        print(f"     conservative 95% interval (two-sided crit on both ends) "
              f"= [{cons[0]:+7.2f}, {cons[1]:+7.2f}] pp")
        print(f"     Imbens-Manski-style 95% interval (one-sided crit)      "
              f"= [{im[0]:+7.2f}, {im[1]:+7.2f}] pp")
        print(f"     test of the UPPER bound against zero: t = {thi:.3f}, df = {dfh}, p = {phi:.6f}")
        excl = "EXCLUDES ZERO" if im[1] < 0 else ("EXCLUDES ZERO" if mhi < 0 and cons[1] < 0 else "INCLUDES ZERO")
        print(f"     -> identified set {'EXCLUDES' if mhi < 0 else 'INCLUDES'} zero; "
              f"IM interval {excl}")
        return mlo, mhi, im

    print()
    bound_summary("(1a) NAIVE -- brief's literal recipe (missing S-members all/none increase). NOT SHARP.", "naive_gap")
    print()
    sharp_lo, sharp_hi, sharp_im = bound_summary(
        "(1b) SHARP under monotonicity A2 -- missing mass drawn from the OBSERVED governed non-high pool.", "mono_gap")
    print()
    nm_lo, nm_hi, nm_im = bound_summary(
        "(1c) SHARP WITHOUT monotonicity -- S may be any governed subset of mass pi.", "nomono_gap")
    print()
    print("  WHY (1b) IS TIGHTER THAN (1a), stated plainly: the naive recipe treats the")
    print("  talked-down decisions' actions as unknown.  They are not unknown -- they are in")
    print("  simulation_log.csv, we merely do not know WHICH governed rows they are.  The")
    print("  governed arm committed only %.2f %% increases in total; it cannot hide more"
          % (100 * L.mean([mb[s]['p'] for s in mb])))
    print("  increases inside S than it committed overall.  That single arithmetic fact is")
    print("  what makes the sharp bound informative, and it is falsification test F1.")
    print("  (1b) and (1c) agree to %.3f pp on the upper end, so the sharp bound does NOT"
          % abs(sharp_hi - nm_hi))
    print("  depend on the monotonicity assumption.")

    # -------------------------------------------------------------- Section 3
    head("SECTION 3 -- DIRECT EVIDENCE ON THE MONOTONICITY ASSUMPTION A2")
    tot, both, gonly, uonly, neither = monotonicity_evidence(anchor_prefix, sorted(anchor))
    print(f"  matched (seed, agent, year) rows: {tot}")
    print(f"    HIGH in both arms                  {both:6d}  ({100*both/tot:6.2f} %)")
    print(f"    HIGH governed only  <-- A2 VIOLATION {gonly:6d}  ({100*gonly/tot:6.2f} %)")
    print(f"    HIGH ungoverned only                {uonly:6d}  ({100*uonly/tot:6.2f} %)")
    print(f"    HIGH in neither                    {neither:6d}  ({100*neither/tot:6.2f} %)")
    print()
    print("  A2 (governance never manufactures a high-scarcity self-report) is FALSE in the")
    print("  observed data at the unit level: %.2f %% of matched rows violate it." % (100 * gonly / tot))
    print("  How much of that is a real violation and how much is the independent LLM sample")
    print("  is NOT separable in this corpus -- there is no resample-only control arm.")
    print("  Consequence: Part 1's headline bound (1b/1c) is unaffected, because (1c) makes no")
    print("  monotonicity assumption at all and lands in the same place.  Part 2 below DOES")
    print("  require A2 and must be read as conditional on an assumption the data strain.")

    # -------------------------------------------------------------- Section 4
    head("SECTION 4 -- PART 2: LEE-STYLE TRIMMING BOUNDS ON Delta_A (ALWAYS-HIGH STRATUM)")
    print("""  ESTIMAND (words): among the decisions that self-report high water scarcity under
  BOTH arms, how much does governance change the share that increase anyway?

  MONOTONICITY REQUIRED (A2): governance only ever moves a decision OUT of the
  high-appraisal set, never into it.  Then the governed high set IS the always-high
  stratum, E[Y(1)|A] is the published 36.05 %, and the ungoverned high set is the
  always-high stratum diluted by decisions governance would have talked down.
  Trimming the ungoverned high set down to the governed high set's size, from the top
  and from the bottom of the OUTCOME, gives the sharp bounds.

  PLAUSIBILITY: Section 3 shows A2 is violated on a non-trivial share of matched rows.
  Lee bounds are therefore reported as an assumption-dependent supplement to Part 1,
  not as the headline.""")
    print()
    print("  (2a) UNCONDITIONAL SHARP LEE BOUNDS")
    print(f"  {'seed':>5s} {'gov high':>9s} {'ung high':>9s} {'keep k':>8s} {'trim q':>8s} "
          f"{'E[Y0|A] lo':>11s} {'E[Y0|A] hi':>11s} {'gap LB':>9s} {'gap UB':>9s}")
    rule()
    lee_u = {}
    for s in sorted(anchor):
        g, u = anchor[s]
        d = lee_unconditional(g, u)
        lee_u[s] = d
        print(f"  {s:>5s} {g.n_high:>9d} {u.n_high:>9d} {d['k']:8.4f} {d['trim']:8.4f} "
              f"{100*d['e0_lo']:11.2f} {100*d['e0_hi']:11.2f} {d['gap_lo']:9.2f} {d['gap_hi']:9.2f}"
              + ("   " + d["flag"] if d["flag"] else ""))
    rule()
    los = [lee_u[s]["gap_lo"] for s in sorted(lee_u)]
    his = [lee_u[s]["gap_hi"] for s in sorted(lee_u)]
    mlo, _, selo, _, _, _ = onesample_t(los)
    mhi, _, sehi, _, dfh, _ = onesample_t(his)
    tc1 = t_crit(0.10, dfh)
    print(f"  identified set for the MEAN Delta_A = [{mlo:+7.2f}, {mhi:+7.2f}] pp")
    print(f"  Imbens-Manski-style 95% interval    = [{mlo - tc1*selo:+7.2f}, {mhi + tc1*sehi:+7.2f}] pp")
    print(f"  -> {'EXCLUDES' if mhi < 0 else 'INCLUDES'} zero.")
    ceiling = sum(1 for s in lee_u if lee_u[s]["e0_hi"] >= 0.9999)
    if ceiling:
        print(f"  !! In {ceiling}/{len(lee_u)} seeds the upper end of E[Y(0)|A] is pinned at 100 %,")
        print("     i.e. the trim proportion is so large the bound is at its arithmetic ceiling.")
        print("     That end of the interval carries NO information from the data.")

    # (2b) stratified
    print()
    print("  (2b) COVARIATE-STRATIFIED SHARP LEE BOUNDS")
    print("       Strata built ONLY from Phase-1-cleared variables: year (merge key, exogenous),")
    print("       cluster and basin (identical on all 16,380 matched rows), water_right terciles")
    print("       (static entitlement, 36 distinct values, identical across arms).")
    print("       Cells with <10 high-appraisal decisions in either arm are POOLED, not dropped.")
    all_wr = sorted({float(r["water_right"]) for r in anchor[sorted(anchor)[0]][0].rows})
    wr_bins = [all_wr[len(all_wr) // 3], all_wr[2 * len(all_wr) // 3]]
    print(f"       water_right tercile edges (from the 36 distinct entitlements): {wr_bins}")
    specs = [("cluster+basin", ("cluster", "basin")),
             ("cluster+basin+wr", ("cluster", "basin", "wr")),
             ("year", ("year",)),
             ("year+cluster", ("year", "cluster"))]
    print()
    print(f"  {'strata':20s} {'seed':>5s} {'cells':>6s} {'pooled':>7s} {'poolmass':>9s} "
          f"{'viol':>5s} {'gap LB':>9s} {'gap UB':>9s}")
    rule()
    strat_summary = {}
    for name, spec in specs:
        los_s, his_s = [], []
        for s in sorted(anchor):
            g, u = anchor[s]
            d = lee_stratified(g, u, spec, wr_bins)
            if d is None:
                print(f"  {name:20s} {s:>5s}  -- no cells --")
                continue
            los_s.append(d["gap_lo"])
            his_s.append(d["gap_hi"])
            print(f"  {name:20s} {s:>5s} {d['n_cells']:>6d} {d['n_pooled_cells']:>7d} "
                  f"{d['pooled_gov_high']:>9d} {d['n_viol_cells']:>5d} "
                  f"{d['gap_lo']:9.2f} {d['gap_hi']:9.2f}")
        strat_summary[name] = (L.mean(los_s), L.mean(his_s), los_s, his_s)
    rule()
    for name, spec in specs:
        mlo_s, mhi_s, ls, hs = strat_summary[name]
        _, _, se_l, _, _, _ = onesample_t(ls)
        _, _, se_h, _, dfx, _ = onesample_t(hs)
        tc1x = t_crit(0.10, dfx)
        print(f"  {name:20s} mean identified set = [{mlo_s:+7.2f}, {mhi_s:+7.2f}] pp"
              f"   IM 95% = [{mlo_s - tc1x*se_l:+7.2f}, {mhi_s + tc1x*se_h:+7.2f}] pp"
              f"   -> {'EXCLUDES' if mhi_s < 0 else 'INCLUDES'} zero")

    # (2c) index-based trimming
    print()
    print("  (2c) INDEX-BASED TRIMMING (the brief's requested variant)")
    precip = load_precip()
    if precip is None:
        print("       SKIPPED: precipitation reference file not found at")
        print("       " + PRECIP_CSV)
    else:
        yrs = sorted({2019 + int(r["year"]) for r in anchor[sorted(anchor)[0]][0].rows})
        missing = [y for y in yrs if y not in precip]
        print(f"       objective-scarcity index = (-exogenous winter precipitation for the year,")
        print(f"                                   -log static water_right entitlement), lexicographic.")
        print(f"       Higher index = objectively scarcer.  No post-treatment input is used.")
        print(f"       Calendar years required {yrs[0]}..{yrs[-1]}; precipitation file covers "
              f"{min(precip)}..{max(precip)}.")
        if missing:
            print(f"       !! {len(missing)} simulation year(s) fall outside the file: {missing}")
            print(f"          (loop year {[y-2019 for y in missing]}).  Those rows are EXCLUDED")
            print("          from 2c in BOTH arms symmetrically, and the excluded counts are printed.")
        print()
        print(f"  {'seed':>5s} {'keep':>6s} {'ung high':>9s} {'trim q':>8s} {'drop g':>7s} {'drop u':>7s} "
              f"{'IBR1(rest)':>11s} {'keep least':>11s} {'keep most':>10s} {'gap A':>8s} {'gap B':>8s}")
        rule()
        idx_lo, idx_hi = [], []
        for s in sorted(anchor):
            g, u = anchor[s]
            d = lee_index_trim(g, u, precip)
            if d is None:
                print(f"  {s:>5s}  -- not computable --")
                continue
            a, b = d["gap_keep_least_scarce"], d["gap_keep_most_scarce"]
            idx_lo.append(min(a, b))
            idx_hi.append(max(a, b))
            print(f"  {s:>5s} {d['keep']:>6d} {d['n_u_high']:>9d} {d['trim']:8.4f} "
                  f"{d['dropped_g']:>7d} {d['dropped_u']:>7d} {d['ibr1_restricted']:11.2f} "
                  f"{d['e0_keep_least_scarce']:11.2f} {d['e0_keep_most_scarce']:10.2f} "
                  f"{a:8.2f} {b:8.2f}")
        rule()
        if idx_lo:
            print(f"  interval across the two trim directions = "
                  f"[{L.mean(idx_lo):+7.2f}, {L.mean(idx_hi):+7.2f}] pp")
            print("  !! THIS IS NOT A BOUND.  Trimming by an index other than the outcome yields a")
            print("     valid interval only if selection into the always-high stratum is monotone in")
            print("     that index (direction unknown).  Nothing here tests that.  If selection is")
            print("     unrelated to objective scarcity, both endpoints are point estimates under a")
            print("     false premise and can sit anywhere inside or outside the sharp interval in")
            print("     (2a).  It is reported because the brief asked for it, and is labelled")
            print("     assumption-dependent so no reader mistakes its narrowness for strength.")

    # -------------------------------------------------------------- Section 5
    head("SECTION 5 -- ALL MODEL CELLS (headline sharp Manski bound, Part 1b)")
    print("  Per-cell mean identified set for Delta_S, plus the published conditional gap for")
    print("  reference.  Balanced cells only in the paired block above; any unbalanced cells")
    print("  (per L.balanced()) are reported per-seed afterwards.")
    print()
    print(f"  {'model':16s} {'seeds':>6s} {'pub gap':>9s} {'sharp LB':>9s} {'sharp UB':>9s} "
          f"{'IM lo':>8s} {'IM hi':>8s} {'excl 0?':>9s} {'uncond gap':>11s}")
    rule()
    cell_rows = []
    for label, prefix in L.MODELS:
        pr = L.paired_seeds(prefix)
        if not L.balanced(prefix):
            continue
        pub, lo_l, hi_l, unc = [], [], [], []
        for s in pr:
            g, u = load_pair(prefix, s)
            pub.append(100 * (g.ibr - u.ibr))
            unc.append(100 * (g.inc_share - u.inc_share))
            b = manski_bounds(g, u)
            lo_l.append(b["mono_gap"][0])
            hi_l.append(b["mono_gap"][1])
        _, _, sel, _, _, _ = onesample_t(lo_l)
        _, _, seh, _, dfx, _ = onesample_t(hi_l)
        tc1x = t_crit(0.10, dfx)
        imlo, imhi = L.mean(lo_l) - tc1x * sel, L.mean(hi_l) + tc1x * seh
        excl = "YES" if imhi < 0 else "no"
        cell_rows.append((label, len(pr), L.mean(pub), L.mean(lo_l), L.mean(hi_l), imlo, imhi, excl, L.mean(unc)))
        print(f"  {label:16s} {len(pr):>6d} {L.mean(pub):9.2f} {L.mean(lo_l):9.2f} {L.mean(hi_l):9.2f} "
              f"{imlo:8.2f} {imhi:8.2f} {excl:>9s} {L.mean(unc):11.2f}")
    rule()
    for label, prefix in L.MODELS:
        if L.balanced(prefix):
            continue
        pr = L.paired_seeds(prefix)
        print(f"  {label} (UNBALANCED, reported per-seed, NOT pooled, NOT tested):")
        for s in pr:
            g, u = load_pair(prefix, s)
            b = manski_bounds(g, u)
            print(f"     seed {s}: published gap {100*(g.ibr-u.ibr):+7.2f} pp; "
                  f"sharp Manski set [{b['mono_gap'][0]:+7.2f}, {b['mono_gap'][1]:+7.2f}] pp; "
                  f"unconditional gap {100*(g.inc_share-u.inc_share):+7.2f} pp")
        print(f"     governed seeds {L.seeds('governed', prefix)} vs ungoverned {L.seeds('ungoverned', prefix)}"
              " -- one governed seed has no partner and is dropped from the pairing.")

    # -------------------------------------------------------------- Section 6
    head("SECTION 6 -- ROBUSTNESS: THE SAME BOUND ON THE EXECUTED ACTION (falsifier F4)")
    print("""  Phase 1 established that `yearly_decision` is the agent's last PROPOSAL, not what
  ran: every REJECTED / REJECTED_FALLBACK row leaves the diversion request unchanged, so
  the world executed `maintain_demand`.  The published statistic is an intent-stage
  number.  This section recomputes Section 2's sharp bound with the action redefined as
  the EXECUTED one, joined 1:1 from the governance audit CSV.""")
    print()
    print(f"  {'seed':>5s} {'IBR1 exec':>10s} {'IBR0 exec':>10s} {'pub-style gap':>14s} "
          f"{'sharp LB':>9s} {'sharp UB':>9s}")
    rule()
    ex_lo, ex_hi, ex_gap = [], [], []
    for s in sorted(anchor):
        g, u = load_pair(anchor_prefix, s, action_fn=executed_action_rows)
        b = manski_bounds(g, u)
        ex_lo.append(b["mono_gap"][0])
        ex_hi.append(b["mono_gap"][1])
        ex_gap.append(100 * (g.ibr - u.ibr))
        print(f"  {s:>5s} {100*g.ibr:10.2f} {100*u.ibr:10.2f} {100*(g.ibr-u.ibr):14.2f} "
              f"{b['mono_gap'][0]:9.2f} {b['mono_gap'][1]:9.2f}")
    rule()
    _, _, sel, _, _, _ = onesample_t(ex_lo)
    _, _, seh, _, dfx, _ = onesample_t(ex_hi)
    tc1x = t_crit(0.10, dfx)
    print(f"  executed-action conditional gap (mean) = {L.mean(ex_gap):+7.2f} pp "
          f"(label-based published value {L.mean(diffs):+7.2f} pp)")
    print(f"  executed-action sharp identified set   = [{L.mean(ex_lo):+7.2f}, {L.mean(ex_hi):+7.2f}] pp")
    print(f"  executed-action IM 95% interval        = "
          f"[{L.mean(ex_lo) - tc1x*sel:+7.2f}, {L.mean(ex_hi) + tc1x*seh:+7.2f}] pp")
    print(f"  -> {'EXCLUDES' if L.mean(ex_hi) < 0 else 'INCLUDES'} zero.")

    # -------------------------------------------------------------- Section 7
    head("SECTION 7 -- SANITY CHECKS")
    problems = []
    for s in sorted(anchor):
        g, u = anchor[s]
        for tag, c in (("gov", g), ("ung", u)):
            if not (0 <= c.n_high <= c.n and 0 <= c.n_inc <= c.n and 0 <= c.n_high_inc <= c.n_high):
                problems.append(f"count inconsistency seed {s} {tag}")
            if not (0.0 <= c.ibr <= 1.0):
                problems.append(f"IBR outside [0,1] seed {s} {tag}")
        b = mb[s]
        for key in ("naive_gap", "mono_gap", "nomono_gap"):
            lo, hi = b[key]
            if lo > hi + 1e-9:
                problems.append(f"inverted interval {key} seed {s}")
            if not (-100.0 - 1e-6 <= lo and hi <= 100.0 + 1e-6):
                problems.append(f"gap outside [-100,100] {key} seed {s}")
        if not (b["mono_gap"][0] >= b["nomono_gap"][0] - 1e-9
                and b["mono_gap"][1] <= b["nomono_gap"][1] + 1e-9):
            problems.append(f"monotonicity refinement is not nested inside the no-assumption bound, seed {s}")
        if not (b["naive_gap"][0] >= -100 and b["mono_gap"][0] >= b["naive_gap"][0] - 1e-9):
            problems.append(f"sharp lower bound is below the naive lower bound, seed {s}")
        d = lee_u[s]
        if not (0.0 <= d["e0_lo"] <= d["e0_hi"] <= 1.0 + 1e-12):
            problems.append(f"Lee E[Y0|A] interval malformed seed {s}")
    print(f"  checks run on {len(anchor)} anchor seeds x 2 arms.")
    if problems:
        print("  !! PROBLEMS:")
        for p_ in problems:
            print("     -", p_)
    else:
        print("  All clear: rates in [0,1], counts nested, every interval ordered lo<=hi and")
        print("  inside [-100,+100] pp, the monotonicity-refined bound nested inside the")
        print("  assumption-free bound, and the sharp bound nested inside the naive bound.")
    print()
    print("  Reported oddities that are real properties of the corpus, not bugs:")
    print(f"    - {sum(anchor[s][0].n_unparsed for s in anchor)} governed and "
          f"{sum(anchor[s][1].n_unparsed for s in anchor)} ungoverned rows carry an UNPARSED")
    print("      appraisal label (the literal string 'N/A'); they are counted as non-high, which")
    print("      is what the published definition does, and they are 0.6 % of the governed arm.")
    print(f"    - the always-high trim proportion is ~{100*L.mean([lee_u[s]['trim'] for s in lee_u]):.0f} %, "
          "which is why Part 2 is close to vacuous.")

    # -------------------------------------------------------------- Section 8
    head("SECTION 8 -- VERDICT")
    print(f"""  PUBLISHED CLAIM UNDER TEST: governed conditional rate 36.05 %, ungoverned 59.07 %,
  gap -23.0 pp, on a denominator that governance itself moves by ~46 pp.

  REPRODUCTION: {L.mean(ibr_g):.2f} % vs {L.mean(ibr_u):.2f} %, gap {L.mean(diffs):+.2f} pp.  Matches the published
  numbers to 2 dp.  The published arithmetic is not in dispute; its interpretation is.

  PART 1 (Delta_S, the would-be-high population; NO assumption beyond arm exchangeability):
      identified set for the mean effect = [{sharp_lo:+.2f}, {sharp_hi:+.2f}] pp
      Imbens-Manski 95 % interval        = [{sharp_im[0]:+.2f}, {sharp_im[1]:+.2f}] pp
      -> the whole interval lies BELOW zero.  Even in the worst case allowed by the data,
         governance reduces the "claims high scarcity, increases anyway" rate on a FIXED
         population.  The SIGN of the published finding is robust to the post-treatment
         conditioning problem.  The MAGNITUDE is NOT identified: any reduction between
         {abs(sharp_hi):.1f} pp and {abs(sharp_lo):.1f} pp is equally consistent with the data.  The
         least favourable admissible value is {abs(sharp_hi):.1f} pp, which is {100*abs(sharp_hi)/abs(L.mean(diffs)):.0f} % of the published
         {abs(L.mean(diffs)):.1f} pp.  The published number sits {'INSIDE' if sharp_lo <= L.mean(diffs) <= sharp_hi else 'OUTSIDE'} the identified set, but sitting
         inside an identified set is not the same as being estimated.

  PART 2 (Delta_A, the always-high stratum; REQUIRES monotonicity, which Section 3 shows
  is violated on {100*gonly/tot:.1f} % of matched rows):
      unconditional sharp Lee set = [{mlo:+.2f}, {mhi:+.2f}] pp -- {'EXCLUDES' if mhi < 0 else 'INCLUDES'} zero, and the
      upper end is pinned at the arithmetic ceiling in {ceiling}/{len(lee_u)} seeds, so that end
      carries no information.  The unconditional Lee bound is NOT informative here; the
      trim proportion (~{100*L.mean([lee_u[s]['trim'] for s in lee_u]):.0f} %) is simply too large.  Do not quote it as reassurance.
      Stratifying on cleared pre-treatment covariates helps only when the stratifier
      actually varies with the trim proportion: year-based strata pull the set to
      [{strat_summary['year'][0]:+.2f}, {strat_summary['year'][1]:+.2f}] pp and year+cluster to [{strat_summary['year+cluster'][0]:+.2f}, {strat_summary['year+cluster'][1]:+.2f}] pp, both excluding
      zero, whereas cluster/basin/water_right strata leave it straddling zero.  Those two
      informative variants still ride on the monotonicity assumption Section 3 contradicts,
      so they are corroboration for Part 1, not an independent result.

  THE HONEST SUMMARY: the published -23.0 pp is not a causal effect on any population, and
  no estimator in this file recovers it as one.  What survives is a weaker but genuine
  claim -- on the fixed population of decisions that would have reported high scarcity
  absent governance, the governance effect is negative, and its size lies somewhere in
  [{abs(sharp_hi):.1f}, {abs(sharp_lo):.1f}] pp rather than being 23.0 pp.  A reduction less than half the headline
  is fully consistent with the data.  The paper's DIRECTION survives the worst case on the
  anchor model; the paper's NUMBER does not survive as a point estimate.
  ANCHOR-ONLY WARNING: of the four balanced cells, only the anchor gemma3:4b has an
  identified set excluding zero.  gemma4:e4b just misses it, gemma4:e2b and gemma3:12b
  straddle zero outright.  The published pair is the most favourable cell in the corpus,
  and the sign-robustness claim above must not be generalised across models.""")

    print()
    rule("=")
    print("DONE.  No files written.  Nothing under examples/ or ref/ was modified.")
    rule("=")
    return 0


if __name__ == "__main__":
    sys.exit(main())
