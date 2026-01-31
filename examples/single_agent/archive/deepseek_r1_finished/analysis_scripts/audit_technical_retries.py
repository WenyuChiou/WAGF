
import pandas as pd
import numpy as np
import os
import re
import subprocess
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
RESULTS_DIR = BASE_DIR / "examples" / "single_agent" / "results" / "JOH_FINAL"
OUTPUT_DIR = BASE_DIR / "examples" / "single_agent" / "analysis" / "SQ3_Final_Results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
groups = ["Group_A", "Group_B", "Group_C"]

def count_pattern(file_path, pattern):
    try:
        # Use PowerShell's Select-String for reliability
        cmd = f'Select-String -Path "{file_path}" -Pattern "{pattern}" | Measure-Object | Select-Object -ExpandProperty Count'
        result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
        return int(result.stdout.strip()) if result.stdout.strip() else 0
    except Exception as e:
        return 0

def audit_log(model, group):
    log_path = RESULTS_DIR / model / group / "Run_1" / "execution.log"
    if not log_path.exists():
        return None
    
    # 1. Parse-Level Failures
    p_invalid_labels = count_pattern(log_path, "Invalid _LABEL values")
    p_missing_constructs = count_pattern(log_path, "Missing required constructs")
    p_schema_missing = count_pattern(log_path, "Response missing required fields")
    p_empty = count_pattern(log_path, "Empty/Null response")
    
    # 2. Hallucinations (Special Scale Mixed Output)
    # Exclude the framework's own "- Constructs:" debug logs
    # Use PowerShell to find TP= but NOT "- Constructs:"
    cmd_h = f'Select-String -Path "{log_path}" -Pattern "TP=" | Where-Object {{ $_.Line -notmatch "- Constructs:" }} | Measure-Object | Select-Object -ExpandProperty Count'
    result_h = subprocess.run(["powershell", "-Command", cmd_h], capture_output=True, text=True)
    p_hallucinations = int(result_h.stdout.strip()) if result_h.stdout.strip() else 0
    
    # 3. Semantic/Policy Blocks
    s_rule_blocks = count_pattern(log_path, "failed validation")
    
    # 4. Total Retries (All types)
    total_gov_retries = count_pattern(log_path, r"\[Governance:Retry\]")
    total_broker_retries = count_pattern(log_path, r"\[Broker:Retry\]")
    total_llm_retries = count_pattern(log_path, r"\[LLM:Retry\]")
    
    # 5. Total Active Steps (N) - READ FROM CSV FOR ACCURACY
    sim_log_path = RESULTS_DIR / model / group / "Run_1" / "simulation_log.csv"
    if sim_log_path.exists():
        sim_df = pd.read_csv(sim_log_path)
        total_active_steps = len(sim_df)
    else:
        # Fallback to log pattern
        if group == "Group_A":
            total_active_steps = count_pattern(log_path, "Decision:") + count_pattern(log_path, "Skill:")
        else:
            total_active_steps = count_pattern(log_path, "--- Executing Step")

    # 6. Adjust Hallucinations for Group A
    # For A, we look for signs of technical instability in the raw log.
    if group == "Group_A":
        # In Native Group A, "TP=" appears if the model failed to follow the template
        # or hallucinated fields.
        p_hallucinations = count_pattern(log_path, "TP=")
        # Check for parse errors
        p_invalid_labels = count_pattern(log_path, "Invalid _LABEL")
        p_missing_constructs = count_pattern(log_path, "Missing required constructs")

    return {
        "Model": model,
        "Group": group,
        "Steps": total_active_steps,
        "Retries_Total": total_gov_retries + total_broker_retries + total_llm_retries,
        "Err_Labels": p_invalid_labels,
        "Err_Constructs": p_missing_constructs,
        "Err_Schema": p_schema_missing,
        "Err_Empty": p_empty,
        "Err_Hallucination": p_hallucinations,
        "Intv_S_Audit": s_rule_blocks,
        "Intv_P_Audit": p_invalid_labels + p_missing_constructs + p_schema_missing + p_empty + p_hallucinations
    }

print("=== STARTING REFINED TECHNICAL AUDIT (V3) ===")
audit_results = []
for m in models:
    for g in groups:
        res = audit_log(m, g)
        if res:
            audit_results.append(res)
            print(f"Audited {m} {g}: {res['Intv_S_Audit']} Safety Blocks, {res['Intv_P_Audit']} Stability Issues.")

if audit_results:
    df_audit = pd.DataFrame(audit_results)
    df_audit.to_csv(OUTPUT_DIR / "technical_retry_audit_v3.csv", index=False)
    print(f"\n[System] Refined audit report saved to: {OUTPUT_DIR / 'technical_retry_audit_v3.csv'}")
else:
    print("No audit results found.")
