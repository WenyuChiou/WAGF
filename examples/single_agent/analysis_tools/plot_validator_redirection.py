import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Paths
OUTPUT_DIR = Path(r"C:\Users\wenyu\.gemini\antigravity\brain\0eefc59d-202e-4d45-bd10-0806e60c7837")
DATA_FILE = OUTPUT_DIR / "validator_action_redirection.csv"

def plot_intervention_delta():
    if not DATA_FILE.exists():
        print("Data file not found.")
        return
        
    df = pd.read_csv(DATA_FILE)
    # Focus on Llama Group B (highest intervention depth)
    llama_b = df[(df['Model'] == 'Llama 3.2 (3B)') & (df['Group'] == 'Group_B')].copy()
    
    if llama_b.empty:
        print("No llama interventions found.")
        return

    # Pivot for plotting: Proposed Skill vs Executed Decision
    pivot = llama_b.pivot(index='proposed_skill', columns='executed_decision', values='count').fillna(0)
    
    # We want to see "For each proposal, what was the outcome?"
    plt.figure(figsize=(10, 6))
    pivot.plot(kind='bar', stacked=True, color=['#118AB2', '#FFD166', '#06D6A0', '#EF476F'], ax=plt.gca())
    
    plt.title("Llama 3.2 (3B) Behavioral Redirection: Proposal → Execution", fontsize=16, fontweight='bold')
    plt.xlabel("Original LLM Intent (Proposed)", fontsize=12)
    plt.ylabel("Count of Interventions", fontsize=12)
    plt.xticks(rotation=0)
    plt.legend(title="Actual Decision (After Validator)", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    output_path = OUTPUT_DIR / "llama_validator_redirection.png"
    plt.savefig(output_path, dpi=200)
    print(f"Redirection plot saved to {output_path}")

if __name__ == "__main__":
    plot_intervention_delta()
