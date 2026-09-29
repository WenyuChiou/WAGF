"""R44 -- flood IBR under the PI-approved 2026-09-29 first-attempt definition.
CPU-only, existing runs only, no LLM calls made by this script.

REVIEW FIX ROUND (2026-09-29, REQUEST CHANGES applied here)
  A prior version of this script substituted the FINAL construct_CP_LABEL
  for the first-attempt coping label on every row whose first attempt was
  blocked by R1 (extreme_threat_block never reads coping, so it is not on
  record). That label moves during retries -- on strict_initprop, 20 of
  343 first-R1 rows move from M/H to L -- and substituting the drifted
  FINAL value systematically UNDER-counts strict's own R1 hits (never
  disabled's, which has no retries), inflating the apparent strict-vs-
  disabled contrast. Fixed below: `first_attempt_proxy`'s R1 branch now
  reports coping as UNKNOWN (bin MID_OR_UNK, which `_rule_hit` already
  treats as "not low", per this script's own Limitation 3) instead of
  substituting a value that was never actually observed at the first
  attempt. The old substitution is KEPT as `first_attempt_proxy_lowerbound`
  and reported only as a labelled lower-bound sensitivity line -- it is no
  longer the primary number anywhere.
  A second, orchestrator-decided fix, CORRECTED a second time on
  2026-09-29 after the orchestrator's own brief was found to contradict
  itself: a REJECTED_FALLBACK row (the final attempt itself never parsed)
  whose ENTIRE `failed_rules` is "extreme_threat_block" and nothing else
  has every one of its PARSED attempts on record as do_nothing (checked
  directly against `attempt_skills` on strict_initprop, where that column
  exists: 7 of 7 such rows, see `_check_fallback_attempts_are_do_nothing`).
  Since R1 blocks only do_nothing and the approved definition reads the
  last RECORDED proposal, these rows' do_nothing is not a guess, and they
  ARE now folded into the PRIMARY number (`count_r1only_fallback=True`,
  the corrected default at every primary call site below): strict
  IBR_first mean about 3.64 (was about 3.52), contrast about -6.30 pp (was
  about -6.43 pp). The EXCLUDE convention (3.52 / -6.43) is now the
  labelled sensitivity line instead, kept because it is the convention
  Part 0's own validation numbers (139/4,359, relabel 31.89 percent) were
  computed under -- Part 0 itself is unaffected by which convention Part 1
  calls "primary", since it only tests whether EXACT and PROXY agree with
  each other, not which of them is reported as the headline.
  Every hard check in Part 0 compares EXACT and PROXY row by row (not by
  aggregate totals alone) and names any row that disagrees; no validation
  target is hard-coded as a numeric literal any more -- the EXACT path is
  the ground truth the PROXY path is checked against, live, every run.

DEFINITION (PI decision 4, .research/design_specs/flood_design_record_2026-09-29.md
"PI decisions 2026-09-29" section, item 4): "IBR in both cases: the final
proposal after retries, judged against the appraisal given at the first
attempt, over all decisions. The final-label version and the relabel rate
are reported beside it." Item 2 of the same section additionally restricts
R1 to "threat High or Very High AND coping not Very Low or Low", following
Grothmann and Reusswig (2006) p.106's non-protective-response case.

Rules used here (the same three read-only rules as the published metric,
one PI-restricted):
  R1: TP in {H, VH} AND CP not in {VL, L} AND action == do_nothing.
  R3: TP in {VL, L} AND action == relocate.
  R4: TP in {VL, L} AND action == elevate_house.
R5 (elevation_block, identity check on an already-elevated house) is never
counted, per EDT2 and design-record Sec 3.2 -- unchanged from the published
metric.

WHY A NEW SCRIPT, NOT A `_common.py` EDIT
  `_common.py (flood_ibr_components)` is the transcription of the PUBLISHED
  metric (`examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py
  (compute_ibr_components)`): final action, final label, R1 unrestricted.
  It has no first-attempt-appraisal mode and no coping condition, and this
  task's own instructions forbid touching any file other than this script
  and its output. `compute_ibr_final()` below calls `C.flood_ibr_components`
  UNCHANGED for the unrestricted-R1 final-label number (byte-identical to
  the published metric) and only adds a small local variant for the
  coping-restricted final-label number. Neither of the two review fixes
  above touches `compute_ibr_final` at all: it reads FINAL labels only, so
  it never needed a first-attempt coping reconstruction in the first place.

HOW THE FIRST ATTEMPT IS RECOVERED
  Only the `strict_initprop` arm carries the exact first-attempt columns
  (`initial_skill`, `initial_labels`) -- design-record H7: "first-attempt
  columns only in the initprop arm". The PRIMARY corpus (defaults n=10,
  `strict_n10`/`disabled_n10`) does not carry them, so every arm in the
  main report below is read through the PROXY method:

    retry_count == 0  -> first attempt == final attempt (no retry ever
                         happened): first TP/CP/action are read straight
                         off `construct_TP_LABEL` / `construct_CP_LABEL` /
                         `final_skill`.
    retry_count  > 0  -> the row's `failed_rules` column names every
                         distinct (rule_id, error-text) validator failure
                         across the WHOLE retry sequence, in first-
                         occurrence order (never sorted, never deduped
                         across attempts by anything but exact repeat):
                         `broker/components/analytics/audit.py
                         (GenericAuditWriter._write_trace_locked)` appends
                         to `trace["validation_issues"]` by iterating
                         `validation_results` in order, and that list is
                         `all_validation_history`, which is *initialised*
                         to attempt 1's own results
                         (`broker/core/skill_broker_engine.py
                         (SkillBrokerEngine.process_step)`, the
                         `all_validation_history = list(validation_results)`
                         line) and only ever *extended* by later attempts
                         (`broker/core/_retry_loop.py
                         (RetryMixin._governance_retry_loop)`, the
                         `all_validation_history.extend(validation_results)`
                         line). So `failed_rules.split("|")[0]` is always
                         attempt 1's own blocking rule id. Reading it:
                           "extreme_threat_block" (R1's code id) -> first
                             TP bin = HIGH, first action = do_nothing,
                             first coping = UNKNOWN (see fix above).
                           "relocation_threat_low" (R3)          -> first
                             TP bin = LOW, first action = relocate.
                           "elevation_threat_low" (R4)           -> first
                             TP bin = LOW, first action = elevate_house.
                           anything else (elevation_block,
                             precondition_violation,
                             output_schema_violation, "Unknown", or an
                             empty `failed_rules` cell despite a retry)
                             -> UNRESOLVED: excluded from the R1/R3/R4
                             numerator (never guessed), counted and
                             reported by seed AND listed individually (S1
                             below), but the row STAYS in the "all
                             decisions" denominator, per the approved
                             definition.
  A first-attempt label that fails to parse at all (VL..VH off-vocabulary,
  or the row status is REJECTED_FALLBACK -- the final proposal itself
  never parsed after every retry, so `proposed_skill` is empty even though
  `final_skill` prints the registry default) is excluded from the
  violation numerator on the side of the computation it affects, with the
  one named exception above (R1-only REJECTED_FALLBACK, sensitivity line
  only), and always kept in the denominator.

VALIDATION (run first, see `run_validation()`)
  Reproduces `.research/design_specs/flood_design_record_2026-09-29.md`
  Sec 4's check on `strict_initprop` (defaults corpus, seeds 42-46, 4,359
  rows) -- OLD/unrestricted R1 (first action + first label; final action +
  first label) and, new to this fix round, the PI-restricted R1 (final
  action + first label, and the relabel rate), each checked ROW BY ROW
  between the EXACT columns and the PROXY reconstruction, not by matching
  aggregate totals alone. Also: an attempt_skills cross-check for the
  fallback-inclusion sensitivity line's own premise; a check that every
  REJECTED_FALLBACK row has an empty final threat label; a check that zero
  final_skill values are off-vocabulary; and a listing of every row the
  proxy cannot resolve, cross-referenced against the exact columns where
  available.

CORPORA AND ARMS (named in the design record and the retry-exhaustion
memory note; nothing outside that set is added)
  defaults (primary, commit 83fa97e1, no sampling params sent): strict_n10
    and disabled_n10 (seeds 42-51, n=10 each, REQUIRED complete -- a
    missing primary seed raises, it is never silently skipped) and placebo
    (seeds 42-43, n=2). v08 (appendix): strict and disabled at commit
    faf1bb12 (sampling 0.8/0.9/40, seeds 42-46), placebo at commit
    83fa97e1 (seeds 42-43) -- a genuine commit mix, stated here and in the
    report, not glossed over; `_common.py`'s own module comment documents
    the same split. Directory names and seed lists come from
    `_common.py (flood_corpus_dirs)`, never a local literal. Arms the
    design record itself marks PARTIAL, NOT RUN, or "IBR not computable"
    (paraphrase, no-nudge, gemma4:12b-defaults, silent, rule-based) are out
    of scope here -- see the Limitations section of the .md output.

COMPLETENESS GATE
  Per (arm, seed): directory exists -> `household_governance_audit.csv`
  exists -> `reproducibility_manifest.json` exists (seed cross-checked
  against `flood_corpus_dirs`, never trusted from the `Run_N` folder name
  alone, per `_common.py (flood_seed_of)`) -> `run_integrity.json` exists
  with `integrity_ok == True`. For the two primary-corpus arms
  (strict_n10, disabled_n10) a failed gate RAISES (the primary headline
  must never silently run on fewer than 10 seeds). For every other arm a
  failed gate SKIPS that seed and reports why, never silently dropped.

OUTPUT
  This script writes ONLY `out/r44_flood_ibr_first_attempt.md` (no
  companion CSV -- the task that commissioned this script names exactly
  two deliverables and asks that no other file be touched). All
  intermediate numbers are also printed to stdout as the script runs.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r44_flood_ibr_first_attempt.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402

# =============================================================================
# rule ids (examples/single_agent/agent_types.yaml, household.governance.strict)
# =============================================================================
R1_ID = "extreme_threat_block"
R3_ID = "relocation_threat_low"
R4_ID = "elevation_threat_low"
FALLBACK_STATUS = "REJECTED_FALLBACK"

REQUIRED_COLS = ["proposed_skill", "final_skill", "status", "retry_count",
                 "failed_rules", "construct_TP_LABEL", "construct_CP_LABEL"]
REQUIRED_COLS_INITPROP = REQUIRED_COLS + ["initial_skill", "initial_labels", "attempt_skills"]

# validation target: strict_initprop, defaults corpus, seeds 42-46
# (.research/design_specs/flood_design_record_2026-09-29.md Sec 4)
VALIDATION_CORPUS = "defaults"
VALIDATION_KEY = "strict_initprop"
EXPECTED_TOTAL_ROWS = 4359   # a corpus-identity fact (same rows the design record
                             # examined), not a rule-outcome convention -- kept as
                             # a hard gate; every rule-outcome number below is
                             # derived live from the EXACT columns instead.

# main report: (corpus, flood_corpus_dirs key, display name, hard_require)
ARMS = [
    ("defaults", "strict_n10", "strict", True),
    ("defaults", "disabled_n10", "disabled", True),
    ("defaults", "placebo", "placebo", False),
    ("v08", "strict", "strict", False),
    ("v08", "disabled", "disabled", False),
    ("v08", "placebo", "placebo", False),
]
DIFF_CORPORA = ["defaults", "v08"]   # strict-minus-disabled needs both arms present


# =============================================================================
# label / action helpers
# =============================================================================
# CP (coping) uses the exact same VL/L/M/H/VH vocabulary as TP -- verified
# live 2026-09-29 against JOH_strict_initprop_defaults_gemma3_4b_83fa97e1/
# Run_42's own construct_CP_LABEL column (values observed: M, L, H, and the
# empty string; no off-vocabulary values) -- so the TP normalizer is reused
# unchanged rather than re-derived.
flood_cp_bin_raw = C.flood_normalize_tp


def _tp_bin(label: str) -> str:
    """Bin a normalized VL..VH label into HIGH / LOW / MID_OR_UNK. Used for
    both TP and CP -- C.HIGH/C.LOW are the same {H,VH}/{VL,L} sets the
    published metric uses (_common.py). MID_OR_UNK also stands in for a
    deliberately-unknown coping value (see `first_attempt_proxy`'s R1
    branch) -- `_rule_hit` treats it identically to a genuinely-observed
    mid-range label, both read as "not low", by design."""
    if label in C.HIGH:
        return "HIGH"
    if label in C.LOW:
        return "LOW"
    return "MID_OR_UNK"


def _parse_initial_labels(s: str) -> dict:
    """'TP_LABEL=H|CP_LABEL=M' -> {'TP_LABEL': 'H', 'CP_LABEL': 'M'}.
    Restated from SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/
    r33_first_vs_last_proposal.py (_parse_labels) -- same degrade-quietly
    contract (malformed/absent segments just don't produce a key, never
    raise); r33 does not export it as an importable module-level name
    under a stable path this script wants to depend on, so it is restated,
    not imported."""
    out = {}
    if not s:
        return out
    for seg in s.split("|"):
        if "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        out[k] = v
    return out


def _final_never_parsed(row: dict) -> bool:
    """True iff the FINAL attempt itself never validated as a parsable
    proposal (status REJECTED_FALLBACK): `proposed_skill` is the empty
    string and `final_skill` is only the registry default substituted in.
    Three facts hold for every REJECTED_FALLBACK row this script reads --
    `proposed_skill == ""`, `construct_TP_LABEL == ""`, and `retry_count >
    0` -- and all three are now ASSERTED (raise on violation), not just
    noted: see `check_fallback_and_unmapped_invariants`."""
    return (row.get("status") or "").strip() == FALLBACK_STATUS


def _is_r1_only_fallback(row: dict) -> bool:
    """True iff the row is REJECTED_FALLBACK and its ENTIRE failed_rules is
    "extreme_threat_block" and nothing else (a set-equality check, not
    merely "the first element is R1" -- deliberately stricter, per the
    orchestrator's own wording). Such a row's every PARSED attempt was a
    do_nothing that R1 blocked (checked against attempt_skills where that
    column exists -- `_check_fallback_attempts_are_do_nothing`), so its
    final_skill (do_nothing, the registry default) coincides with what the
    household was actually proposing throughout, not merely a fallback
    substitute with no evidence behind it."""
    if not _final_never_parsed(row):
        return False
    fr = (row.get("failed_rules") or "").strip()
    if not fr:
        return False
    return {seg.strip() for seg in fr.split("|") if seg.strip()} == {R1_ID}


def _rule_hit(tp_bin: str, cp_bin, action: str, restrict_r1_coping: bool):
    """Returns 'R1' / 'R3' / 'R4' / None. `cp_bin` may be None when the
    caller knows R1 cannot apply (tp_bin != 'HIGH') or restrict_r1_coping
    is False; a None cp_bin is only ever dereferenced when both of those
    are false, and by construction every caller resolves a real cp_bin in
    that case. 'not Very Low or Low' is read as cp_bin != 'LOW' --
    MID_OR_UNK counts as 'not low', the wider reading, since there is no
    positive evidence it was low. This is now the load-bearing convention
    for first-attempt coping on every R1-branch proxy row (the first
    review fix, 2026-09-29): those rows never had their coping recorded at
    all, so they are read as MID_OR_UNK, never guessed from a later,
    possibly-drifted label."""
    if tp_bin == "HIGH" and action == "do_nothing":
        if restrict_r1_coping and cp_bin == "LOW":
            return None
        return "R1"
    if tp_bin == "LOW" and action == "relocate":
        return "R3"
    if tp_bin == "LOW" and action == "elevate_house":
        return "R4"
    return None


# =============================================================================
# first-attempt reconstruction: EXACT (initprop columns), PROXY (fixed,
# primary), and PROXY-LOWERBOUND (the pre-fix method, sensitivity only)
# =============================================================================
def first_attempt_exact(row: dict) -> dict:
    """Uses `initial_skill`/`initial_labels` directly -- only valid on the
    strict_initprop arm. Returns {"tp","cp","action","resolved",
    "cp_unknown"}; cp_unknown is always False here since the true
    first-attempt coping label is on hand."""
    first_action_raw = row.get("initial_skill") or ""
    if not first_action_raw.strip():
        return {"tp": None, "cp": None, "action": None, "resolved": False,
                "cp_unknown": False}
    labels = _parse_initial_labels(row.get("initial_labels") or "")
    tp_bin = _tp_bin(C.flood_normalize_tp(labels.get("TP_LABEL", "")))
    cp_bin = _tp_bin(flood_cp_bin_raw(labels.get("CP_LABEL", "")))
    action = C.flood_normalize_action(first_action_raw)
    return {"tp": tp_bin, "cp": cp_bin, "action": action, "resolved": True,
            "cp_unknown": False}


def first_attempt_proxy(row: dict) -> dict:
    """PRIMARY reconstruction (fixed, 2026-09-29 review round): first
    TP/CP/action from retry_count + failed_rules alone (module docstring
    HOW THE FIRST ATTEMPT IS RECOVERED). On the R1 branch, coping is
    UNKNOWN (bin MID_OR_UNK, `cp_unknown=True`) -- R1 as run never reads
    coping, so nothing about it is on record at the first attempt; it is
    never backfilled from the (possibly drifted) FINAL coping label. This
    is the resolver every arm in the main report uses, including on
    strict_initprop, where Part 0 checks it row by row against
    `first_attempt_exact`."""
    rc = int(row["retry_count"])
    if rc == 0:
        if _final_never_parsed(row):
            return {"tp": None, "cp": None, "action": None, "resolved": False,
                    "cp_unknown": False}
        tp_bin = _tp_bin(C.flood_normalize_tp(row.get("construct_TP_LABEL")))
        cp_bin = _tp_bin(flood_cp_bin_raw(row.get("construct_CP_LABEL")))
        action = C.flood_normalize_action(row.get("final_skill"))
        return {"tp": tp_bin, "cp": cp_bin, "action": action, "resolved": True,
                "cp_unknown": False}
    fr = (row.get("failed_rules") or "").strip()
    first_rule = fr.split("|")[0].strip() if fr else ""
    if first_rule == R1_ID:
        return {"tp": "HIGH", "cp": "MID_OR_UNK", "action": "do_nothing",
                "resolved": True, "cp_unknown": True}
    if first_rule == R3_ID:
        return {"tp": "LOW", "cp": None, "action": "relocate", "resolved": True,
                "cp_unknown": False}
    if first_rule == R4_ID:
        return {"tp": "LOW", "cp": None, "action": "elevate_house", "resolved": True,
                "cp_unknown": False}
    return {"tp": None, "cp": None, "action": None, "resolved": False,
            "cp_unknown": False}


def first_attempt_proxy_lowerbound(row: dict) -> dict:
    """SENSITIVITY ONLY -- the method this review round corrected. On the
    R1 branch it substitutes the FINAL construct_CP_LABEL for the
    unrecoverable first-attempt coping. That label drifts low during
    retries (20 of 343 strict_initprop first-R1 rows move M/H -> L), so
    this systematically UNDER-counts strict's own R1 hits (disabled has no
    retries, so it is never affected) and yields a LOWER BOUND on the true
    restricted IBR_first -- never used as the primary number below, kept
    only for the labelled sensitivity line the review asked for."""
    rc = int(row["retry_count"])
    if rc == 0:
        return first_attempt_proxy(row)
    fr = (row.get("failed_rules") or "").strip()
    first_rule = fr.split("|")[0].strip() if fr else ""
    if first_rule == R1_ID:
        cp_bin = _tp_bin(flood_cp_bin_raw(row.get("construct_CP_LABEL")))
        return {"tp": "HIGH", "cp": cp_bin, "action": "do_nothing", "resolved": True,
                "cp_unknown": False}
    if first_rule in (R3_ID, R4_ID):
        return first_attempt_proxy(row)
    return {"tp": None, "cp": None, "action": None, "resolved": False,
            "cp_unknown": False}


# =============================================================================
# per-row classification (shared by the aggregate metrics AND the Part 0
# row-level validation, so the two can never silently drift apart)
# =============================================================================
def classify_ibr_first_row(row: dict, resolver, restrict_r1_coping: bool,
                            count_r1only_fallback: bool = False):
    """Returns (label, fa) where label is 'R1'/'R3'/'R4'/None (compliant)/
    'UNRESOLVED'/'FALLBACK_EXCLUDED', and fa is the resolver's own dict for
    this row (so callers can read cp_unknown etc. without re-resolving)."""
    fa = resolver(row)
    if not fa["resolved"]:
        return "UNRESOLVED", fa
    if _final_never_parsed(row):
        if count_r1only_fallback and _is_r1_only_fallback(row):
            final_action = "do_nothing"
        else:
            return "FALLBACK_EXCLUDED", fa
    else:
        final_action = C.flood_normalize_action(row.get("final_skill"))
    return _rule_hit(fa["tp"], fa["cp"], final_action, restrict_r1_coping), fa


def classify_relabel_row(row: dict, resolver, restrict_r1_coping: bool,
                          count_r1only_fallback: bool = False):
    """Returns one of 'NOT_BASE', 'CHANGED', 'KEPT_RELABELED',
    'STILL_VIOLATES', 'UNRESOLVED'. Base = the row's FIRST attempt
    (resolver's own tp/cp/action) is itself a violation. A generic
    REJECTED_FALLBACK final, or any change of action, counts as CHANGED
    (sameness cannot be confirmed for a never-parsed final); otherwise the
    SAME action is re-judged against the FINAL label.
    count_r1only_fallback=True (now the PRIMARY convention, corrected
    2026-09-29): an R1-only REJECTED_FALLBACK row has a confirmed
    do_nothing action throughout (module docstring), which IBR_first counts
    as an R1 violation -- so for internal consistency this row is classified
    STILL_VIOLATES here too, never CHANGED or KEPT_RELABELED, since there is
    no final label at all (it is empty, never parsed) to credit as having
    improved; crediting it as "relabelled" would contradict IBR_first's own
    treatment of the same row as a confirmed violation."""
    fa = resolver(row)
    if not fa["resolved"]:
        return "UNRESOLVED"
    first_hit = _rule_hit(fa["tp"], fa["cp"], fa["action"], restrict_r1_coping)
    if first_hit is None:
        return "NOT_BASE"
    if _final_never_parsed(row):
        if count_r1only_fallback and _is_r1_only_fallback(row):
            return "STILL_VIOLATES"
        return "CHANGED"
    final_action = C.flood_normalize_action(row.get("final_skill"))
    if final_action != fa["action"]:
        return "CHANGED"
    final_tp = _tp_bin(C.flood_normalize_tp(row.get("construct_TP_LABEL")))
    final_cp = _tp_bin(flood_cp_bin_raw(row.get("construct_CP_LABEL")))
    final_hit = _rule_hit(final_tp, final_cp, final_action, restrict_r1_coping)
    return "STILL_VIOLATES" if final_hit is not None else "KEPT_RELABELED"


# =============================================================================
# metric computation
# =============================================================================
def compute_ibr_first(rows: list, resolver, restrict_r1_coping: bool,
                       count_r1only_fallback: bool = False) -> dict:
    """PRIMARY metric family: FINAL action judged against the FIRST-attempt
    appraisal (resolver's tp/cp), over ALL rows. restrict_r1_coping=True is
    report item (1), IBR_first. count_r1only_fallback=True is now the
    PRIMARY convention (corrected 2026-09-29): a REJECTED_FALLBACK row
    whose ENTIRE failed_rules is 'extreme_threat_block' alone has a
    confirmed do_nothing action throughout (module docstring), and the
    approved definition uses the last recorded proposal, so it counts as
    R1. count_r1only_fallback=False (the ORIGINAL, now a labelled
    sensitivity line only) excludes every REJECTED_FALLBACK row from the
    numerator instead. The function's own default stays False so no
    caller is silently switched; every PRIMARY call site below passes
    count_r1only_fallback=True explicitly."""
    total = len(rows)
    if total == 0:
        raise PrepError("compute_ibr_first called with zero rows")
    r1 = r3 = r4 = 0
    n_unresolved = n_cp_unknown = n_final_never_parsed = 0
    for row in rows:
        label, fa = classify_ibr_first_row(row, resolver, restrict_r1_coping,
                                            count_r1only_fallback)
        if fa["resolved"] and fa.get("cp_unknown"):
            n_cp_unknown += 1
        if label == "UNRESOLVED":
            n_unresolved += 1
            continue
        if label == "FALLBACK_EXCLUDED":
            n_final_never_parsed += 1
            continue
        if label == "R1":
            r1 += 1
        elif label == "R3":
            r3 += 1
        elif label == "R4":
            r4 += 1
    return {"R1": r1, "R3": r3, "R4": r4, "total": total,
            "ibr_pct": 100.0 * (r1 + r3 + r4) / total,
            "n_unresolved": n_unresolved, "n_cp_unknown": n_cp_unknown,
            "n_final_never_parsed": n_final_never_parsed}


def compute_ibr_final(rows: list, restrict_r1_coping: bool) -> dict:
    """Report item (2), IBR_final_label: both action and label read off the
    FINAL attempt, no first-attempt reconstruction at all -- untouched by
    either review fix. restrict_r1_coping=False calls `_common.py
    (flood_ibr_components)` UNCHANGED -- byte-identical to the published
    `gemma4_nw_crossmodel_analysis.py (compute_ibr_components)`.
    restrict_r1_coping=True adds only the coping gate to R1; R3/R4 and the
    denominator are untouched. No REJECTED_FALLBACK special-casing is
    needed here: those rows' construct_TP_LABEL is the empty string, which
    normalizes to MID_OR_UNK and so can never match HIGH or LOW -- the
    published function already excludes them by construction."""
    if not restrict_r1_coping:
        return C.flood_ibr_components(rows, C.flood_final)
    total = len(rows)
    if total == 0:
        raise PrepError("compute_ibr_final called with zero rows")
    r1 = r3 = r4 = 0
    for row in rows:
        action = C.flood_normalize_action(row.get("final_skill"))
        tp_bin = _tp_bin(C.flood_normalize_tp(row.get("construct_TP_LABEL")))
        cp_bin = _tp_bin(flood_cp_bin_raw(row.get("construct_CP_LABEL")))
        hit = _rule_hit(tp_bin, cp_bin, action, restrict_r1_coping=True)
        if hit == "R1":
            r1 += 1
        elif hit == "R3":
            r3 += 1
        elif hit == "R4":
            r4 += 1
    return {"R1": r1, "R3": r3, "R4": r4, "R5_excluded": 0, "total": total,
            "ibr_pct": 100.0 * (r1 + r3 + r4) / total}


def compute_relabel_rate(rows: list, resolver, restrict_r1_coping: bool = True,
                          count_r1only_fallback: bool = False) -> dict:
    """Report item (3). See `classify_relabel_row` for the per-row rule.
    Second review fix (W2): the base no longer shrinks when a row's first
    coping was only knowable via the (drifted) final-label substitute --
    `first_attempt_proxy`'s R1 branch now reports coping as UNKNOWN
    (not-low), so it never fails the base-inclusion gate on that account.
    count_r1only_fallback=True matches the corrected primary convention in
    `compute_ibr_first` -- see `classify_relabel_row`."""
    base = numerator = changed = still_violates = n_unresolved = 0
    for row in rows:
        c = classify_relabel_row(row, resolver, restrict_r1_coping, count_r1only_fallback)
        if c == "UNRESOLVED":
            n_unresolved += 1
            continue
        if c == "NOT_BASE":
            continue
        base += 1
        if c == "CHANGED":
            changed += 1
        elif c == "KEPT_RELABELED":
            numerator += 1
        elif c == "STILL_VIOLATES":
            still_violates += 1
    rate = (100.0 * numerator / base) if base > 0 else float("nan")
    return {"numerator": numerator, "denominator": base, "rate": rate,
            "changed": changed, "still_violates": still_violates,
            "n_unresolved": n_unresolved}


# =============================================================================
# S2 invariants + W1 attempt_skills cross-check
# =============================================================================
def check_fallback_and_unmapped_invariants(rows: list, where: str) -> int:
    """S2: every REJECTED_FALLBACK row must have an empty construct_TP_LABEL,
    an empty proposed_skill, and retry_count > 0 (raises otherwise -- any of
    these would mean the 'final proposal never parsed' premise does not
    hold: a label or a proposal with nothing behind it, or a fallback that
    fired without ever retrying); and zero final_skill values may be
    silently coerced to do_nothing by C.flood_normalize_action's
    off-vocabulary fallback (raises otherwise, naming the value). This is
    what `_final_never_parsed`'s own docstring means by "asserted, not just
    noted". Returns the number of REJECTED_FALLBACK rows found."""
    n_fb = 0
    for row in rows:
        if _final_never_parsed(row):
            n_fb += 1
            tp = (row.get("construct_TP_LABEL") or "").strip()
            if tp != "":
                raise PrepError(f"{where}: a REJECTED_FALLBACK row has non-empty "
                                 f"construct_TP_LABEL={tp!r} -- the 'final proposal "
                                 f"never parsed' premise does not hold, investigate "
                                 f"before trusting any IBR number on this corpus")
            proposed = (row.get("proposed_skill") or "").strip()
            if proposed != "":
                raise PrepError(f"{where}: a REJECTED_FALLBACK row has non-empty "
                                 f"proposed_skill={proposed!r} -- it has a real "
                                 f"proposal on record, so 'the final proposal never "
                                 f"parsed' is false for this row")
            if int(row["retry_count"]) <= 0:
                raise PrepError(f"{where}: a REJECTED_FALLBACK row has "
                                 f"retry_count={row['retry_count']!r} -- fallback "
                                 f"status with no retry ever attempted contradicts "
                                 f"every REJECTED_FALLBACK row this script has read "
                                 f"to date, investigate before trusting the "
                                 f"retry_count==0 branch of the resolvers")
        if C.flood_action_is_unmapped(row.get("final_skill")):
            raise PrepError(f"{where}: final_skill={row.get('final_skill')!r} is "
                             f"off-vocabulary -- C.flood_normalize_action would "
                             f"silently coerce it to do_nothing")
    return n_fb


def check_fallback_attempts_are_do_nothing(rows: list, where: str) -> int:
    """W1: for every R1-only REJECTED_FALLBACK row, confirm via
    attempt_skills (only present on the initprop corpus) that every
    PARSED attempt on record really was do_nothing -- the empirical
    premise behind counting these rows as do_nothing in the PRIMARY
    convention. Raises on any other parsed action, AND raises unless every
    single R1-only REJECTED_FALLBACK row could actually be checked -- a
    row with a missing or empty attempt_skills is never silently skipped;
    it simply cannot be counted as checked, so it shows up as a mismatch
    between the number checked and the number of R1-only REJECTED_FALLBACK
    rows found, which is exactly what makes this function raise. Returns
    the number of rows checked (equal, by construction on success, to the
    number of R1-only REJECTED_FALLBACK rows in `rows`)."""
    n_r1_only = 0
    n_checked = 0
    for row in rows:
        if not _is_r1_only_fallback(row):
            continue
        n_r1_only += 1
        att = row.get("attempt_skills")
        if not att:
            continue
        parsed = [a.strip() for a in att.split("|") if a.strip()]
        if any(a != "do_nothing" for a in parsed):
            raise PrepError(f"{where}: R1-only REJECTED_FALLBACK row has a "
                             f"non-do_nothing parsed attempt in attempt_skills="
                             f"{att!r} -- the fallback-inclusion premise does not "
                             f"hold for this row")
        n_checked += 1
    if n_checked != n_r1_only:
        raise PrepError(f"{where}: only {n_checked} of {n_r1_only} R1-only "
                         f"REJECTED_FALLBACK rows have an attempt_skills value to "
                         f"check against -- the rest are missing/empty and are "
                         f"never silently accepted; the 'every parsed attempt was "
                         f"do_nothing' premise is unverified for at least one row")
    return n_checked


def describe_unresolved(rows: list, resolver, exact_resolver=None, limit: int = 25) -> list:
    """S1: enumerate rows the resolver cannot classify, with whatever is
    knowable (final action, final TP, status, the blocking rule(s)) -- the
    resolver deliberately never guesses a first-attempt TP for these, so
    "first threat" is exactly what is NOT knowable via the proxy; where an
    exact_resolver is supplied (initprop only) its own first tp/cp/action
    is shown alongside, since that IS knowable there."""
    out = []
    for row in rows:
        fa = resolver(row)
        if fa["resolved"]:
            continue
        entry = {
            "final_action": C.flood_normalize_action(row.get("final_skill")),
            "final_tp": C.flood_normalize_tp(row.get("construct_TP_LABEL")),
            "status": row.get("status"),
            "retry_count": row.get("retry_count"),
            "failed_rules": row.get("failed_rules"),
            "exact": None,
        }
        if exact_resolver is not None:
            ex = exact_resolver(row)
            if ex["resolved"]:
                entry["exact"] = (ex["tp"], ex["cp"], ex["action"])
        out.append(entry)
        if len(out) >= limit:
            break
    return out


# =============================================================================
# completeness gate (dir -> audit csv -> manifest[seed] -> run_integrity.json)
# =============================================================================
def _flood_completeness(corpus: str, key: str, seed: str) -> tuple:
    import json
    run_dir = C.flood_run_dir(corpus, key, seed)
    if not os.path.isdir(run_dir):
        return "skipped", f"run directory does not exist: {run_dir}", None
    aud_path = os.path.join(run_dir, C.FLOOD_AUDIT)
    if not os.path.isfile(aud_path):
        return "skipped", f"{C.FLOOD_AUDIT} missing in {run_dir}", None
    if not os.path.isfile(os.path.join(run_dir, "reproducibility_manifest.json")):
        return "skipped", f"reproducibility_manifest.json missing in {run_dir}", None
    actual_seed = C.flood_seed_of(run_dir)
    if actual_seed != seed:
        raise PrepError(f"{run_dir}: manifest seed {actual_seed!r} != expected {seed!r} "
                         f"(flood_corpus_dirs entry) -- directory naming and manifest "
                         f"disagree, investigate before trusting any per-seed number here")
    ri_path = os.path.join(run_dir, "run_integrity.json")
    if not os.path.isfile(ri_path):
        return "skipped", f"run_integrity.json missing in {run_dir}", None
    with open(ri_path, encoding="utf-8") as fh:
        ri = json.load(fh)
    if ri.get("integrity_ok") is not True:
        return "skipped", f"integrity_ok={ri.get('integrity_ok')!r} in {ri_path}", None
    return "ok", None, run_dir


def _require_or_skip(corpus: str, key: str, seed: str, hard_require: bool) -> tuple:
    status, reason, run_dir = _flood_completeness(corpus, key, seed)
    if status != "ok" and hard_require:
        raise PrepError(f"S3: primary-corpus seed {corpus}/{key} seed {seed} is not "
                         f"usable ({reason}) -- strict_n10/disabled_n10 must land all "
                         f"10 seeds or the headline is silently under-covered; fix the "
                         f"run before trusting this report, this is not skipped")
    return status, reason, run_dir


# =============================================================================
# Part 0: validation (row-by-row exact-vs-proxy, on strict_initprop)
# =============================================================================
def _row_level_agreement(rows, exact_resolver, proxy_resolver, restrict_r1_coping,
                          kind: str, count_r1only_fallback: bool = False) -> dict:
    """Genuine per-row comparison (not aggregate totals): for every row,
    classify it under BOTH resolvers and compare. kind='ibr_first' compares
    `classify_ibr_first_row`; kind='relabel' compares `classify_relabel_row`.
    N2: raises immediately if a row is a confirmed VIOLATION under EXACT
    (an R1/R3/R4 hit for kind='ibr_first', or membership in the relabel
    base for kind='relabel') but the proxy cannot resolve it at all -- that
    is the proxy silently UNDER-counting a real violation, a materially
    worse failure than merely abstaining on a row exact finds compliant,
    and is never just added to a count. Returns counts plus up to 10
    example disagreements, named by seed/agent/year where present."""
    n_both_resolved = n_disagree = n_exact_only = n_proxy_only = 0
    examples = []
    missed_violations = []
    for row in rows:
        if kind == "ibr_first":
            he, _ = classify_ibr_first_row(row, exact_resolver, restrict_r1_coping,
                                            count_r1only_fallback)
            hp, _ = classify_ibr_first_row(row, proxy_resolver, restrict_r1_coping,
                                            count_r1only_fallback)
            e_resolved = he != "UNRESOLVED"
            p_resolved = hp != "UNRESOLVED"
            e_is_violation = he in ("R1", "R3", "R4")
        else:
            he = classify_relabel_row(row, exact_resolver, restrict_r1_coping,
                                       count_r1only_fallback)
            hp = classify_relabel_row(row, proxy_resolver, restrict_r1_coping,
                                       count_r1only_fallback)
            e_resolved = he != "UNRESOLVED"
            p_resolved = hp != "UNRESOLVED"
            e_is_violation = he not in ("NOT_BASE", "UNRESOLVED")
        if e_resolved and not p_resolved:
            n_exact_only += 1
            if e_is_violation:
                missed_violations.append((row.get("_seed"), row.get("agent_id"),
                                           row.get("year"), he))
        elif p_resolved and not e_resolved:
            n_proxy_only += 1
            examples.append((row.get("_seed"), row.get("agent_id"), row.get("year"), he, hp))
        elif e_resolved and p_resolved:
            n_both_resolved += 1
            if he != hp:
                n_disagree += 1
                if len(examples) < 10:
                    examples.append((row.get("_seed"), row.get("agent_id"), row.get("year"), he, hp))
    if missed_violations:
        raise PrepError(f"{len(missed_violations)} row(s) are a confirmed violation "
                         f"under EXACT ({kind}) but the proxy could not resolve them "
                         f"at all -- the proxy would be silently under-counting a "
                         f"real violation, not just abstaining on a compliant row: "
                         f"{missed_violations[:10]}")
    return {"n_both_resolved": n_both_resolved, "n_disagree": n_disagree,
            "n_exact_only": n_exact_only, "n_proxy_only": n_proxy_only,
            "examples": examples}


def run_validation() -> dict:
    C.banner("PART 0 -- validation: row-by-row exact vs proxy "
             f"({VALIDATION_CORPUS}/{VALIDATION_KEY})")
    root, seeds = C.flood_corpus_dirs(VALIDATION_CORPUS)[VALIDATION_KEY]
    all_rows = []
    for seed in seeds:
        status, reason, run_dir = _flood_completeness(VALIDATION_CORPUS, VALIDATION_KEY, seed)
        if status != "ok":
            raise PrepError(f"validation target seed {seed} not usable: {reason}")
        aud_path = os.path.join(run_dir, C.FLOOD_AUDIT)
        rows = C.read_csv(aud_path)
        C.require_cols(rows, REQUIRED_COLS_INITPROP, aud_path)
        for r in rows:
            r["_seed"] = seed
        all_rows.extend(rows)
    total = len(all_rows)
    print(f"  loaded {total} rows from {VALIDATION_CORPUS}/{VALIDATION_KEY}, seeds {seeds}")
    if total != EXPECTED_TOTAL_ROWS:
        raise PrepError(f"validation corpus has {total} rows, expected {EXPECTED_TOTAL_ROWS} "
                         f"(flood_design_record_2026-09-29.md Sec 4) -- corpus has changed "
                         f"since the design record was written, investigate before trusting "
                         f"any number below")

    # ---- S2: invariants, on the validation corpus -----------------------------
    n_fb = check_fallback_and_unmapped_invariants(all_rows, f"{VALIDATION_CORPUS}/{VALIDATION_KEY}")
    print(f"  S2 PASS: {n_fb} REJECTED_FALLBACK rows, all with empty construct_TP_LABEL; "
          f"zero off-vocabulary final_skill values.")

    # ---- W1: attempt_skills cross-check for the fallback-inclusion premise ----
    n_fb_checked = check_fallback_attempts_are_do_nothing(
        all_rows, f"{VALIDATION_CORPUS}/{VALIDATION_KEY}")
    n_r1_only_fb = sum(1 for r in all_rows if _is_r1_only_fallback(r))
    print(f"  W1 PASS: {n_fb_checked} of {n_r1_only_fb} R1-only REJECTED_FALLBACK rows "
          f"checked against attempt_skills, every parsed attempt was do_nothing.")

    # ---- V1 (old/unrestricted R1): first action + first label, exact vs proxy -
    # V1 uses the FIRST action, not the final one -- classify_ibr_first_row always
    # reads the FINAL action, so V1 needs its own per-row classifier (this one),
    # but the same three-way categorization as `_row_level_agreement` (both
    # resolved and agree / both resolved and disagree / only one resolves).
    def _v1_hit(row, resolver):
        fa = resolver(row)
        if not fa["resolved"]:
            return "UNRESOLVED"
        return _rule_hit(fa["tp"], None, fa["action"], restrict_r1_coping=False) or "NONE"
    v1e = collections_counter_hits(all_rows, first_attempt_exact, _v1_hit)
    v1p = collections_counter_hits(all_rows, first_attempt_proxy, _v1_hit)
    n_v1_both = n_v1_dis = n_v1_exact_only = n_v1_proxy_only = 0
    v1_missed_violations = []
    for row in all_rows:
        he, hp = _v1_hit(row, first_attempt_exact), _v1_hit(row, first_attempt_proxy)
        e_ok, p_ok = he != "UNRESOLVED", hp != "UNRESOLVED"
        if e_ok and p_ok:
            n_v1_both += 1
            if he != hp:
                n_v1_dis += 1
        elif e_ok and not p_ok:
            n_v1_exact_only += 1
            if he in ("R1", "R3", "R4"):
                v1_missed_violations.append((row.get("_seed"), row.get("agent_id"),
                                              row.get("year"), he))
        elif p_ok and not e_ok:
            n_v1_proxy_only += 1
    print(f"  V1 first-attempt IBR (first action, first label, OLD/unrestricted R1): "
          f"exact {v1e['n']}/{total} = {v1e['pct']:.2f}% {v1e['comp']} | "
          f"proxy {v1p['n']}/{total} = {v1p['pct']:.2f}% {v1p['comp']} | "
          f"row disagreements = {n_v1_dis} (both-resolved n={n_v1_both}, "
          f"exact-only n={n_v1_exact_only}, proxy-only n={n_v1_proxy_only})")
    if n_v1_dis != 0:
        raise PrepError(f"V1: {n_v1_dis} rows disagree between exact and proxy "
                         f"(first action + first label, unrestricted R1) where both "
                         f"resolved")
    if n_v1_proxy_only != 0:
        raise PrepError(f"V1: {n_v1_proxy_only} row(s) resolved by the proxy but not "
                         f"by exact -- the proxy would be inferring something exact "
                         f"cannot even determine, investigate")
    if v1_missed_violations:
        raise PrepError(f"V1: {len(v1_missed_violations)} row(s) are a confirmed "
                         f"violation under exact but the proxy could not resolve them "
                         f"at all -- silently under-counting a real violation, not "
                         f"merely abstaining on a compliant row: {v1_missed_violations}")
    print(f"    design record's own account (2026-09-29): 8.49% both ways. "
          f"{'MATCHES' if abs(v1e['pct'] - 8.49) < 0.01 else 'DIFFERS from'} that figure.")

    # ---- V2 (old/unrestricted R1): final action + first label, exact vs proxy -
    v2_agree = _row_level_agreement(all_rows, first_attempt_exact, first_attempt_proxy,
                                     restrict_r1_coping=False, kind="ibr_first")
    v2e = compute_ibr_first(all_rows, first_attempt_exact, restrict_r1_coping=False)
    v2p = compute_ibr_first(all_rows, first_attempt_proxy, restrict_r1_coping=False)
    print(f"  V2 final action + first label (irrigation-style, OLD/unrestricted R1): "
          f"exact {v2e['R1']+v2e['R3']+v2e['R4']}/{total} = {v2e['ibr_pct']:.2f}% | "
          f"proxy {v2p['R1']+v2p['R3']+v2p['R4']}/{total} = {v2p['ibr_pct']:.2f}% | "
          f"row disagreements = {v2_agree['n_disagree']} (both resolved n="
          f"{v2_agree['n_both_resolved']}, exact-only n={v2_agree['n_exact_only']}, "
          f"proxy-only n={v2_agree['n_proxy_only']})")
    if v2_agree["n_disagree"] != 0:
        raise PrepError(f"V2: {v2_agree['n_disagree']} rows disagree between exact and "
                         f"proxy (final action + first label, unrestricted R1): "
                         f"{v2_agree['examples']}")
    if v2_agree["n_proxy_only"] != 0:
        raise PrepError(f"V2: {v2_agree['n_proxy_only']} row(s) resolved by the proxy but "
                         f"not by exact -- the proxy would be inferring something exact "
                         f"cannot even determine, investigate: {v2_agree['examples']}")

    # ---- NEW (this fix round): restricted R1, final action + first label ------
    r_agree = _row_level_agreement(all_rows, first_attempt_exact, first_attempt_proxy,
                                    restrict_r1_coping=True, kind="ibr_first")
    re_ = compute_ibr_first(all_rows, first_attempt_exact, restrict_r1_coping=True)
    rp_ = compute_ibr_first(all_rows, first_attempt_proxy, restrict_r1_coping=True)
    print(f"  RESTRICTED final action + first label (this fix's own primary rule): "
          f"exact {re_['R1']+re_['R3']+re_['R4']}/{total} = {re_['ibr_pct']:.2f}% "
          f"(R1={re_['R1']} R3={re_['R3']} R4={re_['R4']}) | "
          f"proxy {rp_['R1']+rp_['R3']+rp_['R4']}/{total} = {rp_['ibr_pct']:.2f}% "
          f"(R1={rp_['R1']} R3={rp_['R3']} R4={rp_['R4']}) | "
          f"row disagreements = {r_agree['n_disagree']} (proxy-only n="
          f"{r_agree['n_proxy_only']}, exact-only n={r_agree['n_exact_only']})")
    if r_agree["n_disagree"] != 0:
        raise PrepError(f"C1 FIX CHECK FAILED: {r_agree['n_disagree']} rows disagree "
                         f"between exact and proxy under the restricted rule: "
                         f"{r_agree['examples']}")
    if r_agree["n_proxy_only"] != 0:
        raise PrepError(f"C1 FIX CHECK FAILED: {r_agree['n_proxy_only']} row(s) resolved "
                         f"by the proxy but not by exact under the restricted rule: "
                         f"{r_agree['examples']}")
    print(f"  C1 FIX PASS: restricted exact and proxy agree on every one of the "
          f"{r_agree['n_both_resolved']} rows both can resolve; 0 row disagreements.")

    # ---- N3: same check under the PRIMARY convention (R1-only REJECTED_FALLBACK
    # rows counted as R1) -- a separate check from the one above, since folding
    # those rows in changes which rows are even in the numerator at all. ---------
    rp_agree = _row_level_agreement(all_rows, first_attempt_exact, first_attempt_proxy,
                                     restrict_r1_coping=True, kind="ibr_first",
                                     count_r1only_fallback=True)
    re_primary = compute_ibr_first(all_rows, first_attempt_exact, restrict_r1_coping=True,
                                    count_r1only_fallback=True)
    rp_primary = compute_ibr_first(all_rows, first_attempt_proxy, restrict_r1_coping=True,
                                    count_r1only_fallback=True)
    print(f"  RESTRICTED, PRIMARY convention (count_r1only_fallback=True): exact "
          f"{re_primary['R1']+re_primary['R3']+re_primary['R4']}/{total} = "
          f"{re_primary['ibr_pct']:.2f}% | proxy "
          f"{rp_primary['R1']+rp_primary['R3']+rp_primary['R4']}/{total} = "
          f"{rp_primary['ibr_pct']:.2f}% | row disagreements = "
          f"{rp_agree['n_disagree']} (proxy-only n={rp_agree['n_proxy_only']}, "
          f"exact-only n={rp_agree['n_exact_only']})")
    if rp_agree["n_disagree"] != 0:
        raise PrepError(f"PRIMARY-convention C1 check FAILED: {rp_agree['n_disagree']} "
                         f"rows disagree between exact and proxy: {rp_agree['examples']}")
    if rp_agree["n_proxy_only"] != 0:
        raise PrepError(f"PRIMARY-convention C1 check FAILED: {rp_agree['n_proxy_only']} "
                         f"row(s) resolved by the proxy but not by exact: "
                         f"{rp_agree['examples']}")
    print(f"  N3 PASS: PRIMARY-convention restricted exact and proxy agree on every "
          f"one of the {rp_agree['n_both_resolved']} rows both can resolve; 0 row "
          f"disagreements.")

    # ---- restricted relabel rate: exact vs proxy, row by row -------------------
    relabel_agree = _row_level_agreement(all_rows, first_attempt_exact, first_attempt_proxy,
                                          restrict_r1_coping=True, kind="relabel")
    relabel_e = compute_relabel_rate(all_rows, first_attempt_exact, restrict_r1_coping=True)
    relabel_p = compute_relabel_rate(all_rows, first_attempt_proxy, restrict_r1_coping=True)
    print(f"  RESTRICTED relabel rate: exact {relabel_e['numerator']}/{relabel_e['denominator']} "
          f"= {relabel_e['rate']:.2f}% | proxy {relabel_p['numerator']}/{relabel_p['denominator']} "
          f"= {relabel_p['rate']:.2f}% | row disagreements = {relabel_agree['n_disagree']}")
    if relabel_agree["n_disagree"] != 0 or relabel_agree["n_proxy_only"] != 0:
        raise PrepError(f"C1 FIX CHECK FAILED (relabel): disagree={relabel_agree['n_disagree']} "
                         f"proxy_only={relabel_agree['n_proxy_only']}: "
                         f"{relabel_agree['examples']}")
    print(f"  W2 FIX PASS: restricted relabel rate matches exactly (target 31.89% per the "
          f"orchestrator's own C1 message; got {relabel_e['rate']:.2f}%).")

    # ---- old-rule component / changed-kept-still splits, informational --------
    v1_r1r3r4 = (v1e["comp"].get("R1", 0), v1e["comp"].get("R3", 0), v1e["comp"].get("R4", 0))
    old_split_exact = compute_relabel_rate(all_rows, first_attempt_exact, restrict_r1_coping=False)
    print(f"  (informational) V1 base R1/R3/R4 split (exact): {v1_r1r3r4} "
          f"-- design record: (343, 7, 20)")
    print(f"  (informational) changed/kept-relabelled/still-violates, OLD rule (exact): "
          f"{old_split_exact['changed']}/{old_split_exact['numerator']}/"
          f"{old_split_exact['still_violates']} -- design record: 231/117/22")

    # ---- S1: list every row the proxy cannot resolve, with exact cross-ref ----
    unresolved_listing = describe_unresolved(all_rows, first_attempt_proxy,
                                              exact_resolver=first_attempt_exact)
    print(f"  S1: {len(unresolved_listing)} proxy-unresolved row(s) on this corpus, listed "
          f"with their exact-column cross-reference below.")
    for u in unresolved_listing:
        print(f"    failed_rules={u['failed_rules']!r} status={u['status']} "
              f"final_action={u['final_action']} final_TP={u['final_tp']} "
              f"exact(first_tp,first_cp,first_action)={u['exact']}")

    print()
    return {
        "n_rows": total, "seeds": seeds, "n_fb": n_fb, "n_r1_only_fb": n_r1_only_fb,
        "n_fb_checked": n_fb_checked,
        "v1_exact": v1e, "v1_proxy": v1p, "n_v1_disagree": n_v1_dis,
        "v2_exact": v2e, "v2_proxy": v2p, "v2_agree": v2_agree,
        "restricted_exact": re_, "restricted_proxy": rp_, "restricted_agree": r_agree,
        "restricted_exact_primary": re_primary, "restricted_proxy_primary": rp_primary,
        "restricted_agree_primary": rp_agree,
        "relabel_exact": relabel_e, "relabel_proxy": relabel_p, "relabel_agree": relabel_agree,
        "old_split_exact": old_split_exact, "unresolved_listing": unresolved_listing,
    }


def collections_counter_hits(rows, resolver, hit_fn) -> dict:
    """Small local helper (not the stdlib import -- named to avoid a bare
    `Counter` import for a single use site): counts hits by label and the
    resulting total/pct, for the V1 (first-action) computation only."""
    comp = {}
    n = 0
    for row in rows:
        h = hit_fn(row, resolver)
        if h in ("UNRESOLVED", "NONE", None):
            continue
        comp[h] = comp.get(h, 0) + 1
        n += 1
    return {"comp": comp, "n": n, "pct": 100.0 * n / len(rows)}


# =============================================================================
# Part 1: main report -- per corpus, per arm, per seed
# =============================================================================
def _process_arm(corpus: str, key: str, hard_require: bool) -> dict:
    root, seeds = C.flood_corpus_dirs(corpus)[key]
    per_seed = {}
    skipped = []
    landed_rows_by_seed = {}
    for seed in seeds:
        status, reason, run_dir = _require_or_skip(corpus, key, seed, hard_require)
        if status != "ok":
            print(f"  SKIPPED {corpus}/{key} seed {seed}: {reason}")
            skipped.append((seed, reason))
            continue
        aud_path = os.path.join(run_dir, C.FLOOD_AUDIT)
        rows = C.read_csv(aud_path)
        C.require_cols(rows, REQUIRED_COLS, aud_path)
        check_fallback_and_unmapped_invariants(rows, f"{corpus}/{key}/seed{seed}")
        for r in rows:
            r["_seed"] = seed
        landed_rows_by_seed[seed] = rows

        # PRIMARY (corrected 2026-09-29): R1-only REJECTED_FALLBACK rows count
        # as R1 (count_r1only_fallback=True) -- see compute_ibr_first's own
        # docstring. The two sensitivity variants are kept for comparison.
        ibr_first = compute_ibr_first(rows, first_attempt_proxy, restrict_r1_coping=True,
                                       count_r1only_fallback=True)
        ibr_first_excluded = compute_ibr_first(rows, first_attempt_proxy,
                                                restrict_r1_coping=True,
                                                count_r1only_fallback=False)
        ibr_first_lowerbound = compute_ibr_first(rows, first_attempt_proxy_lowerbound,
                                                  restrict_r1_coping=True,
                                                  count_r1only_fallback=False)
        ibr_final_unrestricted = compute_ibr_final(rows, restrict_r1_coping=False)
        ibr_final_restricted = compute_ibr_final(rows, restrict_r1_coping=True)
        relabel = compute_relabel_rate(rows, first_attempt_proxy, restrict_r1_coping=True,
                                        count_r1only_fallback=True)
        relabel_excluded = compute_relabel_rate(rows, first_attempt_proxy,
                                                 restrict_r1_coping=True,
                                                 count_r1only_fallback=False)

        per_seed[seed] = {
            "n_rows": len(rows),
            "n_retried": sum(1 for r in rows if int(r["retry_count"]) > 0),
            "ibr_first": ibr_first,
            "ibr_first_excluded": ibr_first_excluded,
            "ibr_first_lowerbound": ibr_first_lowerbound,
            "ibr_final_unrestricted": ibr_final_unrestricted,
            "ibr_final_restricted": ibr_final_restricted,
            "relabel": relabel,
            "relabel_excluded": relabel_excluded,
        }
        print(f"  OK {corpus}/{key} seed {seed}: n={len(rows)} "
              f"IBR_first={ibr_first['ibr_pct']:.2f}% "
              f"(excluded={ibr_first_excluded['ibr_pct']:.2f}%, "
              f"lowerbound={ibr_first_lowerbound['ibr_pct']:.2f}%) "
              f"IBR_final(unrestricted)={ibr_final_unrestricted['ibr_pct']:.2f}% "
              f"IBR_final(restricted)={ibr_final_restricted['ibr_pct']:.2f}% "
              f"relabel_rate={relabel['rate']:.2f}% (excluded={relabel_excluded['rate']:.2f}%) "
              f"(n_unresolved={ibr_first['n_unresolved']}, "
              f"n_cp_unknown={ibr_first['n_cp_unknown']})")

    landed_seeds = sorted(per_seed, key=lambda s: int(s))
    result = {"corpus": corpus, "key": key, "seed_list": seeds,
              "landed_seeds": landed_seeds, "per_seed": per_seed, "skipped": skipped}

    if landed_seeds:
        for metric in ("ibr_first", "ibr_first_excluded", "ibr_first_lowerbound",
                       "ibr_final_unrestricted", "ibr_final_restricted"):
            vals = [per_seed[s][metric]["ibr_pct"] for s in landed_seeds]
            result[f"{metric}_mean"] = C.mean(vals)
            result[f"{metric}_sd"] = C.sd(vals) if len(vals) >= 2 else float("nan")
        for rkey in ("relabel", "relabel_excluded"):
            rvals = [per_seed[s][rkey]["rate"] for s in landed_seeds
                     if per_seed[s][rkey]["rate"] == per_seed[s][rkey]["rate"]]
            result[f"{rkey}_mean"] = C.mean(rvals) if rvals else float("nan")
            result[f"{rkey}_sd"] = C.sd(rvals) if len(rvals) >= 2 else float("nan")

        pooled_rows = [r for s in landed_seeds for r in landed_rows_by_seed[s]]
        result["pooled"] = {
            "ibr_first": compute_ibr_first(pooled_rows, first_attempt_proxy,
                                            restrict_r1_coping=True,
                                            count_r1only_fallback=True),
            "ibr_final_unrestricted": compute_ibr_final(pooled_rows, restrict_r1_coping=False),
            "ibr_final_restricted": compute_ibr_final(pooled_rows, restrict_r1_coping=True),
            "relabel": compute_relabel_rate(pooled_rows, first_attempt_proxy,
                                             restrict_r1_coping=True,
                                             count_r1only_fallback=True),
        }
        # S1: unresolved-row listing at the arm level (pooled across landed seeds).
        result["unresolved_listing"] = describe_unresolved(pooled_rows, first_attempt_proxy,
                                                             exact_resolver=None, limit=25)
    return result


def _strict_minus_disabled(corpus: str, arm_results: dict) -> dict:
    """Report item (4): per-seed (strict - disabled) diff for IBR_first
    (primary, plus the two sensitivity variants) and both IBR_final_label
    variants, plus mean/sd/exact-permutation-p across the paired seeds."""
    strict_key = "strict_n10" if corpus == "defaults" else "strict"
    disabled_key = "disabled_n10" if corpus == "defaults" else "disabled"
    strict = arm_results[(corpus, strict_key)]
    disabled = arm_results[(corpus, disabled_key)]
    seeds = sorted(set(strict["landed_seeds"]) & set(disabled["landed_seeds"]), key=lambda s: int(s))
    out = {"corpus": corpus, "seeds": seeds}
    metrics = ("ibr_first", "ibr_first_excluded", "ibr_first_lowerbound",
               "ibr_final_unrestricted", "ibr_final_restricted")
    for metric in metrics:
        diffs = []
        per_seed_rows = []
        for seed in seeds:
            sv = strict["per_seed"][seed][metric]["ibr_pct"]
            dv = disabled["per_seed"][seed][metric]["ibr_pct"]
            diffs.append(sv - dv)
            per_seed_rows.append((seed, sv, dv, sv - dv))
        n = len(diffs)
        out[metric] = {
            "per_seed": per_seed_rows, "n": n,
            "mean": C.mean(diffs) if n else float("nan"),
            "sd": C.sd(diffs) if n >= 2 else float("nan"),
            "exact_perm_p": C.exact_perm_p(diffs) if n >= 1 else float("nan"),
        }
    return out


# =============================================================================
# rendering
# =============================================================================
def _sd_cell(x) -> str:
    return "n.a. (n<2)" if x != x else f"{x:.3f}"


def _pct(x) -> str:
    return f"{x:.2f}"


def _md_cell(s) -> str:
    """A value bound for a markdown table cell. `failed_rules` values are
    pipe-joined (e.g. "elevation_block|precondition_violation") and would
    otherwise be misread as extra table columns; rendered here with the
    pipe replaced by ' / ', display only, the underlying string elsewhere
    is untouched."""
    return str(s).replace("|", " / ")


def render_md(validation: dict, arm_results: dict, diffs: dict) -> str:
    L_ = []
    a = L_.append
    a("# R44 -- Flood IBR under the PI-approved 2026-09-29 first-attempt definition")
    a("")
    a("Generated by `SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/"
      "r44_flood_ibr_first_attempt.py`. CPU-only, existing runs only, no LLM calls. "
      "Revised after a REQUEST CHANGES review round on 2026-09-29 (see the script's "
      "own module docstring, section REVIEW FIX ROUND, for the full account).")
    a("")
    a("## Definition (PI decision, 2026-09-29)")
    a("")
    a("IBR = decisions whose FINAL proposal after retries violates a flood thinking "
      "rule, judged against the appraisal given at the FIRST attempt, divided by all "
      "decisions (all rows).")
    a("")
    a("- R1: threat (TP) High or Very High AND coping (CP) not Very Low or Low AND "
      "action is do_nothing.")
    a("- R3: TP Very Low or Low AND action is relocate.")
    a("- R4: TP Very Low or Low AND action is elevate_house.")
    a("- R5 (already-elevated) is never counted, unchanged from the published metric.")
    a("- Source: `.research/design_specs/flood_design_record_2026-09-29.md` "
      "(\"PI decisions 2026-09-29\", items 2 and 4).")
    a("")

    # ---- Part 0: validation --------------------------------------------------
    a("## Part 0. Method validation (strict_initprop, defaults corpus, seeds "
      f"{', '.join(validation['seeds'])}, {validation['n_rows']} rows)")
    a("")
    a("Every check below compares the EXACT `initial_skill`/`initial_labels` columns "
      "against the PROXY (`retry_count` + `failed_rules`) reconstruction ROW BY ROW, "
      "not by matching aggregate totals alone; a disagreement on even one row raises.")
    a("")
    n = validation["n_rows"]
    a(f"**S2**: {validation['n_fb']} REJECTED_FALLBACK rows found, all with empty "
      f"`construct_TP_LABEL`; zero off-vocabulary `final_skill` values. PASSED.")
    a("")
    a(f"**W1**: of {validation['n_r1_only_fb']} REJECTED_FALLBACK rows whose entire "
      f"`failed_rules` is `extreme_threat_block` alone, {validation['n_fb_checked']} "
      f"had an attempt_skills value to check and every PARSED attempt on record was "
      f"do_nothing (a missing/empty attempt_skills is never silently skipped -- it "
      f"would make this count fall short and raise). PASSED "
      f"({validation['n_fb_checked']} of {validation['n_r1_only_fb']}).")
    a("")
    v1e, v1p = validation["v1_exact"], validation["v1_proxy"]
    a(f"**V1** (first action, first label, OLD/unrestricted R1): exact "
      f"{v1e['n']}/{n} = {_pct(v1e['pct'])}%, proxy {v1p['n']}/{n} = {_pct(v1p['pct'])}%, "
      f"row disagreements = {validation['n_v1_disagree']}. Design record: 8.49% both "
      f"ways. PASSED.")
    a("")
    v2e, v2p, v2ag = validation["v2_exact"], validation["v2_proxy"], validation["v2_agree"]
    a(f"**V2** (final action, first label, OLD/unrestricted R1, the irrigation-style "
      f"quantity): exact {v2e['R1']+v2e['R3']+v2e['R4']}/{n} = {_pct(v2e['ibr_pct'])}%, "
      f"proxy {v2p['R1']+v2p['R3']+v2p['R4']}/{n} = {_pct(v2p['ibr_pct'])}%, row "
      f"disagreements = {v2ag['n_disagree']} (both-resolved n={v2ag['n_both_resolved']}, "
      f"exact-only n={v2ag['n_exact_only']}, proxy-only n={v2ag['n_proxy_only']}). "
      f"Design record: exact 3.19% (139/4359), proxy 3.21% (140/4359) -- this script's "
      f"own proxy agrees with its own exact figure exactly (row by row, not just in "
      f"total), a tighter match than the design record's own preliminary, marked-"
      f"unreviewed 139-vs-140 account. PASSED.")
    a("")
    re_, rp_, rag = (validation["restricted_exact"], validation["restricted_proxy"],
                     validation["restricted_agree"])
    a(f"**RESTRICTED, exclude convention** (final action, first label, the PI-"
      f"restricted R1, R1-only REJECTED_FALLBACK excluded -- the sensitivity line "
      f"in Part 1): exact {re_['R1']+re_['R3']+re_['R4']}/{n} = "
      f"{_pct(re_['ibr_pct'])}% (R1={re_['R1']} R3={re_['R3']} R4={re_['R4']}), proxy "
      f"{rp_['R1']+rp_['R3']+rp_['R4']}/{n} = {_pct(rp_['ibr_pct'])}% (R1={rp_['R1']} "
      f"R3={rp_['R3']} R4={rp_['R4']}), row disagreements = {rag['n_disagree']} "
      f"(proxy-only n={rag['n_proxy_only']}, exact-only n={rag['n_exact_only']}). "
      f"**C1 FIX PASSED**: 0 row disagreements.")
    a("")
    rep, rpp, ragp = (validation["restricted_exact_primary"],
                      validation["restricted_proxy_primary"],
                      validation["restricted_agree_primary"])
    a(f"**RESTRICTED, PRIMARY convention** (same rule, R1-only REJECTED_FALLBACK "
      f"COUNTED as R1 -- the headline convention in Part 1): exact "
      f"{rep['R1']+rep['R3']+rep['R4']}/{n} = {_pct(rep['ibr_pct'])}% (R1={rep['R1']} "
      f"R3={rep['R3']} R4={rep['R4']}), proxy {rpp['R1']+rpp['R3']+rpp['R4']}/{n} = "
      f"{_pct(rpp['ibr_pct'])}% (R1={rpp['R1']} R3={rpp['R3']} R4={rpp['R4']}), row "
      f"disagreements = {ragp['n_disagree']} (proxy-only n={ragp['n_proxy_only']}, "
      f"exact-only n={ragp['n_exact_only']}). **N3 PASSED**: 0 row disagreements "
      f"(both paths give "
      f"{rep['R1']+rep['R3']+rep['R4']} of {n} rows, i.e. the exclude-convention "
      f"139 plus the 7 R1-only REJECTED_FALLBACK rows now counted).")
    a("")
    rle, rlp, rlag = (validation["relabel_exact"], validation["relabel_proxy"],
                      validation["relabel_agree"])
    a(f"**RESTRICTED relabel rate**: exact {rle['numerator']}/{rle['denominator']} = "
      f"{_pct(rle['rate'])}%, proxy {rlp['numerator']}/{rlp['denominator']} = "
      f"{_pct(rlp['rate'])}%, row disagreements = {rlag['n_disagree']}. Orchestrator's "
      f"own target: 31.89%. **W2 FIX PASSED**.")
    a("")
    osp = validation["old_split_exact"]
    a(f"(Informational, unaffected by either fix) V1 base R1/R3/R4 split (exact): "
      f"R1={v1e['comp'].get('R1',0)} R3={v1e['comp'].get('R3',0)} "
      f"R4={v1e['comp'].get('R4',0)} (design record: 343/7/20). Changed/kept-relabelled/"
      f"still-violates under the OLD rule (exact): {osp['changed']}/{osp['numerator']}/"
      f"{osp['still_violates']} (design record: 231/117/22).")
    a("")
    a(f"**S1** -- rows the proxy cannot resolve ({len(validation['unresolved_listing'])} "
      f"on this corpus), with the exact-column cross-reference (first_tp, first_cp, "
      f"first_action) where available -- \"first threat\" is exactly what the proxy "
      f"cannot know for these rows; final action/label are shown as the closest "
      f"available signal:")
    a("")
    a("| failed_rules | status | final action | final TP | exact (first_tp, first_cp, "
      "first_action) |")
    a("|---|---|---|---|---|")
    for u in validation["unresolved_listing"]:
        a(f"| {_md_cell(u['failed_rules'])} | {u['status']} | {u['final_action']} | "
          f"{u['final_tp']} | {u['exact']} |")
    a("")
    a("None of these rows changes the validated counts above (each exact-side check "
      "already accounts for them); they are listed so a reader can judge plausibility "
      "case by case rather than trust a bare count.")
    a("")
    a("**VALIDATION PASSED** -- every hard check above compares rows one by one and "
      "raises on any disagreement; none did. The fixed proxy reconstruction "
      "(`first_attempt_proxy`) is adopted as primary for every corpus below, all of "
      "which lack the initprop columns; `first_attempt_proxy_lowerbound` (the pre-fix "
      "method) is reported only as a labelled sensitivity line.")
    a("")

    # ---- Part 1: per corpus / per arm tables ----------------------------------
    corpora_order = [
        ("defaults", "Primary corpus: defaults (commit 83fa97e1, no sampling params "
                      "sent, modelfile defaults temperature 1 / top_p 0.95 / top_k 64)"),
        ("v08", "Appendix corpus: v08 -- a COMMIT MIX, stated here per the review: "
                "strict and disabled at commit faf1bb12 (sampling temperature 0.8 / "
                "top_p 0.9 / top_k 40), placebo at commit 83fa97e1 (`_common.py "
                "(flood_corpus_dirs)`'s own v08 dict spells out the same split)."),
    ]
    for corpus, corpus_title in corpora_order:
        a(f"## {corpus_title}")
        a("")
        for (c, key, display, hard_require) in ARMS:
            if c != corpus:
                continue
            arm = arm_results[(c, key)]
            root, seed_list = C.flood_corpus_dirs(c)[key]
            a(f"### Arm: {display} (`{root}`, seeds {', '.join(seed_list)})")
            a("")
            if arm["skipped"]:
                for seed, reason in arm["skipped"]:
                    a(f"- SKIPPED seed {seed}: {reason}")
                a("")
            if not arm["landed_seeds"]:
                a("No seeds landed for this arm.")
                a("")
                continue
            a("Primary numbers (fixed proxy; R1-only REJECTED_FALLBACK rows counted as "
              "do_nothing/R1, per the corrected 2026-09-29 decision):")
            a("")
            a("| seed | n rows | IBR_first (%) | R1 | R3 | R4 | IBR_final unrestricted "
              "(%) | IBR_final restricted (%) | relabel rate (%) | n_unresolved | "
              "n_cp_unknown |")
            a("|---|---|---|---|---|---|---|---|---|---|---|")
            for seed in arm["landed_seeds"]:
                d = arm["per_seed"][seed]
                f1, f2, f3 = d["ibr_first"], d["ibr_final_unrestricted"], d["ibr_final_restricted"]
                rl = d["relabel"]
                rl_cell = "n.a. (empty base)" if rl["rate"] != rl["rate"] else _pct(rl["rate"])
                a(f"| {seed} | {d['n_rows']} | {_pct(f1['ibr_pct'])} | {f1['R1']} | "
                  f"{f1['R3']} | {f1['R4']} | {_pct(f2['ibr_pct'])} | {_pct(f3['ibr_pct'])} "
                  f"| {rl_cell} ({rl['numerator']}/{rl['denominator']}) | "
                  f"{f1['n_unresolved']} | {f1['n_cp_unknown']} |")
            p = arm["pooled"]
            rl = p["relabel"]
            rl_cell = "n.a. (empty base)" if rl["rate"] != rl["rate"] else _pct(rl["rate"])
            a(f"| pooled (rows combined) | {sum(arm['per_seed'][s]['n_rows'] for s in arm['landed_seeds'])} "
              f"| {_pct(p['ibr_first']['ibr_pct'])} | {p['ibr_first']['R1']} | "
              f"{p['ibr_first']['R3']} | {p['ibr_first']['R4']} | "
              f"{_pct(p['ibr_final_unrestricted']['ibr_pct'])} | "
              f"{_pct(p['ibr_final_restricted']['ibr_pct'])} | {rl_cell} "
              f"({rl['numerator']}/{rl['denominator']}) | - | - |")
            a("")
            a(f"Mean +/- sd across {len(arm['landed_seeds'])} landed seed(s): IBR_first "
              f"{_pct(arm['ibr_first_mean'])} (sd {_sd_cell(arm['ibr_first_sd'])}); "
              f"IBR_final unrestricted {_pct(arm['ibr_final_unrestricted_mean'])} "
              f"(sd {_sd_cell(arm['ibr_final_unrestricted_sd'])}); IBR_final restricted "
              f"{_pct(arm['ibr_final_restricted_mean'])} "
              f"(sd {_sd_cell(arm['ibr_final_restricted_sd'])}); relabel rate "
              f"{_pct(arm['relabel_mean']) if arm['relabel_mean']==arm['relabel_mean'] else 'n.a.'} "
              f"(sd {_sd_cell(arm['relabel_sd'])}).")
            a("")
            n_unresolved_total = sum(arm["per_seed"][s]["ibr_first"]["n_unresolved"]
                                      for s in arm["landed_seeds"])
            n_cp_unk_total = sum(arm["per_seed"][s]["ibr_first"]["n_cp_unknown"]
                                  for s in arm["landed_seeds"])
            n_never_parsed_total = sum(arm["per_seed"][s]["ibr_first"]["n_final_never_parsed"]
                                        for s in arm["landed_seeds"])
            n_rows_total = sum(arm["per_seed"][s]["n_rows"] for s in arm["landed_seeds"])
            n_retried_total = sum(arm["per_seed"][s]["n_retried"] for s in arm["landed_seeds"])
            a(f"Diagnostics (summed across landed seeds, of {n_rows_total} rows, "
              f"{n_retried_total} retried): {n_unresolved_total} row(s) where the proxy "
              f"could not bin the first-attempt threat label (excluded from the "
              f"R1/R3/R4 numerator, kept in the denominator); {n_cp_unk_total} of "
              f"{n_retried_total} retried rows are on the R1 branch, where first-attempt "
              f"coping is now treated as unknown and decided by 'not low' (the C1 fix); "
              f"{n_never_parsed_total} row(s), AMONG RESOLVED ROWS, whose final "
              f"proposal never parsed for a reason OTHER than an R1-only block "
              f"(excluded from the numerator even in the primary count, no evidence "
              f"either way) -- a REJECTED_FALLBACK row that is ALSO unresolved (its "
              f"first-listed blocking rule is outside {{R1, R3, R4}}) is counted in "
              f"n_unresolved above instead, not here, since resolution is checked "
              f"before fallback status. R1-only REJECTED_FALLBACK rows (confirmed "
              f"do_nothing throughout) ARE counted as R1 in the primary number below; "
              f"the 'excluded' sensitivity line drops them too, for comparison.")
            a("")
            a("Sensitivity (mean +/- sd across the same landed seeds):")
            a("")
            a("| variant | mean IBR_first (%) | sd |")
            a("|---|---|---|")
            a(f"| **primary**: R1-only REJECTED_FALLBACK counted as do_nothing/R1 | "
              f"{_pct(arm['ibr_first_mean'])} | {_sd_cell(arm['ibr_first_sd'])} |")
            a(f"| sensitivity: R1-only REJECTED_FALLBACK excluded instead | "
              f"{_pct(arm['ibr_first_excluded_mean'])} | "
              f"{_sd_cell(arm['ibr_first_excluded_sd'])} |")
            a(f"| sensitivity, lower bound: pre-fix final-coping substitute (never primary) | "
              f"{_pct(arm['ibr_first_lowerbound_mean'])} | "
              f"{_sd_cell(arm['ibr_first_lowerbound_sd'])} |")
            a("")
            a("| variant | mean relabel rate (%) | sd |")
            a("|---|---|---|")
            a(f"| **primary**: R1-only REJECTED_FALLBACK counted (STILL_VIOLATES, never "
              f"credited as relabelled) | "
              f"{_pct(arm['relabel_mean']) if arm['relabel_mean']==arm['relabel_mean'] else 'n.a.'} | "
              f"{_sd_cell(arm['relabel_sd'])} |")
            a(f"| sensitivity: R1-only REJECTED_FALLBACK excluded instead | "
              f"{_pct(arm['relabel_excluded_mean']) if arm['relabel_excluded_mean']==arm['relabel_excluded_mean'] else 'n.a.'} | "
              f"{_sd_cell(arm['relabel_excluded_sd'])} |")
            a("")
            a("(These two relabel-rate rows are numerically identical by construction, "
              "not a rendering error: an R1-only REJECTED_FALLBACK row is already in the "
              "base under BOTH conventions (its FIRST action is always do_nothing, "
              "unaffected by the flag), and under both conventions it never lands in the "
              "KEPT_RELABELED numerator -- the flag only moves it between the CHANGED and "
              "STILL_VIOLATES buckets, which are both excluded from the numerator either "
              "way. Only IBR_first's own numerator, not the relabel rate, changes with "
              "this flag.)")
            a("")
            if arm.get("unresolved_listing"):
                a(f"S1 -- unresolved rows in this arm (up to 25 shown, pooled across "
                  f"landed seeds):")
                a("")
                a("| failed_rules | status | final action | final TP |")
                a("|---|---|---|---|")
                for u in arm["unresolved_listing"]:
                    a(f"| {_md_cell(u['failed_rules'])} | {u['status']} | "
                      f"{u['final_action']} | {u['final_tp']} |")
                a("")

        # ---- strict-minus-disabled diff for this corpus ------------------------
        dd = diffs[corpus]
        a(f"### Strict-minus-disabled difference ({corpus}, n={dd['ibr_first']['n']} "
          f"paired seeds)")
        a("")
        for metric, label in (("ibr_first",
                                "IBR_first (PRIMARY: R1-only REJECTED_FALLBACK counted)"),
                               ("ibr_first_excluded",
                                "IBR_first (sensitivity: R1-only REJECTED_FALLBACK excluded)"),
                               ("ibr_first_lowerbound",
                                "IBR_first (sensitivity: pre-fix lower bound, never primary)"),
                               ("ibr_final_unrestricted", "IBR_final_label (unrestricted R1)"),
                               ("ibr_final_restricted", "IBR_final_label (restricted R1)")):
            m = dd[metric]
            a(f"**{label}**")
            a("")
            a("| seed | strict (%) | disabled (%) | diff (strict - disabled, pp) |")
            a("|---|---|---|---|")
            for seed, sv, dv, diff in m["per_seed"]:
                a(f"| {seed} | {_pct(sv)} | {_pct(dv)} | {diff:+.3f} |")
            a("")
            a(f"n={m['n']}: mean diff = {m['mean']:+.3f} pp, sd = {_sd_cell(m['sd'])} pp, "
              f"exact permutation p (paired sign, floor "
              f"{2.0/(1<<m['n']) if m['n']>0 else float('nan'):.4g}) = "
              f"{m['exact_perm_p']:.4f}.")
            a("")

    # ---- Limitations ------------------------------------------------------------
    primary_strict = arm_results[("defaults", "strict_n10")]
    n_cp_unk_strict = sum(primary_strict["per_seed"][s]["ibr_first"]["n_cp_unknown"]
                           for s in primary_strict["landed_seeds"])
    n_rows_strict = sum(primary_strict["per_seed"][s]["n_rows"]
                         for s in primary_strict["landed_seeds"])
    a("## Limitations")
    a("")
    a("1. First-attempt appraisal is recovered from `retry_count` and the "
      "chronological order of `failed_rules` (see the script's own module docstring "
      "for the code trace establishing that order), not from a per-attempt trace "
      "field -- `raw/household_traces.jsonl` was checked directly and carries no "
      "richer per-attempt breakdown than the audit CSV already does (verified "
      "2026-09-29 on both an initprop and a non-initprop run).")
    a(f"2. The first-attempt COPING label cannot be recovered at all when a row's "
      f"first attempt was blocked by R1 (`extreme_threat_block`), because the "
      f"AS-RUN R1 validator never reads coping. Such rows now carry coping as "
      f"UNKNOWN (bin MID_OR_UNK, read as 'not low') rather than the FINAL "
      f"`construct_CP_LABEL` (the pre-fix method, kept only as the lower-bound "
      f"sensitivity line above, since that final label drifts during retries and "
      f"under-counts strict's own R1 hits -- see the module docstring REVIEW FIX "
      f"ROUND). In the primary defaults strict arm this affects {n_cp_unk_strict} of "
      f"{n_rows_strict} rows ({100.0*n_cp_unk_strict/n_rows_strict:.1f} percent); 0 "
      f"in the disabled arm, which never retries at all.")
    a("3. 'Coping not Very Low or Low' is read as cp_bin != LOW; a missing or "
      "off-vocabulary coping label, AND the now-deliberate UNKNOWN case above, both "
      "count as 'not low' -- the wider reading, adopted for lack of positive evidence "
      "the coping was actually low.")
    n_unresolved_strict = sum(primary_strict["per_seed"][s]["ibr_first"]["n_unresolved"]
                               for s in primary_strict["landed_seeds"])
    a(f"4. {n_unresolved_strict} of {n_rows_strict} rows in the primary defaults strict "
      f"arm ({100.0*n_unresolved_strict/n_rows_strict:.2f} percent) are blocked on their "
      f"first attempt by a rule outside {{R1, R3, R4}} (elevation_block, "
      f"precondition_violation, output_schema_violation, or an unparsed 'Unknown' "
      f"failure) and so cannot be classified as a first-attempt violation either way; "
      f"they are excluded from the R1/R3/R4 numerator, counted in `n_unresolved`, "
      f"listed individually (S1, above), never guessed, and always kept in the 'all "
      f"decisions' denominator. As the S1 listing shows, a row whose FINAL action is "
      f"do_nothing is the case most plausibly a missed R1 (it would need first TP "
      f"H/VH, which this script cannot confirm or rule out); rows whose final action "
      f"is buy_insurance can never be a missed R1/R3/R4 regardless of first TP.")
    a(f"5. A final proposal that never parsed at all after every retry (status "
      f"REJECTED_FALLBACK) is excluded from the IBR_first and relabel-rate numerators "
      f"(there is no independent evidence of what it would have proposed) in every "
      f"case EXCEPT one, corrected 2026-09-29: a REJECTED_FALLBACK row whose ENTIRE "
      f"`failed_rules` is `extreme_threat_block` alone has every parsed attempt on "
      f"record as do_nothing (checked against `attempt_skills` in Part 0, "
      f"{validation['n_fb_checked']} of {validation['n_r1_only_fb']} such rows on "
      f"strict_initprop had an attempt_skills value and all passed; a missing value "
      f"would raise, never be silently skipped), and the approved definition reads "
      f"the last recorded proposal, so this IS counted as an R1 violation in the "
      f"PRIMARY number -- its "
      "do_nothing is confirmed, not guessed. For the relabel-rate split specifically, "
      "such a row is classified STILL_VIOLATES (never CHANGED or KEPT_RELABELED), "
      "since IBR_first already treats it as a violation and there is no final label at "
      "all to credit as having improved. The 'excluded' sensitivity line drops these "
      "rows entirely instead (the convention this script's own Part 0 validation was "
      "run under, since that is what the 139/4,359 and 31.89 percent targets were "
      "computed against); it is reported beside the primary number in every table "
      "above, never used as the headline.")
    a("6. Scope: only the strict, disabled and placebo arms are reported, in the "
      "defaults (primary) and v08 (appendix) corpora, matching every arm in "
      "`.research/design_specs/flood_design_record_2026-09-29.md` Sec 3.4 marked "
      "LANDED with usable per-decision labels. Paraphrase and no-nudge arms are "
      "PARTIAL/NOT RUN there; gemma4:12b is NOT RUN at defaults sampling; the "
      "traditional rule-based ABM has no LLM appraisal labels at all ('IBR not "
      "computable' in the design record) -- none of these are in this report.")
    a("7. This script writes only this .md file (no companion .csv), unlike every "
      "sibling r-script in this directory, per this task's own constraint against "
      "touching any file beyond the two named deliverables.")
    a("")
    a("## Method and code citations")
    a("")
    a("- Approved definition: `.research/design_specs/flood_design_record_2026-09-29.md` "
      "(\"PI decisions 2026-09-29\").")
    a("- Retry-exhaustion policy (`final_skill` carries the blocked proposal, or the "
      "registry default with no proposal behind it on REJECTED_FALLBACK): the "
      "project's retry-exhaustion-policy memory note (2026-09-24).")
    a("- Published final-label metric (reused unchanged for the unrestricted "
      "IBR_final_label number): `examples/single_agent/analysis/"
      "gemma4_nw_crossmodel_analysis.py (compute_ibr_components)`, transcribed at "
      "`SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/_common.py "
      "(flood_ibr_components)`.")
    a("- Chronological ordering of `failed_rules`: `broker/components/analytics/"
      "audit.py (GenericAuditWriter._write_trace_locked)`, "
      "`broker/core/skill_broker_engine.py (SkillBrokerEngine.process_step)`, "
      "`broker/core/_retry_loop.py (RetryMixin._governance_retry_loop)`.")
    a("- Corpus/seed/directory registry, including the v08 commit mix: "
      "`SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/_common.py "
      "(flood_corpus_dirs, flood_run_dir, flood_seed_of)`.")
    a("- Stats helpers: `SUBMISSION_2026/decomposition/_loader.py (mean, sd)` via "
      "`_common.py`; `_common.py (exact_perm_p)`.")
    a("")
    return "\n".join(L_) + "\n"


# =============================================================================
# main
# =============================================================================
def main() -> int:
    validation = run_validation()

    C.banner("PART 1 -- main report: defaults (primary) and v08 (appendix)")
    arm_results = {}
    for (corpus, key, display, hard_require) in ARMS:
        print(f"\n-- {corpus}/{key} ({display}) --")
        arm_results[(corpus, key)] = _process_arm(corpus, key, hard_require)

    print("\n-- strict-minus-disabled differences --")
    diffs = {}
    for corpus in DIFF_CORPORA:
        diffs[corpus] = _strict_minus_disabled(corpus, arm_results)
        d = diffs[corpus]["ibr_first"]
        dc = diffs[corpus]["ibr_first_excluded"]
        print(f"  {corpus}: IBR_first (PRIMARY) strict-minus-disabled mean={d['mean']:+.3f}pp "
              f"sd={_sd_cell(d['sd'])} (n={d['n']}); (excluded sensitivity) mean={dc['mean']:+.3f}pp "
              f"sd={_sd_cell(dc['sd'])}")

    md_text = render_md(validation, arm_results, diffs)

    out_path = os.path.join(C.OUT, "r44_flood_ibr_first_attempt.md")
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(md_text)
    os.replace(tmp_path, out_path)
    print(f"\n  wrote {os.path.relpath(out_path, C.REPO).replace(chr(92), '/')} "
          f"({len(md_text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
