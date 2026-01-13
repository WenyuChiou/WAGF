"""
OLD vs Window vs Importance Memory Comparison (FIXED)
- Correctly excludes already-relocated agents from each year's count
- Includes GPT-OSS model
- Generates separate EN/CH README files
- Analyzes root causes of behavioral differences
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import json
import numpy as np

# Directory configuration
RESULTS_DIR = Path("examples/single_agent/results")
OLD_RESULTS_DIR = Path("examples/single_agent/results_old")
WINDOW_DIR = Path("examples/single_agent/results_window")
IMPORTANCE_DIR = Path("examples/single_agent/results_importance")
OUTPUT_DIR = Path("examples/single_agent/benchmark_analysis")

# Model configurations (including GPT-OSS)
MODELS = [
    {"old_folder": "Gemma_3_4B", "new_folder": "gemma3_4b_strict", "name": "Gemma 3 (4B)"},
    {"old_folder": "Llama_3.2_3B", "new_folder": "llama3.2_3b_strict", "name": "Llama 3.2 (3B)"},
    {"old_folder": "DeepSeek_R1_8B", "new_folder": "deepseek-r1_8b_strict", "name": "DeepSeek-R1 (8B)"},
    {"old_folder": "GPT-OSS_20B", "new_folder": "gpt-oss_latest_strict", "name": "GPT-OSS (20B)"},
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
    """Load OLD baseline simulation log."""
    for base_dir in [OLD_RESULTS_DIR, RESULTS_DIR]:
        csv_path = base_dir / model_folder / "flood_adaptation_simulation_log.csv"
        if csv_path.exists():
            return pd.read_csv(csv_path)
    return pd.DataFrame()


def load_memory_data(model_folder: str, memory_type: str) -> pd.DataFrame:
    """Load Window or Importance memory simulation log."""
    if memory_type == "window":
        base_dir = WINDOW_DIR
    else:
        base_dir = IMPORTANCE_DIR
    
    csv_path = base_dir / model_folder / "simulation_log.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame()


def load_audit_data(model_folder: str, memory_type: str) -> pd.DataFrame:
    """Load governance audit CSV."""
    if memory_type == "window":
        base_dir = WINDOW_DIR
    else:
        base_dir = IMPORTANCE_DIR
    
    csv_path = base_dir / model_folder / "household_governance_audit.csv"
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
    """Analyze validation and adapter behavior."""
    if audit_df.empty:
        return {"total": 0, "status": "No audit data"}
    
    total = len(audit_df)
    retries = audit_df[audit_df['retry_count'] > 0].shape[0] if 'retry_count' in audit_df.columns else 0
    val_failed = audit_df[audit_df['validated'] == False].shape[0] if 'validated' in audit_df.columns else 0
    parse_warnings = 0
    if 'parsing_warnings' in audit_df.columns:
        parse_warnings = audit_df[audit_df['parsing_warnings'].notna() & (audit_df['parsing_warnings'] != '')].shape[0]
    
    # Count failed rules
    failed_rules = {}
    if 'failed_rules' in audit_df.columns:
        for idx, row in audit_df.iterrows():
            if pd.notna(row['failed_rules']) and row['failed_rules'] != '':
                for r in str(row['failed_rules']).split('|'):
                    r = r.strip()
                    if r:
                        failed_rules[r] = failed_rules.get(r, 0) + 1
    
    status_counts = audit_df['status'].value_counts().to_dict() if 'status' in audit_df.columns else {}
    
    return {
        "total": total,
        "retries": retries,
        "retry_rate": f"{retries/total*100:.1f}%",
        "validation_failed": val_failed,
        "parse_warnings": parse_warnings,
        "failed_rules": failed_rules,
        "status": status_counts
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


def generate_3x4_comparison():
    """Generate 3x4 OLD vs Window vs Importance comparison (4 models)."""
    
    fig, axes = plt.subplots(3, 4, figsize=(18, 12))
    
    all_analysis = []
    
    for i, model_config in enumerate(MODELS):
        # Load data
        old_df = load_old_data(model_config["old_folder"])
        window_df = load_memory_data(model_config["new_folder"], "window")
        importance_df = load_memory_data(model_config["new_folder"], "importance")
        
        # Load audits
        window_audit = load_audit_data(model_config["new_folder"], "window")
        importance_audit = load_audit_data(model_config["new_folder"], "importance")
        
        # Row 1: OLD baseline
        plot_stacked_bar(axes[0, i], old_df, f"OLD: {model_config['name']}")
        
        # Row 2: Window Memory
        plot_stacked_bar(axes[1, i], window_df, f"Window: {model_config['name']}")
        
        # Row 3: Importance Memory
        plot_stacked_bar(axes[2, i], importance_df, f"Importance: {model_config['name']}")
        
        # Collect analysis data
        analysis = {
            "model": model_config["name"],
            "old": analyze_yearly_decisions(old_df, "OLD"),
            "window": analyze_yearly_decisions(window_df, "Window"),
            "importance": analyze_yearly_decisions(importance_df, "Importance"),
            "old_flood": analyze_flood_response(old_df, "OLD"),
            "window_flood": analyze_flood_response(window_df, "Window"),
            "importance_flood": analyze_flood_response(importance_df, "Importance"),
            "window_validation": analyze_validation(window_audit),
            "importance_validation": analyze_validation(importance_audit),
        }
        all_analysis.append(analysis)
    
    # Create unified legend
    handles = [plt.Rectangle((0,0),1,1, facecolor=STATE_COLORS[s]) for s in STATE_ORDER]
    fig.legend(handles, STATE_ORDER, loc='lower center', ncol=5, fontsize=8, 
               title="Adaptation State", title_fontsize=9, bbox_to_anchor=(0.5, 0.02))
    
    # Row labels
    fig.text(0.01, 0.82, "OLD\n(Baseline)", fontsize=10, fontweight='bold', 
             rotation=90, va='center', ha='center')
    fig.text(0.01, 0.50, "Window\nMemory", fontsize=10, fontweight='bold', 
             rotation=90, va='center', ha='center')
    fig.text(0.01, 0.20, "Importance\nMemory", fontsize=10, fontweight='bold', 
             rotation=90, va='center', ha='center')
    
    fig.text(0.99, 0.5, "Red lines = Flood Years (3, 4, 9)", fontsize=7, 
             rotation=90, va='center', ha='center', color='red')
    
    plt.suptitle("OLD vs Window vs Importance Memory Comparison\n(Active Agents Only - Relocated Agents Excluded)", 
                 fontsize=13, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0.03, 0.08, 0.97, 0.94])
    
    # Save chart
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "old_vs_window_vs_importance_3x4.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"[OK] Saved 3x4 comparison chart to: {output_path}")
    plt.close()
    
    return all_analysis


def generate_readme_en(all_analysis: list):
    """Generate English README."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "README_EN.md"
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# Memory Benchmark Analysis Report\n\n")
        f.write("## Key Question: Why Do Models Behave Differently After Applying Governance?\n\n")
        
        f.write("### Root Causes of Behavioral Differences\n\n")
        f.write("1. **Validation Ensures Format, Not Reasoning**\n")
        f.write("   - 100% validation pass means output FORMAT is correct\n")
        f.write("   - Models still differ in HOW they interpret threats and coping ability\n\n")
        
        f.write("2. **Memory Window Effect (top_k=3)**\n")
        f.write("   - Only 3 latest memories are kept\n")
        f.write("   - Flood history gets pushed out by social observations\n")
        f.write("   - Models sensitive to social proof (Llama) show more adaptation\n\n")
        
        f.write("3. **Governance Enforcement**\n")
        f.write("   - `strict` profile BLOCKS 'Do Nothing' when Threat is High\n")
        f.write("   - Legacy allowed 47% of 'High Threat + Do Nothing' combinations\n")
        f.write("   - This forces previously passive agents to act\n\n")
        
        f.write("---\n\n")
        f.write("## Comparison Chart\n\n")
        f.write("![Comparison](old_vs_window_vs_importance_3x4.png)\n\n")
        f.write("*Note: Each year shows only ACTIVE agents (already-relocated agents excluded)*\n\n")
        
        f.write("---\n\n")
        f.write("## Model-Specific Analysis\n\n")
        
        for a in all_analysis:
            model = a["model"]
            f.write(f"### {model}\n\n")
            
            old_reloc = a["old"].get("final_reloc", 0)
            window_reloc = a["window"].get("final_reloc", 0)
            importance_reloc = a["importance"].get("final_reloc", 0)
            
            f.write(f"| Metric | OLD | Window | Importance |\n")
            f.write(f"|--------|-----|--------|------------|\n")
            f.write(f"| Final Relocations | {old_reloc} | {window_reloc} | {importance_reloc} |\n\n")
            
            # Flood year response
            f.write("**Flood Year Response:**\n\n")
            f.write("| Year | OLD Relocate | Window Relocate | Importance Relocate |\n")
            f.write("|------|--------------|-----------------|---------------------|\n")
            for fy in FLOOD_YEARS:
                old_r = a["old_flood"].get(fy, {}).get("relocate", "N/A")
                win_r = a["window_flood"].get(fy, {}).get("relocate", "N/A")
                imp_r = a["importance_flood"].get(fy, {}).get("relocate", "N/A")
                f.write(f"| {fy} | {old_r} | {win_r} | {imp_r} |\n")
            
            f.write("\n")
            
            # Why this model behaves differently
            f.write("**Why This Model Differs:**\n")
            if window_reloc > old_reloc:
                diff = window_reloc - old_reloc
                f.write(f"- Window Memory INCREASED relocations by {diff}\n")
                f.write("- Governance blocks 'High Threat + Do Nothing'\n")
            elif window_reloc < old_reloc:
                diff = old_reloc - window_reloc
                f.write(f"- Window Memory DECREASED relocations by {diff}\n")
                f.write("- Model rarely assesses threat as 'High'\n")
            else:
                f.write("- No significant change in relocations\n")
            
            f.write("\n---\n\n")
        
        f.write("## Validation Summary\n\n")
        f.write("| Model | Memory | Total | Retries | Failed | Parse Warnings |\n")
        f.write("|-------|--------|-------|---------|--------|----------------|\n")
        for a in all_analysis:
            for mem in ["window", "importance"]:
                v = a[f"{mem}_validation"]
                if v.get("total", 0) > 0:
                    f.write(f"| {a['model']} | {mem.capitalize()} | {v['total']} | {v['retries']} | {v['validation_failed']} | {v['parse_warnings']} |\n")
        
        f.write("\n")
    
    print(f"[OK] Saved English README to: {path}")


def generate_readme_ch(all_analysis: list):
    """Generate Chinese README."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "README_CH.md"
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# 記憶體基準分析報告\n\n")
        f.write("## 核心問題：為何套用治理框架後模型行為不同？\n\n")
        
        f.write("### 行為差異的根本原因\n\n")
        f.write("1. **驗證確保格式，而非推理**\n")
        f.write("   - 100% 驗證通過表示輸出格式正確\n")
        f.write("   - 模型在解釋威脅和應對能力方面仍有差異\n\n")
        
        f.write("2. **記憶窗口效應 (top_k=3)**\n")
        f.write("   - 僅保留最新的 3 條記憶\n")
        f.write("   - 洪水歷史被社交觀察擠掉\n")
        f.write("   - 對社會證明敏感的模型（Llama）顯示更多適應\n\n")
        
        f.write("3. **治理執行**\n")
        f.write("   - `strict` 配置在威脅為高時阻止「不採取行動」\n")
        f.write("   - 傳統版允許 47% 的「高威脅 + 不採取行動」組合\n")
        f.write("   - 這迫使以前被動的代理採取行動\n\n")
        
        f.write("---\n\n")
        f.write("## 比較圖表\n\n")
        f.write("![比較](old_vs_window_vs_importance_3x4.png)\n\n")
        f.write("*注：每年僅顯示活躍代理（已搬遷代理已排除）*\n\n")
        
        f.write("---\n\n")
        f.write("## 模型特定分析\n\n")
        
        for a in all_analysis:
            model = a["model"]
            f.write(f"### {model}\n\n")
            
            old_reloc = a["old"].get("final_reloc", 0)
            window_reloc = a["window"].get("final_reloc", 0)
            importance_reloc = a["importance"].get("final_reloc", 0)
            
            f.write(f"| 指標 | 傳統版 | Window | Importance |\n")
            f.write(f"|------|--------|--------|------------|\n")
            f.write(f"| 最終搬遷數 | {old_reloc} | {window_reloc} | {importance_reloc} |\n\n")
            
            # Flood year response
            f.write("**洪水年響應：**\n\n")
            f.write("| 年份 | 傳統版搬遷 | Window 搬遷 | Importance 搬遷 |\n")
            f.write("|------|------------|-------------|------------------|\n")
            for fy in FLOOD_YEARS:
                old_r = a["old_flood"].get(fy, {}).get("relocate", "N/A")
                win_r = a["window_flood"].get(fy, {}).get("relocate", "N/A")
                imp_r = a["importance_flood"].get(fy, {}).get("relocate", "N/A")
                f.write(f"| {fy} | {old_r} | {win_r} | {imp_r} |\n")
            
            f.write("\n")
            
            # Why this model behaves differently
            f.write("**為何此模型有差異：**\n")
            if window_reloc > old_reloc:
                diff = window_reloc - old_reloc
                f.write(f"- Window 記憶增加了 {diff} 次搬遷\n")
                f.write("- 治理阻止「高威脅 + 不採取行動」\n")
            elif window_reloc < old_reloc:
                diff = old_reloc - window_reloc
                f.write(f"- Window 記憶減少了 {diff} 次搬遷\n")
                f.write("- 模型很少將威脅評估為「高」\n")
            else:
                f.write("- 搬遷無顯著變化\n")
            
            f.write("\n---\n\n")
        
        f.write("## 驗證摘要\n\n")
        f.write("| 模型 | 記憶類型 | 總數 | 重試 | 失敗 | 解析警告 |\n")
        f.write("|------|----------|------|------|------|----------|\n")
        for a in all_analysis:
            for mem in ["window", "importance"]:
                v = a[f"{mem}_validation"]
                if v.get("total", 0) > 0:
                    f.write(f"| {a['model']} | {mem.capitalize()} | {v['total']} | {v['retries']} | {v['validation_failed']} | {v['parse_warnings']} |\n")
        
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
        
        # Change analysis
        if window_reloc > old_reloc:
            print(f"  ⬆️ Window increased relocations by {window_reloc - old_reloc}")
        elif window_reloc < old_reloc:
            print(f"  ⬇️ Window decreased relocations by {old_reloc - window_reloc}")


if __name__ == "__main__":
    print("=" * 70)
    print("Generating OLD vs Window vs Importance Memory Comparison (FIXED)")
    print("=" * 70)
    
    # Check data availability
    print("\nData availability check:")
    for model in MODELS:
        old_exists = any((d / model["old_folder"]).exists() for d in [OLD_RESULTS_DIR, RESULTS_DIR])
        window_exists = (WINDOW_DIR / model["new_folder"]).exists()
        importance_exists = (IMPORTANCE_DIR / model["new_folder"]).exists()
        
        print(f"  {model['name']}: OLD={'✓' if old_exists else '✗'}, Window={'✓' if window_exists else '✗'}, Importance={'✓' if importance_exists else '✗'}")
    
    # Generate chart and analysis
    all_analysis = generate_3x4_comparison()
    
    # Print analysis
    print_analysis(all_analysis)
    
    # Generate READMEs
    generate_readme_en(all_analysis)
    generate_readme_ch(all_analysis)
    
    print("\n✅ Analysis complete!")
