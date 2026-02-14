"""
CLI entry point for validation metrics computation.
"""

import sys
import argparse
from pathlib import Path


def main():
    """CLI entry point."""
    # Defer imports to avoid circular dependency at module load time
    from validation.engine import compute_validation

    SCRIPT_DIR = Path(__file__).parent.parent.parent
    FLOOD_DIR = SCRIPT_DIR.parent.parent
    RESULTS_DIR = FLOOD_DIR / "paper3" / "results"
    OUTPUT_DIR = RESULTS_DIR / "validation"

    parser = argparse.ArgumentParser(
        description="Compute L1/L2 validation metrics from experiment traces"
    )
    parser.add_argument(
        "--traces", type=str, required=True,
        help="Path to traces directory",
    )
    parser.add_argument(
        "--profiles", type=str, default=None,
        help="Path to agent_profiles_balanced.csv (default: auto-detect)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output directory (default: paper3/results/validation)",
    )

    args = parser.parse_args()

    traces_dir = Path(args.traces)
    if not traces_dir.exists():
        print(f"Error: Traces directory not found: {traces_dir}")
        sys.exit(1)

    profiles_path = Path(args.profiles) if args.profiles else FLOOD_DIR / "data" / "agent_profiles_balanced.csv"
    if not profiles_path.exists():
        print(f"Error: Agent profiles not found: {profiles_path}")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else OUTPUT_DIR

    print("=" * 60)
    print("Validation Metrics Computation")
    print("=" * 60)

    report = compute_validation(traces_dir, profiles_path, output_dir)

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"\nL1 Micro Metrics:")
    for metric, passed in report.l1.passes_thresholds().items():
        status = "PASS" if passed else "FAIL"
        print(f"  {metric}: {status}")

    print(f"\nL2 Macro Metrics:")
    print(f"  EPI: {'PASS' if report.l2.passes_threshold() else 'FAIL'}")

    print(f"\nOVERALL: {'PASS' if report.pass_all else 'FAIL'}")
    print(f"\nOutputs saved to: {output_dir}")
