"""R10 -- irrigation: which RULE TYPE blocks an increase proposal, and what the IBR
headline would read if one rule family were switched off.

WHAT IT ANSWERS
  A reviewer who has read r3 (rule-firing census) and r5 (proposed vs executed) will
  ask the next question: of the proposals that got blocked, how many were blocked by
  a rule that only looks at the WORLD (a physical/administrative state variable) versus
  a rule that only looks at the agent's own stated LABEL (WSA/ACA), versus both at once?
  And if the label-conditioned rules were the ones a circularity critique targets, what
  would the headline IBR look like with only the world rules doing the blocking -- and
  the mirror question, with only the label rules doing it?

THE FIRST-PROPOSAL COLUMN, AND WHY THIS SCRIPT USES `proposed_skill` INSTEAD
  There IS a first-attempt-proposal column in the broker codebase --
  `initial_skill` (+ `initial_labels` / `attempt_skills`), added by P0-1a
  (broker/tests/test_initial_proposal_columns_p0_1a.py) precisely because
  `skill_proposal` / `proposed_skill` is REASSIGNED on every governance retry, so a
  retried-and-changed decision's audit row shows the LAST attempt, not the first. That
  column is gated by `global_config.audit.initial_proposal_columns`, DEFAULT OFF.
  MEASURED on this package's corpora: `initial_skill` is absent from the header of all
  ten released governed/ungoverned v21 audit CSVs (checked directly, all 5 seeds each
  arm). So this script falls back to `proposed_skill`, exactly as the brief allows, and
  that fallback is NOT free: spot-checking `raw/irrigation_farmer_traces.jsonl` against
  the audit CSV (seed 42, step 3, agent "Fort Mohave Ind Res CA", Y1) shows a row with
  `retry_count=1`, `proposed_skill=increase_small`, `failed_rules=curtailment_awareness`,
  `error_messages="Large demand increase blocked..."` -- i.e. the FIRST attempt was
  `increase_large`, blocked, and the row's own `proposed_skill` already shows the
  retried `increase_small`. So among retried rows, "first proposal was an increase" as
  measured here can MISS a first attempt that was an increase but got retried into a
  non-increase, and can also count a row whose first attempt was NOT an increase but
  whose retried, recorded proposal happens to be one (not observed, but not ruled out
  either). `n_proposal_ne_final` in r5 is 0 for every run (validators do not rewrite a
  skill name mid-decision the way `execute_skill` does at the environment layer) so
  within THIS corpus `proposed_skill` and `final_skill` never diverge; the retry-driven
  drift described above is between attempt 0 and the recorded attempt, which no column
  in the released files can see. This is the same absence r9 already documents for WSA
  labels; here it is for the skill name.

RULE-TYPE TAXONOMY (verified against source, not asserted)
  WORLD/STATE (label-free -- conditions only on environment state or a skill
  precondition, never on a WSA/ACA construct):
    demand_ceiling_stabilizer, demand_floor_stabilizer, water_right_cap,
    minimum_utilisation_floor, curtailment_awareness, supply_gap_block_increase,
    non_negative_diversion, compact_allocation, drought_severity, magnitude_cap,
    consecutive_increase_cap, zero_escape_floor, and the literal id "Unknown" (the
    no-validator arm's skill-registry precondition "not at_allocation_cap" -- the
    SAME physical constraint as `water_right_cap`, raised at a different layer because
    the no-validator arm has no `custom_validators`; confirmed by
    examples/irrigation_abm/validators/irrigation_validators.py:44-80 vs the literal
    error text "Precondition failed: 'not at_allocation_cap'" on 100% of the
    no-validator arm's ERROR-level rows, seed 42).
    Source for the physical/state-only claim: every function above reads only
    `context.get(...)` state keys (curtailment_ratio, shortage_tier, drought_index,
    at_allocation_cap, below_minimum_utilisation, current_request/diversion,
    total_basin_demand, water_right) -- none reads a WSA_LABEL/ACA_LABEL construct.
  LABEL (conditions on a WSA/ACA construct emitted by the model in the same
  generation -- confirmed in examples/irrigation_abm/config/agent_types.yaml
  strict.thinking_rules, each carrying an explicit `construct:` or `conditions:
  [{construct: ...}]` key):
    low_threat_no_increase (WSA_LABEL), high_threat_high_cope_no_increase
    (WSA_LABEL + ACA_LABEL), high_threat_no_maintain (WSA_LABEL, WARNING level only
    -- never appears in `failed_rules` because it never blocks; carried here so an
    unexpected ERROR-level sighting is still classified correctly rather than falling
    to OTHER).
  OTHER: anything not in the two lists above. NONE were observed in the five governed
  or five no-validator seeds analysed here (measured, printed below); of the six
  ERROR-level ids the released corpora actually exercise -- five governed
  (curtailment_awareness, demand_ceiling_stabilizer, demand_floor_stabilizer,
  high_threat_high_cope_no_increase, low_threat_no_increase, supply_gap_block_increase)
  and one no-validator (Unknown) -- all six classify cleanly. `water_right_cap`,
  `minimum_utilisation_floor`, `high_threat_no_maintain`, `non_negative_diversion`,
  `compact_allocation`, `drought_severity`, `magnitude_cap`, `consecutive_increase_cap`
  and `zero_escape_floor` are real rule ids defined in code/config but NEVER observed
  firing at ERROR level in any of the ten runs read here -- they are classified by
  source-code reading alone, not by having fired.

  A SECOND, smaller instance of the same retry-loop attribution gap: `failed_rules`
  unions ids across EVERY attempt of a decision, and a retry can change which skill
  TYPE is proposed, not just its magnitude. `demand_floor_stabilizer` blocks
  `DECREASE_SKILLS` only, yet MEASURED here on 53-89 of each governed seed's
  ~1,250-1,600 increase-first rows (4-6%), it appears in the `failed_rules` of a row
  whose final `proposed_skill` is an increase -- left over from an earlier decrease
  attempt in the same retry loop. Re-classifying those rows with that one id excluded
  flips only 2-5 rows per seed (BOTH -> LABEL_ONLY; every other contaminated row
  already carries a second, non-alien WORLD id), which the 5-seed means below absorb
  without materially moving. Not corrected for here -- reported as measured.

WHAT IS COUNTED (per row whose `proposed_skill` is `increase_large`/`increase_small`
AND whose `failed_rules` is non-empty -- i.e. blocked at least once during that
decision's retry loop, whether or not it was later approved on retry)
  WORLD_ONLY / LABEL_ONLY / BOTH / OTHER   union-of-ids-in-failed_rules classification.
  rejected_share_pct   of the rows in that class, the % whose FINAL status still
                        starts with REJECTED (i.e. never recovered via retry).

THE TWO COUNTERFACTUAL BOUNDS -- ACCOUNTING BOUNDS, NOT COUNTERFACTUAL RUNS
  Neither (a) nor (b) re-simulates anything. A retry that in fact happened is not
  re-run under the hypothetical rule set; a retry that in fact did NOT happen (because
  the row was rejected outright, or approved first attempt) is not invented either.
  The only thing that changes is which of two already-recorded numbers -- the
  `proposed_skill` this script uses as the first-proposal proxy, or the actual executed
  remap `irr_executed` (REJECTED -> `maintain_demand`, else `final_skill`) -- is read as
  "the action" for a given row:
    (a) LABEL-rule-only blocks undone: for a row classified LABEL_ONLY, the action
        becomes its own `proposed_skill` (the increase runs); every other row
        (unblocked, WORLD_ONLY, BOTH, OTHER) keeps `irr_executed`.
    (b) WORLD-rule-only blocks undone: mirror of (a) for WORLD_ONLY rows.
  A row classified BOTH stays at its executed action in EITHER bound, because undoing
  only one rule family leaves the other one still blocking it -- this is exactly why
  the two bounds are not additive and not a joint "both undone" scenario.
  `ibr_pct` and `increase_rate_pct` are then `_loader.ibr` / `_loader.increase_rate`'s
  own definitions (conditional high-WSA rate / unconditional rate), re-applied to
  whichever action column is in play, exactly as r5 already does for `proposal`,
  `final`, `executed`.

RULE-SHARE-OF-REJECTIONS TABLE
  Restricted to rows whose FINAL status starts with REJECTED (the governed arm's
  n = 1,267 of 3,276 for seed 42 -- NOT `r3`'s `share_of_rejected_pct`, which divides
  by the same REJECTED denominator but counts a rule firing on ANY row where it
  appears, including rows that recovered via retry and ended APPROVED; that is why r3's
  own numbers exceed 100% for the busiest rules and are not reused here). For every
  rejected row, every distinct rule id in its own `failed_rules` counts once; shares
  are computed against n_rejected and are NOT expected to sum to 100%, because most
  rejected rows carry more than one id (`n_rejected_multi_rule` / `share_..._pct`
  reports exactly how many).

OUTPUT
  out/r10_rule_type_attribution.csv   row_type in {block_class, rule_share}, each with
                                       per-seed rows plus MEAN/SD summary rows.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r10_rule_type_attribution.py
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import L, PrepError  # noqa: E402

NA = "N/A_by_design"

WORLD_IDS = frozenset({
    "demand_ceiling_stabilizer", "demand_floor_stabilizer", "water_right_cap",
    "minimum_utilisation_floor", "curtailment_awareness", "supply_gap_block_increase",
    "non_negative_diversion", "compact_allocation", "drought_severity",
    "magnitude_cap", "consecutive_increase_cap", "zero_escape_floor", "Unknown",
})
LABEL_IDS = frozenset({
    "low_threat_no_increase", "high_threat_high_cope_no_increase",
    "high_threat_no_maintain",
})

OTHER_IDS_SEEN: set = set()


def _split(v):
    return [x.strip() for x in (v or "").split("|") if x.strip()]


def _row_class(row: dict) -> str | None:
    """None if the row is out of scope (not an increase proposal, or not blocked)."""
    if C.irr_proposal(row) not in L.INCREASE:
        return None
    ids = _split(row.get("failed_rules"))
    if not ids:
        return None
    has_world = any(i in WORLD_IDS for i in ids)
    has_label = any(i in LABEL_IDS for i in ids)
    other = [i for i in ids if i not in WORLD_IDS and i not in LABEL_IDS]
    if other:
        OTHER_IDS_SEEN.update(other)
        return "OTHER"
    if has_world and has_label:
        return "BOTH"
    if has_world:
        return "WORLD_ONLY"
    if has_label:
        return "LABEL_ONLY"
    raise PrepError(f"unreachable: non-empty failed_rules classified as neither {ids!r}")


def _rejected(row: dict) -> bool:
    return (row.get("status") or "").strip().startswith("REJECTED")


def _action_bound(row: dict, bound: str) -> str:
    cls = _row_class(row)
    if bound == "a" and cls == "LABEL_ONLY":
        return C.irr_proposal(row)
    if bound == "b" and cls == "WORLD_ONLY":
        return C.irr_proposal(row)
    return C.irr_executed(row)


def _ibr_bound(aud, hi, bound: str) -> float:
    return 100.0 * sum(1 for r in hi if _action_bound(r, bound) in L.INCREASE) / len(hi)


def _increase_rate_bound(aud, bound: str) -> float:
    return 100.0 * sum(1 for r in aud if _action_bound(r, bound) in L.INCREASE) / len(aud)


def _check_no_initial_skill_column(arm, seed):
    aud = L.load_audit(L.run_dir(arm, "", seed))
    present = "initial_skill" in aud[0]
    return present


def _block_class_row(arm, seed, aud) -> dict:
    C.require_cols(aud, ["proposed_skill", "final_skill", "status", "failed_rules",
                         "construct_WSA_LABEL"], f"{arm} seed {seed}")
    hi = [r for r in aud if C.irr_wsa_audit(r) in L.HIGH]
    if not hi:
        raise PrepError(f"{arm} seed {seed}: no high-WSA rows -- empty IBR denominator")

    inc_first = [r for r in aud if C.irr_proposal(r) in L.INCREASE]
    n_increase_proposals = len(inc_first)
    buckets = {"WORLD_ONLY": [], "LABEL_ONLY": [], "BOTH": [], "OTHER": []}
    for r in inc_first:
        cls = _row_class(r)
        if cls is not None:
            buckets[cls].append(r)
    n_blocked = sum(len(v) for v in buckets.values())

    rec = {
        "row_type": "block_class", "arm": arm, "seed": seed, "rule_id": "",
        "n_rows": len(aud), "n_increase_proposals": n_increase_proposals,
        "n_blocked": n_blocked,
        "n_world_only": len(buckets["WORLD_ONLY"]),
        "n_label_only": len(buckets["LABEL_ONLY"]),
        "n_both": len(buckets["BOTH"]),
        "n_other": len(buckets["OTHER"]),
    }
    for name, key in (("world_only", "n_world_only"), ("label_only", "n_label_only"),
                      ("both", "n_both"), ("other", "n_other")):
        rec[f"share_{name}_pct_of_blocked"] = (
            100.0 * rec[key] / n_blocked if n_blocked else float("nan"))
    for name, bkt in (("world_only", "WORLD_ONLY"), ("label_only", "LABEL_ONLY"),
                      ("both", "BOTH"), ("other", "OTHER")):
        rows_c = buckets[bkt]
        rec[f"rejected_share_{name}_pct"] = (
            100.0 * sum(1 for r in rows_c if _rejected(r)) / len(rows_c)
            if rows_c else float("nan"))

    rec["ibr_pct_published_proposal"] = 100.0 * sum(
        1 for r in hi if C.irr_proposal(r) in L.INCREASE) / len(hi)
    rec["ibr_pct_executed"] = 100.0 * sum(
        1 for r in hi if C.irr_executed(r) in L.INCREASE) / len(hi)
    rec["ibr_pct_bound_a_label_rules_undone"] = _ibr_bound(aud, hi, "a")
    rec["ibr_pct_bound_b_world_rules_undone"] = _ibr_bound(aud, hi, "b")

    rec["increase_rate_pct_published_proposal"] = 100.0 * sum(
        1 for r in aud if C.irr_proposal(r) in L.INCREASE) / len(aud)
    rec["increase_rate_pct_executed"] = 100.0 * sum(
        1 for r in aud if C.irr_executed(r) in L.INCREASE) / len(aud)
    rec["increase_rate_pct_bound_a_label_rules_undone"] = _increase_rate_bound(aud, "a")
    rec["increase_rate_pct_bound_b_world_rules_undone"] = _increase_rate_bound(aud, "b")

    for k in ("n_rejected_total", "n_rejected_with_rule_id", "rule_share_of_rejected_pct",
              "n_rejected_multi_rule", "share_rejected_multi_rule_pct",
              "other_rule_ids_seen"):
        rec[k] = NA
    return rec


def _rule_share_rows(arm, seed, aud, universe: set) -> list:
    rej = [r for r in aud if _rejected(r)]
    n_rej = len(rej)
    if n_rej == 0:
        raise PrepError(f"{arm} seed {seed}: zero REJECTED rows -- unexpected")
    per_row_ids = [set(_split(r.get("failed_rules"))) for r in rej]
    multi = sum(1 for ids in per_row_ids if len(ids) > 1)
    counts = Counter()
    for ids in per_row_ids:
        for i in ids:
            counts[i] += 1

    out = []
    for rid in sorted(universe):
        n_with = counts.get(rid, 0)
        rec = {
            "row_type": "rule_share", "arm": arm, "seed": seed, "rule_id": rid,
            "n_rows": len(aud),
            "n_rejected_total": n_rej,
            "n_rejected_with_rule_id": n_with,
            "rule_share_of_rejected_pct": 100.0 * n_with / n_rej,
            "n_rejected_multi_rule": multi,
            "share_rejected_multi_rule_pct": 100.0 * multi / n_rej,
            "other_rule_ids_seen": "|".join(sorted(OTHER_IDS_SEEN)) if OTHER_IDS_SEEN else "",
        }
        for k in ("n_increase_proposals", "n_blocked", "n_world_only", "n_label_only",
                  "n_both", "n_other", "share_world_only_pct_of_blocked",
                  "share_label_only_pct_of_blocked", "share_both_pct_of_blocked",
                  "share_other_pct_of_blocked", "rejected_share_world_only_pct",
                  "rejected_share_label_only_pct", "rejected_share_both_pct",
                  "rejected_share_other_pct", "ibr_pct_published_proposal",
                  "ibr_pct_executed", "ibr_pct_bound_a_label_rules_undone",
                  "ibr_pct_bound_b_world_rules_undone",
                  "increase_rate_pct_published_proposal", "increase_rate_pct_executed",
                  "increase_rate_pct_bound_a_label_rules_undone",
                  "increase_rate_pct_bound_b_world_rules_undone"):
            rec[k] = NA
        out.append(rec)
    return out


FIELDNAMES = [
    "row_type", "arm", "seed", "rule_id",
    "n_rows", "n_increase_proposals", "n_blocked",
    "n_world_only", "n_label_only", "n_both", "n_other",
    "share_world_only_pct_of_blocked", "share_label_only_pct_of_blocked",
    "share_both_pct_of_blocked", "share_other_pct_of_blocked",
    "rejected_share_world_only_pct", "rejected_share_label_only_pct",
    "rejected_share_both_pct", "rejected_share_other_pct",
    "ibr_pct_published_proposal", "ibr_pct_executed",
    "ibr_pct_bound_a_label_rules_undone", "ibr_pct_bound_b_world_rules_undone",
    "increase_rate_pct_published_proposal", "increase_rate_pct_executed",
    "increase_rate_pct_bound_a_label_rules_undone",
    "increase_rate_pct_bound_b_world_rules_undone",
    "n_rejected_total", "n_rejected_with_rule_id", "rule_share_of_rejected_pct",
    "n_rejected_multi_rule", "share_rejected_multi_rule_pct", "other_rule_ids_seen",
]

NUM_COLS_BLOCK_CLASS = [
    "n_rows", "n_increase_proposals", "n_blocked", "n_world_only", "n_label_only",
    "n_both", "n_other", "share_world_only_pct_of_blocked",
    "share_label_only_pct_of_blocked", "share_both_pct_of_blocked",
    "share_other_pct_of_blocked", "rejected_share_world_only_pct",
    "rejected_share_label_only_pct", "rejected_share_both_pct",
    "rejected_share_other_pct", "ibr_pct_published_proposal", "ibr_pct_executed",
    "ibr_pct_bound_a_label_rules_undone", "ibr_pct_bound_b_world_rules_undone",
    "increase_rate_pct_published_proposal", "increase_rate_pct_executed",
    "increase_rate_pct_bound_a_label_rules_undone",
    "increase_rate_pct_bound_b_world_rules_undone",
]

NUM_COLS_RULE_SHARE = [
    "n_rows", "n_rejected_total", "n_rejected_with_rule_id",
    "rule_share_of_rejected_pct", "n_rejected_multi_rule",
    "share_rejected_multi_rule_pct",
]


def main() -> int:
    C.banner("R10  irrigation rule-type attribution (WORLD vs LABEL)")
    seeds = L.paired_seeds("")

    print("  initial-proposal column check (P0-1a `initial_skill`, default OFF):")
    any_present = False
    for arm in ("governed", "ungoverned"):
        for s in seeds:
            present = _check_no_initial_skill_column(arm, s)
            any_present = any_present or present
            if present:
                print(f"    {arm} seed {s}: initial_skill PRESENT (flag was ON)")
    if not any_present:
        print("    absent from all 10 released runs -- falling back to `proposed_skill`"
              " as the first-proposal proxy, per the brief.")

    rows = []
    block_class_by_arm = {"governed": [], "ungoverned": []}
    rule_share_by_arm = {"governed": [], "ungoverned": []}

    for arm in ("governed", "ungoverned"):
        # rule-id universe for this arm = union over all 5 seeds' failed_rules ids,
        # among REJECTED rows only, so a rule that fires in 4/5 seeds still gets an
        # explicit 0% row (not a silently missing seed) for the seed where it does not.
        universe = set()
        per_seed_aud = {}
        for s in seeds:
            aud = L.load_audit(L.run_dir(arm, "", s))
            per_seed_aud[s] = aud
            for r in aud:
                if _rejected(r):
                    universe.update(_split(r.get("failed_rules")))

        for s in seeds:
            aud = per_seed_aud[s]
            bc = _block_class_row(arm, s, aud)
            rows.append(bc)
            block_class_by_arm[arm].append(bc)
            rs = _rule_share_rows(arm, s, aud, universe)
            rows.extend(rs)
            rule_share_by_arm[arm].extend(rs)

    # MEAN / SD summary rows, block_class
    for arm, recs in block_class_by_arm.items():
        for tag, fn in (("MEAN", C.mean), ("SD", C.sd)):
            out = {"row_type": "block_class", "arm": arm, "seed": tag, "rule_id": ""}
            for k in NUM_COLS_BLOCK_CLASS:
                out[k] = fn([r[k] for r in recs])
            for k in ("n_rejected_total", "n_rejected_with_rule_id",
                      "rule_share_of_rejected_pct", "n_rejected_multi_rule",
                      "share_rejected_multi_rule_pct", "other_rule_ids_seen"):
                out[k] = NA
            rows.append(out)

    # MEAN / SD summary rows, rule_share -- per (arm, rule_id) over the 5 seeds
    for arm, recs in rule_share_by_arm.items():
        by_rule: dict = {}
        for r in recs:
            by_rule.setdefault(r["rule_id"], []).append(r)
        for rid, rs in by_rule.items():
            for tag, fn in (("MEAN", C.mean), ("SD", C.sd)):
                out = {"row_type": "rule_share", "arm": arm, "seed": tag, "rule_id": rid}
                for k in NUM_COLS_RULE_SHARE:
                    out[k] = fn([r[k] for r in rs])
                out["other_rule_ids_seen"] = rs[0]["other_rule_ids_seen"]
                for k in NUM_COLS_BLOCK_CLASS:
                    out[k] = NA
                rows.append(out)

    C.write_csv("r10_rule_type_attribution.csv", FIELDNAMES, rows)

    print("\n  block-class counts (mean over 5 seeds):")
    print(f"    {'arm':11s} {'n_inc_prop':>10s} {'n_blocked':>9s} {'world':>7s} "
          f"{'label':>7s} {'both':>6s} {'other':>6s}")
    for arm, recs in block_class_by_arm.items():
        print(f"    {arm:11s} {C.mean([r['n_increase_proposals'] for r in recs]):10.1f} "
              f"{C.mean([r['n_blocked'] for r in recs]):9.1f} "
              f"{C.mean([r['n_world_only'] for r in recs]):7.1f} "
              f"{C.mean([r['n_label_only'] for r in recs]):7.1f} "
              f"{C.mean([r['n_both'] for r in recs]):6.1f} "
              f"{C.mean([r['n_other'] for r in recs]):6.1f}")

    print("\n  IBR / increase-rate, published vs executed vs the two bounds"
          " (mean +/- sd over 5 seeds):")
    for arm, recs in block_class_by_arm.items():
        print(f"    {arm}:")
        for label, key in (
            ("published (proposal)", "ibr_pct_published_proposal"),
            ("executed             ", "ibr_pct_executed"),
            ("bound (a) label-undone", "ibr_pct_bound_a_label_rules_undone"),
            ("bound (b) world-undone", "ibr_pct_bound_b_world_rules_undone"),
        ):
            vals = [r[key] for r in recs]
            print(f"      IBR   {label}: {C.mean(vals):6.2f} +/- {C.sd(vals):5.2f}")
        for label, key in (
            ("published (proposal)", "increase_rate_pct_published_proposal"),
            ("executed             ", "increase_rate_pct_executed"),
            ("bound (a) label-undone", "increase_rate_pct_bound_a_label_rules_undone"),
            ("bound (b) world-undone", "increase_rate_pct_bound_b_world_rules_undone"),
        ):
            vals = [r[key] for r in recs]
            print(f"      rate  {label}: {C.mean(vals):6.2f} +/- {C.sd(vals):5.2f}")

    print("\n  rule-share of ALL governed rejections (own failed_rules, mean over 5"
          " seeds; multi-rule overlap means shares need not sum to 100%):")
    gov_by_rule: dict = {}
    for r in rule_share_by_arm["governed"]:
        gov_by_rule.setdefault(r["rule_id"], []).append(r["rule_share_of_rejected_pct"])
    for rid, vals in sorted(gov_by_rule.items(), key=lambda kv: -C.mean(kv[1])):
        print(f"    {rid:32s} {C.mean(vals):6.2f} %  (n over seeds = {len(vals)})")
    overlap_vals = [r["share_rejected_multi_rule_pct"]
                    for r in rule_share_by_arm["governed"]
                    if r["rule_id"] == sorted(gov_by_rule)[0]]
    if overlap_vals:
        print(f"    multi-rule overlap (>1 distinct id on the same rejected row): "
              f"{C.mean(overlap_vals):.2f} %")

    print("\n  OTHER (unrecognised) rule ids seen anywhere in the increase-proposal-"
          f"blocked subset: {sorted(OTHER_IDS_SEEN) if OTHER_IDS_SEEN else '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
