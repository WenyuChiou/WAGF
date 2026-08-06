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
    problems = []
    if len(sim_rows) != EXPECTED_ROWS:
        problems.append(f"simulation_log.csv has {len(sim_rows)} rows, expected {EXPECTED_ROWS}")
    if len(audit_rows) != EXPECTED_ROWS:
        problems.append(f"{AUDIT_FILE} has {len(audit_rows)} rows, expected {EXPECTED_ROWS}")
    if problems:
        raise IntegrityError("; ".join(problems))
    return f"OK  {EXPECTED_ROWS} rows in both simulation_log.csv and {AUDIT_FILE}"


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

    missing_in_audit = sim_pairs - audit_pairs
    extra_in_audit = audit_pairs - sim_pairs
    if missing_in_audit or extra_in_audit:
        raise IntegrityError(
            f"sim/audit join is not exact: {len(missing_in_audit)} sim rows unmatched in audit, "
            f"{len(extra_in_audit)} audit rows unmatched in sim"
        )
    return (
        f"OK  {len(agents)} agents x {len(years)} years = {len(sim_pairs)} pairs, "
        "complete grid, sim/audit join exact"
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
    if manifest.get("git_dirty") is True:
        problems.append(
            "manifest git_dirty=true -- the pre-flight 'clean tagged tree' fence "
            "(launch_firstattempt.md section 1a) was not actually satisfied at run time"
        )

    if problems:
        raise IntegrityError("; ".join(problems))

    extra = (
        f" (num_ctx={manifest.get('num_ctx')}, num_predict={manifest.get('num_predict')}, "
        f"seed={manifest.get('seed')}, git_commit={str(manifest.get('git_commit'))[:12]})"
    )
    return "OK  manifest provenance consistent with launch_firstattempt.md" + extra


CHECKS = [
    ("directory", check_directory, "run_dir"),
    ("row counts", check_row_counts, "csv"),
    ("no gaps / duplicates", check_no_gaps_or_duplicates, "csv"),
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
