import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from math import pi
from pathlib import Path

# --- CONFIG ---
CSV_PATH = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ3_Final_Results\sq3_efficiency_data_v2.csv")
OUTPUT_PATH = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ3_Final_Results\cost_benefit_radar.png")

ENTROPY_CSV = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ2_Final_Results\yearly_entropy_audited.csv")

def load_and_prep_data():
    if not CSV_PATH.exists():
        print(f"Error: {CSV_PATH} not found.")
        return None
    
    df_eff = pd.read_csv(CSV_PATH)
    
    # Load Entropy for Diversity (Year 10 if available)
    entropy_map = {}
    if ENTROPY_CSV.exists():
        df_ent = pd.read_csv(ENTROPY_CSV)
        # Get Max Year for each Model/Group
        df_max_year = df_ent.sort_values('Year').groupby(['Model', 'Group']).last().reset_index()
        for _, row in df_max_year.iterrows():
            # Normalized Shannon Entropy (max is ~2 for 4 actions)
            norm_h = row['Shannon_Entropy'] / 2.0
            entropy_map[(row['Model'], row['Group'])] = min(1.0, norm_h)

    plot_data = []
    for _, row in df_eff.iterrows():
        model, group = row['Model'], row['Group']
        diversity = entropy_map.get((model, group), 0.5) # Default 0.5 if missing
        
        plot_data.append({
            'Label': f"{model.replace('deepseek_r1_', '')} {group}",
            'Rationality': row['Rationality'],
            'Stability': 1.0 - row['V1'],
            'Precision': 1.0 - row['Intv_S'],
            'Efficiency': 1.0 - row['Intv_H'],
            'Diversity': diversity
        })
    
    return pd.DataFrame(plot_data)

def make_radar_chart(df, output_path):
    if df is None or df.empty: return
    
    categories = ['Rationality', 'Stability', 'Precision', 'Efficiency', 'Diversity']
    N = len(categories)
    
    angles = [n / float(N) * 2 * pi for n in range(N)]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    
    plt.xticks(angles[:-1], categories, color='grey', size=12)
    ax.set_rlabel_position(0)
    plt.yticks([0.2, 0.4, 0.6, 0.8, 1.0], ["0.2", "0.4", "0.6", "0.8", "1.0"], color="grey", size=8)
    plt.ylim(0, 1.1)
    
    # Plot a few key groups to keep it readable, or all if preferred
    # Here we plot everything available in the CSV
    for i, (_, row) in enumerate(df.iterrows()):
        values = [row[c] for c in categories]
        values += values[:1]
        ax.plot(angles, values, linewidth=2, linestyle='solid', label=row['Label'])
        ax.fill(angles, values, alpha=0.05)
    
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1), fontsize=9)
    plt.title("Surgical Governance: Scalable Oversight Radar", size=18, y=1.1)
    
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Updated radar chart saved to {output_path}")

if __name__ == "__main__":
    df_plot = load_and_prep_data()
    make_radar_chart(df_plot, OUTPUT_PATH)
