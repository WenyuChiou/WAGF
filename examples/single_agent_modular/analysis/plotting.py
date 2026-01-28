"""
Visualization for Flood Adaptation Experiments.
"""
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


def clean_decision_detailed_plot(state_str: str) -> str:
    """Normalize state string for plotting."""
    s = str(state_str).lower()
    if "relocate" in s:
        return "Relocate (Departing)"
    has_ins = "insurance" in s or "buy_insurance" in s
    has_ele = "elevation" in s or "elevate" in s
    if ("both" in s and "insurance" in s and "elevation" in s) or (has_ins and has_ele):
        return "Insurance + Elevation"
    elif has_ins:
        return "Insurance"
    elif has_ele:
        return "Elevation"
    return "Do Nothing"


def plot_adaptation_results(csv_path: Path, output_dir: Path):
    """Generate stacked bar plot of adaptation evolution."""
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return

        CATEGORIES = [
            "Do Nothing", "Insurance", "Elevation",
            "Insurance + Elevation", "Relocate (Departing)"
        ]
        TAB10 = plt.get_cmap("tab10").colors
        COLOR_MAP = {
            "Do Nothing": TAB10[0],
            "Insurance": TAB10[1],
            "Elevation": TAB10[2],
            "Insurance + Elevation": TAB10[3],
            "Relocate (Departing)": TAB10[4]
        }

        state_col = 'cumulative_state' if 'cumulative_state' in df.columns else 'decision'
        if state_col not in df.columns:
            return

        # Handle attrition
        df['temp_state_check'] = df[state_col].astype(str).str.lower()
        reloc_rows = df[df['temp_state_check'].str.contains("relocate")]
        if not reloc_rows.empty:
            first_reloc = reloc_rows.groupby('agent_id')['year'].min().reset_index()
            first_reloc.columns = ['agent_id', 'first_reloc_year']
            df = df.merge(first_reloc, on='agent_id', how='left')
            df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]

        df['norm_raw'] = df[state_col].astype(str)

        # Calculate distribution
        years = sorted(df['year'].unique())
        records = []
        for y in years:
            year_data = df[df['year'] == y]
            states = year_data['norm_raw'].apply(clean_decision_detailed_plot)
            counts = states.value_counts()
            records.append([counts.get(cat, 0) for cat in CATEGORIES])

        df_res = pd.DataFrame(records, columns=CATEGORIES, index=years)

        # Plot
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = [COLOR_MAP[c] for c in CATEGORIES]
        df_res.plot(kind='bar', stacked=True, color=colors, ax=ax, width=0.85)

        ax.set_title("Adaptation Strategy Evolution (Cumulative)", fontsize=14, fontweight='bold')
        ax.set_xlabel("Year")
        ax.set_ylabel("Population Count")
        ax.set_ylim(0, 100)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        ax.legend(title="State", bbox_to_anchor=(1.05, 1), loc='upper left')

        plt.tight_layout()
        save_path = output_dir / "adaptation_cumulative_state.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Generated plot: {save_path}")
    except Exception as e:
        print(f"Plotting failed: {e}")
