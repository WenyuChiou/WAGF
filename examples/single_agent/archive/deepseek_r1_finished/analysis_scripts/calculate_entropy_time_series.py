import pandas as pd
import numpy as np
import os
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import entropy

# --- CONFIGURATION ---
BASE_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
groups = ["Group_A", "Group_B", "Group_C"]
OUTPUT_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ2_Final_Results")

plt.rcParams['font.family'] = 'serif'
sns.set_theme(style="whitegrid", context="paper")

def normalize_decision(d):
    d = str(d).lower()
    if 'reloc' in d: return 'relocate'
    if 'elev' in d: return 'elevate'
    if 'insur' in d: return 'insurance'
    return 'do_nothing'

def calculate_shannon_entropy(series):
    # Get proportions of each category
    pk = series.value_counts(normalize=True).values
    # Calculate Shannon Entropy in bits (base 2)
    return entropy(pk, base=2)

def analyze_cohort_entropy(model, group):
    csv_path = BASE_DIR / model / group / "Run_1" / "simulation_log.csv"
    if not csv_path.exists():
        return None
    
    try:
        df = pd.read_csv(csv_path)
        df.columns = [c.lower() for c in df.columns]
        dec_col = next((c for c in df.columns if 'yearly_decision' in c or 'decision' in c or 'skill' in c), None)
        
        if not dec_col: return None
        
        # Filter for active steps only if needed, but for diversity we want the snapshot of all agents in that year
        # Actually, if they relocated, they are effectively out of the "diversity pool" for that year's decision.
        # So we only calculate entropy for agents who haven't relocated in PREVIOUS years.
        
        results = []
        for year in range(0, int(df['year'].max()) + 1):
            year_data = df[df['year'] == year]
            if year_data.empty: continue
            
            # Normalize decisions
            norm_decs = year_data[dec_col].apply(normalize_decision)
            
            # Calculate Entropy
            h_val = calculate_shannon_entropy(norm_decs)
            
            # Count population size (to detect extinction/mode-collapse context)
            pop_size = len(year_data)
            
            results.append({
                "Year": year,
                "Model": model,
                "Group": group,
                "Entropy": h_val,
                "Population": pop_size
            })
        return results
    except Exception as e:
        print(f"Error {model}/{group}: {e}")
        return None

# --- EXECUTION ---
all_results = []
for model in models:
    for group in groups:
        res = analyze_cohort_entropy(model, group)
        if res:
            all_results.extend(res)

df_entropy = pd.DataFrame(all_results)

# Save Raw Data
df_entropy.to_csv(OUTPUT_DIR / "yearly_entropy_data.csv", index=False)

# --- PLOTTING (2x2 Grid) ---
fig, axes = plt.subplots(2, 2, figsize=(16, 12), sharex=True, sharey=True)
axes = axes.flatten()

for i, model in enumerate(models):
    ax = axes[i]
    model_data = df_entropy[df_entropy['Model'] == model]
    
    if model_data.empty:
        ax.text(0.5, 0.5, f"No data for {model}", ha='center', va='center')
        ax.set_title(f"Model: {model} (No Data)")
        continue
        
    sns.lineplot(data=model_data, x='Year', y='Entropy', hue='Group', 
                 style='Group', markers=True, dashes=False,
                 ax=ax, palette="Dark2", linewidth=2)
    
    ax.set_title(f"Model Scale: {model.split('_')[-1].upper()}", fontsize=14, fontweight='bold')
    ax.set_ylabel("Shannon Entropy (Bits)" if i % 2 == 0 else "")
    ax.set_xlabel("Year" if i >= 2 else "")
    ax.set_ylim(0, 2.3)
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.legend(title="Governance Group", loc='lower left', prop={'size': 8})

plt.suptitle("Assessment of Decision Entropy Evolution Across Model Scales", fontsize=18, fontweight='bold', y=1.02)
plt.tight_layout()

plt.savefig(OUTPUT_DIR / "entropy_evolution_trend_2x2.png", dpi=600, bbox_inches='tight')
plt.savefig(OUTPUT_DIR / "entropy_evolution_trend.png", dpi=300) 
print(f"2x2 Plots and data saved to {OUTPUT_DIR}")

# --- PIVOT TABLE FOR SUMMARY ---
pivot = df_entropy.pivot_table(index=['Model', 'Group'], columns='Year', values='Entropy')
print("\n=== SQ2: YEARLY ENTROPY (BITS) ===")
print(pivot.round(3))
pivot.to_csv(OUTPUT_DIR / "entropy_pivot_summary.csv")
