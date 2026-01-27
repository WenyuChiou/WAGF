import pandas as pd
from pathlib import Path

# Paths
RESULTS_DIR = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")
OUTPUT_DIR = Path(r"C:\Users\wenyu\.gemini\antigravity\brain\0eefc59d-202e-4d45-bd10-0806e60c7837")

MODELS = {
    'llama3_2_3b': 'Llama 3.2 (3B)',
    'gemma3_4b': 'Gemma 2 (9B)'
}

def analyze_intervention_delta():
    summary_data = []
    
    for model_folder, model_label in MODELS.items():
        # Check Group B (highest interventions)
        # Search for audit files in any Run
        audit_files = list((RESULTS_DIR / model_folder / "Group_B").rglob("household_governance_audit.csv"))
        
        for f in audit_files:
            try:
                # Use chunking if file is huge, but 400KB is fine
                df = pd.read_csv(f)
                
                # We care about rows where validated is False or failed_rules is not empty
                # Or simply where proposed != final
                interventions = df[df['proposed_skill'] != df['final_skill']].copy()
                
                if not interventions.empty:
                    # Count transitions
                    counts = interventions.groupby(['proposed_skill', 'final_skill']).size().reset_index(name='count')
                    counts['Model'] = model_label
                    counts['Run'] = f.parent.name
                    summary_data.append(counts)
            except Exception as e:
                print(f"Error processing {f}: {e}")
                
    if not summary_data:
        print("No interventions found in audit logs.")
        return
        
    all_interventions = pd.concat(summary_data)
    
    # Pivot for a clean view
    pivot = all_interventions.groupby(['Model', 'proposed_skill', 'final_skill'])['count'].sum().unstack(fill_value=0)
    
    output_path = OUTPUT_DIR / "validator_intervention_analysis.csv"
    pivot.to_csv(output_path)
    print(pivot)
    print(f"Analysis saved to {output_path}")

if __name__ == "__main__":
    analyze_intervention_delta()
