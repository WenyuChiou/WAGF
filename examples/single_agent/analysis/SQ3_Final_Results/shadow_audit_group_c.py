import pandas as pd
import os

def shadow_audit(csv_path):
    if not os.path.exists(csv_path):
        return None
    
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    
    # Mapping for different versions
    tp_col = None
    for c in ['threat_appraisal', 'tp_label', 'tp']:
        if c in df.columns:
            tp_col = c
            break
            
    dec_col = None
    for c in ['yearly_decision', 'decision', 'action']:
        if c in df.columns:
            dec_col = c
            break
    
    if tp_col is None or dec_col is None:
        print(f"Columns not found in {csv_path}: {df.columns}")
        return None

    # Standardize appraisals to uppercase
    df['tp'] = df[tp_col].astype(str).str.upper()
    
    # Normalize labels (Group A might use "Low", Group B uses "L")
    label_map = {
        'VERY LOW': 'VL', 'LOW': 'L', 'MEDIUM': 'M', 'HIGH': 'H', 'VERY HIGH': 'VH',
        'VL': 'VL', 'L': 'L', 'M': 'M', 'H': 'H', 'VH': 'VH'
    }
    df['tp'] = df['tp'].apply(lambda x: label_map.get(x, x))
    
    # Normalize decisions (Group A uses "Relocate", Group B uses "relocate" or skill-id)
    def normalize_dec(val):
        val = str(val).lower()
        if 'relocate' in val: return 'relocate'
        if 'elevate' in val: return 'elevate_house'
        if 'insurance' in val: return 'buy_insurance'
        if 'do nothing' in val or 'nothing' in val: return 'do_nothing'
        return val
        
    df['decision_cln'] = df[dec_col].apply(normalize_dec)
    
    reloc_violations = len(df[(df['decision_cln'] == 'relocate') & (df['tp'].isin(['VL', 'L']))])
    elev_violations = len(df[(df['decision_cln'] == 'elevate_house') & (df['tp'].isin(['VL', 'L']))])
    complacency_violations = len(df[(df['decision_cln'] == 'do_nothing') & (df['tp'] == 'VH')])
    
    return {
        "total_rows": len(df),
        "reloc_violations": reloc_violations,
        "elev_violations": elev_violations,
        "complacency_violations": complacency_violations,
        "total_violations": reloc_violations + elev_violations + complacency_violations
    }

root = "examples/single_agent/results/JOH_FINAL"
targets = [
    ("1.5B_A", f"{root}/deepseek_r1_1_5b/Group_A/Run_1/simulation_log.csv"),
    ("1.5B_C", f"{root}/deepseek_r1_1_5b/Group_C/Run_1/simulation_log.csv"),
    ("8B_A", f"{root}/deepseek_r1_8b/Group_A/Run_1/simulation_log.csv"),
    ("8B_C", f"{root}/deepseek_r1_8b/Group_C/Run_1/simulation_log.csv"),
    ("14B_A", f"{root}/deepseek_r1_14b/Group_A/Run_1/simulation_log.csv"),
    ("14B_C", f"{root}/deepseek_r1_14b/Group_C/Run_1/simulation_log.csv"),
]

print(f"{'Run':<10} {'Rows':<6} {'Reloc-V':<10} {'Elev-V':<10} {'Compl-V':<10} {'Sum'}")
for name, path in targets:
    res = shadow_audit(path)
    if res:
        print(f"{name:<10} {res['total_rows']:<6} {res['reloc_violations']:<10} {res['elev_violations']:<10} {res['complacency_violations']:<10} {res['total_violations']}")
    else:
        print(f"{name:<10} MISSING")
