"""V2 Temporal Validator — Post-Hoc Diagnostic (uses framework module).

Thin orchestrator that applies the domain-agnostic temporal-rule
framework (`broker/components/governance/temporal_rules/`) to existing
audit CSVs via the flood-domain adapter. Produces aggregate per-run
trigger counts for M1 / M2 / M3 across all 9 models × 2 conditions.

Rule / adapter architecture:
    broker/components/governance/temporal_rules/   ← framework (generic)
    examples/single_agent/adapters/flood_*.py      ← domain adapter

This script is thin on purpose — adding a new domain (e.g., irrigation,
drought) only requires writing a new adapter, not a new diagnostic.

Usage:
    python examples/single_agent/analysis/compute_temporal_diagnostics.py

Outputs:
    .ai/temporal_diagnostic_2026-04-19.csv  (per-run raw counts)
    .ai/temporal_diagnostic_report_2026-04-19.md  (aggregate markdown)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

# Ensure repo root is on sys.path so `examples.*` imports resolve.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from broker.components.governance.temporal_rules import (
    DEFAULT_RULES,
    TemporalRuleEvaluator,
)
from examples.single_agent.adapters.flood_temporal_adapter import FloodTemporalAdapter


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_ROOT = REPO_ROOT / "examples" / "single_agent" / "results"
DEFAULT_OUTPUT_CSV = REPO_ROOT / ".ai" / "temporal_diagnostic_2026-04-19.csv"
DEFAULT_OUTPUT_MD = REPO_ROOT / ".ai" / "temporal_diagnostic_report_2026-04-19.md"

CONDITIONS: Dict[str, Tuple[str, str]] = {
    "governed": ("JOH_FINAL", "Group_C"),
    "disabled": ("JOH_ABLATION_DISABLED", "Group_C_disabled"),
}


def _load_audit(csv_path: Path) -> List[Dict]:
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    return df.to_dict(orient="records")


def discover_runs(
    results_root: Path,
    models: List[str],
    conditions: Dict[str, Tuple[str, str]],
) -> List[Tuple[str, str, str, Path]]:
    out: List[Tuple[str, str, str, Path]] = []
    for model in models:
        for cond_label, (family, group) in conditions.items():
            model_dir = results_root / family / model / group
            if not model_dir.exists():
                continue
            for run_dir in sorted(model_dir.glob("Run_*")):
                csv = run_dir / "household_governance_audit.csv"
                if csv.exists():
                    out.append((model, cond_label, run_dir.name, csv))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--models", nargs="+", default=[
        "gemma3_4b", "gemma3_12b", "gemma3_27b",
        "ministral3_3b", "ministral3_8b", "ministral3_14b",
        "gemma4_e2b", "gemma4_e4b", "gemma4_26b",
    ])
    args = parser.parse_args()

    evaluator = TemporalRuleEvaluator(DEFAULT_RULES, FloodTemporalAdapter())

    rows: List[Dict] = []
    discovered = discover_runs(args.results_root, args.models, CONDITIONS)
    for model, cond, run, csv in discovered:
        audit_rows = _load_audit(csv)
        if not audit_rows:
            continue
        print(f"  [scan] {model:16} {cond:10} {run}: n={len(audit_rows)}")
        result = evaluator.evaluate_experiment(
            audit_rows, model=model, condition=cond, run=run,
        )
        rows.append({
            "model": model,
            "condition": cond,
            "run": run,
            "total_decisions": result.n_decisions,
            "m1_triggers": result.by_rule.get("M1", 0),
            "m1_rate": round(result.rate_by_rule.get("M1", 0.0), 3),
            "m2_triggers": result.by_rule.get("M2", 0),
            "m2_rate": round(result.rate_by_rule.get("M2", 0.0), 3),
            "m3_triggers": result.by_rule.get("M3", 0),
            "m3_rate": round(result.rate_by_rule.get("M3", 0.0), 3),
        })

    if not rows:
        print("No runs found under", args.results_root)
        return 1

    df = pd.DataFrame(rows)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output_csv, index=False, encoding="utf-8")
    print(f"\n[write] per-run CSV: {args.output_csv}")

    # Aggregate markdown
    agg = df.groupby(["model", "condition"]).agg(
        runs=("run", "nunique"),
        total=("total_decisions", "sum"),
        m1_t=("m1_triggers", "sum"),
        m1_r=("m1_rate", "mean"),
        m2_t=("m2_triggers", "sum"),
        m2_r=("m2_rate", "mean"),
        m3_t=("m3_triggers", "sum"),
        m3_r=("m3_rate", "mean"),
    ).reset_index()

    lines: List[str] = [
        "# V2 Temporal Validator — Post-Hoc Diagnostic Report\n",
        "**Date**: 2026-04-19  (auto-generated via framework module)\n",
        "",
        "Counterfactual trigger counts computed by "
        "`broker/components/governance/temporal_rules/` via the flood-domain "
        "adapter (`examples/single_agent/adapters/flood_temporal_adapter.py`).\n",
        "## Aggregate per (model, condition)\n",
        "| Model | Cond | Runs | Total | M1 | M1 rate % | M2 | M2 rate % | M3 | M3 rate % |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in agg.iterrows():
        lines.append(
            f"| {r['model']} | {r['condition']} | {int(r['runs'])} | "
            f"{int(r['total'])} | "
            f"{int(r['m1_t'])} | {r['m1_r']:.2f} | "
            f"{int(r['m2_t'])} | {r['m2_r']:.2f} | "
            f"{int(r['m3_t'])} | {r['m3_r']:.2f} |"
        )
    lines.extend([
        "",
        "**Rule definitions**",
        "- **M1 Appraisal-History Coherence** — salient event in prior 3-yr memory window AND current threat label in low-appraisal set.",
        "- **M2 Behavioural Inertia** — 5 consecutive years of same final_skill while environmental threat spans ≥ 2 ordinal levels.",
        "- **M3 Evidence-Grounded Irreversibility** — year-1 irreversible action with no salient event in seed memory.",
        "",
        "**Theory grounding**: M1 ← Kahneman availability heuristic + memory-consolidation literature; M2 ← cognitive-inertia + adaptive-management review cycles (Pahl-Wostl 2007); M3 ← precautionary principle / real-options theory.",
        "",
        "**Framework note**: diagnostic is post-hoc only; live enforcement would inject rule-retry into the validator pipeline and is deferred to a follow-up study.",
    ])

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"[write] markdown report: {args.output_md}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
