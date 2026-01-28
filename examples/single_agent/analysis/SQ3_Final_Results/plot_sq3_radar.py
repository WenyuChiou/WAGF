import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from math import pi
from pathlib import Path

# --- CONFIGURATION ---
CSV_PATH = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ3_Final_Results\sq3_efficiency_data_v2.csv")
OUTPUT_PATH = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ3_Final_Results\cost_benefit_radar.png")
ENTROPY_CSV = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ2_Final_Results\yearly_entropy_audited.csv")

# Academic Styling Settings
plt.rcParams['font.family'] = 'serif'
plt.rcParams['axes.titlesize'] = 16
plt.rcParams['axes.labelsize'] = 12

# Professional Publication Palette (CMYK-friendly)
# Using distinct line styles and markers for B&W accessibility
STYLE_MAP = {
    "1_5b Group_A": {"color": "#E69F00", "marker": "o", "ls": "--", "label": "1.5B Natural (A)"},
    "1_5b Group_B": {"color": "#56B4E9", "marker": "s", "ls": "-",  "label": "1.5B Governed (B)"},
    "1_5b Group_C": {"color": "#009E73", "marker": "D", "ls": "-",  "label": "1.5B Gov+Memory (C)"},
    "8b Group_A":   {"color": "#000000", "marker": "^", "ls": ":",  "label": "8B Natural (Base)"},
    "14b Group_A":  {"color": "#555555", "marker": "v", "ls": ":",  "label": "14B Natural (Base)"},
    "32b Group_A":  {"color": "#888888", "marker": "p", "ls": ":",  "label": "32B Natural (Base)"}
}

def load_and_prep_data():
    if not CSV_PATH.exists():
        print(f"Error: {CSV_PATH} not found.")
        return None
    
    df_eff = pd.read_csv(CSV_PATH)
    
    # Load Entropy for Diversity
    entropy_map = {}
    if ENTROPY_CSV.exists():
        df_ent = pd.read_csv(ENTROPY_CSV)
        # Calculate Temporal Average of Entropy for all years where population > 0
        df_mean = df_ent.groupby(['Model', 'Group'])['Shannon_Entropy'].mean().reset_index()
        for _, row in df_mean.iterrows():
            norm_h = row['Shannon_Entropy'] / 2.0
            entropy_map[(row['Model'], row['Group'])] = min(1.0, norm_h)

    plot_data = []
    for _, row in df_eff.iterrows():
        model, group = row['Model'], row['Group']
        diversity = entropy_map.get((model, group), 0.5)
        
        plot_data.append({
            'Model_Key': f"{model.replace('deepseek_r1_', '')} {group}",
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
    
    # Use white background for publication
    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
    fig.set_facecolor('white')
    ax.set_facecolor('#F9F9F9') # Very light grey for contrast
    
    plt.xticks(angles[:-1], categories, color='black', size=11, weight='semibold')
    ax.tick_params(axis='x', pad=20)
    
    # Grid styling
    ax.set_rlabel_position(0)
    plt.yticks([0.2, 0.4, 0.6, 0.8, 1.0], ["0.2", "0.4", "0.6", "0.8", "1.0"], color="grey", size=9)
    plt.ylim(0, 1.1)
    ax.grid(True, color='#DDDDDD', linestyle='--')
    
    for i, (_, row) in enumerate(df.iterrows()):
        values = [row[c] for c in categories]
        values += values[:1]
        
        key = row['Model_Key']
        style = STYLE_MAP.get(key, {"color": "grey", "marker": "None", "ls": "-", "label": key})
        
        # Plot with high visibility and distinct markers
        ax.plot(angles, values, color=style['color'], linewidth=2.5, 
                linestyle=style['ls'], marker=style['marker'], 
                markersize=8, label=style['label'], alpha=0.9)
        
        # Subtle fill for area visualization
        ax.fill(angles, values, color=style['color'], alpha=0.08)
    
    # Publication-ready Legend
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), 
               fontsize=10, frameon=True, edgecolor='#CCCCCC')
    
    plt.title("Comparative Performance Analysis of Governed Agents\n(Surgical Governance Metric Suite)", 
              size=16, pad=30, weight='bold')
    
    plt.savefig(output_path, dpi=600, bbox_inches='tight')
    print(f"Ultra-HD Scientific radar chart saved to {output_path}")

if __name__ == "__main__":
    df = load_and_prep_data()
    make_radar_chart(df, OUTPUT_PATH)
