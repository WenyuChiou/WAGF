import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# --- Configuration ---
ROOT_STRESS = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_STRESS")
ROOT_BASELINE = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
REPORT_PATH = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ3_Final_Results\stress_report_v2.md")

plt.rcParams['font.family'] = 'serif'
sns.set_theme(style="white", context="paper")

class StressAnalysisSuite:
    def __init__(self):
        self.scenarios = ["panic", "veteran", "goldfish", "format"]
        self.models = ["deepseek_r1_8b", "llama3_2_3b", "gemma3_4b"]
        
    def get_baseline_metric(self, model, metric_type):
        """Load Group C baseline for comparison."""
        # Baseline path: ROOT_BASELINE / model / Group_C / Run_1 / simulation_log.csv
        csv_path = ROOT_BASELINE / model / "Group_C" / "Run_1" / "simulation_log.csv"
        if not csv_path.exists(): return 0.0
        
        df = pd.read_csv(csv_path)
        if metric_type == "panic":
            # Relocation rate in normal conditions
            return len(df[df['relocated'] == True]) / len(df)
        return 0.0

    def analyze_scenario(self, model, scenario):
        scenario_dir = ROOT_STRESS / model / scenario
        if not scenario_dir.exists(): return None
        
        runs = list(scenario_dir.glob("Run_*"))
        results = []
        for run in runs:
            csv = run / "simulation_log.csv"
            if csv.exists():
                df = pd.read_csv(csv)
                if scenario == "panic":
                    rate = len(df[df['relocated'] == True]) / len(df)
                    results.append(rate)
                # ... add other scenario logic here
        
        return np.mean(results) if results else None

    def run(self):
        print("--- Stress Test Analysis Suite (Group C Baseline) ---")
        # Implementation will be expanded as data populates
        # For now, this is the scaffold to be used after simulation
        pass

if __name__ == "__main__":
    suite = StressAnalysisSuite()
    suite.run()
