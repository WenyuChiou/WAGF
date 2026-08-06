#!/usr/bin/env python
"""The flood-as-control numbers, on the one basis the B5 gate permits.

    python ICLR2027/flood_control_contrasts.py

Writes ICLR2027/flood_control_contrasts.csv and prints the same table.

WHY THIS SCRIPT EXISTS
----------------------
`SUBMISSION_2026/TAE/evidence/e2_flood_instrument.py` rules that flood deltas may be
printed "on the PER-RUN-MEAN basis". A pooled-row computation over the same corpus gives
different figures -- I made that mistake once before this file existed, and it moved the
gemma3:4b cell from -1.16 to -1.24. One source, one basis, so the paper and any figure
cannot silently disagree.

WHAT IT COMPUTES
----------------
For every model cell in both settings, the contrast in the prevalence of the HIGH
appraisal that the conformance statistic conditions on:

    share(arm)  = 100 * (rows whose appraisal label is H or VH) / (all rows)
                  computed per RUN, then averaged across runs
    contrast    = share(no-validator) - share(with-validators)

The appraisal column is `construct_WSA_LABEL` in irrigation and `construct_TP_LABEL` in
flood. **Blank labels stay in the denominator and are not HIGH** -- gate disclosure (a):
the with-validators arm censors the appraisal on retry-exhausted rows, and dropping those
rows would silently change the denominator between arms.

Labels are upper-cased before the membership test -- gate disclosure (c).

WHAT IT IS FOR
--------------
The claim it supports: the same validator stack, in a setting where enforcement rarely
binds, produces no comparable shift. Irrigation and flood share the harness, the
governance code, the audit path and this measure -- so a separation between them is
evidence that the shift is not an artefact of the instrument.

BACKLOG B6 -- SETTLED 2026-08-06, AUTHOR'S DECISION: EXCLUDE THE RUN
--------------------------------------------------------------------
`JOH_FINAL/gemma3_4b/Group_C/Run_1` ran a different prompt: four response fields, no
MULTI-ACTION block, 2,480 characters against 2,972 in its four siblings. It is therefore
not a replicate of the same condition, and it is excluded from the flood gemma3:4b
governed arm.

Effect on that cell: **-1.16 including it, +0.35 excluding it.** Both sit well inside the
flood range, so the separation from irrigation is unaffected either way -- the exclusion
is about not averaging a different prompt into a per-run mean, not about moving a result.

TWO CONSEQUENCES THAT MUST BE DISCLOSED WHEREVER THAT CELL IS PRINTED
--------------------------------------------------------------------
1. **The arms become unequal in n for that cell**: 4 governed runs against 5 no-validator
   runs. Tolerable on a mean-of-per-run-means, which is the basis the B5 gate mandates,
   but it is not a paired comparison and must not be described as one.
2. **The exclusion applies to the appraisal-share contrast computed here.** Any other
   flood statistic taken from that cell elsewhere in the paper must apply the same
   exclusion or state that it does not. Two numbers from the same cell on different run
   sets is exactly the class of defect this project has already recorded twice.

`--keep-b6` recomputes with the run included, for checking the sensitivity.
"""
from __future__ import annotations

import csv
import os
import statistics as st
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "SUBMISSION_2026", "TAE", "evidence"))
import _data as D  # noqa: E402

HIGH = {"H", "VH"}
# The gemma3:4b flood governed run with the divergent prompt. `flood_runs` returns a dict
# keyed by the run NUMBER as an int, so the key is 1 and not the directory name "Run_1" --
# an earlier version of this file skipped on the directory name, matched nothing, and
# reported the excluded figure as identical to the included one.
B6_RUN = "1"


def _runs(getter, arm, key):
    r = getter(arm, key)
    return list(r.items()) if isinstance(r, dict) else list(enumerate(r))


def share_per_run(getter, arm, key, column, skip=None):
    """Mean over runs of each run's HIGH-appraisal share. Blanks stay in the denominator."""
    out = {}
    for run_id, run_dir in _runs(getter, arm, key):
        if skip is not None and str(run_id) == skip:
            continue
        n = high = 0
        for row in D.load_audit(run_dir):
            n += 1
            if (row.get(column) or "").strip().upper() in HIGH:
                high += 1
        if n:
            out[str(run_id)] = 100.0 * high / n
    return out


def cell(getter, key, column, skip=None):
    g = share_per_run(getter, "gov", key, column, skip)
    n = share_per_run(getter, "noval", key, column)
    if not g or not n:
        return None
    gm, nm = st.mean(g.values()), st.mean(n.values())
    return dict(gov=gm, noval=nm, contrast=nm - gm, n_gov=len(g), n_noval=len(n))


KEEP_B6 = "--keep-b6" in sys.argv

rows = []
for m in D.IRRIGATION_MODELS:
    c = cell(D.irrigation_runs, m.prefix, "construct_WSA_LABEL")
    if c:
        rows.append(dict(setting="irrigation", model=m.label, note="", **c))

for m in D.FLOOD_MODELS:
    b6 = (m.label == "gemma3:4b") and not KEEP_B6
    c = cell(D.flood_runs, m.label, "construct_TP_LABEL", skip=B6_RUN if b6 else None)
    if c:
        note = ""
        if m.label == "gemma3:4b":
            other = cell(D.flood_runs, m.label, "construct_TP_LABEL",
                         skip=None if b6 else B6_RUN)
            side = "including" if b6 else "excluding"
            note = (f"B6 run {'EXCLUDED' if b6 else 'INCLUDED'}; "
                    f"{other['contrast']:+.2f} {side} it" if other else "B6")
        rows.append(dict(setting="flood", model=m.label, note=note, **c))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flood_control_contrasts.csv")
if KEEP_B6:
    # --keep-b6 is a sensitivity check, not the decision of record. It must never overwrite
    # the pinned CSV: a run of the check would otherwise silently replace the file the
    # paper's numbers are read from, and nothing would look wrong afterwards.
    print("  [--keep-b6] sensitivity check only; CSV NOT written\n")
else:
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["setting", "model", "gov", "noval", "contrast",
                                           "n_gov", "n_noval", "note"])
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})

print(f"{'setting':<11} {'model':<15} {'with val':>9} {'no val':>9} {'contrast':>9}  note")
print("-" * 78)
for r in rows:
    print(f"{r['setting']:<11} {r['model']:<15} {r['gov']:8.2f}% {r['noval']:8.2f}% "
          f"{r['contrast']:+9.2f}  {r['note']}")

for s in ("irrigation", "flood"):
    d = [r["contrast"] for r in rows if r["setting"] == s]
    print(f"\n  {s:<11} n={len(d)}   range {min(d):+.2f} .. {max(d):+.2f}   mean {st.mean(d):+.2f}")

irr = [r["contrast"] for r in rows if r["setting"] == "irrigation"]
fld = [r["contrast"] for r in rows if r["setting"] == "flood"]
gap = min(irr) - max(fld)
print(f"\n  separation: min(irrigation) {min(irr):+.2f} vs max(flood) {max(fld):+.2f}"
      f"  ->  {'COMPLETE, gap %.2f pp' % gap if gap > 0 else 'RANGES OVERLAP'}")
print(f"\n  written: {OUT}" if not KEEP_B6 else
      "\n  nothing written -- rerun without --keep-b6 to refresh the CSV")
