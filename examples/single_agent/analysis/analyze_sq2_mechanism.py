import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
import re

# --- Configuration ---
MODELS = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b"]
GROUP = "Group_C"  # We focus on Group C for the mechanism analysis
ROOT_DIR = Path("examples/single_agent/results/JOH_FINAL")

# --- HEDGE DICTIONARY (Expert Validated) ---
HEDGE_WORDS = [
    r"\bmaybe\b", r"\bperhaps\b", r"\bpossibly\b", r"\bpossible\b", 
    r"\bmight\b", r"\bcould\b", r"\bdepends\b", r"\buncertain\b", 
    r"\bmonitor\b", r"\bevaluate\b", r"\bhowever\b", r"\balthough\b", 
    r"\bunclear\b", r"\bambiguous\b", r"\bconsider\b"
]

def count_hedges(text):
    text = text.lower()
    count = 0
    for pattern in HEDGE_WORDS:
        count += len(re.findall(pattern, text))
    return count

def analyze_traces(model, group):
    # Locate file (handle the 'raw' folder distinct structures)
    # 14B path: deepseek_r1_14b/Group_C/Run_1/raw/household_traces.jsonl
    # Others might have differing middle folders. Using glob to be safe.
    model_dir = ROOT_DIR / model / group / "Run_1"
    files = list(model_dir.glob("**/household_traces.jsonl"))
    
    if not files:
        print(f"Warning: No traces found for {model}")
        return []
    
    trace_file = files[0]
    results = []
    
    with open(trace_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                
                # Extract Reasoning Text
                # Priority: reasoning.reflection > reasoning.strategy > raw text fallback
                text_content = ""
                proposal = data.get('skill_proposal', {})
                reasoning = proposal.get('reasoning', {})
                
                if isinstance(reasoning, dict):
                    # Robust Strategy: Concatenate ALL string fields
                    # This captures 'strategy', 'reflection', 'TP_REASON', 'CP_REASON', etc.
                    parts = []
                    # Targeted keys first for order (if they exist)
                    priority_keys = ['reflection', 'thought_process', 'strategy', 'TP_REASON', 'CP_REASON']
                    
                    for k in priority_keys:
                        if k in reasoning and isinstance(reasoning[k], str):
                             parts.append(reasoning[k])
                    
                    # Then anything else we missed
                    for k, v in reasoning.items():
                        if k not in priority_keys and isinstance(v, str) and len(v) > 5:
                            parts.append(v)
                            
                    text_content = " ".join(parts)
                else:
                    text_content = str(reasoning)

                # Metrics Calculation
                if not text_content or len(text_content) < 5: 
                    continue
                    
                words = text_content.split()
                word_count = len(words)
                hedge_count = count_hedges(text_content)
                ambiguity_density = (hedge_count / word_count) * 100 if word_count > 0 else 0
                
                results.append({
                    "Model": model,
                    "Word_Count": word_count,
                    "Hedge_Count": hedge_count,
                    "Ambiguity_Density": ambiguity_density
                })
            except:
                continue
                
    return results

# --- Main Execution ---
all_data = []
for m in MODELS:
    print(f"Analyzing {m}...")
    all_data.extend(analyze_traces(m, GROUP))

df = pd.DataFrame(all_data)

if df.empty:
    print("No data found!")
    exit()

print("\n--- Summary Statistics (Mean) ---")
print(df.groupby("Model")[["Word_Count", "Ambiguity_Density"]].mean())

# --- Visualization ---
sns.set_theme(style="whitegrid")
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Plot 1: Reflection Depth (Word Count)
sns.barplot(data=df, x="Model", y="Word_Count", ax=axes[0], palette="Blues_d", errorbar='sd')
axes[0].set_title("Metric A: Reflection Depth (Cognitive Load)")
axes[0].set_ylabel("Average Word Count per Decision")
axes[0].set_xlabel("")

# Plot 2: Ambiguity Density
sns.boxplot(data=df, x="Model", y="Ambiguity_Density", ax=axes[1], palette="Reds_d")
axes[1].set_title("Metric B: Ambiguity Density (Uncertainty)")
axes[1].set_ylabel("Hedge Words per 100 Words (%)")
axes[1].set_xlabel("")

plt.tight_layout()
out_file = "examples/single_agent/analysis/sq2_mechanism_plot.png"
plt.savefig(out_file)
print(f"\nAnalysis plot saved to: {out_file}")

# Export Raw Data for transparency
df.to_csv("examples/single_agent/analysis/sq2_raw_metrics.csv", index=False)
print("Raw metrics saved to: examples/single_agent/analysis/sq2_raw_metrics.csv")
