"""
JOH Rigorous Analysis Script
============================

This script performs the "Comparative Cognitive Governance Analysis" for Groups A, B, and C.
It calculates the 3 core metrics defined in the Technical Note.

Metrics:
1. Rationality Score (RS) - "Decision Compliance"
   - Did the agent follow PMT rules?
   - For Group A: Uses Shadow Audit scores.
   - For Group B/C: Uses internal scores.

2. Internal Fidelity (IF) - "Decision Coherence"
   - Spearman Correlation between Threat Appraisal and Action Intensity.

3. Cognitive Stability (CS) - "The Ratchet Effect"
   - Decay Rate (lambda) of Threat Appraisal after a flood event.

Usage:
    python analyze_joh_rigorous.py --result_dir results/JOH_FINAL
"""

import pandas as pd
import numpy as np
import argparse
from pathlib import Path
from scipy.stats import spearmanr
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import seaborn as sns

# --- Configuration ---
VALID_LABELS = {
    "VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5
}

ACTION_INTENSITY = {
    "Do Nothing": 0,
    "Only Flood Insurance": 1,
    "Only House Elevation": 2, 
    "Both Flood Insurance and House Elevation": 3, # Treated as high intensity
    "Relocate": 3 # Max intensity
}

# Governance Rules (Simplified for Verification)
def check_compliance(row):
    """
    Returns True if decision complies with PMT rules, False otherwise.
    Rule 1: If Threat >= High (4), MUST NOT Do Nothing (0).
    Rule 2: If Coping <= Very Low (1), MUST NOT Elevate/Relocate (2/3).
    """
    t = row.get("threat_score")
    c = row.get("coping_score")
    a = row.get("action_intensity")
    
    if pd.isna(t) or pd.isna(c) or pd.isna(a):
        return None # Cannot evaluate
    
    # Rule 1: Under-reaction
    if t >= 4 and a == 0:
        return False
        
    # Rule 2: Over-estimation of capability (Fantasy)
    if c <= 1 and a >= 2:
        return False
        
    return True

def clean_score(val):
    """Normalize score to 1-5 float."""
    if pd.isna(val): return None
    s = str(val).strip()
    if s in VALID_LABELS:
        return float(VALID_LABELS[s])
    try:
        f = float(s)
        if 1 <= f <= 5: return f
    except:
        pass
    return None

def analyze_experiment(result_dir):
    root = Path(result_dir)
    print(f"Analyzing results in {root}...")
    
    # Data Collection
    all_data = []
    
    # Traverse Model -> Group -> Run
    for model_dir in root.iterdir():
        if not model_dir.is_dir(): continue
        for group_dir in model_dir.iterdir():
            if not group_dir.is_dir(): continue
            group_name = group_dir.name # "Group_A", "Group_B", etc.
            
            for run_dir in group_dir.iterdir():
                if not run_dir.is_dir(): continue
                # Look for log
                log_path = run_dir / "simulation_log.csv"
                shadow_path = run_dir / "simulation_log_shadow.csv"
                
                final_log = None
                
                # Load Logic
                if group_name == "Group_A":
                    if shadow_path.exists():
                        final_log = pd.read_csv(shadow_path)
                        # Use shadow scores
                        final_log["threat_score"] = final_log["shadow_threat_score"]
                        final_log["coping_score"] = final_log["shadow_coping_score"]
                    elif log_path.exists():
                        print(f"Warning: Group A found but no shadow log for {run_dir}. Skipping.")
                        continue
                else:
                    if log_path.exists():
                        final_log = pd.read_csv(log_path)
                            # NEW: Try to join with governance audit to get structured appraisals
                        audit_files = list(run_dir.rglob("household_governance_audit.csv"))
                        if audit_files:
                            audit_df = pd.read_csv(audit_files[0])
                            # Map 'step_id' to 'year' for join parity
                            if "step_id" in audit_df.columns:
                                audit_df["year"] = audit_df["step_id"]
                            
                            # Filter for columns we need
                            cols_to_use = ["agent_id", "year", "reason_tp_label", "reason_cp_label"]
                            # Ensure columns exist
                            cols_to_use = [c for c in cols_to_use if c in audit_df.columns]
                            
                            audit_subset = audit_df[cols_to_use].copy()
                            # Convert to numeric for safe join
                            audit_subset["year"] = pd.to_numeric(audit_subset["year"], errors='coerce')
                            audit_subset["agent_id"] = audit_subset["agent_id"].astype(str)
                            
                            final_log["year"] = pd.to_numeric(final_log["year"], errors='coerce')
                            final_log["agent_id"] = final_log["agent_id"].astype(str)
                            
                            final_log = pd.merge(final_log, audit_subset, on=["agent_id", "year"], how="left")
                            
                            # Map labels to scores
                            final_log["threat_score"] = final_log["reason_tp_label"].apply(clean_score)
                            final_log["coping_score"] = final_log["reason_cp_label"].apply(clean_score)
                        else:
                            # Fallback to standard columns if present
                            t_col = "threat_appraisal" if "threat_appraisal" in final_log.columns else None
                            c_col = "coping_appraisal" if "coping_appraisal" in final_log.columns else None
                            if t_col: final_log["threat_score"] = final_log[t_col].apply(clean_score)
                            if c_col: final_log["coping_score"] = final_log[c_col].apply(clean_score)
                
                if final_log is not None:
                    # Map Actions - Handle both 'cumulative_state' and 'decision' columns
                    state_col = "cumulative_state" if "cumulative_state" in final_log.columns else "decision"
                    
                    # Robust Mapping
                    def map_intensity(val):
                        if pd.isna(val): return 0
                        s = str(val).strip()
                        # Direct string match
                        if s in ACTION_INTENSITY:
                            return ACTION_INTENSITY[s]
                        # Numeric match (0-4)
                        if s in ["0", "1", "2", "3", "4", 0, 1, 2, 3, 4]:
                            # Map numeric back to intensity if needed, 
                            # but in Group A, 'decision' is already "Do Nothing" strings.
                            # Just return 0 as fallback if unknown string.
                            return 0
                        return 0

                    final_log["action_intensity"] = final_log[state_col].apply(map_intensity)
                    final_log["group"] = group_name
                    final_log["model"] = model_dir.name
                    final_log["run"] = run_dir.name
                    print(f"  Added {group_name} {run_dir.name}: {len(final_log)} rows. Columns: {list(final_log.columns)}")
                    all_data.append(final_log)

    if not all_data:
        print("No valid data found.")
        return

    df = pd.concat(all_data, ignore_index=True)
    print(f"Total Rows: {len(df)}")
    
    # --- Metric 1: Rationality Score (RS) ---
    print("\n--- Metric 1: Rationality Score (Compliance) ---")
    df["compliant"] = df.apply(check_compliance, axis=1)
    rs_stats = df.groupby(["group", "model"])["compliant"].mean()
    print(rs_stats)
    
    # --- Metric 2: Internal Fidelity (IF) ---
    print("\n--- Metric 2: Internal Fidelity (Spearman Correlation) ---")
    if_results = []
    print(f"Grouped by: {list(df.columns)}")
    for (group, model), adf in df.groupby(["group", "model"]):
        subset = adf.dropna(subset=["threat_score", "action_intensity"])
        if len(subset) > 10:
            corr, p = spearmanr(subset["threat_score"], subset["action_intensity"])
            if_results.append({"group": group, "model": model, "spearman_r": corr, "p_value": p})
            print(f"{group} | {model}: r={corr:.3f} (p={p:.3f})")
    
    # --- Metric 3: Cognitive Stability (CS) ---
    print("\n--- Metric 3: Cognitive Stability (Ratchet Effect) ---")
    # IdentifyYears after a flood (t=0 is the flood year)
    # df has columns: 'agent_id', 'run', 'year', 'flooded_this_year', 'threat_score'
    
    cs_results = []
    
    for (group, model, run), rdf in df.groupby(["group", "model", "run"]):
        # Find flood years in this run
        flood_years = rdf[rdf["flooded_this_year"] == True]["year"].unique()
        if len(flood_years) == 0: continue
        
        for f_year in flood_years:
            # Look at subsequent years (up to 3 years after)
            for delta in range(0, 4):
                target_year = f_year + delta
                row = rdf[rdf["year"] == target_year]
                if not row.empty:
                    avg_t = row["threat_score"].mean()
                    cs_results.append({
                        "group": group, 
                        "model": model, 
                        "delta": delta, 
                        "threat_score": avg_t
                    })
    
    if cs_results:
        cs_df = pd.DataFrame(cs_results)
        cs_summary = cs_df.groupby(["group", "model", "delta"])["threat_score"].mean().unstack()
        print(cs_summary)
        
    # Save Summary
    summary_path = root / "analysis_summary.csv"
    # Create a comprehensive summary
    with open(summary_path, "w") as f:
        f.write("--- Metric 1: Rationality Score (RS) ---\n")
        rs_stats.to_csv(f)
        f.write("\n--- Metric 2: Internal Fidelity (IF) ---\n")
        pd.DataFrame(if_results).to_csv(f, index=False)
        if cs_results:
            f.write("\n--- Metric 3: Cognitive Stability (CS) ---\n")
            cs_summary.to_csv(f)
            
    print(f"Analysis complete. Summary saved to {summary_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result_dir", type=str, default="results/JOH_FINAL")
    args = parser.parse_args()
    
    analyze_experiment(args.result_dir)
