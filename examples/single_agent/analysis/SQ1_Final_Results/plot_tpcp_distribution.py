import pandas as pd
import json
import re
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# --- Configuration ---
MODELS = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b"]
GROUPS = ["Group_A", "Group_B", "Group_C"]
LABEL_ORDER = ["VH", "H", "M", "L", "VL"]

plt.rcParams['font.family'] = 'serif'
sns.set_theme(style="white", context="paper")

# --- Semantic Keywords (Same as master_report.py) ---
TA_KEYWORDS = {
    "H": ["flood", "storm", "damage", "warning", "danger", "threat", "risky", "exposed", "vulnerable", "imminent", "severe", "property loss", "high risk"],
    "L": ["minimal", "safe", "none", "low", "unlikely", "no risk", "protected", "secure"]
}
CA_KEYWORDS = {
    "H": ["grant", "subsidy", "effective", "capable", "confident", "support", "benefit", "protection", "affordable", "successful", "prepared", "mitigate", "action plan"],
    "L": ["expensive", "costly", "unable", "uncertain", "weak", "unaffordable", "insufficient", "debt", "financial burden"]
}

def map_text_to_level(text, keywords=None):
    if not isinstance(text, str): return "M"
    text = text.upper()
    # 1. Primary: Explicit Codes
    if re.search(r'\bVH\b', text): return "VH"
    if re.search(r'\bH\b', text): return "H"
    if re.search(r'\bVL\b', text): return "VL"
    if re.search(r'\bL\b', text): return "L"
    if re.search(r'\bM\b', text): return "M"
    # 2. Secondary: Keywords
    if keywords:
        if any(w.upper() in text for w in keywords.get("H", [])): return "H"
        if any(w.upper() in text for w in keywords.get("L", [])): return "L"
    return "M"

def extract_labels(model, group):
    root = Path("examples/single_agent/results/JOH_FINAL")
    group_dir = root / model / group / "Run_1"
    
    csv_candidates = list(group_dir.glob("**/simulation_log.csv"))
    jsonl_candidates = list(group_dir.glob("**/household_traces.jsonl"))
    
    formatted_files = jsonl_candidates # Prefer JSONL
    
    appraisals = []
    
    # Method 1: JSONL (Best for B/C)
    if formatted_files:
        with open(formatted_files[0], 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    proposal = data.get('skill_proposal', {})
                    reasoning = proposal.get('reasoning', {})
                    
                    # Extract TP
                    ta = (reasoning.get('TP_LABEL') or 
                          reasoning.get('threat_appraisal', {}).get('label') or
                          reasoning.get('threat_appraisals', {}).get('label'))
                    
                    # Extract CP
                    ca = (reasoning.get('CP_LABEL') or 
                          reasoning.get('coping_appraisal', {}).get('label') or
                          reasoning.get('coping_appraisals', {}).get('label'))
                    
                    # Regex Fallback
                    if not ta or not ca:
                        raw = data.get('raw_output', '')
                        if isinstance(raw, str):
                            ta_m = re.search(r'"threat_appraisals?":\s*{\s*"label":\s*"([^"]+)"', raw, re.I)
                            ca_m = re.search(r'"coping_appraisals?":\s*{\s*"label":\s*"([^"]+)"', raw, re.I)
                            ta_str = ta_m.group(1) if ta_m else ta
                            ca_str = ca_m.group(1) if ca_m else ca
                        else:
                            ta_str, ca_str = ta, ca
                    else:
                        ta_str, ca_str = ta, ca

                    # For JSON output, we stick to the extracted label, but normalize it
                    if ta_str: 
                        lbl = map_text_to_level(ta_str, TA_KEYWORDS if group == "Group_A" else None)
                        appraisals.append({'Type': 'TP', 'Label': lbl, 'Model': model, 'Group': group})
                    if ca_str: 
                        lbl = map_text_to_level(ca_str, CA_KEYWORDS if group == "Group_A" else None)
                        appraisals.append({'Type': 'CP', 'Label': lbl, 'Model': model, 'Group': group})
                        
                except: continue
                
    # Method 2: CSV (Fallback for Group A if No JSONL, or purely relying on text)
    elif csv_candidates and group == "Group_A":
         df = pd.read_csv(csv_candidates[0])
         df.columns = [c.lower() for c in df.columns]
         reason_col = next((c for c in df.columns if 'reasoning' in c), None)
         
         for idx, row in df.iterrows():
            text_ta = " ".join([str(row.get(c, "")) for c in ['threat_appraisal', reason_col, 'memory'] if c in df.columns])
            text_ca = " ".join([str(row.get(c, "")) for c in ['coping_appraisal', reason_col, 'memory'] if c in df.columns])
            
            ta_lbl = map_text_to_level(text_ta, TA_KEYWORDS)
            ca_lbl = map_text_to_level(text_ca, CA_KEYWORDS)
            
            appraisals.append({'Type': 'TP', 'Label': ta_lbl, 'Model': model, 'Group': group})
            appraisals.append({'Type': 'CP', 'Label': ca_lbl, 'Model': model, 'Group': group})

    return appraisals

# --- Main Logic ---
all_data = []
for m in MODELS:
    for g in GROUPS:
        all_data.extend(extract_labels(m, g))

df = pd.DataFrame(all_data)

# Normalize labels (handle minor typos if any, though regex helps)
df['Label'] = df['Label'].apply(lambda x: x if x in LABEL_ORDER else 'M') # Fallback to M if garbage

# Plotting
plt.style.use('seaborn-v0_8-whitegrid')
fig, axes = plt.subplots(1, 2, figsize=(18, 6))

# Plot TP Distribution
tp_df = df[df['Type'] == 'TP']
tp_counts = tp_df.groupby(['Model', 'Group', 'Label']).size().reset_index(name='Count')
tp_total = tp_df.groupby(['Model', 'Group']).size().reset_index(name='Total')
tp_props = tp_counts.merge(tp_total, on=['Model', 'Group'])
tp_props['Probability'] = tp_props['Count'] / tp_props['Total']

sns.barplot(data=tp_props, x='Label', y='Probability', hue='Model', ax=axes[0], order=LABEL_ORDER, errorbar=None)
axes[0].set_title('Threat Appraisal (TP) Probability (All Groups)')
axes[0].set_ylim(0, 1.0)

# Plot CP Distribution
cp_df = df[df['Type'] == 'CP']
cp_counts = cp_df.groupby(['Model', 'Group', 'Label']).size().reset_index(name='Count')
cp_total = cp_df.groupby(['Model', 'Group']).size().reset_index(name='Total')
cp_props = cp_counts.merge(cp_total, on=['Model', 'Group'])
cp_props['Probability'] = cp_props['Count'] / cp_props['Total']

# Faceted Plot or Hue adjustment for 9 bars?
# Using 'hue' with 3 models ok, but we have 3 groups now. 
# Better to use catplot or separate by Group. 
# Let's keep existing style but be aware X-axis handles Model/Group combination? 
# The existing code plots: x='Label', hue='Model'. This aggregates groups if we are not careful?
# Wait, existing code: sns.barplot(data=tp_props, x='Label', y='Probability', hue='Model')
# This merges Groups into the same bar if we don't separate. 
# Actually, if we want to compare Groups, we should probably FacetGrid or put Group in Hue and Model in X.
# But request is "加入group A".
# Let's modify the plot to Facet by "Group".

plt.clf()

# TP Plot
g_tp = sns.catplot(
    data=tp_props, x='Label', y='Probability', hue='Model', col='Group',
    kind='bar', order=LABEL_ORDER, palette='Greys', height=4, aspect=1,
    edgecolor='black', linewidth=1
)
g_tp.fig.suptitle('Distribution of Threat Appraisal (TP) Probability Across Conditions', y=1.05, fontsize=14, fontweight='bold')
g_tp.set(ylim=(0, 1.0))
g_tp.savefig(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ1_Final_Results\tp_distribution_all.png", dpi=600)

# CP Plot
g_cp = sns.catplot(
    data=cp_props, x='Label', y='Probability', hue='Model', col='Group',
    kind='bar', order=LABEL_ORDER, palette='Greys', height=4, aspect=1,
    edgecolor='black', linewidth=1
)
g_cp.fig.suptitle('Distribution of Coping Appraisal (CP) Probability Across Conditions', y=1.05, fontsize=14, fontweight='bold')
g_cp.set(ylim=(0, 1.0))
g_cp.savefig(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\analysis\SQ1_Final_Results\cp_distribution_all.png", dpi=600)

print("Plots saved: examples/single_agent/analysis/tp_distribution_all.png, examples/single_agent/analysis/cp_distribution_all.png")

# Print Pivot Table for User
print("\n=== TP Distribution Table (Probability) ===")
print(tp_props.pivot(index=['Model', 'Group'], columns='Label', values='Probability')[LABEL_ORDER].fillna(0).round(2))

print("\n=== CP Distribution Table (Probability) ===")
print(cp_props.pivot(index=['Model', 'Group'], columns='Label', values='Probability')[LABEL_ORDER].fillna(0).round(2))
