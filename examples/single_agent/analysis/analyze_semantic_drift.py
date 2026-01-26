import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --- Configuration ---
MODELS = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b"]
GROUPS = ["Group_A", "Group_B", "Group_C"]
ROOT_DIR = Path("examples/single_agent/results/JOH_FINAL")

def get_reasoning_text(data, group):
    """Robust extraction of reasoning text."""
    # For Group A, we might not have 'skill_proposal' -> 'reasoning' dict
    # We might have 'thought_process' or just raw decision text?
    # Let's check common patterns.
    
    # 1. Try Standard Group C/B Structure
    proposal = data.get('skill_proposal', {})
    if proposal:
        reasoning = proposal.get('reasoning', {})
        if isinstance(reasoning, dict):
            parts = []
            keys = ['reflection', 'thought_process', 'strategy', 'TP_REASON', 'CP_REASON']
            for k in keys:
                if k in reasoning and isinstance(reasoning[k], str):
                    parts.append(reasoning[k])
            for k, v in reasoning.items():
                if k not in keys and isinstance(v, str) and len(v) > 5:
                    parts.append(v)
            return " ".join(parts)
        elif isinstance(reasoning, str):
            return reasoning
            
    # 2. Try Group A Structure (Memory or direct reasoning columns)
    # Group A usually doesn't output 'skill_proposal' JSON.
    # It might be in 'raw_output' directly or parsed into 'reasoning' column in CSV?
    # But here we are reading JSONL traces.
    # Group A traces usually contain 'raw_output'.
    if 'raw_output' in data and isinstance(data['raw_output'], str):
        return data['raw_output']
        
    return ""

def analyze_drift(model, group):
    model_dir = ROOT_DIR / model / group / "Run_1"
    # Robust file finding: Look recursively under the Group/Run folder
    # This handles the extra 'strict' or 'disabled' subfolders in 8B/1.5B
    files = list(model_dir.rglob("household_traces.jsonl"))
    
    if not files:
        print(f"Warning: No traces found for {model} in {model_dir}")
        return []
        
    print(f"Found traces for {model}: {files[0]}")
        
    # 1. Load Data
    traces = []
    with open(files[0], 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                agent_id = data.get('agent_id')
                step = data.get('step_id', 0)
                
                text = get_reasoning_text(data, group)
                if len(text) > 10:
                    traces.append({
                        'agent_id': agent_id,
                        'step': step,
                        'text': text
                    })
            except: continue
            
    if not traces: return []
    
    df = pd.DataFrame(traces)
    
    # 2. Vectorize All Text (TF-IDF)
    # We build the vocabulary from ALL years for this model to ensure consistency
    vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    tfidf_matrix = vectorizer.fit_transform(df['text'])
    
    # Map array index back to DataFrame
    df['vec_idx'] = range(len(df))
    
    drift_scores = []
    
    # 3. Calculate YoY Similarity per Agent
    for agent_id, group_df in df.groupby('agent_id'):
        # Sort by step to ensure chronological order (Year 1 -> Year 2 -> ...)
        group_df = group_df.sort_values('step')
        
        # We need at least 2 records to compare
        if len(group_df) < 2: continue
        
        # Iterate through consecutive pairs
        for i in range(len(group_df) - 1):
            idx_t = group_df.iloc[i]['vec_idx']
            idx_t1 = group_df.iloc[i+1]['vec_idx']
            
            vec1 = tfidf_matrix[idx_t]
            vec2 = tfidf_matrix[idx_t1]
            
            sim = cosine_similarity(vec1, vec2)[0][0]
                
            drift_scores.append({
                "Model": model,
                "Group": group,
                "Agent_ID": agent_id,
                "Year_Pair": f"Step_{group_df.iloc[i]['step']}-{group_df.iloc[i+1]['step']}",
                "Similarity": sim
            })
            
    return drift_scores
            
    return drift_scores

# --- Main Execution ---
all_drift = []
for m in MODELS:
    for g in GROUPS:
        print(f"Analyzing Semantic Drift for {m} - {g}...")
        all_drift.extend(analyze_drift(m, g))

df_drift = pd.DataFrame(all_drift)

if df_drift.empty:
    print("No drift data calculated.")
    exit()

print("\n--- Semantic Consistency Matrix (Mean) ---")
pivot = df_drift.groupby(["Model", "Agent_ID"])["Similarity"].mean().groupby("Model").mean() 
# Wait, let's group by Model AND Group
print(df_drift.groupby(["Model", "Group"])["Similarity"].mean().unstack())

# --- Visualization ---
sns.set_theme(style="whitegrid")
plt.figure(figsize=(14, 6))

# Faceted Plot: Metric across Groups
g = sns.catplot(
    data=df_drift, x="Model", y="Similarity", col="Group", 
    kind="bar", order=MODELS, palette="viridis", 
    height=5, aspect=0.8, capsize=.1, errorbar="sd"
)

g.fig.suptitle("Lag-1 Semantic Autocorrelation (Inertia)", y=1.05, fontsize=16)
g.set_axis_labels("", "Cosine Similarity (T vs T+1)")
g.set(ylim=(0, 1.0))

out_file = "examples/single_agent/analysis/sq2_semantic_drift_3x3.png"
plt.savefig(out_file)
print(f"\n3x3 Matrix Plot saved to: {out_file}")

# Save CSV
df_drift.to_csv("examples/single_agent/analysis/sq2_semantic_drift_3x3.csv", index=False)
