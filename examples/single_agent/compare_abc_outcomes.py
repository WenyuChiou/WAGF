import pandas as pd
import glob
import os

def analyze_group_outcomes(base_dir, model_name):
    print(f"Analyzing Outcomes for {model_name}...")
    
    comparative_data = []
    
    for group in ["Group_A", "Group_B", "Group_C"]:
        path = os.path.join(base_dir, model_name, group, "Run_1", "simulation_log.csv")
        if not os.path.exists(path):
            print(f"  Missing: {path}")
            continue
            
        try:
            df = pd.read_csv(path)
            
            # 1. Action Distribution
            actions = df['decision'].value_counts(normalize=True).to_dict()
            
            # 2. Wealth / Damage (Need columns? 'current_funds' or similar?)
            # Checking headers from previous step: 
            # agent_id,year,decision,raw_llm_code,raw_llm_decision,threat_appraisal,coping_appraisal,memory...
            # Does it have financial data? Maybe not in this log.  
            # We'll focus on ACTIONS for now. Action = Adaptation.
            
            # 3. Text Analysis of Threat (Qualitative Asymmetry)
            # Group A's "threat_appraisal" column vs Group B/C
            # We can count keywords in the 'threat_appraisal' column if it exists
            
            avg_threat_len = 0
            if 'threat_appraisal' in df.columns:
                avg_threat_len = df['threat_appraisal'].astype(str).apply(len).mean()
            
            comparative_data.append({
                "Group": group,
                "Actions": actions,
                "Avg_Threat_Len": avg_threat_len,
                "Sample_Size": len(df)
            })
            
        except Exception as e:
            print(f"Error reading {group}: {e}")

    # Print Summary
    print(f"\n=== {model_name} Comparative Analysis ===")
    for d in comparative_data:
        print(f"\n[{d['Group']}] (N={d['Sample_Size']})")
        print(f"  Threat Cognition (Chars): {d['Avg_Threat_Len']:.1f}")
        print(f"  Action Distribution:")
        for act, freq in d['Actions'].items():
            print(f"    {act}: {freq*100:.1f}%")

if __name__ == "__main__":
    analyze_group_outcomes("examples/single_agent/results/JOH_FINAL", "deepseek_r1_8b")
    analyze_group_outcomes("examples/single_agent/results/JOH_FINAL", "deepseek_r1_1_5b")
