"""Which IBR do we report? A / B / rule-class — computed from the shipped corpus.

THE QUESTION. When an agent is corrected up to 3 times and still proposes a
rule-violating action, what should execute?

  A  (design intent)  execute the AGENT'S OWN choice, log a WARNING.
                      "We corrected it three times and it still chose this" is the
                      honest record, and it is exactly what a non-compliance metric
                      is supposed to count.
  B  (what the code does, skill_broker_engine.py:476, unconditionally)
                      execute the registry DEFAULT skill (irrigation: maintain_demand,
                      flood: do_nothing).
  C  (rule-class)     HARD rule violated -> B, because the action is impossible.
                      SOFT rule only     -> A, because the action is merely incoherent.

Why it matters: A and B coincide in flood (3 differing rows out of 82,607, because
96.4% of rejected rows proposed do_nothing, which IS the default) and diverge on
45.4% of the irrigation governed corpus.

This script does NOT decide the classification — that is a domain judgement. It takes
a HARD set as input and reports what each choice implies, so the decision is made with
the numbers visible.
"""
from __future__ import annotations

import csv
import glob
import os
import re
import statistics
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_SKILL = "maintain_demand"
INCREASE = {"increase_large", "increase_small"}
HIGH_WSA = {"H", "VH"}

# Candidate HARD sets, to show how sensitive the answer is to the classification.
# These are ILLUSTRATIVE, not a verdict.
# ALWAYS HARD, in every C scenario. The audit CSV records rule_id "Unknown" for
# registry-precondition failures, but the raw JSONL identifies all 1,071 of the
# no-validator arm's rejections as SkillRegistry.preconditions ->
# "Precondition failed: 'not at_allocation_cap'": the agent tried to take more than
# its decreed water right. A farmer cannot receive water it has no right to, so this
# can never be soft. Without this the no-validator arm looks unconstrained and every
# C gap is inflated.
ALWAYS_HARD = {"Unknown", "precondition_violation", "output_schema_violation"}

CANDIDATES = {
    "B: everything hard (what the code does today)": None,   # sentinel = all hard
    # "A0" is scenario A with NOTHING held hard at all -- not even the water right.
    # It is here for ONE reason: it reproduces the published pair exactly, which
    # validates this pipeline. It is NOT a defensible semantics, because it lets an
    # agent take water it has no legal right to.
    "A0: nothing hard at all (reproduces the published pair)": "PURE_A",
    "A : agent's choice stands, but water rights still enforced": set(),
    "C1: institutional + physical validators hard": {
        "curtailment_awareness", "supply_gap_block_increase",
        "demand_ceiling_stabilizer", "demand_floor_stabilizer",
    },
    "C2: C1 minus the two 'stabilizer' rules": {
        "curtailment_awareness", "supply_gap_block_increase",
    },
    "C3: only curtailment (a real legal instrument)": {
        "curtailment_awareness",
    },
}


def _rule_ids(row):
    raw = (row.get("failed_rules") or "").strip()
    return {x for x in re.split(r"[,;|\[\]'\"\s]+", raw) if x}


def executed(row, hard_set):
    """What executes under a given HARD set. hard_set=None means 'all rules hard'."""
    status = (row.get("status") or "").strip()
    final = (row.get("final_skill") or "").strip()
    if not status.startswith("REJECTED"):
        return final
    if hard_set is None:                       # scenario B
        return DEFAULT_SKILL
    if hard_set == "PURE_A":                   # A0: nothing held hard, even affordances
        return final
    if _rule_ids(row) & (hard_set | ALWAYS_HARD):   # a hard rule blocked -> impossible
        return DEFAULT_SKILL
    return final                               # soft only -> agent's choice stands


def rate(paths, hard_set):
    """Conditional high-scarcity increase rate, averaged over runs."""
    per_run = []
    for p in paths:
        cond = hits = 0
        with open(p, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if (row.get("construct_WSA_LABEL") or "").strip().upper() not in HIGH_WSA:
                    continue
                cond += 1
                if executed(row, hard_set) in INCREASE:
                    hits += 1
        if cond:
            per_run.append(100.0 * hits / cond)
    return statistics.mean(per_run) if per_run else float("nan")


def main():
    gov = sorted(glob.glob(os.path.join(
        REPO, "examples/irrigation_abm/results/production_v21_42yr_seed*/irrigation_farmer_governance_audit.csv")))
    nov = sorted(glob.glob(os.path.join(
        REPO, "examples/irrigation_abm/results/ungoverned_v21_42yr_seed*/irrigation_farmer_governance_audit.csv")))
    print(f"gemma3:4b v21 baseline — the published dataset "
          f"({len(gov)} governed / {len(nov)} no-validator runs)\n")
    print(f"{'scenario':62s} {'governed':>9s} {'no-val':>8s} {'gap pp':>8s}")
    print("-" * 90)
    for name, hard in CANDIDATES.items():
        g, n = rate(gov, hard), rate(nov, hard)
        print(f"{name:62s} {g:>8.2f}% {n:>7.2f}% {n - g:>+7.2f}")
    print("""
Reading this table
  * The published Nature Water figures (36.05 / 59.07 / +23.02) match scenario A —
    the manuscripts already report design-intent semantics.
  * The code produced scenario B (0.86 / 26.77 / +25.90).
  * Every C row is a defensible middle, and the spread between them IS the
    sensitivity of the headline number to a classification judgement nobody has
    formally made yet.
  * The GAP is NOT stable across scenarios (it ranges widely below). An earlier
    reading of this table claimed it was; that was an artefact of failing to treat
    the no-validator arm's at_allocation_cap rejections as hard. The DIRECTION and
    SIGN of the effect survive every scenario; the magnitude does not.""")


if __name__ == "__main__":
    main()
