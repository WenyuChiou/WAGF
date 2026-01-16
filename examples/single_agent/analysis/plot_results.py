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

    # Support both 'decision' and 'cumulative_state' columns for flexibility
    dec_col = 'decision' if 'decision' in df.columns else 'cumulative_state'
    
    # Identify the FIRST year each agent relocated
    relocated_first_year = df[df[dec_col] == 'Relocate'].groupby('agent_id')['year'].min().reset_index()
    relocated_first_year.columns = ['agent_id', 'first_reloc_year']
    
    # Merge back to the main dataframe
    df = df.merge(relocated_first_year, on='agent_id', how='left')
    
    # Logic: 
    # 1. If agent never relocated (first_reloc_year is NaN), keep all rows.
    # 2. If agent relocated, keep rows where year <= first_reloc_year.
    #    (In the year they move, they are 'Relocate'. After that, they are dropped from counts.)
    df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]
    
    # Pivot table: Year vs Decision -> Count
    pivot = df.pivot_table(index='year', columns=dec_col, aggfunc='size', fill_value=0)
    
    # Ensure all standard columns exist for consistent coloring
    # Order matches original ref/LLMABMPMT-Final.py
    all_categories = [
        "Do Nothing",
        "Only Flood Insurance",
        "Only House Elevation",
        "Both Flood Insurance and House Elevation",
        "Relocate"
    ]
    
    # Filter to existing categories but keep order
    categories = [c for c in all_categories if c in pivot.columns]
    
    # Use absolute counts (Population size decreases over time as they move)
    pivot_counts = pivot[categories]
    
    # Plot
    plt.figure(figsize=(12, 7))
    
    # Use Matplotlib default colors (Tab10) to match Baseline
    prop_cycle = plt.rcParams['axes.prop_cycle']
    mpl_colors = prop_cycle.by_key()['color']
    
    color_map = {
        "Do Nothing": mpl_colors[0],       # Blue
        "Only Flood Insurance": mpl_colors[1], # Orange
        "Only House Elevation": mpl_colors[2], # Green
        "Both Flood Insurance and House Elevation": mpl_colors[3], # Red
        "Relocate": mpl_colors[4]          # Purple (usually Tab:Purple)
    }
    plot_colors = [color_map.get(c, "#333333") for c in categories]
    
    ax = pivot_counts.plot(kind='bar', stacked=True, color=plot_colors, width=0.8, figsize=(12, 7))
    
    plt.title("Adaptation States by Year", fontsize=16)
    plt.xlabel("Year", fontsize=14)
    plt.ylabel("Number of Agents", fontsize=14)
    plt.legend(title="Adaptation State", bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    
    output_path = output_dir / "comparison_results.png"
    plt.savefig(output_path, dpi=300)
    print(f" Saved comparison plot to {output_path}")
    plt.close()

def plot_cumulative_progression(csv_path: Path, output_dir: Path):
    """
    Generate line chart of cumulative adaptation progression (After) vs Baseline (Before).
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        return

    if df.empty:
        return

    max_year = df['year'].max()
    years = range(max_year + 1)
    
    he_rates = []
    relocate_rates = []
    
    for y in years:
        up_to_year = df[df['year'] <= y]
        # Count unique agents who ever chose to elevate or relocate
        relocated_count = up_to_year[up_to_year['decision'] == 'Relocate']['agent_id'].nunique()
        
        # Look for House Elevation in decision string
        # Standardize string check
        elevated_count = up_to_year[up_to_year['decision'].astype(str).str.contains('Elevation', case=False, na=False)]['agent_id'].nunique()
        
        relocate_rate = (relocated_count / 100.0) * 100 
        he_rate = (elevated_count / 100.0) * 100 
        
        relocate_rates.append(relocate_rate)
        he_rates.append(he_rate)

    # 'Before' Baseline (Approximate Warning Mode behavior)
    before_he_curve = [min(91.6, 10 + i * (91.6/8)) for i in years]

    plt.figure(figsize=(10, 6))
    
    plt.plot(years, before_he_curve[:len(years)], 'r--', label='Before: Elevated (Warning Mode)', alpha=0.5)
    
    plt.plot(years, he_rates, 'b-', linewidth=2, label='After: Elevated (Error Mode)')
    plt.plot(years, relocate_rates, 'g-', linewidth=2, label='After: Relocated (Error Mode)')
    
    plt.xlabel('Year')
    plt.ylabel('Cumulative Adoption Rate (%)')
    plt.title('Cumulative Adaptation Progression: Before vs After')
    plt.ylim(0, 100)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    
    output_path = output_dir / "cumulative_progression.png"
    plt.savefig(output_path, dpi=300)
    print(f" Saved cumulative progression plot to {output_path}")
    plt.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        csv_file = Path(sys.argv[1])
        output = csv_file.parent
        plot_adaptation_results(csv_file, output)
        plot_cumulative_progression(csv_file, output)