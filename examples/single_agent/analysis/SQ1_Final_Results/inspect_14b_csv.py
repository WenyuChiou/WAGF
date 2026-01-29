
import pandas as pd
from pathlib import Path

csv_path = Path("examples/single_agent/results/JOH_FINAL/deepseek_r1_14b/Group_A/Run_1/simulation_log.csv")
if csv_path.exists():
    df = pd.read_csv(csv_path)
    print("Columns:", df.columns.tolist())
    print("\nDecision value counts:")
    dec_col = 'decision' if 'decision' in df.columns else 'yearly_decision'
    print(df[dec_col].value_counts().head(5))
else: print("File not found")
