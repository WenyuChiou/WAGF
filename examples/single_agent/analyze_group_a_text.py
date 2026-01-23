import pandas as pd
import re

def analyze_text_alignment():
    path = r"examples/single_agent/results/JOH_FINAL/deepseek_r1_8b/Group_A/Run_1/simulation_log.csv"
    print(f"Reading {path}...")
    
    try:
        df = pd.read_csv(path)
        
        # We look for rows where threat_appraisal text implies SAFETY but decision is ACTION
        
        safe_keywords = ["safe", "secure", "low risk", "no threat", "not worried", "minimal risk"]
        action_keywords = ["Relocate", "Elevate", "Insurance"] # Decision column values
        
        dissonance_count = 0
        total_actions = 0
        
        print("\n--- Cognitive Dissonance Check ---")
        
        for index, row in df.iterrows():
            decision = str(row['decision'])
            text = str(row['threat_appraisal']).lower()
            
            # Is it an Action?
            is_action = any(act in decision for act in action_keywords)
            
            if is_action:
                total_actions += 1
                # Does the text claim safety?
                is_safe_text = any(kw in text for kw in safe_keywords)
                # But exclude if they also say "but" or "future" (simple heuristic)
                # Let's just look for raw "safe" claims first.
                
                if is_safe_text:
                    # Refine: Ensure it doesn't say "not safe"
                    if "not safe" not in text and "unsafe" not in text:
                        dissonance_count += 1
                        if dissonance_count <= 5:
                            print(f"\n[Dissonance #{dissonance_count}]")
                            print(f"  Decision: {decision}")
                            print(f"  Thought: {row['threat_appraisal']}")
                            
        print(f"\nTotal Actions Checked: {total_actions}")
        print(f"Dissonance Found: {dissonance_count} ({dissonance_count/total_actions*100:.1f}%)")
        
    except Exception as e:
        print(e)

if __name__ == "__main__":
    analyze_text_alignment()
