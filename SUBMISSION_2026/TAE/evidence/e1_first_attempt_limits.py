"""e1 -- "the first-attempt appraisal is not recoverable from this corpus".

WHAT THIS SCRIPT CLAIMS
-----------------------
Paper section 5 states a hazard and section 8 states it as a limitation:

    For a governed decision that was retried and eventually approved, the
    appraisal we observe is the one from the ACCEPTED generation. That is
    conditioning on the acceptance event -- selection on the rule itself. The
    unselected first-attempt appraisal is NOT recoverable from this corpus.

Until now that rested on four inspections done by hand, on one seed, and never
scripted (NUMBERS.md section 11 carried four rows saying exactly that). This
script recomputes all four over ALL FIVE anchor seeds so a reviewer can rerun
them, and fails loudly if any of them stops holding.

    1. RETRY STRUCTURE. How large the selected stratum actually is: rows,
       rows retried at least once, rows that exhausted the retry budget, and
       rows APPROVED after at least one retry -- the stratum whose appraisal is
       observed only in its post-rejection form. Per seed and pooled.

    2. ONE GENERATION PER STORED raw_output. If a retried row's raw_output held
       the whole retry conversation, the first attempt would be sitting right
       there. It does not: the generations in a raw_output are counted by four
       independent structural markers, on every retried row of every seed, in
       BOTH artefacts that store it (the audit csv and the trace JSONL).

    3. proposed_skill IS THE LAST PROPOSAL, NOT THE FIRST. If proposed_skill
       held the attempt-0 action it would disagree with final_skill on retried
       rows far more often than it does. It agrees on essentially all of them,
       so it is the accepted proposal recorded twice, not a first attempt.

    4. ONE JSONL RECORD PER (agent_id, year) -- THE LOAD-BEARING ONE. The trace
       stream is written per DECISION, not per ATTEMPT. If any run held more
       than one record for a key, the earlier attempts would be on disk and the
       limitation in sections 5 and 8 would be WRONG. Checked on all five anchor
       seeds in BOTH arms, not just the one seed that was inspected by hand.

Checks 2, 3 and 4 are each an attempt to FIND the first attempt. They are
written to succeed at finding it. The limitation is what is left when all three
fail.

SCOPE
-----
Anchor cell only (gemma3:4b, irrigation), because that is the cell every retry
number in the paper is quoted for. Checks 1-3 are the GOVERNED arm: the
selection they describe exists only where a validator can reject. Check 4 sweeps
BOTH arms, because it is a property of the trace writer rather than of
governance, and a defect there would not respect the arm boundary.

This script computes no rate, no delta and no test statistic. It is a structural
audit of the corpus, and nothing in it feeds a figure.

WHAT WOULD FALSIFY IT
---------------------
Every one of these exits 1, and the first three are the interesting ones:

  * ANY retried row whose raw_output contains more than one generation by any
    marker -- the first attempt would be partly recoverable from that column;
  * ANY (agent_id, year) with more than one trace record in ANY seed of ANY arm
    -- the first attempt would be recoverable outright, and sections 5 and 8
    would have to be rewritten rather than merely re-worded;
  * proposed_skill disagreeing with final_skill on a substantial share of
    retried rows -- it would then be worth investigating as a first-attempt
    column rather than dismissed as the last proposal;
  * the seed-42 counts departing from the values DECISION.md section 5 quotes
    (3,276 rows / 2,030 retried / 763 approved after retry / 2,007 of 2,030
    proposed == final), which is the hand inspection this script replaces;
  * the trace record schema growing a field that holds a list of attempts.

SIGN CONVENTION
---------------
None. There is no Delta anywhere in this script.

    python SUBMISSION_2026/TAE/evidence/e1_first_attempt_limits.py
"""

from __future__ import annotations

import collections
import json
import sys

import _data as D

# =============================================================================
# The hand-inspected values this script replaces.
# DECISION.md section 5, seed 42, governed arm. Never edited to match output --
# a disagreement is a finding, and it stops the pipeline so it cannot be missed.
# =============================================================================
BRIEF_SEED = 42
BRIEF = {
    "rows": 3276,
    "retried": 2030,
    "approved_after_retry": 763,
    "rejected_after_retry": 1267,
    "proposed_eq_final_on_retried": 2007,
    "trace_records": 3276,
    "trace_distinct_keys": 3276,
    "trace_max_per_key": 1,
}

#: Structural markers of ONE parsed generation. A second generation
#: concatenated into the same cell would push at least one of these above 1.
#: They are counted independently on purpose: the model does not always emit a
#: well-formed fence or a "decision" key, so no single marker is reliable on its
#: own, but NONE of them may ever exceed 1.
GENERATION_MARKERS = (
    '"reasoning"',
    "water_scarcity_assessment",
    "adaptive_capacity_assessment",
    "```json",
    '"decision"',
)

#: Trace-record fields that would hold a per-attempt history if one existed.
#: Presence of any of these is a finding, not an error.
ATTEMPT_HISTORY_FIELDS = (
    "attempts", "attempt_history", "retry_history", "proposals",
    "initial_labels", "initial_proposal", "rejected_proposals",
    "generations", "history",
)

#: The trace writer stores the generation twice: in full under
#: ``skill_proposal.raw_output``, and cut off at 500 characters at the top level
#: with this suffix appended. Two fields, ONE generation -- verified below
#: rather than asserted, because a reader who sees two differing raw_output
#: fields could otherwise read them as two attempts.
TRUNCATION_SUFFIX = "...[truncated]"

BAR = "=" * 100
RULE = "-" * 100


def _pct(num: int, den: int) -> float:
    return 100.0 * num / den if den else float("nan")


# =============================================================================
# 1. Retry structure -- audit csv, governed anchor
# =============================================================================
def retry_structure(seed: int) -> dict:
    """Counts for one governed anchor run. Every field is a count, not a rate."""
    rows = D.load_audit(D.irrigation_run("gov", D.IRRIGATION_ANCHOR, seed))
    budget = max(int(r["retry_count"]) for r in rows)
    retried = [r for r in rows if int(r["retry_count"]) > 0]
    return {
        "seed": seed,
        "rows": len(rows),
        "budget": budget,
        "retried": len(retried),
        "exhausted": sum(1 for r in rows if int(r["retry_count"]) == budget),
        "approved_after_retry": sum(
            1 for r in retried if not D.is_rejected(D.status(r))
        ),
        "rejected_after_retry": sum(1 for r in retried if D.is_rejected(D.status(r))),
        "never_retried": len(rows) - len(retried),
    }


def section1(per_seed: list[dict]) -> None:
    print(BAR)
    print("1. RETRY STRUCTURE -- governed arm, anchor cell (gemma3:4b), audit csv")
    print(BAR)
    print("How big is the stratum whose appraisal is observed only after the validator")
    print("has spoken to it? 'approved after retry' is that stratum: the proposal was")
    print("rejected at least once and the generation we finally observe is the one the")
    print("rule let through.")
    print()
    hdr = (f"{'seed':>5} {'rows':>7} {'retried':>9} {'%':>7} {'exhausted':>10} {'%':>7} "
           f"{'appr.after':>11} {'%':>7} {'rej.after':>10} {'%':>7} {'never':>7} {'%':>7}")
    print(hdr)
    print("-" * len(hdr))
    for s in per_seed:
        print(f"{s['seed']:>5} {s['rows']:>7,} {s['retried']:>9,} {_pct(s['retried'], s['rows']):>7.1f} "
              f"{s['exhausted']:>10,} {_pct(s['exhausted'], s['rows']):>7.1f} "
              f"{s['approved_after_retry']:>11,} {_pct(s['approved_after_retry'], s['rows']):>7.1f} "
              f"{s['rejected_after_retry']:>10,} {_pct(s['rejected_after_retry'], s['rows']):>7.1f} "
              f"{s['never_retried']:>7,} {_pct(s['never_retried'], s['rows']):>7.1f}")
    print("-" * len(hdr))
    tot = {k: sum(s[k] for s in per_seed)
           for k in ("rows", "retried", "exhausted", "approved_after_retry",
                     "rejected_after_retry", "never_retried")}
    print(f"{'pooled':>5} {tot['rows']:>7,} {tot['retried']:>9,} {_pct(tot['retried'], tot['rows']):>7.1f} "
          f"{tot['exhausted']:>10,} {_pct(tot['exhausted'], tot['rows']):>7.1f} "
          f"{tot['approved_after_retry']:>11,} {_pct(tot['approved_after_retry'], tot['rows']):>7.1f} "
          f"{tot['rejected_after_retry']:>10,} {_pct(tot['rejected_after_retry'], tot['rows']):>7.1f} "
          f"{tot['never_retried']:>7,} {_pct(tot['never_retried'], tot['rows']):>7.1f}")
    print()
    budgets = sorted({s["budget"] for s in per_seed})
    print(f"retry budget observed (max retry_count) : {budgets}  -- read from the data, not assumed")
    per_seed_pct = ["%.1f%%" % _pct(s["approved_after_retry"], s["rows"]) for s in per_seed]
    print(f"approved-after-retry stratum, per seed  : {per_seed_pct}")
    print(f"approved-after-retry stratum, pooled    : "
          f"{tot['approved_after_retry']:,} / {tot['rows']:,} = "
          f"{_pct(tot['approved_after_retry'], tot['rows']):.1f}%")
    print()
    print("STRATUM NAMING, which every quoted retry number in the paper must carry:")
    print("  'retried'   = retry_count > 0            (a validator rejected it at least once)")
    print("  'exhausted' = retry_count == the budget  (it never satisfied the stack)")
    print("  These are ALL YEARS. The paper's year-1 numbers (82.1% retried / 70.5%")
    print("  exhausted) are a different stratum and come from fig2_mechanism.py.")
    print()


# =============================================================================
# 2 + 4. One streaming pass over each trace JSONL
# =============================================================================
def scan_traces(arm: str, seed: int) -> dict:
    """One pass over a run's trace stream. Streams; never holds the file."""
    path = D.irrigation_traces_path(D.irrigation_run(arm, D.IRRIGATION_ANCHOR, seed))
    keys: collections.Counter = collections.Counter()
    schema: collections.Counter = collections.Counter()
    marker_top: dict[str, collections.Counter] = {
        m: collections.Counter() for m in GENERATION_MARKERS}
    marker_prop: dict[str, collections.Counter] = {
        m: collections.Counter() for m in GENERATION_MARKERS}
    n_lines = n_records = n_blank = 0
    n_retried = 0
    retry_counts: collections.Counter = collections.Counter()
    no_proposal = 0
    n_with_proposal = n_truncated = n_prefix_of_full = 0

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            n_lines += 1
            if not line.strip():
                n_blank += 1
                continue
            try:
                rec = json.loads(line)
            except ValueError as exc:
                raise D.DataError(
                    f"{path}: line {n_lines} is not valid JSON ({exc}); refusing to "
                    "report a record count over a stream that does not parse"
                ) from exc
            n_records += 1
            schema.update(rec.keys())
            keys[(rec.get("agent_id"), rec.get("year"))] += 1

            rc = int(rec.get("retry_count") or 0)
            retry_counts[rc] += 1

            # Both places a generation is stored. The top-level copy is
            # truncated by the writer; the skill_proposal copy is the full text.
            top = rec.get("raw_output") or ""
            proposal = rec.get("skill_proposal") or {}
            prop = (proposal.get("raw_output") if proposal else "") or ""

            # Is the top-level copy the SAME generation, merely cut short?
            # Checked on every record, not only retried ones.
            if proposal:
                n_with_proposal += 1
                head = (top[: -len(TRUNCATION_SUFFIX)]
                        if top.endswith(TRUNCATION_SUFFIX) else top)
                if prop.startswith(head):
                    n_prefix_of_full += 1
            if top.endswith(TRUNCATION_SUFFIX):
                n_truncated += 1

            if rc <= 0:
                continue
            n_retried += 1
            if not proposal:
                no_proposal += 1
            for m in GENERATION_MARKERS:
                marker_top[m][top.count(m)] += 1
                marker_prop[m][prop.count(m)] += 1

    dupes = {k: v for k, v in keys.items() if v > 1}
    return {
        "arm": arm,
        "seed": seed,
        "path": path,
        "lines": n_lines,
        "blank_lines": n_blank,
        "records": n_records,
        "distinct_keys": len(keys),
        "max_per_key": max(keys.values()) if keys else 0,
        "duplicate_keys": dupes,
        "schema": schema,
        "retried": n_retried,
        "retry_counts": retry_counts,
        "marker_top": marker_top,
        "marker_prop": marker_prop,
        "retried_without_proposal": no_proposal,
        "with_proposal": n_with_proposal,
        "truncated": n_truncated,
        "prefix_of_full": n_prefix_of_full,
    }


def audit_generation_markers(seed: int) -> dict:
    """Marker counts on the audit csv's raw_output, retried rows only."""
    rows = D.load_audit(D.irrigation_run("gov", D.IRRIGATION_ANCHOR, seed))
    retried = [r for r in rows if int(r["retry_count"]) > 0]
    out = {m: collections.Counter() for m in GENERATION_MARKERS}
    lens = []
    for r in retried:
        raw = r.get("raw_output") or ""
        lens.append(len(raw))
        for m in GENERATION_MARKERS:
            out[m][raw.count(m)] += 1
    return {"seed": seed, "n": len(retried), "markers": out,
            "len_min": min(lens) if lens else 0,
            "len_max": max(lens) if lens else 0,
            "empty": sum(1 for n in lens if n == 0)}


def _marker_line(name: str, counters: dict[str, collections.Counter]) -> str:
    dist = dict(sorted(counters[name].items()))
    total = sum(dist.values())
    mx = max(dist) if dist else 0
    flag = "" if mx <= 1 else "   <== MORE THAN ONE GENERATION"
    return f"  {name:<32} n={total:>6,}  max={mx}  distribution {dist}{flag}"


def section2(audit_rows: list[dict], traces: list[dict]) -> None:
    print(BAR)
    print("2. HOW MANY GENERATIONS ARE IN ONE STORED raw_output?")
    print(BAR)
    print("If the retry conversation were stored, a retried row's raw_output would hold")
    print("the rejected attempt AND the accepted one. Counted here on every retried row")
    print("of every anchor seed, by four independent structural markers, rather than by")
    print("reading one row. A count above 1 on any marker is the finding.")
    print()
    print("(a) AUDIT CSV  irrigation_farmer_governance_audit.csv, column raw_output")
    print()
    merged = {m: collections.Counter() for m in GENERATION_MARKERS}
    n_ret = 0
    for a in audit_rows:
        n_ret += a["n"]
        for m in GENERATION_MARKERS:
            merged[m].update(a["markers"][m])
    for a in audit_rows:
        print(f"    seed {a['seed']}: {a['n']:,} retried rows, raw_output length "
              f"{a['len_min']}-{a['len_max']} chars, {a['empty']} empty")
    print()
    print(f"  pooled over {n_ret:,} retried rows, all 5 seeds:")
    for m in GENERATION_MARKERS:
        print(_marker_line(m, merged))
    print()
    print("(b) TRACE JSONL  raw/irrigation_farmer_traces.jsonl, governed arm")
    print()
    tg = [t for t in traces if t["arm"] == "gov"]
    print("  FIRST, the two raw_output fields. A trace record stores raw_output twice --")
    print("  once at the top level and once inside skill_proposal -- and the two strings")
    print("  DIFFER, which a reader could take for two attempts. They are not. The")
    print(f"  top-level copy is the same generation cut off at 500 characters and closed")
    print(f"  with '{TRUNCATION_SUFFIX}':")
    print()
    hdr = (f"  {'arm':<17} {'seed':>5} {'records':>9} {'w/ proposal':>12} "
           f"{'truncated':>10} {'top is a prefix of the full text':>34}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for t in traces:
        print(f"  {D.ARM_DISPLAY[t['arm']]:<17} {t['seed']:>5} {t['records']:>9,} "
              f"{t['with_proposal']:>12,} {t['truncated']:>10,} "
              f"{t['prefix_of_full']:>12,} / {t['with_proposal']:<19,}")
    print()
    print("  So the two fields are one generation, and the marker counts below that read")
    print("  0 on the truncated copy are the 500-character cut, not a missing block. The")
    print("  count that matters is that NOTHING reaches 2.")
    print()
    m_top = {m: collections.Counter() for m in GENERATION_MARKERS}
    m_prop = {m: collections.Counter() for m in GENERATION_MARKERS}
    n_jr = 0
    for t in tg:
        n_jr += t["retried"]
        for m in GENERATION_MARKERS:
            m_top[m].update(t["marker_top"][m])
            m_prop[m].update(t["marker_prop"][m])
    print(f"  record.raw_output  (truncated copy; 0 counts are the cut), {n_jr:,} retried records:")
    for m in GENERATION_MARKERS:
        print(_marker_line(m, m_top))
    print()
    print(f"  record.skill_proposal.raw_output  (the full generation), {n_jr:,} retried records:")
    for m in GENERATION_MARKERS:
        print(_marker_line(m, m_prop))
    print()
    print(f"  Retried records with no skill_proposal object at all: "
          f"{sum(t['retried_without_proposal'] for t in tg):,}")
    print("  (retry-exhausted fallback rows -- nothing was parsed to store). They are")
    print("  the same rows as the blank proposed_skill rows in section 3.")
    print()


# =============================================================================
# 3. proposed_skill vs final_skill on retried rows
# =============================================================================
def proposed_vs_final(seed: int) -> dict:
    rows = D.load_audit(D.irrigation_run("gov", D.IRRIGATION_ANCHOR, seed))
    retried = [r for r in rows if int(r["retry_count"]) > 0]
    equal = differ = 0
    differ_kinds: collections.Counter = collections.Counter()
    blank_proposed = 0
    for r in retried:
        p = (r.get("proposed_skill") or "").strip()
        f = (r.get("final_skill") or "").strip()
        if not p:
            blank_proposed += 1
        if p == f:
            equal += 1
        else:
            differ += 1
            differ_kinds[(p or "<blank>", f or "<blank>", D.status(r))] += 1
    return {"seed": seed, "retried": len(retried), "equal": equal, "differ": differ,
            "kinds": differ_kinds, "blank_proposed": blank_proposed}


def section3(pv: list[dict]) -> None:
    print(BAR)
    print("3. IS proposed_skill THE FIRST PROPOSAL OR THE LAST?  governed, retried rows")
    print(BAR)
    print("A column holding the attempt-0 action would disagree with final_skill on most")
    print("retried rows, since a retry happens exactly because the first action was")
    print("refused. It agrees on essentially all of them.")
    print()
    hdr = f"{'seed':>5} {'retried':>9} {'proposed==final':>17} {'%':>8} {'differ':>8} {'blank proposed':>16}"
    print(hdr)
    print("-" * len(hdr))
    for p in pv:
        print(f"{p['seed']:>5} {p['retried']:>9,} {p['equal']:>17,} "
              f"{_pct(p['equal'], p['retried']):>8.2f} {p['differ']:>8,} {p['blank_proposed']:>16,}")
    print("-" * len(hdr))
    t_ret = sum(p["retried"] for p in pv)
    t_eq = sum(p["equal"] for p in pv)
    t_df = sum(p["differ"] for p in pv)
    print(f"{'pooled':>5} {t_ret:>9,} {t_eq:>17,} {_pct(t_eq, t_ret):>8.2f} {t_df:>8,} "
          f"{sum(p['blank_proposed'] for p in pv):>16,}")
    print()
    print("Every disagreeing row, by (proposed_skill, final_skill, status):")
    kinds: collections.Counter = collections.Counter()
    for p in pv:
        kinds.update(p["kinds"])
    for (prop, fin, st), n in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>6,}  proposed={prop:<16} final={fin:<16} status={st}")
    print()
    non_blank_differ = sum(n for (prop, _f, _s), n in kinds.items() if prop != "<blank>")
    print(f"Disagreements where a proposal was actually recorded: {non_blank_differ:,}")
    print("If that is 0, the column never carries a DIFFERENT action from the accepted")
    print("one: it is the accepted proposal written twice. It is the LAST proposal, and")
    print("the first attempt is not in it.")
    print()


# =============================================================================
# 4. One trace record per (agent_id, year) -- the load-bearing check
# =============================================================================
def section4(traces: list[dict]) -> None:
    print(BAR)
    print("4. ONE TRACE RECORD PER (agent_id, year)?  BOTH ARMS, ALL FIVE ANCHOR SEEDS")
    print(BAR)
    print("THE LOAD-BEARING CHECK. The trace stream is the only artefact large enough to")
    print("have held the whole retry conversation. If it is written per DECISION, the")
    print("rejected attempts were never persisted and the first-attempt appraisal is")
    print("gone. If ANY key has more than one record, they were persisted, the appraisal")
    print("is at least partly recoverable, and sections 5 and 8 of the paper are WRONG.")
    print()
    hdr = (f"{'arm':<17} {'seed':>5} {'lines':>8} {'blank':>6} {'records':>9} "
           f"{'distinct keys':>14} {'max per key':>12} {'dup keys':>9}")
    print(hdr)
    print("-" * len(hdr))
    for t in traces:
        flag = "" if t["max_per_key"] <= 1 else "   <== MORE THAN ONE RECORD PER DECISION"
        print(f"{D.ARM_DISPLAY[t['arm']]:<17} {t['seed']:>5} {t['lines']:>8,} "
              f"{t['blank_lines']:>6,} {t['records']:>9,} {t['distinct_keys']:>14,} "
              f"{t['max_per_key']:>12} {len(t['duplicate_keys']):>9,}{flag}")
    print("-" * len(hdr))
    print()
    for t in traces:
        if t["duplicate_keys"]:
            print(f"!! {D.ARM_DISPLAY[t['arm']]} seed {t['seed']}: "
                  f"{len(t['duplicate_keys']):,} duplicated (agent_id, year) keys")
            for k, v in sorted(t["duplicate_keys"].items(), key=lambda kv: -kv[1])[:10]:
                print(f"     {k} -> {v} records")
    print("Trace-record schema, pooled -- a field holding a list of attempts would")
    print("appear here and would be the whole answer on its own:")
    schema: collections.Counter = collections.Counter()
    n_rec = 0
    for t in traces:
        schema.update(t["schema"])
        n_rec += t["records"]
    for name, n in sorted(schema.items()):
        mark = "  <== ATTEMPT HISTORY FIELD" if name in ATTEMPT_HISTORY_FIELDS else ""
        print(f"  {name:<28} present on {n:>7,} / {n_rec:,} records{mark}")
    found = sorted(set(schema) & set(ATTEMPT_HISTORY_FIELDS))
    print()
    print(f"attempt-history fields present: {found if found else 'NONE'}")
    print()
    # A field that is on every record of some runs and on none of others is a
    # writer-version marker. It does not touch this section's claim -- agent_id,
    # year and retry_count are on every record of every run -- but it is a
    # provenance fact and the paper's provenance paragraph should carry it.
    drift = sorted(
        name for name in schema
        if any(t["schema"].get(name, 0) not in (0, t["records"]) for t in traces)
        or len({t["schema"].get(name, 0) > 0 for t in traces}) > 1
    )
    print("PROVENANCE OBSERVATION (does not bear on the claim above, does not fail):")
    if not drift:
        print("  every trace field is present on every record of every run.")
    else:
        for name in drift:
            has = [f"{D.ARM_DISPLAY[t['arm']]}/{t['seed']}"
                   for t in traces if t["schema"].get(name, 0) > 0]
            lacks = [f"{D.ARM_DISPLAY[t['arm']]}/{t['seed']}"
                     for t in traces if t["schema"].get(name, 0) == 0]
            print(f"  field {name!r} present in {len(has)} run(s), absent in {len(lacks)}")
            print(f"    present : {', '.join(has)}")
            print(f"    absent  : {', '.join(lacks)}")
        print("  The fields that carry the (agent_id, year, retry_count) identity are on")
        print("  every record of every run, so the check above is unaffected. A field that")
        print("  splits the runs is a writer-version marker: these seeds were not all")
        print("  written by the same code state. That belongs in the provenance paragraph.")
    print()
    print("retry_count distribution in the trace stream, governed arm (it matches the")
    print("audit csv, so the record kept IS the final attempt, not the first):")
    rc: collections.Counter = collections.Counter()
    for t in traces:
        if t["arm"] == "gov":
            rc.update(t["retry_counts"])
    print(f"  {dict(sorted(rc.items()))}")
    print()
    print("SCOPE NOTE. This says the first attempt is unrecoverable FROM THE SHIPPED")
    print("CORPUS. It does not say the framework cannot capture it. The code at HEAD")
    print("does persist attempt-0 labels behind a default-OFF audit option; these runs")
    print("were produced before it and did not have it on. The paper must keep those two")
    print("statements apart.")
    print()


# =============================================================================
# Verification
# =============================================================================
def verify(per_seed, audit_rows, pv, traces) -> list[str]:
    fails: list[str] = []

    def check(desc: str, got, want) -> None:
        ok = got == want
        print(f"  {'OK ' if ok else '!! '} {desc:<62} got {str(got):>12}  brief {str(want):>12}"
              f"{'' if ok else '   <== DISAGREES WITH THE BRIEF'}")
        if not ok:
            fails.append(f"{desc}: got {got}, brief {want}")

    def assertion(desc: str, ok: bool, detail: str = "") -> None:
        print(f"  {'OK ' if ok else '!! '} {desc}{'' if ok else '   <== ' + detail}")
        if not ok:
            fails.append(f"{desc}: {detail}")

    print(BAR)
    print("VERIFICATION")
    print(BAR)
    print(f"Against DECISION.md section 5, seed {BRIEF_SEED}, governed arm -- the hand")
    print("inspection this script replaces:")
    s42 = next(s for s in per_seed if s["seed"] == BRIEF_SEED)
    p42 = next(p for p in pv if p["seed"] == BRIEF_SEED)
    t42 = next(t for t in traces if t["arm"] == "gov" and t["seed"] == BRIEF_SEED)
    check("seed 42 audit rows", s42["rows"], BRIEF["rows"])
    check("seed 42 retried (retry_count > 0)", s42["retried"], BRIEF["retried"])
    check("seed 42 approved after retry", s42["approved_after_retry"],
          BRIEF["approved_after_retry"])
    check("seed 42 rejected after retry", s42["rejected_after_retry"],
          BRIEF["rejected_after_retry"])
    check("seed 42 proposed == final on retried rows", p42["equal"],
          BRIEF["proposed_eq_final_on_retried"])
    check("seed 42 trace records", t42["records"], BRIEF["trace_records"])
    check("seed 42 trace distinct (agent, year) keys", t42["distinct_keys"],
          BRIEF["trace_distinct_keys"])
    check("seed 42 trace max records per key", t42["max_per_key"],
          BRIEF["trace_max_per_key"])

    print()
    print("The three attempts to FIND the first attempt, over all five seeds:")

    # -- check 2
    worst = 0
    where = ""
    for a in audit_rows:
        for m in GENERATION_MARKERS:
            mx = max(a["markers"][m]) if a["markers"][m] else 0
            if mx > worst:
                worst, where = mx, f"audit csv seed {a['seed']} marker {m}"
    for t in traces:
        if t["arm"] != "gov":
            continue
        for m in GENERATION_MARKERS:
            for src, cs in (("record.raw_output", t["marker_top"]),
                            ("skill_proposal.raw_output", t["marker_prop"])):
                mx = max(cs[m]) if cs[m] else 0
                if mx > worst:
                    worst, where = mx, f"jsonl {src} seed {t['seed']} marker {m}"
    assertion(
        f"no retried raw_output holds >1 generation (worst marker count {worst})",
        worst <= 1,
        f"{where} reaches {worst}: THE FIRST ATTEMPT IS PARTLY RECOVERABLE FROM raw_output",
    )
    n_wp = sum(t["with_proposal"] for t in traces)
    n_pf = sum(t["prefix_of_full"] for t in traces)
    assertion(
        f"the two raw_output fields are one generation, not two ({n_pf:,}/{n_wp:,} "
        "top-level copies are a literal prefix of the full text)",
        n_pf == n_wp,
        f"{n_wp - n_pf:,} records where the top-level raw_output is NOT a prefix of "
        "skill_proposal.raw_output: the two fields may hold DIFFERENT generations",
    )

    # -- check 3
    non_blank = 0
    for p in pv:
        non_blank += sum(n for (prop, _f, _s), n in p["kinds"].items() if prop != "<blank>")
    assertion(
        f"no retried row records a proposed_skill different from final_skill ({non_blank})",
        non_blank == 0,
        f"{non_blank} rows carry a different proposal: proposed_skill may be the FIRST "
        "attempt after all and must be re-examined",
    )

    # -- check 4, the load-bearing one
    bad = [t for t in traces if t["max_per_key"] > 1]
    assertion(
        f"one trace record per (agent_id, year) in all {len(traces)} runs, both arms",
        not bad,
        "; ".join(f"{D.ARM_DISPLAY[t['arm']]} seed {t['seed']} has up to "
                  f"{t['max_per_key']} records for one key" for t in bad)
        + " -- THE FIRST-ATTEMPT APPRAISAL IS RECOVERABLE AND THE PAPER'S SECTION 5/8 "
          "LIMITATION IS WRONG",
    )
    for t in traces:
        if t["records"] != t["distinct_keys"]:
            fails.append(
                f"{D.ARM_DISPLAY[t['arm']]} seed {t['seed']}: {t['records']} records but "
                f"{t['distinct_keys']} distinct keys"
            )
    assertion(
        "records == distinct keys in every run (no key counted twice)",
        all(t["records"] == t["distinct_keys"] for t in traces),
        "see the table in section 4",
    )
    found = sorted({f for t in traces for f in t["schema"]} & set(ATTEMPT_HISTORY_FIELDS))
    assertion(
        "no attempt-history field in the trace schema",
        not found,
        f"schema carries {found}: the attempts may be persisted after all",
    )

    print()
    print("Consistency of the corpus itself:")
    assertion(
        f"every governed anchor run has {D.IRRIGATION_EXPECTED_ROWS:,} audit rows",
        all(s["rows"] == D.IRRIGATION_EXPECTED_ROWS for s in per_seed),
        str([s["rows"] for s in per_seed]),
    )
    assertion(
        f"every trace stream has {D.IRRIGATION_EXPECTED_ROWS:,} records",
        all(t["records"] == D.IRRIGATION_EXPECTED_ROWS for t in traces),
        str([(t["arm"], t["seed"], t["records"]) for t in traces]),
    )
    assertion(
        "no blank lines in any trace stream",
        all(t["blank_lines"] == 0 for t in traces),
        str([(t["arm"], t["seed"], t["blank_lines"]) for t in traces]),
    )
    gov_traces = {t["seed"]: t for t in traces if t["arm"] == "gov"}
    rc_ok = all(gov_traces[s["seed"]]["retried"] == s["retried"] for s in per_seed)
    assertion(
        "trace retry_count agrees with the audit csv on every governed seed",
        rc_ok,
        str([(s["seed"], s["retried"], gov_traces[s["seed"]]["retried"]) for s in per_seed]),
    )
    print()
    return fails


# =============================================================================
def main() -> int:
    print(BAR)
    print("e1 -- FIRST-ATTEMPT LIMITS  (paper sections 5 and 8)")
    print(BAR)
    print(f"cell        : {D.IRRIGATION_ANCHOR.label}, irrigation, anchor")
    print("checks 1-3  : governed arm  (the selection exists only where a rule can reject)")
    print("check 4     : both arms     (a trace-writer defect would not respect the arm)")
    print("no rate, no delta, no test statistic is computed anywhere in this script")
    print()

    seeds = sorted(D.irrigation_runs("gov", D.IRRIGATION_ANCHOR))
    print(f"governed anchor seeds discovered by _data : {seeds}")
    print(f"no-validator anchor seeds                 : "
          f"{sorted(D.irrigation_runs('noval', D.IRRIGATION_ANCHOR))}")
    print()

    per_seed = [retry_structure(s) for s in seeds]
    audit_rows = [audit_generation_markers(s) for s in seeds]
    pv = [proposed_vs_final(s) for s in seeds]
    traces = [scan_traces(arm, s) for arm in D.ARMS
              for s in sorted(D.irrigation_runs(arm, D.IRRIGATION_ANCHOR))]

    section1(per_seed)
    section2(audit_rows, traces)
    section3(pv)
    section4(traces)
    fails = verify(per_seed, audit_rows, pv, traces)

    print(BAR)
    if fails:
        print("e1: FALSIFIED -- one or more checks disagree")
        print(BAR)
        for f in fails:
            print("  !! " + f)
        print()
        print("Do not tune this script until it stops saying so. If check 2, 3 or 4")
        print("failed, the first-attempt appraisal is more recoverable than DECISION.md")
        print("section 5 claims and the paper's limitation must be rewritten, not the")
        print("script. If only the seed-42 brief values disagree, the hand inspection was")
        print("wrong and the computed values are the ones to publish.")
        print(BAR)
        return 1
    print("e1: VERIFIED -- all four inspections reproduce, on all five anchor seeds.")
    print(BAR)
    print("What the paper may now write, sourced to this script:")
    tot_rows = sum(s["rows"] for s in per_seed)
    tot_ret = sum(s["retried"] for s in per_seed)
    tot_app = sum(s["approved_after_retry"] for s in per_seed)
    tot_exh = sum(s["exhausted"] for s in per_seed)
    print(f"  * Over all years of the governed anchor cell, {_pct(tot_ret, tot_rows):.1f}% of decisions were")
    print(f"    rejected and re-prompted at least once and {_pct(tot_exh, tot_rows):.1f}% exhausted the retry")
    print(f"    budget; {_pct(tot_app, tot_rows):.1f}% ({tot_app:,} of {tot_rows:,}) were approved only after at least")
    print("    one rejection, and it is that stratum whose appraisal is observed solely")
    print("    in its post-rejection form.")
    print("  * The first attempt is not in the corpus: one generation per stored")
    print("    raw_output, proposed_skill equal to final_skill wherever a proposal was")
    print(f"    recorded, and exactly one trace record per (agent, year) in all "
          f"{len(traces)} runs")
    print("    of both arms.")
    print(BAR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
