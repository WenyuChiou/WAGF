import pandas as pd
import re
from pathlib import Path
from textblob import TextBlob
import numpy as np

# Configuration
RESULTS_DIR = Path("results/BENCHMARK_2026")
SUMMARY_FILE = RESULTS_DIR / "deepseek_fidelity_gap_analysis.csv"

def extract_think_and_final(raw_response):
    """
    Extracts the <think> content and the final output from the raw LLM response.
    Returns (think_content, final_content)
    """
    if pd.isna(raw_response):
        return "", ""
    
    # Extract <think>
    think_match = re.search(r'<think>(.*?)</think>', raw_response, re.DOTALL)
    think_content = think_match.group(1).strip() if think_match else ""
    
    # Extract Final (everything after </think>)
    final_content = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL).strip()
    
    return think_content, final_content

def get_action_score(decision_code):
    """
    Maps decision codes to a 'Protective Sentiment' score.
    High Protection (Relocate) = -1.0 (Negative Sentiment towards current state / High Fear)
    Low Protection (Do Nothing) = 1.0 (Positive Sentiment towards current state / Low Fear)
    """
    # Decision Map from Agent Config
    # 1: Do Nothing -> Minimal Fear (1.0)
    # 2: Buy Insurance -> Moderate Fear (0.0)
    # 3: Elevate House -> High Fear (-0.5)
    # 4: Relocate -> Max Fear (-1.0)
    
    try:
        code = int(float(decision_code))
    except (ValueError, TypeError):
        return 1.0 # Default to passive
        
    if code == 1: return 1.0    # Do Nothing (Calm)
    if code == 2: return 0.0    # Insurance (Concerned)
    if code == 3: return -0.5   # Elevate (Afraid)
    if code == 4: return -1.0   # Relocate (Panic)
    return 1.0

def analyze_deepseek_run(model_name, group_name):
    run_dir = RESULTS_DIR / model_name.replace(":", "_") / group_name / "Run_1"
    log_path = run_dir / "simulation_log.csv"
    
    if not log_path.exists():
        print(f"Skipping {group_name}: No log found at {log_path}")
        return None
        
    print(f"Analyzing {group_name}...")
    df = pd.read_csv(log_path)
    
    # We need the RAW response to find <think> tags. 
    # If simulation_log.csv doesn't have it, we might need to check audit logs or 
    # assume 'threat_appraisal' might contain leftover formatting if strict parsing failed.
    # ideally, we should have a 'raw_response' column, but let's try to infer from 'reasoning' columns if available.
    # NOTE: The current simulation_log might usually clean this. 
    # Let's assume for this specific DeepSeek analysis, we are parsing the 'raw_output' if available, 
    # or we check if 'threat_appraisal' contains it. 
    
    # Actually, the best source is usually the `audit.log` or if the CSV saved `raw_output`.
    # Let's check columns.
    required_col = 'raw_output' if 'raw_output' in df.columns else 'threat_appraisal'
    
    results = []
    
    for idx, row in df.iterrows():
        raw_text = str(row.get(required_col, ""))
        
        # 1. Parse Think vs Action
        # In Group A, distinct think tags might not exist, but for DeepSeek they should if we didn't strip them too early.
        # If we stripped them in the CSV, we can't do this analysis post-hoc without raw logs.
        # BUT, assume we have them or we analyze the TextBlob of 'threat_appraisal' (Internal) vs 'decision' (External)
        
        if '<think>' in raw_text:
             think_text, _ = extract_think_and_final(raw_text)
        else:
             # Fallback: Treat the whole 'threat_appraisal' as the internal thought
             think_text = str(row.get('threat_appraisal', ''))
        
        # 2. Calculate Internal Sentiment (The "Fear" Score)
        # We want "Negative" sentiment to map to "High Fear"
        blob = TextBlob(think_text)
        internal_sentiment = blob.sentiment.polarity
        
        # 3. Calculate External Action Score
        action_score = get_action_score(row.get('decision', 1))
        
        # 4. Fidelity Gap
        gap = abs(internal_sentiment - action_score)
        
        results.append({
            "year": row['year'],
            "agent_id": row['agent_id'],
            "think_len": len(think_text),
            "internal_sentiment": internal_sentiment,
            "action_score": action_score,
            "fidelity_gap": gap
        })
        
    return pd.DataFrame(results)

def main():
    model = "deepseek_r1_8b"
    
    stats_rows = []
    
    for group in ["Group_A", "Group_B"]:
        df_res = analyze_deepseek_run(model, group)
        if df_res is not None:
            avg_gap = df_res['fidelity_gap'].mean()
            avg_len = df_res['think_len'].mean()
            
            stats_rows.append({
                "Group": group,
                "Avg Fidelity Gap": avg_gap,
                "Avg Think Length": avg_len,
                "Sample Size": len(df_res)
            })
            
            # Save detail
            output_csv = RESULTS_DIR / model.replace(":", "_") / group / "Run_1" / "fidelity_gap_details.csv"
            df_res.to_csv(output_csv, index=False)
            print(f"Saved details to {output_csv}")

    final_df = pd.DataFrame(stats_rows)
    print("\n=== DeepSeek Fidelity Analysis ===")
    print(final_df.to_string(index=False))
    
    final_df.to_csv(SUMMARY_FILE, index=False)

if __name__ == "__main__":
    main()
