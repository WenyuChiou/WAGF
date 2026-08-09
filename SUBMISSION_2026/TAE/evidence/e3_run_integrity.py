#!/usr/bin/env python
"""e3_run_integrity.py -- the post-run gate for the first-attempt appraisal queue.

    python SUBMISSION_2026/TAE/evidence/e3_run_integrity.py <run_dir> [<run_dir> ...]

Checks ONE governed `gemma3:4b` irrigation run produced by
`SUBMISSION_2026/TAE/runs/launch_firstattempt.md` and decides whether it is allowed into the
analysis. Run it against a seed directory as soon as that seed's process exits, per
`PLAN.md` section 5 "Per-run integrity" fence and `EXPERIMENT_OPTIONS.md` section 7 step 3.

EXIT 0 IS NOT EVIDENCE A RUN SUCCEEDED. This corpus has three documented silent-failure modes,
none of which raises an exception or sets a non-zero process exit code:

  1. Windows Update auto-reboot mid-run (one incident, 6h47m lost, exit code never observed
     because the process was killed, but a RESUMED/relaunched run can still exit 0 while short).
  2. Silent 100% CPU fallback -- ~12x slower, ollama emits no error, the process exits 0.
  3. Silent-death: a run exiting 0 with an empty or truncated ``reflection_log.jsonl`` while the
     audit CSV looks complete (a shape this corpus has produced before).

This script is what stands between "the process exited 0" and "this run counts". It checks the
DATA, not the exit code, and FAILS LOUDLY -- raises ``IntegrityError`` and prints a banner --
rather than downgrading any of the following to a warning:

  * exact row count (78 agents x 42 years = 3,276) on BOTH simulation_log.csv and the audit csv;
  * zero (agent_id, year) gaps or duplicates in either file, and an exact join between them;
  * the initial-proposal columns (initial_skill / initial_labels / attempt_skills) are PRESENT
    in the audit header -- i.e. the isolated config's ``audit.initial_proposal_columns`` flag
    actually took effect for this run, not just in the config file;
  * ``initial_labels`` is non-empty on > 95% of ALL rows (the flag recording something on
    essentially every decision, not just intermittently) AND on > 95% of the RETRIED rows
    specifically (the rows the whole instrument exists to measure);
  * the attempt-0 appraisal (parsed out of ``initial_labels``) actually DIFFERS from the
    accepted-generation appraisal (``construct_WSA_LABEL``) on at least one retried row -- if it
    NEVER differs, the column is being written but is not recording anything, and reporting a
    "bound" from it would be reporting zero as if it were a measurement;
  * ``reflection_log.jsonl`` exists and is non-empty;
  * wall-clock is within 2x of the measured governed-anchor baseline (10.4 h/run,
    ``EXPERIMENT_OPTIONS.md`` section 1e) -- the CPU-fallback detector, computed from the first
    and last ``timestamp`` in ``raw/irrigation_farmer_traces.jsonl``, never from the exit code;
  * (corroborating, not load-bearing) the run's own manifest/config-snapshot records that it read
    the isolated config directory and not the frozen paper config.

A run failing ANY of these is not in the analysis, full stop -- ``PLAN.md`` section 5: "A run
that fails any assertion is not in the analysis." This script does not decide what to do about a
failed run (relaunch it, drop the seed, etc.); it only refuses to certify it.

Nothing here imports ``_data.py``'s discovery functions -- they are hard-anchored to
``examples/*/results`` and correctly refuse any path under ``SUBMISSION_2026/`` via
``_reject_contaminated()`` (see ``BOUNDARY.md`` section 3). This script takes an explicit run
directory on argv instead of discovering one, so no discovery function is needed; it DOES import
``_data``'s public column-name and row-count CONSTANTS, so the design constants (3,276 = 78 x 42,
the two CSV filenames, the HIGH label set) live in exactly one place in this folder.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

HERE = os.path.abspath(os.path.dirname(__file__))
TAE = os.path.dirname(HERE)
RUNS_ROOT = os.path.join(TAE, "runs")
sys.path.insert(0, HERE)

import _data  # noqa: E402  (constants only -- see module docstring)

# =============================================================================
# Constants specific to this gate (not shared with the frozen-corpus scripts,
# because this is a different corpus -- see BOUNDARY.md section 3)
# =============================================================================
IRRIGATION_AGENTS = 78
IRRIGATION_YEARS = 42
EXPECTED_ROWS = _data.IRRIGATION_EXPECTED_ROWS  # 3,276 -- shared constant, single source
assert EXPECTED_ROWS == IRRIGATION_AGENTS * IRRIGATION_YEARS

SIM_FILE = _data.IRRIGATION_SIM              # "simulation_log.csv"
AUDIT_FILE = _data.IRRIGATION_AUDIT           # "irrigation_farmer_governance_audit.csv"
TRACES_FILE = os.path.join("raw", "irrigation_farmer_traces.jsonl")
REFLECTION_FILE = "reflection_log.jsonl"
MANIFEST_FILE = "reproducibility_manifest.json"
CONFIG_SNAPSHOT_FILE = "config_snapshot.yaml"
ISOLATED_CONFIG_MARKER = "config_irrigation_firstattempt"  # dirname of the isolated config tree

BASELINE_HOURS = 10.4          # measured governed gemma3:4b cost, EXPERIMENT_OPTIONS.md section 1e
WALLCLOCK_MULTIPLE = 2.0       # "within 2x" -- PLAN.md section 5, EXPERIMENT_OPTIONS.md section 7
MAX_WALLCLOCK_HOURS = BASELINE_HOURS * WALLCLOCK_MULTIPLE

INITIAL_LABELS_MIN_PCT_ALL = 95.0       # PLAN.md section 5 / EXPERIMENT_OPTIONS.md section 7 step 3
INITIAL_LABELS_MIN_PCT_RETRIED = 95.0   # this script's own bar on the load-bearing subset

_INITIAL_COLS = ("initial_skill", "initial_labels", "attempt_skills")


class IntegrityError(RuntimeError):
    """Raised, never swallowed. A run that raises this is not in the analysis."""


# =============================================================================
# Small, self-contained readers -- deliberately NOT _data.load_sim/_data.load_audit,
# which raise on any path outside the two frozen results roots (see module docstring).
# =============================================================================
def _read_csv_rows(path: str) -> list[dict]:
    if not os.path.isfile(path):
        raise IntegrityError(f"missing file: {path}")
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise IntegrityError(f"file exists but has zero data rows: {path}")
    return rows


def _read_jsonl(path: str) -> list[dict]:
    if not os.path.isfile(path):
        raise IntegrityError(f"missing file: {path}")
    out = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise IntegrityError(f"{path}:{lineno} is not valid JSON: {exc}") from exc
    return out


def _parse_ts(s: str) -> datetime:
    # traces jsonl timestamps are ISO-8601, naive local time (no tz suffix) --
    # verified against examples/irrigation_abm/results/production_v21_42yr_seed42.
    return datetime.fromisoformat(s)


# =============================================================================
# Individual checks. Each either passes silently (returns a short OK string for
# the report) or raises IntegrityError with a specific, actionable message.
# =============================================================================
def check_directory(run_dir: str) -> str:
    run_dir = os.path.abspath(run_dir)
    if not os.path.isdir(run_dir):
        raise IntegrityError(f"not a directory: {run_dir}")
    runs_root_abs = os.path.abspath(RUNS_ROOT)
    if not (run_dir == runs_root_abs or run_dir.startswith(runs_root_abs + os.sep)):
        raise IntegrityError(
            f"run_dir {run_dir} is not under {runs_root_abs} -- this gate only certifies "
            "runs launched by launch_firstattempt.md; pointing it at examples/**/results "
            "or anywhere else is refused rather than silently accepted"
        )
    return f"OK  {run_dir}"


def check_row_counts(sim_rows: list[dict], audit_rows: list[dict]) -> str:
    """simulation_log must be the full grid; the audit CSV may be short by a REFUSAL.

    The original form of this check required exactly EXPECTED_ROWS in both files. That is right
    for simulation_log.csv -- every agent's state advances every year no matter what the model
    said, so a short sim log means a lost year -- but it is wrong for the audit CSV under
    ``--governance-mode strict``.

    Strict mode disables the default fallback: when the model returns output no parser can turn
    into a decision, after retries, the runner REFUSES to invent one. Seed 44 hit this once in
    3,276 agent-years -- ``UpalcoUintaBonnUtes_NonIndian`` year 32, three unparsable generations,
    ``[LLM:Error] Model returned unparsable output after retries`` -- and produced 3,275 audit
    rows against 3,276 sim rows. The audit CSV and the streamed JSONL agree exactly at 3,275, so
    nothing was lost on the write path; the decision was never made.

    Failing that run on a row count treats a loud, recorded, correctly-handled refusal as if it
    were data loss, and -- worse -- the hard failure BREAKS OUT of gate_one_run, skipping the
    seven checks that would have shown the run was otherwise sound. The refusal is a property of
    the model this paper is measuring, not a defect in the corpus, and hiding it behind a
    disqualification would remove the one observation where the governance layer did the exact
    thing the paper argues for.

    So: the grid invariant stays on simulation_log.csv, the audit CSV is bounded ABOVE by it, and
    ``check_undecided_rows_are_refusals`` below proves every shortfall is a refusal rather than a
    gap. Failure direction is deliberate -- an audit row with no sim row still fails hard, because
    that IS impossible.
    """
    problems = []
    if len(sim_rows) != EXPECTED_ROWS:
        problems.append(f"simulation_log.csv has {len(sim_rows)} rows, expected {EXPECTED_ROWS}")
    if len(audit_rows) > len(sim_rows):
        problems.append(
            f"{AUDIT_FILE} has {len(audit_rows)} rows, MORE than simulation_log.csv's "
            f"{len(sim_rows)} -- a decision cannot exist without a state row"
        )
    if problems:
        raise IntegrityError("; ".join(problems))

    short = len(sim_rows) - len(audit_rows)
    if short:
        return (
            f"OK  simulation_log.csv {len(sim_rows)} rows (full grid); {AUDIT_FILE} "
            f"{len(audit_rows)} -- short by {short} ({100 * short / len(sim_rows):.3f}%), "
            "each verified a refusal below"
        )
    return f"OK  {EXPECTED_ROWS} rows in both simulation_log.csv and {AUDIT_FILE}"


def check_undecided_rows_are_refusals(sim_rows: list[dict], audit_rows: list[dict]) -> str:
    """Every sim row with no audit row must be a refusal, evidenced IN THE ARTIFACTS.

    A refusal leaves a sim row whose ``yearly_decision`` is blank: the agent's state advanced,
    but no skill was chosen. A LOST row leaves a sim row with a decision in it and no audit row
    to match. The two are indistinguishable by count and completely different in meaning, which
    is why this check reads the field rather than trusting the arithmetic.

    Evidence is taken from the run directory only, never from the launcher's log file -- the log
    lives outside the run directory, is not part of the archived corpus, and a gate that depends
    on it cannot certify a corpus someone else received.

    The check runs in BOTH directions, because one direction alone is trivially evadable. An
    earlier version only walked sim rows that had no audit row, so it never inspected
    ``yearly_decision`` on a row whose audit row still existed -- blanking the sim decision and
    touching nothing else certified silently, reporting "no refusals". That was found by review
    building the control, after the docstring here had already asserted such an evasion would
    need coordinated edits to three files. It needed one. The claim was wrong and the code was
    the thing that had to change.

    RESIDUAL, stated because this check reads one field and could sound like more. It trusts the
    sim log's own ``yearly_decision`` and does not corroborate it against a third source. Dropping
    a row from the audit CSV, its JSONL trace AND blanking it in the sim log still certifies. That
    shape is not reachable from a single bug: the sim log's decision is set from
    ``result.approved_skill.skill_name`` before the auditor is involved, so the finalize-time
    aggregation defect ``recover_csv_from_jsonl`` exists for cannot also blank it. Every other
    shape tried is refused -- a plain dropped row, a dropped row disguised as a refusal, a
    dropped row with its trace removed, a fabricated audit row, and a real refusal sitting
    alongside a fake one, which is isolated correctly.
    """
    audit_pairs = _agent_year_pairs(audit_rows, AUDIT_FILE)
    REFUSAL_SENTINELS = ("", "nan", "none", "n/a")
    undecided, lost, contradictory = [], [], []
    for row in sim_rows:
        pair = (row.get("agent_id", "").strip(), str(row.get("year", "")).strip())
        # "n/a" is the irrigation sim's own sentinel for a year in which no skill was chosen
        # (run_experiment.py: `"yearly_decision": skill or "N/A"`). Verified across all five
        # seeds: it appears exactly twice in 16,380 rows, on the two genuine refusals, while
        # every other value is one of the five registered skill names. The empty/nan spellings
        # are accepted too because the sentinel is a domain convention rather than a framework
        # guarantee, and a repair tool round-tripping an empty cell through pandas would write
        # one of them.
        decision = (row.get("yearly_decision") or "").strip().lower()
        is_refusal = decision in REFUSAL_SENTINELS
        if pair in audit_pairs:
            # Direction 2: a row claiming to be a refusal while an audit row exists for it. The
            # agent either decided or it did not; both artifacts cannot be right.
            if is_refusal:
                contradictory.append((pair, decision))
            continue
        (undecided if is_refusal else lost).append((pair, decision))

    if lost:
        shown = "; ".join(f"{a} y{y} decided {d!r}" for (a, y), d in lost[:5])
        raise IntegrityError(
            f"{len(lost)} simulation row(s) carry a decision but have NO audit row -- this is "
            f"data loss on the write path, not a refusal: {shown}"
        )
    if contradictory:
        shown = "; ".join(f"{a} y{y} sim says {d!r}" for (a, y), d in contradictory[:5])
        raise IntegrityError(
            f"{len(contradictory)} simulation row(s) record NO decision while an audit row for "
            f"the same (agent, year) exists -- the two artifacts contradict each other, so one "
            f"of them has been altered: {shown}"
        )
    if not undecided:
        return "OK  every simulation row has an audit row; no refusals, no contradictions"
    shown = ", ".join(f"{a} y{y}" for (a, y), _ in undecided[:5])
    return (
        f"OK  {len(undecided)} refusal(s), {100 * len(undecided) / len(sim_rows):.3f}% of "
        f"{len(sim_rows)} -- no decision recorded, no audit row, nothing lost: {shown}"
    )


def check_audit_matches_streamed_traces(
    sim_rows: list[dict], audit_rows: list[dict], run_dir: str
) -> str:
    """The audit CSV must contain exactly what the streaming JSONL recorded.

    This is the write-path integrity check the row count used to stand in for, and it is the one
    that would actually catch a dropped row: the JSONL is appended and fsynced per decision
    during the run, the CSV is written at finalize, so a divergence between them is a loss
    between the two -- the failure mode ``broker.tools.recover_csv_from_jsonl`` exists to repair.

    The first JSONL line is a ``_metadata`` header (framework 0.6.0), not a trace; counting it
    would have made a correct 3,275/3,275 look like 3,276 and hidden exactly what this check is
    for. It is identified by structure -- a ``_metadata`` key and no ``year`` -- not by position.
    """
    path = os.path.join(run_dir, TRACES_FILE)
    if not os.path.isfile(path):
        raise IntegrityError(f"missing {TRACES_FILE} -- cannot verify the audit CSV against it")

    traces = headers = malformed = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if "_metadata" in rec and rec.get("year") is None:
                headers += 1
            else:
                traces += 1

    if malformed:
        raise IntegrityError(
            f"{TRACES_FILE}: {malformed} unparsable line(s) -- the streamed record is damaged, "
            "so it cannot be used to corroborate the audit CSV"
        )
    if traces != len(audit_rows):
        # The two directions are different failures and must not share a sentence. Fewer CSV rows
        # than traces is LOSS between the streamed write and the finalize-time aggregation, which
        # recover_csv_from_jsonl repairs. More CSV rows than traces is the opposite and more
        # alarming: a decision reached the CSV that was never streamed, so it was not produced by
        # the run's own write path. An earlier version phrased both as loss and printed "the CSV
        # lost -1 row(s)" for the second, which points whoever triages it at the wrong tool.
        delta = traces - len(audit_rows)
        if delta > 0:
            detail = (
                f"the CSV is missing {delta} row(s) that WERE streamed during the run -- "
                "recoverable, see broker.tools.recover_csv_from_jsonl"
            )
        else:
            detail = (
                f"the CSV carries {-delta} row(s) that were NEVER streamed -- not loss; a "
                "decision appeared in the aggregate that the run did not write, so treat this "
                "as fabrication or a merge of two runs, and do NOT repair it from the JSONL"
            )
        raise IntegrityError(
            f"{AUDIT_FILE} has {len(audit_rows)} rows but {TRACES_FILE} recorded {traces} "
            f"decision(s) ({headers} metadata header(s) excluded) -- {detail}"
        )
    return f"OK  {traces} streamed decisions == {len(audit_rows)} audit rows ({headers} header)"


def _agent_year_pairs(rows: list[dict], label: str) -> set[tuple[str, str]]:
    pairs = [(r.get("agent_id", "").strip(), str(r.get("year", "")).strip()) for r in rows]
    pair_set = set(pairs)
    if len(pair_set) != len(pairs):
        raise IntegrityError(
            f"{label}: {len(pairs) - len(pair_set)} duplicate (agent_id, year) row(s)"
        )
    return pair_set


def check_no_gaps_or_duplicates(sim_rows: list[dict], audit_rows: list[dict]) -> str:
    sim_pairs = _agent_year_pairs(sim_rows, "simulation_log.csv")
    audit_pairs = _agent_year_pairs(audit_rows, AUDIT_FILE)

    agents = {a for a, _ in sim_pairs}
    years = {y for _, y in sim_pairs}
    if len(agents) != IRRIGATION_AGENTS:
        raise IntegrityError(
            f"simulation_log.csv: {len(agents)} distinct agent_id values, expected "
            f"{IRRIGATION_AGENTS}"
        )
    if len(years) != IRRIGATION_YEARS:
        raise IntegrityError(
            f"simulation_log.csv: {len(years)} distinct year values, expected {IRRIGATION_YEARS}"
        )
    # A set of unique (agent, year) pairs drawn from exactly `agents` x `years` whose size
    # equals |agents| * |years| MUST be the full cross product -- there is no way to have that
    # many distinct pairs from that many agents and years without covering every combination.
    # This is the "no gaps" proof, not just a count coincidence.
    if len(sim_pairs) != len(agents) * len(years):
        missing = len(agents) * len(years) - len(sim_pairs)
        raise IntegrityError(
            f"simulation_log.csv: {missing} (agent_id, year) combination(s) missing -- "
            "not every agent has every year"
        )

    # The join is one-directional now. An audit row with no sim row is still impossible and
    # still fails here. A sim row with no audit row is a refusal OR a loss, and telling those
    # apart needs the yearly_decision field, so it belongs in
    # check_undecided_rows_are_refusals rather than being disqualified on a set difference.
    extra_in_audit = audit_pairs - sim_pairs
    if extra_in_audit:
        shown = ", ".join(f"{a} y{y}" for a, y in sorted(extra_in_audit)[:5])
        raise IntegrityError(
            f"{len(extra_in_audit)} audit row(s) have no matching simulation row -- a decision "
            f"without a state row cannot happen: {shown}"
        )
    unmatched = len(sim_pairs - audit_pairs)
    suffix = (
        "sim/audit join exact"
        if not unmatched
        else f"{unmatched} sim row(s) unmatched, classified by the next check"
    )
    return (
        f"OK  {len(agents)} agents x {len(years)} years = {len(sim_pairs)} pairs, "
        f"complete grid, {suffix}"
    )


def check_columns_present(audit_rows: list[dict]) -> str:
    header = set(audit_rows[0].keys())
    missing = [c for c in _INITIAL_COLS if c not in header]
    if missing:
        raise IntegrityError(
            f"missing column(s) {missing} in {AUDIT_FILE} -- the "
            "global_config.audit.initial_proposal_columns flag did not take effect for this "
            "run. Either --config-dir pointed at the wrong tree, or the isolated config's audit "
            "block regressed. Re-check runs/config_irrigation_firstattempt/DIFF_AGAINST_FROZEN.md "
            "before trusting anything else from this run."
        )
    return f"OK  {', '.join(_INITIAL_COLS)} present in {AUDIT_FILE}"


def _retry_count(row: dict) -> int:
    raw = (row.get("retry_count") or "0").strip()
    try:
        return int(float(raw))
    except ValueError:
        raise IntegrityError(f"unparseable retry_count value {raw!r} in {AUDIT_FILE}")


def check_initial_labels_coverage(audit_rows: list[dict]) -> str:
    n_all = len(audit_rows)
    nonempty_all = sum(1 for r in audit_rows if (r.get("initial_labels") or "").strip())
    pct_all = 100.0 * nonempty_all / n_all

    retried = [r for r in audit_rows if _retry_count(r) > 0]
    if not retried:
        raise IntegrityError(
            "zero rows have retry_count > 0 in this run -- there is no retried-and-approved "
            "stratum to measure, so this run cannot support the appraisal-revision statistic "
            "the whole queue exists to produce. (Expected 60-70% retried per "
            "EXPERIMENT_OPTIONS.md section 1c; zero is not a sampling fluke.)"
        )
    nonempty_retried = sum(1 for r in retried if (r.get("initial_labels") or "").strip())
    pct_retried = 100.0 * nonempty_retried / len(retried)

    problems = []
    if pct_all < INITIAL_LABELS_MIN_PCT_ALL:
        problems.append(
            f"initial_labels non-empty on only {pct_all:.2f}% of all {n_all} rows "
            f"(need > {INITIAL_LABELS_MIN_PCT_ALL:.0f}%)"
        )
    if pct_retried < INITIAL_LABELS_MIN_PCT_RETRIED:
        problems.append(
            f"initial_labels non-empty on only {pct_retried:.2f}% of the {len(retried)} "
            f"retried rows (need > {INITIAL_LABELS_MIN_PCT_RETRIED:.0f}%)"
        )
    if problems:
        raise IntegrityError("; ".join(problems))
    return (
        f"OK  initial_labels non-empty: {pct_all:.2f}% of all {n_all} rows, "
        f"{pct_retried:.2f}% of {len(retried)} retried rows"
    )


def _parse_label_field(pipe_joined: str, key: str) -> str | None:
    """Pull ``key``'s value out of an ``_extract_construct_labels`` pipe-joined string.

    Format is ``KEY=VALUE|KEY=VALUE|...`` (broker/core/_audit_helpers.py
    ``_extract_construct_labels``). Returns None if the key is absent.
    """
    for token in (pipe_joined or "").split("|"):
        if "=" not in token:
            continue
        k, _, v = token.partition("=")
        if k.strip() == key:
            return v.strip()
    return None


def check_appraisal_actually_differs(audit_rows: list[dict]) -> str:
    retried = [r for r in audit_rows if _retry_count(r) > 0]
    comparable = [
        r for r in retried
        if (r.get("initial_labels") or "").strip() and (r.get("construct_WSA_LABEL") or "").strip()
    ]
    if not comparable:
        raise IntegrityError(
            "zero retried rows carry BOTH a non-empty initial_labels and a non-empty "
            "construct_WSA_LABEL -- cannot even test whether the instrument is recording "
            "anything different from the accepted label"
        )
    differing = 0
    for r in comparable:
        initial_wsa = _parse_label_field(r["initial_labels"], "WSA_LABEL")
        final_wsa = (r.get("construct_WSA_LABEL") or "").strip().upper()
        if initial_wsa is None:
            continue
        if initial_wsa.strip().upper() != final_wsa:
            differing += 1
    pct = 100.0 * differing / len(comparable)
    if differing == 0:
        raise IntegrityError(
            f"initial_labels' WSA_LABEL matches construct_WSA_LABEL on ALL {len(comparable)} "
            "comparable retried rows -- the column is being written but never records a "
            "different value from the accepted generation. That means either (a) this run's "
            "retries never revised the appraisal (a real and reportable finding, but NOT what "
            "EXPERIMENT_OPTIONS.md section 1b's pilot observed on the same rule), or (b) the "
            "column is silently recording the ACCEPTED label instead of the attempt-0 one, "
            "which would be a bug upstream of this gate. Either way: do not report a bound from "
            "this run without resolving which one it is."
        )
    return (
        f"OK  WSA_LABEL differs between initial_labels and construct_WSA_LABEL on "
        f"{differing}/{len(comparable)} comparable retried rows ({pct:.2f}%) -- "
        "the instrument is recording something"
    )


def check_reflection_log(run_dir: str) -> str:
    path = os.path.join(run_dir, REFLECTION_FILE)
    rows = _read_jsonl(path)
    if not rows:
        raise IntegrityError(f"{REFLECTION_FILE} exists but has zero records")
    return f"OK  {REFLECTION_FILE}: {len(rows)} record(s)"


def check_wallclock(run_dir: str) -> str:
    path = os.path.join(run_dir, TRACES_FILE)
    if not os.path.isfile(path):
        raise IntegrityError(f"missing {TRACES_FILE} -- cannot compute wall-clock")
    first_ts = last_ts = None
    n = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            n += 1
            rec = json.loads(line)
            ts = rec.get("timestamp")
            if not ts:
                continue
            dt = _parse_ts(ts)
            if first_ts is None or dt < first_ts:
                first_ts = dt
            if last_ts is None or dt > last_ts:
                last_ts = dt
    if first_ts is None or last_ts is None:
        raise IntegrityError(f"{TRACES_FILE}: no record carries a 'timestamp' field")
    hours = (last_ts - first_ts).total_seconds() / 3600.0
    if hours <= 0:
        raise IntegrityError(
            f"{TRACES_FILE}: non-positive wall-clock span ({hours:.3f} h) across {n} records -- "
            "timestamps are not monotonic or the file was concatenated from more than one run"
        )
    if hours > MAX_WALLCLOCK_HOURS:
        raise IntegrityError(
            f"wall-clock {hours:.2f} h exceeds {MAX_WALLCLOCK_HOURS:.1f} h "
            f"({WALLCLOCK_MULTIPLE:g}x the {BASELINE_HOURS:.1f} h baseline) -- this is the "
            "signature of the documented silent CPU-fallback failure mode "
            "(EXPERIMENT_OPTIONS.md section 2, risk 4). Do not add this run to the analysis "
            "on the strength of a clean exit code; check nvidia-smi / ollama ps history for "
            "this run's window."
        )
    return f"OK  wall-clock {hours:.2f} h (baseline {BASELINE_HOURS:.1f} h, ceiling {MAX_WALLCLOCK_HOURS:.1f} h)"


# Everything the runner reads while a seed executes. Anything outside this set can be dirty
# without touching what the run did -- a manuscript, a figure, another domain's analysis.
_EXECUTION_PATHS = (
    "broker",
    "examples/irrigation_abm",
    "SUBMISSION_2026/TAE/runs/" + ISOLATED_CONFIG_MARKER,
)


def _git(*args: str) -> tuple[int, str]:
    """Run git at the repository root. Returns (exit code, stdout). Never raises."""
    import subprocess

    root = os.path.dirname(os.path.dirname(TAE))
    try:
        out = subprocess.run(
            ["git", "-C", root, *args],
            capture_output=True, text=True, timeout=60,
        )
        return out.returncode, out.stdout.strip()
    except Exception as exc:  # noqa: BLE001 -- reported, never swallowed into a pass
        return 127, f"{type(exc).__name__}: {exc}"


def _execution_path_provenance(manifest: dict[str, Any], problems: list[str]) -> str:
    """Did this run execute committed code? -- which is not the same question as `git_dirty`.

    The check this replaces failed any run whose repository-wide `git status` was non-empty. On
    this machine it never can be empty: a co-author is writing the manuscript, and a different
    paper's analysis has carried uncommitted work for weeks. Seeds 42, 43 and 44 each failed on
    it while every file the runner actually reads was committed and unchanged -- so the gate was
    rejecting all three for a property with no bearing on whether they are reproducible, and a
    criterion that fails everything sorts nothing.

    The question worth asking is narrower and answerable: are the files the run READ identical to
    the commit its manifest names? That is what someone re-running from `git_commit` would get.

    Failure direction is deliberate. Uncertainty fails: if git is unavailable, or the commit is
    missing, 'unavailable', or unknown to this clone, this appends a problem rather than passing,
    because then nobody can retrieve what ran.

    WHAT THIS DOES NOT ESTABLISH, stated because the check it replaces appeared to and did not.

    1. Whether the EXECUTION PATHS specifically were dirty AT LAUNCH cannot be recovered
       afterwards -- the manifest records one repository-wide boolean, True on all five seeds
       because of a manuscript and another paper's work-in-progress. For those the execution
       paths were separately confirmed clean at launch and attested; the fix for future runs is
       to record execution-path dirtiness in the manifest at ExperimentRunner.__init__, where
       the launch-time answer is still knowable, rather than inferring it here.

    2. It does not cover the run's UNTRACKED data. ``run_experiment.py`` resolves
       ``PROJECT_ROOT / "ref"`` unconditionally -- not gated by ``--config-dir`` -- and
       ``irrigation_personas.py`` reads ``ref/CRSS_DB/CRSS_DB/{Div_States,HistoricalData,
       Group_Agt}/*.csv`` from it: the historical diversion and precipitation series that
       parameterise all 78 agents and the 42-year trajectory. ``.gitignore`` excludes
       ``ref/CRSS_DB/``, so it is in no commit and no tree hash. Two commits can have
       byte-identical broker/, examples/irrigation_abm/ and config trees while having run
       against different CRSS data, and nothing here would notice. Found by review, 2026-08-09.
       Closing it needs a content hash of that directory recorded in the manifest at launch;
       until then "the executed code is retrievable" is exactly the claim, and the data it read
       is not part of it.

    3. The remote-twin search below is a point-in-time answer, not a durable one. It walks a
       bounded window of remote-reachable commits; this repository has days with 24-38 commits,
       so a twin found today can fall outside the window in weeks with nothing about the run
       having changed, flipping a certified run to refused during a revision. If a twin is ever
       relied on, pin it into the manifest or attestation rather than re-deriving it live.
    """
    commit = str(manifest.get("git_commit") or "").strip()
    repo_dirty = manifest.get("git_dirty")

    # SCHEMA FRESHNESS. Before 2026-08-06, git state was sampled inside
    # _collect_reproducibility_metadata, reached only from _finalize_experiment -- about ten
    # hours after launch -- so `git_commit` named whatever HEAD happened to be near the END of
    # the run, which for seed 42 is a commit authored 16 minutes before its manifest was written
    # and roughly 9.5 hours after it started. The fix moved sampling to __init__ and kept the
    # finalize values under *_at_finalize, so the PRESENCE of that key is what distinguishes a
    # launch-time commit from a finalize-time one. A run without it is not disqualified -- the
    # corpus predates the fix -- but its commit cannot be taken at face value, so this requires
    # the contemporaneous attestation instead of accepting the field silently.
    if "git_commit_at_finalize" not in manifest:
        seed = manifest.get("seed")
        att = os.path.join(RUNS_ROOT, "_logs", f"seed{seed}_provenance_attestation.md")
        name = os.path.basename(att)
        # The attestation must be READ, not merely counted. An earlier version checked only
        # os.path.isfile, so an empty file -- or one containing a shopping list -- satisfied it
        # while the gate printed "the claim rests on <name>, written contemporaneously". Binding
        # it to the commit is what makes the file evidence rather than a filename: every real
        # attestation names the commit it is vouching for, so requiring that substring costs
        # nothing legitimate and refuses a placeholder.
        if not os.path.isfile(att):
            problems.append(
                f"manifest has no 'git_commit_at_finalize' -- it predates the launch-time git "
                f"sampling fix, so git_commit={commit[:12]} was taken at FINALIZE and may name "
                f"code this run never executed. No attestation at {name} either, so nothing "
                "establishes what ran"
            )
            return " exec-path=UNATTESTED-LEGACY"
        try:
            with open(att, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            problems.append(f"attestation {name} is unreadable ({exc})")
            return " exec-path=ATTESTATION-UNREADABLE"
        # The attestation is the AUTHORITY for a legacy run, not a corroboration of the manifest.
        # It exists precisely because the manifest's commit is wrong, so requiring it to repeat
        # that commit would require it to repeat the error -- which is what a first version of
        # this check did, and it refused seed 42 for naming the right commit. seed 42's manifest
        # says 0237cb5f (finalize-sampled); the attestation says 50247de3 was the launch commit,
        # and those two differ in examples/irrigation_abm/ (tree 28539f5e vs 9d52722e), so the
        # distinction is not academic -- the run loaded the launch tree.
        #
        # So the launch commit is taken FROM the attestation, by its own explicit label, and
        # replaces the manifest's value for every check below. No label, or a label naming a
        # commit this clone does not have, fails: an attestation that cannot be resolved to code
        # establishes nothing.
        import re

        m = re.search(r"[Ll]aunch commit\s*`([0-9a-f]{7,40})`", text)
        if not m:
            problems.append(
                f"attestation {name} ({len(text)} chars) has no ``Launch commit `<sha>``` line, "
                "so the code this legacy run executed cannot be identified from it"
            )
            return " exec-path=ATTESTATION-UNPARSEABLE"
        attested = m.group(1)
        if _git("cat-file", "-e", attested + "^{commit}")[0] != 0:
            problems.append(
                f"attestation {name} names launch commit {attested[:12]}, which is not in this "
                "clone -- the code it vouches for cannot be retrieved"
            )
            return " exec-path=ATTESTATION-COMMIT-MISSING"
        legacy = (
            f"; LEGACY MANIFEST: manifest git_commit={commit[:12]} was sampled at FINALIZE and "
            f"is not the code that ran; {name} names launch commit {attested[:12]}, which is "
            "what the checks above used"
        )
        commit = attested
    else:
        legacy = ""

    if not commit or commit == "unavailable":
        problems.append(
            "manifest git_commit is missing or 'unavailable' -- the code this run executed "
            "cannot be identified, so it cannot be certified"
        )
        return " exec-path=UNKNOWN"

    rc, _ = _git("cat-file", "-e", commit + "^{commit}")
    if rc != 0:
        problems.append(
            f"manifest git_commit={commit[:12]} is not present in this clone -- the code this "
            "run executed cannot be retrieved, so it cannot be certified"
        )
        return " exec-path=UNKNOWN"

    # How far the execution paths have MOVED since is recorded, not scored. A seed launched last
    # week legitimately executed older code; that is what its commit is for. Scoring drift would
    # disqualify every run the moment the next commit lands, which is the same "criterion that
    # fails everything" defect in a different costume.
    moved = []
    for path in _EXECUTION_PATHS:
        rc_diff, out_diff = _git("diff", "--name-only", commit, "HEAD", "--", path)
        if rc_diff != 0:
            problems.append(
                f"git diff failed for {path!r} ({out_diff}) -- execution-path provenance is "
                "unverifiable, so this run is not certified"
            )
            return " exec-path=UNVERIFIABLE"
        n = len([l for l in out_diff.splitlines() if l.strip()])
        if n:
            moved.append(f"{path}+{n}")

    # DURABILITY. A commit on no remote ref lives only in this clone: delete the branch holding
    # it, run gc, and the run's provenance is gone. seed 42's commit is in exactly that position,
    # anchored only by a local backup branch.
    #
    # The obvious repair -- tag the commit and push the tag -- is WRONG here, and measuring it
    # rather than assuming it is what stopped this being shipped: that commit predates the
    # history rewrite of 2026-08-06, so pushing anything anchored to it uploads 69.3 MB and 37
    # of the 48 candidate rasters that rewrite removed. The fix would have undone the cleanup.
    #
    # What has to survive is not the commit OBJECT but the CODE. So when the exact commit is not
    # on a remote, look for a remote-reachable commit whose execution-path trees are byte-
    # identical, and report that as the retrievable equivalent. For seed 42 that is 4833ffd7 on
    # origin/p0-1-governance-instrumentation: same broker/ tree, same examples/irrigation_abm/
    # tree, different commit id. The code that ran is retrievable; only the id is local.
    rc_rem, out_rem = _git("branch", "-r", "--contains", commit)
    remotes = [l.strip() for l in out_rem.splitlines() if l.strip()] if rc_rem == 0 else []
    if remotes:
        anchor = f"pushed ({remotes[0].split()[0]}{'+' if len(remotes) > 1 else ''})"
    else:
        want = {}
        for path in _EXECUTION_PATHS:
            rc_t, out_t = _git("rev-parse", f"{commit}:{path}")
            if rc_t == 0:
                want[path] = out_t
        twin = ""
        rc_l, out_l = _git("rev-list", "--remotes", "--max-count=600")
        for cand in (out_l.splitlines() if rc_l == 0 else []):
            cand = cand.strip()
            if not cand:
                continue
            if all(_git("rev-parse", f"{cand}:{p}")[1] == h for p, h in want.items()):
                twin = cand
                break
        if twin:
            anchor = (
                f"commit id LOCAL ONLY, but the CODE is on a remote: {twin[:12]} has "
                f"byte-identical trees for all {len(want)} execution paths"
            )
        else:
            rc_loc, out_loc = _git("branch", "--contains", commit)
            local = [l.strip(" *") for l in out_loc.splitlines() if l.strip()] if rc_loc == 0 else []
            problems.append(
                f"git_commit={commit[:12]} is on no remote, and no remote-reachable commit has "
                f"matching execution-path trees -- the code this run executed exists only in "
                f"this clone ("
                + (", ".join(local) if local else "dangling, gc-eligible")
                + "), so it cannot be certified as reproducible by anyone else"
            )
            return " exec-path=LOCAL-ONLY-UNREPRODUCIBLE"

    since = f"; moved since: {', '.join(moved)}" if moved else "; unchanged since"
    return (
        f" exec-path={commit[:12]} {anchor}{since}; repo-wide git_dirty={repo_dirty} at launch, "
        f"RECORDED NOT SCORED -- see _execution_path_provenance{legacy}"
    )


def check_provenance(run_dir: str) -> str:
    """Corroborating, not load-bearing: confirm the run actually read the isolated config.

    A failure here means the run's OWN records disagree with how it was supposedly launched --
    worth surfacing loudly, but the columns/coverage/differencing checks above are the direct
    evidence the analysis depends on, so this check still fails loudly rather than being
    downgraded, per the module's "no warnings" rule.
    """
    manifest_path = os.path.join(run_dir, MANIFEST_FILE)
    if not os.path.isfile(manifest_path):
        raise IntegrityError(f"missing {MANIFEST_FILE} -- cannot verify provenance")
    with open(manifest_path, encoding="utf-8") as fh:
        manifest: dict[str, Any] = json.load(fh)

    problems = []
    cfg_path = str(manifest.get("agent_types_config", ""))
    if ISOLATED_CONFIG_MARKER not in cfg_path.replace("\\", "/"):
        problems.append(
            f"manifest agent_types_config={cfg_path!r} does not reference "
            f"{ISOLATED_CONFIG_MARKER!r} -- this run may have read the FROZEN paper config "
            "instead of the isolated one (--config-dir omitted or wrong)"
        )
    if manifest.get("model") != "gemma3:4b":
        problems.append(f"manifest model={manifest.get('model')!r}, expected 'gemma3:4b'")
    if manifest.get("governance_profile") != "strict":
        problems.append(
            f"manifest governance_profile={manifest.get('governance_profile')!r}, "
            "expected 'strict'"
        )
    dirty_note = _execution_path_provenance(manifest, problems)

    if problems:
        raise IntegrityError("; ".join(problems))

    extra = (
        f" (num_ctx={manifest.get('num_ctx')}, num_predict={manifest.get('num_predict')}, "
        f"seed={manifest.get('seed')}, git_commit={str(manifest.get('git_commit'))[:12]})"
    )
    return "OK  manifest provenance consistent with launch_firstattempt.md" + extra + dirty_note


CHECKS = [
    ("directory", check_directory, "run_dir"),
    ("row counts", check_row_counts, "csv"),
    ("no gaps / duplicates", check_no_gaps_or_duplicates, "csv"),
    ("undecided rows are refusals", check_undecided_rows_are_refusals, "csv"),
    ("audit matches streamed traces", check_audit_matches_streamed_traces, "csv_and_dir"),
    ("initial-proposal columns present", check_columns_present, "audit_only"),
    ("initial_labels coverage", check_initial_labels_coverage, "audit_only"),
    ("appraisal actually differs", check_appraisal_actually_differs, "audit_only"),
    ("reflection log non-empty", check_reflection_log, "run_dir"),
    ("wall-clock within 2x baseline", check_wallclock, "run_dir"),
    ("manifest provenance", check_provenance, "run_dir"),
]


def gate_one_run(run_dir: str) -> tuple[bool, list[tuple[str, bool, str]]]:
    """Run every check against one run directory. Never raises; collects results."""
    results: list[tuple[str, bool, str]] = []
    sim_rows = audit_rows = None

    for name, fn, kind in CHECKS:
        try:
            if kind == "run_dir":
                msg = fn(run_dir)
            elif kind == "csv":
                if sim_rows is None:
                    sim_rows = _read_csv_rows(os.path.join(run_dir, SIM_FILE))
                if audit_rows is None:
                    audit_rows = _read_csv_rows(os.path.join(run_dir, AUDIT_FILE))
                msg = fn(sim_rows, audit_rows)
            elif kind == "csv_and_dir":
                if sim_rows is None:
                    sim_rows = _read_csv_rows(os.path.join(run_dir, SIM_FILE))
                if audit_rows is None:
                    audit_rows = _read_csv_rows(os.path.join(run_dir, AUDIT_FILE))
                msg = fn(sim_rows, audit_rows, run_dir)
            elif kind == "audit_only":
                if audit_rows is None:
                    audit_rows = _read_csv_rows(os.path.join(run_dir, AUDIT_FILE))
                msg = fn(audit_rows)
            else:  # pragma: no cover -- defensive, kind is a literal above
                raise IntegrityError(f"unknown check kind {kind!r}")
            results.append((name, True, msg))
        except IntegrityError as exc:
            results.append((name, False, str(exc)))
            # A row-count or gap failure poisons every later CSV-shaped check (sim_rows /
            # audit_rows may be inconsistent-length or absent) -- stop this run's checks here
            # rather than cascading confusing secondary failures, but still report every
            # PASS already collected plus this one loud failure.
            if kind in ("run_dir", "csv") and name in ("directory", "row counts"):
                break
        except Exception as exc:  # noqa: BLE001 -- surface anything unexpected, do not hide it
            results.append((name, False, f"UNEXPECTED {type(exc).__name__}: {exc}"))
            break

    passed = all(ok for _, ok, _ in results) and len(results) == len(CHECKS)
    return passed, results


BAR = "=" * 100
RULE = "-" * 100


def _main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        print(RULE)
        print("USAGE: python e3_run_integrity.py <run_dir> [<run_dir> ...]")
        print("No run directories given -- there is nothing to certify. This is a usage")
        print("error, not a pass: this script never treats 'nothing to check' as PASS.")
        return 2

    print(BAR)
    print("e3_run_integrity.py -- per-run integrity gate")
    print(BAR)
    print(f"baseline            : {BASELINE_HOURS:.1f} h/run (governed gemma3:4b, measured)")
    print(f"wall-clock ceiling   : {MAX_WALLCLOCK_HOURS:.1f} h  ({WALLCLOCK_MULTIPLE:g}x baseline)")
    print(f"expected rows/run    : {EXPECTED_ROWS} ({IRRIGATION_AGENTS} agents x {IRRIGATION_YEARS} years)")
    print("EXIT 0 ON THIS SCRIPT MEANS EVERY RUN PASSED. Anything else means at least one run")
    print("is NOT certified for the analysis -- see PLAN.md section 5 'Per-run integrity'.")

    all_ok = True
    summary = []
    for run_dir in argv:
        print()
        print(BAR)
        print(f"RUN: {run_dir}")
        print(BAR)
        ok, results = gate_one_run(run_dir)
        for name, passed, msg in results:
            mark = "PASS" if passed else "FAIL"
            print(f"  [{mark}] {name}")
            for line in msg.splitlines():
                print(f"         {line}")
        n_run = len(results)
        n_expected = len(CHECKS)
        if n_run < n_expected:
            skipped = [name for name, _, _ in CHECKS[n_run:]]
            print(f"  [SKIP] {len(skipped)} check(s) not reached after an earlier hard failure: "
                  f"{', '.join(skipped)}")
        print(RULE)
        if ok:
            print(f"RESULT: {run_dir}  ==>  CERTIFIED, in the analysis")
        else:
            print(f"RESULT: {run_dir}  ==>  FAILED INTEGRITY GATE, NOT IN THE ANALYSIS")
            all_ok = False
        summary.append((run_dir, ok))

    print()
    print(BAR)
    print("SUMMARY")
    print(BAR)
    n_pass = sum(1 for _, ok in summary if ok)
    for run_dir, ok in summary:
        print(f"  {'CERTIFIED' if ok else 'FAILED   '}  {run_dir}")
    print(RULE)
    print(f"{n_pass}/{len(summary)} run(s) certified.")
    if n_pass < 3:
        print()
        print("FEWER THAN 3 CERTIFIED RUNS. Per PLAN.md section 5 / EXPERIMENT_OPTIONS.md section")
        print("2 'Abort rule': n >= 3 is the minimum defensible cell (df = 2). If this is the")
        print("state of the corpus at the 14 Aug freeze, DELETE the appendix section entirely --")
        print("do not report a partial result as if it were the planned n=5 cell.")
    print(BAR)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
