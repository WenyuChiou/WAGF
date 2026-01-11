
import pandas as pd
from pathlib import Path
import sys

def analyze():
    base = Path("results_v4.2")
    models = ["llama3/llama3.2_3b", "gemma/gemma3_4b", "gpt-oss/gpt-oss_latest", "deepseek/deepseek-r1_8b"]
    
    output = []
    output.append("Behavior Distribution Report:")
    for m in models:
        p = base / m / "simulation_log.csv"
        if not p.exists():
            output.append(f"\n--- {m} ---")
            output.append("  (File not found or simulation not started)")
            continue
            
        try:
            df = pd.read_csv(p)
            if df.empty:
                output.append(f"\n--- {m} ---")
                output.append("  (Log empty)")
                continue
                
            last_year = df['year'].max()
            last_year_data = df[df['year'] == last_year]
            
            dist = last_year_data['cumulative_state'].value_counts(normalize=True).mul(100).round(1)
            
            output.append(f"\n--- {m} (Year {last_year}) ---")
            output.append(dist.to_string())
            output.append(f"  Total Agents: {len(last_year_data)}")
            
        except Exception as e:
            output.append(f"\n--- {m} ---")
            output.append(f"  Error: {e}")

    with open("analysis_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    analyze()
