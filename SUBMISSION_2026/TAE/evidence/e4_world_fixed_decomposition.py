"""Reweight on recorded world state, and the appraisal shift becomes small.

WHAT THIS SHOWS
The conformance statistic conditions on the agent's self-reported scarcity appraisal, and that
appraisal's prevalence differs between arms by ~46 pp. This script asks WHERE that difference comes
from, and answers it by direct decomposition rather than by inference.

Stratify on the world state the agent is reporting about -- shortage tier, reservoir elevation,
drought index, all recorded by the simulator and not by the language model -- and compare the two
arms within each stratum, reweighting to a common stratum distribution. This is a descriptive
composition decomposition; those world variables are downstream of validator status in the coupled
simulation and are not treated as causal covariates.

RESULT: the residual falls from +45.7 pp to roughly zero under this reweighting. The analysis does
not establish equal reporting probabilities within every world state. What differs is which world
states each arm occupies: the governed arm spends most of its run in no-shortage conditions and the
no-validator arm in severe shortage. The result is consistent with a large world-composition
contribution, while within-world reporting and treatment-affected selection remain unresolved.

WHAT WOULD CHALLENGE THE DESCRIPTIVE READING
A large residual of consistent sign after reweighting would be compatible with governed agents
reporting different appraisals across the observed world strata, as premise revision might predict.
There is none in this corpus, and at coarse strata the residual runs slightly the other way; this does
not prove equal reporting within every world.

A NEGATIVE RESULT THIS SCRIPT ALSO RECORDS
The hypothesis that world-conditioned norms automatically escape the pathology is not supported here.
Reported below: the
prevalence of every world-state antecedent shifts between arms by as much as the self-report does,
or more (shortage_tier >= 2 shifts +64 pp against the self-report's +46 pp). In a coupled system the
world is downstream of the treatment too. The distinction that survives is not which variable the
norm reads, but whether the shift can be DECOMPOSED -- which requires the world state to be recorded
independently of the generation being governed.

HONEST LIMIT
Fine strata cover only part of the corpus, because a stratum needs enough rows in BOTH arms to
support a comparison. Coverage is printed for every stratification and must be quoted with the
residual. Coarse strata cover 100% and give ~-2.5 pp; fine strata cover about half and give ~0.
Both are far below +45.7, which is the finding.

WHAT PART 2 REPORTS BESIDE THE RESIDUAL (added 2026-08-02)
A residual quoted against a raw gap that carries an interval needs the same furniture the raw gap
has. Part 2 therefore prints, for every rung of the ladder:
  - the number of comparable strata and the per-arm cell counts (min / median / max), so a reader
    can see for themselves that the fine strata are thin rather than take the word "thin" on trust;
  - the weighting scheme by name. Every residual is descriptive direct standardisation. The headline
    column reweights to the POOLED stratum distribution (both arms' rows in the comparable strata). The
    two columns beside it repeat the calculation on the governed arm's own distribution and on the
    no-validator arm's, which is the index-number ambiguity made visible instead of hidden;
  - a 95% confidence interval. The seed is the inferential unit, so the residual is recomputed
    inside each seed and the interval is a paired t interval across the five, df = n-1. A seed with
    no comparable stratum of its own contributes nothing and is named; a rung on which too few
    seeds survive prints NO interval and says why, rather than a bare number.

WHICH CELL THIS RUNS ON (added 2026-08-03)
The decomposition needs the simulator-recorded world columns, which live in ``simulation_log.csv``
and are written by the model-independent simulator, so the analysis is not specific to the anchor.
It defaults to the anchor, gemma3:4b, and that default is byte-identical to what this script printed
before it was parameterised. Pass a cell label to run the same ladder on another model:

    python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py                # gemma3:4b
    python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py gemma4:e4b
    python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py gemma4:e2b

Only cells whose two arms carry five paired seeds and the full world-column set are listed in
``CELLS``; a label outside that allow-list is refused rather than globbed for.

Usage:  python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py [cell]
"""
from __future__ import annotations

import csv
import glob
import math
import os
import re
import statistics as st
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HIGH = {"H", "VH"}
MIN_CELL = 40          # a stratum needs this many rows in BOTH arms to be comparable
T_CRIT_DF4 = 2.776     # two-sided 95%, df = 4
# Two-sided 95% t, df = 1..9. The pooled analysis has 5 seeds (df = 4, 2.776); the table lets a
# rung that loses a seed report the wider interval its own df earns instead of borrowing df = 4.
T_CRIT = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
          6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}
# The per-seed analogue of MIN_CELL. The pooled tabulation stacks 5 seeds, so a stratum that clears
# 40 pooled rows clears 8 in the average seed. Stated rather than tuned: it is MIN_CELL / n_seeds.
MIN_CELL_SEED = 8
MIN_SEEDS_FOR_CI = 3   # below this, print no interval and say which seeds were too thin

#: label -> (directory infix, banner text). ALLOW-LIST, written out literally: a cell is reachable
#: only by naming it here, never by globbing whatever happens to sit in the results directory. The
#: anchor's infix is "" and its banner is the exact string this script printed before it took an
#: argument, so the default run is byte-identical.
CELLS = {
    "gemma3:4b":  ("",            "anchor cell gemma3:4b"),
    "gemma4:e2b": ("gemma4_e2b_", "cell gemma4:e2b (replication; anchor is gemma3:4b)"),
    "gemma4:e4b": ("gemma4_e4b_", "cell gemma4:e4b (replication; anchor is gemma3:4b)"),
    # Added 2026-08-03. These two carry 3 paired seeds rather than 5, so their
    # per-seed intervals are wider and a residual near the gate should be read
    # with that in mind -- but running the decomposition on them costs no GPU
    # time, and reporting the mechanism on 3 of 5 cells while 2 sit unexamined
    # invites exactly the question this replication exists to answer.
    "gemma3:12b": ("gemma3_12b_",   "cell gemma3:12b (replication; anchor is gemma3:4b)"),
    # ministral3:8b becomes usable only when its third no-validator seed lands;
    # until then _runs() sees 3 governed against 2 and the arms are unpaired.
    "ministral3:8b": ("ministral3_8b_", "cell ministral3:8b (replication; anchor is gemma3:4b)"),
}
DEFAULT_CELL = "gemma3:4b"


def _runs(arm: str, prefix: str = "") -> dict:
    out = {}
    for p in glob.glob(os.path.join(
            REPO, f"examples/irrigation_abm/results/{arm}_v21_42yr_{prefix}seed*")):
        m = re.search(r"seed(\d+)$", os.path.basename(p))
        if m and os.path.exists(os.path.join(p, "simulation_log.csv")):
            out[m.group(1)] = p
    if not out:
        raise SystemExit(
            f"no {arm} runs found for prefix {prefix!r} under examples/irrigation_abm/results/")
    return out


def _load(path: str) -> list:
    with open(os.path.join(path, "simulation_log.csv"), encoding="utf-8-sig", newline="") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("yearly_decision") or "").strip()]


def _is_high(row: dict) -> bool:
    return (row.get("wsa_label") or "").strip().upper() in HIGH


def _paired_ci(deltas):
    """Mean and two-sided 95% t interval, df = n-1. n = 5 gives t = 2.776, unchanged."""
    m = st.mean(deltas)
    if len(deltas) < 2:
        return m, float("nan"), float("nan")
    t = T_CRIT.get(len(deltas) - 1, T_CRIT_DF4)
    se = st.stdev(deltas) / math.sqrt(len(deltas))
    return m, m - t * se, m + t * se


# --------------------------------------------------------------------------- part 1
def part1_antecedent_shift(gov, ung, seeds):
    """Every antecedent's prevalence shifts. The world's shifts as much as the self-report's."""
    defs = [
        ("SELF-REPORT  WSA in {H,VH}", _is_high),
        ("world  shortage_tier >= 1", lambda r: float(r["shortage_tier"]) >= 1),
        ("world  shortage_tier >= 2", lambda r: float(r["shortage_tier"]) >= 2),
        ("world  curtailment_ratio > 0", lambda r: float(r["curtailment_ratio"]) > 0),
        ("world  drought_index >= 0.5", lambda r: float(r["drought_index"]) >= 0.5),
    ]
    print("PART 1 — does the pathology avoid world-conditioned antecedents?  NO.\n")
    print(f"  {'antecedent':30s} {'prev|gov':>9s} {'prev|noval':>11s} {'SHIFT':>8s}   95% CI")
    print("  " + "-" * 78)
    rows = []
    for label, cond in defs:
        pg, pu = [], []
        for s in seeds:
            for src, acc in ((gov, pg), (ung, pu)):
                rs = _load(src[s])
                acc.append(100.0 * sum(1 for r in rs if cond(r)) / len(rs))
        m, lo, hi = _paired_ci([b - a for a, b in zip(pg, pu)])
        print(f"  {label:30s} {st.mean(pg):8.2f}% {st.mean(pu):10.2f}% {m:+8.2f}   "
              f"[{lo:+6.2f}, {hi:+6.2f}]")
        rows.append((label, m))
    self_shift = rows[0][1]
    worst_world = max(r[1] for r in rows[1:])
    print(f"\n  CLAIM world_antecedents_shift_too: self-report {self_shift:+.2f} pp, "
          f"largest world antecedent {worst_world:+.2f} pp.")
    print("  The world is downstream of the treatment in a coupled system, so conditioning on it")
    print("  is NOT a repair. What survives is decomposability, which Part 2 demonstrates.\n")
    return self_shift, worst_world


# --------------------------------------------------------------------------- part 2
def _tabulate(paths, keyfn):
    acc = {}
    for p in paths:
        for r in _load(p):
            k = keyfn(r)
            n, h = acc.get(k, (0, 0))
            acc[k] = (n + 1, h + (1 if _is_high(r) else 0))
    return acc


def _standardised_residual(G, U, keys, scheme):
    """Descriptive reweighting of both arms onto ONE stratum distribution.

    scheme = 'pooled' uses both arms' rows in the comparable strata, which is the scheme every
    number this script has ever printed uses. 'gov' and 'noval' use one arm's own distribution;
    they exist so the index-number ambiguity is a printed sensitivity rather than a hidden choice.
    """
    if scheme == "pooled":
        w = {k: G[k][0] + U[k][0] for k in keys}
    elif scheme == "gov":
        w = {k: G[k][0] for k in keys}
    elif scheme == "noval":
        w = {k: U[k][0] for k in keys}
    else:
        raise ValueError(f"unknown weighting scheme {scheme!r}")
    tw = sum(w.values())
    sg = sum(w[k] / tw * (100.0 * G[k][1] / G[k][0]) for k in keys)
    su = sum(w[k] / tw * (100.0 * U[k][1] / U[k][0]) for k in keys)
    return su - sg


def _per_seed_residuals(gov, ung, seeds, keyfn):
    """The residual recomputed inside each seed, which is the inferential unit.

    Each seed is standardised on its OWN pooled stratum distribution over the strata that clear
    MIN_CELL_SEED in both of that seed's arms. A seed with no comparable stratum contributes
    nothing and is returned in the thin list by name, never silently dropped.
    """
    vals, thin, covers = [], [], []
    for s in seeds:
        G, U = _tabulate([gov[s]], keyfn), _tabulate([ung[s]], keyfn)
        common = [k for k in set(G) & set(U)
                  if G[k][0] >= MIN_CELL_SEED and U[k][0] >= MIN_CELL_SEED]
        if not common:
            thin.append(s)
            continue
        vals.append(_standardised_residual(G, U, common, "pooled"))
        covers.append(100.0 * sum(G[k][0] for k in common) / sum(v[0] for v in G.values()))
    return vals, thin, covers


def part2_hold_world_fixed(gov, ung, seeds):
    """Standardise on a COMMON stratum distribution; report the residual and the coverage."""
    strata = [
        ("shortage tier", lambda r: (r["shortage_tier"],)),
        ("tier + curtailment", lambda r: (r["shortage_tier"],
                                          f'{float(r["curtailment_ratio"]):.2f}')),
        ("tier + Mead elevation (25 ft)", lambda r: (r["shortage_tier"],
                                                     int(float(r["lake_mead_level"]) // 25))),
        ("tier + Mead (10 ft) + drought decile", lambda r: (r["shortage_tier"],
                                                            int(float(r["lake_mead_level"]) // 10),
                                                            int(float(r["drought_index"]) * 10))),
        ("tier + Mead + drought + agent cluster", lambda r: (r["shortage_tier"],
                                                             int(float(r["lake_mead_level"]) // 10),
                                                             int(float(r["drought_index"]) * 10),
                                                             r["cluster"])),
    ]
    gp = [gov[s] for s in seeds]
    up = [ung[s] for s in seeds]
    raw_g = _tabulate(gp, lambda r: ("all",))
    raw_u = _tabulate(up, lambda r: ("all",))
    raw = (100.0 * raw_u[("all",)][1] / raw_u[("all",)][0]
           - 100.0 * raw_g[("all",)][1] / raw_g[("all",)][0])
    print("PART 2 — reweight on recorded world state, and the shift becomes small.\n")
    print(f"  Raw, world NOT held fixed:  gov {100.0*raw_g[('all',)][1]/raw_g[('all',)][0]:.2f}%  "
          f"vs noval {100.0*raw_u[('all',)][1]/raw_u[('all',)][0]:.2f}%   ->   SHIFT {raw:+.2f} pp\n")
    print("  WEIGHTING SCHEME, stated rather than implied. Every residual below is DESCRIPTIVE DIRECT")
    print("  STANDARDISATION: each arm's within-stratum HIGH-appraisal rate is recombined under one")
    print("  common stratum distribution, so composition cannot leak back in. The headline column")
    print("  weights by the POOLED distribution — both arms' rows in the comparable strata, gov +")
    print("  noval. The next two columns repeat the same calculation weighting by the governed arm's")
    print("  own distribution and by the no-validator arm's. Three numbers per rung, because the")
    print("  choice of standard is a real ambiguity and hiding it behind one column would be a")
    print(f"  choice made silently. A stratum enters only if it holds >= {MIN_CELL} rows in BOTH arms.\n")

    # ---- 2a: the strata themselves. How many, how big, how much of the corpus they reach.
    print("  2a. STRATA AND PER-ARM CELL COUNTS  (n per comparable stratum, one arm at a time)\n")
    print(f"  {'reweighted by recorded world at':38s} {'strata':>6s} "
          f"{'n|gov  min/med/max':>26s} {'n|noval  min/med/max':>26s} "
          f"{'cov|gov':>8s} {'cov|nov':>8s}")
    print("  " + "-" * 118)
    prepared = []
    for name, keyfn in strata:
        G, U = _tabulate(gp, keyfn), _tabulate(up, keyfn)
        common = sorted(k for k in set(G) & set(U)
                        if G[k][0] >= MIN_CELL and U[k][0] >= MIN_CELL)
        if not common:
            print(f"  {name:38s} {'0':>6s}   (no comparable strata — nothing to report on this rung)")
            continue
        ng = sorted(G[k][0] for k in common)
        nu = sorted(U[k][0] for k in common)
        cov_g = 100.0 * sum(G[k][0] for k in common) / sum(v[0] for v in G.values())
        cov_u = 100.0 * sum(U[k][0] for k in common) / sum(v[0] for v in U.values())
        print(f"  {name:38s} {len(common):>6d} "
              f"{f'{ng[0]:,} / {int(st.median(ng)):,} / {ng[-1]:,}':>26s} "
              f"{f'{nu[0]:,} / {int(st.median(nu)):,} / {nu[-1]:,}':>26s} "
              f"{cov_g:>7.1f}% {cov_u:>7.1f}%")
        prepared.append((name, keyfn, G, U, common, ng, nu, cov_g, cov_u))
    print()
    print("  Read the min column, not the median. The two fine rungs rest on strata whose smallest")
    print("  comparable cell holds tens of decisions, and their per-stratum residuals scatter")
    print("  accordingly (range column in 2b). That thinness is the reason the coarse rungs, which")
    print("  cover the whole corpus, are quoted first in the manuscript.\n")

    # ---- 2b: the residual under three standards, its spread across strata, and its interval.
    print("  2b. RESIDUAL, THREE WEIGHTING SCHEMES, AND A 95% INTERVAL ACROSS SEEDS\n")
    print(f"  {'reweighted by recorded world at':38s} {'pooled-wt':>10s} {'gov-wt':>8s} {'noval-wt':>9s}   "
          f"{'per-stratum range':>19s}   {'per-seed mean':>13s}  {'95% CI':>18s}  seeds")
    print("  " + "-" * 128)
    residuals = []
    rows = []
    for name, keyfn, G, U, common, ng, nu, cov_g, cov_u in prepared:
        res = _standardised_residual(G, U, common, "pooled")
        res_g = _standardised_residual(G, U, common, "gov")
        res_u = _standardised_residual(G, U, common, "noval")
        per = [100.0 * U[k][1] / U[k][0] - 100.0 * G[k][1] / G[k][0] for k in common]
        vals, thin, covers = _per_seed_residuals(gov, ung, seeds, keyfn)
        if len(vals) >= MIN_SEEDS_FOR_CI:
            m, lo, hi = _paired_ci(vals)
            ci_s = f"[{lo:+7.2f},{hi:+7.2f}]"
            mean_s = f"{m:+13.2f}"
        else:
            m = lo = hi = float("nan")
            ci_s = f"{'NO INTERVAL':>18s}"
            mean_s = f"{'--':>13s}"
        print(f"  {name:38s} {res:>+10.2f} {res_g:>+8.2f} {res_u:>+9.2f}   "
              f"{f'[{min(per):+.1f} .. {max(per):+.1f}]':>19s}   {mean_s}  {ci_s}  "
              f"{len(vals)}/{len(seeds)}")
        if covers and len(vals) >= MIN_SEEDS_FOR_CI:
            print(f"  {'':38s} -> the interval's own coverage, seed by seed: "
                  f"{min(covers):.1f}-{max(covers):.1f}% of the governed arm, against {cov_g:.1f}% "
                  f"for the pooled row.")
        if thin:
            print(f"  {'':38s} -> seeds {', '.join(thin)} hold no stratum with "
                  f">= {MIN_CELL_SEED} rows in both arms; excluded from the interval, not imputed.")
        if len(vals) < MIN_SEEDS_FOR_CI:
            print(f"  {'':38s} -> TOO THIN FOR A PER-SEED INTERVAL ({len(vals)} of {len(seeds)} "
                  f"seeds usable, floor {MIN_SEEDS_FOR_CI}). This rung reports no interval.")
        residuals.append((name, res, cov_g))
        rows.append((name, len(common), ng, nu, cov_g, cov_u, res, res_g, res_u,
                     min(per), max(per), m, lo, hi, len(vals), thin, covers))
    print()
    print("  The per-seed column is a DIFFERENT estimator from the pooled-weight column beside it,")
    print("  not a bootstrap of it: it reweights each seed to that seed's own pooled distribution")
    print(f"  over strata clearing {MIN_CELL_SEED} rows per arm, then takes a paired t interval over the")
    print("  seeds (df = n-1). The two agree closely where the strata are thick and part where they")
    print("  are thin, which is the honest reading of a fine stratification on 3,276 rows per seed.\n")

    worst = max(abs(r) for _, r, _ in residuals)
    print(f"  CLAIM world_fixed_residual: |residual| <= {worst:.2f} pp at every resolution, against a")
    print(f"  raw shift of {raw:+.2f} pp. At the finest resolution the residual is "
          f"{residuals[-1][1]:+.2f} pp on {residuals[-1][2]:.1f}% coverage.")
    span = max(max(abs(r[6]), abs(r[7]), abs(r[8])) for r in rows)
    swing, swing_row = max((max(abs(r[7] - r[6]), abs(r[8] - r[6])), r[0]) for r in rows)
    print(f"  CLAIM world_fixed_residual_any_weighting: under ALL THREE weighting schemes and at all")
    print(f"  {len(rows)} resolutions the largest residual in absolute size is {span:.2f} pp.")
    print(f"  CLAIM world_fixed_weighting_sensitivity: switching the standard from the pooled")
    print(f"  distribution to either arm's own moves a residual by at most {swing:.2f} pp ({swing_row}).")
    print("  The choice of standard is therefore not carrying the result.")
    ci_rows = [r for r in rows if not math.isnan(r[12])]
    widest = max((max(abs(r[12]), abs(r[13])), r[0]) for r in ci_rows) if ci_rows else (float("nan"), "-")
    raw_vals = []
    for s in seeds:
        rg, ru = _load(gov[s]), _load(ung[s])
        raw_vals.append(100.0 * sum(1 for r in ru if _is_high(r)) / len(ru)
                        - 100.0 * sum(1 for r in rg if _is_high(r)) / len(rg))
    _, raw_lo, raw_hi = _paired_ci(raw_vals)
    print(f"  CLAIM world_fixed_residual_ci: {len(ci_rows)} of {len(rows)} rungs carry a per-seed 95%")
    print(f"  interval; the furthest any of those intervals reaches from zero is {widest[0]:.2f} pp")
    print(f"  ({widest[1]}), against the raw shift's own interval [{raw_lo:+.2f}, {raw_hi:+.2f}] pp,")
    print("  which does not come near zero at either end.")
    excl = [r for r in ci_rows if (r[12] > 0) == (r[13] > 0)]
    neg = [r for r in excl if r[13] < 0]
    print(f"  CLAIM world_fixed_residual_ci_signs: {len(excl)} of the {len(ci_rows)} intervals exclude")
    print(f"  zero, and {len(neg)} of those lie BELOW it. A residual below zero means the")
    print("  governed arm reports MORE scarcity after this reweighting, which is compatible with")
    print("  a composition contribution but not a within-world equality claim. Reported here rather than rounded")
    print("  to 'roughly zero': the reading the paper needs is that no residual approaches the raw")
    print("  shift, not that every one of them is indistinguishable from zero.")
    print("  Reading: the reweighted residual is small relative to the raw shift. This supports a")
    print("  composition contribution, but does not identify what the agent would report in an")
    print("  identical world or rule out treatment-affected selection.\n")
    return raw, residuals, rows


# --------------------------------------------------------------------------- part 3
def part3_where_each_arm_lives(gov, ung, seeds):
    """The composition itself, which is what the residual analysis leaves as the explanation."""
    print("PART 3 — the composition pattern behind the shift: the two arms occupy different worlds.\n")
    G = _tabulate([gov[s] for s in seeds], lambda r: (r["shortage_tier"],))
    U = _tabulate([ung[s] for s in seeds], lambda r: (r["shortage_tier"],))
    tg, tu = sum(v[0] for v in G.values()), sum(v[0] for v in U.values())
    print(f"  {'shortage tier':16s} {'decisions|gov':>14s} {'decisions|noval':>16s} {'share|gov':>11s} {'share|noval':>12s}")
    print("  " + "-" * 74)
    for k in sorted(set(G) | set(U)):
        ng = G.get(k, (0, 0))[0]
        nu = U.get(k, (0, 0))[0]
        print(f"  tier {k[0]:11s} {ng:>14,d} {nu:>16,d} {100.0*ng/tg:>10.1f}% {100.0*nu/tu:>11.1f}%")
    print("\n  CLAIM arms_occupy_different_worlds: the governed arm spends most of its run in the")
    print("  lowest shortage tier and the no-validator arm in the highest. That is the governance")
    print("  effect on the water system and a plausible source of the appraisal shift; it is not an\n")
    print("  exhaustive attribution of the observed contrast.\n")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) > 1:
        raise SystemExit(f"expected at most one cell label, got {argv}")
    cell = argv[0] if argv else DEFAULT_CELL
    if cell not in CELLS:
        raise SystemExit(f"unknown cell {cell!r}; expected one of {sorted(CELLS)}")
    prefix, banner = CELLS[cell]
    gov, ung = _runs("production", prefix), _runs("ungoverned", prefix)
    seeds = sorted(set(gov) & set(ung))
    if len(seeds) < 2:
        raise SystemExit(f"need >=2 paired seeds, found {seeds}")
    print("=" * 92)
    print("e4 — WORLD-FIXED DECOMPOSITION OF THE APPRAISAL SHIFT")
    print(f"{banner}, paired seeds {', '.join(seeds)}, "
          f"minimum {MIN_CELL} rows per arm per stratum")
    print("=" * 92 + "\n")
    part1_antecedent_shift(gov, ung, seeds)
    raw, residuals, rows = part2_hold_world_fixed(gov, ung, seeds)
    part3_where_each_arm_lives(gov, ung, seeds)

    worst = max(abs(r) for _, r, _ in residuals)
    ok = worst < 0.25 * abs(raw)
    # Same test, applied to the two alternative standards as well. It is the original gate widened
    # to the sensitivity, not a second gate with a different bar, and it passes on this corpus.
    span = max(max(abs(r[6]), abs(r[7]), abs(r[8])) for r in rows)
    ok_w = span < 0.25 * abs(raw)
    # Every rung that survives per-seed computation must carry an interval. A rung that quietly
    # lost its interval would put a bare number in Table 2, which is the objection being answered.
    n_ci = sum(1 for r in rows if not math.isnan(r[12]))
    ok_ci = n_ci == len(rows)
    print("=" * 92)
    print(f"VERDICT: {'HOLDS' if (ok and ok_w and ok_ci) else 'FAILS'} — the largest residual "
          f"({worst:.2f} pp) is {'below' if ok else 'NOT below'} a quarter of the raw shift "
          f"({abs(raw):.2f} pp).")
    print(f"  weighting sensitivity: largest residual under ANY of the three standards {span:.2f} pp, "
          f"{'below' if ok_w else 'NOT below'} the same bar.")
    print(f"  intervals: {n_ci} of {len(rows)} rungs carry a per-seed 95% interval"
          f"{'' if ok_ci else ' — a rung is reporting a residual with no interval'}.")
    print("=" * 92)
    return 0 if (ok and ok_w and ok_ci) else 1


if __name__ == "__main__":
    sys.exit(main())
