"""Read model-call outcomes without importing the runtime or changing a run.

Usage: python -m broker.tools.check_llm_transport RUN_DIR [RUN_DIR ...]
       [--journal FILE] [--log FILE ...] [--json] [--all-steps]

Exit codes: 0 no transport or unclassified failure, 3 failure in a completed
step, 4 failure with no end marker, 2 no readable source or no journal calls,
1 usage or data error. Several runs use priority 3, then 1, 2, 4, and 0.
Text shows failed steps and steps without an end marker; --all-steps shows all.
JSON always includes every step. Known request timeouts count as other failures.
Journal calls and log observations are reported separately, never added.
A truncated last journal line is ignored as the resume loader ignores it, so a
failure recorded only in that broken line cannot be seen. When several logs are
given, overlapping logs can count one event twice.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


# broker/utils/llm_journal.py (LLMJournalWriter.record_call) stores class names.
# These names identify known connection failures without importing providers.
_TRANSPORT_EXCEPTIONS = {
    # Python builtins (OSError) and its non-timeout subclasses and aliases.
    "OSError", "IOError", "EnvironmentError", "WindowsError", "BlockingIOError",
    "ChildProcessError", "ConnectionError", "BrokenPipeError", "ConnectionAbortedError",
    "ConnectionRefusedError", "ConnectionResetError", "FileExistsError",
    "FileNotFoundError", "InterruptedError", "IsADirectoryError", "NotADirectoryError",
    "PermissionError", "ProcessLookupError",
    # requests/exceptions.py (ConnectionError, SSLError, ProxyError, ChunkedEncodingError).
    "SSLError", "ProxyError", "ChunkedEncodingError",
    # urllib3/exceptions.py (connection, protocol, retry and pool errors).
    "ProtocolError", "NewConnectionError", "NameResolutionError", "MaxRetryError",
    "ClosedPoolError", "EmptyPoolError",
    # urllib/error.py (URLError) and http/client.py (connection and response errors).
    "URLError", "RemoteDisconnected", "IncompleteRead", "BadStatusLine", "LineTooLong",
    # broker/utils/llm_safeguard.py (wrap_llm_invoke_with_backoff) catches builtin
    # TimeoutError as OSError and marks it transport, unlike requests timeouts.
    "TimeoutError",
    # broker/utils/llm_journal.py (LLMTransportStopped) stops on failed calls.
    "LLMTransportStopped",
}
_TIMEOUT_EXCEPTIONS = {"Timeout", "ReadTimeout", "ConnectTimeout", "timeout"}

# broker/utils/llm_safeguard.py (wrap_llm_invoke_with_backoff) prints the
# give-up message; broker/core/_retry_loop.py (RetryMixin) prints a
# follow-up notice for the same call. Prefer give-ups within each step.
_LOG_PATTERNS = {
    "step_marker": r"---\s+(?:Year|Step)\s+(\d+)\s+---",
    "give_up": r"\[LLM:Safeguard\] transport failure persisted after \d+ attempt\(s\); giving up",
    "transport_notice": r"\[LLM:Error\] Transport failure persisted",
    "other_error": r"\[Reflection(?::Batch)?:Error\]",
}
_LOG_REGEX = {name: re.compile(pattern) for name, pattern in _LOG_PATTERNS.items()}


def _step(steps, number):
    return steps.setdefault(number, {
        "step": number, "calls": 0, "transport_failed_calls": 0,
        "other_failed_calls": 0, "unclassified_failed_calls": 0,
        "unclassified_exception_types": {}, "has_step_end": False,
        "log_transport_failures": 0, "log_other_failures": 0,
    })


def _read_journal(path, steps, warnings):
    """Stream records with one-line lookahead to identify the final write."""
    readable = False
    # broker/utils/llm_journal.py (load_journal_for_resume) tolerates only
    # a corrupt final JSON line, including one ending with a newline.
    with path.open("rb") as source:
        current = source.readline()
        number = 0
        while current:
            number += 1
            following = source.readline()
            try:
                record = json.loads(current.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                if not following:
                    warnings.append(f"{path}: ignored truncated final line {number}")
                    break
                raise ValueError(f"{path}: line {number}: unreadable journal record: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}: line {number}: expected a record object")
            if number == 1:
                if record.get("type") != "header":
                    raise ValueError(f"{path}: line 1: missing header record")
                readable = True
            elif record.get("type") in ("call", "step_end"):
                step = record.get("step")
                if type(step) is not int or step < 0:
                    raise ValueError(f"{path}: line {number}: step must be a non-negative integer")
                row = _step(steps, step)
                if record["type"] == "step_end":
                    row["has_step_end"] = True
                else:
                    stats = record.get("stats")
                    if stats is None:
                        stats = {}
                    if not isinstance(stats, dict):
                        raise ValueError(f"{path}: line {number}: stats must be an object or null")
                    for key in ("success", "transport_error"):
                        if key in stats and type(stats[key]) is not bool:
                            raise ValueError(f"{path}: line {number}: stats.{key} must be boolean")
                    raised = record.get("raised", False)
                    exception = record.get("exception_type")
                    if type(raised) is not bool or (exception is not None and not isinstance(exception, str)):
                        raise ValueError(f"{path}: line {number}: invalid raised or exception_type field")
                    row["calls"] += 1
                    type_name = (exception or "").rsplit(".", 1)[-1]
                    transport = stats.get("transport_error") is True or (raised and type_name in _TRANSPORT_EXCEPTIONS)
                    if transport:
                        row["transport_failed_calls"] += 1
                    elif raised and type_name not in _TIMEOUT_EXCEPTIONS:
                        row["unclassified_failed_calls"] += 1
                        names = row["unclassified_exception_types"]
                        name = exception or "<unknown>"
                        names[name] = names.get(name, 0) + 1
                    elif raised or stats.get("success") is False:
                        row["other_failed_calls"] += 1
            current = following
    return readable


def _read_log(path, steps):
    """Count terminal messages; preserve unmatched years as an unknown step."""
    by_step = {}
    step = None
    with path.open("rb") as source:
        for number, line in enumerate(source, 1):
            try:
                text = line.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"{path}: line {number}: unreadable log text: {exc}") from exc
            marker = _LOG_REGEX["step_marker"].search(text)
            if marker:
                step = int(marker.group(1))
                _step(steps, step)
            hits = [name for name in ("give_up", "transport_notice", "other_error")
                    if _LOG_REGEX[name].search(text)]
            if hits:
                counts = by_step.setdefault(step, dict.fromkeys(("give_up", "transport_notice", "other_error"), 0))
                for name in hits:
                    counts[name] += 1
    evidence = []
    for step, counts in by_step.items():
        pattern = "give_up" if counts["give_up"] else "transport_notice"
        row = _step(steps, step)
        row["log_transport_failures"] += counts[pattern]
        row["log_other_failures"] += counts["other_error"]
        evidence.append({
            "source": str(path), "step": step, "count_pattern": pattern,
            "transport_failures": counts[pattern], "other_failures": counts["other_error"],
        })
    return evidence, sum(c["transport_notice"] for c in by_step.values())


def _context_json(path):
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"{path}: unreadable JSON: {exc}") from exc
    if not isinstance(content, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return content


def transport_report(run_dir, journal=None, logs=()):
    """Return the report dict; malformed readable sources raise ValueError.

    Explicit source paths apply to this run. Missing paths are reported as
    warnings. Log counts describe observations, not unique calls across logs.
    Only journal step_end records establish completion, including in log mode.
    """
    run_dir = Path(run_dir)
    journal_path = Path(journal) if journal is not None else run_dir / "llm_journal.jsonl"
    steps, warnings, evidence = {}, [], []
    sources = {"journal": None, "logs": [], "manifest": None, "run_integrity": None}
    used_journal = False
    notices = 0
    try:
        if journal_path.exists():
            used_journal = _read_journal(journal_path, steps, warnings)
            if used_journal:
                sources["journal"] = str(journal_path)
            else:
                warnings.append(f"{journal_path}: no readable journal records")
        elif journal is not None:
            warnings.append(f"{journal_path}: journal missing")
        for path in dict.fromkeys(Path(log) for log in logs):
            if not path.exists():
                warnings.append(f"{path}: log missing")
                continue
            log_evidence, transport_notices = _read_log(path, steps)
            evidence.extend(log_evidence)
            notices += transport_notices
            sources["logs"].append(str(path))
        manifest = {}
        manifest_path = run_dir / "reproducibility_manifest.json"
        if manifest_path.exists():
            content = _context_json(manifest_path)
            manifest = {key: content[key] for key in ("run_status", "llm_transport_stop", "resumed_from") if key in content}
            sources["manifest"] = str(manifest_path)
        audit_aborted_rows = None
        integrity_path = run_dir / "run_integrity.json"
        if integrity_path.exists():
            audit_aborted_rows = _context_json(integrity_path).get("audit_aborted_rows")
            sources["run_integrity"] = str(integrity_path)
    except OSError as exc:
        raise ValueError(f"cannot read source: {exc}") from exc
    if not used_journal and sources["logs"]:
        warnings.extend([
            "journal absent, result from log only",
            "log year/step starts do not prove an end marker; completion is unverified",
        ])
        for row in steps.values():
            row["transport_failed_calls"] = row["log_transport_failures"]
            row["other_failed_calls"] = row["log_other_failures"]
    if sources["logs"]:
        warnings.append("log observations are not added to journal calls; multiple logs may overlap")
        if any(item["count_pattern"] == "transport_notice" and item["transport_failures"] for item in evidence):
            warnings.append("a step without safeguard give-ups uses transport notices as fallback evidence")
    rows = sorted(steps.values(), key=lambda row: (row["step"] is None, row["step"] or 0))
    totals = {key: sum(row[key] for row in rows) for key in (
        "calls", "transport_failed_calls", "other_failed_calls", "unclassified_failed_calls",
        "log_transport_failures", "log_other_failures",
    )}
    totals["unclassified_exception_types"] = {}
    for row in rows:
        for name, count in row["unclassified_exception_types"].items():
            names = totals["unclassified_exception_types"]
            names[name] = names.get(name, 0) + count
    if used_journal and not totals["calls"]:
        warnings.append("journal has no calls")
    if totals["other_failed_calls"]:
        warnings.append(f"other_failed_calls={totals['other_failed_calls']}")
    failed = [row for row in rows if row["transport_failed_calls"] or row["unclassified_failed_calls"] or row["log_transport_failures"]]
    if not used_journal and not sources["logs"]:
        code, status = 2, "NO_SOURCES"
    elif any(row["has_step_end"] for row in failed):
        code, status = 3, "COMPLETED_STEP_FAILURE"
    elif failed:
        code, status = 4, "INCOMPLETE_STEP_FAILURE"
    elif used_journal and not totals["calls"]:
        code, status = 2, "NO_CALLS"
    else:
        code, status = 0, "OK"
    return {
        "run_dir": str(run_dir), "exit_code": code, "status": status,
        "sources": sources, "steps": rows, "totals": totals,
        "counts_source": "journal" if used_journal else "logs" if sources["logs"] else None,
        "log_patterns": dict(_LOG_PATTERNS) if sources["logs"] else {},
        "log_failures_by_step": evidence, "log_notices": {"transport": notices},
        "audit_aborted_rows": audit_aborted_rows, "manifest": manifest, "warnings": warnings,
    }


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _print_report(report, all_steps=False):
    if "error" in report:
        print(f"{report['status']} | exit={report['exit_code']} | {report['run_dir']}")
        print(f"  ERROR: {report['error']}")
        return
    totals = report["totals"]
    print(f"{report['status']} | exit={report['exit_code']} | {report['run_dir']} | "
          f"counts_source={report['counts_source']} calls={totals['calls']} "
          f"transport_failed_calls={totals['transport_failed_calls']} other_failed_calls={totals['other_failed_calls']} "
          f"unclassified_failed_calls={totals['unclassified_failed_calls']} "
          f"audit_aborted_rows={report['audit_aborted_rows']}")
    print(f"  sources={json.dumps(report['sources'], sort_keys=True)}")
    for row in report["steps"]:
        if not all_steps and row["has_step_end"] and not any(row[key] for key in (
            "transport_failed_calls", "unclassified_failed_calls", "other_failed_calls",
            "log_transport_failures", "log_other_failures",
        )):
            continue
        print(f"  step={row['step']} transport_failed_calls={row['transport_failed_calls']} "
              f"other_failed_calls={row['other_failed_calls']} unclassified_failed_calls={row['unclassified_failed_calls']} "
              f"has_step_end={row['has_step_end']} "
              f"log_transport_failures={row['log_transport_failures']} log_other_failures={row['log_other_failures']}")
        if row["unclassified_failed_calls"]:
            print(f"    unclassified_exception_types={json.dumps(row['unclassified_exception_types'], sort_keys=True)}")
    if report["sources"]["logs"]:
        print(f"  log_patterns={json.dumps(report['log_patterns'], sort_keys=True)}")
        print(f"  log_transport_failures={totals['log_transport_failures']} "
              f"log_other_failures={totals['log_other_failures']} transport_notices={report['log_notices']['transport']}")
    if report["manifest"]:
        print(f"  manifest={json.dumps(report['manifest'], sort_keys=True)}")
    for warning in report["warnings"]:
        print(f"  WARNING: {warning}")


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--journal", type=Path, help="use this journal instead of the default for each run")
    parser.add_argument("--log", nargs="+", action="extend", type=Path, default=[], help="log files for each run; repeatable")
    parser.add_argument("--json", action="store_true", help="print reports and summary as JSON")
    parser.add_argument("--all-steps", action="store_true", help="print every step in the text report")
    try:
        args = parser.parse_args(argv)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    reports = []
    for run_dir in args.run_dirs:
        try:
            reports.append(transport_report(run_dir, journal=args.journal, logs=args.log))
        except ValueError as exc:
            reports.append({"run_dir": str(run_dir), "status": "ERROR", "exit_code": 1, "error": str(exc)})
    counts = {str(code): sum(report["exit_code"] == code for report in reports) for code in range(5)}
    code = next(code for code in (3, 1, 2, 4, 0) if counts[str(code)])
    failures = len(reports) - counts["0"]
    summary = {"runs": len(reports), "failures": failures, "exit_code_counts": counts, "exit_code": code}
    if args.json:
        print(json.dumps({"runs": reports, "summary": summary}, indent=2))
    else:
        for report in reports:
            _print_report(report, all_steps=args.all_steps)
        code_counts = " ".join(f"exit_{value}_runs={counts[str(value)]}" for value in range(5))
        print(f"=== {failures} failure(s) over {len(reports)} run(s); {code_counts}; exit={code} ===")
    return code


if __name__ == "__main__":
    sys.exit(main())
