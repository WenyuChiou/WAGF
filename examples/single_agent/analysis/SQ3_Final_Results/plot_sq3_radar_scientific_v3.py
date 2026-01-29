
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from math import pi
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
DATA_PATH = BASE_DIR / "examples" / "single_agent" / "analysis" / "SQ3_Final_Results" / "sq3_efficiency_final_consolidated_v3.csv"
OUTPUT_PATH = BASE_DIR / "examples" / "single_agent" / "analysis" / "SQ3_Final_Results" / "sq3_radar_multi_scale_v3.png"

# Set Font to Times New Roman if available, otherwise fallback
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman"] + plt.rcParams["font.serif"]

# 1. Load Data
df = pd.read_csv(DATA_PATH)

# Models to compare
models = [
    ('deepseek_r1_1_5b', 'DeepSeek R1 (1.5B)'),
    ('deepseek_r1_8b', 'DeepSeek R1 (8B)'),
    ('deepseek_r1_14b', 'DeepSeek R1 (14B)'),
    ('deepseek_r1_32b', 'DeepSeek R1 (32B)')
]

# 2. Plotting Setup
# 4 Axes: Quality, Alignment (ex-Safety), Stability, Speed
labels = ['Rationality', 'Speed', 'Alignment', 'Velocity']
num_vars = len(labels)
angles = [n / float(num_vars) * 2 * pi for n in range(num_vars)]
angles += angles[:1]

fig, axs = plt.subplots(2, 2, figsize=(20, 20), subplot_kw=dict(polar=True))
axs = axs.flatten()

# Group Colors & Names
colors = {'Group_A': 'crimson', 'Group_B': 'forestgreen', 'Group_C': 'steelblue'}
group_display = {
    'Group_A': 'Group A', 
    'Group_B': 'Group B', 
    'Group_C': 'Group C'
}

# Define a shared legend list
handles_all = []
labels_all = []

# Subplot labels for scientific notation
subplot_ann = ['(a)', '(b)', '(c)', '(d)']

# 3. Iterate over models
for i, (model_id, model_name) in enumerate(models):
    ax = axs[i]
    df_model = df[df['Model'] == model_id].copy()
    
    # Add (a), (b), (c), (d) labels to top-left of each subplot
    ax.text(-0.15, 1.15, subplot_ann[i], transform=ax.transAxes, 
            fontsize=34, fontweight='bold', va='top', ha='right', family='serif')
    
    # We want to plot A, B, C
    for group in ['Group_A', 'Group_B', 'Group_C']:
        row = df_model[df_model['Group'] == group]
        if row.empty: continue
        row = row.iloc[0]
        
        values = [
            row['Quality'],               # 0-100
            min(100, (row['Speed'] / 20.0) * 100),  # Norm Speed
            row['Safety'],                # Now Mapping 'Safety' col to 'Alignment' axis
            row['Stability']              # 0-100
        ]
        values += values[:1]
        
        line, = ax.plot(angles, values, linewidth=4, linestyle='solid', label=group_display[group], color=colors[group])
        ax.fill(angles, values, color=colors[group], alpha=0.15)
        
        # Collect legend items once
        if i == 0:
            handles_all.append(line)
            labels_all.append(group_display[group])
    
    # Customize sub-plot
    ax.set_xticks(angles[:-1])
    # Massive font sizes for readability
    ax.set_xticklabels(labels, size=24, fontweight='bold', family='serif')
    ax.set_rlabel_position(0)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], color="grey", size=16, family='serif')
    ax.set_ylim(0, 110)
    ax.set_title(f"{model_name}", size=30, fontweight='bold', pad=45, family='serif')

# 4. Final Touches
# Unified legend at the bottom - TIGHTENED WIDTH
fig.legend(handles_all, labels_all, loc='lower center', ncol=3, fontsize=22, 
           frameon=True, borderpad=1.0, handletextpad=0.5, columnspacing=1.0,
           bbox_to_anchor=(0.5, 0.02))

# Adjust layout
plt.tight_layout(rect=[0, 0.1, 1, 0.98])

# Save
plt.savefig(OUTPUT_PATH, dpi=300, bbox_inches='tight')
print(f"Grand Scientific radar grid saved: {OUTPUT_PATH}")
plt.show()
