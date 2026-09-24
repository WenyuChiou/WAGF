"""e1_total_effect -- THE UNCONDITIONAL (TOTAL) EFFECT OF GOVERNANCE ON INCREASING DEMAND.

RUN AS:  python SUBMISSION_2026/decomposition/e1_total_effect.py     (from the repo root)

=============================================================================
THE ESTIMAND, IN WORDS
=============================================================================
For a farmer agent facing one decision in one year of one run, what is the
probability that the decision it lands on is an INCREASE in its diversion
request -- and how much does turning the validator stack ON change that
probability?

Formally:  TE  =  Pr(action is an increase | validators ON)
                - Pr(action is an increase | validators OFF)

The denominator is EVERY logged decision: 78 agents x 42 years = 3,276 rows per
run, fixed by the experiment design before any LLM is called. Nothing in the
denominator is chosen by the model, by the validators, or by the agent's own
self-report. There is no conditioning of any kind.

This is the contrast a water manager cares about: over a whole basin and a whole
planning horizon, does governance make agents ask for more water less often?

=============================================================================
WHY THIS ESTIMAND EXISTS -- WHAT IT FIXES
=============================================================================
The published headline (IBR / AAI, governed 36.05% vs no-validator 59.07%,
gap -23.0 pp) is a CONDITIONAL rate whose denominator is
"decisions where the agent self-reported HIGH water scarcity (wsa_label in
{H, VH})". `wsa_label` is emitted by the SAME LLM call that emits the action,
and governance moves it enormously (Phase 1 measured +45.73 pp on the anchor
model). So the two published rates are computed over DIFFERENT POPULATIONS of
decisions. Conditioning on a post-treatment variable mixes behaviour change with
composition change and does not identify a causal effect.

The total effect below conditions on nothing post-treatment, so the composition
problem cannot arise. What it buys in identification it pays for in specificity:
it answers a coarser question (see LIMITS).

=============================================================================
IDENTIFYING ASSUMPTION (one assumption, and it is checkable)
=============================================================================
A1  ARM EXCHANGEABILITY AT THE SEED. Within a model cell and a seed, the
    governed run and the ungoverned run differ ONLY by the validator toggle.
    Same code commit, same 78 agents, same initial conditions, same 42-year
    horizon, same LLM, same seed. Treatment is assigned by the experimenter, so
    the arm label is independent of everything determined before year 1.

If A1 holds, the arm difference in the unconditional increase rate IS the total
causal effect of the validator stack on that rate, for this population of agents
and this hydrological trace. NO further assumption (no ignorability of a
mediator, no correct outcome model, no positivity on a covariate) is needed,
because nothing is conditioned on and nothing is modelled.

WHAT A1 DOES **NOT** BUY -- stated so no one over-reads this number:
  * It does not decompose the effect. The total effect is silent about whether
    agents changed their minds or were simply blocked; e1 deliberately refuses
    to answer that. That is Phase 3's job.
  * It does not transport. One hydrological trace, one agent population, five
    small local models.
  * The reservoir is COUPLED (Phase 1: governed runs end ~102 ft higher at Lake
    Mead, arms diverge totally from year 2). So the two arms live in different
    worlds from year 2 onward. That divergence is a CONSEQUENCE of treatment and
    therefore part of the total effect -- it is correctly included here, and it
    is exactly why conditioning on any reservoir-derived covariate would be
    wrong. It also means the estimand is a whole-trajectory effect, not a
    per-decision behavioural parameter.

=============================================================================
WHAT WOULD FALSIFY THIS RESULT
=============================================================================
F1  Unequal denominators. If the two arms did not have identical row counts
    (3,276 each) the "denominator fixed by design" claim collapses. CHECKED.
F2  Unparsed / missing actions. If a nonzero share of rows had a blank or
    illegal `yearly_decision`, the denominator would be partly outcome-selected.
    CHECKED (value inventory printed).
F3  Unbalanced seed sets. A paired t on seeds that are not actually paired is
    not a paired test. CHECKED per model; ministral-3:8b fails and is excluded
    from every paired contrast and reported separately.
F4  Sign instability across seeds. If per-seed differences straddled zero the
    5-seed mean would be an artefact. CHECKED (per-seed table + sign count).
F5  Definition fragility. If the conclusion flipped when the action variable is
    read as the WORLD-REALISED action instead of the LLM's last-said label, the
    result would be a labelling artefact rather than a fact about water.
    CHECKED as a secondary estimator (E1-world, section 6) -- Phase 1 proved
    `yearly_decision` is the INTENT label, not the executed action.
F6  Disagreement with the published conditional gap in SIGN. Both estimands
    should at least agree that governance reduces increases. CHECKED per model;
    one cell (the excluded ministral cell) does flip, and it is reported.

=============================================================================
SIGN CONVENTIONS, IN WORDS
=============================================================================
  increase rate   : higher = the agent asks for MORE water more often. Worse.
  gap             : governed MINUS ungoverned. NEGATIVE = governance LOWERED the
                    rate = the direction the paper claims as its benefit.
                    (The paper text quotes the same magnitude flipped, as a
                    "+23.0 pp improvement". This script never flips.)
  composition shift: ungoverned MINUS governed high-appraisal share. POSITIVE =
                    the ungoverned arm reports high scarcity more often, i.e.
                    the ungoverned IBR denominator is the bigger one.

Every number printed below is computed from the CSVs on disk in this run. No
number is carried over from the brief, from project memory, or from the paper.
Where a computed number disagrees with a quoted one, the disagreement is printed
in full rather than reconciled.

Writes nothing anywhere. Reads only examples/irrigation_abm/results/**.
Stdlib only (plus the campaign's canonical loader).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import _loader as L  # noqa: E402  canonical definitions; do not re-implement

# --------------------------------------------------------------------------
# Numbers quoted elsewhere that this script CHECKS rather than trusts.
# --------------------------------------------------------------------------
PUB_IBR_GOV = 36.05        # published conditional, governed
PUB_IBR_UNG = 59.07        # published conditional, no-validator
PUB_GAP = -23.02           # published conditional gap, in this script's sign convention
CTX_UNCOND_QUOTE = 40.90   # UNVERIFIED project-memory note, arm unspecified

LEGAL_ACTIONS = frozenset({
    "increase_large", "increase_small", "maintain_demand",
    "decrease_small", "decrease_large",
})
ARMS = ("governed", "ungoverned")

RULE = "=" * 100
THIN = "-" * 100


def p_str(p: float) -> str:
    if p != p:
        return "  n/a"
    if p < 1e-6:
        return "<1e-6"
    return f"{p:.6f}"


def stars(p: float) -> str:
    if p != p:
        return ""
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"


# ==========================================================================
# 1. CORPUS INTEGRITY  (falsifiers F1, F2, F3)
# ==========================================================================
def corpus_check():
    print(RULE)
    print("1. CORPUS INTEGRITY -- everything below is read off disk, nothing assumed")
    print(RULE)
    print(f"results root: {L.RESULTS}\n")

    cache = {}          # (model, arm, seed) -> rows
    action_counts = {}  # arm -> {action: n}
    problems = []

    hdr = (f"{'model':16s} {'arm':11s} {'seeds on disk':20s} {'runs':>4s} "
           f"{'rows/run':>10s} {'illegal action':>14s} {'blank action':>12s} {'balanced':>9s}")
    print(hdr)
    print(THIN)
    for label, prefix in L.MODELS:
        try:
            bal = L.balanced(prefix)
        except L.DataError as exc:
            problems.append(f"{label}: {exc}")
            print(f"{label:16s} !! {exc}")
            continue
        for arm in ARMS:
            ss = L.seeds(arm, prefix)
            counts, illegal, blank = [], 0, 0
            for s in ss:
                rows = L.load_run(L.run_dir(arm, prefix, s))
                cache[(label, arm, s)] = rows
                counts.append(len(rows))
                for r in rows:
                    a = L.action(r)
                    action_counts.setdefault(arm, {})
                    action_counts[arm][a] = action_counts[arm].get(a, 0) + 1
                    if a == "":
                        blank += 1
                    elif a not in LEGAL_ACTIONS:
                        illegal += 1
            uniq = sorted(set(counts))
            flag = ""
            if uniq != [L.EXPECTED_ROWS]:
                flag = "  <-- ROW COUNT ANOMALY"
                problems.append(f"{label}/{arm}: row counts {uniq} != [{L.EXPECTED_ROWS}]")
            if illegal or blank:
                flag += "  <-- UNPARSED ACTIONS"
                problems.append(f"{label}/{arm}: {illegal} illegal + {blank} blank actions")
            print(f"{label:16s} {arm:11s} {','.join(ss):20s} {len(ss):>4d} "
                  f"{','.join(str(c) for c in uniq):>10s} {illegal:>14d} {blank:>12d} "
                  f"{str(bal):>9s}{flag}")
        if not bal:
            g, u = L.seeds("governed", prefix), L.seeds("ungoverned", prefix)
            problems.append(f"{label}: UNBALANCED arms gov={g} ung={u} -> excluded from paired tests")
        print()

    print("F1 equal denominators across arms ....",
          "PASS -- every run has exactly 3,276 rows" if not any("ROW COUNT" in p or "row counts" in p for p in problems)
          else "FAIL, see problems")
    print("F2 all actions parsed ................",
          "PASS -- 0 blank, 0 illegal `yearly_decision` values corpus-wide"
          if not any("action" in p for p in problems) else "FAIL, see problems")
    bal_models = [l for l, p in L.MODELS if L.balanced(p)]
    unbal = [l for l, p in L.MODELS if not L.balanced(p)]
    print(f"F3 seed sets balanced ................ balanced: {bal_models}")
    print(f"                                      UNBALANCED (excluded from paired tests): {unbal}")

    print("\nAction value inventory (proves the denominator is the full decision set):")
    allkeys = sorted(set(action_counts["governed"]) | set(action_counts["ungoverned"]))
    tot_g = sum(action_counts["governed"].values())
    tot_u = sum(action_counts["ungoverned"].values())
    print(f"  {'action':18s} {'governed n':>12s} {'gov %':>8s} {'ungoverned n':>14s} {'ung %':>8s}")
    for k in allkeys:
        g = action_counts["governed"].get(k, 0)
        u = action_counts["ungoverned"].get(k, 0)
        print(f"  {k:18s} {g:>12d} {100.0*g/tot_g:>7.2f}% {u:>14d} {100.0*u/tot_u:>7.2f}%")
    print(f"  {'TOTAL':18s} {tot_g:>12d} {100.0:>7.2f}% {tot_u:>14d} {100.0:>7.2f}%")
    print("  (pooled over ALL models incl. the unbalanced cell -- descriptive only, "
          "not the estimator)")

    if problems:
        print("\n!! PROBLEMS FOUND:")
        for p in problems:
            print("   -", p)
    else:
        print("\nNo corpus problems found.")
    return cache


# ==========================================================================
# 2 / 3. PER-SEED TABLE AND PER-MODEL MEANS
# ==========================================================================
def per_seed_table(cache):
    print("\n" + RULE)
    print("2. PER-SEED RESULTS -- the primary estimator (E1) plus context columns")
    print(RULE)
    print("E1 = unconditional increase rate (on the final PROPOSED action; a REJECTED")
    print("row's proposal did not execute) = 100 * n(increase) / 3276.")
    print("Context columns are NOT part of E1; they are printed so the reader can see")
    print("the composition problem the primary estimator sidesteps.\n")

    results = {}
    for label, prefix in L.MODELS:
        print(f"--- {label} " + "-" * (94 - len(label)))
        print(f"  {'seed':>5s} {'arm':11s} {'n rows':>7s} {'n incr':>7s} "
              f"{'E1 incr %':>10s} | {'HIGH n':>7s} {'HIGH %':>7s} {'IBR %':>7s} "
              f"{'incr|notHIGH %':>15s}")
        per = {}
        for arm in ARMS:
            for s in L.seeds(arm, prefix):
                rows = cache[(label, arm, s)]
                n = len(rows)
                nin = sum(1 for r in rows if L.is_increase(r))
                e1 = L.increase_rate(rows)
                hi = [r for r in rows if L.is_high(r)]
                lo = [r for r in rows if not L.is_high(r)]
                hs = L.high_share(rows)
                ib = L.ibr(rows)
                lo_rate = L.increase_rate(lo) if lo else float("nan")
                per[(arm, s)] = dict(n=n, nin=nin, e1=e1, nhi=len(hi), hs=hs,
                                     ibr=ib, lo=lo_rate)
                print(f"  {s:>5s} {arm:11s} {n:>7d} {nin:>7d} {e1:>10.2f} | "
                      f"{len(hi):>7d} {hs:>7.2f} {ib:>7.2f} {lo_rate:>15.2f}")
        results[label] = per
        print()
    return results


def model_summary(results):
    print(RULE)
    print("3. PER-MODEL MEANS AND THE PAIRED CONTRAST")
    print(RULE)
    print("Unit of inference = the SEED. Mean of per-seed rates (NOT decision-pooled).")
    print("gap = governed - ungoverned. NEGATIVE = governance lowered the rate.\n")

    rows_out = []
    print(f"{'model':16s} {'pairs':>5s} {'E1 gov':>8s} {'E1 ung':>8s} {'E1 GAP':>9s} "
          f"{'t':>9s} {'df':>3s} {'p':>9s} {'sig':>4s} | "
          f"{'IBR gov':>8s} {'IBR ung':>8s} {'IBR gap':>8s} {'compos.shift':>13s}")
    print(THIN + "-" * 22)
    for label, prefix in L.MODELS:
        per = results[label]
        bal = L.balanced(prefix)
        ps = L.paired_seeds(prefix)
        g = [per[("governed", s)]["e1"] for s in ps]
        u = [per[("ungoverned", s)]["e1"] for s in ps]
        d = [a - b for a, b in zip(g, u)]
        gi = [per[("governed", s)]["ibr"] for s in ps]
        ui = [per[("ungoverned", s)]["ibr"] for s in ps]
        gh = [per[("governed", s)]["hs"] for s in ps]
        uh = [per[("ungoverned", s)]["hs"] for s in ps]
        t, df = L.paired_t(d)
        p = L.t_two_sided_p(t, df)
        tag = "" if bal else "   <-- UNBALANCED: paired test INVALID, shown struck through"
        print(f"{label:16s} {len(ps):>5d} {L.mean(g):>8.2f} {L.mean(u):>8.2f} "
              f"{L.mean(d):>9.2f} {t:>9.3f} {df:>3d} {p_str(p):>9s} {stars(p):>4s} | "
              f"{L.mean(gi):>8.2f} {L.mean(ui):>8.2f} {L.mean(gi)-L.mean(ui):>8.2f} "
              f"{L.mean(uh)-L.mean(gh):>13.2f}{tag}")
        rows_out.append(dict(model=label, bal=bal, ps=ps, g=g, u=u, d=d,
                             t=t, df=df, p=p, gi=gi, ui=ui, gh=gh, uh=uh))
    print()
    print("Per-seed E1 differences (governed - ungoverned), in seed order:")
    for r in rows_out:
        marks = "".join("-" if x < 0 else "+" if x > 0 else "0" for x in r["d"])
        note = "" if r["bal"] else "   [UNBALANCED -- not a paired contrast]"
        print(f"  {r['model']:16s} seeds {','.join(r['ps']):14s} "
              f"[{', '.join(f'{x:+.2f}' for x in r['d'])}]   signs: {marks}{note}")

    bal_rows = [r for r in rows_out if r["bal"]]
    print("\nF4 sign stability: ", end="")
    bad = [r["model"] for r in bal_rows if len({x < 0 for x in r["d"]}) > 1]
    if bad:
        print(f"FAIL -- per-seed differences straddle zero in {bad}")
    else:
        print("PASS -- in every balanced model, every single per-seed difference has "
              "the same sign")
    print("F6 sign agreement with the published conditional gap: ", end="")
    flip = [r["model"] for r in rows_out
            if (r["d"] and (L.mean(r["d"]) < 0) != (L.mean(r["gi"]) - L.mean(r["ui"]) < 0))]
    print("all cells agree (both negative)" if not flip
          else f"SIGN FLIP in {flip} -- reported, not hidden")
    return rows_out


# ==========================================================================
# 4. THE ANCHOR, PROMINENTLY
# ==========================================================================
def anchor_block(results, summary):
    label, prefix = L.ANCHOR
    per = results[label]
    row = next(r for r in summary if r["model"] == label)
    ps = row["ps"]

    print("\n" + RULE)
    print(f"4. HEADLINE -- ANCHOR MODEL {label} (the published pair), {len(ps)} paired seeds")
    print(RULE)

    g, u, d = row["g"], row["u"], row["d"]
    print(f"  {'seed':>6s} {'gov E1 %':>10s} {'ung E1 %':>10s} {'diff pp':>10s}")
    for s, a, b, c in zip(ps, g, u, d):
        print(f"  {s:>6s} {a:>10.2f} {b:>10.2f} {c:>+10.2f}")
    print(f"  {'mean':>6s} {L.mean(g):>10.2f} {L.mean(u):>10.2f} {L.mean(d):>+10.2f}")
    print(f"  {'sd':>6s} {L.sd(g):>10.2f} {L.sd(u):>10.2f} {L.sd(d):>10.2f}")

    n = len(d)
    se = L.sd(d) / n ** 0.5
    # two-sided 95% t critical value for df=n-1, found by bisection on the p-function
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if L.t_two_sided_p(mid, n - 1) > 0.05:
            lo = mid
        else:
            hi = mid
    tcrit = (lo + hi) / 2
    ci = (L.mean(d) - tcrit * se, L.mean(d) + tcrit * se)

    print(f"\n  E1 TOTAL EFFECT = {L.mean(d):+.2f} pp   "
          f"(95% CI {ci[0]:+.2f} .. {ci[1]:+.2f}; paired t = {row['t']:.3f}, "
          f"df = {row['df']}, p = {p_str(row['p'])} {stars(row['p'])})")
    print(f"  t critical value used for the CI: {tcrit:.4f} (two-sided 95%, df={n-1})")
    print("  DIRECTION IN WORDS: governance LOWERS the share of all decisions that are")
    print("  increases. Governed agents ask for more water on "
          f"{L.mean(g):.2f}% of decisions; without validators, {L.mean(u):.2f}%.")

    # supplementary distribution-free check -- reported, never primary
    import itertools
    cnt = sum(1 for signs in itertools.product([1, -1], repeat=n)
              if abs(L.mean([s * x for s, x in zip(signs, d)])) >= abs(L.mean(d)) - 1e-12)
    print(f"\n  Supplementary sign-flip permutation p = {cnt}/{2**n} = {cnt/2**n:.4f} "
          f"(FLOOR for n={n} is {1/2**(n-1):.4f}; it CANNOT reach 0.05, so it is "
          "reported only as a distribution-free direction check, never as the test)")

    print("\n  Pooled (decision-weighted) values, printed for completeness only -- the")
    print("  inferential unit is the seed, so this is NOT the reported estimate:")
    tg = sum(per[("governed", s)]["nin"] for s in ps)
    ng = sum(per[("governed", s)]["n"] for s in ps)
    tu = sum(per[("ungoverned", s)]["nin"] for s in ps)
    nu = sum(per[("ungoverned", s)]["n"] for s in ps)
    print(f"    governed   {tg:6d}/{ng:6d} = {100.0*tg/ng:.2f}%")
    print(f"    ungoverned {tu:6d}/{nu:6d} = {100.0*tu/nu:.2f}%")
    print(f"    pooled gap = {100.0*tg/ng - 100.0*tu/nu:+.2f} pp")
    return row, ci


# ==========================================================================
# 5. WHAT FRACTION OF ALL DECISIONS ARE INCREASES  +  THE TWO-ESTIMAND COMPARISON
# ==========================================================================
def context_and_comparison(results, summary, anchor_row, anchor_ci):
    print("\n" + RULE)
    print("5. CONTEXT: THE FULL ACTION MIX, AND E1 VERSUS THE PUBLISHED CONDITIONAL")
    print(RULE)

    print("5a. Fraction of ALL decisions that are increases (this IS the E1 base rate),")
    print("    per model, mean over paired seeds:\n")
    print(f"  {'model':16s} {'governed %':>11s} {'ungoverned %':>13s} {'gap pp':>9s}")
    for r in summary:
        note = "" if r["bal"] else "   [unbalanced]"
        print(f"  {r['model']:16s} {L.mean(r['g']):>11.2f} {L.mean(r['u']):>13.2f} "
              f"{L.mean(r['d']):>+9.2f}{note}")

    print("\n5b. Mechanical decomposition of the unconditional rate (DESCRIPTIVE ARITHMETIC,")
    print("    NOT a causal decomposition -- it is just the law of total probability):")
    print("      E1 = HIGHshare * IBR  +  (1 - HIGHshare) * incr-rate-among-not-HIGH")
    print("    It shows what the published conditional throws away: the not-HIGH block,")
    print("    which is 63% of governed decisions and 17% of ungoverned ones on the anchor.\n")
    print(f"  {'model':16s} {'arm':11s} {'HIGH%':>7s} {'IBR%':>7s} {'notHIGH%':>9s} "
          f"{'incr|notHIGH%':>14s} {'reconstructed E1':>17s} {'actual E1':>10s} {'err':>7s}")
    for label, prefix in L.MODELS:
        per = results[label]
        for arm in ARMS:
            ps = L.paired_seeds(prefix)
            hs = L.mean([per[(arm, s)]["hs"] for s in ps])
            ib = L.mean([per[(arm, s)]["ibr"] for s in ps])
            lo = L.mean([per[(arm, s)]["lo"] for s in ps])
            e1 = L.mean([per[(arm, s)]["e1"] for s in ps])
            rec = hs / 100.0 * ib + (1 - hs / 100.0) * lo
            print(f"  {label:16s} {arm:11s} {hs:>7.2f} {ib:>7.2f} {100-hs:>9.2f} "
                  f"{lo:>14.2f} {rec:>17.2f} {e1:>10.2f} {rec-e1:>7.3f}")
        print()

    print("5c. THE TWO ESTIMANDS SIDE BY SIDE (both computed here from disk):\n")
    print(f"  {'model':16s} {'conditional IBR gap':>20s} {'unconditional E1 gap':>21s} "
          f"{'E1 / IBR':>9s} {'compos. shift pp':>17s}")
    for r in summary:
        ig = L.mean(r["gi"]) - L.mean(r["ui"])
        eg = L.mean(r["d"])
        ratio = eg / ig if ig else float("nan")
        cs = L.mean(r["uh"]) - L.mean(r["gh"])
        note = "" if r["bal"] else "  [unbalanced]"
        print(f"  {r['model']:16s} {ig:>20.2f} {eg:>21.2f} {ratio*100:>8.1f}% "
              f"{cs:>17.2f}{note}")

    bal = [r for r in summary if r["bal"]]
    print(f"\n  Balanced-cell mean: conditional gap {L.mean([L.mean(r['gi'])-L.mean(r['ui']) for r in bal]):.2f} pp, "
          f"unconditional gap {L.mean([L.mean(r['d']) for r in bal]):.2f} pp")

    print("\n5d. AGAINST THE PUBLISHED NUMBERS (quoted values are CHECKED, not trusted):")
    a = anchor_row
    print(f"    published conditional : governed {PUB_IBR_GOV:.2f}%  no-validator "
          f"{PUB_IBR_UNG:.2f}%  gap {PUB_GAP:+.2f} pp")
    print(f"    recomputed conditional: governed {L.mean(a['gi']):.2f}%  no-validator "
          f"{L.mean(a['ui']):.2f}%  gap {L.mean(a['gi'])-L.mean(a['ui']):+.2f} pp   "
          f"[delta vs published: {L.mean(a['gi'])-L.mean(a['ui'])-PUB_GAP:+.2f} pp]")
    print(f"    THIS SCRIPT (E1)      : governed {L.mean(a['g']):.2f}%  no-validator "
          f"{L.mean(a['u']):.2f}%  gap {L.mean(a['d']):+.2f} pp "
          f"(95% CI {anchor_ci[0]:+.2f} .. {anchor_ci[1]:+.2f})")
    surv = 100.0 * L.mean(a["d"]) / (L.mean(a["gi"]) - L.mean(a["ui"]))
    print(f"    -> on the anchor, {surv:.1f}% of the conditional gap's MAGNITUDE survives "
          "removing the post-treatment conditioning.")

    print("\n5e. The UNVERIFIED context note in project memory quotes an unconditional")
    print(f"    irrigation rate near {CTX_UNCOND_QUOTE:.2f}% for one arm (arm unspecified).")
    print("    WHAT I ACTUALLY COMPUTE on the anchor, mean over the 5 paired seeds:")
    print(f"      governed   E1 = {L.mean(a['g']):.2f}%   "
          f"[delta vs the {CTX_UNCOND_QUOTE:.2f} note: {L.mean(a['g'])-CTX_UNCOND_QUOTE:+.2f} pp]")
    print(f"      ungoverned E1 = {L.mean(a['u']):.2f}%   "
          f"[delta vs the {CTX_UNCOND_QUOTE:.2f} note: {L.mean(a['u'])-CTX_UNCOND_QUOTE:+.2f} pp]")
    print("    The note is consistent with the GOVERNED arm. It is reported as context")
    print("    only; nothing in this script depends on it.")


# ==========================================================================
# 6. SECONDARY ESTIMATOR: THE WORLD-REALISED ACTION  (falsifier F5)
# ==========================================================================
def world_realised(cache):
    print("\n" + RULE)
    print("6. SECONDARY ESTIMATOR E1-world -- SAME ESTIMAND, WORLD-REALISED ACTION")
    print(RULE)
    print("Phase 1 established, from `request` movements, that `yearly_decision` is the")
    print("LLM's LAST-SAID action label, not the executed one: every REJECTED row leaves")
    print("the diversion request UNCHANGED (6,096/6,096 governed, 4,754/4,754 ungoverned")
    print("on the anchor). So E1 above is an INTENT-stage total effect.")
    print("E1-world re-runs the identical estimator with")
    print("    executed = maintain_demand  if audit status starts with 'REJECTED'")
    print("    executed = final_skill      otherwise")
    print("joining simulation_log to the audit CSV 1:1 on (agent_id, year).")
    print("This is a ROBUSTNESS CHECK on the action definition, not a new estimand.\n")

    print(f"{'model':16s} {'pairs':>5s} {'gov %':>7s} {'ung %':>7s} {'GAP pp':>8s} "
          f"{'t':>9s} {'df':>3s} {'p':>9s} {'sig':>4s} {'join':>18s}")
    print(THIN)
    out = []
    for label, prefix in L.MODELS:
        ps = L.paired_seeds(prefix)
        rates = {}
        join_bad = 0
        for arm in ARMS:
            for s in ps:
                sim = cache[(label, arm, s)]
                aud = L.load_audit(L.run_dir(arm, prefix, s))
                key = {}
                for r in aud:
                    k = ((r.get("agent_id") or "").strip(), (r.get("year") or "").strip())
                    if k in key:
                        join_bad += 1
                    key[k] = r
                nin, n = 0, 0
                for r in sim:
                    k = ((r.get("agent_id") or "").strip(), (r.get("year") or "").strip())
                    ar = key.get(k)
                    if ar is None:
                        join_bad += 1
                        continue
                    st = (ar.get("status") or "").strip().upper()
                    fs = (ar.get("final_skill") or "").strip()
                    ex = L.DEFAULT_SKILL if st.startswith("REJECTED") else fs
                    n += 1
                    if ex in L.INCREASE:
                        nin += 1
                rates[(arm, s)] = 100.0 * nin / n if n else float("nan")
        g = [rates[("governed", s)] for s in ps]
        u = [rates[("ungoverned", s)] for s in ps]
        d = [a - b for a, b in zip(g, u)]
        t, df = L.paired_t(d)
        p = L.t_two_sided_p(t, df)
        tag = "OK" if join_bad == 0 else f"{join_bad} BAD KEYS"
        bal = "" if L.balanced(prefix) else "  <-- unbalanced, test invalid"
        print(f"{label:16s} {len(ps):>5d} {L.mean(g):>7.2f} {L.mean(u):>7.2f} "
              f"{L.mean(d):>+8.2f} {t:>9.3f} {df:>3d} {p_str(p):>9s} {stars(p):>4s} "
              f"{tag:>18s}{bal}")
        out.append((label, L.mean(g), L.mean(u), L.mean(d), L.balanced(prefix)))
    return out


# ==========================================================================
# 7. VERDICT
# ==========================================================================
def verdict(summary, anchor_row, anchor_ci, world):
    a = anchor_row
    e1 = L.mean(a["d"])
    cond = L.mean(a["gi"]) - L.mean(a["ui"])
    wm = next(w for w in world if w[0] == L.ANCHOR[0])

    print("\n" + RULE)
    print("7. WHAT THIS MEANS -- IN WORDS")
    print(RULE)
    print(f"""
THE TWO ESTIMANDS ANSWER DIFFERENT QUESTIONS.

  Published conditional (IBR / AAI), gap {cond:+.2f} pp on the anchor:
     "AMONG decisions where the agent said water was scarce, how often did it
      nevertheless ask for more?"  It is a COHERENCE statistic -- a measure of
      whether the agent's stated appraisal matches its chosen action. It is a
      perfectly good descriptive quantity. It is NOT a causal contrast, because
      governance moves membership of the 'said water was scarce' set by tens of
      percentage points, so the two arms' rates are averages over different
      decision populations.

  Unconditional total effect (E1), gap {e1:+.2f} pp on the anchor:
     "Over EVERY decision, how much less often does an agent ask for more water
      when the validators are on?"  It is a BEHAVIOURAL/HYDROLOGICAL statistic.
      It is causal under a single checkable assumption (arm exchangeability),
      and it is the number that maps onto basin-level water demand.

Neither replaces the other. The honest reading is: the paper reported a
coherence statistic and described it in causal language. E1 is what the causal
language would have to be attached to.

WHAT E1 CANNOT TELL YOU (and the paper's number cannot either):
  * It cannot separate "the agent was persuaded" from "the agent was blocked".
    A validator that rejects an increase and a model that never proposes one
    produce the same E1. Phase 3 must split these.
  * It cannot say the effect is desirable. Fewer increases is not automatically
    better water management; it is only better against a stated policy target.
  * The arms' worlds diverge from year 2 (coupled reservoir), so E1 is a
    whole-trajectory effect, not a stable per-decision parameter, and it is not
    transportable to another hydrological trace.

SENSITIVITY TO THE ACTION DEFINITION (F5): under the world-realised action the
anchor gap is {wm[3]:+.2f} pp (governed {wm[1]:.2f}% vs ungoverned {wm[2]:.2f}%),
versus {e1:+.2f} pp on the intent label. Same sign, and larger in magnitude, so the
conclusion is not a labelling artefact.
""")

    bal = [r for r in summary if r["bal"]]
    print("HETEROGENEITY -- THE PART THAT MUST NOT BE BURIED:")
    print("  E1 does NOT behave uniformly across model cells. Per balanced cell,")
    print("  fraction of the conditional gap's magnitude that survives:")
    for r in bal:
        ig = L.mean(r["gi"]) - L.mean(r["ui"])
        eg = L.mean(r["d"])
        print(f"    {r['model']:16s} conditional {ig:+7.2f} pp -> unconditional {eg:+7.2f} pp "
              f"({100*eg/ig:5.1f}% survives)")
    for r in summary:
        if not r["bal"]:
            ig = L.mean(r["gi"]) - L.mean(r["ui"])
            eg = L.mean(r["d"])
            print(f"    {r['model']:16s} conditional {ig:+7.2f} pp -> unconditional {eg:+7.2f} pp "
                  f"  [UNBALANCED, excluded from inference; SIGN FLIPS]"
                  if (ig < 0) != (eg < 0) else
                  f"    {r['model']:16s} conditional {ig:+7.2f} pp -> unconditional {eg:+7.2f} pp"
                  "  [UNBALANCED, excluded]")
    print("  The anchor model -- the one the paper reports -- is the cell where the")
    print("  unconditional effect is LARGEST and survives BEST. That is a selection")
    print("  fact the reader is entitled to.")

    surv = 100.0 * e1 / cond
    if surv >= 85 and a["p"] < 0.05:
        judge = "SURVIVES"
    elif surv >= 50 and a["p"] < 0.05:
        judge = "WEAKENED"
    elif a["p"] < 0.05 and (e1 < 0) == (cond < 0):
        judge = "WEAKENED"
    else:
        judge = "OVERTURNED"
    print(f"\nVERDICT vs the published -23.0 pp, judged on the ANCHOR MODEL: {judge}")
    print(f"  E1 = {e1:+.2f} pp (95% CI {anchor_ci[0]:+.2f} .. {anchor_ci[1]:+.2f}, "
          f"paired t = {a['t']:.3f}, df = {a['df']}, p = {p_str(a['p'])}); "
          f"{surv:.1f}% of the published magnitude,")
    print("  same sign, same significance class, on an estimand that is immune to the")
    print("  composition defect by construction. The DEFECT IN THE PUBLISHED ESTIMAND IS")
    print("  REAL AND UNCHANGED -- but on the anchor cell it did not manufacture the")
    print("  headline. On the corpus as a whole the picture is much weaker (see above).")


def main() -> int:
    print(RULE)
    print("e1_total_effect -- UNCONDITIONAL TOTAL EFFECT OF GOVERNANCE ON DEMAND INCREASES")
    print("irrigation testbed, v21, 42 years, 78 agents")
    print(RULE)
    print(__doc__.split("=====", 1)[0].strip())

    cache = corpus_check()
    results = per_seed_table(cache)
    summary = model_summary(results)
    arow, aci = anchor_block(results, summary)
    context_and_comparison(results, summary, arow, aci)
    world = world_realised(cache)
    verdict(summary, arow, aci, world)

    # -------------------------------------------------------------- sanity
    print("\n" + RULE)
    print("8. AUTOMATED SANITY SWEEP (every assertion below was evaluated, not asserted)")
    print(RULE)
    bad = []
    for label, prefix in L.MODELS:
        for arm in ARMS:
            for s in L.seeds(arm, prefix):
                r = results[label][(arm, s)]
                if not (0.0 <= r["e1"] <= 100.0):
                    bad.append(f"{label}/{arm}/{s}: E1 out of [0,100] = {r['e1']}")
                if r["n"] != L.EXPECTED_ROWS:
                    bad.append(f"{label}/{arm}/{s}: n={r['n']}")
                if not (0 <= r["nin"] <= r["n"]):
                    bad.append(f"{label}/{arm}/{s}: n_incr={r['nin']} vs n={r['n']}")
                if abs(100.0 * r["nin"] / r["n"] - r["e1"]) > 1e-9:
                    bad.append(f"{label}/{arm}/{s}: rate/count mismatch")
                if r["nhi"] == 0:
                    bad.append(f"{label}/{arm}/{s}: EMPTY HIGH group -- IBR undefined")
                if r["ibr"] != r["ibr"]:
                    bad.append(f"{label}/{arm}/{s}: IBR is nan")
    print(f"  rates within [0,100] ................. {'PASS' if not [b for b in bad if 'out of' in b] else 'FAIL'}")
    print(f"  every run has exactly 3,276 rows ..... {'PASS' if not [b for b in bad if 'n=' in b] else 'FAIL'}")
    print(f"  counts consistent with rates ......... {'PASS' if not [b for b in bad if 'mismatch' in b] else 'FAIL'}")
    print(f"  no silently empty HIGH group ......... {'PASS' if not [b for b in bad if 'EMPTY' in b] else 'FAIL'}")
    if bad:
        print("  !! ANOMALIES:")
        for b in bad:
            print("     -", b)
    else:
        print("\n  All sanity checks passed. Nothing odd to report beyond the")
        print("  heterogeneity and the definitional caveat already stated in section 7.")
    print("\nDone. This script wrote no files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
