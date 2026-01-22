import pandas as pd
from pathlib import Path
import re

def heuristic_score(text):
    if pd.isna(text) or not isinstance(text, str):
        return 3.0 # Default to moderate if empty
    
    text = text.lower()
    
    # Very High / Higher priority keywords
    if any(k in text for k in ["very high", "extreme", "severe", "urgent", "critical", "highest"]):
        return 5.0
    if any(k in text for k in ["high", "significant", "worried", "serious", "danger"]):
        return 4.0
    if any(k in text for k in ["moderate", "medium", "concern", "some level", "intermediate"]):
        return 3.0
    if any(k in text for k in ["low", "minor", "slight", "unlikely", "not very"]):
        return 2.0
    if any(k in text for k in ["very low", "negligible", "none", "no concern", "minimal"]):
        return 1.0
        
    return 3.0 # Default baseline

def run_heuristic_audit(log_path):
    path = Path(log_path)
    if not path.exists():
        return
    
    df = pd.read_csv(path)
    
    # Apply heuristic scoring
    df["shadow_threat_score"] = df["threat_appraisal"].apply(heuristic_score)
    df["shadow_coping_score"] = df["coping_appraisal"].apply(heuristic_score)
    
    # Save as shadow log
    out_path = path.parent / "simulation_log_shadow.csv"
    df.to_csv(out_path, index=False)
    print(f"Heuristic audit saved to {out_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=str, required=True)
    args = parser.parse_args()
    run_heuristic_audit(args.log)
