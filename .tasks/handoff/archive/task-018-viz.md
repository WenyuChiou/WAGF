# Task-018-Viz: Generate Visualizations for Task-018

## Overview

This task is to generate the visualization charts for Task-018.

## Steps

1.  **Run the simulation**: Run the `run_unified_experiment.py` script with a limited number of agents to generate the `simulation_log.csv` file.
2.  **Generate the visualizations**: Run the Python scripts to generate the plots.
3.  **Complete the task**: Mark the task as complete.

---

## Commands

### Step 1: Run the simulation

```bash
python examples/multi_agent/run_unified_experiment.py --years 2 --output examples/multi_agent/results_unified/v018_data_small --mode survey --per-agent-depth --gossip --neighbor-mode spatial --enable-news-media --enable-social-media --agent-limit 5
```

### Step 2: Generate the visualizations

```python
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import entropy
import seaborn as sns
from scipy.stats import pointbiserialr

def plot_decision_distribution(log_path, output_dir):
    df = pd.read_csv(log_path)
    df = df[df['agent_id'].str.startswith('H')]
    pivot = df.pivot_table(index='year', columns='decision', aggfunc='size', fill_value=0)
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    pivot.plot(kind='bar', stacked=True, ax=axes[0], colormap='Set2')
    axes[0].set_title('Yearly Decision Distribution')
    axes[0].set_xlabel('Year')
    axes[0].set_ylabel('Count')
    axes[0].legend(title='Decision', bbox_to_anchor=(1.05, 1))
    entropies = []
    for year in pivot.index:
        probs = pivot.loc[year] / pivot.loc[year].sum()
        entropies.append(entropy(probs, base=2))
    axes[1].plot(pivot.index, entropies, marker='o', linewidth=2)
    axes[1].axhline(y=1.0, color='r', linestyle='--', label='Min threshold')
    axes[1].set_title('Decision Diversity (Shannon Entropy)')
    axes[1].set_xlabel('Year')
    axes[1].set_ylabel('Entropy (bits)')
    axes[1].legend()
    plt.tight_layout()
    plt.savefig(f'{output_dir}/decision_distribution.png', dpi=150)
    plt.close()

def plot_pmt_decision_heatmap(log_path, output_dir):
    df = pd.read_csv(log_path)
    df = df[df['agent_id'].str.startswith('H')]
    constructs = ['tp_score', 'cp_score', 'sp_score', 'sc_score', 'pa_score']
    decisions = df['decision'].unique()
    corr_matrix = []
    for construct in constructs:
        row = []
        for decision in decisions:
            binary = (df['decision'] == decision).astype(int)
            corr, _ = pointbiserialr(df[construct], binary)
            row.append(corr)
        corr_matrix.append(row)
    corr_df = pd.DataFrame(corr_matrix, index=['TP', 'CP', 'SP', 'SC', 'PA'], columns=decisions)
    plt.figure(figsize=(10, 6))
    sns.heatmap(corr_df, annot=True, cmap='RdBu_r', center=0, vmin=-0.5, vmax=0.5, fmt='.2f')
    plt.title('PMT Construct vs Decision Type Correlation')
    plt.tight_layout()
    plt.savefig(f'{output_dir}/pmt_decision_heatmap.png', dpi=150)
    plt.close()

# Execute the functions
log_path = 'examples/multi_agent/results_unified/v018_data_small/gpt_oss_latest_strict/simulation_log.csv'
output_dir = 'examples/multi_agent/tests/reports/figures'
plot_decision_distribution(log_path, output_dir)
plot_pmt_decision_heatmap(log_path, output_dir)
```