"""Report historical recorded validator fires from JSONL traces.

Usage:
    python -m broker.tools.replay_shadow <experiment_output_dir>

This is the shadow-mode replay fallback: it aggregates rule IDs already
recorded in trace files. It does not live re-evaluate validators.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

from broker.tools.recover_csv_from_jsonl import _read_jsonl_safely_with_metadata


def _ids_from_value(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        separators = ["|", ","]
        values = [value]
        for sep in separators:
            if sep in value:
                values = value.split(sep)
                break
        return [v.strip() for v in values if v.strip()]
    if isinstance(value, dict):
        rule_ids: List[str] = []
        if value.get("rule_id"):
            rule_ids.append(str(value["rule_id"]))
        metadata = value.get("metadata")
        if isinstance(metadata, dict):
            rule_ids.extend(_ids_from_value(metadata.get("rules_hit")))
        return rule_ids
    if isinstance(value, Iterable):
        rule_ids = []
        for item in value:
            rule_ids.extend(_ids_from_value(item))
        return rule_ids
    return [str(value)]


def _recorded_rule_ids(trace: Dict[str, Any]) -> List[str]:
    rule_ids: List[str] = []
    rule_ids.extend(_ids_from_value(trace.get("validation_issues")))
    rule_ids.extend(_ids_from_value(trace.get("failed_rules")))
    metadata = trace.get("metadata")
    if isinstance(metadata, dict):
        rule_ids.extend(_ids_from_value(metadata.get("rules_hit")))
    return sorted(set(rule_ids))


def recover(output_dir: Path) -> Dict[str, Any]:
    """Aggregate recorded rule fires from raw/*_traces.jsonl."""
    output_dir = Path(output_dir)
    raw_dir = output_dir / "raw"
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"raw/ subdir not found under {output_dir}")

    jsonl_files = sorted(raw_dir.glob("*_traces.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(f"No *_traces.jsonl files in {raw_dir}")

    trace_count = 0
    skipped_lines = 0
    counts: Dict[str, int] = {}
    file_summaries: Dict[str, Dict[str, Any]] = {}

    for jsonl_path in jsonl_files:
        traces, skipped, metadata = _read_jsonl_safely_with_metadata(jsonl_path)
        skipped_lines += skipped
        file_summaries[jsonl_path.name] = {
            "trace_count": len(traces),
            "lines_skipped": skipped,
            "metadata": metadata,
        }
        for trace in traces:
            trace_count += 1
            for rule_id in _recorded_rule_ids(trace):
                counts[rule_id] = counts.get(rule_id, 0) + 1

    rules = {
        rule_id: {
            "rule_id": rule_id,
            "fire_count": count,
            "fire_rate": round(count / trace_count, 4) if trace_count else 0.0,
        }
        for rule_id, count in sorted(counts.items())
    }
    return {
        "mode": "recorded-fire-rate",
        "trace_count": trace_count,
        "skipped_lines": skipped_lines,
        "rules": rules,
        "files": file_summaries,
    }


def _print_report(summary: Dict[str, Any], output_dir: Path) -> None:
    print(f"Shadow replay fallback report for {output_dir}")
    print("mode: recorded-fire-rate (recorded trace issues only; no live re-evaluation)")
    print(f"traces: {summary['trace_count']} ({summary['skipped_lines']} lines skipped)")
    print("rule_id\tfire_count\tfire_rate")
    if not summary["rules"]:
        print("(none)\t0\t0.0")
        return
    for rule_id, info in summary["rules"].items():
        print(f"{rule_id}\t{info['fire_count']}\t{info['fire_rate']}")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="replay_shadow",
        description="Aggregate recorded validator fires from JSONL traces.",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Experiment output directory containing raw/*_traces.jsonl",
    )
    args = parser.parse_args(argv)
    output_dir = args.output_dir.resolve()

    if not output_dir.is_dir():
        print(f"ERROR: {output_dir} is not a directory", file=sys.stderr)
        return 2

    try:
        summary = recover(output_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (OSError, IOError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _print_report(summary, output_dir)
    return 0 if summary["trace_count"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
