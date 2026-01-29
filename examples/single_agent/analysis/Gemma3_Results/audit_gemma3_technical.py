
import pandas as pd
import re
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
OUTPUT_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\Gemma3_Results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

models = ["gemma3_1b", "gemma3_4b", "gemma3_12b", "gemma3_27b"]
groups = ["Group_A", "Group_B", "Group_C"]

def count_pattern_in_text(text, pattern_str, exclude_pattern=None):
    flags = re.MULTILINE | re.IGNORECASE
    if exclude_pattern:
        # Simple line-by-line filter
        count = 0
        for line in text.splitlines():
            if re.search(pattern_str, line, flags) and not re.search(exclude_pattern, line, flags):
                count += 1
        return count
    else:
        return len(re.findall(pattern_str, text, flags))

def audit_log(model, group):
    log_path = BASE_DIR / model / group / "Run_1" / "execution.log"
    if not log_path.exists():
        # print(f"Log not found for {model} {group}")
        return None
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = f.read()
            
        # 1. Parse-Level Failures
        p_invalid_labels = count_pattern_in_text(log_content, "Invalid _LABEL values")
        p_missing_constructs = count_pattern_in_text(log_content, "Missing required constructs")
        p_schema_missing = count_pattern_in_text(log_content, "Response missing required fields")
        p_empty = count_pattern_in_text(log_content, "Empty/Null response")
        
        # 2. Hallucinations
        # "TP=" usually indicates a parsing attempt extracting TP/CP values.
        # In Group A, if it appears outside of structured reasoning (which A doesn't strictly enforce?), 
        # or if it implies the model is trying to fake the format.
        # Framework logs "- Constructs:" which might contain TP=, we want to ignore that debug log.
        p_hallucinations = count_pattern_in_text(log_content, "TP=", exclude_pattern="- Constructs:")
        
        # 3. Semantic/Policy Blocks
        s_rule_blocks = count_pattern_in_text(log_content, "failed validation")
        
        # 4. Total Retries
        total_gov_retries = count_pattern_in_text(log_content, r"\[Governance:Retry\]")
        total_broker_retries = count_pattern_in_text(log_content, r"\[Broker:Retry\]")
        total_llm_retries = count_pattern_in_text(log_content, r"\[LLM:Retry\]")
        
        # 5. Total Active Steps (N)
        sim_log_path = BASE_DIR / model / group / "Run_1" / "simulation_log.csv"
        total_active_steps = 0
        if sim_log_path.exists():
            try:
                sim_df = pd.read_csv(sim_log_path)
                total_active_steps = len(sim_df)
            except: pass
            
        if total_active_steps == 0:
            # Fallback
            if group == "Group_A":
                total_active_steps = count_pattern_in_text(log_content, "Decision:")
            else:
                total_active_steps = count_pattern_in_text(log_content, "--- Executing Step")

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

    except Exception as e:
        print(f"Error processing {model} {group}: {e}")
        return None

print("=== STARTING GEMMA 3 TECHNICAL AUDIT ===")
audit_results = []
for m in models:
    for g in groups:
        res = audit_log(m, g)
        if res:
            audit_results.append(res)
            print(f"Audited {m} {g}: {res['Intv_S_Audit']} Safety Blocks, {res['Retries_Total']} Retries.")

if audit_results:
    df_audit = pd.DataFrame(audit_results)
    out_path = OUTPUT_DIR / "technical_retry_audit_gemma3.csv"
    df_audit.to_csv(out_path, index=False)
    print(f"\nSaved audit report to: {out_path}")
else:
    print("No audit results found.")
