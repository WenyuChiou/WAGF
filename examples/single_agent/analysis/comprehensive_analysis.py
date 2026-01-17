
import pandas as pd
import json
import os
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import sys
import os

# Add project root to sys.path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from validators.agent_validator import AgentValidator

# Constants
script_dir = Path(__file__).parent
# Interim Analysis: Filtering for available models as requested
MODELS = ["llama3_2_3b", "gemma3_4b", "deepseek-r1_8b"] 
GROUPS = {
    "A_Control": {"path": script_dir.parent / "results" / "old_results", "suffix": ""},
    "B_Governance": {"path": script_dir.parent / "results" / "JOH_FINAL", "suffix": "_Group_B"},
    "C_Enhancement": {"path": script_dir.parent / "results" / "JOH_FINAL", "suffix": "_Group_C"}
}

# Map normalized model ID to folder names
OLD_RESULTS_MAP = {
    "llama3_2_3b": "Llama_3.2_3B",
    "gemma3_4b": "Gemma_3_4B",
    "deepseek-r1_8b": "DeepSeek_R1_8B",
    "gpt-oss": "GPT-OSS_20B"
}

# --- Post-Hoc Audit Helpers ---
def extract_label(text):
    text = str(text).lower()
    if "very high" in text or "extreme" in text: return "VH"
    if "high" in text or "significant" in text or "severe" in text: return "H"
    if "moderate" in text or "medium" in text: return "M"
    if "low" in text or "slight" in text or "minimal" in text: return "L"
    if "very low" in text or "no threat" in text or "none" in text: return "VL"
    return "M"

def map_decision(legacy_decision):
    if pd.isna(legacy_decision): return "do_nothing"
    text = str(legacy_decision)
    mapping = {
        "Do Nothing": "do_nothing", 
        "Relocate": "relocate",
        "Only Flood Insurance": "buy_insurance",
        "Only House Elevation": "elevate_house",
        "Both Flood Insurance and House Elevation": "elevate_house",
        "Elevate the house": "elevate_house",
        "Buy flood insurance": "buy_insurance"
    }
    return mapping.get(text, text.lower().replace(" ", "_"))

def run_post_hoc_audit(df, config_path):
    """Run validator on a dataframe of decisions."""
    os.environ["GOVERNANCE_PROFILE"] = "strict"
    validator = AgentValidator(str(config_path))
    violations = 0
    total = 0
    
    for idx, row in df.iterrows():
        total += 1
        threat = extract_label(row.get('threat_appraisal', ''))
        coping = extract_label(row.get('coping_appraisal', ''))
        action_text = row.get('raw_llm_decision', row.get('decision', 'do_nothing'))
        decision = map_decision(action_text)
        
        state = {
            "elevated": row.get('elevated', False),
            "has_insurance": row.get('has_insurance', False),
            "relocated": row.get('relocated', False)
        }
        reasoning = {"TP_LABEL": threat, "CP_LABEL": coping}
        
        # Validate Thinking Check
        results = validator.validate_thinking("household", f"Agent_{idx}", decision, state, reasoning)
        if any(not r.valid for r in results):
            violations += 1
            
    return violations, total

def load_metrics(base_path, model_name, suffix):
    """Load simulation log and governance summary for a specific run."""
    
    # Handle Group A special naming approach
    if "old_results" in str(base_path):
        folder_name = OLD_RESULTS_MAP.get(model_name, model_name)
        run_dir = Path(base_path) / folder_name
    else:
        # Structure: JOH_FINAL/{model_name}/{group_subfolder}
        model_root = Path(base_path) / model_name
        if not model_root.exists():
            print(f"Warning: Model root not found: {model_root}")
            return None
        
        # Find subfolder matching the suffix (which is now a search string like "Group_B")
        run_dir = None
        for sub in model_root.iterdir():
            if sub.is_dir() and suffix in sub.name:
                run_dir = sub
                break
        
    if not run_dir or not run_dir.exists():
        print(f"Warning: Directory not found: {run_dir if run_dir else f'matching {suffix} in {model_name}'}")
        return None

    # Load Logs
    log_path = run_dir / "simulation_log.csv"
    if not log_path.exists():
        log_path = run_dir / "flood_adaptation_simulation_log.csv"
        
    summary_path = run_dir / "governance_summary.json"
    
    metrics = {}
    
    if log_path.exists():
        df = pd.read_csv(log_path)
        # Adaptation Efficiency: % Elevated or Relocated by Year 10
        final_state = df[df['year'] == 10].copy()
        
        # Fill NaNs for safety
        final_state['elevated'] = final_state['elevated'].fillna(False)
        final_state['relocated'] = final_state['relocated'].fillna(False)
        
        # Legacy Fix: If decision says "Already relocated", mark as relocated
        if 'decision' in final_state.columns:
            # Check for strings indicating relocation (case insensitive)
            relocated_mask = final_state['decision'].astype(str).str.contains("relocate", case=False, na=False)
            final_state.loc[relocated_mask, 'relocated'] = True

        adapted = final_state[final_state['elevated'] | final_state['relocated']]
        metrics['adaptation_rate'] = len(adapted) / len(final_state) if len(final_state) > 0 else 0
        metrics['relocation_rate'] = len(final_state[final_state['relocated']]) / len(final_state) if len(final_state) > 0 else 0
    
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            gov = json.load(f)
            # Rationality Score: % of steps NOT blocked
            # We need total steps. Approx Agents * Years.
            total_steps = 100 * 10 
            blocked_steps = gov.get('total_blocking_events', 0)
            metrics['rationality_score'] = (total_steps - blocked_steps) / total_steps
            metrics['hallucination_count'] = blocked_steps
            
            # Extract specific rule failures if available
            # metrics['rule_failures'] = gov.get('rule_stats', {})
            # metrics['rule_failures'] = gov.get('rule_stats', {})
    else:
        # Control group (Group A): Run Post-Hoc Audit to calculate Hypothetical Hallucinations
        if "old_results" in str(base_path) and log_path.exists():
            print(f"Running Post-Hoc Audit for {model_name}...")
            # Locate agent_types.yaml (sibling to runs or in config)
            # Try specific path for single_agent
            config_path = Path("../../agent_types.yaml").resolve()
            if not config_path.exists():
                 # Fallback to project config if local missing
                 config_path = Path("../../../config/agent_types.yaml").resolve()
                
            violations, audited_steps = run_post_hoc_audit(pd.read_csv(log_path), config_path)
            
            metrics['rationality_score'] = (audited_steps - violations) / audited_steps if audited_steps > 0 else 1.0
            metrics['hallucination_count'] = violations
            metrics['audit_type'] = "post_hoc_hypothetical"
        else:
            # Fallback if no log or not Group A
            metrics['rationality_score'] = 1.0 
            metrics['hallucination_count'] = 0
            metrics['audit_type'] = "none"

    return metrics

def generate_report():
    results = []
    
    for model in MODELS:
        for group_name, config in GROUPS.items():
            metrics = load_metrics(config['path'], model, config['suffix'])
            if metrics:
                metrics['model'] = model
                metrics['group'] = group_name
                results.append(metrics)
    
    if not results:
        print("No results found.")
        return

    df_res = pd.DataFrame(results)
    
    print("\n--- Comprehensive Benchmark Summary ---")
    print(df_res.groupby(['model', 'group'])[['adaptation_rate', 'rationality_score']].mean())
    
    # Save to CSV
    df_res.to_csv("benchmark_summary_matrix.csv", index=False)
    print("Saved benchmark_summary_matrix.csv")

if __name__ == "__main__":
    generate_report()
