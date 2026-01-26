import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import entropy
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import os
import glob
import re

# =============================================================================
# CONFIGURATION
# =============================================================================
BASE_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL"
MODEL = "deepseek_r1_1_5b"
RUN_ID = "Run_1"
GROUPS = ["Group_A", "Group_C"]

# Cost Parameters (Net Capital Score)
STARTING_CAPITAL = 1000
COSTS = {
    "relocate": 200,      # High one-time cost
    "elevate_house": 100, # Medium one-time cost
    "buy_insurance": 10,  # Recurring low cost
    "do_nothing": 0
}
FLOOD_DAMAGES = {
    "unprotected": 300, # Severe loss
    "insured": 50,      # Deductible
    "elevated": 0,      # Protected
    "relocated": 0      # Safe
}

OUTPUT_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\sq2_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_simulation_data(group_name):
    """Loads simulation log for a specific group."""
    path = os.path.join(BASE_DIR, MODEL, group_name, RUN_ID, "simulation_log.csv")
    if not os.path.exists(path):
        print(f"WARNING: File not found: {path}")
        return None
    df = pd.read_csv(path)
    df['group'] = group_name

    # Standardize column names (Group A compatibility)
    if 'yearly_decision' not in df.columns:
        if 'raw_llm_decision' in df.columns:
            print(f"   -> Mapping 'raw_llm_decision' to 'yearly_decision' for {group_name}")
            mapping = {
                'Do nothing': 'do_nothing',
                'Relocate': 'relocate',
                'Elevate the house': 'elevate_house',
                'Buy flood insurance': 'buy_insurance',
                'Unknown': 'do_nothing' 
            }
            # Use map and fillna to handle unexpected values gracefully
            df['yearly_decision'] = df['raw_llm_decision'].map(mapping).fillna('do_nothing')
        else:
             print(f"   -> WARNING: 'yearly_decision' column missing in {group_name}")

    return df

def detect_flood_years(df):
    """
    Parses memory column to identify which years had floors.
    Returns a set of flood years.
    """
    # Look for patterns in memory.
    # Assumption based on manual inspection: "No flood occurred this year."
    # We will print unique year-status strings to verify.
    
    flood_years = set()
    years = sorted(df['year'].unique())
    
    print(f"\n--- Flood Detection Analysis ({df['group'].iloc[0]}) ---")
    
    for year in years:
        year_df = df[df['year'] == year]
        # Check the memory of the first agent (assuming environment is shared/global)
        # But to be safe, check a few.
        sample_memories = year_df['memory'].iloc[0:5].values
        
        is_flood = False
        for mem in sample_memories:
            if "No flood occurred" in str(mem):
                is_flood = False
                break # Consensus: No flood
            elif "flood occurred" in str(mem) or "High water levels" in str(mem): # Adjust keywords as needed
                # Strict check: If it DOESNT say "No flood occurred", is it a flood?
                # Let's look for positive confirmation if possible, or default to Yes if "No flood" is absent?
                # Safer: "No flood" vs absence.
                pass
        
        # Heuristic: If "No flood occurred" is NOT found, assume Flood? 
        # Let's verify by printing what IS found.
        
        # We search for the specific "Year X: ..." sentence
        pattern = f"Year {year}: ([^|]+)"
        
        status_text = "Unknown"
        # Extract the segment starting with "Year {year}:"
        # The memory is pipe separated |
        
        # Simple string check for now
        if any(f"Year {year}: No flood occurred" in str(m) for m in sample_memories):
             print(f"Year {year}: No Flood Detected")
        else:
             print(f"Year {year}: >> FLOOD DETECTED (or ambiguous) <<")
             # Let's print the memory to be sure it's a flood
             print(f"   Sample Memory: {sample_memories[0]}")
             flood_years.add(year)
             
    return flood_years

def calculate_action_entropy(df):
    """Calculates Shannon Entropy of action distribution per year."""
    # Action mapping
    # 1: buy_insurance, 2: elevate_house, 3: relocate, 4: do_nothing
    # The csv has 'yearly_decision' as string (e.g. 'do_nothing', 'elevate_house')
    
    entropy_series = []
    
    for year in sorted(df['year'].unique()):
        counts = df[df['year'] == year]['yearly_decision'].value_counts(normalize=True)
        h = entropy(counts) # Base e by default, can use base=2
        h_bit = entropy(counts, base=2)
        entropy_series.append({'year': year, 'entropy': h_bit})
        
    return pd.DataFrame(entropy_series)

def calculate_net_capital(df, flood_years):
    """Calculates final Net Capital Score for each agent."""
    agents = df['agent_id'].unique()
    capital_scores = []
    
    for agent in agents:
        agent_df = df[df['agent_id'] == agent].sort_values('year')
        
        current_capital = STARTING_CAPITAL
        
        # State tracking
        is_relocated = False
        is_elevated = False # Permanent state? The log says 'elevated' (True/False) per row.
                            # Assuming once elevated, stays elevated? 
                            # 'cumulative_state' might help: "Only House Elevation"
                            
        for _, row in agent_df.iterrows():
            if is_relocated:
                break # Stop costs after relocation? Or maybe just maintenance? 
                      # Logic: If relocated, you are safe. No more costs/decisions relative to this location.
            
            action = row['yearly_decision']
            year = row['year']
            
            # 1. Action Costs
            if action == 'relocate':
                current_capital -= COSTS['relocate']
                is_relocated = True
            elif action == 'elevate_house':
                # Only pay elevation cost if not already elevated?
                # The decision 2 is "Elevate House". If they pick it, they pay.
                # Assuming they don't pick it if already elevated (Logic rules usually block it).
                current_capital -= COSTS['elevate_house']
            elif action == 'buy_insurance':
                current_capital -= COSTS['buy_insurance']
            elif action == 'do_nothing':
                current_capital -= COSTS['do_nothing']
                
            # 2. Flood Damage (Only in flood years)
            if year in flood_years and not is_relocated:
                # Check status
                # using 'elevated' and 'has_insurance' columns from log
                elevated = row['elevated']
                insured = row['has_insurance']
                
                if elevated:
                    damage = FLOOD_DAMAGES['elevated']
                elif insured:
                    damage = FLOOD_DAMAGES['insured']
                else:
                    damage = FLOOD_DAMAGES['unprotected']
                    
                current_capital -= damage
        
        capital_scores.append({'agent_id': agent, 'final_capital': current_capital})
        
    return pd.DataFrame(capital_scores)

def gini_coefficient(x):
    """Compute Gini coefficient of array x."""
    x = np.array(x)
    
    # Handle negative values if capital drops below 0?
    # Gini is typically defined for non-negative values.
    # We can shift if needed, or just clip at 0 for "Bankruptcy".
    # Let's clip at 0.
    x = np.clip(x, 0, None)
    
    if np.sum(x) == 0: return 0
    
    diffsum = 0
    for i, xi in enumerate(x):
        for j, xj in enumerate(x):
            diffsum += np.abs(xi - xj)
    return diffsum / (2 * len(x)**2 * np.mean(x))

def run_clustering(df, group_name):
    """
    K-Means clustering on strategy vectors.
    Feature: % of time choosing each action (normalized count).
    """
    # Pivot: Index=Agent, Columns=Action, Values=Count
    pivot = df.pivot_table(index='agent_id', columns='yearly_decision', aggfunc='size', fill_value=0)
    
    # Normalize to percentages
    # Handle division by zero (though unlikely if agents exist) -> fillna(0)
    pivot = pivot.div(pivot.sum(axis=1), axis=0).fillna(0)
    
    # Ensure all expected columns exist 
    target_cols = ['buy_insurance', 'elevate_house', 'relocate', 'do_nothing']
    for col in target_cols:
        if col not in pivot.columns:
            pivot[col] = 0
            
    # Restrict to ONLY target columns to avoid unexpected features
    pivot = pivot[target_cols]
    
    # Final check for Inf/NaN
    pivot = pivot.replace([np.inf, -np.inf], 0).fillna(0)
            
    # Simple KMeans
    # How many clusters? 2-3 is usually good for this population size (50-100) to see if "factions" emerge.
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    labels = kmeans.fit_predict(pivot)
    
    pivot['cluster'] = labels
    pivot['group'] = group_name
    
    return pivot

# =============================================================================
# MAIN EXECUTION
# =============================================================================

dfs = {}
flood_years = set()

# 1. Load Data
print("Loading Data...")
for group in GROUPS:
    dfs[group] = load_simulation_data(group)

# 2. Detect Flood Years (Assume consistent environment, so check Group A or C)
# Checking Group C first as it was viewed recently
if dfs["Group_C"] is not None:
    flood_years = detect_flood_years(dfs["Group_C"])
print(f"Detected Flood Years: {sorted(list(flood_years))}")

results_gini = []
results_entropy = []
all_clusters = []

for group in GROUPS:
    df = dfs[group]
    if df is None: continue
    
    print(f"\nProcessing {group}...")
    
    # Entropy
    ent_df = calculate_action_entropy(df)
    ent_df['group'] = group
    results_entropy.append(ent_df)
    avg_entropy = ent_df['entropy'].mean()
    print(f"  Average Action Entropy: {avg_entropy:.4f}")
    
    # Net Capital & Gini
    cap_df = calculate_net_capital(df, flood_years)
    gini = gini_coefficient(cap_df['final_capital'])
    results_gini.append({'group': group, 'gini': gini, 'mean_wealth': cap_df['final_capital'].mean()})
    print(f"  Gini Coefficient: {gini:.4f}")
    print(f"  Mean Wealth: {cap_df['final_capital'].mean():.2f}")
    
    # Clustering (Optional / Exploratory)
    clus_df = run_clustering(df, group)
    all_clusters.append(clus_df)

# =============================================================================
# VISUALIZATION
# =============================================================================

# 1. Plot Entropy Over Time
plt.figure(figsize=(10, 6))
entropy_combined = pd.concat(results_entropy)
sns.lineplot(data=entropy_combined, x='year', y='entropy', hue='group', marker='o')
plt.title('Action Entropy (Diversity) Over Time')
plt.ylabel('Shannon Entropy (Bits)')
plt.ylim(0, 2.5) # Max entropy for 4 choices is 2 bits
plt.grid(True, alpha=0.3)
plt.savefig(os.path.join(OUTPUT_DIR, "plot_action_entropy.png"))
plt.close()

# 2. Plot Gini Comparison
gini_df = pd.DataFrame(results_gini)
plt.figure(figsize=(8, 6))
sns.barplot(data=gini_df, x='group', y='gini', hue='group', dodge=False)
plt.title('Wealth Gini Coefficient (Inequality)')
plt.ylabel('Gini (0=Equal, 1=Unequal)')
plt.ylim(0, 0.6)
for i, row in gini_df.iterrows():
    plt.text(i, row['gini'] + 0.01, f"{row['gini']:.3f}", ha='center', color='black')
plt.savefig(os.path.join(OUTPUT_DIR, "plot_wealth_gini.png"))
plt.close()

# 3. Strategy Clusters (Scatterplot of PC1 vs PC2)
if all_clusters:
    cluster_combined = pd.concat(all_clusters)
    features = cluster_combined.drop(columns=['cluster', 'group'])
    
    pca = PCA(n_components=2)
    pca_result = pca.fit_transform(features)
    cluster_combined['pc1'] = pca_result[:, 0]
    cluster_combined['pc2'] = pca_result[:, 1]
    
    plt.figure(figsize=(10, 8))
    sns.scatterplot(data=cluster_combined, x='pc1', y='pc2', hue='group', style='cluster', s=100, alpha=0.8)
    plt.title('Strategy Space (PCA of Action Frequencies)')
    plt.xlabel(f'PC1 (Var: {pca.explained_variance_ratio_[0]:.2f})')
    plt.ylabel(f'PC2 (Var: {pca.explained_variance_ratio_[1]:.2f})')
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_strategy_clusters.png"))
    plt.close()

# Save Metrics to CSV
gini_df.to_csv(os.path.join(OUTPUT_DIR, "diversity_metrics.csv"), index=False)
entropy_combined.to_csv(os.path.join(OUTPUT_DIR, "entropy_timeseries.csv"), index=False)

print("\nAnalysis Complete. Results saved to:", OUTPUT_DIR)
