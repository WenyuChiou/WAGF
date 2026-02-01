import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import os

def analyze_finance_results(results_dir: str):
    results_path = Path(results_dir)
    # Find the model directory (e.g., llama3_2_3b_strict)
    model_dirs = [d for d in results_path.iterdir() if d.is_dir() and d.name != "raw"]
    if not model_dirs:
        print(f"No results found in {results_dir}")
        return
    
    # Use the most recent or the first one
    model_dir = model_dirs[0]
    print(f"Analyzing results from: {model_dir}")

    retail_csv = model_dir / "retail_trader_governance_audit.csv"
    insto_csv = model_dir / "institutional_investor_governance_audit.csv"

    if not retail_csv.exists() or not insto_csv.exists():
        print("Missing audit CSVs.")
        return

    df_retail = pd.read_csv(retail_csv)
    df_insto = pd.read_csv(insto_csv)

    # 1. Decision Distribution over Steps
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    def plot_decisions(df, title, ax):
        pivot_df = df.groupby(['step_id', 'final_skill']).size().unstack(fill_value=0)
        pivot_df.plot(kind='bar', stacked=True, ax=ax)
        ax.set_title(title)
        ax.set_ylabel("Number of Agents")
        ax.set_xlabel("Step ID")
        ax.legend(title="Decision", bbox_to_anchor=(1.05, 1), loc='upper left')

    plot_decisions(df_retail, "Retail Trader Decisions", ax1)
    plot_decisions(df_insto, "Institutional Investor Decisions", ax2)

    plt.tight_layout()
    output_plot = model_dir / "decision_trends.png"
    plt.savefig(output_plot)
    print(f"Saved decision trends plot to: {output_plot}")

    # 2. Confidence Analysis
    plt.figure(figsize=(10, 6))
    df_retail['type'] = 'Retail'
    df_insto['type'] = 'Institutional'
    df_all = pd.concat([df_retail, df_insto])
    
    # Ensure confidence is numeric
    df_all['reason_confidence'] = pd.to_numeric(df_all['reason_confidence'], errors='coerce')
    
    # Average confidence per step
    avg_conf = df_all.groupby(['step_id', 'type'])['reason_confidence'].mean().unstack()
    avg_conf.plot(marker='o')
    plt.title("Average Decision Confidence over Steps")
    plt.ylabel("Confidence Level")
    plt.xlabel("Step ID")
    plt.grid(True, linestyle='--', alpha=0.7)
    
    output_conf_plot = model_dir / "confidence_trends.png"
    plt.savefig(output_conf_plot)
    print(f"Saved confidence trends plot to: {output_conf_plot}")

if __name__ == "__main__":
    analyze_finance_results("examples/finance/results_hetero")
