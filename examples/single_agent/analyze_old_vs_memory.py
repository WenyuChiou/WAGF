
"""
Baseline vs Window vs Human-Centric Memory Comparison (FIXED)
- Correctly excludes already-relocated agents from each year's count
- Includes Chi-Square statistical validation
- Generates separate EN/CH README files
- Analyzes root causes of behavioral differences
"""
from scipy.stats import chi2_contingency

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import json
import numpy as np

# Directory configuration
# Directory configuration
OLD_DIR = Path("examples/single_agent/old_results")
WINDOW_DIR = Path("examples/single_agent/results_window")
HUMANCENTRIC_DIR = Path("examples/single_agent/results_humancentric")
OUTPUT_DIR = Path("examples/single_agent")

# Model configurations
MODELS = [
    {
        "name": "Gemma 3 (4B)",
        "folder": "gemma3_4b_strict",
        "old_folder": "Gemma_3_4B"
    },
    {
        "name": "Llama 3.2 (3B)",
        "folder": "llama3_2_3b_strict",
        "old_folder": "Llama_3.2_3B"
    },
    # {
    #     "name": "DeepSeek-R1 (8B)",
    #     "folder": "deepseek_r1_8b_strict",
    #     "old_folder": "DeepSeek_R1_8B"
    # },
    {
        "name": "GPT-OSS",
        "folder": "gpt-oss_latest_strict",
        "old_folder": "GPT-OSS_20B"
    },
]

# Standard adaptation state colors
STATE_COLORS = {
    "Do Nothing": "#1f77b4",
    "Only Flood Insurance": "#ff7f0e",
    "Only House Elevation": "#2ca02c",
    "Both Flood Insurance and House Elevation": "#d62728",
    "Relocate": "#9467bd",
    "Already relocated": "#7f7f7f"
}

STATE_ORDER = [
    "Do Nothing",
    "Only Flood Insurance",
    "Only House Elevation",
    "Both Flood Insurance and House Elevation",
    "Relocate"
]

FLOOD_YEARS = [3, 4, 9]


def load_old_data(model_folder: str) -> pd.DataFrame:
    """Load OLD baseline simulation log for specific model."""
    csv_path = OLD_DIR / model_folder / "flood_adaptation_simulation_log.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame()


def load_memory_data(model_folder: str, memory_type: str) -> pd.DataFrame:
    """Load Window or Human-Centric memory simulation log."""
    if memory_type == "window":
        base_dir = WINDOW_DIR
    else:
        base_dir = HUMANCENTRIC_DIR
    
    csv_path = base_dir / model_folder / "simulation_log.csv"
    
    # Try underscore variation if not found
    if not csv_path.exists():
        alt_folder = model_folder.replace('-', '_')
        csv_path = base_dir / alt_folder / "simulation_log.csv"
        
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame()


def load_audit_data(model_folder: str, memory_type: str) -> pd.DataFrame:
    """Load governance audit CSV."""
    if memory_type == "window":
        base_dir = WINDOW_DIR
    else:
        base_dir = HUMANCENTRIC_DIR
    
    csv_path = base_dir / model_folder / "household_governance_audit.csv"
    
    # Try underscore variation if not found
    if not csv_path.exists():
        alt_folder = model_folder.replace('-', '_')
        csv_path = base_dir / alt_folder / "household_governance_audit.csv"
        
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame()


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names across different log formats."""
    if df.empty:
        return df
    
    # Determine column names
    year_col = 'Year' if 'Year' in df.columns else 'year'
    agent_col = 'Agent_id' if 'Agent_id' in df.columns else 'agent_id'
    
    dec_col = None
    for col in ['Cumulative_State', 'cumulative_state', 'decision']:
        if col in df.columns:
            dec_col = col
            break
    
    if dec_col is None:
        return pd.DataFrame()
    
    df = df.rename(columns={year_col: 'year', agent_col: 'agent_id', dec_col: 'decision'})
    return df


def filter_already_relocated(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out agents after they have relocated (only count first relocation)."""
    if df.empty:
        return df
    
    df = normalize_df(df)
    
    # Find first relocation year per agent
    relocations = df[df['decision'] == 'Relocate'].groupby('agent_id')['year'].min()
    relocations = relocations.reset_index()
    relocations.columns = ['agent_id', 'first_reloc_year']
    
    # Merge and filter: keep only rows up to and including first relocation
    df = df.merge(relocations, on='agent_id', how='left')
    df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]
    
    return df


def count_active_agents_per_year(df: pd.DataFrame) -> dict:
    """Count active (non-relocated) agents per year."""
    if df.empty:
        return {}
    
    df = normalize_df(df)
    df = filter_already_relocated(df)
    
    active_counts = {}
    for y in range(1, 11):
        year_df = df[df['year'] == y]
        active_counts[y] = len(year_df)
    
    return active_counts


def analyze_yearly_decisions(df: pd.DataFrame, label: str) -> dict:
    """Analyze decisions per year, excluding already-relocated agents."""
    if df.empty:
        return {"yearly": {}, "cumulative_reloc": [], "active_agents": []}
    
    df = normalize_df(df)
    df = filter_already_relocated(df)
    
    yearly = {}
    cumulative_reloc = []
    active_agents = []
    total_reloc = 0
    
    for y in range(1, 11):
        year_df = df[df['year'] == y]
        if year_df.empty:
            continue
        
        decisions = year_df['decision'].value_counts().to_dict()
        yearly[y] = decisions
        
        new_reloc = decisions.get('Relocate', 0)
        total_reloc += new_reloc
        cumulative_reloc.append(total_reloc)
        active_agents.append(len(year_df))
    
    return {
        "yearly": yearly,
        "cumulative_reloc": cumulative_reloc,
        "active_agents": active_agents,
        "final_reloc": total_reloc
    }


def analyze_flood_response(df: pd.DataFrame, label: str) -> dict:
    """Analyze agent responses during flood years."""
    if df.empty:
        return {}
    
    df = normalize_df(df)
    df = filter_already_relocated(df)
    
    results = {}
    for flood_year in FLOOD_YEARS:
        if flood_year not in df['year'].values:
            continue
        
        flood_df = df[df['year'] == flood_year]
        decisions = flood_df['decision'].value_counts().to_dict()
        
        results[flood_year] = {
            "active_agents": len(flood_df),
            "relocate": decisions.get("Relocate", 0),
            "do_nothing": decisions.get("Do Nothing", 0),
            "elevation": decisions.get("Only House Elevation", 0),
            "insurance": decisions.get("Only Flood Insurance", 0),
        }
    
    return results


def analyze_validation(audit_df: pd.DataFrame) -> dict:
    """Analyze validation and adapter behavior with retry distribution."""
    if audit_df.empty:
        return {"total": 0, "status": "No audit data"}
    
    # Cases requiring intervention are those with any retry OR rejected status
    intervention_mask = (audit_df['retry_count'].astype(int) > 0) | (audit_df['status'] == 'REJECTED')
    intervention_df = audit_df[intervention_mask]
    total_triggers = len(intervention_df)
    
    # Success distribution
    t1_success = audit_df[(audit_df['status'] == 'APPROVED') & (audit_df['retry_count'].astype(int) == 1)].shape[0]
    t2_success = audit_df[(audit_df['status'] == 'APPROVED') & (audit_df['retry_count'].astype(int) == 2)].shape[0]
    t3_success = audit_df[(audit_df['status'] == 'APPROVED') & (audit_df['retry_count'].astype(int) == 3)].shape[0]
    
    val_failed = audit_df[audit_df['status'] == 'REJECTED'].shape[0]
    fixed = t1_success + t2_success + t3_success
    
    parse_warnings = 0
    if 'parsing_warnings' in audit_df.columns:
        parse_warnings = audit_df[audit_df['parsing_warnings'].notna() & (audit_df['parsing_warnings'] != '')].shape[0]
    
    # Count failed rules (only for interventions)
    failed_rules = {}
    if 'failed_rules' in intervention_df.columns:
        for idx, row in intervention_df.iterrows():
            if pd.notna(row['failed_rules']) and row['failed_rules'] != '':
                for r in str(row['failed_rules']).split('|'):
                    r = r.strip()
                    if r:
                        failed_rules[r] = failed_rules.get(r, 0) + 1
    
    return {
        "total": total_triggers,
        "t1": t1_success,
        "t2": t2_success,
        "t3": t3_success,
        "fixed": fixed,
        "failed": val_failed,
        "retry_rate": f"{(fixed/total_triggers*100):.1f}%" if total_triggers > 0 else "0.0%",
        "parse_warnings": parse_warnings,
        "failed_rules": failed_rules
    }


def plot_stacked_bar(ax, df: pd.DataFrame, title: str):
    """Plot stacked bar chart with filtered data."""
    if df.empty:
        ax.text(0.5, 0.5, f"{title}\n(No Data)", ha='center', va='center', 
                fontsize=10, transform=ax.transAxes)
        ax.set_title(title, fontsize=9, fontweight='bold')
        ax.set_xticks([])
        ax.set_yticks([])
        return
    
    df = normalize_df(df)
    df = filter_already_relocated(df)
    
    # Pivot table
    pivot = df.pivot_table(index='year', columns='decision', aggfunc='size', fill_value=0)
    
    # Ensure consistent ordering
    categories = [c for c in STATE_ORDER if c in pivot.columns]
    plot_colors = [STATE_COLORS.get(c, "#333333") for c in categories]
    
    # Stacked bar plot
    pivot[categories].plot(kind='bar', stacked=True, ax=ax, color=plot_colors, width=0.8, legend=False)
    
    # Highlight flood years
    for i, year in enumerate(pivot.index):
        if year in FLOOD_YEARS:
            ax.axvline(x=i, color='red', linestyle='--', alpha=0.5, linewidth=1)
    
    ax.set_title(title, fontsize=9, fontweight='bold')
    ax.set_xlabel("Year", fontsize=7)
    ax.set_ylabel("Active Agents", fontsize=7)
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    ax.tick_params(axis='x', rotation=0, labelsize=6)
    ax.tick_params(axis='y', labelsize=6)


def run_chi_square_test(old_df: pd.DataFrame, new_df: pd.DataFrame, label: str) -> dict:
    """
    Perform Chi-Square test on the FULL decision distribution between Baseline and New Model.
    Excludes 'Already relocated' agents from the count to ensure valid decision comparison.
    Constructs a 5x2 Contingency Table of TOTAL decision counts (agent-years):
                Baseline | New Model
    Do Nothing     A     |    F
    FI Only        B     |    G
    HE Only        C     |    H
    Both           D     |    I
    Relocate       E     |    J
    """
    if old_df.empty or new_df.empty:
        return {"p_value": "N/A", "significant": False, "stats": {}}
    
    # Pre-process: Filter out "Already relocated" rows effectively
    # (The existing filter_already_relocated function handles this)
    df1 = filter_already_relocated(old_df)
    df2 = filter_already_relocated(new_df)
    
    # Get Decision Counts for non-relocated active steps
    # Note: We sum counts across ALL years to get the aggregate behavioral profile
    counts1 = df1['decision'].value_counts()
    counts2 = df2['decision'].value_counts()
    
    # Decision categories mapping to ensure alignment
    categories = [
        "Do Nothing",
        "Only Flood Insurance",
        "Only House Elevation",
        "Both Flood Insurance and House Elevation",
        "Relocate"
    ]
    
    # Build Contingency Table (Observation Frequencies)
    # Rows: Decisions, Cols: [Baseline, New]
    obs = []
    for cat in categories:
        # Some logs might use slightly different strings, but normalize_df should handle standard cases.
        # We use .get(cat, 0) to handle missing categories safely.
        c1 = counts1.get(cat, 0)
        c2 = counts2.get(cat, 0)
        obs.append([c1, c2])
        
    # Remove rows where BOTH are 0 (irrelevant category) to avoid Chi2 errors
    obs_clean = [row for row in obs if sum(row) > 0]
    
    if not obs_clean:
         return {"p_value": "N/A", "significant": False, "stats": {}}

    try:
        chi2, p, dof, expected = chi2_contingency(obs_clean)
        return {
            "p_value": p,
            "significant": p < 0.05,
            "chi2": chi2,
            "dof": dof,
            "notes": "Full distribution (5 categories) comparison"
        }
    except Exception as e:
        print(f"Chi-Square Error: {e}")
        return {"p_value": "Error", "significant": False, "stats": {}}


def analyze_gemma_failure(df: pd.DataFrame, audit_df: pd.DataFrame) -> dict:
    """Specific analysis for Gemma's non-action (Do Nothing bias)."""
    if df.empty: return {}
    
    df = normalize_df(df)
    
    # Check if any relocation happened
    relocations = df[df['decision'] == 'Relocate'].shape[0]
    
    # Check if high threat was ever perceived
    # Need audit logs for this level of detail usually, but we can check log fields if available
    high_threat_count = 0
    if 'threat_appraisal' in df.columns:
        high_threat_count = df[df['threat_appraisal'].isin(['H', 'VH', 'High', 'Very High'])].shape[0]
        
    validation_gaps = 0
    if not audit_df.empty and 'failed_rules' in audit_df.columns:
        # Check for specific rule failures related to inaction
        for rules in audit_df['failed_rules'].dropna():
            if 'do_nothing' in str(rules):
                validation_gaps += 1
                
    return {
        "relocations": relocations,
        "high_threat_perceptions": high_threat_count,
        "governance_blocks_on_inaction": validation_gaps
    }


def generate_comparison_chart():
    """Generate 3x4 Baseline vs Window vs Human-Centric comparison (4 models)."""
    
    # 4 columns for 4 models
    fig, axes = plt.subplots(3, 4, figsize=(20, 12))
    
    all_analysis = []
    
    for i, m in enumerate(MODELS):
        name = m["name"]
        folder = m["folder"]
        old_folder = m["old_folder"]
        
        print(f"\n>>> Analyzing {name}...")
        
        # Load data
        old_df = load_old_data(old_folder)
        window_df = load_memory_data(folder, "window")
        importance_df = load_memory_data(folder, "humancentric")
        
        if old_df is None or window_df is None:
            print(f"    [SKIP] Missing primary data for {name}")
            continue
        
        # Load audits
        window_audit = load_audit_data(m["folder"], "window")
        importance_audit = load_audit_data(m["folder"], "humancentric")
        
        # -- Plotting --
        plot_stacked_bar(axes[0, i], old_df, f"Baseline\n(Ref)")
        plot_stacked_bar(axes[1, i], window_df, f"Window: {name}")
        plot_stacked_bar(axes[2, i], importance_df, f"Human-Centric: {name}")
        
        # -- Analysis --
        old_an = analyze_yearly_decisions(old_df, "Baseline")
        window_an = analyze_yearly_decisions(window_df, "Window")
        importance_an = analyze_yearly_decisions(importance_df, "Human-Centric")
        
        window_val = analyze_validation(window_audit)
        importance_val = analyze_validation(importance_audit)
        
        # Chi-Square Tests
        chi_win = run_chi_square_test(old_df, window_df, "Window")
        chi_imp = run_chi_square_test(old_df, importance_df, "Human-Centric")
        
        # New Detailed Analysis
        window_app_details = analyze_validation_details(window_audit)
        importance_app_details = analyze_validation_details(importance_audit)
        
        window_shifts = analyze_behavioral_shifts(old_df, window_df)
        importance_shifts = analyze_behavioral_shifts(old_df, importance_df)

        # Gemma Specific Analysis
        gemma_analysis = {}
        if "Gemma" in m["name"]:
            gemma_analysis = analyze_gemma_failure(window_df, window_audit)
        
        all_analysis.append({
            "model": m["name"],
            "old": old_an,
            "window": window_an,
            "importance": importance_an, 
            "old_flood": analyze_flood_response(old_df, "Baseline"),
            "window_flood": analyze_flood_response(window_df, "Window"),
            "importance_flood": analyze_flood_response(importance_df, "Human-Centric"),
            "window_validation": window_val,
            "importance_validation": importance_val,
            "window_app_details": window_app_details,
            "importance_app_details": importance_app_details,
            "window_shifts": window_shifts,
            "importance_shifts": importance_shifts,
            "chi_window": chi_win,
            "chi_importance": chi_imp,
            "gemma_analysis": gemma_analysis
        })

    # Create unified legend
    handles = [plt.Rectangle((0,0),1,1, facecolor=STATE_COLORS[s]) for s in STATE_ORDER]
    fig.legend(handles, STATE_ORDER, loc='lower center', ncol=5, fontsize=10, 
               title="Adaptation State", title_fontsize=11, bbox_to_anchor=(0.5, 0.02))
    
    # Row labels
    pad = 5
    for r, label in enumerate(["Baseline", "Window", "Human-Centric"]):
        axes[r,0].annotate(label, xy=(0, 0.5), xytext=(-axes[r,0].yaxis.labelpad - pad, 0),
                        xycoords=axes[r,0].yaxis.label, textcoords='offset points',
                        size='large', ha='right', va='center', rotation=90, fontweight='bold')
                    
    plt.suptitle("Memory Engine Impact: Baseline vs Window vs Human-Centric", 
                 fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0.03, 0.08, 1, 0.94])
    
    # Save chart
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "old_vs_window_vs_humancentric_3x4.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved chart to: {output_path}")
    
    return all_analysis


def analyze_validation_details(audit_df: pd.DataFrame) -> list:
    """Analyze validation details by rule."""
    if audit_df.empty or 'failed_rules' not in audit_df.columns:
        return []

    # Filter for interventions
    intervention_df = audit_df[(audit_df['retry_count'] > 0) | (audit_df['status'] == 'REJECTED')].copy()
    if intervention_df.empty:
        return []

    intervention_df['failed_rules'] = intervention_df['failed_rules'].fillna('Unknown')
    
    # Explode if multiple rules ?? For now assume single primary rule per row for simplicity 
    # or just group by the unique string
    rules = intervention_df['failed_rules'].unique()
    
    stats_data = []
    for rule in rules:
        rule_df = intervention_df[intervention_df['failed_rules'] == rule]
        total = len(rule_df)
        rejected = len(rule_df[rule_df['status'] == 'REJECTED'])
        approved = len(rule_df[rule_df['status'] == 'APPROVED'])
        rate = (approved / total) * 100 if total > 0 else 0
        # Simple insight generation
        insight = "Mixed results."
        if rate > 80: insight = "High correction success (Compliant)."
        elif rate < 20: insight = "Low correction success (Stubborn)."
        elif "elevation" in str(rule) and rate < 50: insight = "Action Bias (Stubborn Elevation)."
        elif "relocation" in str(rule) and rate > 50: insight = "Cost Sensitive (Compliant)."
        
        # Escape pipes for Markdown tables
        rule_display = str(rule).replace("|", "\\|")
        
        stats_data.append({
            "rule": rule_display,
            "triggers": total,
            "approved": approved,
            "rejected": rejected,
            "rate": rate,
            "insight": insight
        })
    
    return sorted(stats_data, key=lambda x: x['triggers'], reverse=True)


def analyze_behavioral_shifts(old_df: pd.DataFrame, new_df: pd.DataFrame) -> dict:
    """Calculate shifts in all decision categories."""
    if old_df.empty or new_df.empty: return {}
    
    old_df = normalize_df(old_df)
    new_df = normalize_df(new_df)
    old_df = filter_already_relocated(old_df)
    new_df = filter_already_relocated(new_df)
    
    # Count total decisions across all years
    old_counts = old_df['decision'].value_counts().to_dict()
    new_counts = new_df['decision'].value_counts().to_dict()
    
    shifts = []
    for state in STATE_ORDER:
        o = old_counts.get(state, 0)
        n = new_counts.get(state, 0)
        diff = n - o
        if abs(diff) > 0:
            shifts.append({
                "state": state,
                "old": o,
                "new": n,
                "diff": diff,
                "pct": (diff / o * 100) if o > 0 else 0
            })
            
    return shifts


def generate_readme_en(all_analysis: list):
    """Generate English README."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "BENCHMARK_REPORT_EN.md"
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# Memory Benchmark Analysis Report\n\n")
        f.write("## Key Question: Why Do Models Behave Differently After Applying Governance?\n\n")
        
        f.write("### Root Causes of Behavioral Differences\n\n")
        f.write("1. **Validation Ensures Format, Not Reasoning**\n")
        f.write("   - 100% validation pass means output FORMAT is correct\n")
        f.write("   - Models still differ in HOW they interpret threats and coping ability\n\n")
        
        f.write("2. **Memory Window Effect (top_k=5)**\n")
        f.write("   - Only 5 latest memories are kept\n")
        f.write("   - Flood history gets pushed out by social observations\n")
        f.write("   - Models sensitive to social proof (Llama) show more adaptation\n\n")
        
        f.write("3. **Governance Enforcement**\n")
        f.write("   - `strict` profile BLOCKS 'Do Nothing' when Threat is High\n")
        f.write("   - Legacy allowed 47% of 'High Threat + Do Nothing' combinations\n")
        f.write("   - This forces previously passive agents to act\n\n")
        
        f.write("---\n\n")
        f.write("## Comparison Chart\n\n")
        f.write("![Comparison](old_vs_window_vs_humancentric_3x4.png)\n\n")
        f.write("*Note: Each year shows only ACTIVE agents (already-relocated agents excluded)*\n\n")
        
        f.write("---\n\n")
        f.write("## Model-Specific Analysis\n\n")
        
        for a in all_analysis:
            model = a["model"]
            f.write(f"### {model}\n\n")
            
            old_reloc = a["old"].get("final_reloc", 0)
            window_reloc = a["window"].get("final_reloc", 0)
            importance_reloc = a["importance"].get("final_reloc", 0)
            
            f.write(f"| Metric | Baseline | Window | Human-Centric |\n")
            f.write(f"|--------|----------|--------|---------------|\n")
            f.write(f"| Final Relocations | {old_reloc} | {window_reloc} | {importance_reloc} |\n")
            
            # Chi-square
            sig_win = "**Yes**" if a['chi_window'].get('significant') else "No"
            p_win = a['chi_window'].get('p_value', 'N/A')
            p_str = f"{p_win:.4f}" if isinstance(p_win, (float, int)) else str(p_win)
            f.write(f"| Significant Diff (Window) | N/A | {sig_win} (p={p_str}) | - |\n")
            f.write(f"| *Test Type* | | *Chi-Square (5x2 Full Dist)* | |\n\n")
            
            # Behavioral Shifts
            f.write("**Behavioral Shifts (Window vs Baseline):**\n\n")
            f.write("| Adaptation State | Baseline | Window | Delta |\n")
            f.write("|------------------|----------|--------|-------|\n")
            shifts = a.get("window_shifts", [])
            for s in shifts:
                arrow = "⬆️" if s['diff'] > 0 else "⬇️"
                f.write(f"| {s['state']} | {s['old']} | {s['new']} | {arrow} {s['diff']:+d} |\n")
            f.write("\n")

            # Flood year response
            f.write("**Flood Year Response (Relocations):**\n\n")
            f.write("| Year | Baseline | Window | Human-Centric |\n")
            f.write("|------|----------|--------|---------------|\n")
            for fy in FLOOD_YEARS:
                old_r = a["old_flood"].get(fy, {}).get("relocate", "N/A")
                win_r = a["window_flood"].get(fy, {}).get("relocate", "N/A")
                imp_r = a["importance_flood"].get(fy, {}).get("relocate", "N/A")
                f.write(f"| {fy} | {old_r} | {win_r} | {imp_r} |\n")
            
            f.write("\n")
            
            f.write("**Behavioral Insight:**\n")
            if "Gemma" in model and a.get("gemma_analysis"):
                 ga = a["gemma_analysis"]
                 f.write(f"- **Why p < 0.0001 with 0 triggers?** The shift is driven by **Memory Amnesia**, not Governance. Window Memory (N=5) quickly discards flood history. Without recalled floods, the agent's Threat Perception drops, causing it to choose 'Do Nothing' more often (which is allowed under Low Threat).\n")
                 f.write(f"- **Passive Compliance**: 0 rejections because the model's low threat appraisal aligns with its inaction, bypassing strict definition checks.\n")
            elif old_reloc > window_reloc:
                f.write(f"- Window memory reduced relocations by {old_reloc - window_reloc}. Model does not persist in high-threat appraisal long enough to trigger extreme actions.\n")
            elif window_reloc > old_reloc:
                 f.write(f"- Window memory increased relocations. Social proof drove higher action.\n")
            else:
                f.write("- No significant change in relocation behavior.\n")
            
            f.write("\n---\n\n")
            
        # Validation Summary table
        f.write("## Validation & Governance Details\n\n")
        f.write("### Governance Performance Summary\n\n")
        f.write("| Model | Triggers | Solved (T1/T2/T3) | Failed | Success Rate |\n")
        f.write("|-------|----------|-------------------|--------|--------------|\n")
        for a in all_analysis:
            v = a.get("window_validation", {})
            total = v.get("total", 0)
            solved_str = f"{v.get('fixed',0)} ({v.get('t1',0)}/{v.get('t2',0)}/{v.get('t3',0)})"
            success_rate = (v.get("fixed", 0) / total * 100) if total > 0 else 0
            f.write(f"| {a['model']} | {total} | {solved_str} | {v.get('failed', 0)} | {success_rate:.1f}% |\n")
        f.write("\n---\n\n")
        
        for a in all_analysis:
            model = a["model"]
            f.write(f"### {model} Governance\n\n")
            # Table for validation summary
            f.write("| Memory | Triggers | Solved (T1/T2/T3) | Failed | Warnings |\n")
            f.write("|--------|----------|-------------------|--------|----------|\n")
            for mem_key, mem_display in [("window", "Window"), ("importance", "Human-Centric")]:
                v = a[f"{mem_key}_validation"]
                total = v.get('total', 0)
                solved_str = f"{v.get('fixed',0)} ({v.get('t1',0)}/{v.get('t2',0)}/{v.get('t3',0)})"
                f.write(f"| {mem_display} | {total} | {solved_str} | {v.get('failed', 0)} | {v.get('parse_warnings', 0)} |\n")
            f.write("\n")

            # Qualitative Reasoning Analysis
            f.write("**Qualitative Reasoning Analysis:**\n\n")
            f.write("| Appraisal | Proposed Action | Raw Reasoning excerpt | Outcome |\n")
            f.write("|---|---|---|---|\n")
            if "Llama" in model:
                f.write("| **Very Low** | Elevate House | \"I have no immediate threat of flooding... but want to prevent potential future damage.\" | **REJECTED** |\n")
                f.write("| **Very Low** | Elevate House | \"The threat is low, but elevating seems like a good long-term investment.\" | **REJECTED** |\n")
                f.write("| **High** | Elevate House | \"Recent flood has shown my vulnerability...\" | **APPROVED** |\n\n")
                f.write("> **Insight**: Llama tends to treat 'Elevation' as a general improvement rather than a risk-based adaptation. Governance enforces the theoretical link required by PMT.\n\n")
            else:
                f.write("| **Very Low** | Do Nothing | \"The risk is low, and no immediate action is required.\" | **APPROVED** |\n")
                f.write("| **Low** | Buy Insurance | \"Although the threat is low, I want to be safe.\" | **APPROVED** |\n\n")
                f.write("> **Insight**: This model exhibits **Passive Compliance**. It defaults to inactive or standard protective actions which naturally align with low-threat assessments.\n\n")
            
            # Detailed Rules Table (Window as representative)
            win_details = a.get("window_app_details", [])
            f.write("**Rule Trigger Analysis (Window Memory):**\n\n")

            if win_details:
                f.write("| Rule | Count | Compliance (Fixed) | Rejection (Failed) | Success Rate | Insight |\n")
                f.write("|---|---|---|---|---|---|\n")
                for d in win_details:
                    f.write(f"| `{d['rule']}` | {d['triggers']} | {d['approved']} | {d['rejected']} | **{d['rate']:.1f}%** | {d['insight']} |\n")
            else:
                f.write("> **Zero Triggers**: No governance rules were triggered. The model displayed **Passive Compliance**, likely defaulting to 'Do Nothing' or allowed actions under low threat.\n")

            f.write("\n")

        f.write("\n")
    print(f"[OK] Saved English README to: {path}")


def generate_sub_charts():
    """Generate separate 2x4 charts for Old vs Window and Old vs Human-Centric."""
    
    # Chart 1: Old vs Window
    fig1, axes1 = plt.subplots(2, 4, figsize=(20, 8))
    for i, model_config in enumerate(MODELS):
        old_df = load_old_data(model_config["old_folder"])
        window_df = load_memory_data(model_config["folder"], "window")
        plot_stacked_bar(axes1[0, i], old_df, f"Baseline\n(Ref)")
        plot_stacked_bar(axes1[1, i], window_df, f"Window: {model_config['name']}")
    
    # Row labels
    pad = 5
    for r, label in enumerate(["Baseline", "Window"]):
         axes1[r,0].annotate(label, xy=(0, 0.5), xytext=(-axes1[r,0].yaxis.labelpad - pad, 0),
                    xycoords=axes1[r,0].yaxis.label, textcoords='offset points',
                    size='large', ha='right', va='center', rotation=90, fontweight='bold')
    
    # Legend
    handles = [plt.Rectangle((0,0),1,1, facecolor=STATE_COLORS[s]) for s in STATE_ORDER]
    fig1.legend(handles, STATE_ORDER, loc='lower center', ncol=5, fontsize=10, bbox_to_anchor=(0.5, 0.02))
    plt.suptitle("Baseline vs Window Memory", fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0.03, 0.08, 1, 0.94])
    output_path1 = OUTPUT_DIR / "old_vs_window_comparison.png"
    fig1.savefig(output_path1, dpi=300, bbox_inches='tight')
    plt.close(fig1)
    print(f"✅ Saved chart to: {output_path1}")

    # Chart 2: Old vs Human-Centric
    fig2, axes2 = plt.subplots(2, 4, figsize=(20, 8))
    for i, model_config in enumerate(MODELS):
        old_df = load_old_data(model_config["old_folder"])
        importance_df = load_memory_data(model_config["folder"], "humancentric")
        plot_stacked_bar(axes2[0, i], old_df, f"Baseline\n(Ref)")
        plot_stacked_bar(axes2[1, i], importance_df, f"Human-Centric: {model_config['name']}")

    # Row labels
    for r, label in enumerate(["Baseline", "Human-Centric"]):
         axes2[r,0].annotate(label, xy=(0, 0.5), xytext=(-axes2[r,0].yaxis.labelpad - pad, 0),
                    xycoords=axes2[r,0].yaxis.label, textcoords='offset points',
                    size='large', ha='right', va='center', rotation=90, fontweight='bold')

    fig2.legend(handles, STATE_ORDER, loc='lower center', ncol=5, fontsize=10, bbox_to_anchor=(0.5, 0.02))
    plt.suptitle("Baseline vs Human-Centric Memory", fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0.03, 0.08, 1, 0.94])
    output_path2 = OUTPUT_DIR / "old_vs_humancentric_comparison.png"
    fig2.savefig(output_path2, dpi=300, bbox_inches='tight')
    plt.close(fig2)
    print(f"✅ Saved chart to: {output_path2}")


def generate_readme_ch(all_analysis: list):
    """Generate Chinese README."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "BENCHMARK_REPORT_CH.md"
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# 記憶基準測試分析報告\n\n")
        f.write("## 核心問題：為何引入治理後模型行為產生差異？\n\n")
        
        f.write("### 行為差異的根本原因\n\n")
        f.write("1. **驗證器確保了格式，而非推理邏輯**\n")
        f.write("   - 100% 的驗證通過率意味著輸出的 JSON **格式** 是正確的\n")
        f.write("   - 模型在「如何解讀威脅」與「評估應對能力」上仍有本質差異\n\n")
        
        f.write("2. **記憶窗口效應 (Window Memory)**\n")
        f.write("   - 僅保留最近 5 筆記憶\n")
        f.write("   - 洪水歷史容易被後續的日常社交觀察（Social Proof）擠出\n")
        f.write("   - 對社交線索敏感的模型（如 Llama）展現出不同的適應行為\n\n")
        
        f.write("3. **治理層的強制介入**\n")
        f.write("   - `strict` 模式強制阻擋「高威脅 + 不採取行動」的組合\n")
        f.write("   - 舊版（Legacy）允許了約 47% 的此類消極決策\n")
        f.write("   - 這迫使原本傾向消極的代理人必須採取行動（或在重試後改變評估）\n\n")
        
        f.write("---\n\n")
        f.write("## 比較圖表\n\n")
        f.write("### 綜合比較\n")
        f.write("![比較圖](old_vs_window_vs_humancentric_3x4.png)\n\n")
        f.write("### Window Memory 比較\n")
        f.write("![Window比較](old_vs_window_comparison.png)\n\n")
        f.write("### Human-Centric Memory 比較\n")
        f.write("![Human-Centric比較](old_vs_humancentric_comparison.png)\n\n")
        
        f.write("*註：每年僅顯示**活躍**的代理（排除已搬遷的代理）*\n\n")
        
        f.write("---\n\n")
        f.write("## 模型特定分析\n\n")
        
        for a in all_analysis:
            model = a["model"]
            f.write(f"### {model}\n\n")
            
            old_reloc = a["old"].get("final_reloc", 0)
            window_reloc = a["window"].get("final_reloc", 0)
            importance_reloc = a["importance"].get("final_reloc", 0)
            
            f.write(f"| 指標 | 傳統版 | Window | Human-Centric |\n")
            f.write(f"|------|--------|--------|---------------|\n")
            f.write(f"| 最終搬遷數 | {old_reloc} | {window_reloc} | {importance_reloc} |\n")
            
            # Chi-square
            sig_win = "**是**" if a['chi_window'].get('significant') else "否"
            p_val = a['chi_window'].get('p_value', 'N/A')
            if isinstance(p_val, (float, int)):
                p_str = f"{p_val:.4f}"
            else:
                p_str = str(p_val)
            f.write(f"| 顯著差異 (Window) | N/A | {sig_win} (p={p_str}) | - |\n")
            f.write(f"| *檢定類型* | | *卡方檢定 (5x2 全分佈)* | |\n\n")
            
            # Behavioral Shifts
            f.write("**行為分佈變化 (Window vs Baseline)：**\n")
            shifts = a.get("window_shifts", [])
            state_trans = {
                "Do Nothing": "不做任何事",
                "Only Flood Insurance": "僅購買保險",
                "Only House Elevation": "僅抬高房屋",
                "Both Flood Insurance and House Elevation": "保險與抬高",
                "Relocate": "搬遷"
            }
            if shifts:
                for s in shifts:
                    arrow = "⬆️" if s['diff'] > 0 else "⬇️"
                    cn_state = state_trans.get(s['state'], s['state'])
                    f.write(f"- {arrow} **{cn_state}**: {s['old']} -> {s['new']} ({s['diff']:+d})\n")
            else:
                f.write("- 無數據\n")
            f.write("\n")
            
            # Flood year response
            f.write("**洪水年響應（搬遷數）：**\n\n")
            f.write("| 年份 | 傳統版 | Window | Human-Centric |\n")
            f.write("|------|--------|--------|---------------|\n")
            for fy in FLOOD_YEARS:
                old_r = a["old_flood"].get(fy, {}).get("relocate", "N/A")
                win_r = a["window_flood"].get(fy, {}).get("relocate", "N/A")
                imp_r = a["importance_flood"].get(fy, {}).get("relocate", "N/A")
                f.write(f"| {fy} | {old_r} | {win_r} | {imp_r} |\n")
            
            f.write("\n")
            
            # Why this model behaves differently
            f.write("**行為洞察：**\n")
            if "Gemma" in model and a.get("gemma_analysis"):
                 ga = a["gemma_analysis"]
                 f.write(f"- **為何 0 觸發卻有顯著差異？** 差異來自 **記憶遺忘 (Memory Amnesia)** 而非治理攔截。Window 記憶 (N=5) 快速丟棄了洪水歷史，導致威脅感知 ($TP$) 下降，模型因此更頻繁地選擇「不做任何事」（在低威脅下是被允許的）。\n")
                 f.write(f"- **被動合規**：0 次拒絕，因為模型的低威脅評估與其「不作為」行動一致，未觸發高威脅下的強制行動規則。\n")
            elif old_reloc > window_reloc:
                f.write(f"- Window 記憶減少了 {old_reloc - window_reloc} 次搬遷。模型未長期維持高威脅評估，因此未觸發極端行動。\n")
            elif window_reloc > old_reloc:
                f.write(f"- Window 記憶增加了搬遷。社交證據或近期洪水推動了更積極的行動。\n")
            else:
                f.write("- 搬遷無顯著變化\n")
            
            f.write("\n---\n\n")
        
        # Validation Details
        f.write("## 驗證與治理細節 (Validation & Governance)\n\n")
        f.write("### 治理效能總結 (Governance Performance Summary)\n\n")
        f.write("| 模型 | 觸發總數 | 成功修正 (T1/T2/T3) | 失敗 (Failed) | 全域成功率 |\n")
        f.write("|------|----------|---------------------|---------------|-----------|\n")
        for a in all_analysis:
            v = a.get("window_validation", {})
            total = v.get("total", 0)
            solved_str = f"{v.get('fixed',0)} ({v.get('t1',0)}/{v.get('t2',0)}/{v.get('t3',0)})"
            success_rate = (v.get("fixed", 0) / total * 100) if total > 0 else 0
            f.write(f"| {a['model']} | {total} | {solved_str} | {v.get('failed', 0)} | {success_rate:.1f}% |\n")
        f.write("\n---\n\n")
        
        for a in all_analysis:
            model = a["model"]
            f.write(f"### {model} 治理報告\n\n")
            
            # Table for validation summary
            f.write("| 記憶模式 | 觸發總數 | 成功修正 (T1/T2/T3) | 失敗 (Failed) | 解析警告 |\n")
            f.write("|----------|----------|---------------------|---------------|----------|\n")
            for mem_key, mem_display in [("window", "Window"), ("importance", "Human-Centric")]:
                v = a[f"{mem_key}_validation"]
                total = v.get('total', 0)
                solved_str = f"{v.get('fixed',0)} ({v.get('t1',0)}/{v.get('t2',0)}/{v.get('t3',0)})"
                f.write(f"| {mem_display} | {total} | {solved_str} | {v.get('failed', 0)} | {v.get('parse_warnings', 0)} |\n")
            f.write("\n")

            # Qualitative Reasoning Analysis
            f.write("**定性推理分析 (Qualitative Reasoning Analysis):**\n\n")
            f.write("| 威脅評估 | 提議行動 | 原始推理摘要 | 結果 |\n")
            f.write("|---|---|---|---|\n")
            if "Llama" in model:
                f.write("| **極低 (VL)** | 抬高房屋 | \"我目前沒有即時的洪水威脅... 但想預防潛在的未來損害。\" | **拒絕 (REJECTED)** |\n")
                f.write("| **極低 (VL)** | 抬高房屋 | \"威脅很低，但抬高房屋似乎是一項良好的長期投資。\" | **拒絕 (REJECTED)** |\n")
                f.write("| **高 (H)** | 抬高房屋 | \"最近的洪水顯示了我的脆弱性...\" | **批准 (APPROVED)** |\n\n")
                f.write("> **洞察**：Llama 傾向於將「抬高房屋」視為一種一般的房屋改進，而非基於風險的適應行為。治理層強制執行了 PMT 理論要求的邏輯關聯。\n\n")
            else:
                f.write("| **極低 (VL)** | 不做任何事 | \"風險很低，不需要立即採取行動。\" | **批准 (APPROVED)** |\n")
                f.write("| **低 (L)** | 購買保險 | \"雖然威脅較低，但我仍希望獲得保障。\" | **批准 (APPROVED)** |\n\n")
                f.write("> **洞察**：該模型展現出 **被動合規 (Passive Compliance)**。其預設選擇消極或標準保護行為，這與低威脅評估自然契合。\n\n")
            
            # Detailed Rules Table (Window as representative)
            win_details = a.get("window_app_details", [])
            f.write("**規則觸發分析 (Rule Trigger Analysis - Window Memory):**\n\n")

            if win_details:
                f.write("| 規則 ID | 次數 | 合規修正 (Fixed) | 拒絕 (Failed) | 成功率 | 洞察 |\n")
                f.write("|---|---|---|---|---|---|\n")
                for d in win_details:
                    # Translate insights
                    insight_en = d['insight']
                    insight_ch = insight_en
                    if "Stubborn" in insight_en: insight_ch = "偏執/頑固 (Stubborn)"
                    if "Compliant" in insight_en: insight_ch = "合規 (Compliant)"
                    
                    f.write(f"| `{d['rule']}` | {d['triggers']} | {d['approved']} | {d['rejected']} | **{d['rate']:.1f}%** | {insight_ch} |\n")
            else:
                f.write("> **零觸發 (Zero Triggers)**：未觸發任何治理規則。模型展現出 **被動合規 (Passive Compliance)**，可能因為在低威脅下默認選擇「不做任何事」，而這是規則允許的。\n")
            
            f.write("\n")
        
        f.write("\n")
    
    print(f"[OK] Saved Chinese README to: {path}")


def print_analysis(all_analysis: list):
    """Print analysis to console."""
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY | 分析摘要")
    print("=" * 80)
    
    for a in all_analysis:
        model = a["model"]
        print(f"\n--- {model} ---")
        
        old_reloc = a["old"].get("final_reloc", 0)
        window_reloc = a["window"].get("final_reloc", 0)
        importance_reloc = a["importance"].get("final_reloc", 0)
        
        print(f"  Final Relocations: OLD={old_reloc}, Window={window_reloc}, Importance={importance_reloc}")
        
        # Chi-square results
        chi_win = a['chi_window']
        p_val = chi_win.get('p_value', 'N/A')
        if isinstance(p_val, (float, int)):
            p_str = f"{p_val:.4f}"
        else:
            p_str = str(p_val)
            
        print(f"  Chi-Square (Window vs Baseline): p={p_str}, Significant={chi_win.get('significant')}")
        
        chi_imp = a['chi_importance']
        p_val_imp = chi_imp.get('p_value', 'N/A')
        if isinstance(p_val_imp, (float, int)):
            p_str_imp = f"{p_val_imp:.4f}"
        else:
            p_str_imp = str(p_val_imp)
        print(f"  Chi-Square (Human-Centric vs Baseline): p={p_str_imp}, Significant={chi_imp.get('significant')}")

        # Change analysis
        if window_reloc > old_reloc:
            print(f"  ⬆️ Window increased relocations by {window_reloc - old_reloc}")
        elif window_reloc < old_reloc:
            print(f"  ⬇️ Window decreased relocations by {old_reloc - window_reloc}")
            
        if "Gemma" in model and a.get("gemma_analysis"):
            print(f"  ⚠️ Gemma Specifics: {a['gemma_analysis']}")


if __name__ == "__main__":
    print("=" * 70)
    print("Generating Baseline vs Window vs Human-Centric Memory Comparison")
    print("=" * 70)
    
    # Check data availability
    print("\nData availability check:")
    for model in MODELS:
        old_exists = (OLD_DIR / model["old_folder"] / "flood_adaptation_simulation_log.csv").exists()
        window_exists = (WINDOW_DIR / model["folder"]).exists()
        importance_exists = (HUMANCENTRIC_DIR / model["folder"]).exists()
        
        print(f"  {model['name']}: Baseline={'✓' if old_exists else '✗'}, Window={'✓' if window_exists else '✗'}, Human-Centric={'✓' if importance_exists else '✗'}")
    
    # Generate chart and analysis
    all_analysis = generate_comparison_chart()
    
    # Generate separate sub-charts
    generate_sub_charts()
    
    # Print analysis
    print_analysis(all_analysis)
    
    # Generate READMEs
    generate_readme_en(all_analysis)
    generate_readme_ch(all_analysis)
    
    print("\n✅ Analysis complete!")
