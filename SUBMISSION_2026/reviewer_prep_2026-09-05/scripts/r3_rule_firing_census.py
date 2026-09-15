"""R3 -- rule-firing census: which validator rule actually fired, how often, and with
what outcome. Both domains, both arms, per seed.

WHAT IT ANSWERS
  "You claim a governance layer. Show me the rules firing, one by one, and show me
   that the effect is not one rule doing everything."

WHICH COLUMNS -- and which are dead
  USED
    failed_rules    pipe-delimited rule ids that BLOCKED the proposal (ERROR level).
                    Empty on an unblocked row. This is the only populated blocking
                    record in the released corpora.
    warning_rules   pipe-delimited rule ids that fired at WARNING level, i.e. were
                    recorded and did NOT block. Project memory: WARNING rules
                    change small-model behaviour 0 %, which is exactly why the
                    separation matters here.
    status          APPROVED | REJECTED | REJECTED_FALLBACK.
    retry_count     0..3.
  DEAD -- verified empty/zero on every released run, never used
    rules_triggered      empty string on 100 % of rows
    rules_personal_hit / rules_social_hit / rules_thinking_hit /
    rules_physical_hit / rules_semantic_hit    all "0" on 100 % of rows
    fallback_activated   "False" on 100 % of rows even where status is
                         REJECTED_FALLBACK -- the column contradicts the status
                         column and must not be used.
  The script MEASURES the deadness rather than assuming it, and prints what it found.

PER-RULE QUANTITIES
  n_rows_fired          rows on which the id appears (in failed_rules for level
                        ERROR, in warning_rules for level WARNING)
  share_of_rows_pct     n_rows_fired / all rows of the run
  share_of_rejected_pct n_rows_fired / rows whose status starts with REJECTED
                        (for a WARNING rule this is simply co-occurrence, not cause)
  n_approved_after_retry   rows where the id fired, status == APPROVED and
                        retry_count > 0 -- the proposal was re-asked and got through
  n_rejected_final      rows where the id fired and the final status is REJECTED*

RUN-LEVEL STATUS SHARES (written with rule_id = "__STATUS__")
  approved_first_attempt   status APPROVED and retry_count == 0
  approved_after_retry     status APPROVED and retry_count > 0
  rejected_to_fallback     status starts with REJECTED (the executed action becomes
                           the registry default)

OUTPUT
  out/r3_rule_firing_census.csv

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r3_rule_firing_census.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import L, PrepError  # noqa: E402

DEAD_CANDIDATES = ["rules_triggered", "rules_personal_hit", "rules_social_hit",
                   "rules_thinking_hit", "rules_physical_hit", "rules_semantic_hit",
                   "fallback_activated"]

FLOOD_MODEL = "gemma3_4b"
FLOOD_ARMS = {
    "governed": ("JOH_FINAL", "Group_C"),
    "ungoverned": ("JOH_ABLATION_DISABLED", "Group_C_disabled"),
}


def _split(v):
    return [x.strip() for x in (v or "").split("|") if x.strip()]


def _census(domain, arm, seed, aud):
    C.require_cols(aud, ["status", "retry_count", "failed_rules", "warning_rules"],
                   f"{domain}/{arm}/{seed}")
    n = len(aud)
    rej = [r for r in aud if (r.get("status") or "").strip().startswith("REJECTED")]
    out = []

    for level, col in (("ERROR", "failed_rules"), ("WARNING", "warning_rules")):
        ids = {}
        for r in aud:
            for rid in _split(r.get(col)):
                ids.setdefault(rid, []).append(r)
        for rid, rs in sorted(ids.items()):
            st = [(r.get("status") or "").strip() for r in rs]
            rc = [int(float((r.get("retry_count") or "0").strip() or 0)) for r in rs]
            # `failed_rules` records the literal id "Unknown" for a block raised by a
            # SKILL PRECONDITION rather than by a named theory rule. Carrying the
            # modal error message is the only way to tell those apart, and it matters:
            # the no-validator irrigation arm's "Unknown" is the hard world affordance
            # "Precondition failed: 'not at_allocation_cap'", not a validator.
            msgs = [(r.get("error_messages") or "").strip()[:120] for r in rs]
            modal = max(set(msgs), key=msgs.count) if msgs else ""
            out.append({
                "modal_error_message": modal,
                "domain": domain, "arm": arm, "seed": seed, "level": level,
                "rule_id": rid, "source_column": col,
                "n_rows_total": n,
                "n_rows_fired": len(rs),
                "share_of_rows_pct": 100.0 * len(rs) / n,
                "share_of_rejected_pct": (100.0 * len(rs) / len(rej)) if rej else float("nan"),
                "n_approved_after_retry": sum(
                    1 for s, c in zip(st, rc) if s == "APPROVED" and c > 0),
                "n_approved_first_attempt": sum(
                    1 for s, c in zip(st, rc) if s == "APPROVED" and c == 0),
                "n_rejected_final": sum(1 for s in st if s.startswith("REJECTED")),
            })

    # run-level status shares
    rc_all = [int(float((r.get("retry_count") or "0").strip() or 0)) for r in aud]
    st_all = [(r.get("status") or "").strip() for r in aud]
    for name, k in (
        ("approved_first_attempt", sum(1 for s, c in zip(st_all, rc_all)
                                       if s == "APPROVED" and c == 0)),
        ("approved_after_retry", sum(1 for s, c in zip(st_all, rc_all)
                                     if s == "APPROVED" and c > 0)),
        ("rejected_to_fallback", len(rej)),
    ):
        out.append({
            "domain": domain, "arm": arm, "seed": seed, "level": "__STATUS__",
            "rule_id": name, "source_column": "status+retry_count",
            "n_rows_total": n, "n_rows_fired": k,
            "share_of_rows_pct": 100.0 * k / n,
            "share_of_rejected_pct": float("nan"),
            "n_approved_after_retry": "", "n_approved_first_attempt": "",
            "n_rejected_final": "", "modal_error_message": "",
        })
    covered = sum(x["n_rows_fired"] for x in out if x["level"] == "__STATUS__")
    if covered != n:
        raise PrepError(f"{domain}/{arm}/{seed}: status buckets cover {covered} of {n} rows")
    return out


def _deadness(aud):
    rep = {}
    for c in DEAD_CANDIDATES:
        if c not in aud[0]:
            rep[c] = "column absent"
            continue
        vals = {(r.get(c) or "").strip() for r in aud}
        rep[c] = "DEAD (" + "/".join(sorted(v or "<empty>" for v in vals)[:3]) + ")" \
            if len(vals) <= 1 or vals <= {"", "0", "False"} else "live"
    return rep


def main() -> int:
    C.banner("R3  rule-firing census")
    rows = []

    print("  irrigation (gemma3:4b v21)")
    for arm in ("governed", "ungoverned"):
        for s in L.paired_seeds(""):
            aud = L.load_audit(L.run_dir(arm, "", s))
            rows += _census("irrigation", arm, s, aud)
            if s == "42":
                print(f"    dead-column check, {arm} seed 42: {_deadness(aud)}")

    print("  flood (gemma3_4b, single-agent)")
    for arm, (root, group) in FLOOD_ARMS.items():
        for run, (seed, rd) in C.flood_runs(root, FLOOD_MODEL, group).items():
            aud = C.read_csv(os.path.join(rd, C.FLOOD_AUDIT))
            rows += _census("flood", arm, f"{seed}({run})", aud)
            if run == "Run_1":
                print(f"    dead-column check, {arm} Run_1: {_deadness(aud)}")

    C.write_csv(
        "r3_rule_firing_census.csv",
        ["domain", "arm", "seed", "level", "rule_id", "source_column", "n_rows_total",
         "n_rows_fired", "share_of_rows_pct", "share_of_rejected_pct",
         "n_approved_after_retry", "n_approved_first_attempt", "n_rejected_final",
         "modal_error_message"],
        rows)

    print("\n  distinct rule ids seen (level ERROR):")
    for dom in ("irrigation", "flood"):
        for arm in ("governed", "ungoverned"):
            ids = sorted({r["rule_id"] for r in rows
                          if r["domain"] == dom and r["arm"] == arm and r["level"] == "ERROR"})
            print(f"    {dom:11s} {arm:11s} {len(ids):>2d}: {ids}")
    print("\n  distinct rule ids seen (level WARNING):")
    for dom in ("irrigation", "flood"):
        for arm in ("governed", "ungoverned"):
            ids = sorted({r["rule_id"] for r in rows
                          if r["domain"] == dom and r["arm"] == arm and r["level"] == "WARNING"})
            print(f"    {dom:11s} {arm:11s} {len(ids):>2d}: {ids}")

    print("\n  run-level status shares, mean over seeds (%):")
    print(f"    {'domain':11s} {'arm':11s} {'first-attempt':>14s} {'after-retry':>12s} "
          f"{'rejected->fallback':>19s}")
    for dom in ("irrigation", "flood"):
        for arm in ("governed", "ungoverned"):
            def g(name):
                return C.mean([r["share_of_rows_pct"] for r in rows
                               if r["domain"] == dom and r["arm"] == arm
                               and r["rule_id"] == name])
            print(f"    {dom:11s} {arm:11s} {g('approved_first_attempt'):14.2f} "
                  f"{g('approved_after_retry'):12.2f} {g('rejected_to_fallback'):19.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
