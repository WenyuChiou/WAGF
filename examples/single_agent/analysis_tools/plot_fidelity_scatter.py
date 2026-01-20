
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import json
import glob
import os
import re

# Set style
sns.set_theme(style="whitegrid", context="paper", font_scale=1.4)
plt.rcParams['font.family'] = 'sans-serif'

def semantic_to_score(label):
    """Maps Threat/Risk labels to 0-4 scale."""
    if not isinstance(label, str): return -1
    label = label.upper().strip()
    if any(x in label for x in ["VERY HIGH", "VH", "SEVERE", "EXTREME"]): return 4
    if any(x in label for x in ["HIGH", "H", "MAJOR"]): return 3
    if any(x in label for x in ["MEDIUM", "MODERATE", "M"]): return 2
    if any(x in label for x in ["LOW", "L", "MINOR"]): return 1
    if any(x in label for x in ["NONE", "VERY LOW", "VL"]): return 0
    return -1

def action_to_score(skill):
    """Maps Actions to Intensity Score 0-3."""
    skill = skill.lower()
    if "relocate" in skill: return 3
    if "elevate" in skill: return 2
    if "insurance" in skill: return 1
    return 0

def load_data(root_dir):
    data = []
    # Search recursively for trace files
    files = glob.glob(os.path.join(root_dir, "**", "household_traces.jsonl"), recursive=True)
    
    for fpath in files:
        # Determine Group
        group = "Unknown"
        if "Group_B" in fpath: group = "Group B (Governed)"
        elif "Group_C" in fpath: group = "Group C (Human-Centric)"
        else: continue # Skip A or others
        
        # Determine Model
        model = "Unknown"
        if "llama" in fpath.lower(): model = "Llama 3.2"
        elif "gemma" in fpath.lower(): model = "Gemma 3"
        elif "gpt" in fpath.lower(): model = "GPT-OSS"
        
        with open(fpath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    res = rec.get('execution_result', {})
                    # Only look at approved actions or proposals
                    # Prefer APPROVED decision
                    skill_name = rec.get("approved_skill", {}).get("skill_name", "do_nothing")
                    
                    # Extract Threat
                    reasoning = rec.get("skill_proposal", {}).get("reasoning", {})
                    threat_label = reasoning.get("THREAT_LABEL", reasoning.get("threat_perception", "VL"))
                    
                    t_score = semantic_to_score(threat_label)
                    a_score = action_to_score(skill_name)
                    
                    if t_score >= 0:
                        data.append({
                            "Threat Appraisal": t_score,
                            "Action Intensity": a_score,
                            "Group": group,
                            "Model": model
                        })
                except:
                    continue
    return pd.DataFrame(data)

def plot_fidelity_scatter(df):
    if df.empty:
        print("No data found.")
        return

    # Jitter plot
    g = sns.catplot(
        data=df, 
        x="Threat Appraisal", 
        y="Action Intensity", 
        hue="Group", 
        col="Model",
        kind="strip", 
        jitter=0.2, 
        alpha=0.6, 
        height=5, 
        aspect=1,
        palette="viridis"
    )
    
    # Customizing axes
    # X: 0=None, 1=Low, 2=Med, 3=High, 4=Very High
    # Y: 0=DoNothing, 1=Insurance, 2=Elevate, 3=Relocate
    
    for ax in g.axes.flat:
        ax.set_xticks([0, 1, 2, 3, 4])
        ax.set_xticklabels(["None", "Low", "Med", "High", "Crit"])
        ax.set_yticks([0, 1, 2, 3])
        ax.set_yticklabels(["Wait", "Insur", "Elev", "Reloc"])
        
        # Add Ideal Diagonal Reference
        ax.plot([0, 3], [0, 3], ls="--", c="red", alpha=0.3, label="Ideal Rationality")

    g.fig.subplots_adjust(top=0.85)
    g.fig.suptitle("Internal Fidelity: Threat vs. Action Alignment", fontsize=16, fontweight='bold')
    
    plt.savefig("figure_4_fidelity_scatter.png")
    print("Saved figure_4_fidelity_scatter.png")

if __name__ == "__main__":
    root = "results/JOH_FINAL"
    print("Loading data...")
    df = load_data(root)
    print(f"Loaded {len(df)} points.")
    plot_fidelity_scatter(df)
