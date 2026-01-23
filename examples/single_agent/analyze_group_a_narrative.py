import pandas as pd
import re
from collections import Counter

def analyze_narrative(model_name):
    path = f"examples/single_agent/results/JOH_FINAL/{model_name}/Group_A/Run_1/simulation_log.csv"
    print(f"analyzing Narrative for {model_name}...")
    
    try:
        df = pd.read_csv(path)
        
        # Combine all threat thoughts into one corpus
        # We target 'threat_appraisal' but fallback to 'raw_llm_decision' if needed
        # 8B has 'threat_appraisal' populated. 1.5B might strictly rely on 'raw_llm_decision' or missing text.
        
        text_column = 'threat_appraisal'
        if text_column not in df.columns or df[text_column].isna().all():
            print("  'threat_appraisal' empty, falling back to 'raw_llm_decision'")
            text_column = 'raw_llm_decision' # 1.5B might be here?
            
        texts = df[text_column].dropna().astype(str).tolist()
        
        # Keywords
        keywords = {
            "Anxiety": ["fear", "scared", "worry", "threat", "danger", "risk", "flood", "damage", "vulnerable"],
            "Safety": ["safe", "secure", "protection", "no risk", "calm", "okay", "fine"],
            "Uncertainty": ["unsure", "maybe", "don't know", "unknown", "predict", "change"],
            "Economic": ["cost", "expensive", "money", "afford", "price", "budget"]
        }
        
        counts = {k: 0 for k in keywords}
        total_words = 0
        
        for text in texts:
            words = re.findall(r'\w+', text.lower())
            total_words += len(words)
            for category, keys in keywords.items():
                for key in keys:
                    counts[category] += text.lower().count(key)
        
        # Normalize per 1000 words
        print(f"\n--- Narrative Sentiments ({model_name}) ---")
        print(f"Total Words Analyzed: {total_words}")
        if total_words > 0:
            for cat, count in counts.items():
                freq = (count / total_words) * 1000
                print(f"  {cat} Intensity: {freq:.2f} (per 1k words)")
        
        # Sample
        print(f"  Avg Length: {sum(len(t) for t in texts)/len(texts):.1f} chars")
        if len(texts) > 0:
            print(f"  Sample: {texts[0][:100]}...")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_narrative("deepseek_r1_1_5b")
    analyze_narrative("deepseek_r1_8b")
