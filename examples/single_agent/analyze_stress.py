import pandas as pd
import json
import glob
import os
import sys
from pathlib import Path
import re
import numpy as np

# --- CONFIG ---
# Discovery: Find the results directory relative to this script
SCRIPT_DIR = Path(__file__).parent
STRESS_ROOT = SCRIPT_DIR / "results" / "JOH_STRESS"
BASELINE_ROOT = SCRIPT_DIR / "results" / "JOH_FINAL"
REPORT_DIR = SCRIPT_DIR / "analysis" / "reports"

class StressAnalyzer:
    def __init__(self, baseline_model="llama3_2_3b"):
        self.baseline_model = baseline_model
        # Construct path to Group B (Standard Governance)
        self.baseline_dir = BASELINE_ROOT / f"{baseline_model}" / "Group_B_Governance_Window"
        self.metrics = {}
        REPORT_DIR.mkdir(parents=True, exist_ok=True)

    def find_files(self, run_dir):
        """Helper to find files handling the nested llama3_2_3b_strict folder."""
        csv_path = run_dir / "simulation_log.csv"
        # If not in root, try finding in subdirs
        if not csv_path.exists():
             for sub in run_dir.iterdir():
                 if sub.is_dir() and (sub / "simulation_log.csv").exists():
                     csv_path = sub / "simulation_log.csv"
                     break
        
        json_path = run_dir / "raw/household_traces.jsonl"
        if not json_path.exists():
            for sub in run_dir.iterdir():
                if sub.is_dir() and (sub / "raw/household_traces.jsonl").exists():
                    json_path = sub / "raw/household_traces.jsonl"
                    break

        audit_path = run_dir / "audit_summary.json"
        if not audit_path.exists():
             for sub in run_dir.iterdir():
                 if sub.is_dir() and (sub / "audit_summary.json").exists():
                     audit_path = sub / "audit_summary.json"
                     break
                     
        return csv_path, json_path, audit_path

    def load_log(self, path):
        if not os.path.exists(path):
            return pd.DataFrame()
        return pd.read_csv(path)

    def load_traces(self, path):
        traces = []
        if not os.path.exists(path):
            return traces
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                try: traces.append(json.loads(line))
                except: pass
        return traces

    def aggregate_runs(self, scenario_name, metric_func):
        """
        Aggregates metrics across multiple 'Run_X' folders for a given scenario.
        Returns formatted string "Mean% ± StdDev%"
        """
        scenario_dir = STRESS_ROOT / scenario_name
        if not scenario_dir.exists():
            return "N/A"
            
        run_dirs = [d for d in scenario_dir.iterdir() if d.is_dir() and d.name.startswith("Run_")]
        if not run_dirs:
            # Check if there's a direct model subfolder (e.g. results/JOH_STRESS/scenario/model_strict)
            # This happens if it was a single run output.
            for sub in scenario_dir.iterdir():
                if sub.is_dir() and (sub / "simulation_log.csv").exists():
                    run_dirs = [scenario_dir] # Treat scenario_dir as a single run root
                    break
        
        if not run_dirs: return "N/A"

        values = []
        for rd in run_dirs:
            csv_path, json_path, audit_path = self.find_files(rd)
            
            df = pd.read_csv(csv_path) if csv_path.exists() else pd.DataFrame()
            
            audit_data = {}
            if audit_path.exists():
                try:
                    with open(audit_path, 'r') as f: audit_data = json.load(f)
                except: pass

            # We don't load traces by default for speed unless metric_func asks?
            # Actually, let's pass a lazy loader or just load them if needed.
            traces = []
            if json_path.exists():
                # Only load if we are goldfish or veteran (qualitative)
                if scenario_name in ["goldfish", "veteran"]:
                    traces = self.load_traces(json_path)

            val = metric_func(df, traces, audit_data)
            if val is not None:
                values.append(val)
        
        if not values: return "N/A"
        
        mean_val = np.mean(values)
        std_val = np.std(values)
        if len(values) == 1:
            return f"{mean_val:.1%}"
        return f"{mean_val:.1%} (±{std_val:.1%})"

    def run(self):
        print(f"--- JOH Stress Test Analysis (Model: {self.baseline_model}) ---")
        print(f" Source: {STRESS_ROOT}")

        # 1. Metric definitions
        def get_relocation_rate(df, traces, audit):
            if df.empty: return None
            final_yr = df['year'].max()
            final = df[df['year'] == final_yr]
            if len(final) == 0: return 0.0
            return len(final[final['relocated'] == True]) / len(final)

        def get_inaction_rate(df, traces, audit):
            """Veteran: Inaction despite high risk (Year 5)."""
            if df.empty: return None
            year_5 = df[df['year'] == 5]
            if year_5.empty: return None
            # Count agents who are NOT elevated and NOT relocated
            stubborn = len(year_5[(year_5['elevated'] == False) & (year_5['relocated'] == False)])
            return stubborn / len(year_5)

        def get_repair_rate(df, traces, audit):
            """Format: Successful repairs / Total evaluations."""
            if not audit: return None
            repairs = audit.get('total_repairs', 0)
            evals = audit.get('total_evaluations', 0)
            if evals == 0: return 0.0
            return repairs / evals

        def get_goldfish_flip_rate(df, traces, audit):
            """Goldfish: Buying insurance multiple times redundantly or inconsistent state."""
            # Simple proxy: Average decisions per agent? No.
            # Let's check cumulative state consistency.
            if df.empty: return None
            # Placeholder: ratio of agents who changed states in non-flood years?
            return 0.0 # Implementation requires deeper logic

        # 2. Collect Stats
        panic_stats = self.aggregate_runs("panic", get_relocation_rate)
        vet_stats = self.aggregate_runs("veteran", get_inaction_rate)
        # goldfish_stats = self.aggregate_runs("goldfish", get_goldfish_flip_rate)
        fmt_stats = self.aggregate_runs("format", get_repair_rate)

        # 3. Baseline stats
        base_rr = "N/A"
        base_ir = "N/A"
        if (self.baseline_dir / "simulation_log.csv").exists():
            df_b = pd.read_csv(self.baseline_dir / "simulation_log.csv")
            val_rr = get_relocation_rate(df_b, [], {})
            val_ir = get_inaction_rate(df_b, [], {})
            if val_rr is not None: base_rr = f"{val_rr:.1%}"
            if val_ir is not None: base_ir = f"{val_ir:.1%}"

        # 4. Generate Markdown Table
        table_md = f"""# stress_comparison_table
### Stress Test Validation Matrix (Multi-Run Extraction)

| Scenario | Metric | Baseline (Llama 3.2) | Stress Result (Mean ± SD) | Status |
| :--- | :--- | :--- | :--- | :--- |
| **ST-1: Panic** | Relocation Rate | {base_rr} | {panic_stats} | {"⚠️ STRESSED" if panic_stats != "N/A" and "0.0%" not in panic_stats else "N/A"} |
| **ST-2: Veteran** | Inaction Rate | {base_ir} | {vet_stats} | {"🛡️ ANCHORED" if vet_stats != "N/A" and "100.0%" not in vet_stats else "N/A"} |
| **ST-4: Format** | Repair Rate | 0.0% | {fmt_stats} | {"✅ SELF-HEALED" if fmt_stats != "N/A" and "0.0%" not in fmt_stats else "N/A"} |

*Note: Baseline: Group B (Standard Governance). Stress Result shows mean across available runs.*
"""
        print(table_md)
        
        # Save Report
        table_path = REPORT_DIR / "stress_comparison_table.md"
        with open(table_path, "w", encoding='utf-8') as f:
            f.write(table_md)
        print(f"Saved table to {table_path}")

if __name__ == "__main__":
    analyzer = StressAnalyzer()
    analyzer.run()
