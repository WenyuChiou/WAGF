#!/usr/bin/env python3
"""
Governed vs Ungoverned Irrigation ABM Comparison Pipeline

Comprehensive analysis comparing governed vs ungoverned irrigation experiments
for Nature Water article. Processes multiple seeds, computes ensemble statistics,
performs statistical tests, and generates comparison figures.

Usage:
    python governed_vs_ungoverned.py
    python governed_vs_ungoverned.py --seeds "42,43,44"
    python governed_vs_ungoverned.py --results-base "examples/irrigation_abm/results/"

Outputs:
    - governed_vs_ungoverned_results.json: All metrics with ensemble statistics
    - governed_vs_ungoverned_table.csv: Comparison table
    - figures/: EHE trajectory, demand trajectory, skill distribution, etc.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Configure UTF-8 for Windows
sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore', category=RuntimeWarning)

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

# Add analysis directory to path for compute_ibr import
ANALYSIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS_DIR))

# Import from compute_ibr.py
from compute_ibr import compute_ibr_metrics, compute_ehe, load_run_data


# =============================================================================
# Constants
# =============================================================================

N_AGENTS = 78
N_YEARS = 42
N_DECISIONS_PER_RUN = N_AGENTS * N_YEARS  # 3276


# =============================================================================
# Data Loading & Aggregation
# =============================================================================

def load_ensemble_data(
    results_base: Path,
    seeds: List[int],
    condition: str = "governed"
) -> Tuple[Dict, List[pd.DataFrame]]:
    """
    Load data from multiple seed runs.

    Args:
        results_base: Base results directory
        seeds: List of seed values
        condition: "governed" or "ungoverned"

    Returns:
        (ensemble_metrics, dataframes_list)
        ensemble_metrics contains mean±std across seeds
        dataframes_list contains raw data for trajectory analysis
    """
    metrics_list = []
    dfs = []
    successful_seeds = []

    prefix = "production_v20_42yr_seed" if condition == "governed" else "ungoverned_v20_42yr_seed"

    for seed in seeds:
        results_dir = results_base / f"{prefix}{seed}"
        if not results_dir.exists():
            print(f"  WARNING: {results_dir.name} not found, skipping...")
            continue

        try:
            # Compute IBR metrics (use proposed for ungoverned, final for governed)
            use_proposed = (condition == "ungoverned")
            metrics = compute_ibr_metrics(results_dir, use_proposed=use_proposed)
            metrics_list.append(metrics)

            # Load raw data for trajectory analysis
            df = load_run_data(results_dir)
            df['seed'] = seed
            dfs.append(df)

            successful_seeds.append(seed)
            print(f"  Loaded seed {seed}: {len(df)} decisions, CACR={metrics['cacr_irrigation']:.4f}")
        except FileNotFoundError as e:
            print(f"  ERROR: File not found for seed {seed}: {e}")
            continue
        except KeyError as e:
            print(f"  ERROR: Missing required column for seed {seed}: {e}")
            continue
        except Exception as e:
            print(f"  ERROR loading seed {seed} ({type(e).__name__}): {e}")
            continue

    if len(metrics_list) == 0:
        print(f"  WARNING: No valid {condition} runs found for seeds {seeds}")
        return None, []

    # Compute ensemble statistics
    ensemble = {
        'n_seeds': len(metrics_list),
        'seeds': successful_seeds,
    }

    # Aggregate scalar metrics
    for key in ['ibr_physical', 'ibr_coherence', 'ibr_temporal', 'cacr_irrigation', 'ehe_mean']:
        values = [m[key] for m in metrics_list]
        ensemble[f'{key}_mean'] = round(float(np.mean(values)), 4)
        ensemble[f'{key}_std'] = round(float(np.std(values, ddof=1)), 4) if len(values) > 1 else 0.0
        ensemble[f'{key}_values'] = values

    # Aggregate skill distributions
    all_skills = {}
    for m in metrics_list:
        for skill, count in m.get('skill_distribution', {}).items():
            all_skills[skill] = all_skills.get(skill, 0) + count
    total_decisions = sum(all_skills.values())
    ensemble['skill_distribution'] = {
        k: round(v / total_decisions, 4) for k, v in all_skills.items()
    }

    # Aggregate quadrant CACR
    quadrant_lists = {}
    for m in metrics_list:
        for q, cacr in m.get('quadrant_cacr', {}).items():
            if q not in quadrant_lists:
                quadrant_lists[q] = []
            quadrant_lists[q].append(cacr)
    ensemble['quadrant_cacr'] = {
        q: {
            'mean': round(float(np.mean(vals)), 4),
            'std': round(float(np.std(vals, ddof=1)), 4) if len(vals) > 1 else 0.0
        }
        for q, vals in quadrant_lists.items()
    }

    # Governance intervention stats (governed only)
    if condition == "governed":
        gov_rates = [m['governance_intervention_rate'] for m in metrics_list
                     if m.get('governance_intervention_rate') is not None]
        if gov_rates:
            ensemble['governance_intervention_rate_mean'] = round(float(np.mean(gov_rates)), 4)
            ensemble['governance_intervention_rate_std'] = round(float(np.std(gov_rates, ddof=1)), 4) if len(gov_rates) > 1 else 0.0

    return ensemble, dfs


# =============================================================================
# Analysis 1: IBR Ensemble Comparison
# =============================================================================

def report_ibr_ensemble(governed: Dict, ungoverned: Dict) -> str:
    """Generate formatted ensemble comparison report."""
    report = []
    report.append("\n" + "=" * 90)
    report.append("IBR ENSEMBLE COMPARISON (Governed vs Ungoverned)")
    report.append("=" * 90)

    report.append(f"\nSeeds: Governed n={governed['n_seeds']}, Ungoverned n={ungoverned['n_seeds']}")
    report.append(f"Governed seeds: {governed['seeds']}")
    report.append(f"Ungoverned seeds: {ungoverned['seeds']}")

    report.append(f"\n{'Metric':<30} {'Ungoverned (mean±std)':<25} {'Governed (mean±std)':<25} {'Delta':<15}")
    report.append("-" * 95)

    metrics_to_compare = [
        ("CACR (Coherence)", "cacr_irrigation"),
        ("IBR Physical", "ibr_physical"),
        ("IBR Coherence", "ibr_coherence"),
        ("IBR Temporal", "ibr_temporal"),
        ("EHE (Mean Entropy)", "ehe_mean"),
    ]

    for label, key in metrics_to_compare:
        ug_mean = ungoverned[f'{key}_mean']
        ug_std = ungoverned[f'{key}_std']
        gv_mean = governed[f'{key}_mean']
        gv_std = governed[f'{key}_std']
        delta = gv_mean - ug_mean

        ug_str = f"{ug_mean:.4f} ± {ug_std:.4f}"
        gv_str = f"{gv_mean:.4f} ± {gv_std:.4f}"
        report.append(f"{label:<30} {ug_str:<25} {gv_str:<25} {delta:+.4f}")

    # Governance value
    report.append("\n" + "-" * 95)
    gov_value = governed['cacr_irrigation_mean'] - ungoverned['cacr_irrigation_mean']
    report.append(f"Governance Value-Add (CACR improvement): {gov_value:+.4f}")
    if 'governance_intervention_rate_mean' in governed:
        gov_int = governed['governance_intervention_rate_mean']
        gov_int_std = governed.get('governance_intervention_rate_std', 0.0)
        report.append(f"Intervention Rate: {gov_int:.4f} ± {gov_int_std:.4f}")

    report.append("=" * 90)
    return "\n".join(report)


# =============================================================================
# Analysis 2: EHE Trajectory
# =============================================================================

def compute_ehe_trajectories(dfs: List[pd.DataFrame]) -> pd.DataFrame:
    """Compute EHE per year for each seed."""
    trajectories = []

    for df in dfs:
        seed = df['seed'].iloc[0]
        ehe_by_year = compute_ehe(df, skill_col='yearly_decision')['ehe_by_year']
        for year, ehe in ehe_by_year.items():
            trajectories.append({'seed': seed, 'year': year, 'ehe': ehe})

    return pd.DataFrame(trajectories)


def plot_ehe_trajectory(
    gov_dfs: List[pd.DataFrame],
    ungov_dfs: List[pd.DataFrame],
    output_dir: Path
):
    """Plot EHE trajectories comparing governed vs ungoverned."""
    gov_traj = compute_ehe_trajectories(gov_dfs)

    # Compute mean and std per year
    gov_mean = gov_traj.groupby('year')['ehe'].mean()
    gov_std = gov_traj.groupby('year')['ehe'].std().fillna(0)

    fig, ax = plt.subplots(figsize=(12, 6))
    years = gov_mean.index

    # Plot governed
    ax.plot(years, gov_mean, 'b-', linewidth=2, label='Governed', alpha=0.8)
    ax.fill_between(years, gov_mean - gov_std, gov_mean + gov_std,
                     color='blue', alpha=0.2)

    # Plot ungoverned (if available)
    if ungov_dfs:
        ungov_traj = compute_ehe_trajectories(ungov_dfs)
        ungov_mean = ungov_traj.groupby('year')['ehe'].mean()
        ungov_std = ungov_traj.groupby('year')['ehe'].std().fillna(0)
        ax.plot(years, ungov_mean, 'r--', linewidth=2, label='Ungoverned', alpha=0.8)
        ax.fill_between(years, ungov_mean - ungov_std, ungov_mean + ungov_std,
                         color='red', alpha=0.2)
        for seed in ungov_traj['seed'].unique():
            seed_data = ungov_traj[ungov_traj['seed'] == seed]
            ax.plot(seed_data['year'], seed_data['ehe'], 'r--', alpha=0.15, linewidth=1)

    # Individual seed traces (lighter)
    for seed in gov_traj['seed'].unique():
        seed_data = gov_traj[gov_traj['seed'] == seed]
        ax.plot(seed_data['year'], seed_data['ehe'], 'b-', alpha=0.15, linewidth=1)

    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('EHE (Effective Heterogeneity Entropy)', fontsize=12)
    ax.set_title('Behavioral Diversity Over Time: Governed vs Ungoverned', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11, loc='best')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1)

    plt.tight_layout()
    plt.savefig(output_dir / 'ehe_trajectory.png', dpi=300, bbox_inches='tight')
    plt.savefig(output_dir / 'ehe_trajectory.pdf', bbox_inches='tight')
    plt.close()

    print(f"  Saved: ehe_trajectory.png, ehe_trajectory.pdf")


# =============================================================================
# Analysis 3: Demand Trajectory
# =============================================================================

def compute_demand_trajectories(dfs: List[pd.DataFrame]) -> pd.DataFrame:
    """Compute aggregate demand ratio per year for each seed."""
    trajectories = []

    for df in dfs:
        seed = df['seed'].iloc[0]

        # Get baseline water rights from year 1
        baseline = df[df['year'] == 1]['water_right'].sum()

        for year in df['year'].unique():
            year_data = df[df['year'] == year]
            total_request = year_data['request'].sum()
            demand_ratio = total_request / baseline if baseline > 0 else 1.0
            trajectories.append({
                'seed': seed,
                'year': year,
                'demand_ratio': demand_ratio,
            })

    return pd.DataFrame(trajectories)


def plot_demand_trajectory(
    gov_dfs: List[pd.DataFrame],
    ungov_dfs: List[pd.DataFrame],
    output_dir: Path
):
    """Plot demand trajectories comparing governed vs ungoverned."""
    gov_traj = compute_demand_trajectories(gov_dfs)

    # Compute mean and std per year
    gov_mean = gov_traj.groupby('year')['demand_ratio'].mean()
    gov_std = gov_traj.groupby('year')['demand_ratio'].std().fillna(0)

    fig, ax = plt.subplots(figsize=(12, 6))
    years = gov_mean.index

    # Plot governed
    ax.plot(years, gov_mean, 'b-', linewidth=2, label='Governed', alpha=0.8)
    ax.fill_between(years, gov_mean - gov_std, gov_mean + gov_std,
                     color='blue', alpha=0.2)

    # Plot ungoverned (if available)
    if ungov_dfs:
        ungov_traj = compute_demand_trajectories(ungov_dfs)
        ungov_mean = ungov_traj.groupby('year')['demand_ratio'].mean()
        ungov_std = ungov_traj.groupby('year')['demand_ratio'].std().fillna(0)
        ax.plot(years, ungov_mean, 'r--', linewidth=2, label='Ungoverned', alpha=0.8)
        ax.fill_between(years, ungov_mean - ungov_std, ungov_mean + ungov_std,
                         color='red', alpha=0.2)
        for seed in ungov_traj['seed'].unique():
            seed_data = ungov_traj[ungov_traj['seed'] == seed]
            ax.plot(seed_data['year'], seed_data['demand_ratio'], 'r--', alpha=0.15, linewidth=1)

    # Individual governed seed traces (lighter)
    for seed in gov_traj['seed'].unique():
        seed_data = gov_traj[gov_traj['seed'] == seed]
        ax.plot(seed_data['year'], seed_data['demand_ratio'], 'b-', alpha=0.15, linewidth=1)

    # Reference line at CRSS baseline (1.0)
    ax.axhline(y=1.0, color='black', linestyle=':', linewidth=1.5,
               label='CRSS Baseline', alpha=0.7)

    ax.set_xlabel('Year', fontsize=12)
    ax.set_ylabel('Aggregate Demand Ratio (Request / Baseline)', fontsize=12)
    ax.set_title('Aggregate Water Demand Over Time: Governed vs Ungoverned', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11, loc='best')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / 'demand_trajectory.png', dpi=300, bbox_inches='tight')
    plt.savefig(output_dir / 'demand_trajectory.pdf', bbox_inches='tight')
    plt.close()

    print(f"  Saved: demand_trajectory.png, demand_trajectory.pdf")


# =============================================================================
# Analysis 4: Governance Value Decomposition
# =============================================================================

def compute_governance_value_decomposition(gov_dfs: List[pd.DataFrame]) -> Dict:
    """
    Compute pre-governance vs post-governance CACR.

    Pre-governance CACR uses proposed_skill from audit.
    Post-governance CACR uses final_skill / yearly_decision.
    """
    results = []

    for df in gov_dfs:
        seed = df['seed'].iloc[0]

        # Check if we have audit data
        if 'proposed_skill' not in df.columns or df['proposed_skill'].isna().all():
            print(f"  WARNING: No proposed_skill data for seed {seed}, skipping decomposition")
            continue

        # Pre-governance coherence (proposed_skill)
        from compute_ibr import is_coherent_skill
        df['pre_coherent'] = df.apply(
            lambda r: is_coherent_skill(r, skill_col='proposed_skill'), axis=1
        )
        pre_cacr = df['pre_coherent'].sum() / len(df)

        # Post-governance coherence (final_skill)
        df['post_coherent'] = df.apply(
            lambda r: is_coherent_skill(r, skill_col='final_skill'), axis=1
        )
        post_cacr = df['post_coherent'].sum() / len(df)

        gov_value = post_cacr - pre_cacr

        results.append({
            'seed': seed,
            'pre_governance_cacr': round(pre_cacr, 4),
            'post_governance_cacr': round(post_cacr, 4),
            'governance_value': round(gov_value, 4),
        })

    if not results:
        return {}

    # Compute ensemble statistics
    decomposition = {
        'n_seeds': len(results),
        'seeds': [r['seed'] for r in results],
        'pre_governance_cacr_mean': round(float(np.mean([r['pre_governance_cacr'] for r in results])), 4),
        'pre_governance_cacr_std': round(float(np.std([r['pre_governance_cacr'] for r in results], ddof=1)), 4) if len(results) > 1 else 0.0,
        'post_governance_cacr_mean': round(float(np.mean([r['post_governance_cacr'] for r in results])), 4),
        'post_governance_cacr_std': round(float(np.std([r['post_governance_cacr'] for r in results], ddof=1)), 4) if len(results) > 1 else 0.0,
        'governance_value_mean': round(float(np.mean([r['governance_value'] for r in results])), 4),
        'governance_value_std': round(float(np.std([r['governance_value'] for r in results], ddof=1)), 4) if len(results) > 1 else 0.0,
        'by_seed': results,
    }

    return decomposition


# =============================================================================
# Analysis 5: Skill Distribution Chi-Squared Test
# =============================================================================

def skill_distribution_test(gov_ensemble: Dict, ungov_ensemble: Dict) -> Dict:
    """
    Compare skill distributions using chi-squared test.
    """
    # Get all skill names
    all_skills = set(gov_ensemble['skill_distribution'].keys()) | set(ungov_ensemble['skill_distribution'].keys())
    all_skills = sorted(all_skills)

    # Build frequency table
    gov_freqs = [gov_ensemble['skill_distribution'].get(s, 0) for s in all_skills]
    ungov_freqs = [ungov_ensemble['skill_distribution'].get(s, 0) for s in all_skills]

    # Convert proportions back to counts (approximate)
    # Use total decisions from first seed as estimate
    n_gov = N_DECISIONS_PER_RUN * gov_ensemble['n_seeds']
    n_ungov = N_DECISIONS_PER_RUN * ungov_ensemble['n_seeds']

    gov_counts = [int(f * n_gov) for f in gov_freqs]
    ungov_counts = [int(f * n_ungov) for f in ungov_freqs]

    # Chi-squared test
    contingency = np.array([gov_counts, ungov_counts])
    chi2, p_value, dof, expected = stats.chi2_contingency(contingency)

    # Build frequency table
    freq_table = pd.DataFrame({
        'skill': all_skills,
        'governed_pct': [f * 100 for f in gov_freqs],
        'ungoverned_pct': [f * 100 for f in ungov_freqs],
        'governed_count': gov_counts,
        'ungoverned_count': ungov_counts,
    })

    return {
        'chi2_statistic': round(float(chi2), 4),
        'p_value': round(float(p_value), 6),
        'degrees_of_freedom': int(dof),
        'frequency_table': freq_table.to_dict('records'),
    }


def plot_skill_distribution(
    gov_ensemble: Dict,
    ungov_ensemble: Dict,
    chi2_results: Dict,
    output_dir: Path
):
    """Plot skill distribution comparison."""
    skills = sorted(set(gov_ensemble['skill_distribution'].keys()) |
                   set(ungov_ensemble['skill_distribution'].keys()))

    gov_pcts = [gov_ensemble['skill_distribution'].get(s, 0) * 100 for s in skills]
    ungov_pcts = [ungov_ensemble['skill_distribution'].get(s, 0) * 100 for s in skills]

    x = np.arange(len(skills))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))

    rects1 = ax.bar(x - width/2, ungov_pcts, width, label='Ungoverned',
                     color='#ff7f0e', alpha=0.8)
    rects2 = ax.bar(x + width/2, gov_pcts, width, label='Governed',
                     color='#1f77b4', alpha=0.8)

    ax.set_xlabel('Skill', fontsize=12)
    ax.set_ylabel('Frequency (%)', fontsize=12)
    ax.set_title(f'Skill Distribution Comparison (χ²={chi2_results["chi2_statistic"]:.2f}, p={chi2_results["p_value"]:.4f})',
                 fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(skills, rotation=30, ha='right')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_dir / 'skill_distribution.png', dpi=300, bbox_inches='tight')
    plt.savefig(output_dir / 'skill_distribution.pdf', bbox_inches='tight')
    plt.close()

    print(f"  Saved: skill_distribution.png, skill_distribution.pdf")


# =============================================================================
# Analysis 6: Cluster-Stratified Analysis
# =============================================================================

def cluster_stratified_analysis(
    gov_dfs: List[pd.DataFrame],
    ungov_dfs: List[pd.DataFrame]
) -> Dict:
    """
    Compute per-cluster IBR_coherence and EHE.
    """
    from compute_ibr import is_coherent_skill

    def analyze_clusters(dfs: List[pd.DataFrame], condition: str) -> Dict:
        all_df = pd.concat(dfs, ignore_index=True)

        cluster_stats = {}
        for cluster in sorted(all_df['cluster'].unique()):
            cluster_df = all_df[all_df['cluster'] == cluster]

            # Coherence rate
            cluster_df['coherent'] = cluster_df.apply(
                lambda r: is_coherent_skill(r, skill_col='yearly_decision'), axis=1
            )
            cacr = cluster_df['coherent'].sum() / len(cluster_df)

            # EHE
            ehe_result = compute_ehe(cluster_df, skill_col='yearly_decision')

            cluster_stats[str(cluster)] = {
                'n_decisions': len(cluster_df),
                'cacr': round(float(cacr), 4),
                'ehe_mean': ehe_result['ehe_mean'],
            }

        return cluster_stats

    gov_clusters = analyze_clusters(gov_dfs, 'governed')
    ungov_clusters = analyze_clusters(ungov_dfs, 'ungoverned') if ungov_dfs else {}

    return {
        'governed': gov_clusters,
        'ungoverned': ungov_clusters,
    }


# =============================================================================
# Analysis 7: Statistical Tests
# =============================================================================

def statistical_tests(gov_ensemble: Dict, ungov_ensemble: Dict) -> Dict:
    """
    Perform Mann-Whitney U tests, Cohen's d, and bootstrap CIs.
    """
    results = {}

    for metric in ['cacr_irrigation', 'ehe_mean']:
        gov_values = gov_ensemble[f'{metric}_values']
        ungov_values = ungov_ensemble[f'{metric}_values']

        # Mann-Whitney U test
        u_stat, p_value = stats.mannwhitneyu(gov_values, ungov_values, alternative='two-sided')

        # Cohen's d effect size
        pooled_std = np.sqrt((np.var(gov_values, ddof=1) + np.var(ungov_values, ddof=1)) / 2)
        cohens_d = (np.mean(gov_values) - np.mean(ungov_values)) / pooled_std if pooled_std > 0 else 0.0

        # Bootstrap CI for difference (10k resamples)
        n_bootstrap = 10000
        bootstrap_diffs = []
        rng = np.random.default_rng(42)  # Fixed seed for reproducibility
        for _ in range(n_bootstrap):
            gov_sample = rng.choice(gov_values, size=len(gov_values), replace=True)
            ungov_sample = rng.choice(ungov_values, size=len(ungov_values), replace=True)
            bootstrap_diffs.append(np.mean(gov_sample) - np.mean(ungov_sample))

        ci_lower = np.percentile(bootstrap_diffs, 2.5)
        ci_upper = np.percentile(bootstrap_diffs, 97.5)

        results[metric] = {
            'mann_whitney_u': round(float(u_stat), 4),
            'mann_whitney_p': round(float(p_value), 6),
            'cohens_d': round(float(cohens_d), 4),
            'bootstrap_ci_95': [round(float(ci_lower), 4), round(float(ci_upper), 4)],
            'effect_size_interpretation': interpret_cohens_d(cohens_d),
        }

    return results


def interpret_cohens_d(d: float) -> str:
    """Interpret Cohen's d effect size."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


# =============================================================================
# Analysis 8: Cross-Domain Alignment Table
# =============================================================================

def create_cross_domain_table(irrigation_results: Dict) -> pd.DataFrame:
    """
    Create cross-domain comparison table.

    Irrigation metrics from current analysis.
    Flood metrics hardcoded from paper/tables/Table1_main_grouped_columns_v4.csv:
        Gemma3-4B Group A: IBR=1.57%, EHE=0.456
        Gemma3-4B Group B: IBR=0.64%, EHE=0.657
    """
    table = pd.DataFrame([
        {
            'Domain': 'Flood (Group A)',
            'Model': 'Gemma3-4B',
            'IBR_Coherence (%)': 1.57,
            'EHE': 0.456,
            'CACR (%)': 98.43,  # 100 - 1.57
            'Notes': 'Owner + Renter, governed',
        },
        {
            'Domain': 'Flood (Group B)',
            'Model': 'Gemma3-4B',
            'IBR_Coherence (%)': 0.64,
            'EHE': 0.657,
            'CACR (%)': 99.36,  # 100 - 0.64
            'Notes': 'Renter only, governed',
        },
        {
            'Domain': 'Irrigation (Governed)',
            'Model': 'Gemma3-4B',
            'IBR_Coherence (%)': round(irrigation_results['governed']['ibr_coherence_mean'] * 100, 2),
            'EHE': irrigation_results['governed']['ehe_mean_mean'],
            'CACR (%)': round(irrigation_results['governed']['cacr_irrigation_mean'] * 100, 2),
            'Notes': f"78 CRSS agents, {irrigation_results['governed']['n_seeds']} seeds",
        },
    ])

    ungov = irrigation_results.get('ungoverned')
    if ungov and ungov.get('ibr_coherence_mean') is not None:
        table = pd.concat([table, pd.DataFrame([{
            'Domain': 'Irrigation (Ungoverned)',
            'Model': 'Gemma3-4B',
            'IBR_Coherence (%)': round(ungov['ibr_coherence_mean'] * 100, 2),
            'EHE': ungov['ehe_mean_mean'],
            'CACR (%)': round(ungov['cacr_irrigation_mean'] * 100, 2),
            'Notes': f"78 CRSS agents, {ungov['n_seeds']} seeds",
        }])], ignore_index=True)
    else:
        table = pd.concat([table, pd.DataFrame([{
            'Domain': 'Irrigation (Ungoverned)',
            'Model': 'Gemma3-4B',
            'IBR_Coherence (%)': '[TBD]',
            'EHE': '[TBD]',
            'CACR (%)': '[TBD]',
            'Notes': 'Experiments pending',
        }])], ignore_index=True)

    return table


# =============================================================================
# Main Pipeline
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Governed vs Ungoverned Irrigation ABM Comparison Pipeline"
    )
    parser.add_argument(
        "--results-base",
        type=str,
        default="examples/irrigation_abm/results/",
        help="Base results directory (default: examples/irrigation_abm/results/)",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default="42,43,44",
        help="Comma-separated seed values (default: 42,43,44)",
    )

    args = parser.parse_args()

    results_base = Path(args.results_base)
    if not results_base.is_absolute():
        results_base = PROJECT_ROOT / results_base

    seeds = [int(s.strip()) for s in args.seeds.split(',')]

    print("\n" + "=" * 90)
    print("GOVERNED VS UNGOVERNED IRRIGATION ABM COMPARISON PIPELINE")
    print("=" * 90)
    print(f"Results base: {results_base}")
    print(f"Seeds: {seeds}")

    # Create output directories
    output_dir = results_base.parent / "analysis" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Load ensemble data
    print("\n[1/8] Loading ensemble data...")
    print("  Loading governed runs...")
    gov_ensemble, gov_dfs = load_ensemble_data(results_base, seeds, "governed")
    if gov_ensemble is None:
        print("  FATAL: No governed data found. Aborting.")
        sys.exit(1)
    print("  Loading ungoverned runs...")
    ungov_ensemble, ungov_dfs = load_ensemble_data(results_base, seeds, "ungoverned")
    has_ungoverned = ungov_ensemble is not None

    # Analysis 1: IBR Ensemble Comparison
    print("\n[2/8] IBR Ensemble Comparison...")
    if has_ungoverned:
        ensemble_report = report_ibr_ensemble(gov_ensemble, ungov_ensemble)
        print(ensemble_report)
    else:
        print("  [SKIP] No ungoverned data — reporting governed only")
        for m in ['cacr_irrigation', 'ibr_physical', 'ibr_coherence', 'ehe_mean']:
            print(f"    {m}: {gov_ensemble[f'{m}_mean']:.4f} ± {gov_ensemble.get(f'{m}_std', 0):.4f}")

    # Analysis 2: EHE Trajectory
    print("\n[3/8] Computing EHE trajectories...")
    plot_ehe_trajectory(gov_dfs, ungov_dfs if has_ungoverned else [], output_dir)

    # Analysis 3: Demand Trajectory
    print("\n[4/8] Computing demand trajectories...")
    plot_demand_trajectory(gov_dfs, ungov_dfs if has_ungoverned else [], output_dir)

    # Analysis 4: Governance Value Decomposition
    print("\n[5/8] Computing governance value decomposition...")
    decomposition = compute_governance_value_decomposition(gov_dfs)
    if decomposition:
        print(f"  Pre-governance CACR:  {decomposition['pre_governance_cacr_mean']:.4f} ± {decomposition['pre_governance_cacr_std']:.4f}")
        print(f"  Post-governance CACR: {decomposition['post_governance_cacr_mean']:.4f} ± {decomposition['post_governance_cacr_std']:.4f}")
        print(f"  Governance value:     {decomposition['governance_value_mean']:+.4f} ± {decomposition['governance_value_std']:.4f}")

    # Analysis 5: Skill Distribution Chi-Squared
    chi2_results = None
    if has_ungoverned:
        print("\n[6/8] Skill distribution analysis...")
        chi2_results = skill_distribution_test(gov_ensemble, ungov_ensemble)
        print(f"  χ² = {chi2_results['chi2_statistic']:.4f}, p = {chi2_results['p_value']:.6f}")
        plot_skill_distribution(gov_ensemble, ungov_ensemble, chi2_results, output_dir)
    else:
        print("\n[6/8] Skill distribution analysis... [SKIP — no ungoverned data]")

    # Analysis 6: Cluster-Stratified Analysis
    print("\n[7/8] Cluster-stratified analysis...")
    cluster_analysis = cluster_stratified_analysis(gov_dfs, ungov_dfs if has_ungoverned else [])
    print("  Governed clusters:")
    for cluster, stats in cluster_analysis.get('governed', {}).items():
        print(f"    {cluster}: CACR={stats['cacr']:.4f}, EHE={stats['ehe_mean']:.4f}")
    if has_ungoverned:
        print("  Ungoverned clusters:")
        for cluster, stats in cluster_analysis.get('ungoverned', {}).items():
            print(f"    {cluster}: CACR={stats['cacr']:.4f}, EHE={stats['ehe_mean']:.4f}")

    # Analysis 7: Statistical Tests
    stat_tests = None
    if has_ungoverned:
        print("\n[8/8] Statistical tests...")
        stat_tests = statistical_tests(gov_ensemble, ungov_ensemble)
        for metric, results in stat_tests.items():
            print(f"\n  {metric.upper()}:")
            print(f"    Mann-Whitney U = {results['mann_whitney_u']:.4f}, p = {results['mann_whitney_p']:.6f}")
            print(f"    Cohen's d = {results['cohens_d']:.4f} ({results['effect_size_interpretation']})")
            print(f"    Bootstrap 95% CI: [{results['bootstrap_ci_95'][0]:.4f}, {results['bootstrap_ci_95'][1]:.4f}]")
    else:
        print("\n[8/8] Statistical tests... [SKIP — no ungoverned data]")

    # Cross-domain table
    print("\n[Bonus] Creating cross-domain alignment table...")
    cross_domain_table = create_cross_domain_table({
        'governed': gov_ensemble,
        'ungoverned': ungov_ensemble if has_ungoverned else {'cacr_irrigation_mean': None, 'ehe_mean_mean': None},
    })

    # Save results
    print("\nSaving results...")

    # JSON output
    results_json = {
        'governed': gov_ensemble,
        'ungoverned': ungov_ensemble,
        'governance_value_decomposition': decomposition,
        'skill_distribution_test': chi2_results,
        'cluster_analysis': cluster_analysis,
        'statistical_tests': stat_tests,
    }

    json_path = results_base.parent / "analysis" / "governed_vs_ungoverned_results.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results_json, f, indent=2, default=str)
    print(f"  Saved: {json_path}")

    # Comparison table CSV
    if has_ungoverned:
        comparison_data = []
        for metric in ['cacr_irrigation', 'ibr_physical', 'ibr_coherence', 'ibr_temporal', 'ehe_mean']:
            comparison_data.append({
                'Metric': metric,
                'Ungoverned_Mean': ungov_ensemble[f'{metric}_mean'],
                'Ungoverned_Std': ungov_ensemble[f'{metric}_std'],
                'Governed_Mean': gov_ensemble[f'{metric}_mean'],
                'Governed_Std': gov_ensemble[f'{metric}_std'],
                'Delta': gov_ensemble[f'{metric}_mean'] - ungov_ensemble[f'{metric}_mean'],
            })
        comparison_table = pd.DataFrame(comparison_data)

        table_path = results_base.parent / "analysis" / "governed_vs_ungoverned_table.csv"
        comparison_table.to_csv(table_path, index=False, encoding='utf-8')
        print(f"  Saved: {table_path}")
    else:
        print("  [SKIP] Comparison table — no ungoverned data")

    # Cross-domain table
    cross_domain_path = results_base.parent / "analysis" / "cross_domain_alignment_table.csv"
    cross_domain_table.to_csv(cross_domain_path, index=False, encoding='utf-8')
    print(f"  Saved: {cross_domain_path}")

    print("\n" + "=" * 90)
    print("PIPELINE COMPLETE")
    print("=" * 90)
    print(f"\nOutputs:")
    print(f"  - Metrics JSON: {json_path}")
    if has_ungoverned:
        table_path = results_base.parent / "analysis" / "governed_vs_ungoverned_table.csv"
        print(f"  - Comparison table: {table_path}")
    print(f"  - Cross-domain table: {cross_domain_path}")
    print(f"  - Figures: {output_dir}/")
    print()


if __name__ == "__main__":
    main()
