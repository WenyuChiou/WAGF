import pandas as pd
import os

BASE_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL"
GROUP = "Group_C"

def normalize_decision(d):
    d = str(d).lower()
    if 'relocat' in d: return 'Relocate'
    if 'elevat' in d: return 'Elevation'
    if 'insur' in d: return 'Insurance'
    if 'do' in d or 'nothing' in d: return 'DoNothing'
    return 'Other'

def check_violations():
    # Check 14B Group C (Flat structure observed)
    path = os.path.join(BASE_DIR, "deepseek_r1_14b", "Group_C", "Run_1", "household_governance_audit.csv")
    if not os.path.exists(path):
        print(f"Audit log not found at {path}")
        return
    
    df = pd.read_csv(path)
    
    # Audit log columns: 'reason_threat_appraisal' (JSON string/dict) or 'reason_tp_label'
    
    def is_low_threat(row):
        # Prefer specific label column if exists
        label = str(row.get('reason_tp_label', '')).upper()
        if label in ['L', 'VL']: return True
        
        # Fallback to reason text
        t = str(row.get('reason_threat_appraisal', '')).upper()
        if 'VL' in t or 'Label: L' in t or 'Low' in t or 'Minimal' in t: 
            return True
        return False
        
    df['is_panic_state'] = df.apply(is_low_threat, axis=1)
    panic_df = df[df['is_panic_state']]
    
    # Audit log 'final_skill' is the decision
    v1_count = panic_df['final_skill'].apply(lambda x: normalize_decision(x) == 'Relocate').sum()
    v2_count = panic_df['final_skill'].apply(lambda x: normalize_decision(x) == 'Elevation').sum()
    
    print(f"--- {GROUP} Re-Verification (From Audit Log) ---")
    print(f"Total Steps: {len(df)}")
    print(f"Panic States (L/VL) Found: {len(panic_df)}")
    print(f"V1 Violations (Relocate | Low): {v1_count}")
    print(f"V2 Violations (Elevate  | Low): {v2_count}")

check_violations()
