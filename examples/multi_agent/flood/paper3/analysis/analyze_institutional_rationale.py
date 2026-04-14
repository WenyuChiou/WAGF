import argparse
import json
import os
from collections import Counter
from pathlib import Path

import pandas as pd

_PAPER3_OVERRIDE = os.environ.get("PAPER3_TRACE_DIR")
_PAPER3_OUTPUT_OVERRIDE = os.environ.get("PAPER3_OUTPUT_DIR")

CATEGORIES = {
    "crisis_response": ["crisis", "immediate", "severe", "emergency"],
    "budget_concern": ["budget", "sustainability", "afford", "cost", "limited funds"],
    "equity_concern": ["marginalized", "equity", "inequality", "disadvantaged", "access"],
    "loss_ratio_reaction": ["loss ratio", "premium", "actuarial", "losses"],
    "mitigation_reward": ["mitigation", "crs", "improvement", "community score"],
    "status_quo": ["maintain", "stable", "continue", "current level"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-dir", default=None)
    return parser.parse_args()


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    trace_dir_raw = args.trace_dir or _PAPER3_OVERRIDE
    if not trace_dir_raw:
        raise SystemExit("Missing trace dir. Use --trace-dir or PAPER3_TRACE_DIR.")
    trace_dir = Path(os.path.normpath(trace_dir_raw))
    output_dir_raw = _PAPER3_OUTPUT_OVERRIDE or str(trace_dir.parent / "analysis")
    output_dir = Path(os.path.normpath(output_dir_raw)) / "institutional_rationale"
    output_dir.mkdir(parents=True, exist_ok=True)
    return trace_dir, output_dir


def iter_records(raw_dir: Path):
    for filename in ("government_traces.jsonl", "insurance_traces.jsonl"):
        with (raw_dir / filename).open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def classify_categories(text: str) -> list[str]:
    lowered = (text or "").lower()
    return [category for category, phrases in CATEGORIES.items() if any(phrase in lowered for phrase in phrases)]


def is_adjustment(skill_name: str) -> bool:
    skill = (skill_name or "").lower()
    return not (skill.startswith("maintain") or skill == "none")


def build_outputs(trace_dir: Path, output_dir: Path) -> tuple[dict[str, pd.DataFrame], list[str]]:
    raw_dir = trace_dir / "raw"
    trajectory_rows = []
    text_rows = []
    category_rows = []
    warnings = []
    reactivity_counter = Counter()
    records_by_agent = {}

    for rec in iter_records(raw_dir):
        year = int(rec.get("year"))
        agent_id = rec.get("agent_id", "")
        records_by_agent.setdefault(agent_id, []).append(rec)
        env = rec.get("environment_context") or {}
        reasoning = ((rec.get("skill_proposal") or {}).get("reasoning") or {})
        skill = ((rec.get("approved_skill") or {}).get("skill_name")) or ((rec.get("skill_proposal") or {}).get("skill_name")) or ""
        strategy = reasoning.get("strategy", "") or ""
        rationale = reasoning.get("reasoning", "") or ""
        combined = f"{strategy}\n{rationale}".strip()

        trajectory_rows.append({
            "year": year,
            "agent_id": agent_id,
            "skill": skill,
            "subsidy_rate": env.get("subsidy_rate"),
            "crs_class": env.get("crs_class"),
            "crs_discount": env.get("crs_discount"),
            "loss_ratio": env.get("loss_ratio"),
            "premium_rate": env.get("premium_rate"),
        })
        text_rows.append({
            "year": year,
            "agent_id": agent_id,
            "skill": skill,
            "strategy": strategy,
            "reasoning": rationale,
            "strategy_len": len(strategy),
            "reasoning_len": len(rationale),
        })

        matched = classify_categories(combined)
        for category in matched or ["uncategorized"]:
            category_rows.append({
                "year": year,
                "agent_id": agent_id,
                "skill": skill,
                "category": category,
                "matched": category != "uncategorized",
            })

        retrieved_count = ((rec.get("memory_audit") or {}).get("retrieved_count")) or 0
        if retrieved_count > 0:
            warnings.append(f"{agent_id} year {year} retrieved_count={retrieved_count}")

    for agent_id, records in records_by_agent.items():
        sorted_records = sorted(records, key=lambda item: int(item.get("year")))
        flood_years = {int(rec.get("year")) for rec in sorted_records if (rec.get("environment_context") or {}).get("flood_occurred")}
        adjustments = 0
        reactive_adjustments = 0
        for rec in sorted_records:
            year = int(rec.get("year"))
            skill = ((rec.get("approved_skill") or {}).get("skill_name")) or ((rec.get("skill_proposal") or {}).get("skill_name")) or ""
            if is_adjustment(skill):
                adjustments += 1
                if year in flood_years or (year - 1) in flood_years:
                    reactive_adjustments += 1
        reactivity_counter[f"{agent_id}_adjustments"] = adjustments
        reactivity_counter[f"{agent_id}_reactive_adjustments"] = reactive_adjustments

    outputs = {
        "institutional_trajectory.csv": pd.DataFrame(trajectory_rows).sort_values(["agent_id", "year"]),
        "institutional_rationale_text.csv": pd.DataFrame(text_rows).sort_values(["agent_id", "year"]),
        "institutional_rationale_categories_by_year.csv": pd.DataFrame(category_rows).sort_values(["agent_id", "year", "category"]),
    }
    for filename, frame in outputs.items():
        frame.to_csv(output_dir / filename, index=False)

    reactive_total = reactivity_counter["NJ_STATE_reactive_adjustments"] + reactivity_counter["FEMA_NFIP_reactive_adjustments"]
    adjustment_total = reactivity_counter["NJ_STATE_adjustments"] + reactivity_counter["FEMA_NFIP_adjustments"]
    warnings.append(f"reactive_adjustments={reactive_total}/{adjustment_total}")
    return outputs, warnings


def write_report(trace_dir: Path, output_dir: Path, outputs: dict[str, pd.DataFrame], warnings: list[str]) -> None:
    trajectory_df = outputs["institutional_trajectory.csv"]
    categories_df = outputs["institutional_rationale_categories_by_year.csv"]
    text_df = outputs["institutional_rationale_text.csv"]
    category_summary = categories_df.groupby(["agent_id", "category"], as_index=False).size().rename(columns={"size": "count"}).sort_values(["agent_id", "count"], ascending=[True, False])
    text_summary = text_df[["year", "agent_id", "skill", "strategy_len", "reasoning_len"]]
    report_lines = [
        "# Institutional Rationale",
        "",
        f"Trace dir: `{trace_dir.as_posix()}`",
        "",
        "## Policy Trajectory",
        "",
        trajectory_df.to_markdown(index=False),
        "",
        "## Rationale Lengths",
        "",
        text_summary.to_markdown(index=False),
        "",
        "## Rationale Category Counts",
        "",
        category_summary.to_markdown(index=False),
        "",
        "## Summary",
        "",
        "- `institutional_trajectory.csv` lists yearly government and insurance policy states.",
        "- `institutional_rationale_text.csv` extracts the free-text policy rationale and its lengths.",
        "- `institutional_rationale_categories_by_year.csv` tags crisis, budget, equity, loss-ratio, mitigation, and status-quo motifs.",
        "- Memory audit cross-check warnings are preserved below rather than suppressed.",
        "",
        "## Warnings",
        "",
    ]
    report_lines.extend([f"- {warning}" for warning in warnings] or ["- none"])
    (output_dir / "institutional_rationale_report.md").write_text("\n".join(report_lines), encoding="utf-8")


def print_summary(outputs: dict[str, pd.DataFrame], warnings: list[str]) -> None:
    categories_df = outputs["institutional_rationale_categories_by_year.csv"]
    print("institutional_rationale complete")
    print(f"files={len(outputs) + 1}")
    print(f"category_rows={len(categories_df)}")
    print(f"warnings={len(warnings)}")


def main() -> None:
    args = parse_args()
    trace_dir, output_dir = resolve_paths(args)
    outputs, warnings = build_outputs(trace_dir, output_dir)
    write_report(trace_dir, output_dir, outputs, warnings)
    print_summary(outputs, warnings)


if __name__ == "__main__":
    main()
