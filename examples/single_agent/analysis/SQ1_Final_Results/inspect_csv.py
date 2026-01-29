
import pandas as pd
from pathlib import Path

csv_path = Path("examples/single_agent/results/JOH_FINAL/deepseek_r1_8b/Group_A/Run_1/simulation_log.csv")
if csv_path.exists():
    df = pd.read_csv(csv_path)
    print("Columns:", df.columns.tolist())
    print("\nFirst 5 rows:")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(df.head(5))
else:
    print("File not found")
