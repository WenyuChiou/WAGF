import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def plot_adaptation_results(csv_path: Path, output_dir: Path):
    """
    Generate stacked bar chart of adaptation states over time.
    Reproduces the 'comparison_results' visualization style.
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: Could not find {csv_path}")
        return

    if df.empty:
        print("Warning: Log file is empty, skipping plot.")
        return

    # Count decisions/states per year
    # Mapping raw states to simplified categories if needed
    # Typically: 'Relocate', 'Both...', 'Only House Elevation', 'Only Flood Insurance', 'Do Nothing'
    
    # Pivot table: Year vs Decision -> Count
    pivot = df.pivot_table(index='year', columns='decision', aggfunc='size', fill_value=0)
    
    # Ensure all standard columns exist for consistent coloring
    all_categories = [
        "Relocate",
        "Both Flood Insurance and House Elevation",
        "Only House Elevation",
        "Only Flood Insurance",
        "Do Nothing"
    ]
    
    # Filter to existing categories but keep order
    categories = [c for c in all_categories if c in pivot.columns]
    
    # Normalize to percentages (0-100%)
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    
    # Plot
    plt.figure(figsize=(10, 6))
    
    # Colors aligned with standard palette
    colors = {
        "Relocate": "#8c564b",       # Brown
        "Both Flood Insurance and House Elevation": "#9467bd", # Purple
        "Only House Elevation": "#d62728", # Red
        "Only Flood Insurance": "#1f77b4", # Blue
        "Do Nothing": "#7f7f7f"      # Gray
    }
    plot_colors = [colors.get(c, "#333333") for c in categories]
    
    ax = pivot_pct.plot(kind='bar', stacked=True, color=plot_colors, width=0.8, figsize=(12, 7))
    
    plt.title("Adaptation Decisions Over Time (Skill-Governed)", fontsize=16)
    plt.xlabel("Year", fontsize=14)
    plt.ylabel("Percentage of Agents (%)", fontsize=14)
    plt.legend(title="Adaptation State", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    
    output_path = output_dir / "comparison_results.png"
    plt.savefig(output_path, dpi=300)
    print(f"📊 Saved comparison plot to {output_path}")
    plt.close()

if __name__ == "__main__":
    # Test run
    import sys
    if len(sys.argv) > 1:
        csv_file = Path(sys.argv[1])
        output = csv_file.parent
        plot_adaptation_results(csv_file, output)
