"""
Shadow Audit Script for Group A (Naive) Analysis
================================================

This script performs "Post-Hoc Rationality Quantization" on Group A's unstructured simulation logs.
Since Group A (Naive LLM) outputs free-text appraisals (e.g., "I am worried..."), we cannot directly 
compare it with Group B/C's structured ratings (1-5).

Methodology:
1. Load `simulation_log.csv` from Group A results.
2. Identify rows where `threat_appraisal` or `coping_appraisal` are non-numeric.
3. Use a fast LLM (gemma:2b or similar) as a "Shadow Auditor" to score the text.
4. Save the enhanced log as `simulation_log_shadow.csv`.

Metrics Generated:
- `shadow_threat_score`: 1 (Very Low) to 5 (Very High)
- `shadow_coping_score`: 1 (Very Low) to 5 (Very High)
- `shadow_confidence`: LLM's confidence in its rating.
"""

import pandas as pd
import argparse
from pathlib import Path
from tqdm import tqdm
import json
import re

# Import Broker LLM Utils for consistent API usage
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent)) # Add project root
from broker.utils.llm_utils import create_legacy_invoke

def parse_score(llm_output: str) -> dict:
    """Extract JSON score from LLM output."""
    try:
        # Try to find JSON block
        match = re.search(r"\{.*\}", llm_output, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        # Fallback: finding numbers
        return {"score": 3, "confidence": 0.1, "reason": "Parse Error"}
    except:
        return {"score": 3, "confidence": 0.0, "reason": "Exception"}

def run_shadow_audit(log_path: str, model: str = "gemma2:2b", workers: int = 4):
    print(f"--- Shadow Audit: Quantifying Group A Logs ---")
    print(f"Target: {log_path}")
    print(f"Auditor Model: {model}")
    
    path = Path(log_path)
    if not path.exists():
        print(f"Error: File not found {path}")
        return

    df = pd.read_csv(path)
    print(f"Loaded {len(df)} rows.")

    # Check if already audited
    if "shadow_threat_score" in df.columns:
        print("Audit columns already exist (skipping).")
        # return # Optional: Allow overwrite
    
    # Initialize Auditor
    llm_invoke = create_legacy_invoke(model_name=model)
    
    # We only audit rows where appraisal is NOT already a valid VL/L/M/H label
    # Actually, Group A output is usually a full sentence.
    # Group B output is usually "M" or "H".
    
    valid_labels = ["VL", "L", "M", "H", "VH"]
    
    # Define scoring prompts
    def get_prompt(text, type_="threat"):
        if type_ == "threat":
            return (
                f"You are a psychological coder. Read this internal monologue about flood risk: \"{text}\"\n"
                "Rate the PERCEIVED THREAT level on a scale of 1 (Very Low) to 5 (Very High).\n"
                "Return EXACT JSON format: {\"score\": <int 1-5>, \"reason\": \"<brief>\"}"
            )
        else:
             return (
                f"You are a psychological coder. Read this internal monologue about coping capacity: \"{text}\"\n"
                "Rate the SELF-EFFICACY (Coping) level on a scale of 1 (Very Low) to 5 (Very High).\n"
                "Return EXACT JSON format: {\"score\": <int 1-5>, \"reason\": \"<brief>\"}"
            )

    # Iterate and Score (This is slow, so we focus on a subset if needed, but for precision we do all)
    # Optimization: Batching? For now, simple loop with TQDM.
    
    shadow_threats = []
    shadow_copings = []
    
    print("Auditing Appraisals...")
    
    # Filter rows that need auditing (ignore if they look like standard labels)
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        # 1. Threat Audit
        t_raw = str(row.get("threat_appraisal", ""))
        if t_raw in valid_labels:
            # Map standard labels directly
            mapping = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
            shadow_threats.append(mapping.get(t_raw, 3))
        elif len(t_raw) < 2 or t_raw == "nan" or t_raw == "N/A":
             shadow_threats.append(None) # No data
        else:
            # Call LLM
            res = llm_invoke(get_prompt(t_raw, "threat"))
            parsed = parse_score(res)
            shadow_threats.append(parsed.get("score", 3))

        # 2. Coping Audit
        c_raw = str(row.get("coping_appraisal", ""))
        if c_raw in valid_labels:
             mapping = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
             shadow_copings.append(mapping.get(c_raw, 3))
        elif len(c_raw) < 2 or c_raw == "nan" or c_raw == "N/A":
             shadow_copings.append(None)
        else:
            res = llm_invoke(get_prompt(c_raw, "coping"))
            parsed = parse_score(res)
            shadow_copings.append(parsed.get("score", 3))
            
    df["shadow_threat_score"] = shadow_threats
    df["shadow_coping_score"] = shadow_copings
    
    # Save
    out_path = path.parent / "simulation_log_shadow.csv"
    df.to_csv(out_path, index=False)
    print(f"Shadow Audit Complete. Saved to {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=str, required=True, help="Path to input simulation_log.csv")
    parser.add_argument("--model", type=str, default="gemma2:2b", help="Model for auditing")
    args = parser.parse_args()
    
    run_shadow_audit(args.log, args.model)
