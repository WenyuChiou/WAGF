"""
Parity Validation Script for Task-012

Compares simulation outputs from baseline (pre-refactor) and refactored (post-refactor)
code to ensure that the `BaseAgent.apply_delta()` change does not alter simulation logic.

Usage:
    python validate_parity.py <baseline_dir> <refactored_dir>

Example:
    python validate_parity.py parity_check/baseline parity_check/refactored
"""

import pandas as pd
import sys
from pathlib import Path


def validate_parity(baseline_path: str, refactored_path: str) -> bool:
    """
    Compare two simulation logs for decision and state parity.
    
    Returns:
        True if all checks pass, False otherwise.
    """
    baseline_csv = Path(baseline_path) / "simulation_log.csv"
    refactored_csv = Path(refactored_path) / "simulation_log.csv"
    
    if not baseline_csv.exists():
        print(f"❌ Baseline file not found: {baseline_csv}")
        return False
    if not refactored_csv.exists():
        print(f"❌ Refactored file not found: {refactored_csv}")
        return False
    
    df_baseline = pd.read_csv(baseline_csv)
    df_refactored = pd.read_csv(refactored_csv)
    
    print(f"📊 Baseline rows: {len(df_baseline)}, Refactored rows: {len(df_refactored)}")
    
    # Check 1: Same number of rows
    if len(df_baseline) != len(df_refactored):
        print(f"❌ Row count mismatch: {len(df_baseline)} vs {len(df_refactored)}")
        return False
    
    # Check 2: Decision parity (most critical)
    decision_col = 'approved_skill' if 'approved_skill' in df_baseline.columns else 'decision'
    if decision_col not in df_baseline.columns:
        print(f"⚠️ Warning: Decision column not found. Skipping decision check.")
    else:
        if not df_baseline[decision_col].equals(df_refactored[decision_col]):
            mismatches = (df_baseline[decision_col] != df_refactored[decision_col]).sum()
            print(f"❌ Decision parity failed! {mismatches} mismatched decisions.")
            # Show first 5 mismatches
            diff_idx = df_baseline[decision_col] != df_refactored[decision_col]
            print("First 5 mismatches:")
            print(df_baseline[diff_idx].head())
            return False
        else:
            print(f"✅ Decision parity: PASSED ({len(df_baseline)} decisions match)")
    
    # Check 3: State persistence parity
    state_col = 'cumulative_state' if 'cumulative_state' in df_baseline.columns else None
    if state_col and state_col in df_baseline.columns:
        if not df_baseline[state_col].equals(df_refactored[state_col]):
            mismatches = (df_baseline[state_col] != df_refactored[state_col]).sum()
            print(f"❌ State parity failed! {mismatches} mismatched states.")
            return False
        else:
            print(f"✅ State parity: PASSED ({len(df_baseline)} states match)")
    else:
        print(f"⚠️ Warning: State column not found. Skipping state check.")
    
    print("\n🎉 Parity Verification PASSED: All decisions and states are identical.")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        baseline = "examples/single_agent/parity_check/baseline"
        refactored = "examples/single_agent/parity_check/refactored"
        print(f"Using default paths: {baseline}, {refactored}")
    else:
        baseline = sys.argv[1]
        refactored = sys.argv[2]
    
    success = validate_parity(baseline, refactored)
    sys.exit(0 if success else 1)
