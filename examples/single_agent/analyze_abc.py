import pandas as pd
import numpy as np
import os
from pathlib import Path
import json

# Configuration
PROJECT_ROOT = Path("H:/我的雲端硬碟/github/governed_broker_framework")
RESULTS_DIR = PROJECT_ROOT / "examples/single_agent/results"
ROOT_RESULTS = PROJECT_ROOT / "results"  # Catch misplaced data
REPORT_DIR = PROJECT_ROOT / "examples/single_agent/analysis/reports"

class ABCAnalyzer:
    def __init__(self):
        self.roots = [RESULTS_DIR, ROOT_RESULTS]
        self.groups = ["Group A", "Group B", "Group C"] 
        self.models = ["llama3.2:3b", "gemma3:4b", "deepseek-r1:8b", "gpt-oss"]
        self.model_map = {
            "llama3.2:3b": "Llama 3.2",
            "gemma3:4b": "Gemma 3",
            "deepseek-r1:8b": "DeepSeek R1",
            "gpt-oss": "GPT-OSS"
        }

    def find_run_dirs(self, group, model_id):
        found = []
        safe_model = model_id.replace(":", "_").replace("-", "_").replace(".", "_")
        
        # Mapping Groups to sub-paths or naming conventions
        # Group A: Legacy (no governance)
        # Group B: Standard (governance only)
        # Group C: Enhanced (governance + cognitive)
        
        for root in self.roots:
            # Check for legacy Group A in 'old_results' or 'results_fixed' if they exist
            if group == "Group A":
                # Look for baseline runs (often named without human/strict in old structure)
                legacy_candidates = [root / "old_results", root / "results_fixed", root / "JOH_FINAL"]
                for cand in legacy_candidates:
                    if not cand.exists(): continue
                    # Search specifically for non-governed or baseline folders for the model
                    for path in cand.rglob("simulation_log.csv"):
                        # Group A shouldn't have 'human' or 'strict' in path if it's pure legacy
                        if safe_model in str(path) and "human" not in str(path).lower() and "strict" not in str(path).lower():
                            found.append(path.parent)
            
            # Check for current JOH structure
            base_dir = root / "JOH_FINAL"
            if base_dir.exists():
                model_dir = base_dir / safe_model
                if model_dir.exists():
                    for path in model_dir.rglob("simulation_log.csv"):
                        is_human = "human" in str(path).lower()
                        if group == "Group C" and is_human:
                            found.append(path.parent)
                        elif group == "Group B" and not is_human and "strict" in str(path).lower():
                            found.append(path.parent)
        return list(set(found))

    def calculate_metrics(self, df):
        if df.empty: return None
        final_yr = df['year'].max()
        final = df[df['year'] == final_yr]
        if len(final) == 0: return None
        
        adaptation_rate = len(final[(final['elevated'] == True) | (final['has_insurance'] == True)]) / len(final)
        relocation_rate = len(final[final['relocated'] == True]) / len(final)
        return {
            "adaptation": adaptation_rate,
            "relocation": relocation_rate
        }

    def run(self):
        print("--- Macro Benchmark ABC Analysis ---")
        results = []
        for model in self.models:
            model_results = {"model": self.model_map[model]}
            for group in self.groups:
                dirs = self.find_run_dirs(group, model)
                metrics_list = []
                for d in dirs:
                    df = pd.read_csv(d / "simulation_log.csv")
                    m = self.calculate_metrics(df)
                    if m: metrics_list.append(m)
                
                if metrics_list:
                    avg_ad = np.mean([x['adaptation'] for x in metrics_list])
                    model_results[group] = f"{avg_ad:.1%}"
                else:
                    model_results[group] = "N/A"
            results.append(model_results)
            
        # Generate Table
        headers = ["Model"] + self.groups
        print(" | ".join(headers))
        for r in results:
            print(f"{r['model']} | {r['Group B']} | {r['Group C']}")

        # Save to reports
        with open(REPORT_DIR / "abc_comparison_table.md", "w") as f:
            f.write("# Macro Benchmark Comparison (ABC)\n\n")
            f.write("| Model | Group B | Group C |\n| :--- | :--- | :--- |\n")
            for r in results:
                f.write(f"| {r['model']} | {r['Group B']} | {r['Group C']} |\n")

if __name__ == "__main__":
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    analyzer = ABCAnalyzer()
    analyzer.run()
