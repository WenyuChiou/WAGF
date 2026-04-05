#!/usr/bin/env python3
"""
Cross-model conservatism diagnostic report.

Scans all model directories under JOH_FINAL and JOH_ABLATION_DISABLED,
computes CCA/CSI/ACI/ESRR for each, and prints a comparison table.

Usage:
    python model_conservatism_report.py
    python model_conservatism_report.py --results-dir path/to/results
"""
import sys
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from broker.validators.calibration.conservatism_diagnostic import (
    run_conservatism_diagnostic,
    ConservatismReport,
)


def find_experiments(results_dir: Path):
    """Find all model/condition/run combinations."""
    experiments = []

    for condition_dir_name, condition_label, subdir_pattern in [
        ("JOH_FINAL", "governed", "Group_C"),
        ("JOH_ABLATION_DISABLED", "disabled", "Group_C_disabled"),
    ]:
        condition_dir = results_dir / condition_dir_name
        if not condition_dir.exists():
            continue

        for model_dir in sorted(condition_dir.iterdir()):
            if not model_dir.is_dir() or model_dir.name.startswith("_"):
                continue

            model_name = model_dir.name
            group_dir = model_dir / subdir_pattern

            if not group_dir.exists():
                continue

            for run_dir in sorted(group_dir.iterdir()):
                if not run_dir.is_dir() or not run_dir.name.startswith("Run"):
                    continue

                audit = run_dir / "household_governance_audit.csv"
                sim_log = run_dir / "simulation_log.csv"

                if audit.exists():
                    experiments.append({
                        "model": model_name,
                        "condition": condition_label,
                        "run": run_dir.name,
                        "audit_path": str(audit),
                        "sim_log_path": str(sim_log) if sim_log.exists() else None,
                    })

    return experiments


def main():
    parser = argparse.ArgumentParser(description="Cross-model conservatism diagnostic")
    parser.add_argument(
        "--results-dir",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "results"),
        help="Root results directory containing JOH_FINAL and JOH_ABLATION_DISABLED",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    experiments = find_experiments(results_dir)

    if not experiments:
        print(f"No experiments found in {results_dir}")
        return

    print(f"Found {len(experiments)} experiment runs\n")

    # Run diagnostics
    reports = []
    for exp in experiments:
        try:
            report = run_conservatism_diagnostic(
                audit_path=exp["audit_path"],
                sim_log_path=exp["sim_log_path"],
                model_name=exp["model"],
                condition=exp["condition"],
            )
            reports.append(report)
        except Exception as e:
            print(f"  [ERROR] {exp['model']}/{exp['condition']}/{exp['run']}: {e}")

    # Aggregate by model+condition (average across runs)
    from collections import defaultdict
    agg = defaultdict(list)
    for r in reports:
        agg[(r.model, r.condition)].append(r)

    # Print comparison table
    print("=" * 100)
    print(f"{'Model':<20} {'Cond':<10} {'N':>6} {'CCA':>7} {'CSI':>7} {'ACI':>7} {'ESRR':>7} {'TP H+VH%':>9} {'Top Action':<18} {'Warnings'}")
    print("-" * 100)

    for (model, condition), run_reports in sorted(agg.items()):
        n = sum(r.n_decisions for r in run_reports)
        cca = np.mean([r.cca for r in run_reports if not math.isnan(r.cca)])
        csi = np.mean([r.csi for r in run_reports if not math.isnan(r.csi)])
        aci = np.mean([r.aci for r in run_reports if not math.isnan(r.aci)])
        esrr = np.mean([r.esrr for r in run_reports if not math.isnan(r.esrr)])

        # Aggregate TP distribution
        tp_total = defaultdict(int)
        for r in run_reports:
            for k, v in r.tp_distribution.items():
                tp_total[k] += v
        tp_hv = (tp_total.get("H", 0) + tp_total.get("VH", 0)) / max(n, 1) * 100

        # Most common action
        act_total = defaultdict(int)
        for r in run_reports:
            for k, v in r.action_distribution.items():
                act_total[k] += v
        top_action = max(act_total, key=act_total.get) if act_total else "N/A"

        # Aggregate warnings
        all_warnings = set()
        for r in run_reports:
            all_warnings.update(r.warnings)
        warn_str = "; ".join(sorted(all_warnings)[:2]) if all_warnings else ""

        print(f"{model:<20} {condition:<10} {n:>6} {cca:>7.3f} {csi:>7.3f} {aci:>7.3f} {esrr:>7.3f} {tp_hv:>8.1f}% {top_action:<18} {warn_str}")

    print("=" * 100)
    print("\nMetric Guide:")
    print("  CCA  = Construct-Context Alignment [0-1]: fraction of flood-year decisions with TP>=H")
    print("  CSI  = Construct Sensitivity Index [-1,1]: Spearman(year, TP) — responsiveness to exposure")
    print("  ACI  = Action Concentration Index [0-1]: 0=diverse, 1=all same action")
    print("  ESRR = Extreme Scenario Response Rate [0-1]: strong actions in severe scenarios")


if __name__ == "__main__":
    import math
    import numpy as np
    main()
