
"""
Threat & Coping Appraisal Distribution Analysis (Fixed)
-------------------------------------------------------
This script analyzes how agent perceptions (Threat Appraisal & Coping Appraisal) evolve over time.
It compares:
1. Baseline (Old) - Reads directly from `threat_appraisal` column.
2. Window Memory - Merges `simulation_log.csv` with `household_governance_audit.csv` and parses JSON.
3. Human-Centric Memory - Merges `simulation_log.csv` with `household_governance_audit.csv` and parses JSON.

It generates visualization plots (Stacked Area / Heatmap style) to show the shift in perception.
"""
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np
import json
import re

# Directory configuration
OLD_DIR = Path("examples/single_agent/old_results")
WINDOW_DIR = Path("examples/single_agent/results_window")
HUMANCENTRIC_DIR = Path("examples/single_agent/results_humancentric")
OUTPUT_DIR = Path("examples/single_agent/benchmark_analysis")

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
    }
]

# Normalization Map
NORMALIZATION_MAP = {
    "VERY LOW": "VL", "VERYLOW": "VL", "VERY_LOW": "VL", "VL": "VL",
    "LOW": "L", "L": "L",
    "MEDIUM": "M", "MED": "M", "MODERATE": "M", "MOD": "M", "M": "M",
    "HIGH": "H", "H": "H",
    "VERY HIGH": "VH", "VERYHIGH": "VH", "VERY_HIGH": "VH", "VH": "VH"
}

ORDERED_LABELS = ["VL", "L", "M", "H", "VH"]
LABEL_COLORS = {
    "VL": "#2ecc71",  # Green
    "L": "#a9dfbf",   # Light Green
    "M": "#f4d03f",   # Yellow
    "H": "#e67e22",   # Orange
    "VH": "#e74c3c"   # Red
}

def normalize_sim_df(df):
    """Normalize decision column name to 'decision'."""
    if df.empty: return df
    
    # Check possible names for decision column
    for col in ['Cumulative_State', 'cumulative_state', 'decision']:
        if col in df.columns:
            df = df.rename(columns={col: 'decision'})
            break
            
    # Also normalize Year/Agent_id if needed
    if 'Year' in df.columns: df = df.rename(columns={'Year': 'year'})
    if 'Agent_id' in df.columns: df = df.rename(columns={'Agent_id': 'agent_id'})
            
    return df

def load_baseline_data(path):
    """Load old baseline data which has TP/CP columns directly."""
    if path.exists():
        df = pd.read_csv(path)
        return normalize_sim_df(df)
    return pd.DataFrame()

def load_new_data(folder_path):
    """Load new data by merging simulation log and audit log."""
    sim_path = folder_path / "simulation_log.csv"
    audit_path = folder_path / "household_governance_audit.csv"
    
    if not sim_path.exists() or not audit_path.exists():
        return pd.DataFrame()
        
    sim_df = pd.read_csv(sim_path)
    sim_df = normalize_sim_df(sim_df)
    
    audit_df = pd.read_csv(audit_df_path := audit_path)
    
    # Merge: year in sim_df matches step_id in audit_df
    # Also perform left join on agent_id
    # Note: audit_df has 'step_id' and 'agent_id'
    
    merged = pd.merge(
        sim_df, 
        audit_df, 
        left_on=['year', 'agent_id'], 
        right_on=['step_id', 'agent_id'], 
        how='left'
    )
    
    return merged

def normalize_label(val):
    val_str = str(val).upper().strip()
    
    # CASE 1: JSON String (New format)
    # e.g., '{"label": "M", "reason": "..."}'
    if "LABEL" in val_str:
        try:
            # Need to fix potential single quote json
            json_str = val.replace("'", '"')
            data = json.loads(json_str)
            if isinstance(data, dict):
                return NORMALIZATION_MAP.get(data.get("label", "M").upper(), "M")
        except:
            # Fallback regex extraction
            match = re.search(r'"label":\s*"(\w+)"', val, re.IGNORECASE)
            if match:
                return NORMALIZATION_MAP.get(match.group(1).upper(), "M")
    
    # CASE 2: List-like strings [HIGH] (Old format)
    clean_val = val_str.replace("[", "").replace("]", "").strip()
    
    # CASE 3: Numbers (0.0 - 1.0)
    if clean_val.replace('.', '', 1).isdigit():
        fval = float(clean_val)
        if fval < 0.2: return "VL"
        if fval < 0.4: return "L"
        if fval < 0.6: return "M"
        if fval < 0.8: return "H"
        return "VH"
    
    return NORMALIZATION_MAP.get(clean_val, "M") # Default to Medium if unknown

def analyze_model_tp_cp(model_config):
    """Analyze TP/CP for a specific model across 3 configurations."""
    print(f"Analyzing {model_config['name']}...")
    
    scenarios = {
        "Baseline": (OLD_DIR / model_config['old_folder'] / "flood_adaptation_simulation_log.csv", "old"),
        "Window": (WINDOW_DIR / model_config['folder'], "new"),
        "Human-Centric": (HUMANCENTRIC_DIR / model_config['folder'], "new")
    }
    
    fig, axes = plt.subplots(3, 2, figsize=(18, 12), sharex=True, sharey=True)
    fig.suptitle(f"{model_config['name']} - Perception Evolution (Active Agents Only)", fontsize=16)
    
    row_idx = 0
    
    for scenario_name, (path, fmt) in scenarios.items():
        if fmt == "old":
            df = load_baseline_data(path)
            tp_col = 'threat_appraisal'
            cp_col = 'coping_appraisal'
            dec_col = 'decision'
        else:
            df = load_new_data(path)
            tp_col = 'reason_threat_appraisal'
            cp_col = 'reason_coping_appraisal'
            dec_col = 'decision'
        
        if df.empty:
            print(f"Skipping {scenario_name} (No Data)")
            row_idx += 1
            continue
            
        print(f"  Processing {scenario_name} ({len(df)} rows)")
        
        # --- CRITICAL: FILTER RELOCATED AGENTS ---
        # Find first relocation year per agent
        # We assume 'Relocate' is the decision string. 
        # In some logs it might be 'Action 3' or 'Relocate'.
        # Let's standardize or check. The logs usually have "Relocate" or "Action 3".
        # Based on previous context, "Relocate" is likely.
        
        reloc_events = df[df[dec_col].astype(str).str.contains("Relocate", case=False, na=False)]
        
        # Map agent_id to first relocation year
        agent_reloc_year = {}
        if not reloc_events.empty:
            agent_reloc_year = reloc_events.groupby('agent_id')['year'].min().to_dict()
            
        def is_active(row):
             reloc_y = agent_reloc_year.get(row['agent_id'])
             if reloc_y is None:
                 return True
             # If current year is BEFORE or AT the relocation year, they are present.
             # BUT: User wants to see *decisions* or *perceptions*.
             # Usually, if they relocate in Year Y, they are gone in Year Y+1.
             # So we keep them IN Year Y (to capture the perception that led to relocation).
             return row['year'] <= reloc_y

        df = df[df.apply(is_active, axis=1)]
        print(f"    Active active rows after filtering: {len(df)}")

        # Normalize columns using appropriate logic
        if fmt == "new":
            df[tp_col] = df[tp_col].fillna("M")
            df[cp_col] = df[cp_col].fillna("M")
            
        df['norm_threat'] = df[tp_col].apply(normalize_label)
        df['norm_coping'] = df[cp_col].apply(normalize_label)
        
        # --- Threat Plot (Bar Chart) ---
        threat_counts = df.groupby(['year', 'norm_threat']).size().unstack(fill_value=0)
        threat_counts = threat_counts.reindex(columns=ORDERED_LABELS, fill_value=0)
        threat_pct = threat_counts.div(threat_counts.sum(axis=1), axis=0) * 100
        
        ax_threat = axes[row_idx, 0]
        # Use kind='bar', width=1.0 to look like a histogram but categorical
        threat_pct.plot(kind='bar', stacked=True, ax=ax_threat, color=[LABEL_COLORS[l] for l in ORDERED_LABELS], alpha=0.9, width=0.8)
        ax_threat.set_title(f"{scenario_name}: Threat Appraisal", fontsize=12)
        ax_threat.set_ylabel("Percentage (%)")
        ax_threat.set_ylim(0, 100)
        ax_threat.tick_params(axis='x', rotation=0)
        
        if row_idx == 0:
             ax_threat.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize='small', title="Level")
        else:
             ax_threat.legend().remove()

        # --- Coping Plot (Bar Chart) ---
        coping_counts = df.groupby(['year', 'norm_coping']).size().unstack(fill_value=0)
        coping_counts = coping_counts.reindex(columns=ORDERED_LABELS, fill_value=0)
        coping_pct = coping_counts.div(coping_counts.sum(axis=1), axis=0) * 100
        
        ax_coping = axes[row_idx, 1]
        coping_pct.plot(kind='bar', stacked=True, ax=ax_coping, color=[LABEL_COLORS[l] for l in ORDERED_LABELS], alpha=0.9, width=0.8)
        ax_coping.set_title(f"{scenario_name}: Coping Appraisal", fontsize=12)
        ax_coping.set_ylim(0, 100)
        ax_coping.legend().remove()
        ax_coping.tick_params(axis='x', rotation=0)
        
        row_idx += 1
        
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    output_filename = OUTPUT_DIR / f"{model_config['name'].replace(' ', '_').replace('(', '').replace(')', '')}_TP_CP_Evolution.png"
    plt.savefig(output_filename, dpi=150)
    print(f"Saved plot to {output_filename}")
    plt.close()

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for model in MODELS:
        analyze_model_tp_cp(model)

if __name__ == "__main__":
    main()
