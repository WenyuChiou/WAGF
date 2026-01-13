
import pandas as pd
import glob
import os

def check_audit_columns():
    files = glob.glob("results/mock_llm_strict/*.csv")
    print(f"Found {len(files)} csv files.")
    
    for f in files:
        print(f"\n--- Checking: {f} ---")
        try:
            df = pd.read_csv(f)
            cols = list(df.columns)
            
            # Check for target columns
            demo_score = "demo_score" in cols
            demo_anchors = "demo_anchors" in cols
            
            print(f"Columns Found: {len(cols)}")
            print(f"Has 'demo_score': {demo_score}")
            print(f"Has 'demo_anchors': {demo_anchors}")
            
            if demo_score:
                print(f"Sample Score: {df['demo_score'].iloc[0] if not df.empty else 'N/A'}")
            
        except Exception as e:
            print(f"Error reading {f}: {e}")

if __name__ == "__main__":
    check_audit_columns()
