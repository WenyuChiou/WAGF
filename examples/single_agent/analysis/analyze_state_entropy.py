import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import entropy
import os

# Configuration
BASE_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\deepseek_r1_1_5b"
GROUPS = ["Group_A", "Group_C"]
OUTPUT_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\sq2_results_entropy"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_and_standardize(group_name):
    # Try disabled first for Group C (audit location) or standard for Group A
    # Actually standard run logic:
    # Group A: Run_1/simulation_log.csv
    # Group C: Run_1/simulation_log.csv (main log always there)
    
    path = os.path.join(BASE_DIR, group_name, "Run_1", "simulation_log.csv")
    if not os.path.exists(path):
        print(f"File not found: {path} for {group_name}")
        return None
        
    df = pd.read_csv(path)
    
    # Standardize Decision Column
    if 'yearly_decision' not in df.columns:
        if 'decision' in df.columns:
            df['yearly_decision'] = df['decision']
        elif 'raw_llm_decision' in df.columns:
             # Group A mapping
             mapping = {
                'Do nothing': 'do_nothing',
                'Relocate': 'relocate',
                'Elevate the house': 'elevate_house',
                'Buy flood insurance': 'buy_insurance',
                'Unknown': 'do_nothing'
             }
             df['yearly_decision'] = df['raw_llm_decision'].map(mapping).fillna('do_nothing')
             
    # Clean string format
    df['yearly_decision'] = df['yearly_decision'].astype(str).str.lower().str.strip()
    return df

def calculate_state_entropy(df, group_name):
    agents = df['agent_id'].unique()
    years = sorted(df['year'].unique())
    
    # State Tracking: {agent_id: 'state'}
    # States: 'relocated', 'elevated', 'insured', 'vulnerable'
    # Priorities: Relocated > Elevated > Insured > Vulnerable
    # Note: Relocated and Elevated are sticky (accumulate). Insured is transient (yearly).
    
    agent_status = {a: 'vulnerable' for a in agents} 
    agent_elevated = {a: False for a in agents}
    agent_relocated = {a: False for a in agents}
    
    entropy_history = []
    
    for year in years:
        year_data = df[df['year'] == year].set_index('agent_id')
        
        current_year_states = []
        
        for agent in agents:
            # 1. Check Previous Permanent States
            if agent_relocated[agent]:
                current_year_states.append('relocated')
                continue
                
            # 2. Get this year's decision
            if agent not in year_data.index:
                # Agent missing? Assume Relocated or existing state? 
                # If logs are complete, shouldn't happen unless relocated previously.
                current_year_states.append('relocated' if agent_relocated[agent] else 'vulnerable')
                continue
                
            decision = year_data.loc[agent, 'yearly_decision']
            
            # 3. Update Permanent Flags
            if 'relocate' in decision:
                agent_relocated[agent] = True
                current_year_states.append('relocated')
            elif 'elevate' in decision:
                agent_elevated[agent] = True
                current_year_states.append('elevated')
            elif agent_elevated[agent]:
                current_year_states.append('elevated')
            elif 'insurance' in decision:
                current_year_states.append('insured')
            else:
                current_year_states.append('vulnerable')
                
        # Calculate Entropy for this year
        state_counts = pd.Series(current_year_states).value_counts(normalize=True)
        # Identify how many valid states exist (max 4)
        # Fill missing states with 0 for consistent indexing if needed, 
        # but scipy entropy handles missing by ignoring or we pass probability vector.
        
        ent = entropy(state_counts, base=2) # Bits
        entropy_history.append({'year': year, 'entropy': ent, 'group': group_name, 'counts': state_counts.to_dict()})
        
    return pd.DataFrame(entropy_history)

# Execution
results = []
for g in GROUPS:
    print(f"Processing {g}...")
    df = load_and_standardize(g)
    if df is not None:
        res = calculate_state_entropy(df, g)
        results.append(res)

if results:
    final_df = pd.concat(results)
    print(final_df)
    
    # Plotting
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=final_df, x='year', y='entropy', hue='group', marker='o', linewidth=2.5)
    plt.title('State Entropy Over Time (Diversity of Adaptation)', fontsize=14)
    plt.ylabel('Shannon Entropy (Bits)', fontsize=12)
    plt.xlabel('Year', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.ylim(0, 2.1) # Max entropy for 4 states is log2(4)=2
    
    save_path = os.path.join(OUTPUT_DIR, "plot_state_entropy.png")
    plt.savefig(save_path, dpi=300)
    print(f"Plot saved to {save_path}")
    
    # Save CSV
    final_df.to_csv(os.path.join(OUTPUT_DIR, "state_entropy_metrics.csv"), index=False)
