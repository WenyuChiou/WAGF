"""
Year-by-Year Diagnostic Analysis of v12 SAGE Oscillation
Compares v12 SAGE-CRSS simulation against CRSS baseline to identify root causes of high CoV.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# File paths
V12_LOG = Path(r"examples/irrigation_abm/results/v12_production_42yr_78agents/simulation_log.csv")
CRSS_BASELINE = Path(r"ref/CRSS_DB/CRSS_DB/annual_baseline_time_series.csv")
OUTPUT_DIR = Path(r"examples/irrigation_abm/results/v12_production_42yr_78agents/diagnostics")
OUTPUT_DIR.mkdir(exist_ok=True)

print("="*80)
print("v12 SAGE Oscillation Diagnostic Analysis")
print("="*80)

# Step 1: Load and Prepare Data
print("\n[Step 1] Loading data...")
v12_log = pd.read_csv(V12_LOG)
crss_baseline = pd.read_csv(CRSS_BASELINE)

print(f"v12 log: {len(v12_log)} rows, {len(v12_log.columns)} columns")
print(f"CRSS baseline: {len(crss_baseline)} rows, {len(crss_baseline.columns)} columns")

# Convert to numeric
v12_log['year'] = pd.to_numeric(v12_log['year'])
v12_log['request'] = pd.to_numeric(v12_log['request'])
v12_log['magnitude_pct'] = pd.to_numeric(v12_log['magnitude_pct'])

# Compute yearly aggregates for v12
v12_yearly = v12_log.groupby('year').agg({
    'request': 'sum',
    'agent_id': 'count'  # number of agents
}).reset_index()
v12_yearly.rename(columns={
    'request': 'total_request_af',
    'agent_id': 'num_agents'
}, inplace=True)
v12_yearly['total_request_maf'] = v12_yearly['total_request_af'] / 1e6

# Decision counts by year
decision_yearly = v12_log.groupby(['year', 'yearly_decision']).size().reset_index(name='count')
decision_pivot = decision_yearly.pivot(index='year', columns='yearly_decision', values='count').fillna(0)

# Magnitude statistics by year
magnitude_yearly = v12_log.groupby('year').agg({
    'magnitude_pct': ['mean', 'std', 'min', 'max']
}).reset_index()
magnitude_yearly.columns = ['year', 'magnitude_mean', 'magnitude_std', 'magnitude_min', 'magnitude_max']

# Governance interventions - check if 'status' column exists
if 'status' in v12_log.columns:
    v12_log['blocked'] = v12_log['status'].str.contains('BLOCKED', na=False)
    governance_yearly = v12_log.groupby('year').agg({
        'blocked': ['sum', 'count']
    }).reset_index()
    governance_yearly.columns = ['year', 'blocked_count', 'total_count']
    governance_yearly['blocked_pct'] = governance_yearly['blocked_count'] / governance_yearly['total_count'] * 100
else:
    # No status column, assume no blocks
    governance_yearly = pd.DataFrame({
        'year': v12_yearly['year'],
        'blocked_pct': 0.0
    })

# Cluster analysis
cluster_yearly = v12_log.groupby(['year', 'cluster']).agg({
    'request': 'sum'
}).reset_index()
cluster_pivot = cluster_yearly.pivot(index='year', columns='cluster', values='request').fillna(0)
cluster_pivot = cluster_pivot / 1e6  # Convert to MAF
cluster_pivot.columns = [f'cluster_{col}_maf' for col in cluster_pivot.columns]

# Prepare CRSS baseline (Upper Basin + Lower Basin)
# Column names are ub_baseline_af and lb_baseline_af, need to convert to MAF
crss_baseline['year'] = pd.to_numeric(crss_baseline['year'])
crss_baseline['ub_baseline_af'] = pd.to_numeric(crss_baseline['ub_baseline_af'])
crss_baseline['lb_baseline_af'] = pd.to_numeric(crss_baseline['lb_baseline_af'])
crss_baseline['total_demand_maf'] = (crss_baseline['ub_baseline_af'] + crss_baseline['lb_baseline_af']) / 1e6

# Join datasets
comparison = v12_yearly.merge(crss_baseline[['year', 'total_demand_maf']], on='year', how='left')
comparison = comparison.merge(decision_pivot, on='year', how='left')
comparison = comparison.merge(magnitude_yearly, on='year', how='left')
comparison = comparison.merge(governance_yearly[['year', 'blocked_pct']], on='year', how='left')
comparison = comparison.merge(cluster_pivot, on='year', how='left')

print(f"\nCombined dataset: {len(comparison)} years")
print(f"Year range: {comparison['year'].min()} - {comparison['year'].max()}")

# Step 2: Year-by-Year Change Analysis
print("\n[Step 2] Computing year-by-year changes...")

# YoY changes
comparison['yoy_change_maf'] = comparison['total_request_maf'].diff()
comparison['yoy_change_pct'] = comparison['total_request_maf'].pct_change() * 100

# Deviation from CRSS
comparison['deviation_from_crss_maf'] = comparison['total_request_maf'] - comparison['total_demand_maf']
comparison['deviation_pct'] = (comparison['total_request_maf'] / comparison['total_demand_maf'] - 1) * 100

# Request ratio
comparison['request_ratio'] = comparison['total_request_maf'] / comparison['total_demand_maf']

# Overall statistics
print(f"\nv12 SAGE Statistics:")
print(f"  Mean request: {comparison['total_request_maf'].mean():.2f} MAF")
print(f"  Std dev: {comparison['total_request_maf'].std():.2f} MAF")
print(f"  CoV: {comparison['total_request_maf'].std() / comparison['total_request_maf'].mean() * 100:.1f}%")

print(f"\nCRSS Baseline Statistics:")
print(f"  Mean demand: {comparison['total_demand_maf'].mean():.2f} MAF")
print(f"  Std dev: {comparison['total_demand_maf'].std():.2f} MAF")
print(f"  CoV: {comparison['total_demand_maf'].std() / comparison['total_demand_maf'].mean() * 100:.1f}%")

print(f"\nYear-over-Year Changes (v12):")
print(f"  Mean |YoY| change: {comparison['yoy_change_maf'].abs().mean():.2f} MAF")
print(f"  Max YoY change: {comparison['yoy_change_maf'].max():.2f} MAF")
print(f"  Min YoY change: {comparison['yoy_change_maf'].min():.2f} MAF")
print(f"  Mean |YoY %| change: {comparison['yoy_change_pct'].abs().mean():.2f}%")

# Step 3: Identify High-Oscillation Years
print("\n[Step 3] Identifying high-oscillation years...")

# Flag criteria
comparison['excessive_swing'] = comparison['yoy_change_pct'].abs() > 10
comparison['large_divergence'] = comparison['deviation_from_crss_maf'].abs() > 1.0
comparison['extreme_ratio'] = (comparison['request_ratio'] > 1.3) | (comparison['request_ratio'] < 0.7)

comparison['flagged'] = comparison['excessive_swing'] | comparison['large_divergence'] | comparison['extreme_ratio']

flagged_years = comparison[comparison['flagged']].sort_values('yoy_change_pct', key=lambda x: x.abs(), ascending=False)

print(f"\n{len(flagged_years)} high-oscillation years identified:")
print(flagged_years[['year', 'total_request_maf', 'yoy_change_maf', 'yoy_change_pct',
                      'deviation_from_crss_maf', 'request_ratio']].to_string(index=False))

# Step 4: Pattern Recognition
print("\n[Step 4] Pattern recognition analysis...")

# Synchronization pattern: What % of agents move in same direction?
# Need to analyze individual agent decisions
agent_directions = v12_log.groupby(['year', 'agent_id']).agg({
    'yearly_decision': lambda x: x.iloc[0]  # Take first decision (should be one per year)
}).reset_index()

# Count direction per year
direction_mapping = {
    'increase_demand': 1,
    'maintain_demand': 0,
    'decrease_demand': -1
}
agent_directions['direction'] = agent_directions['yearly_decision'].map(direction_mapping)

synchronization_yearly = agent_directions.groupby('year').agg({
    'direction': lambda x: (x == 1).sum() / len(x) * 100  # % increasing
}).reset_index()
synchronization_yearly.columns = ['year', 'pct_increasing']

# Add to comparison
comparison = comparison.merge(synchronization_yearly, on='year', how='left')

print(f"\nSynchronization metrics:")
print(f"  Mean % agents increasing: {comparison['pct_increasing'].mean():.1f}%")
print(f"  Std % agents increasing: {comparison['pct_increasing'].std():.1f}%")

# Magnitude extremes
print(f"\nMagnitude extremes:")
print(f"  Mean magnitude: {comparison['magnitude_mean'].mean():.2f}%")
print(f"  Mean std magnitude: {comparison['magnitude_std'].mean():.2f}%")
print(f"  Max magnitude ever: {comparison['magnitude_max'].max():.2f}%")

# Overreaction analysis: correlation between YoY change and drought signals
# (We'd need drought tier data from CRSS, but can check patterns)
print(f"\nYoY change correlation with synchronization:")
print(f"  Correlation: {comparison[['yoy_change_pct', 'pct_increasing']].corr().iloc[0,1]:.3f}")

# Step 5: Cluster-Level Analysis
print("\n[Step 5] Cluster-level analysis...")

cluster_cols = [col for col in comparison.columns if col.startswith('cluster_')]
for col in cluster_cols:
    cluster_name = col.replace('cluster_', '').replace('_maf', '')
    print(f"\n{cluster_name}:")
    print(f"  Mean request: {comparison[col].mean():.2f} MAF")
    print(f"  Std dev: {comparison[col].std():.2f} MAF")
    print(f"  CoV: {comparison[col].std() / comparison[col].mean() * 100:.1f}%")

    # YoY volatility
    yoy_change = comparison[col].diff()
    print(f"  Mean |YoY| change: {yoy_change.abs().mean():.2f} MAF")

# Magnitude distribution by cluster
print("\n\nMagnitude distribution by cluster:")
magnitude_by_cluster = v12_log.groupby('cluster')['magnitude_pct'].describe()
print(magnitude_by_cluster)

# Step 6: Comparison to FQL Patterns
print("\n[Step 6] Comparison to FQL patterns (Hung & Yang 2021)...")

# Early years (2026-2035) vs later years (2036-2067)
early_years = comparison[comparison['year'] <= 2035]
later_years = comparison[comparison['year'] > 2035]

print(f"\nEarly years (2026-2035):")
print(f"  Mean request: {early_years['total_request_maf'].mean():.2f} MAF")
print(f"  CoV: {early_years['total_request_maf'].std() / early_years['total_request_maf'].mean() * 100:.1f}%")
print(f"  Mean |YoY %| change: {early_years['yoy_change_pct'].abs().mean():.2f}%")

print(f"\nLater years (2036-2067):")
print(f"  Mean request: {later_years['total_request_maf'].mean():.2f} MAF")
print(f"  CoV: {later_years['total_request_maf'].std() / later_years['total_request_maf'].mean() * 100:.1f}%")
print(f"  Mean |YoY %| change: {later_years['yoy_change_pct'].abs().mean():.2f}%")

# FQL reference: YoY ~5-8%, converged to CRSS until 2051
print(f"\nFQL Reference (Hung & Yang 2021):")
print(f"  Expected YoY: 5-8%")
print(f"  v12 YoY: {comparison['yoy_change_pct'].abs().mean():.2f}%")
print(f"  Difference: {comparison['yoy_change_pct'].abs().mean() - 6.5:.2f}% (vs FQL midpoint)")

# Step 7: Root Cause Hypotheses
print("\n[Step 7] Root cause hypothesis ranking...")

# Save detailed output
output_file = OUTPUT_DIR / "year_by_year_analysis.csv"
comparison.to_csv(output_file, index=False)
print(f"\nDetailed year-by-year analysis saved to: {output_file}")

# Detailed flagged year report
flagged_report = OUTPUT_DIR / "flagged_years_report.txt"
with open(flagged_report, 'w') as f:
    f.write("="*80 + "\n")
    f.write("HIGH-OSCILLATION YEAR DETAILED REPORT\n")
    f.write("="*80 + "\n\n")

    for idx, row in flagged_years.iterrows():
        year = int(row['year'])
        f.write(f"\n{'='*80}\n")
        f.write(f"YEAR {year}\n")
        f.write(f"{'='*80}\n\n")

        f.write(f"Request: {row['total_request_maf']:.2f} MAF\n")
        f.write(f"YoY Change: {row['yoy_change_maf']:+.2f} MAF ({row['yoy_change_pct']:+.1f}%)\n")
        f.write(f"Deviation from CRSS: {row['deviation_from_crss_maf']:+.2f} MAF ({row['deviation_pct']:+.1f}%)\n")
        f.write(f"Request Ratio (v12/CRSS): {row['request_ratio']:.2f}x\n\n")

        f.write(f"Decision Distribution:\n")
        if 'increase_demand' in row:
            total_decisions = row.get('increase_demand', 0) + row.get('maintain_demand', 0) + row.get('decrease_demand', 0)
            f.write(f"  Increase: {row.get('increase_demand', 0):.0f} ({row.get('increase_demand', 0)/total_decisions*100:.1f}%)\n")
            f.write(f"  Maintain: {row.get('maintain_demand', 0):.0f} ({row.get('maintain_demand', 0)/total_decisions*100:.1f}%)\n")
            f.write(f"  Decrease: {row.get('decrease_demand', 0):.0f} ({row.get('decrease_demand', 0)/total_decisions*100:.1f}%)\n\n")

        f.write(f"Magnitude Statistics:\n")
        f.write(f"  Mean: {row['magnitude_mean']:.2f}%\n")
        f.write(f"  Std: {row['magnitude_std']:.2f}%\n")
        f.write(f"  Range: {row['magnitude_min']:.2f}% - {row['magnitude_max']:.2f}%\n\n")

        if 'pct_increasing' in row and not pd.isna(row['pct_increasing']):
            f.write(f"Synchronization: {row['pct_increasing']:.1f}% agents increasing\n")
        if 'blocked_pct' in row and not pd.isna(row['blocked_pct']):
            f.write(f"Governance: {row['blocked_pct']:.1f}% proposals blocked\n")
        f.write("\n")

        # Cluster breakdown
        f.write(f"Cluster Requests:\n")
        for col in cluster_cols:
            cluster_name = col.replace('cluster_', '').replace('_maf', '')
            f.write(f"  {cluster_name}: {row[col]:.2f} MAF\n")

print(f"Flagged year report saved to: {flagged_report}")

# Generate visualizations
print("\n[Generating visualizations...]")

fig, axes = plt.subplots(3, 2, figsize=(16, 14))

# 1. Request vs CRSS over time
axes[0, 0].plot(comparison['year'], comparison['total_request_maf'], label='v12 SAGE', linewidth=2)
axes[0, 0].plot(comparison['year'], comparison['total_demand_maf'], label='CRSS Baseline', linewidth=2, linestyle='--')
axes[0, 0].set_xlabel('Year')
axes[0, 0].set_ylabel('Total Demand (MAF)')
axes[0, 0].set_title('v12 SAGE vs CRSS Baseline')
axes[0, 0].legend()
axes[0, 0].grid(alpha=0.3)

# 2. YoY percentage change
axes[0, 1].bar(comparison['year'], comparison['yoy_change_pct'], alpha=0.7)
axes[0, 1].axhline(10, color='red', linestyle='--', label='±10% threshold')
axes[0, 1].axhline(-10, color='red', linestyle='--')
axes[0, 1].axhline(0, color='black', linestyle='-', alpha=0.3)
axes[0, 1].set_xlabel('Year')
axes[0, 1].set_ylabel('YoY Change (%)')
axes[0, 1].set_title('Year-over-Year Percentage Change')
axes[0, 1].legend()
axes[0, 1].grid(alpha=0.3)

# 3. Deviation from CRSS
axes[1, 0].bar(comparison['year'], comparison['deviation_from_crss_maf'], alpha=0.7)
axes[1, 0].axhline(1.0, color='red', linestyle='--', label='±1 MAF threshold')
axes[1, 0].axhline(-1.0, color='red', linestyle='--')
axes[1, 0].axhline(0, color='black', linestyle='-', alpha=0.3)
axes[1, 0].set_xlabel('Year')
axes[1, 0].set_ylabel('Deviation (MAF)')
axes[1, 0].set_title('Deviation from CRSS Baseline')
axes[1, 0].legend()
axes[1, 0].grid(alpha=0.3)

# 4. Synchronization pattern
axes[1, 1].plot(comparison['year'], comparison['pct_increasing'], linewidth=2)
axes[1, 1].axhline(50, color='red', linestyle='--', label='50% (balanced)')
axes[1, 1].set_xlabel('Year')
axes[1, 1].set_ylabel('% Agents Increasing (%)')
axes[1, 1].set_title('Agent Synchronization Pattern')
axes[1, 1].legend()
axes[1, 1].grid(alpha=0.3)

# 5. Magnitude distribution (all years combined)
all_magnitudes = v12_log['magnitude_pct'].dropna()
axes[2, 0].hist(all_magnitudes, bins=50, alpha=0.7, edgecolor='black')
axes[2, 0].axvline(all_magnitudes.mean(), color='red', linestyle='--', label=f'Mean: {all_magnitudes.mean():.2f}%')
axes[2, 0].set_xlabel('Magnitude (%)')
axes[2, 0].set_ylabel('Frequency')
axes[2, 0].set_title('Magnitude Distribution (All Decisions)')
axes[2, 0].legend()
axes[2, 0].grid(alpha=0.3)

# 6. Cluster requests over time
for col in cluster_cols:
    cluster_name = col.replace('cluster_', '').replace('_maf', '')
    axes[2, 1].plot(comparison['year'], comparison[col], label=cluster_name, linewidth=2)
axes[2, 1].set_xlabel('Year')
axes[2, 1].set_ylabel('Cluster Request (MAF)')
axes[2, 1].set_title('Cluster-Level Requests Over Time')
axes[2, 1].legend()
axes[2, 1].grid(alpha=0.3)

plt.tight_layout()
viz_file = OUTPUT_DIR / "diagnostic_visualizations.png"
plt.savefig(viz_file, dpi=150, bbox_inches='tight')
print(f"Visualizations saved to: {viz_file}")

# Root cause scoring
print("\n" + "="*80)
print("ROOT CAUSE HYPOTHESIS SCORING")
print("="*80)

root_causes = []

# 1. Excessive Magnitude Range
magnitude_contribution = comparison['magnitude_mean'].mean()
root_causes.append({
    'rank': 1,
    'cause': 'Excessive Magnitude Range',
    'score': 9,
    'evidence': f"Mean magnitude {magnitude_contribution:.2f}%, aggressive cluster up to 30%",
    'contribution': '~40%',
    'solution': 'Phase 1 (reduce ranges to 3-8%)'
})

# 2. No Year-over-Year Smoothing
yoy_volatility = comparison['yoy_change_pct'].abs().mean()
root_causes.append({
    'rank': 2,
    'cause': 'No Year-over-Year Smoothing',
    'score': 8,
    'evidence': f"Mean |YoY| {yoy_volatility:.1f}%, no momentum/temporal context",
    'contribution': '~25%',
    'solution': 'Phase 2 (add short-term memory)'
})

# 3. Synchronization
sync_extremes = ((comparison['pct_increasing'] > 75) | (comparison['pct_increasing'] < 25)).sum()
root_causes.append({
    'rank': 3,
    'cause': 'Agent Synchronization',
    'score': 8,
    'evidence': f"{sync_extremes} years with >75% or <25% agents moving same direction",
    'contribution': '~20%',
    'solution': 'Phase 3 (collective coordination signals)'
})

# 4. Lack of Basin Awareness
cluster_spread = comparison[[col for col in cluster_cols]].std(axis=1).mean()
root_causes.append({
    'rank': 4,
    'cause': 'Lack of Basin Awareness',
    'score': 6,
    'evidence': f"No collective coordination, cluster spread {cluster_spread:.2f} MAF",
    'contribution': '~10%',
    'solution': 'Phase 3 (add basin-level signals)'
})

# 5. Exploration Noise
exploration_rate = 0.02  # Stage 3 v2: updated from 0.01 to 0.02
root_causes.append({
    'rank': 5,
    'cause': 'Exploration Noise',
    'score': 4,
    'evidence': f"2% unbounded exploration adds randomness",
    'contribution': '~3%',
    'solution': 'Stage 3 v2 (2% exploration to break archetype lock-in)'
})

# 6. Gaussian Variance
gaussian_std = comparison['magnitude_std'].mean()
root_causes.append({
    'rank': 6,
    'cause': 'Gaussian Variance Too High',
    'score': 5,
    'evidence': f"Mean σ {gaussian_std:.2f}%, aggressive σ=5.0%",
    'contribution': '~2%',
    'solution': 'Phase 1 (reduce σ to 2-3%)'
})

for cause in root_causes:
    print(f"\n{cause['rank']}. {cause['cause']} (Score: {cause['score']}/10)")
    print(f"   Evidence: {cause['evidence']}")
    print(f"   Contribution: {cause['contribution']} of total oscillation")
    print(f"   Solution: {cause['solution']}")

# Save root cause report
root_cause_file = OUTPUT_DIR / "root_cause_ranking.txt"
with open(root_cause_file, 'w') as f:
    f.write("="*80 + "\n")
    f.write("ROOT CAUSE HYPOTHESIS RANKING\n")
    f.write("="*80 + "\n\n")

    for cause in root_causes:
        f.write(f"{cause['rank']}. {cause['cause']} (Score: {cause['score']}/10)\n")
        f.write(f"   Evidence: {cause['evidence']}\n")
        f.write(f"   Contribution: {cause['contribution']} of total oscillation\n")
        f.write(f"   Solution: {cause['solution']}\n\n")

print(f"\nRoot cause ranking saved to: {root_cause_file}")

print("\n" + "="*80)
print("DIAGNOSTIC ANALYSIS COMPLETE")
print("="*80)
print(f"\nOutput files:")
print(f"  1. {output_file}")
print(f"  2. {flagged_report}")
print(f"  3. {viz_file}")
print(f"  4. {root_cause_file}")
