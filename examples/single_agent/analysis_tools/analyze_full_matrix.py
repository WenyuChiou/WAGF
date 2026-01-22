
import pandas as pd
import numpy as np
import os
from pathlib import Path

# Goal: "Total Matrix"
# Rows: Gemma A, B, C | Llama A, B, C
# Cols: Adaptation Rate (Standard), Mismatch Rate (Silent Failure), Retries

SCRIPT_DIR = Path(__file__).parent
BASE_RESULTS = SCRIPT_DIR.parent / "results" / "JOH_FINAL"

MODELS = ["gemma3_4b", "llama3_2_3b"]
GROUPS = ["Group_A", "Group_B", "Group_C"]

def detect_mismatch(row):
    # Thinking-Doing Gap: Talks about action, does nothing.
    # Note: Only applicable if 'reason_tp_reason' exists (Groups B/C)
    reason = str(row.get('reason_tp_reason', '')).lower()
    action = str(row.get('proposed_skill', '')).lower()
    
    intent_insurance = "buy insurance" in reason or "purchase insurance" in reason
    intent_relocate = "relocate" in reason or "move out" in reason or "leave" in reason
    
    if action == "do_nothing":
        if intent_insurance: return True
        if intent_relocate: return True
    return False

def analyze_full_matrix():
    results = []
    
    for m in MODELS:
        for g in GROUPS:
            path = BASE_RESULTS / m / g
            if not path.exists(): continue
            
            runs = list(path.glob("Run_*"))
            
            # Metric 1: Adaptation Rate (from Simulation Log)
            # Defined as: % of agents who have insurance OR elevated OR relocated by Year 10
            total_agents = 0
            adapted_agents = 0
            
            # Metric 2: Mismatch Rate (from Audit Log)
            total_audits = 0
            mismatches = 0
            retries = 0
            
            for run in runs:
                # 1. Sim Log
                sim_log_path = run / "simulation_log.csv"
                if sim_log_path.exists():
                    try:
                        df_sim = pd.read_csv(sim_log_path)
                        # Get final state (Year 10 usually, or max year per agent)
                        final_states = df_sim.sort_values('year').groupby('agent_id').last()
                        total_agents += len(final_states)
                        # Adapted = elevated (True) OR has_insurance (True) OR relocated (True)
                        # Note: dataframe bools might be strings or actual bools
                        adapted = final_states[
                            (final_states['elevated'] == True) | 
                            (final_states['has_insurance'] == True) | 
                            (final_states['relocated'] == True) |
                            (final_states['elevated'].astype(str).str.lower() == 'true') |
                            (final_states['has_insurance'].astype(str).str.lower() == 'true') |
                            (final_states['relocated'].astype(str).str.lower() == 'true')
                        ]
                        adapted_agents += len(adapted)
                    except: pass
                
                # 2. Audit Log (B/C only)
                audits = list(run.rglob("household_governance_audit.csv"))
                if audits:
                    try:
                        df_aud = pd.read_csv(audits[0])
                        total_audits += len(df_aud)
                        if 'retry_count' in df_aud:
                            retries += df_aud['retry_count'].sum()
                        if 'reason_tp_reason' in df_aud:
                            mismatches += df_aud.apply(lambda r: 1 if detect_mismatch(r) else 0, axis=1).sum()
                    except: pass

            # Calculate Rates
            adapt_rate = (adapted_agents / total_agents * 100) if total_agents > 0 else 0
            gap_rate = (mismatches / total_audits * 100) if total_audits > 0 else 0 # usually 0 for Group A
            
            # Formatting
            results.append({
                "Model": m,
                "Group": g,
                "Adapted%": adapt_rate,
                "Retries": retries,
                "GapRate%": gap_rate,
                "TotalAudits": total_audits
            })
            
    # Print Table
    print(f"{'Model':<12} | {'Group':<8} | {'Adapted %':<10} | {'Retries':<8} | {'Gap Rate %':<10}")
    print("-" * 60)
    for r in results:
        gap_str = f"{r['GapRate%']:.2f}%" if r['TotalAudits'] > 0 else "N/A"
        print(f"{r['Model']:<12} | {r['Group']:<8} | {r['Adapted%']:.1f}%      | {r['Retries']:<8} | {gap_str:<10}")

if __name__ == "__main__":
    analyze_full_matrix()
