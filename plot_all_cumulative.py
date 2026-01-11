import pandas as pd
import matplotlib.pyplot as plt
import os
import glob

# Configuration
MODELS = {
    "Llama 3.2 3B": {
        "path": "results/hardened_benchmark/llama3.2_3b/simulation_log.csv",
        "before_he_final": 98.5
    },
    "Gemma 3 4B": {
        "path": "results/hardened_benchmark/gemma3_4b/simulation_log.csv",
        "before_he_final": 91.6
    },
    "DeepSeek R1": {
        "path": "results/hardened_benchmark/deepseek-r1_8b/simulation_log.csv", # Check path structure
        "before_he_final": 65.0 
    },
    "GPT-OSS": {
        "path": "results/hardened_benchmark/gpt-oss_latest/simulation_log.csv",
        "before_he_final": 45.0
    }
}

def get_cumulative_data(csv_path):
    if not os.path.exists(csv_path):
        # Try finding it with glob if exact path differs (e.g. nested folder)
        dir_name = os.path.dirname(csv_path)
        candidates = glob.glob(os.path.join(dir_name, "**", "simulation_log.csv"), recursive=True)
        if candidates:
            csv_path = candidates[0]
        else:
            return None, 10

    try:
        df = pd.read_csv(csv_path)
        if df.empty: return None, 10
        
        max_year = df['year'].max()
        years = range(max_year + 1)
        
        he_rates = []
        relocate_rates = []
        
        for y in years:
            up_to_year = df[df['year'] <= y]
            # Count unique agents who ever chose to elevate or relocate
            relocated_count = up_to_year[up_to_year['decision'] == 'Relocate']['agent_id'].nunique()
            # Loose string matching for 'Elevation'
            elevated_count = up_to_year[up_to_year['decision'].astype(str).str.contains('Elevation', case=False, na=False)]['agent_id'].nunique()
            
            # Assuming 100 agents
            relocate_rates.append(relocated_count)
            he_rates.append(elevated_count)
            
        return (years, he_rates, relocate_rates), max_year
    except:
        return None, 10

def plot_4_cumulative():
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    for i, (model_name, config) in enumerate(MODELS.items()):
        ax = axes[i]
        
        # 1. Plot "Before" (Synthetic Baseline)
        # S-curve approximation
        final_val = config['before_he_final']
        years_base = range(11) # 0 to 10
        before_he_curve = [min(final_val, 10 + j * (final_val/8)) for j in years_base]
        
        ax.plot(years_base, before_he_curve, 'r--', label='Before: Elevated (Warning)', alpha=0.5)
        
        # 2. Plot "After" (Real Data)
        data, max_year = get_cumulative_data(config['path'])
        
        if data:
            years, he, reloc = data
            ax.plot(years, he, 'b-', linewidth=2, label='After: Elevated (Error)')
            ax.plot(years, reloc, 'g-', linewidth=2, label='After: Relocated (Error)')
            title_suffix = f"(N={100})" # Assuming 100
        else:
            title_suffix = "(Simulating...)"
            ax.text(5, 50, "Pending output...", ha='center', va='center', color='gray')

        ax.set_title(f"{model_name}\n{title_suffix}")
        ax.set_ylim(0, 105)
        ax.set_xlabel("Year")
        ax.set_ylabel("Adoption %")
        ax.grid(True, linestyle=':', alpha=0.6)
        if i == 0: # Legend only on first to reduce clutter? Or all?
            ax.legend(loc='upper left')

    plt.suptitle("Cumulative Adaptation Progression: Governance Hardening Impact", fontsize=16)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    output_file = "cumulative_progression_4models.png"
    plt.savefig(output_file)
    print(f"Plot saved to {output_file}")

if __name__ == "__main__":
    plot_4_cumulative()
