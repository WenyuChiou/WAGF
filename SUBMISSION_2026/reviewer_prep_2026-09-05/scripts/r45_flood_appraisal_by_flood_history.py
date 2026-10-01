"""R45 -- flood first-stated threat appraisal by the household's own flood history.
CPU-only, existing runs only, no LLM calls made by this script. Report-only /
descriptive: pre-registered spec item 33f (2026-10-01), the flood analogue of the
irrigation R5 table -- "does a household's FIRST-STATED threat appraisal fade with
time since its last flood?"

TEMPLATE
  SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r44_flood_ibr_first_attempt.py.
  This script imports that module directly (`import r44_flood_ibr_first_attempt as
  R44`) and CALLS `R44.first_attempt_proxy(row)` directly inside
  `classify_first_tp` for every row, rather than re-deriving its
  first-attempt-appraisal branch logic -- so "the TP label at the first attempt,
  as r44 reads it" is literally r44's own function executing, not a restated copy
  that could silently drift from it (B1 fix, 2026-10 review round: an earlier
  version of this script re-derived the same retry_count/failed_rules/R1_ID/
  R3_ID/R4_ID branching here instead of calling r44's function; that restatement
  is now gone). The one thing this script still computes independently is the
  EXACT 5-level VL..VH label on the retry_count == 0 branch, since r44's own
  resolver only ever returns a HIGH/LOW/unresolved bin there too -- and even for
  that one independent computation, `classify_first_tp` ASSERTS its own bin
  agrees with r44's bin for the identical row, so the two can never silently
  disagree (see FIRST-STATED THREAT APPRAISAL below). Corpus selection, arm
  naming, and the completeness gate are all reused from `R44.ARMS` /
  `R44._require_or_skip` unchanged; this script only adds the flood-history
  reconstruction, the memory-visibility check, and the appraisal-by-history
  tables.

QUESTION
  Per arm (as in r44): mean first-stated threat appraisal (ordinal VL=1..VH=5) and
  the full label distribution, broken out (a) by years since the household's own
  last experienced flood (this year / 1 / 2 / 3 / 4+ / never flooded), and (b) by
  the number of floods the household has experienced so far (0 / 1 / 2 / 3+).

FLOOD-EXPERIENCE FIELD (found, not invented)
  `examples/single_agent/results/<run>/Run_<seed>/simulation_log.csv`, column
  `memory`. Every household's per-year outcome is written there as exactly one of
  five fixed sentences keyed to that row's own year, unconditionally appended
  every year BEFORE that year's governance decision by
  `examples/single_agent/run_flood.py (FinalParityHook.pre_year)`:
    "Got flooded with $10,000 damage on my house."                      -> flooded
    "Despite elevation, the flood was severe enough to cause damage."   -> flooded
    "A flood occurred, but my house was spared damage."                 -> not flooded
    "A flood occurred, but my house was protected by its elevation."    -> not flooded
    "No flood occurred this year."                                     -> not flooded
  EXPERIENCED A FLOOD is therefore defined as OWN-HOUSE DAMAGE that year (the first
  two templates), not merely a regional flood event with no personal loss and not
  merely "a flood happened somewhere nearby". This mirrors `agent.flood_history`,
  the simulation's own internal per-agent-per-year boolean (same file, same
  function) -- the memory column is simply where that internal fact is the only
  place it is externally recorded, so parsing it is reading a recorded field, not
  inventing a proxy.
  One subtlety, found by checking a sample household whose own governance
  decision WAS the relocate action, not assumed away: `pre_year` writes year Y's
  sentence before year Y's decision runs, but `simulation_log.csv`'s own
  `relocated` column on that same row reflects the state AFTER the decision is
  applied. So the row for the exact year a household relocates still carries a
  real "Year Y: ..." sentence even though `relocated` already reads True on that
  row (confirmed on-disk); `build_flood_map` therefore does NOT filter rows by
  `relocated` -- it scans every row and lets the sentence lookup itself decide.
  Years strictly after relocation correctly resolve to "not found" with no filter
  needed, because `pre_year` never writes a new sentence for an already-relocated
  household (confirmed: its `memory` text is frozen, byte-identical, in every
  post-relocation year). Verified live below, not assumed: every row needed to
  resolve an audit row's flood history is looked up this way; any row where the
  sentence cannot be found is a counted "coverage gap", excluded from every
  history bucket, never guessed.
  Because `FinalParityHook.pre_year` computes and records this year's own flood
  outcome BEFORE the household's decision for that same year is made (verified:
  the year-1 sample row's own context already states "Year 1: ..."), the household
  already knows its OWN current-year flood status when it states its appraisal for
  that year. "Floods experienced so far" and "years since last flood" are therefore
  both computed INCLUSIVE of the current decision year: a household flooded this
  year has years-since = 0 ("this year") and that flood counts toward its
  floods-so-far total.
  Scope note: `broker/domains/water/providers.py (FinancialCostProvider)` also
  reads `years_since_flood`, but that provider is wired only into the
  MULTI-AGENT flood domain (`examples/multi_agent/flood/`, Paper 3), not
  `examples/single_agent/run_flood.py` -- confirmed by grep, zero hits for
  `years_since_flood` or that provider in `examples/single_agent/run_flood.py`.
  `flood_count` DOES appear in `examples/single_agent/run_flood.py` (corrected,
  2026-10 review round -- an earlier version of this docstring claimed zero hits
  for both names, which was wrong for this one): it is a reflection trait set in
  `FinalParityHook.post_year` (`ctx.custom_traits["flood_count"]`), fed to the
  BATCH REFLECTION prompt, not to the household's own yearly decision prompt --
  a different field for a different purpose, still not used here. This script
  derives the household's own flood history entirely from `simulation_log.csv`'s
  `memory` column as described above.

FIRST-STATED THREAT APPRAISAL -- WHAT "AS R44 READS IT" ACTUALLY RECOVERS
  r44's own resolver (`first_attempt_proxy`) only ever returns a BIN (HIGH / LOW /
  MID_OR_UNK), never the exact VL..VH label, because for a retried row the only
  recoverable signal is WHICH RULE blocked the first attempt (R1 => TP in {H,VH};
  R3/R4 => TP in {VL,L}), which cannot distinguish H from VH or VL from L. This
  script needs the exact 5-level label (the task asks for an ordinal VL=1..VH=5
  mean and the full label distribution), so it reuses r44's method one level
  closer to the data instead of its bin:
    retry_count == 0 (first attempt IS the final attempt, no retry ever happened):
      EXACT first-stated TP = `construct_TP_LABEL`, normalized via
      `_common.py (flood_normalize_tp)` -- the same source and same case r44's own
      `first_attempt_proxy` reads for this branch, just not binned away.
    retry_count  > 0: the EXACT first-stated TP is NOT recoverable from this
      corpus (only the coarse HIGH/LOW bin is, via `failed_rules`, exactly as r44
      documents in its own module docstring, section HOW THE FIRST ATTEMPT IS
      RECOVERED). These rows are EXCLUDED from the primary (exact-label) table
      below -- counted, never guessed -- and reported separately as a labelled
      coarse-bin sensitivity line, the same primary/sensitivity pattern r44 itself
      uses throughout.
  This is a genuine data-recoverability limit, not a methodological choice: the
  governance validators that blocked a first attempt read rule membership, not the
  literal label, so the literal label was never on record for those rows. Because
  retried rows are disproportionately the HIGH-threat/do_nothing and
  LOW-threat/relocate-or-elevate cases -- precisely the extremes this analysis
  cares about -- the primary (exact-only) table is a SELECTION on the less extreme
  / non-blocked first attempts. This is stated again in Limitations, with a live
  bias-direction bound (putting the excluded rows back at their bin's low/high
  ordinal and reporting the resulting mean range), and is the reason the coarse
  sensitivity line (which keeps the retried rows, at bin resolution) is reported
  beside it on every table.

MEMORY VISIBILITY (item 1, 2026-10 review round)
  These runs use a 5-item SLIDING-WINDOW memory, found (not assumed) by reading
  `examples/single_agent/run_flood.py (run_parity_benchmark)`'s own default
  parameters (`memory_engine_type="window"`, `window_size=5`, also the
  `--window-size` CLI default) and confirming live that `FinalParityHook.post_year`
  retrieves exactly `top_k=5` memory items for the exported `memory`/`memory_pre`
  field ("Retrieve memory for logging (Parity)"). Measured directly (not inferred
  from the parameter alone): every decision record's `memory_pre` list length is
  capped at 5, and one individual seed-run from each of the six arms shows the
  SAME per-seed-run length distribution (49 records at length 3, 100 at length
  4, the remainder at the length-5 cap) -- this identity holds PER SEED-RUN, not
  pooled across an arm's several landed seeds (pooling multiplies these same
  counts by the seed count, it does not change their shape). A
  governance-independent simulation constant either way, confirming strict/
  disabled/placebo never differ on this. Traced through one sample household
  (flooded at year 4, active through year 7+): its own damage sentence is present
  in the window through year 8 (4 years later, the oldest surviving slot of a
  5-year window spanning years 4-8) and GONE by year 9 (5 years later, the window
  has rolled to years 5-9) -- a hard mechanical cutoff, not a gradual fade. The
  "4+" bucket used everywhere else in this report therefore AVERAGES together
  years_since==4 (sentence should still be at the window's edge) with
  years_since>=5 (sentence should be gone) -- the Memory visibility section
  reports the visibility share and the visible-vs-not-visible TP split needed to
  see this instead of only the averaged bucket mean. `memory_pre` is read
  directly from `raw/household_traces.jsonl` per the task brief, not from
  `simulation_log.csv`'s `memory` column, though the two were checked and found
  identical in content (`" | ".join(memory_pre)` reproduces the CSV cell exactly
  on every row checked) -- `memory_pre` is simply already a list, with no
  pipe-join ambiguity to parse back out. Trace availability: `raw/
  household_traces.jsonl` was confirmed present for every landed seed in all six
  r44 arms used by this report (a live file-existence check, not an assumption);
  if a future rerun is missing a trace for some seed, that seed's rows are
  excluded from the visibility table only (reported, never guessed), while the
  seed's rows still contribute fully to every other table in this report, which
  never reads the trace file at all.

PROTECTION CONFOUND (item 2, 2026-10 review round)
  Protection motivation theory (Grothmann and Reusswig 2006 -- the same source
  r44 cites for its own R1 rule) predicts a household that elevated, bought
  insurance, or both can RATIONALLY report a lower threat afterward (lower
  residual vulnerability), which would look identical to "fading" in the
  top-line table without any forgetting at all. Protection state (elevated /
  insured only / both / neither) is read from the trace's own `state_before`
  field -- the household's state AS RECORDED BEFORE that year's decision was
  applied -- never `state_after`. Verified live, not assumed: a sample household
  (defaults/strict_n10 arm, seed 42) has `state_before.elevated=False` at year 1,
  the SAME year its own decision elevates it; `state_after.elevated=True` that
  year matches
  `simulation_log.csv`'s own `elevated` column for that exact row -- proving
  `simulation_log.csv`'s protection columns are the POST-decision state and
  confirming the task's own instruction (do not use the state after the
  decision) rules them out. The Protection confound section reports mean TP
  split by this state, pooled (4-way) and per arm (2-way, neither vs protected,
  n-gated at 20 to avoid overstating precision on thin cells), plus each
  bucket's protection composition, so a decline that survives WITHIN the
  unprotected group (where no protection-driven reason to lower threat exists)
  can be told apart from one that is fully explained by who became protected.

CORPUS AND ARMS
  Identical to r44: `R44.ARMS` (defaults: strict_n10, disabled_n10, placebo; v08:
  strict, disabled, placebo), same completeness gate
  (`R44._require_or_skip`, extended below to also require `simulation_log.csv`),
  same hard-require semantics (defaults' two primary arms raise on an incomplete
  seed; every other arm skips and reports why). Single model throughout
  (gemma3:4b) -- r44's own ARMS scope never includes gemma4:12b or any other
  model, so there is no per-model split to report.

OUTPUT
  Writes `out/r45_flood_appraisal_by_flood_history.md` and a companion
  `out/r45_flood_appraisal_by_flood_history.csv` (aggregate bucket-level numbers
  only -- no agent_id, no per-household row, per the PII rule). All intermediate
  numbers are also printed to stdout as the script runs.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r45_flood_appraisal_by_flood_history.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r44_flood_ibr_first_attempt as R44  # noqa: E402

_tp_bin = R44._tp_bin  # reused unchanged from r44 -- HIGH={H,VH} LOW={VL,L} else MID_OR_UNK

# =============================================================================
# flood-experience templates -- verbatim from
# examples/single_agent/run_flood.py (FinalParityHook.pre_year)
# =============================================================================
FLOODED_TRUE_SUFFIXES = [
    "Got flooded with $10,000 damage on my house.",
    "Despite elevation, the flood was severe enough to cause damage.",
]
FLOODED_FALSE_SUFFIXES = [
    "A flood occurred, but my house was spared damage.",
    "A flood occurred, but my house was protected by its elevation.",
    "No flood occurred this year.",
]

REQUIRED_COLS_R45 = list(R44.REQUIRED_COLS) + ["agent_id", "year", "format_retries"]
SIMLOG_REQUIRED = ["agent_id", "year", "relocated", "memory"]

ORDINAL = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
LABELS_ORDER = ["VL", "L", "M", "H", "VH"]

YEARS_SINCE_BUCKETS = ["this year", "1", "2", "3", "4+", "never flooded"]
FLOODS_SO_FAR_BUCKETS = ["0", "1", "2", "3+"]


def bucket_years_since(years_since) -> str:
    if years_since is None:
        return "never flooded"
    if years_since == 0:
        return "this year"
    if years_since in (1, 2, 3):
        return str(years_since)
    return "4+"


def bucket_floods_so_far(n: int) -> str:
    if n in (0, 1, 2):
        return str(n)
    return "3+"


# =============================================================================
# flood-history reconstruction from simulation_log.csv's own `memory` column
# =============================================================================
def flood_status_for_row(memory_text: str, year: int):
    """Returns (status, diag). status is True/False/None (None = cannot tell).
    diag names exactly which of the four cases applied, so the markdown can
    report real counts rather than collapsing "sentence absent" and "sentence
    present but off-vocabulary" into one silent bucket."""
    text = memory_text or ""
    prefix = f"Year {year}: "
    for suf in FLOODED_TRUE_SUFFIXES:
        if prefix + suf in text:
            return True, "matched_true"
    for suf in FLOODED_FALSE_SUFFIXES:
        if prefix + suf in text:
            return False, "matched_false"
    if prefix in text:
        return None, "prefix_present_unrecognized"
    return None, "prefix_missing"


def build_flood_map(sim_rows: list, where: str) -> tuple:
    """{(agent_id, year_int): True/False/None} from EVERY simulation_log row
    (not filtered by `relocated`), plus a diagnostic Counter of
    flood_status_for_row's own diag labels.

    Checked empirically before relying on this (see a sample agent whose
    governance decision at year Y was itself the relocate action): `relocated`
    in a given row reflects the END-of-year Y state, AFTER that year's decision
    was applied, while the "Year Y: ..." flood sentence is written by
    `FinalParityHook.pre_year` BEFORE that year's decision is made. So the row
    for the very year a household relocates still carries a normal, real
    "Year Y: ..." sentence (confirmed: its own `memory` cell contains it) even
    though `relocated` already reads 'True' on that same row -- filtering on
    `relocated == 'False'` would silently manufacture a coverage gap on exactly
    the relocation-decision year, which is wrong, not conservative: the
    household DID have a household flood status that year, it is on record,
    filtering it out just because the end-of-year flag already flipped would
    throw away real data for no reason. For years AFTER relocation,
    `pre_year` never adds a new sentence at all (confirmed: the `memory` text
    is frozen, byte-identical, in every post-relocation year), so those years
    correctly resolve to None (a genuine gap) without any filter needed --
    there is nothing to find because nothing was ever written, not because
    this function excluded it.

    Raises if the SAME (agent_id, year) appears twice with disagreeing
    resolved status -- a corpus-identity problem, never silently resolved by
    "last one wins"."""
    flood_map = {}
    diag = {"matched_true": 0, "matched_false": 0,
            "prefix_present_unrecognized": 0, "prefix_missing": 0}
    for r in sim_rows:
        year = int(r["year"])
        status, d = flood_status_for_row(r.get("memory"), year)
        diag[d] += 1
        if d == "prefix_missing":
            # Live check of the documented mechanism (never just asserted in
            # prose): a missing own-year sentence should occur ONLY on a row
            # that is already past its relocation decision (relocated == True
            # and NOT the relocation-decision year itself, which still gets a
            # real sentence -- see the module docstring). If this ever fires
            # on a relocated == False row, the "coverage gap" story above is
            # wrong and every gap count in this report would be untrustworthy.
            relocated = (r.get("relocated") or "").strip()
            if relocated != "True":
                raise PrepError(f"{where}: {r['agent_id']}@{year} has no own-year "
                                 f"flood sentence but relocated={relocated!r} (not "
                                 f"'True') -- the 'missing sentences are all "
                                 f"post-relocation' premise does not hold for this "
                                 f"row, investigate before trusting any "
                                 f"flood-history number on this run")
        key = (r["agent_id"], year)
        if key in flood_map and flood_map[key] != status:
            raise PrepError(f"{where}: conflicting flood status for {key}: "
                             f"{flood_map[key]!r} vs {status!r} across duplicate "
                             f"simulation_log rows -- investigate before trusting "
                             f"any flood-history number on this run")
        flood_map[key] = status
    return flood_map, diag


def flood_history_as_of(flood_map: dict, agent_id: str, year: int) -> dict:
    """{'ok': True, 'floods_so_far': int, 'years_since': int|None} inclusive of
    `year` itself (see module docstring for why). {'ok': False} if any year in
    1..year has no resolvable flood status for this agent (a coverage gap) --
    never guessed, the caller excludes the row from every bucket."""
    seq = []
    for y in range(1, year + 1):
        v = flood_map.get((agent_id, y))
        # None covers both "no row at all for this agent/year" (key absent) and
        # "row present but the own-year sentence could not be resolved" (key
        # present, value None) -- both are coverage gaps, treated identically.
        if v is None:
            return {"ok": False}
        seq.append(v)
    floods_so_far = sum(1 for v in seq if v)
    last_flood_year = None
    if seq[-1]:
        years_since = 0
        last_flood_year = year
    else:
        years_since = None
        for i in range(len(seq) - 2, -1, -1):
            if seq[i]:
                years_since = year - (i + 1)
                last_flood_year = i + 1
                break
    if (years_since is None) != (floods_so_far == 0):
        raise PrepError(f"{agent_id}@{year}: years_since={years_since!r} and "
                         f"floods_so_far={floods_so_far!r} disagree on whether any "
                         f"flood ever occurred -- internal consistency bug, "
                         f"investigate before trusting this row")
    if (last_flood_year is None) != (floods_so_far == 0):
        raise PrepError(f"{agent_id}@{year}: last_flood_year={last_flood_year!r} and "
                         f"floods_so_far={floods_so_far!r} disagree -- internal "
                         f"consistency bug, investigate before trusting this row")
    return {"ok": True, "floods_so_far": floods_so_far, "years_since": years_since,
            "last_flood_year": last_flood_year}


# =============================================================================
# memory-visibility (review item 1, 2026-10 round): does the household's own
# last-damage sentence still appear in ITS OWN decision prompt by the time of
# a later decision, or has it fallen out of the memory window? Uses the raw
# trace's own `memory_pre` field directly, per the reviewer's instruction, not
# simulation_log.csv's `memory` column (same content -- verified identical,
# `" | ".join(memory_pre) == simulation_log.csv's memory cell` on every row
# checked -- but `memory_pre` is what was explicitly asked for and is already
# a list, no pipe-join ambiguity).
#
# MECHANISM (found, not assumed): `examples/single_agent/run_flood.py
# (run_parity_benchmark)` defaults `memory_engine_type="window"` and
# `window_size=5` (also the `--window-size` CLI default); the per-year memory
# actually exported is retrieved by `FinalParityHook.post_year`'s
# `memory_engine.retrieve_content_only(agent, top_k=5)` /
# `.retrieve(agent, top_k=5)` call ("Retrieve memory for logging (Parity)").
# Verified live by direct inspection (not just read off the default
# parameter): every record's `memory_pre` list length is capped at 5, and one
# individual seed-run (Run_<seed>, ~100 agents) from each of the six arms
# shows the SAME per-seed-run length distribution (49 rows at length 3, 100
# at length 4, the rest at the length-5 cap). This identity holds PER
# SEED-RUN, not pooled across an arm's several landed seeds -- an arm with
# 10 landed seeds shows these same counts roughly 10 times over when its
# seeds are summed, the per-seed-run shape does not change. Confirms this is
# a fixed, governance-independent simulation design choice, not something
# strict/disabled/placebo differ on. Traced through a
# sample household (flooded at year 4, still active through year 7): its own
# "Year 4: Got flooded..." sentence is present in the window through year 8
# (4 years later, the oldest surviving slot of a 5-year window spanning
# years 4..8) and is GONE by year 9 (5 years later, the window has rolled to
# years 5..9). This is a hard, mechanical cutoff, not a gradual fade -- any
# partial visibility inside the "4+" bucket below is the bucket averaging
# together years_since==4 (window edge, should read ~fully visible) with
# years_since>=5 (window has rolled past it, should read ~never visible).
# =============================================================================
def load_trace_records(run_dir: str) -> dict:
    """{(agent_id, year_int): {"memory_pre": list, "state_before": dict|None}}
    from `raw/household_traces.jsonl` in this run directory, or None if the
    file does not exist (callers must handle that -- both visibility and
    protection-state are secondary diagnostics, their absence never blocks
    the primary flood-history tables). Skips the file's own leading
    run-metadata line (`{"_metadata":..., "agent_type":...}`, no `agent_id`
    key) -- confirmed by direct inspection to be the only non-decision line.

    `state_before` (item 2, 2026-10 review round, protection confound): the
    household's OWN state as recorded BEFORE that year's decision was applied
    -- verified live by example (defaults/strict_n10 arm, seed 42:
    `state_before.elevated` False at year 1 matches the household that THEN
    elevated; `state_after` True at year 1 matches `simulation_log.csv`'s own
    `elevated` column for
    that row, confirming `simulation_log.csv`'s protection columns are the
    POST-decision state and must NOT be used for "protection at decision
    time" -- `state_before` is read instead, per the task's explicit
    instruction not to use the post-decision state)."""
    path = os.path.join(run_dir, "raw", "household_traces.jsonl")
    if not os.path.isfile(path):
        return None
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "agent_id" not in rec:
                continue
            key = (rec["agent_id"], int(rec["year"]))
            if key in out:
                raise PrepError(f"{path}: duplicate trace record for {key} -- "
                                 f"expected exactly one decision record per "
                                 f"(agent_id, year), investigate before trusting "
                                 f"any visibility or protection number from this "
                                 f"run")
            out[key] = {"memory_pre": rec.get("memory_pre") or [],
                        "state_before": rec.get("state_before")}
    return out


PROTECTION_CATEGORIES_4WAY = ["neither", "elevated", "insured only", "both"]
PROTECTION_CATEGORIES_2WAY = ["neither", "protected"]


def protection_category(state_before) -> str:
    """4-way protection state AT DECISION TIME, from the trace's own
    `state_before` dict (never `state_after`, never simulation_log.csv's
    `elevated`/`has_insurance` columns -- see `load_trace_records`). None (no
    trace, or a trace with no `state_before`) returns None -- excluded by the
    caller, never guessed."""
    if not state_before:
        return None
    elevated = bool(state_before.get("elevated"))
    insured = bool(state_before.get("has_insurance"))
    if elevated and insured:
        return "both"
    if elevated:
        return "elevated"
    if insured:
        return "insured only"
    return "neither"


def protection_category_2way(cat4) -> str:
    """Collapses the 4-way category to neither/protected, used only for the
    per-arm table (kept small enough that sparse arms still have usable N in
    most cells)."""
    if cat4 is None:
        return None
    return "neither" if cat4 == "neither" else "protected"


def damage_sentence_visible(memory_pre_list: list, flood_year: int) -> bool:
    """True iff the own-house-damage sentence for `flood_year` (one of
    FLOODED_TRUE_SUFFIXES, the same templates `flood_status_for_row` matches)
    appears anywhere in this decision's own `memory_pre` list. Reuses the
    existing TRUE-suffix list -- a visible flood is by definition one where
    flood_status_for_row already resolved True for that year, so there is
    nothing new to template here, only a different list to search."""
    text = " | ".join(memory_pre_list)
    prefix = f"Year {flood_year}: "
    return any(prefix + suf in text for suf in FLOODED_TRUE_SUFFIXES)


def count_active_no_audit(sim_rows: list, audit_keys: set, trace_map) -> int:
    """Number of (agent_id, year) pairs where the household was ACTIVE
    (relocated == 'False', i.e. a real decision should have been made) but
    BOTH `household_governance_audit.csv` AND the raw trace (`trace_map`, or
    None if the trace file itself is missing for this seed) have no record
    for that key -- an audit-trail gap neither r44 nor this script's own
    ABORTED check can ever see (both only read rows that exist; a decision
    missing from every log entirely leaves no row to classify as ABORTED or
    anything else). A key present in ONE of the two but not the other is a
    different, smaller kind of gap and is not counted here -- this function
    only counts the "vanished from everything" case the review asked about."""
    n = 0
    for r in sim_rows:
        if (r.get("relocated") or "").strip() != "False":
            continue
        key = (r["agent_id"], int(r["year"]))
        no_audit = key not in audit_keys
        no_trace = (trace_map is None) or (key not in trace_map)
        if no_audit and no_trace:
            n += 1
    return n


# =============================================================================
# first-stated TP classification (exact where r44's method allows it, coarse
# bin otherwise, both reusing r44's own rule ids / normalizer / status check)
# =============================================================================
def classify_first_tp(row: dict) -> dict:
    """Returns {'tier','label','bin'}. tier is one of:
      'aborted'  -- status == ABORTED (checked live; see Limitations for the
                    observed count on this corpus -- never assumed to be zero).
      'exact'    -- retry_count == 0: label is the exact VL..VH value (or 'UNK'
                    is treated as 'blank' instead, see below).
      'blank'    -- retry_count == 0 but construct_TP_LABEL is empty/off-
                    vocabulary.
      'bin'      -- retry_count > 0 and r44's own resolver recovered a bin:
                    only HIGH/LOW is ever recoverable this way, never the
                    exact label (see module docstring).
      'unknown'  -- r44's own resolver could not resolve this row at all
                    (its 'resolved' flag is False) -- r44's own 'UNRESOLVED'
                    case, read directly from r44, never re-derived.

    B1 fix (2026-10 review round): this function now CALLS
    `R44.first_attempt_proxy(row)` directly for the resolved/bin decision,
    instead of re-deriving it by re-reading `retry_count` + `failed_rules`
    against R1_ID/R3_ID/R4_ID (that re-derivation used to live here and could
    silently drift from r44's own branch logic if either file changed without
    the other). The only thing this function still computes independently is
    the EXACT 5-level label for the retry_count == 0 branch, because r44's
    own resolver only ever returns a bin (see module docstring) -- and even
    there, the independently-derived bin is ASSERTED equal to r44's own bin
    for that same row, so the two readings of the identical branch can never
    silently disagree.
    """
    if (row.get("status") or "").strip().upper() == "ABORTED":
        return {"tier": "aborted", "label": None, "bin": None}
    fa = R44.first_attempt_proxy(row)  # r44's own resolver, called directly
    rc = int(row["retry_count"])
    if rc == 0:
        # r44 resolves this branch itself (resolved=False only via
        # _final_never_parsed, i.e. a REJECTED_FALLBACK row with
        # retry_count == 0 -- check_fallback_and_unmapped_invariants already
        # proves that combination impossible for any row reaching here, so
        # the "not fa['resolved']" arm below is defensive, never expected to
        # fire). r45 additionally needs the EXACT label (r44's own "tp" is
        # only ever the bin), so it reads construct_TP_LABEL itself here and
        # asserts the two bins agree.
        raw = C.flood_normalize_tp(row.get("construct_TP_LABEL"))
        own_bin = _tp_bin(raw)
        if fa["resolved"]:
            if fa["tp"] != own_bin:
                raise PrepError(f"classify_first_tp: R44.first_attempt_proxy bin "
                                 f"{fa['tp']!r} disagrees with r45's own bin "
                                 f"{own_bin!r} derived from the SAME "
                                 f"construct_TP_LABEL={raw!r} at retry_count==0 -- "
                                 f"these two readings of one branch must never "
                                 f"differ, investigate before trusting any label "
                                 f"in this report")
            if raw == "UNK":
                return {"tier": "blank", "label": None, "bin": None}
            return {"tier": "exact", "label": raw, "bin": own_bin}
        return {"tier": "unknown", "label": None, "bin": None}
    # retried: r44's own resolver is the ONLY source of the bin here -- r45
    # does not re-derive it from failed_rules (that was the B1 bug), it just
    # reads r44's resolution: resolved=False <-> tier 'unknown'; resolved=True
    # <-> tier 'bin' with r44's own "HIGH"/"LOW" bin value carried through.
    if not fa["resolved"]:
        return {"tier": "unknown", "label": None, "bin": None}
    return {"tier": "bin", "label": None, "bin": fa["tp"]}


# =============================================================================
# completeness gate -- r44's own gate, extended to also require simulation_log.csv
# =============================================================================
def _require_or_skip_r45(corpus: str, key: str, seed: str, hard_require: bool) -> tuple:
    status, reason, run_dir = R44._require_or_skip(corpus, key, seed, hard_require)
    if status != "ok":
        return status, reason, run_dir
    sim_path = os.path.join(run_dir, C.FLOOD_SIM)
    if not os.path.isfile(sim_path):
        reason2 = (f"{C.FLOOD_SIM} missing in {run_dir} (needed to reconstruct "
                    f"flood history; household_governance_audit.csv alone is not "
                    f"enough for this report)")
        if hard_require:
            raise PrepError(f"S3: primary-corpus seed {corpus}/{key} seed {seed} is "
                             f"not usable ({reason2}) -- the headline must never "
                             f"silently run on fewer than its required seeds")
        return "skipped", reason2, None
    return "ok", None, run_dir


# =============================================================================
# per-arm processing
# =============================================================================
def _process_arm(corpus: str, key: str, display: str, hard_require: bool) -> dict:
    root, seeds = C.flood_corpus_dirs(corpus)[key]
    landed_seeds = []
    skipped = []
    pooled = []  # list of dicts: tier,label,bin,bucket_ys,bucket_fs,visible
    n_rows_total = 0
    n_coverage_gap = 0
    n_active_no_audit = 0
    n_seeds_no_trace = 0
    n_exact_total = [0]            # item 5 (2026-10 round 3): format-retries
    n_exact_with_format_retry = [0]  # note, among exact-label (retry_count==0) rows
    mem_diag_total = {"matched_true": 0, "matched_false": 0,
                       "prefix_present_unrecognized": 0, "prefix_missing": 0}

    for seed in seeds:
        status, reason, run_dir = _require_or_skip_r45(corpus, key, seed, hard_require)
        if status != "ok":
            print(f"  SKIPPED {corpus}/{key} seed {seed}: {reason}")
            skipped.append((seed, reason))
            continue
        landed_seeds.append(seed)
        aud_path = os.path.join(run_dir, C.FLOOD_AUDIT)
        rows = C.read_csv(aud_path)
        C.require_cols(rows, REQUIRED_COLS_R45, aud_path)
        R44.check_fallback_and_unmapped_invariants(rows, f"{corpus}/{key}/seed{seed}")

        sim_path = os.path.join(run_dir, C.FLOOD_SIM)
        sim_rows = C.read_csv(sim_path)
        C.require_cols(sim_rows, SIMLOG_REQUIRED, sim_path)
        flood_map, diag = build_flood_map(sim_rows, f"{corpus}/{key}/seed{seed}")
        for k, v in diag.items():
            mem_diag_total[k] += v

        # Item 6 (2026-10 review round): decisions that are missing from the
        # audit CSV entirely are invisible to r44's IBR calc AND to this
        # script's own ABORTED check -- neither can special-case a row that
        # was never written. Counted here so it is reported, not silently
        # absorbed into "0 ABORTED".
        #
        # Item 1 (2026-10 review round): memory-visibility of the household's
        # own last-damage sentence at decision time. Item 2 (same round,
        # protection confound): the household's own protection state AT
        # DECISION TIME (`state_before`, never `state_after` -- see
        # `load_trace_records`). Both secondary diagnostics -- their absence
        # never blocks the primary flood-history tables above. Loaded BEFORE
        # the audit-trail gap count below, which needs it too (item 6: "no
        # audit row AND no trace" is the gap being counted).
        trace_map = load_trace_records(run_dir)
        if trace_map is None:
            n_seeds_no_trace += 1

        audit_keys = {(r["agent_id"], int(r["year"])) for r in rows}
        n_active_no_audit += count_active_no_audit(sim_rows, audit_keys, trace_map)

        n_gap_seed = 0
        for row in rows:
            n_rows_total += 1
            tier_info = classify_first_tp(row)
            year = int(row["year"])
            fh = flood_history_as_of(flood_map, row["agent_id"], year)
            trace_rec = trace_map.get((row["agent_id"], year)) if trace_map is not None else None
            if not fh["ok"]:
                n_coverage_gap += 1
                n_gap_seed += 1
                bucket_ys = bucket_fs = None
                visible = None
            else:
                bucket_ys = bucket_years_since(fh["years_since"])
                bucket_fs = bucket_floods_so_far(fh["floods_so_far"])
                visible = None
                if fh["last_flood_year"] is not None and trace_rec is not None:
                    visible = damage_sentence_visible(trace_rec["memory_pre"], fh["last_flood_year"])
            protection = (protection_category(trace_rec["state_before"])
                          if trace_rec is not None else None)
            if tier_info["tier"] == "exact":
                n_exact_total[0] += 1
                if int(row.get("format_retries") or 0) > 0:
                    n_exact_with_format_retry[0] += 1
            pooled.append({"seed": seed, "tier": tier_info["tier"],
                            "label": tier_info["label"], "bin": tier_info["bin"],
                            "bucket_ys": bucket_ys, "bucket_fs": bucket_fs,
                            "visible": visible, "protection": protection,
                            "year": year})
        print(f"  OK {corpus}/{key} seed {seed}: n={len(rows)} rows, "
              f"{n_gap_seed} flood-history coverage gap(s), trace "
              f"{'present' if trace_map is not None else 'MISSING'}")

    return {"corpus": corpus, "key": key, "display": display, "root": root,
            "seed_list": seeds, "landed_seeds": landed_seeds, "skipped": skipped,
            "pooled": pooled, "n_rows_total": n_rows_total,
            "n_coverage_gap": n_coverage_gap, "mem_diag_total": mem_diag_total,
            "n_active_no_audit": n_active_no_audit,
            "n_seeds_no_trace": n_seeds_no_trace,
            "n_exact_total": n_exact_total[0],
            "n_exact_with_format_retry": n_exact_with_format_retry[0]}


# =============================================================================
# aggregation
# =============================================================================
def summarize_exact(subset: list) -> dict:
    """subset: pooled rows with tier == 'exact'. None if empty."""
    n = len(subset)
    if n == 0:
        return None
    vals = [ORDINAL[r["label"]] for r in subset]
    counts = {lab: 0 for lab in LABELS_ORDER}
    for r in subset:
        counts[r["label"]] += 1
    return {"n": n, "mean": C.mean(vals),
            "pct": {lab: 100.0 * counts[lab] / n for lab in LABELS_ORDER},
            "counts": counts}


def summarize_coarse(subset: list) -> dict:
    """subset: pooled rows with tier in ('exact','bin'). None if empty."""
    n = len(subset)
    if n == 0:
        return None
    counts = {"HIGH": 0, "LOW": 0, "MID_OR_UNK": 0}
    for r in subset:
        b = r["bin"] if r["tier"] == "bin" else _tp_bin(r["label"])
        counts[b] += 1
    return {"n": n, "pct": {k: 100.0 * v / n for k, v in counts.items()}, "counts": counts}


def build_bucket_table(pooled: list, bucket_key: str, bucket_order: list) -> list:
    """One row per bucket: exact-label summary + exclusion counts beside it
    (blank / bin-only / unknown / ABORTED), plus the coarse (exact+bin) summary
    for the sensitivity line. Rows with bucket_key is None (coverage gap) are
    never included here -- they cannot be placed in any bucket."""
    out = []
    for b in bucket_order:
        in_bucket = [r for r in pooled if r[bucket_key] == b]
        exact = [r for r in in_bucket if r["tier"] == "exact"]
        coarse_subset = [r for r in in_bucket if r["tier"] in ("exact", "bin")]
        n_blank = sum(1 for r in in_bucket if r["tier"] == "blank")
        n_bin = sum(1 for r in in_bucket if r["tier"] == "bin")
        n_unknown = sum(1 for r in in_bucket if r["tier"] == "unknown")
        n_aborted = sum(1 for r in in_bucket if r["tier"] == "aborted")
        out.append({"bucket": b, "exact": summarize_exact(exact),
                     "coarse": summarize_coarse(coarse_subset),
                     "n_blank": n_blank, "n_bin": n_bin, "n_unknown": n_unknown,
                     "n_aborted": n_aborted,
                     "n_bucket_total": len(in_bucket)})
    return out


def bin_bound_range(pooled: list, bucket_key: str, bucket_value: str):
    """Limitation 1 (2026-10 review round): bias-direction check. Combines
    exact-label ordinals with the EXCLUDED bin-only rows of this bucket,
    assigned the LOW end of their bin (HIGH->H=4, LOW->VL=1) for `mean_low`
    and the HIGH end (HIGH->VH=5, LOW->L=2) for `mean_high`. The true mean,
    if every excluded row's exact label were known, is guaranteed to fall
    inside [mean_low, mean_high] -- this is the full range of what putting
    those rows "back at their bin bounds" can possibly do to the primary
    exact-only mean, not a guess at where they'd actually land. 'unknown' /
    'blank' / 'aborted' rows are never included (no bin at all to bound
    from). Returns None if there are zero exact-or-bin rows in this bucket."""
    in_bucket = [r for r in pooled if r[bucket_key] == bucket_value]
    exact_vals = [ORDINAL[r["label"]] for r in in_bucket if r["tier"] == "exact"]
    bin_rows = [r for r in in_bucket if r["tier"] == "bin"]
    if not exact_vals and not bin_rows:
        return None
    low_vals = exact_vals + [4 if r["bin"] == "HIGH" else 1 for r in bin_rows]
    high_vals = exact_vals + [5 if r["bin"] == "HIGH" else 2 for r in bin_rows]
    return {"n_exact": len(exact_vals), "n_bin": len(bin_rows),
            "mean_low": C.mean(low_vals), "mean_high": C.mean(high_vals)}


GOVERNED_ARMS = [("defaults", "strict_n10", "strict"), ("defaults", "placebo", "placebo"),
                  ("v08", "strict", "strict"), ("v08", "placebo", "placebo")]


def bias_bound_statement(arm_results: dict) -> str:
    """Generates Limitation 1's bias-direction sentence LIVE from the actual
    corpus (never hardcoded). B2 fix (2026-10 round-3 review): a HIGH-bin row
    can only raise a bucket's exact-label mean (H=4/VH=5 sit above it) and a
    LOW-bin row can only lower it (VL=1/L=2 sit below it) -- so the net
    direction depends on the HIGH-vs-LOW split WITHIN each bucket, not a
    single corpus-wide ratio. Computed separately for 'this year' (checked
    live: a meaningfully different mix, since R3/R4 LOW-bin rows -- relocate
    or elevate under a low first-stated threat -- concentrate there) versus
    every other bucket (1 through 4+ and never flooded, checked live: these
    are overwhelmingly R1/HIGH-bin). Then, for each governed arm, compares
    the 'this year' bin-bound range against the '4+' and 'never flooded'
    bin-bound ranges and reports whether they overlap. Governed arms =
    strict and placebo in both corpora; disabled never retries, so it has no
    bin-only rows to bound at all."""
    n_high_ty = n_low_ty = n_high_other = n_low_other = 0
    for corpus, key, _display in GOVERNED_ARMS:
        arm = arm_results.get((corpus, key))
        if not arm:
            continue
        for r in arm["pooled"]:
            if r["tier"] != "bin":
                continue
            if r["bucket_ys"] == "this year":
                if r["bin"] == "HIGH":
                    n_high_ty += 1
                elif r["bin"] == "LOW":
                    n_low_ty += 1
            else:
                if r["bin"] == "HIGH":
                    n_high_other += 1
                elif r["bin"] == "LOW":
                    n_low_other += 1
    n_ty_total = n_high_ty + n_low_ty
    n_other_total = n_high_other + n_low_other
    ty_comp = (f"{n_high_ty} HIGH-bin (R1) vs {n_low_ty} LOW-bin (R3/R4) of "
               f"{n_ty_total} excluded bin-only rows" if n_ty_total else
               "no excluded bin-only rows")
    other_comp = (f"{n_high_other} of {n_other_total} "
                  f"({100.0*n_high_other/n_other_total:.1f} percent) excluded "
                  f"bin-only rows are HIGH-bin (R1), {n_low_other} are LOW-bin "
                  f"(R3/R4)" if n_other_total else "no excluded bin-only rows")
    comp = (f"A HIGH-bin row can only raise a bucket's exact-label mean and a "
            f"LOW-bin row only lower it; in buckets 1 through 4+ and never "
            f"flooded, {other_comp}, so the exact mean in those buckets is "
            f"biased DOWN relative to what the full sample would show; in "
            f"'this year', {ty_comp}, so the LOW rows there leave the net bias "
            f"direction open rather than pointing one way")
    bits = []
    for corpus, key, display in GOVERNED_ARMS:
        arm = arm_results.get((corpus, key))
        if not arm or not arm["landed_seeds"]:
            continue
        pooled = arm["pooled"]
        ty = bin_bound_range(pooled, "bucket_ys", "this year")
        far = bin_bound_range(pooled, "bucket_ys", "4+")
        never = bin_bound_range(pooled, "bucket_ys", "never flooded")
        if not ty:
            continue
        far_label_parts = []
        far_low = far_high = None
        for label, r in (("4+", far), ("never flooded", never)):
            if r:
                far_label_parts.append(f"{label} [{r['mean_low']:.2f}, "
                                        f"{r['mean_high']:.2f}] (n={r['n_exact']} "
                                        f"exact + {r['n_bin']} bin)")
                far_low = r["mean_low"] if far_low is None else min(far_low, r["mean_low"])
                far_high = r["mean_high"] if far_high is None else max(far_high, r["mean_high"])
        if not far_label_parts:
            continue
        overlap = not (ty["mean_low"] > far_high or ty["mean_high"] < far_low)
        bits.append(f"{corpus}/{display}: this year [{ty['mean_low']:.2f}, "
                    f"{ty['mean_high']:.2f}] (n={ty['n_exact']} exact + "
                    f"{ty['n_bin']} bin) vs " + " and ".join(far_label_parts) +
                    (" -- RANGES OVERLAP" if overlap else " -- ranges do not overlap"))
    if not bits:
        return (f"{comp}. No governed arm had both a populated 'this year' bucket "
                f"and a populated far-end bucket to bound, so no bias-direction "
                f"range check can be stated for this corpus.")
    return (f"{comp}. Putting the excluded bin-only rows of each bucket back at "
            f"the low and high end of their own bin (the full range consistent "
            f"with their unknown exact label -- never a guess at the true value) "
            f"gives, per governed arm: " + "; ".join(bits) + ".")


def memory_visibility_table(all_pooled: list) -> list:
    """Item 1 (2026-10 review round): for each years-since-last-flood bucket
    EXCEPT 'never flooded' (which has no last flood to look for), the share
    of decisions whose OWN `memory_pre` trace still contains the sentence for
    their own last flood year, plus the mean first-stated TP (exact-label
    rows only) split by visible vs not-visible. `all_pooled` is pooled across
    EVERY landed arm/seed that has a trace (the memory window is a
    governance-independent simulation constant -- see module docstring --
    so one pooled table is used instead of six near-identical copies)."""
    out = []
    for b in ("this year", "1", "2", "3", "4+"):
        in_bucket = [r for r in all_pooled if r["bucket_ys"] == b and r["visible"] is not None]
        n = len(in_bucket)
        n_visible = sum(1 for r in in_bucket if r["visible"])
        visible_exact = summarize_exact([r for r in in_bucket if r["visible"] and r["tier"] == "exact"])
        not_visible_exact = summarize_exact([r for r in in_bucket if not r["visible"] and r["tier"] == "exact"])
        out.append({"bucket": b, "n": n, "n_visible": n_visible,
                     "pct_visible": (100.0 * n_visible / n) if n else float("nan"),
                     "visible_exact": visible_exact, "not_visible_exact": not_visible_exact})
    return out


# Item 2 (2026-10 review round): protection confound. PMT (Grothmann and
# Reusswig 2006) predicts a protected household can rationally report LOWER
# threat (lower residual vulnerability) -- that would look identical to
# "fading" in the plain top-line table unless protection state is held
# constant. Minimum cell size below which a per-arm mean is shown as "n too
# small" rather than printed and silently over-read -- arbitrary but stated,
# a common small-sample convention, never hidden.
PROTECTION_MIN_N = 20


def protection_pooled_table(all_pooled: list, bucket_order: list, bucket_key: str = "bucket_ys") -> list:
    """Pooled across every arm/seed with a trace: one row per (bucket,
    4-way protection category). Two DIFFERENT n's, never conflated (2026-10
    round-3 fix): `n_all` is every row with a resolvable protection state in
    this (bucket, category) cell -- the denominator for `pct_of_bucket`, the
    composition number. `exact` (and its own `exact['n']`) is the SMALLER
    exact-label-only subset of those same rows actually used for the mean TP
    -- a cell can have a large `n_all` (confident composition) and a small
    `exact['n']` (unreliable mean) at the same time; the renderer flags the
    mean, not the composition, when that subset is thin."""
    out = []
    for b in bucket_order:
        in_bucket = [r for r in all_pooled if r[bucket_key] == b and r["protection"] is not None]
        n_bucket = len(in_bucket)
        for cat in PROTECTION_CATEGORIES_4WAY:
            cat_rows = [r for r in in_bucket if r["protection"] == cat]
            exact = summarize_exact([r for r in cat_rows if r["tier"] == "exact"])
            out.append({"bucket": b, "category": cat, "n_all": len(cat_rows),
                         "pct_of_bucket": (100.0 * len(cat_rows) / n_bucket) if n_bucket else float("nan"),
                         "exact": exact})
    return out


def protection_per_arm_table(arm_results: dict, bucket_order: list, bucket_key: str = "bucket_ys") -> list:
    """Per arm, 2-way protection split (neither / protected) only -- kept
    small enough that the sparser arms still have usable N in most cells. A
    cell below PROTECTION_MIN_N is reported as n-too-small rather than a
    mean, never silently hidden (the row still appears, with its real n)."""
    out = []
    for (corpus, key, display, _hard) in R44.ARMS:
        arm = arm_results.get((corpus, key))
        if not arm or not arm["landed_seeds"]:
            continue
        pooled = arm["pooled"]
        for b in bucket_order:
            in_bucket = [r for r in pooled if r[bucket_key] == b and r["protection"] is not None]
            for cat in PROTECTION_CATEGORIES_2WAY:
                cat_rows = [r for r in in_bucket
                            if protection_category_2way(r["protection"]) == cat]
                exact = summarize_exact([r for r in cat_rows if r["tier"] == "exact"])
                n = exact["n"] if exact else 0
                out.append({"corpus": corpus, "key": key, "display": display,
                             "bucket": b, "category": cat, "n": n,
                             "mean": exact["mean"] if (exact and n >= PROTECTION_MIN_N) else None,
                             "n_too_small": exact is None or n < PROTECTION_MIN_N})
    return out


# =============================================================================
# rendering
# =============================================================================
def _pct(x) -> str:
    return f"{x:.2f}"


def _mean_cell(exact) -> str:
    return "n/a (0 rows)" if exact is None else f"{exact['mean']:.2f}"


def _dist_cell(exact) -> str:
    if exact is None:
        return "-"
    return " / ".join(f"{lab} {_pct(exact['pct'][lab])}%" for lab in LABELS_ORDER)


def _n_exact_cell(exact) -> str:
    return "0" if exact is None else str(exact["n"])


def render_bucket_table(rows: list, bucket_label: str) -> list:
    L_ = []
    a = L_.append
    a(f"| {bucket_label} | n (exact) | mean TP (1=VL..5=VH) | label distribution "
      f"(exact) | excluded: blank | excluded: bin-only | excluded: unresolved | "
      f"excluded: ABORTED |")
    a("|---|---|---|---|---|---|---|---|")
    for r in rows:
        a(f"| {r['bucket']} | {_n_exact_cell(r['exact'])} | {_mean_cell(r['exact'])} "
          f"| {_dist_cell(r['exact'])} | {r['n_blank']} | {r['n_bin']} | "
          f"{r['n_unknown']} | {r['n_aborted']} |")
    return L_


def render_protection_pooled_table(rows: list, bucket_order: list, bucket_label: str) -> list:
    L_ = []
    a = L_.append
    a(f"| {bucket_label} | protection at decision time | n (all rows, for % of "
      f"bin) | % of bin (composition) | n (exact rows, used for the mean) | mean "
      f"TP (exact) |")
    a("|---|---|---|---|---|---|")
    by_key = {(r["bucket"], r["category"]): r for r in rows}
    for b in bucket_order:
        for cat in PROTECTION_CATEGORIES_4WAY:
            r = by_key[(b, cat)]
            pct_cell = "n/a (0 rows)" if r["n_all"] == 0 else f"{r['pct_of_bucket']:.1f}%"
            n_exact = 0 if r["exact"] is None else r["exact"]["n"]
            flag = " (n<20)" if 0 < n_exact < PROTECTION_MIN_N else ""
            mean_cell = _mean_cell(r["exact"]) + flag
            a(f"| {b} | {cat} | {r['n_all']} | {pct_cell} | {n_exact} | {mean_cell} |")
    return L_


def render_protection_per_arm_table(rows: list) -> list:
    L_ = []
    a = L_.append
    a(f"| arm | years since last flood | neither (n, mean TP) | protected -- "
      f"elevated/insured/both (n, mean TP) |")
    a("|---|---|---|---|")
    order = []
    cells = {}
    for r in rows:
        k = (r["corpus"], r["key"], r["display"], r["bucket"])
        if k not in cells:
            cells[k] = {}
            order.append(k)
        cells[k][r["category"]] = r

    def fmt(cell):
        if cell is None:
            return "n/a"
        if cell["n_too_small"]:
            return f"n too small (n={cell['n']})"
        return f"{cell['mean']:.2f} (n={cell['n']})"

    for corpus, key, display, bucket in order:
        c = cells[(corpus, key, display, bucket)]
        a(f"| {corpus}/{display} | {bucket} | {fmt(c.get('neither'))} | "
          f"{fmt(c.get('protected'))} |")
    return L_


def protection_reading_statement(all_pooled: list) -> str:
    """Item 2 (2026-10 review round): pooled 'neither' vs 'protected'
    (elevated/insured/both combined) mean-TP sequence across the genuine
    time-ordered buckets (this year..4+; 'never flooded' reported alongside
    but never used to judge decline direction, same convention as the main
    Plain reading paragraph), stating plainly whether a decline survives
    WITHIN each group. A verdict is only given using buckets with
    n >= PROTECTION_MIN_N on BOTH ends of the comparison -- found live (not
    assumed) that the unprotected group shrinks fast with years since the
    last flood (most households adopt SOME protection within 1-2 years), so
    naively comparing 'this year' to whatever bucket happens to have >=1 row
    left (sometimes n=1) would silently fabricate a verdict from a single
    household; this function refuses to do that and says so instead."""
    TIME_ORDER = ["this year", "1", "2", "3", "4+"]

    def seq_for(want_neither: bool):
        pts = []
        for b in TIME_ORDER + ["never flooded"]:
            rows = [r for r in all_pooled if r["bucket_ys"] == b and r["tier"] == "exact"
                    and r["protection"] is not None
                    and (r["protection"] == "neither") == want_neither]
            pts.append((b, summarize_exact(rows) if rows else None))
        return pts

    def describe(seq, label):
        """Returns (text, enough_data: bool)."""
        shown = [(b, e) for b, e in seq if e is not None]
        if not shown:
            return f"{label}: no rows with a resolvable protection state at all", False
        shown_str = " / ".join(f"{b}={e['mean']:.2f}(n={e['n']})" for b, e in shown)
        usable = [(b, e) for b, e in seq
                  if b != "never flooded" and e is not None and e["n"] >= PROTECTION_MIN_N]
        if len(usable) < 2:
            return (f"{label} ({shown_str}): FEWER THAN 2 of 'this year'..'4+' reach "
                     f"n>={PROTECTION_MIN_N} -- no decline verdict can be given for "
                     f"this group on this data, not even a negative one; the cell "
                     f"n's above are the reason, not an oversight"), False
        first_b, first_e = usable[0]
        last_b, last_e = usable[-1]
        delta = last_e["mean"] - first_e["mean"]
        verdict = ("DECLINES" if delta < -0.05 else
                   "RISES" if delta > 0.05 else "STAYS ~FLAT")
        return (f"{label} ({shown_str}): {verdict} from '{first_b}' to '{last_b}' "
                f"(delta={delta:+.2f}, both ends n>={PROTECTION_MIN_N})"), True

    neither_seq = seq_for(True)
    protected_seq = seq_for(False)
    neither_text, neither_ok = describe(neither_seq, "UNPROTECTED (neither)")
    protected_text, protected_ok = describe(protected_seq, "PROTECTED (elevated and/or insured)")

    # B3 fix (2026-10 round-3 review): live per-bucket unprotected counts,
    # replacing the earlier qualitative "within 1-2 years... almost every
    # household" sentence with the actual numbers behind it.
    def total_at(b):
        return sum(1 for r in all_pooled if r["bucket_ys"] == b and r["protection"] is not None)

    neither_by_bucket = dict(neither_seq)

    def n_at(b):
        e = neither_by_bucket.get(b)
        return e["n"] if e else 0

    b3_counts = "; ".join(f"{n_at(b)} of {total_at(b)} at {b}" for b in ("1", "2", "3", "4+"))

    if not neither_ok and protected_ok:
        scarcity_note = (" On THIS corpus the comparison that would most directly "
                          "rule out a pure-PMT explanation (a same-population "
                          "decline WITHIN the never-protected group) could not be "
                          "run, because that group is too sparse past 'this year': "
                          "one year after its own flood damage almost every "
                          "household is protected -- unprotected decisions, "
                          "computed live: " + b3_counts + ". The PROTECTED group's "
                          "own decline above is therefore consistent with either "
                          "fading or a PMT-rational lowering of threat, and this "
                          "data cannot distinguish the two.")
    elif neither_ok:
        scarcity_note = (" Both groups had enough data for a verdict; read the two "
                          "verdicts above directly against each other.")
    else:
        scarcity_note = " Neither group had enough data for a verdict on this corpus."

    # Item 7 (2026-10 round-3 review): shape within 'elevated' and 'both', the
    # 'already elevated before the flood' point, and the never-flooded/year
    # confound -- all computed live, not asserted.
    def cat_seq(cat):
        pts = []
        for b in TIME_ORDER:
            rows = [r for r in all_pooled if r["bucket_ys"] == b and r["tier"] == "exact"
                    and r["protection"] == cat]
            pts.append((b, summarize_exact(rows) if rows else None))
        return pts

    def rise_then_fall_text(seq, label):
        pts = [(b, e) for b, e in seq if e is not None]
        if len(pts) < 3:
            return f"{label}: not enough populated buckets to describe a shape"
        s = " / ".join(f"{b}={e['mean']:.2f}(n={e['n']})" for b, e in pts)
        vals = [e["mean"] for _, e in pts]
        peak_idx = max(range(len(vals)), key=lambda i: vals[i])
        if 0 < peak_idx < len(vals) - 1:
            shape = f"rises from '{pts[0][0]}' to '{pts[peak_idx][0]}' then falls to '{pts[-1][0]}'"
        elif peak_idx == 0:
            shape = "falls throughout"
        else:
            shape = f"rises throughout to '{pts[-1][0]}'"
        return f"{label} ({s}): {shape}"

    shape_note = (" Within the protected categories themselves: " +
                  rise_then_fall_text(cat_seq("elevated"), "elevated") + "; " +
                  rise_then_fall_text(cat_seq("both"), "both") +
                  ". A household counted 'elevated' at 'this year' was already "
                  "elevated BEFORE this year's flood damage occurred (elevation "
                  "is read from `state_before`, which reflects the end of the "
                  "prior year, unaffected by whether this year floods it) -- its "
                  "flood this year happened despite, not in response to, that "
                  "protection.")

    never_rows = [r for r in all_pooled if r["bucket_ys"] == "never flooded" and r["protection"] == "neither"]
    if never_rows:
        n_never_early = sum(1 for r in never_rows if r["year"] <= 3)
        never_note = (f" The 'never flooded' row by protection is confounded with "
                      f"simulation year, not a clean same-age comparison: "
                      f"{n_never_early} of {len(never_rows)} "
                      f"({100.0*n_never_early/len(never_rows):.1f} percent) "
                      f"'never flooded'-and-'neither' rows are at simulation year "
                      f"3 or earlier (computed live), so no claim is made here "
                      f"about protection itself raising or lowering TP within "
                      f"'never flooded' -- a household that has never flooded by "
                      f"year 1 or 2 has simply had less time to do anything, "
                      f"protect or otherwise.")
    else:
        never_note = (" No 'never flooded'-and-'neither' rows exist on this "
                      "corpus to check for a year confound.")

    return ("Pooled across all six arms, mean first-stated TP (exact-label rows "
            "only) by years since last flood, split by protection state AT "
            "DECISION TIME: " + neither_text + "; " + protected_text +
            ". No causal claim: protection motivation theory predicts a protected "
            "household can rationally report LOWER threat from lower residual "
            "vulnerability, which would look like 'fading' without any forgetting "
            "-- the comparison above is what would separate that from a decline "
            "that also happens inside the unprotected group, where no such "
            "mechanical reason to lower threat exists." + scarcity_note +
            shape_note + never_note)


def render_coarse_table(rows: list, bucket_label: str) -> list:
    L_ = []
    a = L_.append
    any_bin = any(r["n_bin"] > 0 for r in rows)
    if not any_bin:
        a("(No retried rows with a recognized first-blocking rule in this arm -- "
          "every resolvable row already has an exact label, so the coarse "
          "sensitivity table would be identical to the exact one above and is "
          "omitted.)")
        return L_
    a(f"Sensitivity (coarse bin, exact-label rows plus bin-only retried rows, "
      f"larger N, HIGH/LOW/MID_OR_UNK only -- never the primary number):")
    a("")
    a(f"| {bucket_label} | n (exact+bin) | % HIGH | % LOW | % MID_OR_UNK |")
    a("|---|---|---|---|---|")
    for r in rows:
        c = r["coarse"]
        if c is None:
            a(f"| {r['bucket']} | 0 | - | - | - |")
        else:
            a(f"| {r['bucket']} | {c['n']} | {_pct(c['pct']['HIGH'])} | "
              f"{_pct(c['pct']['LOW'])} | {_pct(c['pct']['MID_OR_UNK'])} |")
    return L_


def render_arm(arm: dict) -> list:
    L_ = []
    a = L_.append
    a(f"### Arm: {arm['display']} (`{arm['root']}`, seeds "
      f"{', '.join(arm['seed_list'])})")
    a("")
    if arm["skipped"]:
        for seed, reason in arm["skipped"]:
            a(f"- SKIPPED seed {seed}: {reason}")
        a("")
    if not arm["landed_seeds"]:
        a("No seeds landed for this arm.")
        a("")
        return L_

    pooled = arm["pooled"]
    n_total = arm["n_rows_total"]
    n_gap = arm["n_coverage_gap"]
    tier_counts = {"exact": 0, "blank": 0, "bin": 0, "unknown": 0, "aborted": 0}
    for r in pooled:
        tier_counts[r["tier"]] += 1
    md = arm["mem_diag_total"]
    a(f"Landed seeds: {len(arm['landed_seeds'])} of {len(arm['seed_list'])} "
      f"({', '.join(arm['landed_seeds'])}); pooled rows = {n_total}.")
    a("")
    a(f"First-stated TP resolution, pooled across landed seeds: exact label "
      f"known for {tier_counts['exact']} rows (retry_count==0); coarse bin only "
      f"for {tier_counts['bin']} retried rows; fully unresolved for "
      f"{tier_counts['unknown']} rows; blank/off-vocabulary label for "
      f"{tier_counts['blank']} rows; ABORTED status for {tier_counts['aborted']} "
      f"rows (checked live, not assumed).")
    a("")
    unrecognized_note = ("none found, as expected -- the 5 templates in Method are "
                          "treated as exhaustive" if md["prefix_present_unrecognized"] == 0
                          else "UNEXPECTED -- a 6th template exists on this corpus that "
                               "Method does not yet document, investigate before trusting "
                               "the flood-history numbers below")
    a(f"Flood-history reconstruction (own-year sentence lookup across every "
      f"`simulation_log.csv` row, pooled across landed seeds): {md['matched_true']} "
      f"rows resolved flooded, {md['matched_false']} rows resolved not-flooded, "
      f"{md['prefix_present_unrecognized']} rows had the year prefix but an "
      f"unrecognized sentence ({unrecognized_note}), and "
      f"{md['prefix_missing']} simulation_log rows had no own-year sentence at all "
      f"-- every one of these is a row strictly AFTER a household's relocation "
      f"decision (checked live, asserted in `build_flood_map`: a missing sentence "
      f"on a `relocated != True` row would raise), where `pre_year` never writes a "
      f"new sentence by design (see Method), so this count is expected and is not "
      f"itself a data-quality signal. The number that actually matters is: {n_gap} "
      f"of {n_total} audit rows ({100.0*n_gap/n_total:.2f} percent) could not be "
      f"placed in ANY flood-history bucket because at least one year in their "
      f"1..year span has no resolvable flood status (a coverage gap, excluded "
      f"from every table below, never guessed).")
    a("")
    a(f"Audit-trail gap (item 6, 2026-10 review round): {arm['n_active_no_audit']} "
      f"active agent-year(s) (household not relocated that year, a real decision "
      f"should exist) have a `simulation_log.csv` row but NO "
      f"`household_governance_audit.csv` row AND no trace record at all, pooled "
      f"across landed seeds -- the same blind spot r44 has (it only ever reads "
      f"rows that exist in the audit CSV, so it has no way to see a decision that "
      f"is missing from it entirely). These rows are invisible to every count in "
      f"this report, including the ABORTED count above: a row that was never "
      f"written can never be classified as ABORTED or anything else.")
    a("")
    if arm["n_seeds_no_trace"] > 0:
        a(f"Trace availability: {arm['n_seeds_no_trace']} of {len(arm['landed_seeds'])} "
          f"landed seed(s) in this arm have no `raw/household_traces.jsonl` file, "
          f"so this arm's rows contribute no memory-visibility data (see Memory "
          f"visibility section below) -- the primary tables above are unaffected, "
          f"since they never read the trace file.")
        a("")
    a("**By years since the household's own last experienced flood** (0 = this "
      "year; 'never flooded' = floods-so-far is 0):")
    a("")
    L_.extend(render_bucket_table(build_bucket_table(pooled, "bucket_ys", YEARS_SINCE_BUCKETS),
                                   "years since last flood"))
    a("")
    L_.extend(render_coarse_table(build_bucket_table(pooled, "bucket_ys", YEARS_SINCE_BUCKETS),
                                   "years since last flood"))
    a("")
    a("**By number of floods the household has experienced so far** (inclusive "
      "of the current decision year):")
    a("")
    L_.extend(render_bucket_table(build_bucket_table(pooled, "bucket_fs", FLOODS_SO_FAR_BUCKETS),
                                   "floods so far"))
    a("")
    L_.extend(render_coarse_table(build_bucket_table(pooled, "bucket_fs", FLOODS_SO_FAR_BUCKETS),
                                   "floods so far"))
    a("")
    return L_


def _step_word(delta: float, flat_eps: float = 0.05) -> str:
    if delta > flat_eps:
        return "up"
    if delta < -flat_eps:
        return "down"
    return "flat"


def plain_reading_paragraph(arm_results: dict) -> str:
    """One descriptive paragraph per arm, no claims beyond the numbers: the
    full 6-bucket mean sequence (this year / 1 / 2 / 3 / 4+ / never flooded),
    each reported separately (2026-10 review round: '4+' and 'never flooded'
    must not be collapsed into one tail number), plus a step-by-step shape
    description (up/down/flat between consecutive populated buckets, +-0.05
    treated as flat) computed live from the actual means -- never a
    pre-written label like 'plateau', always derived from the numbers shown
    right beside it."""
    TIME_ORDER = ["this year", "1", "2", "3", "4+"]  # a genuine elapsed-time
    # sequence; 'never flooded' is a DIFFERENT population (no flood ever,
    # not merely "more years since one") and is reported separately below,
    # never chained into the up/down/flat step sequence as if it were the
    # next point in time after '4+'.
    bits = []
    for (corpus, key, display, _hard) in R44.ARMS:
        arm = arm_results.get((corpus, key))
        if not arm or not arm["landed_seeds"]:
            continue
        rows = build_bucket_table(arm["pooled"], "bucket_ys", YEARS_SINCE_BUCKETS)
        by_bucket = {r["bucket"]: r["exact"] for r in rows}
        seq = [(b, by_bucket[b]) for b in TIME_ORDER
               if by_bucket.get(b) and by_bucket[b]["n"] > 0]
        never = by_bucket.get("never flooded")
        if len(seq) < 2 and not never:
            continue
        means_str = " / ".join(f"{b}={e['mean']:.2f}(n={e['n']})" for b, e in seq)
        if never and never["n"] > 0:
            means_str += f" / never flooded={never['mean']:.2f}(n={never['n']})"
        if len(seq) >= 2:
            steps = []
            for (b0, e0), (b1, e1) in zip(seq, seq[1:]):
                steps.append(f"{b0}->{b1} {_step_word(e1['mean'] - e0['mean'])} "
                             f"({e0['mean']:.2f}->{e1['mean']:.2f})")
            shape = ", ".join(steps)
        else:
            shape = "not enough populated this-year..4+ buckets to describe a step shape"
        bits.append(f"{corpus}/{display}: {means_str}; shape (this year through "
                    f"4+ only): {shape}")
    if not bits:
        return ("No arm had at least two populated buckets on the exact-label "
                "table, so no shape can be described for this corpus.")
    return ("Reading the exact-label ('this attempt was never retried') rows only, "
            "with no statistical test and no causal claim, mean first-stated TP "
            "(1=VL..5=VH) by years since last flood, 'this year' through '4+' and "
            "'never flooded' reported separately (never collapsed into one tail "
            "number): " + "; ".join(bits) + ". Cell sizes vary a lot across "
            "buckets and some are small (see the n's above); the coarse "
            "sensitivity tables, which also include retried rows at bin "
            "resolution, and the bin-bound check in Limitations item 1, should "
            "both be checked before treating any single cell as a stable "
            "estimate.")


def render_md(arm_results: dict) -> str:
    L_ = []
    a = L_.append
    a("# R45 -- Flood first-stated threat appraisal by household flood history")
    a("")
    a("Generated by `SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/"
      "r45_flood_appraisal_by_flood_history.py`. CPU-only, existing runs only, no "
      "LLM calls. Pre-registered report-only item (spec item 33f, decided "
      "2026-10-01): the flood analogue of the irrigation R5 table -- does a "
      "household's FIRST-STATED threat appraisal fade with time since its last "
      "flood? Descriptive only; no claims beyond the numbers shown.")
    a("")
    a("## Method")
    a("")
    a("**Flood-experience field**: `simulation_log.csv` column `memory`, parsed "
      "for the exact per-year sentence `examples/single_agent/run_flood.py "
      "(FinalParityHook.pre_year)` appends every year, BEFORE that year's "
      "governance decision runs. 'Experienced a flood' = the household's OWN "
      "house took damage that year (\"Got flooded with $10,000 damage on my "
      "house.\" / \"Despite elevation, the flood was severe enough to cause "
      "damage.\"), not merely a regional flood event with no personal loss (\"A "
      "flood occurred, but my house was spared damage.\" / \"...protected by its "
      "elevation.\") and not no flood at all (\"No flood occurred this year.\"). "
      "The lookup scans every `simulation_log.csv` row regardless of that row's "
      "own `relocated` flag: a sample household whose OWN decision that year was "
      "to relocate still has a real \"Year Y: ...\" sentence on that row (checked "
      "on-disk), because `relocated` reflects the state AFTER the decision while "
      "the sentence is written BEFORE it; years strictly after relocation "
      "correctly resolve to 'not found' because no new sentence is ever written "
      "then. Both history measures below are computed INCLUSIVE of the current "
      "decision year, because the household's own current-year outcome is already "
      "recorded before that year's decision (see the script's own module "
      "docstring for the verification). "
      "`broker/domains/water/providers.py (FinancialCostProvider)`'s "
      "`years_since_flood` field was checked and is wired only into the "
      "multi-agent flood domain, not into `examples/single_agent/run_flood.py` -- "
      "not used here. `flood_count` DOES appear in "
      "`examples/single_agent/run_flood.py`, but only as a reflection trait "
      "(`FinalParityHook.post_year`, `ctx.custom_traits[\"flood_count\"]`, fed to "
      "the batch reflection prompt, not to the household's own decision prompt) -- "
      "a different field for a different purpose, not used here either.")
    a("")
    a("**First-stated threat appraisal**: calls "
      "`r44_flood_ibr_first_attempt.py (first_attempt_proxy)` directly for every "
      "row (imported, not restated -- B1 fix, 2026-10 review round: an earlier "
      "version of this script re-derived the same retry_count/failed_rules branch "
      "logic instead of calling r44's own function, which could have silently "
      "drifted from it). r44's own resolver only ever returns a HIGH/LOW/'not "
      "resolved' bin, never the exact VL..VH label, so for the one branch where "
      "this script also needs the exact label (`retry_count == 0`, the first "
      "attempt is also the final attempt) it separately reads `construct_TP_LABEL` "
      "and ASSERTS the bin derived from that label agrees with r44's own bin for "
      "the identical row -- the two readings of one branch can never silently "
      "disagree. For a retried row, r44's resolver can only recover a HIGH/LOW bin "
      "(via which rule blocked the first attempt), never the exact label -- a real "
      "limit of what the governance validators recorded, not a choice made here, "
      "and this script does not attempt to re-derive anything finer than what r44 "
      "itself returns for that branch. The primary tables below therefore use "
      "exact-label rows only; retried rows are counted and reported as a labelled "
      "coarse-bin sensitivity line beside each table, never silently dropped and "
      "never guessed into a specific label.")
    a("")
    _n_exact_total_all = sum(arm["n_exact_total"] for arm in arm_results.values())
    _n_fmt_retry_all = sum(arm["n_exact_with_format_retry"] for arm in arm_results.values())
    _fmt_pct = (100.0 * _n_fmt_retry_all / _n_exact_total_all) if _n_exact_total_all else float("nan")
    a(f"**Format-retries note** (item 5, 2026-10 round-3 review): "
      f"`retry_count` counts GOVERNANCE retries only; `format_retries` (a "
      f"separate audit column) counts parse-level retries before the output even "
      f"reached a governance check. {_n_fmt_retry_all} of {_n_exact_total_all} "
      f"({_fmt_pct:.2f} percent) exact-label (`retry_count == 0`) rows, pooled "
      f"across all six arms, had `format_retries > 0` -- computed live, not "
      f"assumed. 'First-stated' therefore means the first attempt that PARSED "
      f"(the same sense in which r44's own `initial_labels` column, on the "
      f"strict_initprop arm, is understood to hold the first attempt), not "
      f"necessarily the model's very first raw generation if an earlier one was "
      f"malformed and silently re-prompted for format alone.")
    a("")
    a("**Corpus and arms**: identical to r44 -- `defaults` (primary, commit "
      "83fa97e1) strict_n10/disabled_n10 (seeds 42-51) and placebo (seeds 42-43); "
      "`v08` (appendix, commit mix: strict/disabled at faf1bb12, placebo at "
      "83fa97e1) at seeds 42-46/42-43. Single model (gemma3:4b) -- r44's own arm "
      "scope never includes another model, so there is no per-model split to "
      "report. Directory names and seed lists come from `_common.py "
      "(flood_corpus_dirs)`, via `r44_flood_ibr_first_attempt.py`'s own `ARMS` "
      "list, never a local literal.")
    a("")
    a("**Buckets**: years since last flood -- this year (0), 1, 2, 3, 4+, never "
      "flooded (no flood recorded in 1..current year). Floods so far -- 0, 1, 2, "
      "3+ (inclusive of the current year).")
    a("")
    a("**Memory visibility** (item 1, 2026-10 review round): these runs use a "
      "5-item sliding-window memory (`examples/single_agent/run_flood.py "
      "(run_parity_benchmark)` defaults `memory_engine_type=\"window\"`, "
      "`window_size=5`; the per-decision memory actually exported is retrieved by "
      "`FinalParityHook.post_year`'s `retrieve_content_only(agent, top_k=5)` / "
      "`retrieve(agent, top_k=5)` call), confirmed live by measuring every "
      "record's `memory_pre` list length (capped at 5; one individual seed-run "
      "from each of the six arms shows the SAME per-seed-run length distribution "
      "-- a simulation-wide constant, not a governance effect -- this identity "
      "holds PER SEED-RUN, not pooled across an arm's several landed seeds). The "
      "Memory visibility section below checks, for each years-since-last-flood "
      "bucket, what share of decisions still have their own last-damage sentence "
      "inside that window at decision time, read from `memory_pre` in "
      "`raw/household_traces.jsonl` (present for every seed in all six arms -- "
      "confirmed by direct file-existence check, not assumed). A drop in mean TP "
      "while the sentence is STILL visible in the prompt is NOT caused by the "
      "sentence leaving the window (it has not left); protection state is also "
      "changing across these same years (see Protection confound below), so that "
      "drop is not attributed to 'the model's own weighting' alone either -- only "
      "the leaving-the-window explanation is ruled out for it. A further drop "
      "AFTER the sentence has left the window is at least partly attributable to "
      "the memory design itself.")
    a("")
    a("**Exclusions counted beside every mean**: ABORTED status (checked live on "
      "this corpus; see each arm's totals below for the actual count) and blank "
      "or off-vocabulary first-stated label, plus two further categories specific "
      "to this method: bin-only (retried, exact label unrecoverable) and "
      "unresolved (retried, first-blocking rule not R1/R3/R4). A row is placed in "
      "a flood-history bucket independently of whether its TP label is known, so "
      "the exclusion counts shown per bucket reveal whether exclusion concentrates "
      "in particular history buckets rather than spreading evenly.")
    a("")
    a("**Protection confound check** (item 2, 2026-10 review round): protection "
      "state -- elevated / insured only / both / neither -- is read AT DECISION "
      "TIME from the trace's own `state_before` field (`raw/household_traces.jsonl`), "
      "never `state_after` and never `simulation_log.csv`'s `elevated`/"
      "`has_insurance` columns. Checked and confirmed live (sample household, "
      "defaults/strict_n10 arm, seed 42): `state_before.elevated` is False at "
      "year 1, the SAME year that household's decision elevates it, and "
      "`state_after.elevated` is "
      "True that same year, matching `simulation_log.csv`'s own `elevated` column "
      "for that row exactly -- proving `simulation_log.csv`'s protection columns "
      "are POST-decision, so they are never used for this split. `state_before` "
      "is present and complete (both keys present) on every decision record "
      "checked, with `state_before.relocated` never True (a relocated household "
      "never makes another decision, so it never reaches this script's rows at "
      "all).")
    a("")

    corpora_order = [
        ("defaults", "Primary corpus: defaults (commit 83fa97e1, no sampling "
                      "params sent, modelfile defaults temperature 1 / top_p "
                      "0.95 / top_k 64)"),
        ("v08", "Appendix corpus: v08 (commit mix -- strict/disabled at faf1bb12, "
                "sampling temperature 0.8 / top_p 0.9 / top_k 40; placebo at "
                "83fa97e1)"),
    ]
    for corpus, title in corpora_order:
        a(f"## {title}")
        a("")
        for (c, key, display, hard_require) in R44.ARMS:
            if c != corpus:
                continue
            L_.extend(render_arm(arm_results[(c, key)]))

    a("## Memory visibility of the last flood")
    a("")
    all_pooled = [r for arm in arm_results.values() for r in arm["pooled"]]
    n_with_trace = sum(1 for r in all_pooled if r["visible"] is not None)
    n_seeds_no_trace_total = sum(arm["n_seeds_no_trace"] for arm in arm_results.values())
    n_seeds_landed_total = sum(len(arm["landed_seeds"]) for arm in arm_results.values())
    trace_coverage_note = (
        "`raw/household_traces.jsonl` is present for every landed seed in every "
        "arm on this corpus (confirmed live: 0 of "
        f"{n_seeds_landed_total} landed seed-runs reported a missing trace file)."
        if n_seeds_no_trace_total == 0 else
        f"`raw/household_traces.jsonl` is MISSING for {n_seeds_no_trace_total} of "
        f"{n_seeds_landed_total} landed seed-runs (see each arm's own 'Trace "
        f"availability' line above for which) -- this table is pooled only over "
        f"seeds that do have a trace file.")
    a(f"Pooled across all six arms' landed seeds ({n_seeds_landed_total} "
      f"seed-runs total) -- the memory window is a governance-independent "
      f"simulation constant (see Method), so one pooled table is used instead of "
      f"six near-identical copies. {n_with_trace} of "
      f"{sum(len(arm['pooled']) for arm in arm_results.values())} rows have both "
      f"a resolvable flood history and a trace to check. {trace_coverage_note} "
      f"'never flooded' is excluded from this table -- there is no last-damage "
      f"sentence to look for.")
    a("")
    vis_rows = memory_visibility_table(all_pooled)
    a("| years since last flood | n (resolvable) | % sentence still visible | "
      "mean TP when visible (n) | mean TP when NOT visible (n) |")
    a("|---|---|---|---|---|")
    for r in vis_rows:
        pct_cell = "n/a (0 rows)" if r["n"] == 0 else f"{r['pct_visible']:.2f}"
        vis_cell = (f"{r['visible_exact']['mean']:.2f} (n={r['visible_exact']['n']})"
                    if r["visible_exact"] else "n/a (0 rows)")
        notvis_cell = (f"{r['not_visible_exact']['mean']:.2f} (n={r['not_visible_exact']['n']})"
                       if r["not_visible_exact"] else "n/a (0 rows)")
        a(f"| {r['bucket']} | {r['n']} | {pct_cell} | {vis_cell} | {notvis_cell} |")
    a("")
    a("Reading this table plainly, no causal claim: a bucket where % visible is "
      "near 100 and the TP-when-NOT-visible column is 'n/a' or thin means almost "
      "every decision in that bucket still had the sentence in its own prompt, so "
      "any mean-TP drop already seen in that bucket (Plain reading, below) happened "
      "WHILE the model could still see the flood -- that is the model's own "
      "weighting, not a memory-design artifact. A bucket where % visible has "
      "fallen well below 100 mixes two different situations (sentence still "
      "present vs already rolled out of the window); the visible-vs-not-visible "
      "split in the last two columns is what separates them. If TP stays similarly "
      "low in BOTH the visible and not-visible rows of such a bucket, the drop is "
      "not explained by visibility alone. If TP is noticeably higher in the "
      "visible rows than the not-visible rows of the same bucket, visibility (the "
      "memory window design) is doing at least part of the work.")
    a("")

    a("## Protection confound (protection motivation theory check)")
    a("")
    a("Item 2 (2026-10 review round): after a flood a household may elevate, buy "
      "insurance, or relocate; under protection motivation theory (Grothmann and "
      "Reusswig 2006) a household that is now protected can rationally report a "
      "LOWER threat (lower residual vulnerability), which would look identical to "
      "'fading' in the top-line table without any forgetting at all. Protection "
      "state is read from the trace's own `state_before` field -- the household's "
      "state AS RECORDED BEFORE that year's decision was applied -- never "
      "`state_after` and never `simulation_log.csv`'s `elevated`/`has_insurance` "
      "columns, which were checked and confirmed to hold the POST-decision state "
      "instead (see Method).")
    a("")
    a("Pooled across all six arms (4-way split, with each category's share of "
      "the bin alongside, i.e. the protection composition of each bin):")
    a("")
    all_pooled_prot = [r for arm in arm_results.values() for r in arm["pooled"]]
    L_.extend(render_protection_pooled_table(
        protection_pooled_table(all_pooled_prot, YEARS_SINCE_BUCKETS), YEARS_SINCE_BUCKETS,
        "years since last flood"))
    a("")
    a(f"Per arm (2-way split, neither vs protected -- kept small enough that the "
      f"sparser arms still have usable N; a cell below n={PROTECTION_MIN_N} is "
      f"shown as 'n too small' rather than a mean):")
    a("")
    L_.extend(render_protection_per_arm_table(
        protection_per_arm_table(arm_results, YEARS_SINCE_BUCKETS)))
    a("")
    a(protection_reading_statement(all_pooled_prot))
    a("")

    a("## Plain reading")
    a("")
    a(plain_reading_paragraph(arm_results))
    a("")

    a("## Limitations")
    a("")
    a("1. The primary (exact-label) table is a SELECTION on rows whose first "
      "attempt was never retried. Retried rows are disproportionately the "
      "HIGH-threat/do_nothing and LOW-threat/relocate-or-elevate cases -- exactly "
      "the extremes most relevant to a fading-salience question -- so the primary "
      "table under-represents exactly the rows this question cares most about on "
      "arms where governance is active (strict, placebo). The disabled arm never "
      "retries at all, so its exact-label table has no such selection. BIAS "
      "DIRECTION (B2 fix, 2026-10 round-3 review): " + bias_bound_statement(arm_results))
    a("2. 'Experienced a flood' is defined at the household level (own-house "
      "damage), not at the community level (a flood event occurring that year "
      "regardless of personal damage). A household can correctly report 'not "
      "flooded' in a year when a regional flood event occurred, if its own house "
      "was spared or protected by elevation.")
    a("3. Years since last flood and floods-so-far are both computed INCLUSIVE of "
      "the current decision year (see Method) -- a household flooded this year "
      "has years-since = 0, not 'undefined' or '1'.")
    a("4. A flood-history coverage gap (a year in 1..current year with no "
      "resolvable own-year sentence anywhere in that agent's `simulation_log.csv` "
      "rows) excludes the row from every bucket table; the per-arm counts above "
      "report how often this happened on this corpus -- it was not assumed to be "
      f"zero (live total across all six arms: "
      f"{sum(arm['n_coverage_gap'] for arm in arm_results.values())} of "
      f"{sum(arm['n_rows_total'] for arm in arm_results.values())} rows).")
    a("5. No statistical test, trend line, or causal claim is computed anywhere "
      "in this report. The 'Plain reading' paragraph above states the full "
      "6-bucket mean sequence actually observed, by arm, with each bucket's own n "
      "-- '4+' and 'never flooded' are always reported separately, never merged "
      "into one tail number.")
    a("6. Scope matches r44 exactly: only strict, disabled, and placebo, in the "
      "defaults and v08 corpora. Paraphrase/no-nudge/gemma4:12b/rule-based arms "
      "are out of scope here for the same reasons r44 excludes them (see r44's "
      "own Limitations item 6).")
    a("7. Audit-trail gap (item 6, 2026-10 review round): some active agent-years "
      "per arm have a `simulation_log.csv` row (a real decision should exist) but "
      "no `household_governance_audit.csv` row and no trace record at all, so "
      "they never reach the ABORTED count or any other count in this report -- "
      "the same gap r44 itself cannot see, since r44 also only ever reads rows "
      "that exist in the audit CSV. Per-arm counts are printed in each arm's own "
      "'Audit-trail gap' line above (computed live from this corpus, not assumed "
      "to be zero and not copied from any prior estimate).")
    a("8. Memory visibility (item 1, 2026-10 review round): a mean-TP drop that "
      "occurs WHILE the household's last-damage sentence is still inside its "
      "5-item memory window reflects the model's own weighting of that "
      "information -- the sentence was there to read and the stated appraisal "
      "still fell. A further drop AFTER the sentence has rolled out of the "
      "window cannot be attributed to the model alone in the same way: at that "
      "point the information literally is not in the prompt, so part (not "
      "necessarily all) of that later drop may be the memory design rather than "
      "the model discounting a flood it can still see. The Memory visibility "
      "section above reports the visible-vs-not-visible split needed to tell "
      "these two apart within a bucket, instead of only the window-size fact.")
    a("9. Protection confound (item 2, 2026-10 review round): the top-line tables "
      "above do not hold protection state constant, so any decline they show "
      "could be entirely a PMT-consistent, rational lowering of threat by "
      "households that elevated, insured, or both -- not fading memory at all. "
      "The Protection confound section reports the decline SEPARATELY within the "
      "unprotected ('neither') group and the protected group; only a decline that "
      "also appears within 'neither' (where no protection-driven reason to lower "
      "threat exists) is evidence against a pure-PMT explanation. Cells below "
      "n=20 are shown as 'n too small' rather than a mean. The PER-ARM table is "
      "the 2-way split (neither vs protected) only -- its sparse cells are "
      "overwhelmingly 'neither': always thin in buckets '1' through '4+' (n<=4 "
      "per arm on every arm checked), and also thin at 'this year' specifically "
      "on the two 2-seed placebo arms (n=13, n=15); 'protected' is not thin in "
      "any arm or bucket checked (always in the hundreds or more). The POOLED "
      "table is the 4-way split; there, 'neither' past 'this year' and 'insured "
      "only' past '1' are the cells most likely to be thin -- see the n<20 flags "
      "printed directly in that table, never omitted.")
    a("")

    a("## Method and code citations")
    a("")
    a("- Pre-registered spec: item 33f, decided 2026-10-01 (task brief for this "
      "script).")
    a("- First-attempt appraisal method (reused, not restated): "
      "`SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/"
      "r44_flood_ibr_first_attempt.py (first_attempt_proxy, _tp_bin, "
      "check_fallback_and_unmapped_invariants, ARMS, _require_or_skip)`.")
    a("- Flood-experience sentence source: `examples/single_agent/run_flood.py "
      "(FinalParityHook.pre_year)`.")
    a("- Flood-experience field checked and ruled out for this domain: "
      "`broker/domains/water/providers.py (FinancialCostProvider)` (multi-agent "
      "flood only); `flood_count` reflection trait checked and ruled out: "
      "`examples/single_agent/run_flood.py (FinalParityHook.post_year)`.")
    a("- Memory-window mechanism (item 1, 2026-10 review round): "
      "`examples/single_agent/run_flood.py (run_parity_benchmark)` "
      "(`window_size=5` default, `memory_engine_type=\"window\"`) and "
      "`FinalParityHook.post_year` (`retrieve_content_only`/`retrieve` with "
      "`top_k=5`, the \"Retrieve memory for logging (Parity)\" call); raw trace "
      "field read: `raw/household_traces.jsonl`'s `memory_pre`.")
    a("- Protection state at decision time (item 2, 2026-10 review round): "
      "`raw/household_traces.jsonl`'s `state_before` field (`elevated`, "
      "`has_insurance`); `state_after` and `simulation_log.csv`'s own "
      "`elevated`/`has_insurance` columns checked and confirmed to be the "
      "POST-decision state, not used for this split. PMT citation: Grothmann and "
      "Reusswig (2006), the same source r44 cites for the R1 non-protective-"
      "response rule.")
    a("- TP normalizer and corpus/seed/directory registry: "
      "`SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/_common.py "
      "(flood_normalize_tp, flood_corpus_dirs, FLOOD_SIM, FLOOD_AUDIT)`.")
    a("- Stats helper: `SUBMISSION_2026/decomposition/_loader.py (mean)` via "
      "`_common.py`.")
    a("")
    return "\n".join(L_) + "\n"


# =============================================================================
# CSV rendering (aggregate only -- no agent_id, no per-household row)
# =============================================================================
def render_csv_rows(arm_results: dict) -> list:
    out = []
    for (corpus, key, display, _hard) in R44.ARMS:
        arm = arm_results.get((corpus, key))
        if not arm or not arm["landed_seeds"]:
            continue
        for bucket_type, bucket_key, order in (
                ("years_since_last_flood", "bucket_ys", YEARS_SINCE_BUCKETS),
                ("floods_so_far", "bucket_fs", FLOODS_SO_FAR_BUCKETS)):
            for r in build_bucket_table(arm["pooled"], bucket_key, order):
                e = r["exact"]
                row = {"corpus": corpus, "arm_key": key, "arm_display": display,
                       "bucket_type": bucket_type, "bucket": r["bucket"],
                       "n_exact": 0 if e is None else e["n"],
                       "mean_tp_ordinal": float("nan") if e is None else e["mean"],
                       "n_excluded_blank": r["n_blank"],
                       "n_excluded_bin_only": r["n_bin"],
                       "n_excluded_unresolved": r["n_unknown"],
                       "n_excluded_aborted": r["n_aborted"]}
                for lab in LABELS_ORDER:
                    row[f"pct_{lab}"] = float("nan") if e is None else e["pct"][lab]
                out.append(row)
    return out


CSV_FIELDNAMES = (["corpus", "arm_key", "arm_display", "bucket_type", "bucket",
                    "n_exact", "mean_tp_ordinal"] +
                   [f"pct_{lab}" for lab in LABELS_ORDER] +
                   ["n_excluded_blank", "n_excluded_bin_only",
                    "n_excluded_unresolved", "n_excluded_aborted"])


# =============================================================================
# main
# =============================================================================
def main() -> int:
    C.banner("R45 -- flood appraisal by flood history: per-arm processing")
    arm_results = {}
    for (corpus, key, display, hard_require) in R44.ARMS:
        print(f"\n-- {corpus}/{key} ({display}) --")
        arm_results[(corpus, key)] = _process_arm(corpus, key, display, hard_require)

    md_text = render_md(arm_results)
    csv_rows = render_csv_rows(arm_results)

    out_path = os.path.join(C.OUT, "r45_flood_appraisal_by_flood_history.md")
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(md_text)
    os.replace(tmp_path, out_path)
    print(f"\n  wrote {os.path.relpath(out_path, C.REPO).replace(chr(92), '/')} "
          f"({len(md_text.splitlines())} lines)")

    C.write_csv("r45_flood_appraisal_by_flood_history.csv", CSV_FIELDNAMES, csv_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
