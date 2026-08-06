"""e0 -- the cornerstone check: at YEAR 1 the two arms' worlds are identical.

    python SUBMISSION_2026/TAE/evidence/e0_year1_exogeneity.py

The paper's mechanism argument (DECISION.md section 4) leads on this: at year 1
the governed and no-validator arms inhabit the SAME world, so any year-1
difference in the self-reported appraisal cannot be world-driven. Fig 2a then
shows that difference is null. That reading is only worth anything if the
premise is checked rather than asserted, and until this script existed the
premise was cited from a script outside this folder.

WHAT IT DOES
------------
For every irrigation cell, on the PAIRED seeds only (seeds present in BOTH
arms), it joins the two arms' ``simulation_log.csv`` on (seed, agent_id, year)
and computes the EXACT-EQUALITY rate per column per year -- string equality on
the raw csv cell, so no tolerance, no rounding, no numeric coercion can launder
a difference away. It prints the year-1 rate for every column and the first year
at which each column disagrees.

EXIT CODE
    0  every PRE-DECISION column is exactly equal on 100% of year-1 pairs
    1  any pre-decision column is not, i.e. the cornerstone is falsified

A non-zero exit here is not a bug in this script. It would mean the year-1 null
in Fig 2a cannot be read as "same world, different report", and DECISION.md
section 4 would have to be rewritten. Report it; do not tune it.

WHICH COLUMNS ARE PRE-DECISION -- established, not assumed
----------------------------------------------------------
``simulation_log.csv`` is written in ``post_year`` (examples/irrigation_abm/
run_experiment.py:307), i.e. AFTER the year's decision has been executed against
the environment. Whether a given column is pre- or post-decision is therefore a
question about the quantity, not about when the row was written.

PRE-DECISION (gates the exit code). Two kinds:

  * static agent attributes, fixed at setup and never written by a skill --
    ``cluster``, ``basin``, ``water_right``, ``has_efficient_system``;
  * the environment/institution state the agent is SHOWN when it is asked --
    ``drought_index``, ``shortage_tier``, ``curtailment_ratio``,
    ``lake_mead_level``, ``mead_storage_maf``. In year 1 these carry the
    initial hydrology, which no year-1 decision can have moved yet.

POST-DECISION, and therefore EXCLUDED from the exit condition -- but still
computed and printed below, because dropping a column silently is exactly the
move this folder exists to prevent:

  * ``utilisation_pct``, written at run_experiment.py:344-347 as
    ``agent_state["request"] / water_right * 100``. ``request`` is the demand the
    year's skill just set, so this is a function of the decision.
  * ``below_minimum_utilisation``, an agent-state flag on that same
    post-decision utilisation.

Both were listed as pre-decision in the task brief for this script. They are
not, and the corpus proves it rather than the code merely suggesting it: this
script runs a CONTROL -- restrict to year-1 agent-years where the two arms
applied the SAME demand change, i.e. the same skill AND the same
``magnitude_pct``. On every such pair, in every cell, both columns are exactly
equal. Note that the same skill alone is not enough: ``magnitude_pct`` is a
bounded-Gaussian draw made when the skill executes, so two arms can both choose
``increase_small`` and still move demand by different amounts. That is itself
post-decision variation, and the control separates the two cases rather than
lumping them.

WHAT THIS CHECK CANNOT DO
-------------------------
It compares the LOGGED world. It cannot see a difference that was never written
to a column, and it says nothing about year >= 2, where the arms' worlds diverge
by construction -- that divergence IS the mechanism the paper argues for, and
the first-divergence-year column below is where it starts.
"""
from __future__ import annotations

import os
import sys
from typing import NamedTuple

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import _data as D                                                # noqa: E402

# --- column classification; see the module docstring for the evidence ---------
STATIC_ATTRS = ("cluster", "basin", "water_right", "has_efficient_system")
ENV_STATE = (
    "drought_index", "shortage_tier", "curtailment_ratio",
    "lake_mead_level", "mead_storage_maf",
)
PRE_DECISION = STATIC_ATTRS + ENV_STATE

#: listed as pre-decision in the brief, established here to be post-decision.
#: Printed, never gates the exit code.
POST_DECISION_RECLASSIFIED = ("utilisation_pct", "below_minimum_utilisation")

#: the skill that moves no demand -- the control for the reclassification
NEUTRAL_SKILL = "maintain_demand"

BAR = "=" * 100
RULE = "-" * 100


class Pairing:
    """The matched (agent_id, year) rows of one seed, both arms.

    Refuses to compare anything but an exact one-to-one key match. A partial
    match would shrink the comparison base silently, which would make a 100%
    equality rate mean less than it appears to.
    """

    def __init__(self, prefix, seed: int):
        gov = {self._key(r): r for r in D.load_sim(D.irrigation_run("gov", prefix, seed))}
        nov = {self._key(r): r for r in D.load_sim(D.irrigation_run("noval", prefix, seed))}
        if len(gov) != D.IRRIGATION_EXPECTED_ROWS or len(nov) != D.IRRIGATION_EXPECTED_ROWS:
            raise D.DataError(
                f"seed {seed}: expected {D.IRRIGATION_EXPECTED_ROWS} unique "
                f"(agent_id, year) keys per arm, got gov={len(gov)} noval={len(nov)}"
            )
        if set(gov) != set(nov):
            raise D.DataError(
                f"seed {seed}: the two arms' (agent_id, year) key sets differ "
                f"({len(set(gov) - set(nov))} gov-only, {len(set(nov) - set(gov))} noval-only); "
                "refusing to compare a partial overlap"
            )
        self.seed = seed
        self.gov = gov
        self.nov = nov
        self.keys = sorted(gov)

    @staticmethod
    def _key(row: dict) -> tuple[str, int]:
        return (row["agent_id"], int(row["year"]))


def _tally(pairings, columns):
    """``{(column, year): [equal, total]}`` over every matched pair, all seeds.

    Equality is on the RAW csv string. No float tolerance: the claim is exact
    equality, so it is tested exactly.
    """
    counts: dict[tuple[str, int], list[int]] = {}
    for p in pairings:
        for k in p.keys:
            g, n = p.gov[k], p.nov[k]
            year = k[1]
            for c in columns:
                if c not in g or c not in n:
                    raise D.DataError(f"column {c!r} absent from simulation_log.csv")
                cell = counts.setdefault((c, year), [0, 0])
                cell[1] += 1
                if g[c] == n[c]:
                    cell[0] += 1
    return counts


def _rate(counts, column, year):
    eq, tot = counts[(column, year)]
    return 100.0 * eq / tot, eq, tot


def _first_divergence(counts, column, years):
    for y in years:
        eq, tot = counts[(column, y)]
        if eq != tot:
            return y
    return None


class Control(NamedTuple):
    n_same_change: int          # year-1 pairs with identical (skill, magnitude_pct)
    n_neutral: int              # subset of those where both arms chose maintain_demand
    same_change_equal: dict     # column -> [equal, total] over the same-change pairs
    neutral_equal: dict         # column -> [equal, total] over the neutral subset
    unequal_diff_change: dict   # column -> unequal pairs whose demand change differed


def _control_same_demand_change(pairings) -> Control:
    """Year-1 equality of the reclassified columns where the SAME demand change ran.

    "Same demand change" = same skill AND the same ``magnitude_pct``. If the two
    columns are post-decision they must be exactly equal on every such pair, and
    every disagreement must sit on a pair whose demand change differed. The
    ``maintain_demand`` subset (no demand moved at all) is reported separately as
    the cleanest case.
    """
    same_eq = {c: [0, 0] for c in POST_DECISION_RECLASSIFIED}
    neutral_eq = {c: [0, 0] for c in POST_DECISION_RECLASSIFIED}
    unequal_diff = {c: 0 for c in POST_DECISION_RECLASSIFIED}
    n_same = n_neutral = 0
    for p in pairings:
        for k in p.keys:
            if k[1] != 1:
                continue
            g, n = p.gov[k], p.nov[k]
            same_change = (
                D.action(g) == D.action(n)
                and (g.get("magnitude_pct") or "") == (n.get("magnitude_pct") or "")
            )
            neutral = same_change and D.action(g) == NEUTRAL_SKILL
            n_same += same_change
            n_neutral += neutral
            for c in POST_DECISION_RECLASSIFIED:
                equal = g[c] == n[c]
                if same_change:
                    same_eq[c][1] += 1
                    same_eq[c][0] += equal
                if neutral:
                    neutral_eq[c][1] += 1
                    neutral_eq[c][0] += equal
                if not equal and not same_change:
                    unequal_diff[c] += 1
    return Control(n_same, n_neutral, same_eq, neutral_eq, unequal_diff)


def check_cell(model) -> dict:
    m = D.irrigation_model(model)
    seeds = D.paired_seeds(m.prefix)
    if not seeds:
        raise D.DataError(f"no paired seeds for irrigation model {m.label!r}")
    pairings = [Pairing(m.prefix, s) for s in seeds]
    columns = PRE_DECISION + POST_DECISION_RECLASSIFIED
    counts = _tally(pairings, columns)
    years = sorted({y for _, y in counts})
    n_pairs = sum(len(p.keys) for p in pairings)
    n_year1 = sum(1 for p in pairings for k in p.keys if k[1] == 1)
    return {
        "model": m,
        "seeds": seeds,
        "pairings": pairings,
        "counts": counts,
        "years": years,
        "n_pairs": n_pairs,
        "n_year1": n_year1,
    }


def _print_cell(res) -> list[str]:
    """Print one cell. Returns the list of cornerstone failures it found."""
    m = res["model"]
    counts, years = res["counts"], res["years"]
    excl = " (excluded from paired contrasts; shown for completeness)" if \
        D.excluded_from_paired(m.prefix) else ""
    print(RULE)
    print(f"{m.label}{'  [ANCHOR]' if m.anchor else ''}{excl}")
    print(f"  paired seeds {list(res['seeds'])}   matched (seed, agent_id, year) pairs "
          f"compared: {res['n_pairs']:,}   of which year 1: {res['n_year1']:,}")
    print(RULE)
    print(f"  {'column':28s} {'class':14s} {'year-1 equal':>16s} {'rate%':>8s} "
          f"{'year-2 rate%':>13s} {'first year != ':>15s}")
    failures = []
    for c in PRE_DECISION + POST_DECISION_RECLASSIFIED:
        pre = c in PRE_DECISION
        kind = ("static" if c in STATIC_ATTRS else "env-state") if pre else "POST-DECISION"
        r1, eq1, tot1 = _rate(counts, c, 1)
        r2, _, _ = _rate(counts, c, 2) if 2 in years else (float("nan"), 0, 0)
        fd = _first_divergence(counts, c, years)
        mark = ""
        if pre and eq1 != tot1:
            mark = "   <== CORNERSTONE FALSIFIED"
            failures.append(
                f"{m.label} column {c!r}: year-1 exact equality {eq1}/{tot1} = {r1:.4f}%"
            )
        print(f"  {c:28s} {kind:14s} {eq1:>8,d}/{tot1:<7,d} {r1:>8.4f} "
              f"{r2:>13.4f} {('none' if fd is None else str(fd)):>15s}{mark}")
    pre_first = [
        _first_divergence(counts, c, years) for c in PRE_DECISION
        if _first_divergence(counts, c, years) is not None
    ]
    print(f"  -> FIRST year at which ANY pre-decision column disagrees: "
          f"{min(pre_first) if pre_first else 'never (all 42 years identical)'}")
    return failures


def main() -> int:
    print(BAR)
    print("e0 -- YEAR-1 EXOGENEITY: are the two arms' worlds identical when year 1 is decided?")
    print(BAR)
    print("Run directories come from _data.irrigation_run(); this script owns no path and no glob.")
    print("Equality is EXACT string equality on the raw csv cell. No tolerance is applied.")
    print(f"Pre-decision columns (gate the exit code), {len(PRE_DECISION)}: "
          f"{', '.join(PRE_DECISION)}")
    print(f"Reclassified as POST-decision (printed, do NOT gate): "
          f"{', '.join(POST_DECISION_RECLASSIFIED)}")
    print()

    results = [check_cell(m) for m in D.IRRIGATION_MODELS]
    failures: list[str] = []
    for res in results:
        failures.extend(_print_cell(res))
        print()

    # ---- the control that establishes the reclassification -------------------
    print(BAR)
    print("CONTROL -- why utilisation_pct and below_minimum_utilisation are POST-decision")
    print(BAR)
    print("Restrict year 1 to agent-years where the two arms applied the SAME demand change --")
    print("same skill AND the same magnitude_pct. A post-decision column must be exactly equal")
    print("on every such pair, and every disagreement must sit on a pair whose change differed.")
    print(f"The {NEUTRAL_SKILL!r} subset (no demand moved at all) is broken out separately.")
    print()
    print(f"  {'model':14s} {'column':28s} {'same-change pairs':>18s} {'equal':>16s} "
          f"{'neutral pairs':>14s} {'equal':>13s} {'unequal, change differed':>26s}")
    control_problems = []
    for res in results:
        ctrl = _control_same_demand_change(res["pairings"])
        for c in POST_DECISION_RECLASSIFIED:
            eq, tot = ctrl.same_change_equal[c]
            neq, ntot = ctrl.neutral_equal[c]
            ok = (tot > 0 and eq == tot and ntot > 0 and neq == ntot)
            if not ok:
                control_problems.append(
                    f"{res['model'].label} {c}: same-change equality {eq}/{tot}, "
                    f"neutral equality {neq}/{ntot}"
                )
            print(f"  {res['model'].label:14s} {c:28s} {ctrl.n_same_change:>18,d} "
                  f"{eq:>7,d}/{tot:<8,d} {ctrl.n_neutral:>14,d} {neq:>5,d}/{ntot:<7,d} "
                  f"{ctrl.unequal_diff_change[c]:>26,d}"
                  f"{'' if ok else '   <== CONTROL FAILED'}")
    print()
    print("  Every year-1 disagreement in these two columns sits on an agent-year where the two")
    print("  arms applied a different demand change; there are no disagreements left over. They")
    print("  are functions of the decision, not of the world the decision was made in. Same skill")
    print("  alone is NOT sufficient -- magnitude_pct is drawn when the skill executes, so two")
    print("  arms can both choose increase_small and still move demand by different amounts.")

    # ---- verdict -------------------------------------------------------------
    print()
    print(BAR)
    total_pairs = sum(r["n_pairs"] for r in results)
    total_y1 = sum(r["n_year1"] for r in results)
    print(f"compared {total_pairs:,} matched (seed, agent_id, year) pairs across "
          f"{len(results)} irrigation cells; {total_y1:,} of them at year 1")
    if failures:
        print()
        print("*** CORNERSTONE FALSIFIED -- the two arms' year-1 worlds are NOT identical ***")
        for f in failures:
            print("   ", f)
        print()
        print("DECISION.md section 4 and the Fig 2a reading depend on this. Report it. Do not")
        print("relax the column set or add a tolerance until it passes.")
        print(BAR)
        return 1
    if control_problems:
        print()
        print("*** CONTROL FAILED -- the post-decision reclassification is not established ***")
        for p in control_problems:
            print("   ", p)
        print(BAR)
        return 1
    print()
    print("YEAR-1 EXOGENEITY: HOLDS. Every pre-decision column is exactly equal on 100% of")
    print("year-1 pairs, in every irrigation cell. The arms' worlds first diverge at year 2,")
    print("which is when the year-1 decisions have had an effect to have.")
    print(BAR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
