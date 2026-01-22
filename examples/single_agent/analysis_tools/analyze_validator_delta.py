import pandas as pd
from pathlib import Path

# Paths
RESULTS_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
OUTPUT_DIR = Path(r"C:\Users\wenyu\.gemini\antigravity\brain\0eefc59d-202e-4d45-bd10-0806e60c7837")

MODELS = {
    'llama3_2_3b': 'Llama 3.2 (3B)',
    'gemma3_4b': 'Gemma 2 (9B)'
}

GROUPS = ['Group_B', 'Group_C']

def analyze_before_after():
    all_deltas = []
    
    for model_folder, model_label in MODELS.items():
        for group_folder in GROUPS:
            # Find all runs
            group_path = RESULTS_DIR / model_folder / group_folder
            if not group_path.exists(): continue
            
            runs = [d for d in group_path.iterdir() if d.is_dir()]
            for run_dir in runs:
                audit_file = list(run_dir.rglob("household_governance_audit.csv"))
                sim_log_file = run_dir / "simulation_log.csv"
                
                if not audit_file or not sim_log_file.exists(): continue
                
                try:
                    # 1. Load Audit
                    audit_df = pd.read_csv(audit_file[0], on_bad_lines='skip')
                    # Filter for corrections/rejections
                    rejections = audit_df[audit_df['status'] == 'REJECTED'].copy()
                    if rejections.empty: continue
                    
                    # Fix missing 'year' using step_id
                    if 'year' not in rejections.columns or rejections['year'].isnull().all():
                        rejections['year'] = (rejections['step_id'] // 100) + 1
                    
                    # 2. Load Simulation Log
                    sim_df = pd.read_csv(sim_log_file)
                    
                    merged = pd.merge(
                        rejections[['agent_id', 'year', 'proposed_skill', 'status', 'failed_rules']],
                        sim_df[['agent_id', 'year', 'yearly_decision']],
                        on=['agent_id', 'year'],
                        how='inner'
                    )
                    
                    if not merged.empty:
                        merged.rename(columns={'yearly_decision': 'executed_decision'}, inplace=True)
                        merged['Model'] = model_label
                        merged['Group'] = group_folder
                        merged['Run'] = run_dir.name
                        all_deltas.append(merged)
                except Exception as e:
                    print(f"Error in {run_dir}: {e}")
                    
    if not all_deltas:
        print("No paired intervention data found.")
        return
        
    final_df = pd.concat(all_deltas)
    
    # Analyze the mapping
    # Proposed -> Executed
    mapping = final_df.groupby(['Model', 'Group', 'proposed_skill', 'executed_decision']).size().reset_index(name='count')
    
    output_csv = OUTPUT_DIR / "validator_action_redirection.csv"
    mapping.to_csv(output_csv, index=False)
    
    print("--- Validator Redirection Analysis (Proposed -> Executed) ---")
    print(mapping)
    print(f"\nSaved results to {output_csv}")

if __name__ == "__main__":
    analyze_before_after()
