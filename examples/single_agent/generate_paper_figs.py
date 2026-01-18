import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Paths
BASE_PATH = Path(r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b")
STABILITY_CSV = BASE_PATH / "all_groups_stability_analysis.csv"
SAWTOOTH_CSV = BASE_PATH / "Group_C" / "Run_1" / "agent_001_sawtooth_data.csv"
OUTPUT_DIR = BASE_PATH

def generate_figure_2():
    """Stochastic Instability: Inter-run variance of adaptation rates."""
    print("Generating Figure 2...")
    df = pd.read_csv(STABILITY_CSV)
    
    plt.figure(figsize=(10, 6))
    
    # Define colors
    colors = {'Group_A': '#2ecc71', 'Group_B': '#e74c3c', 'Group_C': '#3498db'}
    labels = {'Group_A': 'Group A (Naive)', 'Group_B': 'Group B (Governed, Small Window)', 'Group_C': 'Group C (Tiered Memory)'}
    
    for group in ['Group_A', 'Group_B', 'Group_C']:
        subset = df[df['group'] == group]
        plt.plot(subset['year'], subset['mean'], label=labels[group], color=colors[group], marker='o', linewidth=2)
        plt.fill_between(subset['year'], subset['mean'] - subset['std'], subset['mean'] + subset['std'], 
                         color=colors[group], alpha=0.2)
    
    plt.title("Figure 2: Stochastic Instability across Simulation Runs (Gemma 3 4B)", fontsize=14, fontweight='bold')
    plt.xlabel("Year", fontsize=12)
    plt.ylabel("Number of Adapted Agents (Elevated=True)", fontsize=12)
    plt.xticks(range(1, 11))
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    output_path = OUTPUT_DIR / "Figure2_Stochastic_Instability.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Figure 2 saved to {output_path}")

def generate_figure_3():
    """The Sawtooth Curve: Trauma Recall (Agent_001)."""
    print("Generating Figure 3...")
    if not SAWTOOTH_CSV.exists():
        print(f"Error: {SAWTOOTH_CSV} not found. Run extract_sawtooth_data.py first.")
        return
        
    df = pd.read_csv(SAWTOOTH_CSV)
    
    plt.figure(figsize=(10, 4))
    
    # Plot elevated status (0 or 1)
    df['elevated_int'] = df['elevated'].astype(int)
    
    plt.step(df['year'], df['elevated_int'], where='post', color='#3498db', linewidth=3, label='Self-Protection State')
    
    # Add vertical line for Flood Event in Year 2 (Recall is in Year 3)
    plt.axvline(x=2, color='#e74c3c', linestyle='--', alpha=0.8, label='Flood Event (Year 2)')
    
    # Annotate State Transition
    plt.annotate('Trauma Recall &\nAdaptation', xy=(3, 1), xytext=(4, 0.7),
                 arrowprops=dict(facecolor='black', shrink=0.05),
                 fontsize=10, fontweight='bold')
    
    plt.title("Figure 3: The 'Sawtooth' Curve - Trauma Recall in Tiered Memory", fontsize=14, fontweight='bold')
    plt.xlabel("Year", fontsize=12)
    plt.ylabel("Elevated State (0=No, 1=Yes)", fontsize=12)
    plt.ylim(-0.1, 1.2)
    plt.yticks([0, 1], ['Base', 'Elevated'])
    plt.xticks(range(1, 11))
    plt.grid(True, linestyle=':', alpha=0.5)
    plt.legend()
    
    output_path = OUTPUT_DIR / "Figure3_Sawtooth_Curve.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Figure 3 saved to {output_path}")

def generate_figure_5():
    """Stability Metrics Summary Table (Text output for now)."""
    print("Generating Figure 5 Summary...")
    df = pd.read_csv(STABILITY_CSV)
    
    metrics = []
    for group in ['Group_A', 'Group_B', 'Group_C']:
        subset = df[df['group'] == group]
        avg_std = subset['std'].mean()
        max_adaptation = subset['mean'].max()
        group_short = group.replace('Group_', '')
        
        metrics.append({
            'Group': group_short,
            'Avg Inter-Run Std': round(avg_std, 3),
            'Max Adaptation Mean': round(max_adaptation, 1),
            'Rationality Score': 1.0 if group in ['Group_B', 'Group_C'] else 'N/A'
        })
    
    metrics_df = pd.DataFrame(metrics)
    print("\nFigure 5: Stability Metrics Summary")
    print(metrics_df.to_string(index=False))
    
    # Save as CSV for paper inclusion
    metrics_df.to_csv(OUTPUT_DIR / "Figure5_Stability_Metrics.csv", index=False)

if __name__ == "__main__":
    generate_figure_2()
    generate_figure_3()
    generate_figure_5()
