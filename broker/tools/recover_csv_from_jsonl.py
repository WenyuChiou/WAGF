"""Rebuild *_governance_audit.csv from raw/*_traces.jsonl after a crash.

Background (Phase 6G, 2026-05-15): the live audit writer streams traces
into JSONL per step but only emits the wide CSV at experiment finalize().
A process that crashes mid-run leaves the JSONL intact but the CSV
absent — the canonical 2026-05-13/14 14-hour-data-loss failure mode.

Usage:
    python -m broker.tools.recover_csv_from_jsonl <output_dir>

Where <output_dir> is the experiment directory (e.g.,
examples/irrigation_abm/results/production_v21_42yr_gemma4_e4b_seed46/).
The script reads every raw/<agent_type>_traces.jsonl, converts each line
back to a trace dict, and emits <agent_type>_governance_audit.csv at the
same column schema as a live finalize() would have produced.

The recovered CSV will carry JSONL's truncated raw_output (>500 chars
becomes "...[truncated]"), so it is byte-identical to a finalize() CSV
in every column EXCEPT raw_output. Analysis pipelines that don't read
raw_output (the common case) see no difference.

Exit status:
    0 — recovery succeeded for at least one file
    1 — no JSONL inputs found
    2 — IOError on input or output
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from broker.components.analytics.audit import (
    trace_to_csv_row,
    compute_csv_fieldnames,
)


def _read_jsonl_safely_with_metadata(
    path: Path,
) -> Tuple[List[Dict[str, Any]], int, Optional[Dict[str, Any]]]:
    """Read JSONL line-by-line, tolerating a truncated final line.

    Returns (parsed traces, skipped_line_count, metadata). Skipped lines are
    the last-line-incomplete case (mid-write crash leaves a partial JSON
    object). Mid-file malformed lines also get skipped with a warning.
    """
    traces: List[Dict[str, Any]] = []
    skipped = 0
    metadata: Optional[Dict[str, Any]] = None
    seen_json_record = False
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not seen_json_record:
                seen_json_record = True
                # Only the literal first record, and only if it is a proper
                # W2 metadata header (dict whose _metadata carries
                # audit_schema_version), is treated as metadata. A real
                # trace that happens to contain a _metadata key falls
                # through to traces (code-review W2 hardening).
                meta = record.get("_metadata") if isinstance(record, dict) else None
                if isinstance(meta, dict) and "audit_schema_version" in meta:
                    metadata = meta
                    continue
            if not isinstance(record, dict):
                # valid JSON but not a trace object (bare array/number/string)
                skipped += 1
                continue
            traces.append(record)
    return traces, skipped, metadata


def _read_jsonl_safely(path: Path) -> Tuple[List[Dict[str, Any]], int]:
    """Read JSONL traces, excluding a leading W2 _metadata record if present."""
    traces, skipped, _metadata = _read_jsonl_safely_with_metadata(path)
    return traces, skipped


def _schema_report(metadata: Optional[Dict[str, Any]]) -> str:
    if metadata is None:
        return "  schema: (no _metadata - pre-W2 trace)"
    return (
        "  schema: "
        f"framework={metadata.get('framework_version', 'unknown')} "
        f"audit_schema={metadata.get('audit_schema_version', 'unknown')} "
        f"git={metadata.get('git_commit_short', 'unknown')}"
    )


def recover_csv(output_dir: Path) -> Dict[str, Any]:
    """Recover all CSVs from raw/*_traces.jsonl in output_dir.

    Returns a dict mapping agent_type -> {csv_path, rows_recovered,
    lines_skipped}.
    """
    raw_dir = output_dir / "raw"
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"raw/ subdir not found under {output_dir}")

    summary: Dict[str, Any] = {}
    jsonl_files = sorted(raw_dir.glob("*_traces.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(f"No *_traces.jsonl files in {raw_dir}")

    for jsonl_path in jsonl_files:
        agent_type = jsonl_path.stem.removesuffix("_traces")
        traces, skipped, metadata = _read_jsonl_safely_with_metadata(jsonl_path)
        if not traces:
            summary[agent_type] = {
                "csv_path": None,
                "rows_recovered": 0,
                "lines_skipped": skipped,
                "metadata": metadata,
            }
            continue

        flat_rows = [trace_to_csv_row(t) for t in traces]
        audit_priority = None
        if "_audit_priority" in traces[0] and isinstance(traces[0]["_audit_priority"], list):
            audit_priority = traces[0]["_audit_priority"]
        fieldnames = compute_csv_fieldnames(flat_rows, audit_priority=audit_priority)

        csv_path = output_dir / f"{agent_type}_governance_audit.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames,
                extrasaction="ignore",
                quoting=csv.QUOTE_ALL,
            )
            writer.writeheader()
            writer.writerows(flat_rows)

        summary[agent_type] = {
            "csv_path": str(csv_path),
            "rows_recovered": len(flat_rows),
            "lines_skipped": skipped,
            "metadata": metadata,
        }
    return summary


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="recover_csv_from_jsonl",
        description="Rebuild governance audit CSVs from raw JSONL traces.",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Experiment output directory containing raw/*_traces.jsonl",
    )
    args = parser.parse_args(argv)
    output_dir: Path = args.output_dir.resolve()

    if not output_dir.is_dir():
        print(f"ERROR: {output_dir} is not a directory", file=sys.stderr)
        return 2

    try:
        summary = recover_csv(output_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (OSError, IOError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Recovered CSVs from {output_dir}:")
    total_rows = 0
    for agent_type, info in summary.items():
        if info["csv_path"] is None:
            print(f"  [empty] {agent_type}: 0 rows ({info['lines_skipped']} lines skipped)")
            print(_schema_report(info.get("metadata")))
            continue
        total_rows += info["rows_recovered"]
        print(
            f"  [OK] {agent_type}: {info['rows_recovered']:,} rows "
            f"({info['lines_skipped']} lines skipped) -> {Path(info['csv_path']).name}"
        )
        print(_schema_report(info.get("metadata")))
    print(f"Total rows recovered: {total_rows:,}")
    return 0 if total_rows > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
