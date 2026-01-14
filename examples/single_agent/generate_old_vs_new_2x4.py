"""
OLD vs NEW 2x4 Comparison Chart Generator

Creates a 2x4 grid comparing:
- Row 1: OLD baseline results (LLMABMPMT-Final.py)
- Row 2: NEW governed framework results (_strict suffix)

Includes validation metrics and decision reasoning analysis.
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import json

# Directory configuration
RESULTS_DIR = Path("examples/single_agent/results_window_v2")
OLD_RESULTS_DIR = Path("examples/single_agent/results_old")

# Model configurations
MODELS = [
    {"old_folder": "Gemma_3_4B", "new_folder": "gemma3_4b_strict", "name": "Gemma 3 (4B)"},
    {"old_folder": "Llama_3.2_3B", "new_folder": "llama3_2_3b_strict", "name": "Llama 3.2 (3B)"},
    {"old_folder": "DeepSeek_R1_8B", "new_folder": "deepseek_r1_8b_strict", "name": "DeepSeek-R1 (8B)"},
    {"old_folder": "GPT-OSS_20B", "new_folder": "gpt_oss_latest_strict", "name": "GPT-OSS (20B)"},
]

# Standard adaptation state colors (matching baseline)
STATE_COLORS = {
    "Do Nothing": "#1f77b4",
    "Only Flood Insurance": "#ff7f0e",
    "Only House Elevation": "#2ca02c",
    "Both Flood Insurance and House Elevation": "#d62728",
    "Relocate": "#9467bd"
}

STATE_ORDER = [
    "Do Nothing",
    "Only Flood Insurance",
    "Only House Elevation",
    "Both Flood Insurance and House Elevation",
    "Relocate"
]


def load_old_data(model_folder: str) -> pd.DataFrame:
    """Load OLD baseline simulation log."""
    # Try both potential locations
    for base_dir in [OLD_RESULTS_DIR, RESULTS_DIR]:
        csv_path = base_dir / model_folder / "flood_adaptation_simulation_log.csv"
        if csv_path.exists():
            return pd.read_csv(csv_path)
    return pd.DataFrame()


def load_new_data(model_folder: str) -> pd.DataFrame:
    """Load NEW governed framework simulation log."""
    csv_path = RESULTS_DIR / model_folder / "simulation_log.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame()


def load_audit_summary(model_folder: str) -> dict:
    """Load audit summary for validation metrics."""
    json_path = RESULTS_DIR / model_folder / "audit_summary.json"
    if json_path.exists():
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def process_for_chart(df: pd.DataFrame) -> pd.DataFrame:
    """Process dataframe: filter relocated agents after their first year."""
    if df.empty:
        return df
    
    # Determine column names (different between old and new)
    year_col = 'Year' if 'Year' in df.columns else 'year'
    dec_col = None
    for col in ['Cumulative_State', 'cumulative_state', 'decision']:
        if col in df.columns:
            dec_col = col
            break
    
    if dec_col is None:
        return pd.DataFrame()
    
    # Normalize column names
    df = df.rename(columns={year_col: 'year', dec_col: 'decision'})
    
    # Determine agent ID column
    agent_col = 'Agent_id' if 'Agent_id' in df.columns else 'agent_id'
    df = df.rename(columns={agent_col: 'agent_id'})
    
    # Find first relocation year per agent
    relocations = df[df['decision'] == 'Relocate'].groupby('agent_id')['year'].min()
    relocations = relocations.reset_index()
    relocations.columns = ['agent_id', 'first_reloc_year']
    
    # Merge and filter
    df = df.merge(relocations, on='agent_id', how='left')
    df = df[df['first_reloc_year'].isna() | (df['year'] <= df['first_reloc_year'])]
    
    return df


def plot_stacked_bar(ax, df: pd.DataFrame, title: str, show_legend: bool = False):
    """Plot stacked bar chart on given axes."""
    if df.empty:
        ax.text(0.5, 0.5, f"{title}\n(No Data)", ha='center', va='center', 
                fontsize=11, transform=ax.transAxes)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.set_xticks([])
        ax.set_yticks([])
        return None
    
    # Pivot table
    pivot = df.pivot_table(index='year', columns='decision', aggfunc='size', fill_value=0)
    
    # Ensure consistent ordering
    categories = [c for c in STATE_ORDER if c in pivot.columns]
    plot_colors = [STATE_COLORS.get(c, "#333333") for c in categories]
    
    # Stacked bar plot
    pivot[categories].plot(kind='bar', stacked=True, ax=ax, color=plot_colors, width=0.8, legend=False)
    
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel("Year", fontsize=9)
    ax.set_ylabel("Agents", fontsize=9)
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    ax.tick_params(axis='x', rotation=0, labelsize=8)
    ax.tick_params(axis='y', labelsize=8)
    
    return categories


def extract_validation_stats(model_folder: str) -> dict:
    """Extract validation statistics from audit files.
    
    Reads both the audit summary JSON and CSV for comprehensive stats.
    """
    stats = {"total": 0, "approved": 0, "blocked": 0, "approval_rate": "N/A"}
    
    # Try JSON summary first (most accurate)
    json_path = RESULTS_DIR / model_folder / "audit_summary.json"
    if json_path.exists():
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)
                stats["total"] = summary.get("total_traces", 0)
                stats["validation_errors"] = summary.get("validation_errors", 0)
                stats["validation_warnings"] = summary.get("validation_warnings", 0)
                
                # Get decision breakdown
                agent_types = summary.get("agent_types", {})
                household = agent_types.get("household", {})
                decisions = household.get("decisions", {})
                stats["decisions"] = decisions
                
                # Calculate approval rate from CSV if available
                csv_path = RESULTS_DIR / model_folder / "household_governance_audit.csv"
                if csv_path.exists():
                    df = pd.read_csv(csv_path)
                    total = len(df)
                    # Use 'validated' column (True/False) or 'status' column
                    if 'validated' in df.columns:
                        approved = df['validated'].sum() if df['validated'].dtype == bool else (df['validated'] == True).sum()
                    elif 'status' in df.columns:
                        approved = (df['status'] == 'approved').sum()
                    else:
                        approved = total  # Assume all approved if no validation column
                    
                    stats["total"] = total
                    stats["approved"] = approved
                    stats["blocked"] = total - approved
                    stats["approval_rate"] = f"{approved/total*100:.1f}%" if total > 0 else "N/A"
                    
                return stats
        except Exception as e:
            print(f"  Warning: Could not read audit summary for {model_folder}: {e}")
    
    # Fallback to CSV only
    csv_path = RESULTS_DIR / model_folder / "household_governance_audit.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            total = len(df)
            stats["total"] = total
            stats["approved"] = total  # Conservative assumption
            stats["approval_rate"] = "100.0%"
        except Exception:
            pass
    
    return stats


def calculate_decision_distribution(df: pd.DataFrame) -> dict:
    """Calculate final year decision distribution."""
    if df.empty:
        return {}
    
    max_year = df['year'].max()
    final_df = df[df['year'] == max_year]
    
    dist = final_df['decision'].value_counts()
    total = len(final_df)
    
    return {state: f"{count} ({count/total*100:.1f}%)" for state, count in dist.items()}


def generate_2x4_comparison():
    """Generate the 2x4 OLD vs NEW comparison chart."""
    
    fig, axes = plt.subplots(2, 4, figsize=(20, 10))
    
    all_categories = set()
    comparison_data = []
    
    for i, model_config in enumerate(MODELS):
        # Load OLD baseline data
        old_df = load_old_data(model_config["old_folder"])
        old_df = process_for_chart(old_df)
        
        # Load NEW governed data
        new_df = load_new_data(model_config["new_folder"])
        new_df = process_for_chart(new_df)
        
        # Row 1: OLD baseline
        cats = plot_stacked_bar(axes[0, i], old_df, f"OLD: {model_config['name']}")
        if cats:
            all_categories.update(cats)
        
        # Row 2: NEW governed
        cats = plot_stacked_bar(axes[1, i], new_df, f"NEW: {model_config['name']}")
        if cats:
            all_categories.update(cats)
        
        # Collect comparison data
        old_dist = calculate_decision_distribution(old_df)
        new_dist = calculate_decision_distribution(new_df)
        validation = extract_validation_stats(model_config["new_folder"])
        
        comparison_data.append({
            "model": model_config["name"],
            "old_dist": old_dist,
            "new_dist": new_dist,
            "validation": validation
        })
    
    # Create unified legend
    handles = [plt.Rectangle((0,0),1,1, facecolor=STATE_COLORS[s]) for s in STATE_ORDER]
    fig.legend(handles, STATE_ORDER, loc='lower center', ncol=5, fontsize=10, 
               title="Adaptation State", title_fontsize=11, bbox_to_anchor=(0.5, 0.02))
    
    # Row labels
    fig.text(0.01, 0.75, "OLD\n(Baseline)", fontsize=14, fontweight='bold', 
             rotation=90, va='center', ha='center')
    fig.text(0.01, 0.35, "NEW\n(Governed)", fontsize=14, fontweight='bold', 
             rotation=90, va='center', ha='center')
    
    plt.suptitle("OLD Baseline vs NEW Governed Framework Comparison\n(100 Agents, 10 Years)", 
                 fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0.03, 0.08, 1, 0.94])
    
    # Save chart
    output_path = Path("examples/single_agent/old_vs_new_comparison_2x4.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"[OK] Saved 2x4 comparison chart to: {output_path}")
    plt.close()
    
    # Print comparison analysis
    print("\n" + "=" * 70)
    print("COMPARISON ANALYSIS: OLD Baseline vs NEW Governed Framework")
    print("=" * 70)
    
    for data in comparison_data:
        print(f"\n[MODEL] {data['model']}")
        print("-" * 50)
        
        print("  OLD (Baseline) Final Distribution:")
        for state, val in data["old_dist"].items():
            print(f"    - {state}: {val}")
        
        print("  NEW (Governed) Final Distribution:")
        for state, val in data["new_dist"].items():
            print(f"    - {state}: {val}")
        
        if data["validation"]:
            v = data["validation"]
            decisions = v.get("decisions", {})
            if decisions:
                dec_str = ", ".join([f"{k}={cnt}" for k, cnt in decisions.items()])
                print(f"  Decisions: {dec_str}")
            print(f"  Validation: {v.get('approved', 'N/A')}/{v.get('total', 'N/A')} ({v.get('approval_rate', 'N/A')}) | Errors: {v.get('validation_errors', 0)} | Warnings: {v.get('validation_warnings', 0)}")
    
    return comparison_data


if __name__ == "__main__":
    print("=" * 70)
    print("Generating OLD vs NEW 2x4 Comparison Chart")
    print("=" * 70)
    
    # Check data availability
    print("\nData availability check:")
    for model in MODELS:
        old_exists = any((d / model["old_folder"]).exists() for d in [OLD_RESULTS_DIR, RESULTS_DIR])
        new_exists = (RESULTS_DIR / model["new_folder"]).exists()
        old_status = "[OK]" if old_exists else "[MISSING]"
        new_status = "[OK]" if new_exists else "[MISSING]"
        print(f"  {model['name']}: OLD={old_status}, NEW={new_status}")
    
    # Generate chart
    generate_2x4_comparison()
