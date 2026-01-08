import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
import sys

def plot_comparison(v2_log: Path, v22_log: Path, output_file: Path):
    """
    Generate side-by-side comparison of decision distributions.
    """
    print(f"Comparing:")
    print(f"  V2 (Baseline): {v2_log}")
    print(f"  V2-2 (Clean):  {v22_log}")
    
    if not v2_log.exists():
        print(f"Error: Baseline file not found: {v2_log}")
        return
    if not v22_log.exists():
        print(f"Error: Clean file not found: {v22_log}")
        return

    try:
        df_v2 = pd.read_csv(v2_log)
        df_v22 = pd.read_csv(v22_log)
    except Exception as e:
        print(f"Error reading logs: {e}")
        return

    # Aggregate decisions (Cumulative over 10 years, all agents)
    v2_counts = df_v2['decision'].value_counts(normalize=True) * 100
    v22_counts = df_v22['decision'].value_counts(normalize=True) * 100
    
    # Align categories
    all_decisions = sorted(list(set(v2_counts.index) | set(v22_counts.index)))
    
    # Create DataFrame for plotting
    plot_df = pd.DataFrame({
        'V2 (Polluted/Legacy)': v2_counts,
        'V2-2 (Clean Arch)': v22_counts
    }).reindex(all_decisions).fillna(0)
    
    print("\nComparison Data (Percentage):")
    print(plot_df)
    
    # Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    plot_df.plot(kind='bar', ax=ax, color=['#7f7f7f', '#1f77b4'], width=0.8)
    
    ax.set_title("Adaptation Decision Distribution (10-Year Simulation)", fontsize=14)
    ax.set_ylabel("Percentage of Decisions (%)", fontsize=12)
    ax.set_xlabel("Decision Type", fontsize=12)
    ax.legend(title="Framework Version")
    plt.xticks(rotation=20, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    
    # Annotate values
    for container in ax.containers:
        ax.bar_label(container, fmt='%.1f%%', label_type='edge', fontsize=9, padding=3)

    plt.tight_layout()
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_file, dpi=300)
    print(f"\n📊 Saved comparison plot to {output_file}")

if __name__ == "__main__":
    # Hardcoded paths based on known execution locations
    base_dir = Path(__file__).parent.parent.parent # Repo root
    v2_log = base_dir / "results/llama3.2_3b/simulation_log.csv"
    v22_log = base_dir / "examples/v2-2_clean_skill_governed/results/llama3.2_3b/simulation_log.csv"
    output = base_dir / "examples/v2-2_clean_skill_governed/results/llama3.2_3b/version_comparison.png"
    
    plot_comparison(v2_log, v22_log, output)
