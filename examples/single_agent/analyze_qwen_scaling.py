import os
import json
import pandas as pd
import numpy as np
import glob

# Configuration
RESULTS_ROOT = "results/JOH_FINAL"
MODELS = ["qwen3_1_7b", "qwen3_4b", "qwen3_7b", "qwen3_14b", "qwen3_32b"]
GROUPS = ["Group_A", "Group_B", "Group_C"]

# Metric Definitions matching Manuscript (Section 3.2.2)
METRIC_A_NAME = "Metric_A_SRR"        # Stability: Self-Repair Rate (% of raw outputs blocked by SkillBroker)
METRIC_B_NAME = "Metric_B_Fidelity"   # Alignment: Fidelity Gap (Accuracy of Action given Threat)
METRIC_C_NAME = "Metric_C_T_gov"      # Efficiency: Governance Tax (Induced Semantic Volume / Reasoning Length)

def analyze_model_metrics(model_dir):
    """
    Extracts core scaling metrics for a given model directory.
    Returns a dict with:
      - Metric_A_SRR (Stabilization)
      - Metric_B_Fidelity (Alignment)
      - Metric_C_T_gov (Efficiency Cost)
    """
    metrics = {}
    
    # Iterate through Groups
    for group in GROUPS:
        # Initialize with NaN
        metrics[f"{group}_{METRIC_A_NAME}"] = np.nan
        metrics[f"{group}_{METRIC_B_NAME}"] = np.nan
        metrics[f"{group}_{METRIC_C_NAME}"] = np.nan
        
        # Find trace file recursively
        run_dir = os.path.join(model_dir, group, "Run_1")
        trace_files = glob.glob(os.path.join(run_dir, "**", "household_traces.jsonl"), recursive=True)
        
        # Fallback: try looking one level up if structure varies
        if not trace_files:
            trace_files = glob.glob(os.path.join(model_dir, group, "**", "household_traces.jsonl"), recursive=True)
            
        trace_path = trace_files[0] if trace_files else None
        
        if trace_path and os.path.exists(trace_path):
            try:
                # --- PROCESS JSONL TRACES (Groups B/C) ---
                # Data for Alignment Calculation
                threat_levels = [] # 0=Low (VL, L), 1=High (M, H, VH)
                action_types = []  # 0=Passive (do_nothing), 1=Active
                
                retries = []
                reasoning_lens = []
                
                with open(trace_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            record = json.loads(line)
                            
                            # --- Metric A: SRR ---
                            # Extract Retry Count (SRR)
                            r_count = record.get('retry_count', 0)
                            retries.append(r_count)
                            
                            # --- Metric C: T_gov ---
                            # Extract Reasoning Length
                            r_len = 0
                            raw = record.get('raw_output')
                            
                            # Safe extraction of JSON from raw_output
                            raw_json = {}
                            if isinstance(raw, str):
                                try:
                                    raw_json = json.loads(raw)
                                except:
                                    # Start of JSON check if mixed with text
                                    if "{" in raw and "}" in raw:
                                        try:
                                            start = raw.find("{")
                                            end = raw.rfind("}") + 1
                                            raw_json = json.loads(raw[start:end])
                                        except:
                                            pass
                            elif isinstance(raw, dict):
                                raw_json = raw
                                
                            # Get reasoning length
                            if isinstance(raw_json, dict) and 'reasoning' in raw_json:
                                r_len = len(str(raw_json.get('reasoning', '')))
                            elif isinstance(raw, str):
                                r_len = len(raw) # Fallback
                                
                            reasoning_lens.append(r_len)
                            
                            # --- Metric B: Fidelity ---
                            # 1. Get Threat Appraisal (VL/L vs M/H/VH)
                            t_label = 'L'
                            if isinstance(raw_json, dict):
                                t_data = raw_json.get('threat_appraisal', {})
                                if isinstance(t_data, dict):
                                    t_label = t_data.get('label', 'L')
                            
                            is_high_threat = str(t_label).upper() in ['M', 'H', 'VH']
                            threat_levels.append(1 if is_high_threat else 0)
                            
                            # 2. Get Action (Passive vs Active)
                            skill = "do_nothing"
                            if record.get('approved_skill'):
                                skill = record['approved_skill'].get('skill_name', 'do_nothing')
                            
                            # Active = anything NOT do_nothing (and not numeric 4)
                            s_str = str(skill).lower()
                            is_active = s_str not in ['do_nothing', '4', 'nan', 'none']
                            action_types.append(1 if is_active else 0)
                            
                        except Exception:
                            continue
                
                # --- Calculate Aggregates (JSONL) ---
                if retries:
                    intervention_count = sum(1 for r in retries if r > 0)
                    metrics[f"{group}_{METRIC_A_NAME}"] = intervention_count / len(retries)
                    
                if threat_levels and action_types:
                    matches = sum(1 for t, a in zip(threat_levels, action_types) if t == a)
                    valid_count = len(threat_levels)
                    if valid_count > 0:
                        metrics[f"{group}_{METRIC_B_NAME}"] = matches / valid_count
                        
                if reasoning_lens:
                    metrics[f"{group}_{METRIC_C_NAME}"] = np.mean(reasoning_lens)
                    
            except Exception as e:
                print(f"Error processing trace {trace_path}: {e}")

        else:
             # --- FALLBACK: PROCESS CSV LOGS (Group A) ---
             # Group A (No Monitor) doesn't produce structural traces, but has simulation_log.csv
             csv_files = glob.glob(os.path.join(run_dir, "simulation_log.csv"))
             
             if not csv_files:
                 # Check parent if flat
                 csv_files = glob.glob(os.path.join(model_dir, group, "**", "simulation_log.csv"), recursive=True)
            
             if csv_files:
                 csv_path = csv_files[0]
                 try:
                     df = pd.read_csv(csv_path)
                     
                     # Metric A: SRR
                     # For Group A (Ungoverned), SRR is 0 by definition (no governance repair).
                     metrics[f"{group}_{METRIC_A_NAME}"] = 0.0
                     
                     # Metric C: T_gov (Reasoning Load)
                     # Proxy: Length of 'threat_appraisal' + 'coping_appraisal' text columns
                     if 'threat_appraisal' in df.columns and 'coping_appraisal' in df.columns:
                         df['reasoning_len'] = df['threat_appraisal'].fillna("").astype(str).str.len() + \
                                               df['coping_appraisal'].fillna("").astype(str).str.len()
                         metrics[f"{group}_{METRIC_C_NAME}"] = df['reasoning_len'].mean()
                     
                     # Metric B: Fidelity (Alignment)
                     # Heuristic parsing of Threat Text
                     if 'threat_appraisal' in df.columns and 'decision' in df.columns:
                         high_threat_keywords = ['moderate', 'high', 'significant', 'severe', 'growing', 'rising', 'threatened']
                         # Function to detect high threat
                         def is_high_threat(text):
                             text = str(text).lower()
                             for kw in high_threat_keywords:
                                 if kw in text:
                                     return 1
                             return 0 # Default to Low
                             
                         df['threat_numeric'] = df['threat_appraisal'].apply(is_high_threat)
                         
                         # Action: Active vs Passive
                         # "Do Nothing" = 0, anything else = 1
                         df['action_numeric'] = df['decision'].apply(lambda x: 0 if str(x).lower() == 'do nothing' else 1)
                         
                         # Calculate Fidelity (Accuracy)
                         matches = (df['threat_numeric'] == df['action_numeric']).sum()
                         metrics[f"{group}_{METRIC_B_NAME}"] = matches / len(df)
                         
                 except Exception as e:
                     print(f"Error processing CSV {csv_path}: {e}")
            
    return metrics

def main():
    print("=== Qwen Scaling Law Analysis (Metrics A, B, C) ===")
    results = []
    
    # Analyze standard experiments
    for model in MODELS:
        model_path = os.path.join(RESULTS_ROOT, model)
        if os.path.exists(model_path):
            print(f"Analyzing {model}...")
            m = analyze_model_metrics(model_path)
            m['Model'] = model
            results.append(m)
        else:
            # print(f"Skipping {model} - Not found in {RESULTS_ROOT}")
            pass
        
    if results:
        final_df = pd.DataFrame(results)
        # Reorder columns: Model, then A, B, C for each group
        cols = ['Model']
        for group in GROUPS:
            cols.append(f"{group}_{METRIC_A_NAME}")
            cols.append(f"{group}_{METRIC_B_NAME}")
            cols.append(f"{group}_{METRIC_C_NAME}")
            
        # Filter cols that exist
        cols = [c for c in cols if c in final_df.columns]
        final_df = final_df[cols]
        
        print("\n--- Summary Table ---")
        print(final_df.to_string())
        
        # Save
        csv_path = "qwen_scaling_metrics_ABC.csv"
        final_df.to_csv(csv_path, index=False)
        print(f"\nSaved to {csv_path}")
    else:
        print("No results found in results/JOH_FINAL yet.")

if __name__ == "__main__":
    main()
