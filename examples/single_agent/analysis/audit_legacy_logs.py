
import pandas as pd
import sys
import os
from pathlib import Path

# Add project root to sys.path to import broker modules
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

from validators.agent_validator import AgentValidator

def extract_label(text):
    """Simple keyword extraction for legacy natural language."""
    text = str(text).lower()
    if "very high" in text or "extreme" in text: return "VH"
    if "high" in text or "significant" in text or "severe" in text: return "H"
    if "moderate" in text or "medium" in text: return "M"
    if "low" in text or "slight" in text or "minimal" in text: return "L"
    if "very low" in text or "no threat" in text or "none" in text: return "VL"
    return "M" # Default to Medium if ambiguous

def map_decision(legacy_decision):
    """Map legacy decision text to standard skill names if needed."""
    if pd.isna(legacy_decision): return "do_nothing"
    text = str(legacy_decision)
    
    # Legacy: "Do Nothing", "Relocate", "Only Flood Insurance", "Only House Elevation"
    # Current Skills: "do_nothing", "relocate", "buy_insurance", "elevate_house"
    mapping = {
        "Do Nothing": "do_nothing",
        "Relocate": "relocate", 
        "Only Flood Insurance": "buy_insurance",
        "Only House Elevation": "elevate_house",
        "Both Flood Insurance and House Elevation": "elevate_house", # Simplify to elevate
        "Elevate the house": "elevate_house",
        "Buy flood insurance": "buy_insurance"
    }
    return mapping.get(text, text.lower().replace(" ", "_"))

def audit_file(filepath, validator):
    if not filepath.exists():
        print(f"Skipping {filepath} - Not found")
        return None

    df = pd.read_csv(filepath)
    violations = 0
    total = 0
    relocations = 0
    
    # We focus on the ACTION taken this step, derived from raw_llm_decision
    # raw_llm_decision: "Do nothing", "Buy flood insurance", "Relocate", "Elevate the house"
    
    for idx, row in df.iterrows():
        total += 1
        
        # 1. Extract Logic State
        threat = extract_label(row.get('threat_appraisal', ''))
        coping = extract_label(row.get('coping_appraisal', ''))
        
        # 2. Determine Action
        action_text = row.get('raw_llm_decision', 'Do nothing')
        decision = map_decision(action_text)
        
        if decision == "relocate":
            relocations += 1

        # 3. Validation Context
        state = {
            "elevated": row.get('elevated', False),
            "has_insurance": row.get('has_insurance', False),
            "relocated": row.get('relocated', False)
        }
        
        reasoning = {
            "TP_LABEL": threat,
            "CP_LABEL": coping
        }

        # 4. Run Validator (Tier 2: Thinking Rules)
        # We assume agent_type="household" (default)
        results = validator.validate_thinking("household", f"Agent_{idx}", decision, state, reasoning)
        
        # Check validation failures (valid=False)
        is_blocked = any(not r.valid for r in results)
        
        if is_blocked:
            violations += 1
            # Optional: Print first few violations
            pass

    return {"violations": violations, "total": total, "rate": violations/total if total > 0 else 0, "relocations": relocations}

def main():
    # Force strict governance profile
    os.environ["GOVERNANCE_PROFILE"] = "strict"
    
    # Robust path resolution relative to this script
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent / "old_results"
    config_path = script_dir.parent / "agent_types.yaml"
    
    print(f"Loading rules from: {config_path}")
    validator = AgentValidator(str(config_path))
    
    # Analyze multiple models
    models = ["Llama_3.2_3B", "DeepSeek_R1_8B"]
    
    print("--- Legacy Governance Audit (Hypothetical) ---")
    
    # Collect results
    results = {}
    for model in models:
        path = base_dir / model / "flood_adaptation_simulation_log.csv"
        print(f"\nScanning {model}...")
        results[model] = audit_file(path, validator)

    print("\n" + "="*60)
    print(f"{'Model':<20} | {'Decisions':<10} | {'Blocks':<8} | {'Rate':<8} | {'Relocations':<10}")
    print("-" * 60)
    for model, stats in results.items():
        if stats:
            print(f"{model:<20} | {stats['total']:<10} | {stats['violations']:<8} | {stats['rate']:<8.1%} | {stats['relocations']:<10}")
    print("="*60 + "\n")
    
    import json
    with open("audit_results.json", "w") as f:
        json.dump(results, f, indent=4)
    print("Saved results to audit_results.json")

if __name__ == "__main__":
    main()
