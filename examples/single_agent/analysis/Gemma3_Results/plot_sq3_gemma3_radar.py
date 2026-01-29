
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from math import pi
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
DATA_PATH = BASE_DIR / "examples" / "single_agent" / "analysis" / "Gemma3_Results" / "sq3_gemma3_final_metrics.csv"
OUTPUT_PATH = BASE_DIR / "examples" / "single_agent" / "analysis" / "Gemma3_Results" / "sq3_gemma3_radar_scientific.png"

# Set Font to Times New Roman if available
plt.rcParams["font.family"] = "serif"
# plt.rcParams["font.serif"] = ["Times New Roman"] + plt.rcParams["font.serif"]

# 1. Load Data
if not DATA_PATH.exists():
    print(f"Data not found at {DATA_PATH}")
    exit()

df = pd.read_csv(DATA_PATH)

# Models to compare
models = [
    ('gemma3_1b', 'Gemma 3 (1B)'),
    ('gemma3_4b', 'Gemma 3 (4B)'),
    ('gemma3_12b', 'Gemma 3 (12B)'),
    ('gemma3_27b', 'Gemma 3 (27B)')
]

# 2. Plotting Setup
# 4 Axes: Quality, Velocity (ex-Speed), Alignment (ex-Safety), Stability
labels = ['Rationality', 'Speed', 'Alignment', 'Velocity'] # Just labels? No, this list length sets angles.
# Actual Visual Labels are set in 'display_labels' below.
# Logic: Quality (North), Velocity (East), Alignment (South), Stability (West).
# The 'values' list in loop must match this order.

num_vars = 4
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
subplot_ann = ['(a)', '(b)', '(c)', '(d)']

# 3. Iterate over models
for i, (model_id, model_name) in enumerate(models):
    ax = axs[i]
    df_model = df[df['Model'] == model_id].copy()
    
    # We want to plot A, B, C
    for group in ['Group_A', 'Group_B', 'Group_C']:
        row = df_model[df_model['Group'] == group]
        if row.empty: continue
        row = row.iloc[0]
        
        # Prepare Values
        # Note: 'Velocity' column in CSV maps to 'Velocity' axis (East).
        # We normalize Velocity: (Steps/Min / 20) * 100. Capped at 100.
        # This normalization factor (20) implies 20 steps/min is "100% Speed".
        velocity_val = row.get('Velocity', 0)
        norm_velocity = min(100, (velocity_val / 20.0) * 100) if pd.notnull(velocity_val) else 0

        values = [
            row.get('Quality', 0),        # North
            norm_velocity,                # East
            row.get('Safety', 0),         # South (Mapped to Alignment axis)
            row.get('Stability', 0)       # West
        ]
        values += values[:1]
        
        line, = ax.plot(angles, values, linewidth=4, linestyle='solid', label=group_display[group], color=colors[group])
        ax.fill(angles, values, color=colors[group], alpha=0.15)
        
        if i == 0:
            handles_all.append(line)
            labels_all.append(group_display[group])
    
    # Customize sub-plot
    ax.set_theta_offset(pi / 2)
    ax.set_theta_direction(-1) # Clockwise
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([])
    
    # Manual Label Placement
    # Quality (Top), Velocity (Right), Alignment (Bottom), Stability (Left)
    display_labels = ['Quality', 'Velocity', 'Alignment', 'Stability']
    label_distances = [118, 140, 118, 140]
    
    for label, angle, dist in zip(display_labels, angles[:-1], label_distances):
        ax.text(angle, dist, label, 
                size=34, fontweight='bold', family='serif', 
                ha='center', va='center')

    ax.set_rlabel_position(45)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], color="black", size=14, family='serif', fontweight='bold')
    
    ax.yaxis.grid(True, color='grey', linestyle='--', alpha=0.5)
    ax.xaxis.grid(True, color='grey', linestyle='-', alpha=0.5)
    
    ax.set_ylim(0, 110)
    ax.set_title(f"{model_name}", size=30, fontweight='bold', pad=80, family='serif')
    
    ax.text(-0.25, 1.25, subplot_ann[i], transform=ax.transAxes, 
            fontsize=34, fontweight='bold', va='top', ha='right', family='serif')

# 4. Final Touches
fig.legend(handles_all, labels_all, loc='lower center', ncol=3, fontsize=22, 
           frameon=True, borderpad=1.0, handletextpad=0.5, columnspacing=1.0,
           bbox_to_anchor=(0.5, 0.02))

plt.tight_layout(rect=[0, 0.1, 1, 0.98])
plt.savefig(OUTPUT_PATH, dpi=300, bbox_inches='tight')
print(f"Grand Scientific radar grid saved: {OUTPUT_PATH}")
