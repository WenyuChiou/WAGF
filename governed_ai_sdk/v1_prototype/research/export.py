"""Export traces for statistical analysis (R, Python, Stata)."""
from typing import List, Dict, Any
import json


def _trace_to_research_dict(trace: Any) -> Dict[str, Any]:
    """
    Convert a GovernanceTrace or ResearchTrace to flat dict for export.

    Handles nested structures by flattening with underscores.
    """
    result = {
        "trace_id": getattr(trace, "trace_id", None),
        "timestamp": str(getattr(trace, "timestamp", "")),
        "valid": getattr(trace, "valid", None),
        "decision": getattr(trace, "decision", None),
        "blocked_by": getattr(trace, "blocked_by", None),
    }

    if hasattr(trace, "domain"):
        result["domain"] = trace.domain
    if hasattr(trace, "research_phase"):
        result["research_phase"] = trace.research_phase
    if hasattr(trace, "treatment_group"):
        result["treatment_group"] = trace.treatment_group
    if hasattr(trace, "effect_size"):
        result["effect_size"] = trace.effect_size
    if hasattr(trace, "baseline_surprise"):
        result["baseline_surprise"] = trace.baseline_surprise

    delta_state = getattr(trace, "delta_state", None)
    if delta_state and isinstance(delta_state, dict):
        for k, v in delta_state.items():
            result[f"delta_{k}"] = v

    cf = getattr(trace, "counterfactual", None)
    if cf:
        result["cf_feasibility"] = getattr(cf, "feasibility_score", None)
        result["cf_strategy"] = str(getattr(cf, "strategy_used", ""))

    return result


def export_traces_to_csv(
    traces: List[Any],
    path: str,
    include_headers: bool = True
) -> None:
    """
    Export traces for R/Python statistical analysis.

    Args:
        traces: List of GovernanceTrace or ResearchTrace objects
        path: Output CSV file path
        include_headers: Whether to include column headers
    """
    if not traces:
        return

    rows = [_trace_to_research_dict(t) for t in traces]

    all_keys = set()
    for row in rows:
        all_keys.update(row.keys())
    all_keys = sorted(all_keys)

    with open(path, "w", newline="", encoding="utf-8") as f:
        if include_headers:
            f.write(",".join(all_keys) + "\n")

        for row in rows:
            values = []
            for key in all_keys:
                val = row.get(key, "")
                if val is None:
                    val = ""
                elif isinstance(val, bool):
                    val = "1" if val else "0"
                elif isinstance(val, (int, float)):
                    val = str(val)
                else:
                    val = str(val).replace('"', '""')
                    if "," in val or '"' in val or "\n" in val:
                        val = f'"{val}"'
                values.append(val)
            f.write(",".join(values) + "\n")


def export_to_stata(
    traces: List[Any],
    path: str
) -> None:
    """
    Export for Stata analysis (.dta format).

    Requires pandas with pyreadstat installed.
    Falls back to CSV if not available.

    Args:
        traces: List of trace objects
        path: Output .dta file path
    """
    try:
        import pandas as pd
        rows = [_trace_to_research_dict(t) for t in traces]
        df = pd.DataFrame(rows)
        df.to_stata(path, write_index=False)
    except ImportError:
        csv_path = path.replace(".dta", ".csv")
        export_traces_to_csv(traces, csv_path)
        raise ImportError(
            f"pandas with pyreadstat required for Stata export. "
            f"Saved as CSV instead: {csv_path}"
        )


def export_to_json(
    traces: List[Any],
    path: str,
    indent: int = 2
) -> None:
    """
    Export traces as JSON (preserves full structure).

    Args:
        traces: List of trace objects
        path: Output JSON file path
        indent: JSON indentation level
    """
    rows = [_trace_to_research_dict(t) for t in traces]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=indent, default=str)


def export_summary_stats(
    traces: List[Any],
    path: str
) -> Dict[str, Any]:
    """
    Generate and export summary statistics.

    Args:
        traces: List of trace objects
        path: Output JSON file path

    Returns:
        Summary statistics dictionary
    """
    if not traces:
        return {}

    rows = [_trace_to_research_dict(t) for t in traces]

    total = len(rows)
    valid_count = sum(1 for r in rows if r.get("valid"))
    blocked_count = total - valid_count

    by_treatment = {}
    for row in rows:
        group = row.get("treatment_group", "unknown")
        if group not in by_treatment:
            by_treatment[group] = {"total": 0, "valid": 0, "blocked": 0}
        by_treatment[group]["total"] += 1
        if row.get("valid"):
            by_treatment[group]["valid"] += 1
        else:
            by_treatment[group]["blocked"] += 1

    stats = {
        "total_traces": total,
        "valid_count": valid_count,
        "blocked_count": blocked_count,
        "valid_rate": valid_count / total if total > 0 else 0,
        "by_treatment_group": by_treatment,
    }

    with open(path, "w") as f:
        json.dump(stats, f, indent=2)

    return stats
