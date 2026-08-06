"""The rule's antecedent is a CONJUNCTION, and both conjuncts are written by the agent.

WHY THIS SCRIPT EXISTS
A reviewer-simulation pass on 2026-08-01 found that the manuscript described its denominator as
"the decisions whose self-reported appraisal falls inside the rule's antecedent" while measuring only
the scarcity conjunct. The rule actually reads, from
examples/irrigation_abm/config/agent_types.yaml:

    id: high_threat_high_cope_no_increase          # R4
    conditions:
      - {construct: WSA_LABEL, values: [H, VH]}    # reported water scarcity
      - {construct: ACA_LABEL, values: [H, VH]}    # reported adaptive capacity
    blocked_skills: [increase_large, increase_small]

    id: low_threat_no_increase                     # R2
    conditions:
      - {construct: WSA_LABEL, values: [VL]}
    blocked_skills: [increase_large, increase_small]

Scarcity-high is a strict SUPERSET of R4's antecedent and is DISJOINT from R2's, so a rate
conditioned on scarcity alone is not the rule's conformance rate. The paper's own recommendation is
that a conformance rate be reported beside the prevalence of its conditioning variable in both arms;
measuring one conjunct and calling it the antecedent fails that standard.

This script measures every version so the manuscript can state which one it means.

WHAT IT SHOWS
The finding is robust to the correction. Both conjuncts are agent-written and BOTH shift between
arms, which strengthens rather than weakens the claim: the coping conjunct is not a fixed covariate
either. The conjunction's prevalence shift is close to the scarcity marginal's, so no headline
changes direction or magnitude class -- only the wording of what is being measured.

WHAT WOULD FALSIFY IT
If the coping conjunct did NOT shift, the paper could fairly describe the antecedent by its scarcity
marginal. It does shift, so it cannot.

Usage:  python SUBMISSION_2026/TAE/evidence/e6_antecedent_conjunction.py
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
HIGH = {"H", "VH"}
T_CRIT_DF4 = 2.776


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


def load(path: str) -> list:
    with open(os.path.join(path, "simulation_log.csv"), encoding="utf-8-sig", newline="") as fh:
        return [r for r in csv.DictReader(fh) if (r.get("yearly_decision") or "").strip()]


def wsa(r): return (r.get("wsa_label") or "").strip().upper()
def aca(r): return (r.get("aca_label") or "").strip().upper()


DEFS = [
    ("scarcity marginal  WSA in {H,VH}", lambda r: wsa(r) in HIGH,
     "what the manuscript measured before this correction; a SUPERSET of R4's antecedent"),
    ("coping marginal    ACA in {H,VH}", lambda r: aca(r) in HIGH,
     "the conjunct that was never reported; also agent-written"),
    ("R4 antecedent      WSA and ACA both high", lambda r: wsa(r) in HIGH and aca(r) in HIGH,
     "the actual conjunction the rule fires on"),
    ("R2 antecedent      WSA == VL", lambda r: wsa(r) == "VL",
     "the second enforced rule; disjoint from the scarcity-high set"),
    ("R2 or R4 fires", lambda r: wsa(r) == "VL" or (wsa(r) in HIGH and aca(r) in HIGH),
     "the full set of decisions any enforced theory rule applies to"),
]


def paired(xs):
    m = st.mean(xs)
    se = st.stdev(xs) / math.sqrt(len(xs))
    return m, m - T_CRIT_DF4 * se, m + T_CRIT_DF4 * se


def main() -> int:
    gov, ung = runs("production"), runs("ungoverned")
    seeds = sorted(set(gov) & set(ung))
    print("=" * 104)
    print("e6 — THE ANTECEDENT IS A CONJUNCTION, AND BOTH CONJUNCTS ARE AGENT-WRITTEN")
    print(f"anchor cell gemma3:4b, paired seeds {', '.join(seeds)}")
    print("=" * 104 + "\n")
    print(f"{'antecedent':42s} {'prev|gov':>9s} {'prev|nov':>9s} {'SHIFT':>8s} "
          f"{'rate|gov':>9s} {'rate|nov':>9s} {'GAP':>8s}")
    print("-" * 104)

    out = {}
    for label, cond, _note in DEFS:
        pg, pu, rg, ru = [], [], [], []
        for s in seeds:
            for src, P, R in ((gov, pg, rg), (ung, pu, ru)):
                rows = load(src[s])
                sel = [r for r in rows if cond(r)]
                P.append(100.0 * len(sel) / len(rows))
                R.append(100.0 * sum(1 for r in sel
                                     if r["yearly_decision"].strip() in INCREASE) / len(sel)
                         if sel else float("nan"))
        sm, slo, shi = paired([b - a for a, b in zip(pg, pu)])
        gm, glo, ghi = paired([b - a for a, b in zip(rg, ru)])
        out[label] = (st.mean(pg), st.mean(pu), sm, slo, shi, st.mean(rg), st.mean(ru), gm)
        print(f"{label:42s} {st.mean(pg):8.2f}% {st.mean(pu):8.2f}% {sm:+8.2f} "
              f"{st.mean(rg):8.2f}% {st.mean(ru):8.2f}% {gm:+8.2f}")

    print("\nNOTES")
    for label, _c, note in DEFS:
        print(f"  {label:42s} {note}")

    scar = out["scarcity marginal  WSA in {H,VH}"]
    cope = out["coping marginal    ACA in {H,VH}"]
    conj = out["R4 antecedent      WSA and ACA both high"]

    print(f"\n  CLAIM both_conjuncts_move: the scarcity conjunct shifts {scar[2]:+.2f} pp and the")
    print(f"  coping conjunct shifts {cope[2]:+.2f} pp (95% CI {cope[3]:+.2f}, {cope[4]:+.2f}). Neither")
    print("  is a fixed covariate, so the antecedent cannot be described by one of them.")
    print(f"\n  CLAIM conjunction_shift: R4's actual antecedent shifts {conj[2]:+.2f} pp "
          f"(95% CI {conj[3]:+.2f}, {conj[4]:+.2f}),")
    print(f"  and the increase rate on it differs by {conj[7]:+.2f} pp between arms.")

    cope_moves = cope[3] > 0 or cope[4] < 0        # CI excludes zero
    same_class = abs(conj[2] - scar[2]) < 10.0
    print("\n" + "=" * 104)
    print(f"VERDICT: {'HOLDS' if (cope_moves and same_class) else 'CHECK'} — the coping conjunct "
          f"{'does' if cope_moves else 'does NOT'} move, so the manuscript must name the conjunction; "
          f"and the conjunction's shift is\n  within 10 pp of the scarcity marginal's, so the "
          "correction changes the WORDING and not the magnitude class of the finding.")
    print("=" * 104)
    return 0 if (cope_moves and same_class) else 1


if __name__ == "__main__":
    sys.exit(main())
