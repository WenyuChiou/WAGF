import pandas as pd
import numpy as np
import json
from pathlib import Path
import sys

# Define default paths relative to this script
# We scan both the local 'results' (if run from examples/single_agent) 
# and the project root 'results' (if run from root)
DEFAULT_ROOTS = [
    Path(__file__).parent / "results" / "JOH_STRESS",           # examples/single_agent/results/JOH_STRESS
    Path(__file__).parent.parent.parent / "results" / "JOH_STRESS" # project_root/results/JOH_STRESS
]
REPORT_DIR = Path(__file__).parent / "analysis" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

class StressAnalyzer:
    def __init__(self):
        self.roots = [r for r in DEFAULT_ROOTS if r.exists()]
        if not self.roots:
            # If neither exists, fallback to creating one for reference or ensure we don't crash immediately
            self.roots = [DEFAULT_ROOTS[0]]
            
        self.scenarios = ["panic", "veteran", "goldfish", "format"]
        self.models = ["llama3.2:3b", "gemma3:4b", "deepseek-r1:8b", "gpt-oss"]
        
        # Friendly display names for columns
        self.model_map = {
            "llama3.2:3b": "Llama 3.2",
            "gemma3:4b": "Gemma 3",
            "deepseek-r1:8b": "DeepSeek R1",
            "gpt-oss": "GPT-OSS"
        }

    def find_run_dirs(self, scenario, model_id):
        """
        Finds valid run directories for a given scenario and model.
        Supports both 'Run_X' structure and direct model folders.
        """
        found_dirs = []
        # Normalize model ID tokens for folder matching
        # e.g. "gemma3:4b" -> "gemma3_4b"
        safe_model = model_id.replace(":", "_").replace("-", "_").replace(".", "_")
        
        for root in self.roots:
            scenario_dir = root / scenario
            if not scenario_dir.exists(): continue
            
            # Strategy A: Look for explicit model folder (e.g., veteran/gemma3_4b)
            candidate = scenario_dir / safe_model
            if candidate.exists():
                # Check for sub-runs (Run_1, Run_2) inside the model folder
                sub_runs = [d for d in candidate.iterdir() if d.is_dir() and "Run_" in d.name]
                if sub_runs:
                    found_dirs.extend(sub_runs)
                else: 
                    # Treat as single run if it directly contains simulation_log.csv
                    # OR if it contains the timestamped subfolder from run_flood.py
                    if (candidate / "simulation_log.csv").exists():
                         found_dirs.append(candidate)
                    else:
                         # Deep Search for nested logs (common in direct python runs like 'ollama_gemma3_4b_strict')
                         # We want the DIRECT parent of simulation_log.csv
                         for path in candidate.rglob("simulation_log.csv"):
                             found_dirs.append(path.parent)

            # Strategy B: Legacy Llama Handling (files directly in Run_X under scenario root)
            # This handles the strict "Run_1", "Run_2" folders directly under "veteran/" for the baseline
            if "llama" in model_id.lower() and not found_dirs:
                legacy_runs = [d for d in scenario_dir.iterdir() if d.is_dir() and d.name.startswith("Run_")]
                # Filter to ensure these are actually Llama runs if we can (usually by checking config or just assuming baseline)
                # For now, we assume direct Run_X under scenario is the Llama baseline
                if legacy_runs:
                    found_dirs.extend(legacy_runs)
                
        # Deduplicate paths
        return list(set(found_dirs))

    def aggregate_runs(self, scenario, model_id, metric_func):
        """Run metric calculation across all found runs for a (scenario, model) pair."""
        run_dirs = self.find_run_dirs(scenario, model_id)
        if not run_dirs:
            return "N/A"

        values = []
        for rd in run_dirs:
            # Locate log file
            csv_path = rd / "simulation_log.csv"
            audit_path = rd / "audit.json"
            
            if not csv_path.exists(): 
                continue
            
            try:
                df = pd.read_csv(csv_path)
            except Exception:
                continue
                
            # Load audit if available
            audit_data = {}
            if audit_path.exists():
                try: 
                    with open(audit_path, 'r') as f: audit_data = json.load(f)
                except: pass

            # Load Traces (Lazy)
            # We assume household_traces.jsonl is in raw/ sibling to the csv usually
            traces = []
            json_path = csv_path.parent / "raw" / "household_traces.jsonl"
            if json_path.exists():
                # Load lazily inside metric func if needed? Or just load here.
                # Only load for goldfish/veteran to save time on large files?
                # For now, let's skip actual loading unless strictly necessary to avoid perf hit
                pass 

            val = metric_func(df, traces, audit_data)
            if val is not None:
                values.append(val)
        
        if not values: 
            return "N/A"
        
        mean_val = np.mean(values)
        std_val = np.std(values)
        count = len(values)
        
        if count == 1:
             return f"{mean_val:.1%} (N=1)"
        return f"{mean_val:.1%} ±{std_val:.1%} (N={count})"

    def run(self):
        print(f"--- JOH Stress Test Analysis (Multi-Model) ---")
        print(f" Scanning Roots: {[str(r) for r in self.roots]}")
        
        # --- Metric Definitions ---
        
        def get_relocation_rate(df, traces, audit):
            # Panic: Relocation Rate
            if df.empty: return None
            final_yr = df['year'].max()
            final = df[df['year'] == final_yr]
            if len(final) == 0: return 0.0
            return len(final[final['relocated'] == True]) / len(final)

        def get_inaction_rate(df, traces, audit):
            # Veteran: Inaction (Not Elevated AND Not Relocated) at Year 5 or 10
            if df.empty: return None
            # Target Year 5 for check
            target_year = 5
            if target_year not in df['year'].values: target_year = df['year'].max()
            
            yr_df = df[df['year'] == target_year]
            if yr_df.empty: return None
            
            stubborn = len(yr_df[(yr_df['elevated'] == False) & (yr_df['relocated'] == False)])
            return stubborn / len(yr_df)

        def get_repair_rate(df, traces, audit):
            # Format: Repair Rate (from Audit)
            if not audit: return None
            repairs = audit.get('total_repairs', 0)
            evals = audit.get('total_evaluations', 0)
            if evals == 0: return 0.0
            return repairs / evals

        # --- Report Generation ---
        
        rows = []
        
        # 1. Panic (ST-1)
        row = ["**ST-1: Panic**", "Relocation Rate"]
        for m in self.models:
            row.append(self.aggregate_runs("panic", m, get_relocation_rate))
        rows.append(row)
        
        # 2. Veteran (ST-2)
        row = ["**ST-2: Veteran**", "Inaction Rate"]
        for m in self.models:
            row.append(self.aggregate_runs("veteran", m, get_inaction_rate))
        rows.append(row)
        
        # 3. Format (ST-4)
        row = ["**ST-4: Format**", "Repair Rate"]
        for m in self.models:
            row.append(self.aggregate_runs("format", m, get_repair_rate))
        rows.append(row)

        # Build Markdown Table
        headers = ["Scenario", "Metric"] + [self.model_map[m] for m in self.models]
        
        header_line = "| " + " | ".join(headers) + " |"
        sep_line = "| " + " | ".join([":---"] * len(headers)) + " |"
        
        # Console Output
        print("\n" + header_line)
        print(sep_line)
        for r in rows:
            print("| " + " | ".join(r) + " |")

        # Save to File
        table_path = REPORT_DIR / "stress_comparison_table.md"
        with open(table_path, "w", encoding='utf-8') as f:
            f.write(f"# Multi-Model Stress Test Results\n\n")
            f.write(f"Generated from: `{'`, `'.join([r.name for r in self.roots])}`\n\n")
            f.write(header_line + "\n")
            f.write(sep_line + "\n")
            for r in rows:
                f.write("| " + " | ".join(r) + " |\n")
        
        print(f"\nSaved Report to: {table_path}")

if __name__ == "__main__":
    analyzer = StressAnalyzer()
    analyzer.run()
