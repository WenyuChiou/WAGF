import pandas as pd
import json
import re
import os
import glob

def analyze_abc_narrative(model_name):
    base_dir = f"examples/single_agent/results/JOH_FINAL/{model_name}"
    print(f"\n=== A/B/C Narrative Analysis ({model_name}) ===")
    
    comparative_stats = []
    
    for group in ["Group_A", "Group_B", "Group_C"]:
        texts = []
        source_type = "Unknown"
        
        # Strategy 1: Try JSONL (Preferred for B/C)
        jsonl_path = glob.glob(f"{base_dir}/{group}/Run_1/*/raw/household_traces.jsonl")
        if jsonl_path:
            source_type = "JSONL"
            with open(jsonl_path[0], 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        # Extract thought/reasoning
                        reasoning = record.get("skill_proposal", {}).get("reasoning", {})
                        
                        # DeepSeek often puts the long CoT in 'thought' or 'TP_REASON'
                        # We combine all narrative fields
                        text_parts = []
                        if "thought" in reasoning: text_parts.append(str(reasoning["thought"]))
                        if "TP_REASON" in reasoning: text_parts.append(str(reasoning["TP_REASON"]))
                        if "threat_perception" in reasoning: text_parts.append(str(reasoning["threat_perception"]))
                        
                        full_text = " ".join(text_parts)
                        if len(full_text) > 5:
                            texts.append(full_text)
                    except: continue
        
        # Strategy 2: Try CSV (Fallback for A)
        if not texts:
            csv_path = f"{base_dir}/{group}/Run_1/simulation_log.csv"
            if os.path.exists(csv_path):
                source_type = "CSV"
                df = pd.read_csv(csv_path)
                col = 'threat_appraisal' if 'threat_appraisal' in df.columns else 'raw_llm_decision'
                texts = df[col].dropna().astype(str).tolist()
                # Filter out "N/A"
                texts = [t for t in texts if len(t) > 5 and t != "N/A"]

        # Analyze
        if not texts:
            print(f"[{group}] No data found.")
            continue
            
        total_chars = sum(len(t) for t in texts)
        avg_len = total_chars / len(texts) if texts else 0
        total_words = sum(len(re.findall(r'\w+', t)) for t in texts)
        
        # Anxiety Keywords
        anxiety_keys = ["fear", "scared", "worry", "threat", "danger", "risk", "flood", "damage", "vulnerable"]
        anxiety_count = 0
        for t in texts:
            for k in anxiety_keys:
                anxiety_count += t.lower().count(k)
        
        anxiety_density = (anxiety_count / total_words * 1000) if total_words else 0
        
        comparative_stats.append({
            "Group": group,
            "Source": source_type,
            "N": len(texts),
            "Avg_Chars": avg_len,
            "Anxiety_Density": anxiety_density,
            "Cognitive_Volume_Total": total_words
        })
        
    # Print Table
    print(f"{'Group':<10} {'Source':<8} {'Avg_Len':<10} {'Anxiety/1k':<12} {'Total_Vol':<10}")
    print("-" * 60)
    for s in comparative_stats:
        print(f"{s['Group']:<10} {s['Source']:<8} {s['Avg_Chars']:<10.1f} {s['Anxiety_Density']:<12.1f} {s['Cognitive_Volume_Total']:<10}")

if __name__ == "__main__":
    analyze_abc_narrative("deepseek_r1_1_5b")
