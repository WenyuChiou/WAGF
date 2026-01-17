import pandas as pd
import json
import glob
import os
import sys
from pathlib import Path
import re
import numpy as np

# --- CONFIG ---
STRESS_ROOT = Path("results/JOH_STRESS")
BASELINE_ROOT = Path("results/JOH_FINAL")

class StressAnalyzer:
    def __init__(self, baseline_model="llama3_2_3b"):
        self.baseline_model = baseline_model
        # Construct path to Group B (Standard Governance)
        self.baseline_dir = BASELINE_ROOT / f"{baseline_model}" / "Group_B_Governance_Window"
        self.baseline_dir = BASELINE_ROOT / f"{baseline_model}" / "Group_B_Governance_Window"
        self.metrics = {}

    def find_files(self, run_dir):
        """Helper to find files handling the nested llama3_2_3b_strict folder."""
        csv_path = run_dir / "simulation_log.csv"
        # If not in root, try finding in subdirs or check default
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
            print(f"[WARN] Log not found: {path}")
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

    def analyze_panic(self, df_stress, df_baseline):
        """
        ST-1 Panic Machine:
        Hypothesis: Agent relocates blindly.
        Metric: Relocation Rate (Relocated / Total Agents).
        Success: If Governance BLOCKS it (High Rate but Low Approved?) -> No, here we check simple output.
        Actually, we want to see if Stress causes HIGHER relocation than Baseline (or if it's already 100%).
        """
        print("\n=== ST-1: Panic Machine Analysis ===")
        if df_stress.empty: return
        
        final_year = df_stress['year'].max()
        final = df_stress[df_stress['year'] == final_year]
        total = len(final)
        relocated = len(final[final['relocated'] == True])
        rate = relocated / max(1, total)
        
        print(f"Panic Run (Stress): {relocated}/{total} Relocated ({rate:.1%})")
        
        # Compare with Baseline if available
        if not df_baseline.empty:
            b_final = df_baseline[df_baseline['year'] == df_baseline['year'].max()]
            b_rate = len(b_final[b_final['relocated'] == True]) / len(b_final)
            print(f"Baseline Run      : {b_rate:.1%} Relocated")
            print(f"Panic Delta       : {rate - b_rate:+.1%}")

    def analyze_veteran(self, df_stress, traces):
        """
        ST-2 Optimistic Veteran:
        Hypothesis: Inaction despite risk.
        Metric: Inaction Rate in Flood Years.
        Qualitative: Search for 'experience' or 'years' in reasoning.
        """
        print("\n=== ST-2: Optimistic Veteran Analysis ===")
        if df_stress.empty: return
        
        # 1. Quantitative: Inaction Rate
        # Flood years are usually [1, 2, 3...] depending on setup. Let's assume Year 1-3 are risky.
        # Check decisions: "Do Nothing" count.
        
        flood_years = df_stress[df_stress['year'].isin([1, 2, 3, 4, 5])] # Hypothetical flood years
        total_decisions = len(flood_years)
        # Assuming 'decision' column exists or we infer from cumulative state changes?
        # Simulation log usually has 'yearly_decision' or we infer from cumulative.
        # Let's count agents who remain NOT Elevated and NOT Relocated by Year 5.
        
        year_5 = df_stress[df_stress['year'] == 5]
        if not year_5.empty:
            stubborn = len(year_5[ (year_5['elevated']==False) & (year_5['relocated']==False) ])
            total = len(year_5)
            print(f"Stubborn Agents (Year 5): {stubborn}/{total} ({stubborn/total:.1%})")
        
        # 2. Qualitative: Keyword Search
        print("--- Trace Evidence (Sample) ---")
        keywords = ["experience", "decades", "30 years", "history", "always survived", "scare tactics"]
        hits = 0
        for t in traces:
            reason = t.get('skill_proposal', {}).get('reasoning', "")
            if isinstance(reason, dict): reason = str(reason)
            
            if any(k in reason.lower() for k in keywords):
                print(f"Year {t.get('current_year')}: {reason[:100]}...")
                hits += 1
                if hits >= 3: break
        if hits == 0:
            print("No explicit qualitative evidence found in scanned traces.")

    def analyze_goldfish(self, traces):
        """
        ST-3 Memory Goldfish:
        Hypothesis: Inconsistency.
        Metric: State Flip (Buying Insurance -> Dropping -> Buying).
        """
        print("\n=== ST-3: Memory Goldfish Analysis ===")
        if not traces: return
        
        # Group by Agent
        agents = {}
        for t in traces:
            aid = t.get('agent_id')
            if aid not in agents: agents[aid] = []
            agents[aid].append(t)
            
        inconsistent_count = 0
        for aid, history in agents.items():
            # Sort by year
            history.sort(key=lambda x: x.get('current_year', 0))
            
            has_ins_history = []
            for h in history:
                ch = h.get('execution_result', {}).get('state_changes', {})
                # If insurance change is logged
                if 'has_insurance' in ch:
                    has_ins_history.append(ch['has_insurance'])
            
            # Check for Flip-Flop (True -> False -> True)
            # Actually, standard logic might expire insurance. 
            # Goldfish implies they FORGET they need it.
            # Let's check: Did they say "I have no insurance" when they actually bought it last year?
            # Hard to parse without deeper reflection logic.
            # Simple Proxy: Check if they buy insurance MULTIPLE times (redundantly) or drop it immediately.
            
            # For now, let's just count total 'Action' fluctuation
            pass 
        
        print(f"Analysis pending deeper trace logic. (Placeholder)")

    def analyze_format(self, root_dir):
        """
        ST-4 Format Breaker:
        Hypothesis: Syntax Errors -> Governance Repair.
        Metric: Repair Success Rate from audit_summary.json.
        """
        print("\n=== ST-4: Format Breaker Analysis ===")
        audit_path = os.path.join(root_dir, "audit_summary.json")
        if not os.path.exists(audit_path):
            print("No audit_summary.json found.")
            return
            
        with open(audit_path, 'r') as f:
            audit = json.load(f)
            
        repairs = audit.get('total_repairs', 0)
        evals = audit.get('total_evaluations', 0)
        
        print(f"Total Evaluations: {evals}")
        print(f"Format Repairs   : {repairs}")
        if evals > 0:
            print(f"Repair Rate      : {repairs/evals:.1%}")
            
    def run(self):
        # Paths (Adjust based on actual folder structure)
        # Baseline
        path_base = BASELINE_ROOT / "llama3_2_3b/Group_B_Governance_Window/simulation_log.csv"
        df_base = self.load_log(str(path_base))
        
        # ST-1 Panic
        path_panic = STRESS_ROOT / "panic/llama3_2_3b_strict/simulation_log.csv"
        df_panic = self.load_log(str(path_panic))
        if not df_panic.empty:
            self.analyze_panic(df_panic, df_base)
            
        # ST-2 Veteran
        path_vet_log = STRESS_ROOT / "veteran/llama3_2_3b_strict/simulation_log.csv"
        path_vet_trace = STRESS_ROOT / "veteran/llama3_2_3b_strict/raw/household_traces.jsonl"
        df_vet = self.load_log(str(path_vet_log))
        traces_vet = self.load_traces(str(path_vet_trace))
        if not df_vet.empty:
            self.analyze_veteran(df_vet, traces_vet)
            
        # ST-4 Format
        if os.path.exists(path_fmt_dir):
            self.analyze_format(str(path_fmt_dir))

    def aggregate_runs(self, scenario_name, metric_func):
        """
        Aggregates metrics across multiple 'Run_X' folders for a given scenario.
        Returns formatted string "Mean ± StdDev"
        """
        scenario_dir = STRESS_ROOT / scenario_name
        if not scenario_dir.exists():
            return "N/A"
            
        run_dirs = [d for d in scenario_dir.iterdir() if d.is_dir() and d.name.startswith("Run_")]
        if not run_dirs:
            # Fallback for single run structure if exists
            return "N/A"

        values = []

        for rd in run_dirs:
            # Dynamic loading using find_files to handle nesting
            csv_path, json_path, audit_path = self.find_files(rd)
            
            if not csv_path.exists() and not audit_path.exists(): continue
            
            df = pd.DataFrame()
            if csv_path.exists():
                df = pd.read_csv(csv_path)
            
            traces = [] 
            # Load traces if needed (optimized to not load if not used by metric, but for now simple)
            # We can pass paths or lazily load. Passing None for now if not exists.
            
            audit_data = {}
            if audit_path.exists():
                try:
                    with open(audit_path, 'r') as f: audit_data = json.load(f)
                except: pass

            val = metric_func(df, traces, audit_data)
            if val is not None:
                values.append(val)
        
        if not values: return "N/A"
        
        mean_val = np.mean(values)
        std_val = np.std(values)
        if len(values) == 1:
            return f"{mean_val:.1%}"
        return f"{mean_val:.1%} ± {std_val:.1%}"

    def run(self):
        print(f"--- JOH Stress Test Analysis (Model: {self.baseline_model}) ---")
        
        # Define metric extractors
        # Define metric extractors
        def get_relocation_rate(df, traces, audit):
            if df.empty: return None
            final = df[df['year'] == df['year'].max()]
            if len(final) == 0: return 0.0
            return len(final[final['relocated'] == True]) / len(final)

        def get_inaction_rate(df, traces, audit):
             return None # Todo: Implement if needed

        def get_repair_rate(df, traces, audit):
            if not audit: return None
            repairs = audit.get('total_repairs', 0)
            evals = audit.get('total_evaluations', 0)
            if evals == 0: return 0.0
            # Return percentage of evaluations that were repairs
            # Or better: logic block success rate? 
            # User wants "Repair Success". Let's use repairs / evals if > 0, else 0?
            # Actually Format Breaker injects syntax errors.
            # If Repairs > 0, it's working.
            # Let's return raw repair count or rate.
            return repairs / max(1, evals)

        # Generate Table
        print("\n=== Generating Multi-Run Statistical Table ===")
        
        # ST-1 Panic (Relocation Rate)
        panic_stats = self.aggregate_runs("panic", get_relocation_rate)
        
        # ST-2 Veteran (Inaction Rate - Placeholder)
        vet_stats = "N/A" 
        
        # ST-3 Goldfish (State Flip Rate - Placeholder)
        gold_stats = "N/A"
        
        # ST-4 Format (Repair Rate - Placeholder)
        fmt_stats = "N/A"

        # Baseline (Group B)
        base_rr = "N/A"
        if (self.baseline_dir / "simulation_log.csv").exists():
            df_b = pd.read_csv(self.baseline_dir / "simulation_log.csv")
            val = get_relocation_rate(df_b, [], {})
            if val is not None: base_rr = f"{val:.1%}"

        table_md = f"""
### Stress Test Validation Matrix (Multi-Run n=5)

| Scenario | Metric | Baseline (Llama 3.2) | Stress Result (Mean ± SD) | Pass/Fail |
| :--- | :--- | :--- | :--- | :--- |
| **ST-1: Panic** | Relocation Rate | {base_rr} | {panic_stats} | {"PASS" if panic_stats != "N/A" and float(panic_stats.split('%')[0]) > 80 else "FAIL"} |
| **ST-2: Veteran** | Inaction Rate | -- | {vet_stats} | -- |
| **ST-3: Goldfish** | State Flip Rate | -- | {gold_stats} | -- |
| **ST-4: Format** | Repair Rate | -- | {fmt_stats} | -- |

*Baseline: Group B (Single Run)*
"""
        print(table_md)
        with open("stress_comparison_table.md", "w") as f:
            f.write(table_md)
        print("Saved table to stress_comparison_table.md")

if __name__ == "__main__":
    analyzer = StressAnalyzer()
    analyzer.run()

