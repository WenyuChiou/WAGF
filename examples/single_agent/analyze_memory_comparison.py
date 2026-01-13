import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import glob

def analyze_memory_benchmark():
    base_dir = Path("examples/single_agent")
    
    # Define expected results
    scenarios = {
        "Window (Baseline)": base_dir / "results_window",
        "Importance (Retrieval)": base_dir / "results_importance"
    }
    
    combined_data = []
    
    for name, path in scenarios.items():
        # Find simulation_log.csv (might be nested in model folder)
        log_files = list(path.rglob("simulation_log.csv"))
        if not log_files:
            print(f"Warning: No log file found for {name} in {path}")
            continue
            
        # Assume the first one is correct if multiple (or newest)
        csv_path = log_files[0]
        print(f"Loading {name} from {csv_path}")
        
        df = pd.read_csv(csv_path)
        # Filter for final year (Year 10)
        final_year = df[df['year'] == df['year'].max()]
        
        # Calculate stats
        total_agents = len(final_year)
        elevated = final_year['elevated'].sum()
        relocated = final_year['relocated'].sum()
        insured = final_year['has_insurance'].sum()
        
        # Adaptation Rate: (Elevated + Relocated) / Total
        adaptation_rate = (elevated + relocated) / total_agents if total_agents > 0 else 0
        
        combined_data.append({
            "Memory System": name,
            "Adaptation Rate": adaptation_rate,
            "Elevated": elevated,
            "Relocated": relocated,
            "Insured": insured,
            "Total Agents": total_agents
        })
        
    if not combined_data:
        print("No data found to plot.")
        return

    stats_df = pd.DataFrame(combined_data)
    print("\nBenchmark Results:")
    print(stats_df)
    
    # Plotting
    plt.figure(figsize=(15, 6))
    
    # 1. Adaptation Rate Bar Chart (Final)
    plt.subplot(1, 3, 1)
    sns.barplot(data=stats_df, x="Memory System", y="Adaptation Rate", palette="viridis")
    plt.title("Final Adaptation Rate")
    plt.ylim(0, 1.0)
    plt.ylabel("Elevated + Relocated (%)")
    
    # 2. Detailed Breakdown Stacked
    plt.subplot(1, 3, 2)
    stats_df.set_index("Memory System")[["Elevated", "Relocated"]].plot(kind='bar', stacked=True, ax=plt.gca(), colormap="tab10")
    plt.title("Action Breakdown")
    plt.ylabel("Number of Agents")
    
    # 3. Trajectory Over Time
    plt.subplot(1, 3, 3)
    for name, path in scenarios.items():
        log_files = list(path.rglob("simulation_log.csv"))
        if log_files:
            df = pd.read_csv(log_files[0])
            # Group by year and calculate rate
            trajectory = df.groupby("year").apply(lambda x: (x['elevated'].sum() + x['relocated'].sum()) / len(x)).reset_index()
            trajectory.columns = ["year", "rate"]
            plt.plot(trajectory['year'], trajectory['rate'], marker='o', label=name)
    
    plt.title("Adaptation Trajectory")
    plt.xlabel("Year")
    plt.ylabel("Adaptation Rate")
    plt.ylim(0, 1.0)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig(base_dir / "memory_comparison_result.png")
    print(f"\nAnalysis Plot Saved: {base_dir / 'memory_comparison_result.png'}")

if __name__ == "__main__":
    analyze_memory_benchmark()
