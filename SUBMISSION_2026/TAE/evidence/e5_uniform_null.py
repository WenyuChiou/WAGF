"""The uniform-random null, and why only the unconditional rate can be tested against it.

WHAT THIS SHOWS
A null model is only interpretable when the denominator is fixed independently of the treatment.
The irrigation action set holds five skills, two of which are increases, so an agent choosing
uniformly at random would propose an increase on 40% of its decisions. That null can be tested
against the UNCONDITIONAL rate, whose denominator is fixed by the experiment design at
78 agents x 42 years, and cannot be tested against the CONDITIONAL rate, whose denominator is
written by the model and differs between arms.

Measured on the anchor cell: without validators the unconditional rate sits far above the null,
and with validators we did not reject comparison with that null. The directional pull toward increases is
what enforcement removes.

WHAT WOULD FALSIFY IT
The action-set composition is read from skill_registry.yaml rather than assumed, so a registry with
a different increase fraction changes the null and the script prints the value it derived. If the
governed arm's interval stopped containing the null, the "indistinguishable from chance" reading
would fail and the script says so in its verdict line.

HONEST LIMIT
A uniform-random agent is a weak null. It says the governed arm shows no net directional pull, not
that governed behaviour is random: the same marginal rate is consistent with many different
policies. The claim in the paper is confined to the direction, and this script does not license
anything stronger.

Usage:  python SUBMISSION_2026/TAE/evidence/e5_uniform_null.py
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
INCREASE = {"increase_large", "increase_small"}
T_CRIT_DF4 = 2.776          # two-sided 95%, df = 4
REGISTRY = os.path.join(REPO, "examples/irrigation_abm/config/skill_registry.yaml")


def derive_null() -> tuple:
    """Read the action set from the registry rather than hardcoding 40%."""
    try:
        with open(REGISTRY, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise SystemExit(f"cannot read {REGISTRY}: {exc}")
    # skill ids appear as top-level-ish keys; count the distinct known action names
    skills = sorted({m for m in re.findall(
        r"\b(increase_large|increase_small|decrease_large|decrease_small|maintain_demand)\b", text)})
    if not skills:
        raise SystemExit(f"no known skill ids found in {REGISTRY}; cannot derive the null")
    inc = [s for s in skills if s in INCREASE]
    return 100.0 * len(inc) / len(skills), skills, inc


def runs(arm: str) -> dict:
    out = {}
    for p in glob.glob(os.path.join(
            REPO, f"examples/irrigation_abm/results/{arm}_v21_42yr_seed*")):
        m = re.search(r"seed(\d+)$", os.path.basename(p))
        if m and os.path.exists(os.path.join(p, "simulation_log.csv")):
            out[m.group(1)] = p
    if not out:
        raise SystemExit(f"no {arm} runs found")
    return out


def unconditional_rate(path: str) -> float:
    n = inc = 0
    with open(os.path.join(path, "simulation_log.csv"), encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            a = (r.get("yearly_decision") or "").strip()
            if not a:
                continue
            n += 1
            if a in INCREASE:
                inc += 1
    return 100.0 * inc / n


def one_sample(xs, mu):
    m = st.mean(xs)
    s = st.stdev(xs)
    se = s / math.sqrt(len(xs))
    return m, s, se, (m - mu) / se, m - T_CRIT_DF4 * se, m + T_CRIT_DF4 * se


def main() -> int:
    null, skills, inc = derive_null()
    gov, ung = runs("production"), runs("ungoverned")
    seeds = sorted(set(gov) & set(ung))

    print("=" * 88)
    print("e5 — THE UNIFORM-RANDOM NULL, TESTABLE ONLY AGAINST A DESIGN-FIXED DENOMINATOR")
    print(f"anchor cell gemma3:4b, paired seeds {', '.join(seeds)}")
    print("=" * 88 + "\n")

    print(f"  action set read from skill_registry.yaml: {len(skills)} skills, "
          f"{len(inc)} of them increases")
    print(f"    {', '.join(skills)}")
    print(f"  CLAIM uniform_null: a uniformly random agent proposes an increase on "
          f"{null:.0f}% of decisions\n")

    rows = []
    for label, src in (("no-validator", ung), ("with validators", gov)):
        xs = [unconditional_rate(src[s]) for s in seeds]
        m, s, se, t, lo, hi = one_sample(xs, null)
        contains = lo <= null <= hi
        rows.append((label, m, t, lo, hi, contains))
        print(f"  {label:16s} unconditional rate {m:6.2f}%   sd {s:4.2f}   "
              f"t vs {null:.0f}% = {t:+7.3f} (df = {len(xs)-1})")
        print(f"  {'':16s} 95% CI [{lo:.2f}, {hi:.2f}]  ->  "
              f"{'CONTAINS the null' if contains else 'EXCLUDES the null'}")
        print(f"  {'':16s} per seed: {', '.join(f'{x:.2f}' for x in xs)}\n")

    nov, govr = rows[0], rows[1]
    print("  CLAIM null_comparison: without validators the unconditional rate sits far above the")
    print(f"  null (t = {nov[2]:+.1f}); with validators we did not reject comparison with it "
          f"(95% CI {govr[3]:.1f} to {govr[4]:.1f}).")
    print("  The same test CANNOT be applied to the conditional rate: its denominator is written")
    print("  by the model and differs between arms, so there is no fixed reference to test against.\n")

    ok = (not nov[5]) and govr[5]
    print("=" * 88)
    print(f"VERDICT: {'HOLDS' if ok else 'FAILS'} — no-validator "
          f"{'excludes' if not nov[5] else 'CONTAINS'} the null and with-validators "
          f"{'contains' if govr[5] else 'EXCLUDES'} it.")
    print("  Weak-null caveat: this bounds the DIRECTION only. A marginal rate at chance is")
    print("  consistent with many policies and does not mean governed behaviour is random.")
    print("=" * 88)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
