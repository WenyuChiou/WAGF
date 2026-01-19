
import pandas as pd
import numpy as np
from sklearn.metrics import matthews_corrcoef, confusion_matrix
import os
import argparse

def parse_binary_threat(memory_str):
    """
    Parses agent memory to determine BINARY Internal Threat.
    Theory: PMT (Protection Motivation)
    TRUE (1) = "I feel threatened" (Flood occurred, damage, neighbors fleeing)
    FALSE (0) = "I feel safe" (No flood, house protected)
    """
    if pd.isna(memory_str): return 0
    mem = str(memory_str).lower()
    
    # Strong Threat Indicators
    if "got flooded" in mem or "damage on my house" in mem: return 1
    if "severe enough to cause damage" in mem: return 1
    # if "relocated" in mem and "neighbors" in mem: return 1 # Social proof threat - DISABLED: false positives on 0% prompt

    
    # "House was protected" -> Technically a threat occurred, but coping is high. 
    # For Fidelity, if they don't act further (already elevated), it's rational.
    # But if they are NOT elevated and flood occurs -> Threat=1.
    return 0

def parse_binary_action(decision_str, current_state_elevated):
    """
    Parses decision to determine BINARY Action.
    TRUE (1) = Active Adaptation (Buy Insurance, Elevate, Relocate)
    FALSE (0) = Do Nothing / Maintain Status Quo
    """
    if pd.isna(decision_str): return 0
    d = str(decision_str).lower().strip()
    
    # Inaction
    if d in ["do nothing", "do_nothing", "n/a", "4", "3"]: return 0 # 3 is sometimes 'Do nothing' in legacy prompt if elevated
    if "do nothing" in d: return 0
    
    # Active Action
    if "relocated" in d or "relocate" in d: return 1
    if "elevate" in d or "elevation" in d: return 1
    if "insurance" in d: return 1
    
    # Legacy specific (Capitalized full phrases)
    # "Only House Elevation", "Only Flood Insurance", "Both..."
    if "elevation" in d or "insurance" in d: return 1
    
    return 0

def calculate_mcc_metrics(df):
    """
    Calculates MCC and irrationality types.
    """
    # 1. Binarize
    y_true = df['memory'].apply(parse_binary_threat) # Internal Threat (The "Ground Truth" of their mind)
    
    # We need to know if they *acted* this year. 
    # If logs show cumulative state, we might overcount. 
    # Assuming 'yearly_decision' reflects the CHOICE made that year.
    y_pred = df['yearly_decision'].apply(lambda x: parse_binary_action(x, False)) # External Action
    
    # Filter N/A
    valid_mask = df['yearly_decision'] != 'N/A'
    y_true = y_true[valid_mask]
    y_pred = y_pred[valid_mask]
    
    # DEBUG: Print sample for Llama Group A
    # We can detect via length or just print first few of any run
    if len(y_true) > 0 and y_pred.sum() > 0: # If any action
        print(f"DEBUG SAMPLE (Action Sum={y_pred.sum()}):")
        for i in range(min(5, len(y_true))):
            print(f"  T={y_true.iloc[i]} A={y_pred.iloc[i]} | Mem='{df['memory'].iloc[i][:30]}' | Dec='{df['yearly_decision'].iloc[i]}'")
            
    if len(y_true) < 5: return np.nan, 0, 0, 0
    
    # 3. Error Types
    # Calculate these BEFORE returning for zero variance
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    
    # Type I (Panic): Threat=0, Action=1 (False Positive)
    panic_rate = fp / len(y_true) if len(y_true) > 0 else 0
    
    # Type II (Complacency): Threat=1, Action=0 (False Negative)
    complacency_rate = fn / len(y_true) if len(y_true) > 0 else 0
    
    # 2. MCC
    # Handle zero variance safety
    if len(np.unique(y_true)) < 2 or len(np.unique(y_pred)) < 2:
        # constant prediction matches
        if np.array_equal(y_true.values, y_pred.values):
             return 1.0, panic_rate, complacency_rate, len(y_true), tn, fp, fn, tp
        return 0.0, panic_rate, complacency_rate, len(y_true), tn, fp, fn, tp
        
    mcc = matthews_corrcoef(y_true, y_pred)
    
    return mcc, panic_rate, complacency_rate, len(y_true), tn, fp, fn, tp

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", type=str, default="results/JOH_FINAL")
    args = parser.parse_args()
    
    results = []
    
    print(f"Scanning {args.base_dir}...")
    
    for model in os.listdir(args.base_dir):
        path_model = os.path.join(args.base_dir, model)
        if not os.path.isdir(path_model) or model == "JOH_STRESS": continue
        
        for group in ["Group_A", "Group_B", "Group_C"]:
            path_group = os.path.join(path_model, group)
            if not os.path.exists(path_group): continue
            
            for run in os.listdir(path_group):
                if not run.startswith("Run_"): continue
                
                # Robustly find log file (handle nested "gemma3_4b_disabled" etc)
                run_dir = os.path.join(path_group, run)
                log_path = os.path.join(run_dir, "simulation_log.csv")
                
                if not os.path.exists(log_path):
                    # Deep search using recursive glob
                    from pathlib import Path
                    found = list(Path(run_dir).rglob("simulation_log.csv"))
                    if found:
                        log_path = str(found[0])
                    else:
                        continue 
                
                if not os.path.exists(log_path): continue
                
                try:
                    df = pd.read_csv(log_path)
                    
                    # Legacy Mapping
                    if 'yearly_decision' not in df.columns and 'decision' in df.columns:
                        df.rename(columns={'decision': 'yearly_decision'}, inplace=True)
                        
                    if 'memory' not in df.columns or 'yearly_decision' not in df.columns: continue
                    
                    mcc, panic, comp, n, tn, fp, fn, tp = calculate_mcc_metrics(df)
                    
                    results.append({
                        "Model": model,
                        "Group": group,
                        "Run": run,
                        "MCC": mcc,
                        "Panic_Rate": panic,
                        "Complacency_Rate": comp,
                        "N": n,
                        "TN": tn, "FP": fp, "FN": fn, "TP": tp
                    })
                except Exception as e:
                    print(f"Error {log_path}: {e}")
                    
    # Summary
    df_res = pd.DataFrame(results)
    if df_res.empty:
        print("No metrics calculated.")
        return
        
    summary = df_res.groupby(['Model', 'Group'])[['MCC', 'Panic_Rate', 'Complacency_Rate']].agg(['mean', 'std'])
    print("\n=== Agent Rationality Analysis (MCC) ===")
    print(summary)
    
    metrics_dir = os.path.join(args.base_dir, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)
    
    out_path = os.path.join(metrics_dir, "mcc_analysis_all.csv")
    df_res.to_csv(out_path, index=False)
    print(f"\n✅ Saved consolidated MCC analysis to: {out_path}")

if __name__ == "__main__":
    main()
