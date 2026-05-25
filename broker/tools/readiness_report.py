"""Phase 6O-C — Generic readiness reporter CLI.

Domain-agnostic post-experiment audit. Reads an existing results dir
(produced by any WAGF run, regardless of domain), computes a fixed
set of metrics, compares them to a named profile's thresholds, prints
a console summary, optionally writes ``readiness_report.json`` next
to the audit data, and exits 0 (pass) / 1 (any threshold failed) /
2 (CLI error / inputs missing).

Usage::

    python -m broker.tools.readiness_report \\
        --results <dir> \\
        --profile functional

This module is a **read-only orchestrator** — it never mutates the
audit data, never instantiates validators, never loads broker
runtime. It depends on:

- `<dir>/audit_summary.json` (written by GenericAuditWriter.finalize)
- `<dir>/*_governance_audit.csv` (the audit CSV)
- `<dir>/raw/*.jsonl` (optional — terminal-taxonomy classification
  degrades gracefully to `unknown_terminal` when JSONL is absent)

Phase 6O-C-1 scope: functional / behavioral / stress profiles +
console + JSON output. Skill orchestration (call `wagf-quickstart`,
`abm-reproducibility-checker`, `llm-agent-audit-trace-analyzer` from
the CLI) deferred to 6O-C-2.

Production profile not shipped — persona alignment undefined per
user decision at `.ai/2026/05/25/phase_6o_gap_matrix.md`.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from broker.components.analytics.terminal_taxonomy import (
    TERMINAL_CATEGORIES,
    classify_terminal,
)
from broker.components.validation.readiness_profile import (
    PROFILE_NAMES,
    ReadinessProfile,
    load_readiness_profile,
)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ReadinessMetrics:
    """Numeric metrics extracted from a results directory.

    Every metric is optional — when an input file is missing the
    relevant field stays `None` and the threshold check on it is
    skipped (caller treats as "not enforced").
    """

    total_traces: Optional[int] = None
    approved_count: Optional[int] = None
    # 6O-C-1 round-1 rename: was `parse_success_rate`, but the computation
    # was always `approved / total`. The actual parse-quality signal lives
    # in the `parser_failure` terminal-taxonomy bucket. Use that for a
    # separate `parse_success_rate` metric in 6O-C-2.
    approval_rate: Optional[float] = None
    format_retry_rate: Optional[float] = None
    terminal_rate: Optional[float] = None
    terminal_taxonomy: Dict[str, int] = field(default_factory=dict)
    action_coverage: Optional[int] = None
    distinct_actions: List[str] = field(default_factory=list)
    validator_firing_diversity: Optional[int] = None
    dead_validators: List[str] = field(default_factory=list)


@dataclass
class ThresholdCheck:
    """One pass/fail check derived from comparing metric to threshold."""

    metric_name: str
    threshold: Any  # numeric bound or bool flag
    observed: Any
    passed: bool
    detail: str


@dataclass
class ReadinessReport:
    """Top-level result of `compute_readiness_report`."""

    profile_name: str
    profile_description: str
    results_dir: str
    metrics: ReadinessMetrics
    checks: List[ThresholdCheck]
    overall_passed: bool

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "profile_name": self.profile_name,
            "profile_description": self.profile_description,
            "results_dir": self.results_dir,
            "metrics": asdict(self.metrics),
            "checks": [asdict(c) for c in self.checks],
            "overall_passed": self.overall_passed,
        }


# ---------------------------------------------------------------------------
# I/O helpers (graceful degradation)
# ---------------------------------------------------------------------------


def _read_audit_summary(results_dir: Path) -> Dict[str, Any]:
    """Return audit_summary.json contents or empty dict if missing."""
    path = results_dir / "audit_summary.json"
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _find_audit_csv(results_dir: Path) -> Optional[Path]:
    """Return the FIRST *_governance_audit.csv found in the dir, or None."""
    for path in sorted(results_dir.glob("*_governance_audit.csv")):
        return path
    return None


def _find_jsonl_traces(results_dir: Path) -> List[Path]:
    """Return sorted list of raw JSONL trace files, or empty list."""
    raw_dir = results_dir / "raw"
    if not raw_dir.is_dir():
        return []
    return sorted(raw_dir.glob("*.jsonl"))


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------


def _compute_metrics(results_dir: Path) -> ReadinessMetrics:
    """Read the results dir and compute every metric defined in
    `ReadinessMetrics`. Missing inputs leave fields `None`.
    """
    metrics = ReadinessMetrics()

    summary = _read_audit_summary(results_dir)
    total = summary.get("total_traces")
    if isinstance(total, int) and total > 0:
        metrics.total_traces = total

    # Approved + parse-success from audit CSV
    csv_path = _find_audit_csv(results_dir)
    if csv_path is not None:
        try:
            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except OSError:
            rows = []

        if rows:
            approved = sum(
                1 for r in rows if str(r.get("status") or "").upper() == "APPROVED"
            )
            metrics.approved_count = approved
            if metrics.total_traces is None:
                metrics.total_traces = len(rows)

            if metrics.total_traces and metrics.total_traces > 0:
                metrics.approval_rate = round(
                    approved / metrics.total_traces, 4
                )

            distinct_skills = sorted(
                {
                    str(r["final_skill"])
                    for r in rows
                    if r.get("final_skill")
                }
            )
            metrics.distinct_actions = distinct_skills
            metrics.action_coverage = len(distinct_skills)

    # format_retry_rate
    total_fr = summary.get("total_format_retries", 0)
    if metrics.total_traces and metrics.total_traces > 0:
        metrics.format_retry_rate = round(
            max(0.0, float(total_fr)) / metrics.total_traces, 4
        )

    # Validator firing diversity + dead validators
    health = summary.get("validator_health")
    if isinstance(health, dict):
        firing = [rid for rid, stat in health.items() if _firing(stat)]
        dead = [rid for rid, stat in health.items() if _is_dead(stat)]
        metrics.validator_firing_diversity = len(firing)
        metrics.dead_validators = sorted(dead)

    # Terminal taxonomy. CSV rows give the flat `status` / `retry_count` /
    # `format_retries` shape the classifier expects; JSONL gives the
    # optional `validation_issues` metadata that enables expected_hard_block
    # / recoverable_retry_failed classification. Merge by (agent_id, year)
    # when both available, fall back to CSV-only otherwise.
    metrics.terminal_taxonomy = dict.fromkeys(TERMINAL_CATEGORIES, 0)
    if csv_path is not None and rows:
        # Build a (agent_id, year) -> validation_issues lookup from JSONL.
        # C1 fix (6O-C-1 round-1): duplicate keys (multi-decision-per-year
        # MA agents) get list-merged instead of last-write-wins overwrite.
        validation_issues_by_key: Dict[Tuple[str, str], List[Any]] = {}
        for jsonl in _find_jsonl_traces(results_dir):
            try:
                with jsonl.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(obj, dict) or "_metadata" in obj:
                            continue
                        key = (
                            str(obj.get("agent_id", "")),
                            str(obj.get("year", obj.get("step_id", ""))),
                        )
                        issues = obj.get("validation_issues")
                        if isinstance(issues, list):
                            validation_issues_by_key.setdefault(key, []).extend(issues)
            except OSError:
                continue

        counter = Counter()
        for row in rows:
            key = (
                str(row.get("agent_id", "")),
                str(row.get("year", row.get("step_id", ""))),
            )
            # Build the classifier input — CSV gives status/retry_count/etc.,
            # JSONL contributes validation_issues if matched.
            trace = dict(row)
            issues = validation_issues_by_key.get(key)
            if issues is not None:
                trace["validation_issues"] = issues
            counter[classify_terminal(trace)] += 1

        for cat, n in counter.items():
            metrics.terminal_taxonomy[cat] = n

        non_terminal = (
            metrics.terminal_taxonomy.get("approved", 0)
            + metrics.terminal_taxonomy.get("retry_recovered", 0)
        )
        total_classified = sum(counter.values())
        if total_classified > 0:
            metrics.terminal_rate = round(
                (total_classified - non_terminal) / total_classified, 4
            )

    return metrics


def _firing(stat: Any) -> bool:
    """Validator-health entry counts as "firing" if it logged at least one
    hit (errors > 0 or warnings > 0).
    """
    if not isinstance(stat, dict):
        return False
    return any(
        int(stat.get(key, 0) or 0) > 0
        for key in ("error_count", "warn_count", "hit_count")
    )


def _is_dead(stat: Any) -> bool:
    """Validator-health entry counts as "dead" if it has zero fires AND
    is explicitly listed as registered (registered_count > 0 or just
    present in validator_health).
    """
    return not _firing(stat)


# ---------------------------------------------------------------------------
# Threshold evaluation
# ---------------------------------------------------------------------------


def _evaluate_profile(
    metrics: ReadinessMetrics,
    profile: ReadinessProfile,
) -> List[ThresholdCheck]:
    """Compare metrics to each profile threshold, return per-metric checks."""
    checks: List[ThresholdCheck] = []
    thr = profile.thresholds

    if thr.min_approval_rate is not None:
        observed = metrics.approval_rate
        passed = observed is not None and observed >= thr.min_approval_rate
        checks.append(
            ThresholdCheck(
                metric_name="approval_rate",
                threshold=thr.min_approval_rate,
                observed=observed,
                passed=passed,
                detail=_explain("approval_rate", observed, thr.min_approval_rate, "min"),
            )
        )

    if thr.max_format_retry_rate is not None:
        observed = metrics.format_retry_rate
        passed = observed is None or observed <= thr.max_format_retry_rate
        checks.append(
            ThresholdCheck(
                metric_name="format_retry_rate",
                threshold=thr.max_format_retry_rate,
                observed=observed,
                passed=passed,
                detail=_explain("format_retry_rate", observed, thr.max_format_retry_rate, "max"),
            )
        )

    if thr.max_terminal_rate is not None:
        observed = metrics.terminal_rate
        passed = observed is None or observed <= thr.max_terminal_rate
        checks.append(
            ThresholdCheck(
                metric_name="terminal_rate",
                threshold=thr.max_terminal_rate,
                observed=observed,
                passed=passed,
                detail=_explain("terminal_rate", observed, thr.max_terminal_rate, "max"),
            )
        )

    if thr.min_action_coverage is not None:
        observed = metrics.action_coverage
        passed = observed is not None and observed >= thr.min_action_coverage
        checks.append(
            ThresholdCheck(
                metric_name="action_coverage",
                threshold=thr.min_action_coverage,
                observed=observed,
                passed=passed,
                detail=_explain("action_coverage", observed, thr.min_action_coverage, "min"),
            )
        )

    if thr.min_validator_firing_diversity is not None:
        observed = metrics.validator_firing_diversity
        passed = observed is not None and observed >= thr.min_validator_firing_diversity
        checks.append(
            ThresholdCheck(
                metric_name="validator_firing_diversity",
                threshold=thr.min_validator_firing_diversity,
                observed=observed,
                passed=passed,
                detail=_explain(
                    "validator_firing_diversity",
                    observed,
                    thr.min_validator_firing_diversity,
                    "min",
                ),
            )
        )

    # W4 fix (6O-C-1 round-1): required_metrics declared in the profile
    # MUST be present in the report; FAIL if any is None / missing.
    for metric_name in profile.required_metrics:
        observed: Any = getattr(metrics, metric_name, None)
        is_dict = isinstance(observed, dict)
        present = bool(observed) if not is_dict else any(v for v in observed.values())
        checks.append(
            ThresholdCheck(
                metric_name=f"required:{metric_name}",
                threshold="present",
                observed=observed,
                passed=present,
                detail=(
                    f"required metric {metric_name!r} present"
                    if present
                    else f"required metric {metric_name!r} missing or empty"
                ),
            )
        )

    if thr.max_dead_validators is not None:
        dead_count = len(metrics.dead_validators)
        passed = dead_count <= thr.max_dead_validators
        checks.append(
            ThresholdCheck(
                metric_name="dead_validators",
                threshold=thr.max_dead_validators,
                observed=dead_count,
                passed=passed,
                detail=(
                    f"dead validators: {dead_count} <= {thr.max_dead_validators}"
                    if passed
                    else f"{dead_count} dead validator(s) > {thr.max_dead_validators} allowed: {', '.join(metrics.dead_validators[:5])}"
                ),
            )
        )

    return checks


def _explain(name: str, observed: Any, threshold: Any, direction: str) -> str:
    if observed is None:
        return f"{name}: no data (degraded)"
    op = ">=" if direction == "min" else "<="
    return f"{name}: observed={observed} {op} threshold={threshold}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_readiness_report(
    results_dir: Path,
    profile: ReadinessProfile,
) -> ReadinessReport:
    """Compute a `ReadinessReport` for a results directory + named profile."""
    metrics = _compute_metrics(results_dir)
    checks = _evaluate_profile(metrics, profile)
    overall = all(c.passed for c in checks) if checks else True
    return ReadinessReport(
        profile_name=profile.name,
        profile_description=profile.description.strip(),
        results_dir=str(results_dir),
        metrics=metrics,
        checks=checks,
        overall_passed=overall,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_console(report: ReadinessReport) -> str:
    """Pretty-print the report for human terminal viewing."""
    lines = [
        f"=== Readiness report  profile={report.profile_name}  dir={report.results_dir} ===",
        report.profile_description,
        "",
        "Metrics",
    ]
    m = report.metrics
    lines.append(f"  total_traces                : {m.total_traces}")
    lines.append(f"  approved_count              : {m.approved_count}")
    lines.append(f"  approval_rate               : {m.approval_rate}")
    lines.append(f"  format_retry_rate           : {m.format_retry_rate}")
    lines.append(f"  terminal_rate               : {m.terminal_rate}")
    lines.append(f"  action_coverage             : {m.action_coverage}  {m.distinct_actions}")
    lines.append(f"  validator_firing_diversity  : {m.validator_firing_diversity}")
    lines.append(f"  dead_validators             : {len(m.dead_validators)}")
    if m.terminal_taxonomy:
        nonzero = {k: v for k, v in m.terminal_taxonomy.items() if v > 0}
        lines.append(f"  terminal_taxonomy           : {nonzero}")

    lines.append("")
    lines.append("Threshold checks")
    if not report.checks:
        lines.append("  (no thresholds configured for this profile)")
    for c in report.checks:
        mark = "PASS" if c.passed else "FAIL"
        lines.append(f"  [{mark}] {c.detail}")

    lines.append("")
    lines.append(f"Overall: {'PASS' if report.overall_passed else 'FAIL'}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="readiness_report",
        description=(
            "Generic, domain-agnostic readiness reporter for a WAGF "
            "experiment results directory."
        ),
    )
    parser.add_argument(
        "--results",
        required=True,
        type=Path,
        help="Path to results directory (containing audit_summary.json + audit CSV + raw/*.jsonl).",
    )
    parser.add_argument(
        "--profile",
        required=True,
        choices=PROFILE_NAMES,
        help="Profile name.",
    )
    parser.add_argument(
        "--profile-yaml",
        type=Path,
        default=None,
        help="Override path to profile thresholds YAML.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help=(
            "Optional path for JSON report. Default writes "
            "<results>/readiness_report.json. Pass --no-json to skip."
        ),
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip writing the JSON report file.",
    )
    args = parser.parse_args(argv)

    if not args.results.is_dir():
        print(f"ERROR: results dir not found: {args.results}", file=sys.stderr)
        return 2

    try:
        profile = load_readiness_profile(
            args.profile, yaml_path=args.profile_yaml
        )
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    report = compute_readiness_report(args.results, profile)
    print(_format_console(report))

    if not args.no_json:
        json_path = args.json_output or (args.results / "readiness_report.json")
        try:
            with json_path.open("w", encoding="utf-8") as f:
                json.dump(report.to_json_dict(), f, indent=2)
            print(f"\nJSON report: {json_path}")
        except OSError as exc:
            print(f"WARN: could not write JSON report: {exc}", file=sys.stderr)

    return 0 if report.overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
