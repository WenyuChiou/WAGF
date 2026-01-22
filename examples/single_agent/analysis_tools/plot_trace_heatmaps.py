import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path

# Config
RESULTS_DIR = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
OUTPUT_DIR = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis_tools\analysis\reports\figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FILES = {
    ("Gemma 3 4B", "Group B"): RESULTS_DIR / "gemma3_4b/Group_B/Run_1/gemma3_4b_strict/raw/household_traces.jsonl",
    ("Gemma 3 4B", "Group C"): RESULTS_DIR / "gemma3_4b/Group_C/Run_1/gemma3_4b_strict/raw/household_traces.jsonl",
    ("Llama 3.2 3B", "Group B"): RESULTS_DIR / "llama3_2_3b/Group_B/Run_1/llama3_2_3b_strict/raw/household_traces.jsonl",
    ("Llama 3.2 3B", "Group C"): RESULTS_DIR / "llama3_2_3b/Group_C/Run_1/llama3_2_3b_strict/raw/household_traces.jsonl",
}

SKILL_MAP = {
    1: "Buy Insurance",
    2: "Elevate House",
    3: "Relocate",
    4: "Do Nothing"
}

ORDERED_THREATS = ["VL", "L", "M", "H", "VH"]
ORDERED_ACTIONS = ["Do Nothing", "Buy Insurance", "Elevate House", "Relocate"]

def parse_traces(filepath, model_label, group_label):
    data = []
    if not filepath.exists():
        print(f"Warning: File not found {filepath}")
        return data

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                record = json.loads(line)
                
                # Extract Action
                skill_id = None
                
                # Try from execution result (final action)
                if 'approved_skill' in record and 'mapping' in record['approved_skill']:
                    # This is tricky, mapping is 'sim.noop'. 
                    # Better to use decision from input/output if possible, but trace format varies.
                    # Let's trust 'skill_proposal' -> 'raw_output' -> 'decision' for INTENT vs 'approved' for OUTCOME.
                    # The friction comes from INTENT being blocked. So we want INTENT.
                    pass
                
                # Extract INTENT (What they WANTED to do)
                intent_action = "Unknown"
                if 'skill_proposal' in record:
                   prop = record.get('skill_proposal', {}) 
                   raw = prop.get('raw_output')
                   
                   # Try parsing raw string if it's a string
                   if isinstance(raw, str):
                       try:
                           raw_json = json.loads(raw)
                           if 'decision' in raw_json:
                               val = raw_json['decision']
                               # Handle list or int
                               if isinstance(val, list): val = val[0] 
                               intent_action = SKILL_MAP.get(int(val), "Unknown")
                       except:
                           pass
                   elif isinstance(raw, dict):
                       if 'decision' in raw:
                           val = raw['decision']
                           if isinstance(val, list): val = val[0]
                           intent_action = SKILL_MAP.get(int(val), "Unknown")

                # Extract Threat Appraisal
                threat_label = "Unknown"
                if 'skill_proposal' in record:
                    prop = record.get('skill_proposal', {})
                    if 'reasoning' in prop and isinstance(prop['reasoning'], dict):
                        threat_label = prop['reasoning'].get('TP_LABEL', 'Unknown')
                    
                    # Fallback to parsing raw output if reasoning dict is missing TP_LABEL
                    if threat_label == "Unknown":
                         try:
                            # Access raw_output again
                            if isinstance(prop.get('raw_output'), str):
                                raw_json = json.loads(prop.get('raw_output'))
                                threat_label = raw_json.get('threat_appraisal', {}).get('label', 'Unknown')
                            elif isinstance(prop.get('raw_output'), dict):
                                threat_label = prop['raw_output'].get('threat_appraisal', {}).get('label', 'Unknown')
                         except:
                            pass
                
                # Filter weird labels
                if threat_label not in ORDERED_THREATS:
                    continue 

                data.append({
                    "Model": model_label,
                    "Group": group_label,
                    "Threat Appraisal": threat_label,
                    "Action Intent": intent_action
                })
            except Exception as e:
                # print(f"Error parsing line: {e}")
                pass
                
    return data

def plot_heatmaps():
    all_data = []
    for (model, group), path in TARGET_FILES.items():
        print(f"Processing {model} - {group}...")
        all_data.extend(parse_traces(path, model, group))

    df = pd.DataFrame(all_data)
    
    if df.empty:
        print("No data found!")
        return

    # Create a grid of plots
    # We want 2x2: Rows=Model, Cols=Group
    
    g = sns.FacetGrid(df, row="Model", col="Group", height=5, aspect=1.2)
    
    def heatmap_const(data, **kwargs):
        # Pivot to create matrix: Action (y) x Threat (x)
        # Count frequency
        pivot = data.groupby(['Action Intent', 'Threat Appraisal']).size().unstack(fill_value=0)
        
        # Reindex to ensure all rows/cols exist
        pivot = pivot.reindex(index=ORDERED_ACTIONS, columns=ORDERED_THREATS, fill_value=0)
        
        # Plot
        sns.heatmap(pivot, annot=True, fmt='d', cmap="YlOrRd", cbar=False, linewidths=.5)

    g.map_dataframe(heatmap_const)
    
    g.set_titles(row_template="{row_name}", col_template="{col_name}")
    g.set_axis_labels("Threat Appraisal (Perceived Risk)", "Intended Action")
    
    plt.subplots_adjust(top=0.9)
    g.fig.suptitle('Micro-Audit: Decision Logic vs. Perceived Threat\n(Revealing "Appraisal Collapse" vs "Panic")', fontsize=16, fontweight='bold')
    
    save_path = OUTPUT_DIR / "final_combined_trace_heatmap.png"
    plt.savefig(save_path, bbox_inches='tight', dpi=300)
    print(f"Saved {save_path}")

if __name__ == "__main__":
    plot_heatmaps()
