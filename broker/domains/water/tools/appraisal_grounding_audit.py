"""Deterministic post-hoc audit for appraisal grounding.

This tool makes no LLM calls and is read-only over existing experiment
trace JSONL inputs. Version 1 audits WSA_LABEL only; ACA_LABEL is out of
scope because objective environment signals do not directly imply adaptive
capacity.

The drought_index field is optional. When present and numeric it can apply
the configured drought bump; when absent or non-numeric, only that optional
bump is skipped and tier-based scoring still proceeds.

Known limitation: the audit is directional rather than point-precise. It
catches qualitative inversions, not a self-consistent uniform down-shift
where direction still tracks; that residual is the other approach's job.

Usage:
    python -m broker.domains.water.tools.appraisal_grounding_audit <output_dir> --domain irrigation
"""
from __future__ import annotations

import argparse
import csv
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from broker.domains.registry import DomainPackRegistry
from broker.domains.water.thinking_checks import (
    WATER_FRAMEWORK_LABEL_ORDERS,
    WATER_LABEL_MAPPINGS,
)
from broker.tools.recover_csv_from_jsonl import (
    _read_jsonl_safely_with_metadata,
    _schema_report,
)


CSV_FIELDNAMES = [
    "step_id",
    "agent_id",
    "year",
    "model",
    "agent_type",
    "self_wsa",
    "env_wsa",
    "shortage_tier",
    "drought_index",
    "drift",
    "label_inconsistent",
]

SUMMARY_FIELDNAMES = [
    "agent_type",
    "model",
    "scored",
    "skipped",
    "fidelity",
    "mean_drift",
    "pct_label_inconsistent",
]

FRAMEWORK = "dual_appraisal"
LABEL_ORDER = WATER_FRAMEWORK_LABEL_ORDERS[FRAMEWORK]
LABEL_NORMALIZATION = WATER_LABEL_MAPPINGS[FRAMEWORK]


def _normalize_wsa(label: Any) -> Optional[str]:
    if label is None:
        return None
    key = str(label).strip().upper()
    if not key:
        return None
    if key in LABEL_ORDER:
        return key
    normalized = LABEL_NORMALIZATION.get(key)
    if normalized in LABEL_ORDER:
        return normalized
    return None


def _level(label: str) -> int:
    return LABEL_ORDER[label]


def _label_at_level(level: int) -> str:
    for label, candidate_level in LABEL_ORDER.items():
        if candidate_level == level:
            return label
    raise ValueError(f"No WSA label for level {level}")


def _resolve_domain_pack(domain: str) -> Any:
    pack = DomainPackRegistry.get(domain)
    if pack is not None:
        return pack

    # Import the explicitly requested example package so its registration
    # side effect can run. The mapping still comes only from DomainPackRegistry.
    for module_name in (f"examples.{domain}", f"examples.{domain}_abm"):
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                raise
            continue
        pack = DomainPackRegistry.get(domain)
        if pack is not None:
            return pack
    return None


def _expected_env_wsa(
    mapping: Dict[str, Any],
    shortage_tier: Any,
    drought_index: Any,
) -> Optional[str]:
    """Return env-implied WSA from shortage tier plus optional drought bump.

    The base shortage-tier mapping is required. Drought index is optional:
    missing, None, or non-numeric values disable only the bump and do not
    make an otherwise mapped record unscoreable.
    """
    try:
        tier = int(shortage_tier)
    except (TypeError, ValueError):
        return None

    tier_map = mapping.get("shortage_tier_to_wsa")
    if not isinstance(tier_map, dict) or not tier_map:
        return None

    numeric_keys = sorted(key for key in tier_map if isinstance(key, int))
    if not numeric_keys:
        return None

    mapped_tier = tier
    if mapped_tier > numeric_keys[-1]:
        mapped_tier = numeric_keys[-1]
    if mapped_tier not in tier_map:
        return None

    env_wsa = _normalize_wsa(tier_map[mapped_tier])
    if env_wsa is None:
        return None

    threshold = mapping.get("drought_index_bump_threshold")
    if threshold is not None:
        try:
            bump_threshold = float(threshold)
        except (TypeError, ValueError):
            return env_wsa
        try:
            drought = float(drought_index)
        except (TypeError, ValueError):
            return env_wsa
        if drought >= bump_threshold:
            bumped_level = min(max(LABEL_ORDER.values()), _level(env_wsa) + 1)
            env_wsa = _label_at_level(bumped_level)

    return env_wsa


def _record_self_wsa(record: Dict[str, Any]) -> Optional[str]:
    skill_proposal = record.get("skill_proposal")
    if not isinstance(skill_proposal, dict):
        return None
    reasoning = skill_proposal.get("reasoning")
    if not isinstance(reasoning, dict):
        return None
    return _normalize_wsa(reasoning.get("WSA_LABEL"))


def _score_record(
    record: Dict[str, Any],
    agent_type: str,
    mapping: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Tuple[str, Any]]:
    model = record.get("model")
    summary_key = (agent_type, model)

    self_wsa = _record_self_wsa(record)
    if self_wsa is None:
        return None, summary_key

    state_before = record.get("state_before")
    if not isinstance(state_before, dict) or "shortage_tier" not in state_before:
        return None, summary_key

    shortage_tier = state_before.get("shortage_tier")
    environment_context = record.get("environment_context")
    drought_index = (
        environment_context.get("drought_index")
        if isinstance(environment_context, dict)
        else None
    )
    env_wsa = _expected_env_wsa(mapping, shortage_tier, drought_index)
    if env_wsa is None:
        return None, summary_key

    drift = abs(_level(self_wsa) - _level(env_wsa))
    return (
        {
            "step_id": record.get("step_id"),
            "agent_id": record.get("agent_id"),
            "year": record.get("year"),
            "model": model,
            "agent_type": agent_type,
            "self_wsa": self_wsa,
            "env_wsa": env_wsa,
            "shortage_tier": shortage_tier,
            "drought_index": drought_index,
            "drift": drift,
            "label_inconsistent": drift >= 2,
        },
        summary_key,
    )


def _empty_summary() -> Dict[str, Any]:
    return {
        "scored": 0,
        "skipped": 0,
        "drifts": [],
        "inconsistent": 0,
    }


def _build_summary_rows(
    summary: Dict[Tuple[str, Any], Dict[str, Any]]
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for (agent_type, model), info in sorted(summary.items(), key=lambda item: (item[0][0], str(item[0][1]))):
        scored = info["scored"]
        skipped = info["skipped"]
        drifts = info["drifts"]
        inconsistent = info["inconsistent"]
        if scored > 0:
            fidelity = sum(1 for drift in drifts if drift < 2) / scored
            mean_drift = sum(drifts) / scored
            pct_label_inconsistent = inconsistent / scored
        else:
            fidelity = ""
            mean_drift = ""
            pct_label_inconsistent = ""
        rows.append(
            {
                "agent_type": agent_type,
                "model": model,
                "scored": scored,
                "skipped": skipped,
                "fidelity": fidelity,
                "mean_drift": mean_drift,
                "pct_label_inconsistent": pct_label_inconsistent,
            }
        )
    return rows


def run_audit(output_dir: Path, domain: str) -> Dict[str, Any]:
    raw_dir = output_dir / "raw"
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"raw/ subdir not found under {output_dir}")

    jsonl_files = sorted(raw_dir.glob("*_traces.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(f"No *_traces.jsonl files in {raw_dir}")

    pack = _resolve_domain_pack(domain)
    if pack is None:
        raise ValueError(f"Domain '{domain}' is not registered")
    mapping_getter = getattr(pack, "appraisal_grounding_map", None)
    mapping = mapping_getter() if callable(mapping_getter) else None
    if mapping is None:
        raise ValueError(
            f"Domain '{domain}' does not provide appraisal_grounding_map()"
        )

    all_rows: List[Dict[str, Any]] = []
    summary: Dict[Tuple[str, Any], Dict[str, Any]] = {}
    file_reports: List[Dict[str, Any]] = []
    total_parse_skipped = 0
    total_record_skipped = 0

    for jsonl_path in jsonl_files:
        agent_type = jsonl_path.stem.removesuffix("_traces")
        records, parse_skipped, metadata = _read_jsonl_safely_with_metadata(jsonl_path)
        file_scored = 0
        file_record_skipped = 0

        for record in records:
            scored_row, summary_key = _score_record(record, agent_type, mapping)
            info = summary.setdefault(summary_key, _empty_summary())
            if scored_row is None:
                info["skipped"] += 1
                file_record_skipped += 1
                continue
            info["scored"] += 1
            info["drifts"].append(scored_row["drift"])
            if scored_row["label_inconsistent"]:
                info["inconsistent"] += 1
            all_rows.append(scored_row)
            file_scored += 1

        assert file_scored + file_record_skipped == len(records)
        total_parse_skipped += parse_skipped
        total_record_skipped += file_record_skipped
        file_fidelity = (
            sum(1 for row in all_rows[-file_scored:] if row["drift"] < 2) / file_scored
            if file_scored > 0
            else ""
        )
        file_reports.append(
            {
                "agent_type": agent_type,
                "scored": file_scored,
                "record_skipped": file_record_skipped,
                "parse_skipped": parse_skipped,
                "fidelity": file_fidelity,
                "metadata": metadata,
            }
        )

    if len(all_rows) == 0:
        raise ValueError("0 scoreable records (check --domain and trace schema)")

    with open(output_dir / "appraisal_grounding.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(all_rows)

    with open(output_dir / "appraisal_grounding_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDNAMES, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(_build_summary_rows(summary))

    return {
        "rows": all_rows,
        "file_reports": file_reports,
        "total_scored": len(all_rows),
        "total_record_skipped": total_record_skipped,
        "total_parse_skipped": total_parse_skipped,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="appraisal_grounding_audit",
        description="Audit self-reported WSA against env-implied expected WSA.",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Experiment output directory containing raw/*_traces.jsonl",
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="Registered domain name, e.g. irrigation.",
    )
    args = parser.parse_args(argv)
    output_dir: Path = args.output_dir.resolve()

    if not output_dir.is_dir():
        print(f"ERROR: {output_dir} is not a directory", file=sys.stderr)
        return 2

    try:
        report = run_audit(output_dir, args.domain)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (OSError, IOError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for file_report in report["file_reports"]:
        print(
            f"  [OK] {file_report['agent_type']}: "
            f"{file_report['scored']} scored, "
            f"{file_report['record_skipped']} skipped "
            f"(+{file_report['parse_skipped']} malformed lines), "
            f"fidelity={file_report['fidelity']}"
        )
        print(_schema_report(file_report.get("metadata")))
    print(
        f"Total scored: {report['total_scored']}  "
        f"Total record-skipped: {report['total_record_skipped']}  "
        f"Total malformed-lines: {report['total_parse_skipped']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
