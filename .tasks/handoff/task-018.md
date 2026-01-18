# Task-018: MA Experiment Visualization & Analysis

## Last Updated

**2026-01-18T17:00:00Z** - Initial creation

## Metadata

| Field            | Value                                                    |
| :--------------- | :------------------------------------------------------- |
| **ID**           | Task-018                                                 |
| **Title**        | MA Experiment Visualization & Analysis                   |
| **Status**       | `planned`                                                |
| **Type**         | visualization                                            |
| **Priority**     | High                                                     |
| **Owner**        | antigravity                                              |
| **Reviewer**     | WenyuChiou                                               |
| **Dependencies** | Task-015 (MA System Verification)                        |
| **Handoff File** | `.tasks/handoff/task-018.md`                             |

---

## Overview

Create comprehensive visualization charts to analyze and communicate MA experiment results, focusing on:
1. Agent behavior patterns and decision diversity
2. PMT construct correlations with decisions
3. Marginalized Group (MG) equity analysis
4. Institutional policy impacts

---

## Subtask Assignments

### For Codex (CLI Executor)

| ID | Title | Priority | Description |
|:---|:------|:---------|:------------|
| **018-A** | Decision Distribution Charts | High | Yearly stacked bar charts + Shannon entropy trend |
| **018-B** | PMT-Decision Correlation Heatmap | High | 5x5 heatmap (TP/CP/SP/SC/PA vs decision types) |
| **018-E** | Institutional Policy Impact | Medium | Subsidy rate vs elevation, premium vs take-up |

### For Antigravity (AI IDE)

| ID | Title | Priority | Description |
|:---|:------|:---------|:------------|
| **018-C** | Agent Trajectory Analysis | High | Individual agent decision timelines |
| **018-D** | MG Equity Analysis | High | MG vs non-MG adaptation comparison |
| **018-F** | PMT Construct Evolution | Medium | Temporal line charts of construct changes |

---

## Data Sources

### Primary Data Files

```
examples/multi_agent/results_unified/<model>_<profile>/
├── simulation_log.csv          # Main decision log
├── raw/
│   ├── household_*_traces.jsonl  # Per-agent traces with PMT constructs
│   ├── government_traces.jsonl   # Gov decisions
│   └── insurance_traces.jsonl    # Insurance decisions
├── governance_summary.json     # Env variable history
└── audit_summary.json          # Parse stats
```

### Key Columns in simulation_log.csv

| Column | Description |
|:-------|:------------|
| `agent_id` | Household/Govt/Insurance ID |
| `year` | Simulation year (1-N) |
| `decision` | Action taken |
| `tp_score`, `cp_score`, `sp_score`, `sc_score`, `pa_score` | PMT construct scores (1-5) |
| `mg` | Marginalized Group flag |
| `elevated`, `has_insurance`, `relocated` | State variables |
| `cumulative_damage` | Total flood damage |

---

## 018-A: Decision Distribution Charts

### Objective
Visualize yearly decision distribution and diversity metrics.

### Charts to Create

1. **Yearly Stacked Bar Chart**
   - X-axis: Year (1-N)
   - Y-axis: Count / Percentage
   - Stacks: do_nothing, buy_insurance, elevate_house, buyout_program
   - Color scheme: Consistent across all charts

2. **Shannon Entropy Trend**
   - X-axis: Year
   - Y-axis: Entropy value (0-2)
   - Reference line at 1.0 (minimum acceptable)

### Implementation

```python
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import entropy

def plot_decision_distribution(log_path, output_dir):
    df = pd.read_csv(log_path)

    # Filter household agents only
    df = df[df['agent_id'].str.startswith('H')]

    # Group by year and decision
    pivot = df.pivot_table(
        index='year',
        columns='decision',
        aggfunc='size',
        fill_value=0
    )

    # Plot stacked bar
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))

    pivot.plot(kind='bar', stacked=True, ax=axes[0],
               colormap='Set2')
    axes[0].set_title('Yearly Decision Distribution')
    axes[0].set_xlabel('Year')
    axes[0].set_ylabel('Count')
    axes[0].legend(title='Decision', bbox_to_anchor=(1.05, 1))

    # Calculate entropy per year
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

# Execute
plot_decision_distribution(
    'results_unified/llama3_2_3b_strict/simulation_log.csv',
    'tests/reports/figures'
)
```

### Output
- `tests/reports/figures/decision_distribution.png`

---

## 018-B: PMT-Decision Correlation Heatmap

### Objective
Show correlation between PMT constructs and decision types.

### Chart Specification

- **Type**: Heatmap
- **Rows**: PMT constructs (TP, CP, SP, SC, PA)
- **Columns**: Decision types (do_nothing, buy_insurance, elevate_house, buyout_program)
- **Values**: Point-biserial correlation coefficient
- **Color**: Diverging (blue-white-red)

### Implementation

```python
import seaborn as sns
from scipy.stats import pointbiserialr

def plot_pmt_decision_heatmap(log_path, output_dir):
    df = pd.read_csv(log_path)
    df = df[df['agent_id'].str.startswith('H')]

    constructs = ['tp_score', 'cp_score', 'sp_score', 'sc_score', 'pa_score']
    decisions = df['decision'].unique()

    # Calculate correlations
    corr_matrix = []
    for construct in constructs:
        row = []
        for decision in decisions:
            # Binary: 1 if this decision, 0 otherwise
            binary = (df['decision'] == decision).astype(int)
            corr, _ = pointbiserialr(df[construct], binary)
            row.append(corr)
        corr_matrix.append(row)

    corr_df = pd.DataFrame(
        corr_matrix,
        index=['TP', 'CP', 'SP', 'SC', 'PA'],
        columns=decisions
    )

    plt.figure(figsize=(10, 6))
    sns.heatmap(corr_df, annot=True, cmap='RdBu_r', center=0,
                vmin=-0.5, vmax=0.5, fmt='.2f')
    plt.title('PMT Construct vs Decision Type Correlation')
    plt.tight_layout()
    plt.savefig(f'{output_dir}/pmt_decision_heatmap.png', dpi=150)
    plt.close()

plot_pmt_decision_heatmap(
    'results_unified/llama3_2_3b_strict/simulation_log.csv',
    'tests/reports/figures'
)
```

### Expected Patterns
- High TP → More protective actions (positive correlation with elevate/insurance)
- Low CP → Less expensive actions (negative correlation with elevate/buyout)
- High PA → Less relocation (negative correlation with buyout)

---

## 018-C: Agent Trajectory Analysis

### Objective
Visualize individual agent decision sequences and state transitions.

### Charts to Create

1. **Decision Timeline Heatmap**
   - Rows: Agent IDs (sample 20)
   - Columns: Years
   - Colors: Decision types

2. **State Transition Sankey Diagram**
   - Show flow between states (unprotected → insured → elevated → relocated)

### Implementation Notes

```python
def plot_agent_trajectories(log_path, output_dir, sample_n=20):
    df = pd.read_csv(log_path)
    df = df[df['agent_id'].str.startswith('H')]

    # Sample agents
    agents = df['agent_id'].unique()[:sample_n]
    df_sample = df[df['agent_id'].isin(agents)]

    # Create decision matrix
    decision_map = {
        'do_nothing': 0, 'buy_insurance': 1,
        'elevate_house': 2, 'buyout_program': 3
    }

    pivot = df_sample.pivot(index='agent_id', columns='year', values='decision')
    pivot_numeric = pivot.replace(decision_map)

    fig, ax = plt.subplots(figsize=(14, 8))
    cmap = plt.cm.get_cmap('Set2', 4)
    im = ax.imshow(pivot_numeric, aspect='auto', cmap=cmap)

    ax.set_yticks(range(len(agents)))
    ax.set_yticklabels(agents)
    ax.set_xlabel('Year')
    ax.set_ylabel('Agent ID')
    ax.set_title('Agent Decision Trajectories')

    # Legend
    cbar = plt.colorbar(im, ticks=[0, 1, 2, 3])
    cbar.ax.set_yticklabels(['do_nothing', 'buy_insurance',
                             'elevate_house', 'buyout_program'])

    plt.tight_layout()
    plt.savefig(f'{output_dir}/agent_trajectories.png', dpi=150)
```

---

## 018-D: MG Equity Analysis

### Objective
Compare adaptation outcomes between Marginalized Group (MG) and non-MG households.

### Charts to Create

1. **Adaptation Rate Comparison**
   - Grouped bar chart: MG vs non-MG
   - Categories: Elevated, Insured, Relocated, No adaptation

2. **Cumulative Damage Distribution**
   - Box plot or violin plot
   - Groups: MG vs non-MG

3. **Subsidy Benefit Analysis**
   - Stacked bar showing who received elevation subsidies
   - Check if MG proportion matches population proportion

### Implementation

```python
def plot_mg_equity(log_path, output_dir):
    df = pd.read_csv(log_path)
    df = df[df['agent_id'].str.startswith('H')]

    # Get final year data
    final_year = df['year'].max()
    df_final = df[df['year'] == final_year]

    # Group by MG status
    mg_stats = df_final.groupby('mg').agg({
        'elevated': 'mean',
        'has_insurance': 'mean',
        'relocated': 'mean',
        'cumulative_damage': 'mean'
    }).T

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Adaptation rates
    mg_stats.iloc[:3].plot(kind='bar', ax=axes[0])
    axes[0].set_title('Adaptation Rates by MG Status')
    axes[0].set_ylabel('Rate')
    axes[0].set_xticklabels(['Elevated', 'Insured', 'Relocated'], rotation=0)
    axes[0].legend(['Non-MG', 'MG'])

    # Damage comparison
    df_final.boxplot(column='cumulative_damage', by='mg', ax=axes[1])
    axes[1].set_title('Cumulative Damage Distribution')
    axes[1].set_xlabel('Marginalized Group')
    axes[1].set_ylabel('Cumulative Damage ($)')

    plt.tight_layout()
    plt.savefig(f'{output_dir}/mg_equity_analysis.png', dpi=150)
```

---

## 018-E: Institutional Policy Impact

### Objective
Visualize relationship between government/insurance policies and household adaptation.

### Charts to Create

1. **Subsidy Rate vs Elevation Adoption**
   - Dual Y-axis line chart
   - Left: Subsidy rate (%)
   - Right: Cumulative elevation count

2. **Premium Rate vs Insurance Take-up**
   - Dual Y-axis line chart
   - Left: Premium rate (%)
   - Right: Insurance purchase count per year

### Data Source
- `governance_summary.json` for policy rates
- `simulation_log.csv` for adoption counts

---

## 018-F: PMT Construct Temporal Evolution

### Objective
Track how PMT constructs change over simulation years (if dynamic).

### Note
If PMT constructs are static (from initial survey), this chart shows:
- Distribution of constructs at simulation start
- Correlation with final outcomes

### Alternative Charts
1. **PMT Radar Chart** per agent type (Owner vs Renter)
2. **Construct Score Distribution** histograms

---

## Execution Commands

### For Codex

```bash
cd examples/multi_agent

# Ensure data exists
ls results_unified/llama3_2_3b_strict/

# Create output directory
mkdir -p tests/reports/figures

# Run visualization scripts
python -c "
# 018-A: Decision Distribution
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import entropy
import numpy as np

df = pd.read_csv('results_unified/llama3_2_3b_strict/simulation_log.csv')
df_h = df[df['agent_id'].str.startswith('H')]

# ... (implementation code above)
"
```

### For Antigravity

Use the provided code templates in your IDE to create visualization scripts:
1. `examples/multi_agent/tests/viz_agent_trajectory.py`
2. `examples/multi_agent/tests/viz_mg_equity.py`
3. `examples/multi_agent/tests/viz_pmt_evolution.py`

---

## Report Format

After completing visualizations, report:

```
REPORT
agent: Codex / Antigravity
task_id: task-018-X
scope: examples/multi_agent/tests/reports/figures/
status: done|partial|blocked
charts_created: <list of PNG files>
issues: <any problems>
next: <next subtask>
```

---

## Subtasks
- id: task-018/018-A
  assigned_to: codex
  status: done
  summary: Decision distribution stacked bars + Shannon entropy trend from household traces.
  changes: examples/multi_agent/tests/viz_decision_distribution.py
  tests: python examples/multi_agent/tests/viz_decision_distribution.py --results examples/multi_agent/results_unified/llama3_2_3b_strict --output examples/multi_agent/tests/reports/figures
  artifacts: examples/multi_agent/tests/reports/figures/decision_distribution.png
  issues: Uses raw traces (simulation_log.csv not present in results dir).

- id: task-018/018-B
  assigned_to: codex
  status: done
  summary: PMT construct vs decision heatmap (point-biserial correlation).
  changes: examples/multi_agent/tests/viz_pmt_decision_heatmap.py
  tests: python examples/multi_agent/tests/viz_pmt_decision_heatmap.py --results examples/multi_agent/results_unified/llama3_2_3b_strict --output examples/multi_agent/tests/reports/figures
  artifacts: examples/multi_agent/tests/reports/figures/pmt_decision_heatmap.png
  issues: Uses raw traces; sample is small (2 agents, 2 steps).

- id: task-018/018-E
  assigned_to: codex
  status: done
  summary: Policy impact chart (subsidy/premium vs adoption) from institutional + household traces.
  changes: examples/multi_agent/tests/viz_policy_impact.py, examples/multi_agent/tests/viz_utils.py
  tests: python examples/multi_agent/tests/viz_policy_impact.py --results examples/multi_agent/results_unified/llama3_2_3b_strict --output examples/multi_agent/tests/reports/figures
  artifacts: examples/multi_agent/tests/reports/figures/policy_impact.png
  issues: Uses raw traces; sample is small (2 agents, 2 steps).

- id: task-018/018-C
  assigned_to: codex
  status: done
  summary: Agent trajectory heatmap from household traces.
  changes: examples/multi_agent/tests/viz_agent_trajectory.py, examples/multi_agent/tests/viz_utils.py
  tests: python examples/multi_agent/tests/viz_agent_trajectory.py --results examples/multi_agent/results_unified/llama3_2_3b_strict --output examples/multi_agent/tests/reports/figures
  artifacts: examples/multi_agent/tests/reports/figures/agent_trajectories.png
  issues: Uses raw traces; sample is small (2 agents, 2 steps).

- id: task-018/018-D
  assigned_to: codex
  status: done
  summary: MG equity comparison charts from household traces.
  changes: examples/multi_agent/tests/viz_mg_equity.py
  tests: python examples/multi_agent/tests/viz_mg_equity.py --results examples/multi_agent/results_unified/llama3_2_3b_strict --output examples/multi_agent/tests/reports/figures
  artifacts: examples/multi_agent/tests/reports/figures/mg_equity_analysis.png
  issues: Uses raw traces; sample is small (2 agents, 2 steps).

- id: task-018/018-F
  assigned_to: codex
  status: done
  summary: PMT construct evolution line chart from household traces.
  changes: examples/multi_agent/tests/viz_pmt_evolution.py
  tests: python examples/multi_agent/tests/viz_pmt_evolution.py --results examples/multi_agent/results_unified/llama3_2_3b_strict --output examples/multi_agent/tests/reports/figures
  artifacts: examples/multi_agent/tests/reports/figures/pmt_construct_evolution.png
  issues: Uses raw traces; sample is small (2 agents, 2 steps).

---

## Recommendation (for Claude Code)

- Run a full MA experiment that outputs `simulation_log.csv` plus complete `raw/*.jsonl` traces, then re-run the visualization scripts under `examples/multi_agent/tests/` to generate publication-ready charts.

---

## Dependencies

- Python packages: `matplotlib`, `seaborn`, `pandas`, `numpy`, `scipy`
- Data: Completed MA experiment run with `llama3.2:3b` or similar

```bash
pip install matplotlib seaborn pandas scipy
```

---

## Notes

1. All charts should use consistent color schemes for decisions
2. Export at 150+ DPI for publication quality
3. Include axis labels, legends, and titles
4. Save both PNG and PDF formats for flexibility
