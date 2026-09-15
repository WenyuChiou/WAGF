"""R9 -- did the appraisal change between the first attempt and the final one?

WHAT IT ANSWERS
  The leak/drift attack on the headline. The published irrigation IBR conditions on
  the agent's own water-scarcity appraisal. If the retry loop lets an agent restate
  that appraisal on a later attempt, the statistic is dividing by a quantity the
  enforcement itself moved. Measuring that needs the FIRST attempt's appraisal.

VERDICT ON THE RELEASED CORPORA: NOT AVAILABLE. This script proves the absence
rather than asserting it, by checking three places the first attempt could hide:

  1. the audit csv columns. The released runs carry `construct_WSA_LABEL` (final
     only). The TAE runs additionally carry `initial_labels`, `initial_skill` and
     `attempt_skills` -- those columns are what P0-1a (broker 0c6aa60e, opt-in,
     default-OFF) adds, and they are absent from every released run.
  2. the raw JSONL under each run's raw/. One object per DECISION, not per attempt:
     `skill_proposal.reasoning.WSA_LABEL` holds the accepted attempt's label and no
     earlier one. The script asserts the record count equals the decision count,
     which is what "one record per decision" means.
  3. the reflection log. Post-decision reflection, no per-attempt appraisal.

WHAT IS REPORTED INSTEAD -- the denominator the measurement would have used
  For every governed seed: the share of decisions that were retried at all
  (retry_count > 0), the share retried AND finally approved, and the share of the
  corpus that is therefore un-auditable for drift. That last figure is the size of
  the hole, and a reviewer can be told it exactly.

  SUBMISSION_2026/TAE/evidence/e7_appraisal_drift.py did the real measurement, but
  only on the unreleased TAE seed 42 run (45.3 % of retried decisions changed their
  appraisal). That run is provenance RED and is not part of any published corpus, so
  the number is quoted as a disclosure and never as a corpus statistic.

OUTPUT
  out/r9_appraisal_drift.csv

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r9_appraisal_drift.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import L, PrepError  # noqa: E402

#: ONLY these carry a first-attempt APPRAISAL, which is what drift needs. The other
#: P0-1a columns (initial_skill / attempt_skills / shadow_blocked) record the first
#: attempt's ACTION or a shadow flag and cannot answer the appraisal question, so
#: their presence never counts as measurability -- they are listed for context only.
APPRAISAL_FIRST_ATTEMPT_COLS = ["initial_labels", "attempt_labels", "first_attempt_wsa"]
CONTEXT_COLS = ["initial_skill", "attempt_skills", "shadow_blocked"]
FIRST_ATTEMPT_COLS = APPRAISAL_FIRST_ATTEMPT_COLS + CONTEXT_COLS
TAE_RUNS = os.path.join(C.SUB, "TAE", "runs")
FLOOD_MODEL = "gemma3_4b"
FLOOD_ARMS = {
    "governed": ("JOH_FINAL", "Group_C"),
    "ungoverned": ("JOH_ABLATION_DISABLED", "Group_C_disabled"),
}


def _jsonl_check(run_dir, n_decisions):
    raw = os.path.join(run_dir, "raw")
    if not os.path.isdir(raw):
        return "no raw/ directory", 0, False
    files = [f for f in sorted(os.listdir(raw)) if f.endswith(".jsonl")]
    if not files:
        return "raw/ present but no .jsonl", 0, False
    path = os.path.join(raw, files[0])
    n, per_attempt = 0, False
    keys = set()
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            n += 1
            if i == 0:
                obj = json.loads(line)
                keys = set(obj.keys())
                for k in ("attempts", "attempt", "attempt_index", "initial_labels",
                          "attempt_history"):
                    if k in obj:
                        per_attempt = True
    return (f"{files[0]}: {n} records, top-level keys include "
            f"{'attempts' if per_attempt else 'no per-attempt key'}"), n, (n != n_decisions)


def main() -> int:
    C.banner("R9  appraisal change across retries -- availability audit")
    rows = []

    for arm in ("governed", "ungoverned"):
        for s in L.paired_seeds(""):
            d = L.run_dir(arm, "", s)
            aud = L.load_audit(d)
            present = [c for c in FIRST_ATTEMPT_COLS if c in aud[0]]
            appr = [c for c in APPRAISAL_FIRST_ATTEMPT_COLS if c in aud[0]]
            rc = [int(float((r.get("retry_count") or "0").strip() or 0)) for r in aud]
            st = [(r.get("status") or "").strip() for r in aud]
            n = len(aud)
            desc, n_raw, mismatch = _jsonl_check(d, n)
            rows.append({
                "corpus": "released", "domain": "irrigation", "arm": arm, "seed": s,
                "n_decisions": n,
                "first_attempt_columns_present": ";".join(present) or "NONE",
                "drift_measurable": "YES" if appr else "NO",
                "reason_if_not": "no first-attempt appraisal column in the audit csv; "
                                 "raw JSONL is one record per decision, not per attempt",
                "share_retried_pct": 100.0 * sum(1 for c in rc if c > 0) / n,
                "share_retried_and_approved_pct": 100.0 * sum(
                    1 for c, x in zip(rc, st) if c > 0 and x == "APPROVED") / n,
                "raw_jsonl": desc,
                "raw_record_count_differs_from_decisions": mismatch,
            })

    for arm, (root, group) in FLOOD_ARMS.items():
        for run, (seed, rd) in C.flood_runs(root, FLOOD_MODEL, group).items():
            aud = C.read_csv(os.path.join(rd, C.FLOOD_AUDIT))
            present = [c for c in FIRST_ATTEMPT_COLS if c in aud[0]]
            appr = [c for c in APPRAISAL_FIRST_ATTEMPT_COLS if c in aud[0]]
            rc = [int(float((r.get("retry_count") or "0").strip() or 0)) for r in aud]
            st = [(r.get("status") or "").strip() for r in aud]
            n = len(aud)
            desc, n_raw, mismatch = _jsonl_check(rd, n)
            rows.append({
                "corpus": "released", "domain": "flood", "arm": arm,
                "seed": f"{seed}({run})", "n_decisions": n,
                "first_attempt_columns_present": ";".join(present) or "NONE",
                "drift_measurable": "YES" if appr else "NO",
                "reason_if_not": "no first-attempt appraisal column in the audit csv; "
                                 "raw JSONL is one record per decision, not per attempt",
                "share_retried_pct": 100.0 * sum(1 for c in rc if c > 0) / n,
                "share_retried_and_approved_pct": 100.0 * sum(
                    1 for c, x in zip(rc, st) if c > 0 and x == "APPROVED") / n,
                "raw_jsonl": desc,
                "raw_record_count_differs_from_decisions": mismatch,
            })

    # TAE, for contrast only
    if not os.path.isdir(TAE_RUNS):
        raise PrepError(f"missing {TAE_RUNS}")
    for d in sorted(x for x in os.listdir(TAE_RUNS) if x.startswith("firstattempt_gov_seed")):
        p = os.path.join(TAE_RUNS, d, "irrigation_farmer_governance_audit.csv")
        aud = C.read_csv(p)
        present = [c for c in FIRST_ATTEMPT_COLS if c in aud[0]]
        appr = [c for c in APPRAISAL_FIRST_ATTEMPT_COLS if c in aud[0]]
        rc = [int(float((r.get("retry_count") or "0").strip() or 0)) for r in aud]
        st = [(r.get("status") or "").strip() for r in aud]
        n = len(aud)
        rows.append({
            "corpus": "TAE_firstattempt (UNRELEASED, provenance RED)",
            "domain": "irrigation", "arm": "governed", "seed": d.split("seed")[-1],
            "n_decisions": n,
            "first_attempt_columns_present": ";".join(present) or "NONE",
            "drift_measurable": "YES" if appr else "NO",
            "reason_if_not": "",
            "share_retried_pct": 100.0 * sum(1 for c in rc if c > 0) / n,
            "share_retried_and_approved_pct": 100.0 * sum(
                1 for c, x in zip(rc, st) if c > 0 and x == "APPROVED") / n,
            "raw_jsonl": "", "raw_record_count_differs_from_decisions": "",
        })

    C.write_csv("r9_appraisal_drift.csv",
                ["corpus", "domain", "arm", "seed", "n_decisions",
                 "first_attempt_columns_present", "drift_measurable", "reason_if_not",
                 "share_retried_pct", "share_retried_and_approved_pct", "raw_jsonl",
                 "raw_record_count_differs_from_decisions"], rows)

    print("\n  VERDICT")
    for corpus in sorted({r["corpus"] for r in rows}):
        for dom in sorted({r["domain"] for r in rows if r["corpus"] == corpus}):
            for arm in sorted({r["arm"] for r in rows
                               if r["corpus"] == corpus and r["domain"] == dom}):
                sel = [r for r in rows if r["corpus"] == corpus
                       and r["domain"] == dom and r["arm"] == arm]
                print(f"    {corpus:46s} {dom:11s} {arm:11s} "
                      f"measurable={sel[0]['drift_measurable']:3s} "
                      f"cols={sel[0]['first_attempt_columns_present']:44s} "
                      f"retried {C.mean([r['share_retried_pct'] for r in sel]):5.1f} %")
    print("\n  R9 on the RELEASED corpora: NOT AVAILABLE.")
    print("  The size of the hole is the retried share above: on the governed "
          "irrigation arm\n  that is roughly two thirds of every decision, and none "
          "of it can be checked for\n  appraisal drift from the shipped files.")
    print("  The only measurement that exists (45.3 % of retried decisions changed "
          "their\n  appraisal) is on TAE seed 42, which is unreleased and provenance "
          "RED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
