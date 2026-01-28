
import pandas as pd
log = "examples/single_agent/results/JOH_FINAL/deepseek_r1_1_5b/Group_B/Run_1/simulation_log.csv"
df = pd.read_csv(log)
df.columns = [c.lower() for c in df.columns]
print("Columns:", df.columns)
dec_col = 'yearly_decision'
print(f"Using Decision Col: {dec_col}")
if dec_col in df.columns:
    relocs = df[df[dec_col].astype(str).str.contains('relocate', case=False, na=False)] 
    print("Unique Threat Values for 1.5B Group B Relocations:")
    print(relocs['threat_appraisal'].unique())
