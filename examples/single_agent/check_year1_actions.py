import pandas as pd
import sys

def check_year1():
    path = r"examples/single_agent/results/JOH_FINAL/deepseek_r1_1_5b/Group_A/Run_1/simulation_log.csv"
    print(f"Reading {path}...")
    try:
        df = pd.read_csv(path)
        y1 = df[df['year'] == 1]
        print(f"Year 1 Records: {len(y1)}")
        print("Year 1 Actions:")
        print(y1['decision'].value_counts())
        
        # Check Year 2 for 'Already relocated' where Year 1 was NOT Relocate
        # This proves hallucination
        y2 = df[df['year'] == 2]
        
        # Join on agent_id
        merged = pd.merge(y1, y2, on='agent_id', suffixes=('_y1', '_y2'))
        
        hallucinations = merged[
            (merged['decision_y1'] != 'Relocate') & 
            (merged['decision_y2'] == 'Already relocated')
        ]
        
        print("\n--- Hallucination Check ---")
        print(f"Agents who DID NOT Move in Y1 but claimed 'Already relocated' in Y2: {len(hallucinations)}")
        if len(hallucinations) > 0:
            print("Examples:")
            print(hallucinations[['agent_id', 'decision_y1', 'decision_y2']].head())
            
    except Exception as e:
        print(e)

if __name__ == "__main__":
    check_year1()
