
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import scipy.stats as stats

# Configuration
SCRIPT_DIR = Path(__file__).parent
BASE_RESULTS = SCRIPT_DIR.parent / "results" / "JOH_FINAL"
OUTPUT_DIR = SCRIPT_DIR / "analysis" / "reports" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODELS = ["gemma3_4b", "llama3_2_3b"]
GROUPS = ["Group_A", "Group_B", "Group_C"]

# --- HELPER FUNCTIONS ---

def get_flood_years(audit_df):
    # Heuristic: Find years where 'reason_tp_label' or narrative mentions flood being active
    # Or just hardcode based on known simulation seed if available. 
    # For now, we assume standard flood schedule (Year 1, 4, 7, etc.) if not detectable.
    # But better to detect "High Threat" appraisal as proxy for flood year.
    if 'reason_tp_label' in audit_df.columns:
        # If label is High/Critical, it's likely a flood year
        return audit_df[audit_df['reason_tp_label'].str.lower().str.contains('high|critical', na=False)]['year'].unique()
    return []

def detect_mismatch(row):
    # Thinking-Doing Gap (Silent Failure)
    # Target: Agent SAYS "I will elevate" or "choose to elevate" but Action is "do_nothing"
    reason = str(row.get('reason_reasoning', '')).lower() # Use actual decision reasoning
    action = str(row.get('proposed_skill', '')).lower()
    
    # Simple Intent Heuristics
    # "decision is to elevate", "choose to elevate", "will elevate", "intend to elevate"
    # "buying insurance", "purchase insurance"
    intent_elevate = "elevate" in reason and ("choose" in reason or "decid" in reason or "will" in reason) and "not" not in reason 
    intent_insure = "insurance" in reason and ("buy" in reason or "purchas" in reason) and "not" not in reason 
    intent_relocate = "relocate" in reason and ("choose" in reason or "decid" in reason) and "not" not in reason
    
    intent_action = intent_elevate or intent_insure or intent_relocate
    
    if action == "do_nothing" and intent_action:
        return True
    return False

def get_action_intensity(row):
    skill = str(row.get('proposed_skill', '')).lower()
    if 'relocate' in skill: return 3
    if 'elevate' in skill: return 2
    if 'insurance' in skill: return 1
    return 0

def get_threat_score(row):
    label = str(row.get('reason_tp_label', '')).upper()
    if 'H' in label or 'HIGH' in label or 'CRITICAL' in label: return 3
    if 'M' in label or 'MEDIUM' in label: return 2
    if 'L' in label or 'LOW' in label: return 1
    if 'VL' in label or 'VERY' in label: return 0
    return 0 # Default/Unknown

# --- METRIC CALCULATORS ---

def analyze_model_group(model, group):
    path = BASE_RESULTS / model / group
    if not path.exists(): return None
    
    stats = {
        "Model": model, "Group": group,
        "Runs": 0, "TotalSteps": 0,
        "AdaptationRate": 0.0,
        "Retries": 0, "Mismatches": 0,
        "IF_All": np.nan, "IF_Flood": np.nan, # Internal Fidelity
        "RS": np.nan # Rationality
    }
    
    runs = list(path.glob("Run_*"))
    stats["Runs"] = len(runs)
    
    # Aggregators
    all_threats = []
    all_actions = []
    flood_threats = []
    flood_actions = []
    
    total_agents = 0
    adapted_agents = 0
    
    for run in runs:
        # 1. Audit Log (Process Logic)
        audits = list(run.rglob("household_governance_audit.csv"))
        if audits:
            try:
                df = pd.read_csv(audits[0])
                stats["TotalSteps"] += len(df)
                
                # Gap Analysis
                if 'retry_count' in df: stats["Retries"] += df['retry_count'].sum()
                if 'reason_tp_reason' in df:
                    stats["Mismatches"] += df.apply(lambda r: 1 if detect_mismatch(r) else 0, axis=1).sum()
                
                # Metric 2: Internal Fidelity (IF)
                # We need columns: threat_score, action_intensity
                df['threat'] = df.apply(get_threat_score, axis=1)
                df['action'] = df.apply(get_action_intensity, axis=1)
                
                all_threats.extend(df['threat'].tolist())
                all_actions.extend(df['action'].tolist())
                
                # Refined IF: Filter for Flood Years (Threat >= 2)
                # "Fidelity only matters when it matters"
                flood_df = df[df['threat'] >= 2]
                flood_threats.extend(flood_df['threat'].tolist())
                flood_actions.extend(flood_df['action'].tolist())

            except: pass

        # 2. Simulation Log (Outcomes)
        sim_log = run / "simulation_log.csv"
        if sim_log.exists():
            try:
                sdf = pd.read_csv(sim_log)
                final = sdf.sort_values('year').groupby('agent_id').last()
                total_agents += len(final)
                adapted = final[
                    (final['elevated'] == True) | 
                    (final['has_insurance'] == True) | 
                    (final['relocated'] == True)
                ]
                adapted_agents += len(adapted)
            except: pass

    # Calculate Final Metrics
    if total_agents > 0:
        stats["AdaptationRate"] = (adapted_agents / total_agents) * 100
        
    # IF Calculation (Correlation)
    if len(all_threats) > 10 and np.std(all_threats) > 0 and np.std(all_actions) > 0:
        stats["IF_All"] = np.corrcoef(all_threats, all_actions)[0, 1]
    else:
        stats["IF_All"] = 0 # No variance usually means 0 fidelity in this context (blind action or inaction)
        
    if len(flood_threats) > 10 and np.std(flood_threats) > 0 and np.std(flood_actions) > 0:
        stats["IF_Flood"] = np.corrcoef(flood_threats, flood_actions)[0, 1]
    elif len(flood_threats) > 0:
        stats["IF_Flood"] = 0 # High threat but constant action (e.g. 0) -> 0 Fidelity
        
    return stats

def run_analysis():
    print("Running Consolidated Analysis...")
    results = []
    
    for m in MODELS:
        for g in GROUPS:
            s = analyze_model_group(m, g)
            if s: results.append(s)
            
    df = pd.DataFrame(results)
    
    # Calculate Rates
    df['GapRate%'] = df.apply(lambda r: (r['Mismatches']/r['TotalSteps']*100) if r['TotalSteps']>0 else 0, axis=1)
    
    # Display Table
    print("\n--- Comprehensive Metric Table ---")
    cols = ['Model', 'Group', 'AdaptationRate', 'GapRate%', 'IF_All', 'IF_Flood']
    print(df[cols].to_string(index=False, float_format="%.4f"))
    
    # Save CSV
    df.to_csv(OUTPUT_DIR.parent / "comprehensive_metrics.csv", index=False)
    print(f"\nSaved metrics to {OUTPUT_DIR.parent / 'comprehensive_metrics.csv'}")

if __name__ == "__main__":
    run_analysis()
