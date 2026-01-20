
import json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import random

def analyze_agent_trajectory(traces_dir: Path, output_dir: Path, num_agents_to_plot: int = 5):
    """
    Analyzes and visualizes the trajectory of selected agents over time,
    showing decisions and key state changes.
    """
    all_agent_traces = {}
    
    # Load all household agent traces
    for trace_file in traces_dir.glob('household_*_traces.jsonl'):
        agent_id = trace_file.stem.replace('_traces', '') # Extract agent_id
        agent_history = []
        with open(trace_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    trace = json.loads(line)
                    agent_history.append(trace)
                except json.JSONDecodeError:
                    continue
        if agent_history:
            all_agent_traces[agent_id] = sorted(agent_history, key=lambda x: x.get('step_id', 0))

    if not all_agent_traces:
        print("No household agent traces found for trajectory analysis.")
        return

    # Select random agents to plot
    selected_agent_ids = random.sample(list(all_agent_traces.keys()), min(num_agents_to_plot, len(all_agent_traces)))
    
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Analyzing trajectories for {len(selected_agent_ids)} agents...")

    for agent_id in selected_agent_ids:
        history = all_agent_traces[agent_id] 
        
        # Prepare data for plotting
        years = []
        decisions = []
        elevated_states = []
        insurance_states = []
        cumulative_damage = []
        
        for trace in history:
            years.append(trace.get('step_id'))
            decisions.append(trace.get('approved_skill', {}).get('skill_name', 'unknown'))
            
            state_after = trace.get('state_after', {})
            elevated_states.append(1 if state_after.get('elevated', False) else 0)
            insurance_states.append(1 if state_after.get('has_insurance', False) else 0)
            cumulative_damage.append(state_after.get('cumulative_damage', 0))
            
        df_agent = pd.DataFrame({
            'Year': years,
            'Decision': decisions,
            'Elevated': elevated_states,
            'Has_Insurance': insurance_states,
            'Cumulative_Damage': cumulative_damage
        })
        
        # Plotting
        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        
        # Plot 1: Decisions
        axes[0].plot(df_agent['Year'], df_agent['Decision'], marker='o', linestyle='-')
        axes[0].set_ylabel('Decision')
        axes[0].set_title(f'Agent {agent_id} Trajectory')
        axes[0].grid(True, linestyle='--', alpha=0.6)
        
        # Plot 2: State Changes (Elevated, Has_Insurance)
        axes[1].plot(df_agent['Year'], df_agent['Elevated'], marker='x', linestyle='--', label='Elevated (1=True)')
        axes[1].plot(df_agent['Year'], df_agent['Has_Insurance'], marker='+', linestyle='--', label='Has Insurance (1=True)')
        axes[1].set_ylabel('Binary State')
        axes[1].set_yticks([0, 1])
        axes[1].legend()
        axes[1].grid(True, linestyle='--', alpha=0.6)
        
        # Plot 3: Cumulative Damage
        axes[2].plot(df_agent['Year'], df_agent['Cumulative_Damage'], marker='s', linestyle='-', color='red')
        axes[2].set_xlabel('Year')
        axes[2].set_ylabel('Cumulative Damage ($)')
        axes[2].grid(True, linestyle='--', alpha=0.6)
        axes[2].ticklabel_format(style='plain', axis='y') # Prevent scientific notation for currency
        
        plt.tight_layout()
        plot_filename = output_dir / f'v3_agent_{agent_id}_trajectory.png'
        plt.savefig(plot_filename)
        print(f"  - Trajectory plot for Agent {agent_id} saved to: {plot_filename}")
        plt.close(fig) # Close plot to free memory

    print(f"\nAgent trajectory analysis completed. Plots saved to {output_dir}")

if __name__ == "__main__":
    traces_dir = Path("examples/multi_agent/results_unified/v015_full_bg/llama3_2_3b_strict/raw")
    output_dir = Path("examples/multi_agent/analysis/reports/")
    analyze_agent_trajectory(traces_dir, output_dir, num_agents_to_plot=5)
