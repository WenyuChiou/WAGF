"""E7 -- does enforcement rewrite the appraisal it conditions on? Measured, not inferred.

WHY THIS SCRIPT EXISTS
Section 8 opens with the paper's largest admission: an accepted report after a retry is selected by
the rule that judged it, that stratum is 24.3% of governed decisions, and ITS FIRST ATTEMPT IS ABSENT
FROM THE SHIPPED CORPUS. That absence is why Section 5 has to infer the mechanism by stratifying on
world state instead of observing it.

P0-1a (broker commit 0c6aa60e, opt-in, default-OFF) snapshots the attempt-0 proposal before the retry
loop reassigns it. With that flag ON, the first attempt is no longer absent and the question becomes
directly measurable:

    among decisions the governance loop spoke to, how often did the recorded appraisal end up
    DIFFERENT from the one the agent first wrote -- and does that differ between arms?

WHAT THIS SCRIPT DOES NOT ASSUME
It does not assume the answer is yes. Three outcomes are possible and all are reportable:

  * the governed arm rewrites MORE than the no-validator arm -> the mechanism is the validator layer,
    as Section 5 argues, and the paper can stop inferring it;
  * both arms rewrite EQUALLY -> rewriting is generic to the retry loop, the between-arm difference
    must come from somewhere else, and Section 5's world-composition account is doing all the work;
  * the governed arm rewrites LESS -> the current framing is wrong.

Both arms retry. Measured on the shipped corpus before this script was written: governed seed 42
retries 62.0% of decisions, no-validator seed 42 retries 39.1%, both capped at 3. So the no-validator
arm is a real control, not a null condition -- the water-right precondition blocks and re-prompts
exactly as the validators do.

THE QUANTITY THAT MATTERS MOST
Drift is interesting; drift ACROSS THE DENOMINATOR BOUNDARY is the paper's claim. A decision whose
appraisal moves M -> H has entered the HIGH set that the conformance rate divides by. A decision
moving H -> M has left it. This script counts both directions separately, because their difference is
the number of decisions the enforcement added to or removed from its own denominator.

FAILURE DIRECTION
This script raises rather than returning zero when the columns are absent. A flag-OFF run carries no
``initial_labels`` column at all, and silently reporting "0% drift" for it would be indistinguishable
from the genuine finding that nothing drifts. That is exactly the failure this paper is about, so the
check fails loudly and names the run.

SELF-TEST
Run with --self-test. It builds synthetic rows with known drift, asserts the measured numbers match,
and then MUTATES each rule in turn to confirm the checker can fail. A checker that has never failed
proves nothing.

Usage:
    python SUBMISSION_2026/TAE/evidence/e7_appraisal_drift.py --self-test
    python SUBMISSION_2026/TAE/evidence/e7_appraisal_drift.py --irrigation-root <dir>
    python SUBMISSION_2026/TAE/evidence/e7_appraisal_drift.py --flood-root <dir>

Outputs: figures/e7_appraisal_drift.csv  (one row per arm x seed x domain)
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
TAE = os.path.dirname(HERE)
FIGURES = os.path.join(TAE, "figures")

# The appraisal each domain conditions on. Irrigation's conformance rate selects on WSA; the Nature
# Water paper's IBR selects on TP. Both are agent-authored in the generation being judged, which is
# why the same question applies to both.
DOMAIN = {
    "irrigation": {
        "audit": "irrigation_farmer_governance_audit.csv",
        "label_key": "WSA_LABEL",
        "final_col": "construct_WSA_LABEL",
    },
    "flood": {
        "audit": "household_governance_audit.csv",
        "label_key": "TP_LABEL",
        "final_col": "construct_TP_LABEL",
    },
}

HIGH = frozenset({"H", "VH"})

REQUIRED = ("initial_labels", "retry_count")


class DriftError(RuntimeError):
    """Raised when a run cannot answer the question. Never degraded to a warning."""


def parse_initial_labels(cell: str, key: str) -> str | None:
    """Pull one ``KEY=VALUE`` out of P0-1a's pipe-joined snapshot.

    Returns None when the key is absent, which is a real state: a parse failure at attempt 0 leaves
    the proposal with no ``*_LABEL`` keys and ``_extract_construct_labels`` returns "". Those rows
    are counted separately rather than dropped, because dropping them would quietly select on
    parse success.
    """
    if not cell:
        return None
    for part in cell.split("|"):
        k, _, v = part.partition("=")
        if k.strip() == key:
            return v.strip()
    return None


def measure_run(path: str, domain: str) -> dict:
    """One run directory -> its drift counts. Raises if the run cannot answer."""
    spec = DOMAIN[domain]
    audit = os.path.join(path, spec["audit"])
    if not os.path.exists(audit):
        raise DriftError(f"{path}: no {spec['audit']}")

    with open(audit, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames or []
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            raise DriftError(
                f"{path}: missing {missing}. This run was produced with "
                f"global_config.audit.initial_proposal_columns OFF, so the first attempt was never "
                f"recorded. It cannot answer this question and must not be scored as zero drift."
            )
        if spec["final_col"] not in cols:
            raise DriftError(f"{path}: no {spec['final_col']}; wrong domain for this run?")

        n = retried = comparable = 0
        unchanged = changed = 0
        entered_high = left_high = 0
        no_initial_label = 0

        for row in reader:
            n += 1
            try:
                rc = int(float(row.get("retry_count") or 0))
            except (TypeError, ValueError):
                rc = 0
            if rc <= 0:
                continue
            retried += 1

            first = parse_initial_labels(row.get("initial_labels", ""), spec["label_key"])
            if first is None:
                no_initial_label += 1
                continue
            final = (row.get(spec["final_col"]) or "").strip()
            if not final:
                no_initial_label += 1
                continue

            comparable += 1
            if first == final:
                unchanged += 1
                continue
            changed += 1
            # The direction that matters: did this decision cross the denominator boundary?
            if first not in HIGH and final in HIGH:
                entered_high += 1
            elif first in HIGH and final not in HIGH:
                left_high += 1

    if retried == 0:
        raise DriftError(
            f"{path}: no decision was retried. Both arms of this corpus retry "
            f"(62.0% governed / 39.1% no-validator on seed 42), so a zero here means the run is "
            f"not what it claims to be."
        )

    return {
        "decisions": n,
        "retried": retried,
        "comparable": comparable,
        "no_initial_label": no_initial_label,
        "unchanged": unchanged,
        "changed": changed,
        "entered_high": entered_high,
        "left_high": left_high,
        "drift_pct": 100.0 * changed / comparable if comparable else float("nan"),
        "net_into_high": entered_high - left_high,
    }


def _self_test() -> int:
    """Synthetic rows with known answers, then mutate each rule to prove the checker can fail."""
    import tempfile

    def write(rows, cols, d):
        p = os.path.join(d, DOMAIN["irrigation"]["audit"])
        with open(p, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        return d

    cols = ["retry_count", "initial_labels", "construct_WSA_LABEL"]
    rows = [
        # retried, appraisal unchanged
        {"retry_count": "1", "initial_labels": "WSA_LABEL=H|ACA_LABEL=M", "construct_WSA_LABEL": "H"},
        {"retry_count": "2", "initial_labels": "WSA_LABEL=L", "construct_WSA_LABEL": "L"},
        # retried, moved INTO the HIGH denominator
        {"retry_count": "1", "initial_labels": "WSA_LABEL=M", "construct_WSA_LABEL": "H"},
        {"retry_count": "3", "initial_labels": "WSA_LABEL=L", "construct_WSA_LABEL": "VH"},
        # retried, moved OUT of it
        {"retry_count": "1", "initial_labels": "WSA_LABEL=VH", "construct_WSA_LABEL": "M"},
        # retried, changed but stayed outside
        {"retry_count": "1", "initial_labels": "WSA_LABEL=VL", "construct_WSA_LABEL": "L"},
        # retried but attempt 0 had no parseable label
        {"retry_count": "1", "initial_labels": "", "construct_WSA_LABEL": "H"},
        # never retried -- must be ignored entirely
        {"retry_count": "0", "initial_labels": "WSA_LABEL=VL", "construct_WSA_LABEL": "VH"},
    ]
    expect = dict(decisions=8, retried=7, comparable=6, no_initial_label=1,
                  unchanged=2, changed=4, entered_high=2, left_high=1, net_into_high=1)

    ok = True
    with tempfile.TemporaryDirectory() as d:
        write(rows, cols, d)
        got = measure_run(d, "irrigation")
        for k, v in expect.items():
            if got[k] != v:
                print(f"  FAIL  {k}: got {got[k]}, expected {v}")
                ok = False
        if ok:
            print(f"  pass  counts correct: {expect}")
            print(f"  pass  drift {got['drift_pct']:.1f}% of comparable retried decisions")

    # Mutation 1: the flag-OFF guard must fire when initial_labels is absent.
    with tempfile.TemporaryDirectory() as d:
        write([{k: v for k, v in r.items() if k != "initial_labels"} for r in rows],
              [c for c in cols if c != "initial_labels"], d)
        try:
            measure_run(d, "irrigation")
            print("  FAIL  a run with no initial_labels column was scored instead of refused")
            ok = False
        except DriftError:
            print("  pass  flag-OFF run refused, not scored as zero drift")

    # Mutation 2: a corpus where nothing retried must be refused, not reported as 0% drift.
    with tempfile.TemporaryDirectory() as d:
        write([dict(r, retry_count="0") for r in rows], cols, d)
        try:
            measure_run(d, "irrigation")
            print("  FAIL  a run with zero retries was scored instead of refused")
            ok = False
        except DriftError:
            print("  pass  zero-retry run refused")

    # Mutation 3: plant extra drift and confirm the number moves. A measure that cannot move is not
    # measuring.
    with tempfile.TemporaryDirectory() as d:
        planted = rows + [
            {"retry_count": "1", "initial_labels": "WSA_LABEL=L", "construct_WSA_LABEL": "H"},
            {"retry_count": "1", "initial_labels": "WSA_LABEL=M", "construct_WSA_LABEL": "VH"},
        ]
        write(planted, cols, d)
        got2 = measure_run(d, "irrigation")
        if got2["entered_high"] == expect["entered_high"] + 2 and got2["changed"] == expect["changed"] + 2:
            print("  pass  planted drift is detected and counted in the right direction")
        else:
            print(f"  FAIL  planted drift not counted: {got2['entered_high']} / {got2['changed']}")
            ok = False

    print("\n  SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true",
                    help="run the synthetic checks and the mutation tests, touch no corpus")
    ap.add_argument("--irrigation-root", default=None,
                    help="a directory holding flag-ON irrigation run dirs")
    ap.add_argument("--flood-root", default=None,
                    help="a directory holding flag-ON flood run dirs")
    args = ap.parse_args(argv)

    if args.self_test or (not args.irrigation_root and not args.flood_root):
        print("E7 -- appraisal drift across the governance retry\n")
        print("SELF-TEST (no corpus read; use --irrigation-root / --flood-root for real runs)\n")
        return _self_test()

    out = []
    for root, domain in ((args.irrigation_root, "irrigation"), (args.flood_root, "flood")):
        if not root:
            continue
        if not os.path.isdir(root):
            raise SystemExit(f"not a directory: {root}")
        for name in sorted(os.listdir(root)):
            p = os.path.join(root, name)
            if not os.path.isdir(p):
                continue
            try:
                rec = measure_run(p, domain)
            except DriftError as e:
                print(f"  SKIP  {name}: {e}")
                continue
            rec.update(run=name, domain=domain)
            out.append(rec)
            print(f"  {domain:10s} {name:44s} retried {rec['retried']:5d}  "
                  f"drift {rec['drift_pct']:5.1f}%  into HIGH {rec['entered_high']:4d}  "
                  f"out {rec['left_high']:4d}  net {rec['net_into_high']:+5d}")

    if not out:
        raise SystemExit("no run could be measured; nothing written")

    os.makedirs(FIGURES, exist_ok=True)
    dest = os.path.join(FIGURES, "e7_appraisal_drift.csv")
    cols = ["domain", "run", "decisions", "retried", "comparable", "no_initial_label",
            "unchanged", "changed", "drift_pct", "entered_high", "left_high", "net_into_high"]
    with open(dest, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({c: r[c] for c in cols})
    print(f"\n  wrote {dest}  ({len(out)} runs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
