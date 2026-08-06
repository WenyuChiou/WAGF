#!/usr/bin/env python
"""run_all.py -- regenerate every TAE evidence artefact, in order, from raw data.

    python SUBMISSION_2026/TAE/evidence/run_all.py

Runs, in this order:

    1. _data.py                module self-test (15 contamination guards + 7 sections)
    2. e0_year1_exogeneity.py  the cornerstone premise: year-1 worlds identical
    3. e1_first_attempt_limits.py
                               the section 5/8 limitation: the unselected
                               first-attempt appraisal is not in this corpus
    4. e2_flood_instrument.py  the B5 gate: both flood arms measure threat
                               appraisal with ONE instrument, or flood prints
                               no numbers at all
    5. e4_world_fixed_decomposition.py
                               the mechanism: hold the world state fixed and the
                               appraisal shift falls from +45.7 pp to ~0
    6. e5_uniform_null.py      the uniform-random null, testable only against a
                               design-fixed denominator
    7. e6_antecedent_conjunction.py
                               the specification check: the enforced rule's
                               antecedent is a CONJUNCTION and both conjuncts are
                               agent-written, so no single marginal is "the
                               antecedent"
    8. table1_cells.py         the per-cell table -> evidence/table1_cells.csv
    9. table1_manuscript_crosscheck.py
                               the manuscript Table 1 -> canonical CSV check
   10. reproducibility_inventory.py
                               the selected LLM-run manifest inventory
   11. fig1_rule_layers.py     Figure 2 -> figures/fig1_rule_layers.{png,pdf,csv}
   12. fig2_mechanism.py       Figure 3 -> figures/fig2_mechanism.{png,pdf,csv}
   13. fig3_consequence.py     Figure 4 -> figures/fig3_consequence.{png,pdf,csv}
   14. _verify_pipeline.py     independent re-derivation of the headline numbers

Steps 2, 3, 4, 5, 6 and 7 write no artefact. They run early because each checks a PREMISE
rather than producing a number. If the two arms' year-1 worlds are not identical,
Fig 2a's year-1 null cannot be read as "same world, different report", and the
figures downstream are still correct but mean something else. If step 3 fails,
the paper's own stated limitation is wrong -- the first attempt would be on disk
after all -- and sections 5 and 8 have to be rewritten before anything else is.
If step 4 fails, every flood delta compares two different measuring devices and
none of them may be printed. If step 7 fails, the coping conjunct is a fixed
covariate after all and the manuscript's wording for its denominator changes.

Step 14 imports nothing from _data.py -- different libraries (pandas / numpy /
scipy rather than csv + a hand-rolled incomplete beta), literal per-seed paths
rather than regex discovery, every rate recomputed from the raw column. It runs
last because agreement between two independent implementations is only evidence
once the first one has been exercised. It writes no artefact.

Order otherwise matters only in that _data.py's self-test is the cheapest way to learn
that the data roots moved or a run directory disappeared; every later script
imports the same module, so a failure there explains all the others. Nothing
downstream consumes an upstream script's output file -- each figure reads the
raw results itself -- so a later script is still run after an earlier one
fails, and the summary reports the whole set rather than the first casualty.

EXIT CODE
    0  every script exited 0
    1  at least one script exited non-zero, or crashed, or timed out

A NON-ZERO EXIT IS NOT ALWAYS A CRASH. The analysis scripts are written to
fail loudly rather than silently: table1_cells.py exits 1 if any cell
disagrees with the brief's verified list, and fig2_mechanism.py exits 1 if any
of its cross-checks disagrees. Read the captured tail -- a disagreement is a
finding, and it is meant to stop the pipeline so it cannot be missed.

This runner deliberately does NOT special-case those exit codes into "pass".
Suppressing a script's own alarm here would defeat the reason it was written.

No shell=True anywhere; every child is launched as an argv list with
sys.executable, so no part of a path is ever parsed by a shell.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
TAE = os.path.dirname(HERE)
FIGURES = os.path.join(TAE, "figures")

# (filename, one-line purpose, artefacts it is expected to write)
SCRIPTS = [
    (
        "_data.py",
        "shared data-access module self-test (contamination guards + join checks)",
        [],
    ),
    (
        "e0_year1_exogeneity.py",
        "cornerstone premise -- the two arms' year-1 worlds are exactly identical",
        [],
    ),
    (
        "e1_first_attempt_limits.py",
        "sections 5/8 limitation -- the first-attempt appraisal is not in this corpus",
        [],
    ),
    (
        "e2_flood_instrument.py",
        "B5 gate -- do both flood arms measure threat appraisal with one instrument",
        [],
    ),
    (
        "e4_world_fixed_decomposition.py",
        "descriptive recorded-world reweighting -- the appraisal shift leaves a small residual",
        [],
    ),
    (
        "e5_uniform_null.py",
        "the uniform-random null, testable only against a design-fixed denominator",
        [],
    ),
    (
        "e6_antecedent_conjunction.py",
        "specification check -- the antecedent is a conjunction and both conjuncts move",
        [],
    ),
    (
        "table1_cells.py",
        "per-cell table, both testbeds, both action readings",
        [os.path.join(HERE, "table1_cells.csv")],
    ),
    (
        "table1_manuscript_crosscheck.py",
        "manuscript Table 1 cross-check against the canonical evidence CSV",
        [],
    ),
    (
        "reproducibility_inventory.py",
        "selected LLM-run manifest inventory; absent metadata stays absent",
        [os.path.join(HERE, "reproducibility_inventory.csv")],
    ),
    (
        "fig0_problem_schematic.py",
        "Figure 1 -- image-generated paper schematic; values re-checked against NUMBERS.md",
        # Figure numbers below are the numbers AS TYPESET IN THE MANUSCRIPT.
        # The filenames are one lower because fig0_ was inserted later:
        # fig0_=Fig 1, fig1_=Fig 2, fig2_=Fig 3, fig3_=Fig 4. Do not "fix"
        # the filenames to match; the manuscript markers are the authority
        # (paper/manuscript.md, the "<!-- FIGURE n -->" comments).
        [],
    ),
    (
        "fig1_rule_layers.py",
        "Figure 2 -- what causes a rejection, by arm and by rule kind",
        [os.path.join(FIGURES, "fig1_rule_layers." + e) for e in ("png", "pdf", "csv")],
    ),
    (
        "fig2_mechanism.py",
        "Figure 3 -- the world moved, and the reported appraisal followed it",
        [os.path.join(FIGURES, "fig2_mechanism." + e) for e in ("png", "pdf", "csv")],
    ),
    (
        "fig3_consequence.py",
        "Figure 4 -- removing the conditioning shrinks the reported effect",
        [os.path.join(FIGURES, "fig3_consequence." + e) for e in ("png", "pdf", "csv")],
    ),
    (
        "_verify_pipeline.py",
        "independent re-derivation of the headline numbers (imports nothing from _data)",
        [],
    ),
]

# Generous: the whole set runs in well under two minutes on a laptop, but the
# irrigation audit CSVs are large and a cold filesystem cache is slow.
TIMEOUT_S = 1800

BAR = "=" * 100
RULE = "-" * 100

# Tail lines echoed for a failing script, so the operator does not have to
# re-run it by hand to see what went wrong.
FAIL_TAIL_LINES = 40


def _banner(idx: int, total: int, name: str, purpose: str) -> None:
    print()
    print(BAR)
    print(f"[{idx}/{total}]  {name}")
    print(f"         {purpose}")
    print(BAR)
    sys.stdout.flush()


def _missing(paths):
    return [p for p in paths if not os.path.isfile(p)]


def main() -> int:
    if not os.path.isdir(FIGURES):
        os.makedirs(FIGURES, exist_ok=True)

    print(BAR)
    print("TAE SUBMISSION -- REGENERATE ALL EVIDENCE")
    print(BAR)
    print(f"python     : {sys.version.split()[0]}  ({sys.executable})")
    print(f"evidence   : {HERE}")
    print(f"figures    : {FIGURES}")
    print(f"scripts    : {len(SCRIPTS)}")
    print("sign convention throughout: Delta = (no-validator) MINUS (with-validators);")
    print("                            positive means the validators LOWERED the quantity.")
    sys.stdout.flush()

    results = []
    total = len(SCRIPTS)
    t_all = time.time()

    for i, (name, purpose, artefacts) in enumerate(SCRIPTS, start=1):
        path = os.path.join(HERE, name)
        _banner(i, total, name, purpose)

        if not os.path.isfile(path):
            print(f"MISSING SCRIPT: {path}")
            results.append((name, "MISSING", None, 0.0, ["script file not found"]))
            continue

        t0 = time.time()
        captured = ""
        try:
            # check=False: we aggregate rather than abort, so one loud
            # disagreement does not hide the state of the other four.
            proc = subprocess.run(
                [sys.executable, path],
                cwd=HERE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT_S,
                check=False,
            )
            captured = proc.stdout or ""
            code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            captured = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            code = None
            print(captured, end="" if captured.endswith("\n") else "\n")
            dt = time.time() - t0
            print(f"\nTIMEOUT after {TIMEOUT_S}s")
            results.append((name, "TIMEOUT", None, dt, [f"exceeded {TIMEOUT_S}s"]))
            continue
        except OSError as exc:
            dt = time.time() - t0
            print(f"\nCOULD NOT LAUNCH: {exc}")
            results.append((name, "ERROR", None, dt, [str(exc)]))
            continue

        dt = time.time() - t0
        try:
            print(captured, end="" if captured.endswith("\n") else "\n")
        except UnicodeEncodeError:
            # A non-UTF-8 console (Windows cp950/cp1252 is the default here) cannot
            # render every captured character. Degrade the glyph rather than abort:
            # losing a character to the terminal must never be reported as a failing
            # pipeline, which is what happened on 2026-08-01 before this guard.
            enc = sys.stdout.encoding or "ascii"
            sys.stdout.write(captured.encode(enc, "replace").decode(enc))
            if not captured.endswith("\n"):
                sys.stdout.write("\n")

        notes = []
        if code == 0:
            status = "PASS"
        else:
            status = "FAIL"
            notes.append(f"exit code {code}")
            tail = captured.rstrip().splitlines()[-FAIL_TAIL_LINES:]
            print(RULE)
            print(f"LAST {len(tail)} LINES OF {name} (exit {code})")
            print(RULE)
            for line in tail:
                print("  | " + line)

        gone = _missing(artefacts)
        if gone:
            # Report separately from the exit code: a script can exit non-zero
            # on a disagreement and still have written its figure.
            notes.append(f"{len(gone)} expected artefact(s) not on disk")
            print(RULE)
            print(f"EXPECTED ARTEFACTS MISSING AFTER {name}:")
            for p in gone:
                print("  - " + p)
            if status == "PASS":
                status = "FAIL"
        elif artefacts:
            notes.append(f"{len(artefacts)} artefact(s) written")

        print(RULE)
        print(f"{name}: {status}   exit={code}   {dt:.1f}s")
        results.append((name, status, code, dt, notes))
        sys.stdout.flush()

    dt_all = time.time() - t_all

    print()
    print(BAR)
    print("SUMMARY")
    print(BAR)
    print(f"{'script':<28} {'status':<8} {'exit':>5} {'sec':>7}  notes")
    print(RULE)
    for name, status, code, dt, notes in results:
        code_s = "-" if code is None else str(code)
        print(f"{name:<28} {status:<8} {code_s:>5} {dt:>7.1f}  {'; '.join(notes)}")
    print(RULE)

    n_pass = sum(1 for r in results if r[1] == "PASS")
    n_fail = len(results) - n_pass
    print(f"total {len(results)} script(s): {n_pass} PASS, {n_fail} not-PASS   ({dt_all:.1f}s wall)")

    if n_fail:
        print()
        print("NOT ALL SCRIPTS EXITED 0.")
        print("Before assuming a bug: these scripts exit non-zero ON PURPOSE when a")
        print("computed value disagrees with the verified list in the brief. Read the")
        print("captured tail above. A disagreement is a finding to report, never a")
        print("thing to tune the code until it stops saying.")
        print(BAR)
        return 1

    print()
    print("ALL SCRIPTS CLEAN. Every figure, csv and table above is regenerated from")
    print("the raw run directories, and every value cross-checked against the brief.")
    print(BAR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
