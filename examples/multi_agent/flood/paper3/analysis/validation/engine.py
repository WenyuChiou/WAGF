"""
Validation Engine — main pipeline orchestrating L1 + L2 computation.
"""

import json
import math
from pathlib import Path
from collections import Counter
from dataclasses import asdict
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import pandas as pd

from validation.metrics.l1_micro import (
    compute_l1_metrics,
    compute_cacr_decomposition,
    L1Metrics,
)
from validation.metrics.l2_macro import compute_l2_metrics
from validation.metrics.cgr import compute_cgr
from validation.metrics.entropy import _compute_entropy
from validation.reporting.report_builder import ValidationReport, _to_json_serializable
from validation.benchmarks.flood import EMPIRICAL_BENCHMARKS  # default for backward compat

if TYPE_CHECKING:
    from validation.theories.base import BehavioralTheory
    from validation.hallucinations.base import HallucinationChecker
    from validation.grounding.base import GroundingStrategy


def load_traces(traces_dir: Path) -> Tuple[List[Dict], List[Dict]]:
    """Load owner and renter traces from directory."""
    owner_traces = []
    renter_traces = []

    for pattern in ["**/household_owner_traces.jsonl", "**/owner_traces.jsonl"]:
        for filepath in traces_dir.glob(pattern):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        owner_traces.append(json.loads(line))

    for pattern in ["**/household_renter_traces.jsonl", "**/renter_traces.jsonl"]:
        for filepath in traces_dir.glob(pattern):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        renter_traces.append(json.loads(line))

    return owner_traces, renter_traces


def compute_validation(
    traces_dir: Path,
    agent_profiles_path: Path,
    output_dir: Path,
    theory: Optional["BehavioralTheory"] = None,
    hallucination_checker: Optional["HallucinationChecker"] = None,
    grounder: Optional["GroundingStrategy"] = None,
) -> ValidationReport:
    """Compute full validation report."""
    print(f"Loading traces from: {traces_dir}")
    owner_traces, renter_traces = load_traces(traces_dir)
    all_traces = owner_traces + renter_traces

    print(f"  Owner traces: {len(owner_traces)}")
    print(f"  Renter traces: {len(renter_traces)}")
    print(f"  Total: {len(all_traces)}")

    if len(all_traces) == 0:
        raise ValueError(f"No traces found in {traces_dir}")

    print(f"Loading agent profiles from: {agent_profiles_path}")
    agent_profiles = pd.read_csv(agent_profiles_path)
    print(f"  Agents: {len(agent_profiles)}")

    print("\nComputing L1 metrics...")
    l1_owner = compute_l1_metrics(owner_traces, "owner", theory=theory,
                                   hallucination_checker=hallucination_checker)
    l1_renter = compute_l1_metrics(renter_traces, "renter", theory=theory,
                                    hallucination_checker=hallucination_checker)

    # Combined L1
    combined_actions = {
        k: l1_owner.action_distribution.get(k, 0) + l1_renter.action_distribution.get(k, 0)
        for k in set(l1_owner.action_distribution) | set(l1_renter.action_distribution)
    }
    combined_ebe = round(_compute_entropy(Counter(combined_actions)), 4)
    k_combined = 5  # Fixed: full household action space (owner 4 + renter 3, shared do_nothing)
    combined_ebe_max = round(math.log2(k_combined), 4)
    combined_ebe_ratio = round(combined_ebe / combined_ebe_max, 4) if combined_ebe_max > 0 else 0.0

    l1_combined = L1Metrics(
        cacr=round((l1_owner.cacr * len(owner_traces) + l1_renter.cacr * len(renter_traces)) / len(all_traces), 4),
        r_h=round((l1_owner.r_h * len(owner_traces) + l1_renter.r_h * len(renter_traces)) / len(all_traces), 4),
        ebe=combined_ebe,
        ebe_max=combined_ebe_max,
        ebe_ratio=combined_ebe_ratio,
        total_decisions=len(all_traces),
        coherent_decisions=l1_owner.coherent_decisions + l1_renter.coherent_decisions,
        hallucinations=l1_owner.hallucinations + l1_renter.hallucinations,
        action_distribution=combined_actions,
    )

    # CACR decomposition
    audit_csvs = list(traces_dir.glob("**/*governance_audit.csv"))
    if audit_csvs:
        print(f"\n  Found {len(audit_csvs)} governance audit CSV(s)")
        cacr_decomp = compute_cacr_decomposition(audit_csvs, theory=theory)
        if cacr_decomp:
            l1_combined.cacr_decomposition = cacr_decomp
            print(f"  CACR_raw (pre-governance): {cacr_decomp.cacr_raw}")
            print(f"  CACR_final (post-governance): {cacr_decomp.cacr_final}")
            print(f"  Retry rate: {cacr_decomp.retry_rate}")
            print(f"  Fallback rate: {cacr_decomp.fallback_rate}")
            print(f"  Quadrant CACR: {cacr_decomp.quadrant_cacr}")

    print(f"  CACR: {l1_combined.cacr} (threshold >=0.75)")
    print(f"  R_H: {l1_combined.r_h} (threshold <=0.10)")
    print(f"  EBE: {l1_combined.ebe} (ratio={l1_combined.ebe_ratio}, threshold 0.1<ratio<0.9)")

    # CGR (Construct Grounding Rate)
    print("\nComputing CGR metrics...")
    cgr_results = compute_cgr(all_traces, grounder=grounder, theory=theory)
    print(f"  CGR_TP exact: {cgr_results['cgr_tp_exact']}")
    print(f"  CGR_CP exact: {cgr_results['cgr_cp_exact']}")
    print(f"  CGR_TP adjacent: {cgr_results['cgr_tp_adjacent']}")
    print(f"  CGR_CP adjacent: {cgr_results['cgr_cp_adjacent']}")
    print(f"  Kappa TP: {cgr_results['kappa_tp']}, Kappa CP: {cgr_results['kappa_cp']}")
    print(f"  Grounded: {cgr_results['n_grounded']}, Skipped: {cgr_results['n_skipped']}")

    # L2
    print("\nComputing L2 metrics...")
    l2 = compute_l2_metrics(all_traces, agent_profiles)

    print(f"  EPI: {l2.epi} (threshold >=0.60)")
    print(f"  Benchmarks in range: {l2.benchmarks_in_range}/{l2.total_benchmarks}")

    # Metadata
    seed = None
    model = "unknown"
    if "seed_" in str(traces_dir):
        try:
            seed = int(str(traces_dir).split("seed_")[1].split("/")[0].split("\\")[0])
        except:
            pass

    l1_pass = all(l1_combined.passes_thresholds().values())
    l2_pass = l2.passes_threshold()

    report = ValidationReport(
        l1=l1_combined,
        l2=l2,
        traces_path=str(traces_dir),
        seed=seed,
        model=model,
        pass_all=l1_pass and l2_pass,
    )

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "validation_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(_to_json_serializable({
            "l1": asdict(l1_combined),
            "l2": asdict(l2),
            "cgr": cgr_results,
            "traces_path": str(traces_dir),
            "seed": seed,
            "model": model,
            "pass_all": report.pass_all,
            "l1_pass": l1_pass,
            "l2_pass": l2_pass,
        }), f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {report_path}")

    l1_path = output_dir / "l1_micro_metrics.json"
    l1_data = {
        "combined": asdict(l1_combined),
        "owner": asdict(l1_owner),
        "renter": asdict(l1_renter),
        "thresholds": {"CACR": ">=0.75", "R_H": "<=0.10", "EBE": "0.1<ratio<0.9"},
        "pass": l1_combined.passes_thresholds(),
    }
    if l1_combined.cacr_decomposition:
        l1_data["cacr_decomposition"] = asdict(l1_combined.cacr_decomposition)
    with open(l1_path, 'w', encoding='utf-8') as f:
        json.dump(_to_json_serializable(l1_data), f, indent=2, ensure_ascii=False)
    print(f"Saved: {l1_path}")

    cgr_path = output_dir / "cgr_metrics.json"
    with open(cgr_path, 'w', encoding='utf-8') as f:
        json.dump(_to_json_serializable(cgr_results), f, indent=2, ensure_ascii=False)
    print(f"Saved: {cgr_path}")

    l2_path = output_dir / "l2_macro_metrics.json"
    l2_data = {
        "epi": l2.epi,
        "benchmarks_in_range": l2.benchmarks_in_range,
        "total_benchmarks": l2.total_benchmarks,
        "benchmark_results": l2.benchmark_results,
        "pass": l2.passes_threshold(),
    }
    if l2.supplementary:
        l2_data["supplementary"] = l2.supplementary
    with open(l2_path, 'w', encoding='utf-8') as f:
        json.dump(_to_json_serializable(l2_data), f, indent=2, ensure_ascii=False)
    print(f"Saved: {l2_path}")

    benchmark_df = pd.DataFrame([
        {
            "Benchmark": name,
            "Value": result["value"],
            "Range_Low": result["range"][0],
            "Range_High": result["range"][1],
            "In_Range": result["in_range"],
            "Weight": result["weight"],
        }
        for name, result in l2.benchmark_results.items()
    ])
    benchmark_path = output_dir / "benchmark_comparison.csv"
    benchmark_df.to_csv(benchmark_path, index=False)
    print(f"Saved: {benchmark_path}")

    return report
