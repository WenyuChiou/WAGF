
import sys
from pathlib import Path

# Add the directory to path so we can import get_stats
sys.path.append(str(Path("examples/single_agent/analysis/SQ1_Final_Results").absolute()))

try:
    from master_report import get_stats
    
    models = ["deepseek_r1_1_5b", "deepseek_r1_14b"]
    groups = ["Group_B", "Group_C"]
    
    for m in models:
        for g in groups:
            res = get_stats(m, g)
            print(f"--- {m} {g} ---")
            if res:
                for k, v in res.items():
                    print(f"{k}: {v}")
            else:
                print("No data found.")
except Exception as e:
    print(f"Error: {e}")
