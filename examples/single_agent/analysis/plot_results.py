import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def plot_adaptation_results(csv_path, output_dir):
    """
    Generates comparison_results.png for a single simulation run.
    Shows the distribution of states (Normal, Elevated, Relocated) over time.
    """
    try:
        df = pd.read_csv(csv_path)
        if df.empty: return
        
        df.columns = [c.lower() for c in df.columns]
        
        # Determine the decision column
        dec_col = 'yearly_decision' if 'yearly_decision' in df.columns else ('decision' if 'decision' in df.columns else 'cumulative_state')
        
        def normalize_state(d):
            d = str(d).lower()
            if 'relocate' in d: return 'Relocated'
            if 'elevat' in d or 'he' in d: return 'Elevated'
            return 'Baseline'

        df['state_category'] = df[dec_col].apply(normalize_state)
        
        # Pivot to get counts per year
        stats = df.groupby(['year', 'state_category']).size().unstack(fill_value=0)
        
        # Ensure all categories exist
        for cat in ['Baseline', 'Elevated', 'Relocated']:
            if cat not in stats.columns:
                stats[cat] = 0
                
        stats = stats[['Baseline', 'Elevated', 'Relocated']]
        
        # Plot
        plt.figure(figsize=(10, 6))
        stats.plot(kind='bar', stacked=True, color=['#95a5a6', '#3498db', '#e74c3c'], ax=plt.gca())
        
        plt.title(f"Simulation Outcome: Behavioral Distribution", fontsize=14, fontweight='bold')
        plt.xlabel("Year", fontsize=12)
        plt.ylabel("Agent Count", fontsize=12)
        plt.legend(title="Resilience State")
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        save_path = Path(output_dir) / "comparison_results.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"    Saved single-run summary to {save_path}")
        
    except Exception as e:
        print(f"    Error generating comparison_results.png: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        plot_adaptation_results(sys.argv[1], sys.argv[2])
