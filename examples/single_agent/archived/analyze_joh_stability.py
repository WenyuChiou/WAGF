import pandas as pd
import numpy as np
import os
from pathlib import Path
import matplotlib.pyplot as plt

# Configuration
SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR / "results/JOH_FINAL"

class StabilityAnalyzer:
    def __init__(self):
        self.groups = ["Group A", "Group B", "Group C"]
        self.models = ["llama3_2_3b", "gemma3_4b", "deepseek_r1_8b", "gpt_oss_safeguard_20b"]
        self.model_labels = {
            "llama3_2_3b": "Llama 3.2", 
            "gemma3_4b": "Gemma 3",
            "deepseek_r1_8b": "DeepSeek R1",
            "gpt_oss_safeguard_20b": "GPT-OSS"
        }

    def get_run_metrics(self, model_id, group):
        group_path = RESULTS_DIR / model_id / group.replace(" ", "_")
        if not group_path.exists():
            return []
        
        metrics = []
        # Find all RunDirs
        for run_dir in group_path.glob("Run_*"):
            log_file = run_dir / "simulation_log.csv"
            if log_file.exists():
                try:
                    df = pd.read_csv(log_file)
                    if df.empty: continue
                    
                    final_yr = df['year'].max()
                    final = df[df['year'] == final_yr]
                    if len(final) == 0: continue
                    
                    # Adaptation Rate: (Elevated OR Insured) / Total
                    adapt_count = len(final[(final['elevated'] == True) | (final['has_insurance'] == True)])
                    total_count = len(final)
                    rate = adapt_count / total_count
                    metrics.append(rate)
                except Exception as e:
                    print(f"Error reading {log_file}: {e}")
        return metrics

    def run(self):
        print("\n=== JOH Stability Analysis (Coefficient of Variation) ===")
        print(f"{'Model':<12} | {'Group':<10} | {'N':<3} | {'Mean':<8} | {'Std':<8} | {'CV (%)':<8}")
        print("-" * 65)
        
        plot_data = {}

        for model in self.models:
            plot_data[model] = {}
            for group in self.groups:
                rates = self.get_run_metrics(model, group)
                if rates:
                    n = len(rates)
                    mean = np.mean(rates)
                    std = np.std(rates)
                    cv = (std / mean * 100) if mean > 0 else 0
                    
                    print(f"{self.model_labels[model]:<12} | {group:<10} | {n:<3} | {mean:>7.1%} | {std:>7.3f} | {cv:>7.1f}%")
                    plot_data[model][group] = rates
                else:
                    print(f"{self.model_labels[model]:<12} | {group:<10} | 0   | {'N/A':>8} | {'N/A':>8} | {'N/A':>8}")

        # Preliminary Boxplot Generation
        try:
            active_models = [m for m in self.models if any(self.get_run_metrics(m, g) for g in self.groups)]
            if not active_models:
                print("\n[INFO] No data available for plotting.")
                return

            fig, axes = plt.subplots(1, len(active_models), figsize=(6 * len(active_models), 6), squeeze=False)
            axes = axes.flatten()
            
            for i, model in enumerate(active_models):
                data = [plot_data[model].get(g, []) for g in self.groups]
                labels = [f"{g}\n(N={len(d)})" for g, d in zip(self.groups, data)]
                
                axes[i].boxplot(data, tick_labels=[l if len(d)>0 else "[N/A]" for l, d in zip(labels, data)])
                axes[i].set_title(f"{self.model_labels[model]} Stability")
                axes[i].set_ylabel("Adaptation Rate (Year 10)")
                axes[i].grid(axis='y', linestyle='--', alpha=0.7)
            
            plt.tight_layout()
            output_img = SCRIPT_DIR / "analysis/preliminary_stability_boxplot.png"
            output_img.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_img)
            print(f"\n[SUCCESS] Preliminary boxplot saved to: {output_img}")
        except Exception as e:
            print(f"\n[ERROR] Could not generate plot: {e}")

if __name__ == "__main__":
    analyzer = StabilityAnalyzer()
    analyzer.run()
