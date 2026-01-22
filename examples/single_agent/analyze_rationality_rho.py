
import pandas as pd
from scipy.stats import spearmanr
import numpy as np

def calculate_rho(file_path, group_name):
    print(f"Analyzing {group_name} from: {file_path}")
    try:
        df = pd.read_csv(file_path)
        print(f"Columns in {group_name}: {df.columns.tolist()}")
        
        # Standardize theoretical columns
        if 'Threat' in df.columns:
             df['Threat_Score'] = df['Threat'] # Simple mapping
        elif 'Threat_Appraisal' in df.columns:
             df['Threat_Score'] = df['Threat_Appraisal']
             
        # Map Actions to Quantifiable Intensity
        action_map = {
            "DoNothing": 0,
            "WetProof": 1,
            "DryProof": 2,
            "Elevate": 3,
            "Relocate": 4,
            "BuyInsurance": 1
        }
        
        decision_col = 'Decision' if 'Decision' in df.columns else 'Action'
        if decision_col not in df.columns:
            print(f"Decision column '{decision_col}' not found.")
            return None, None
            
        df['Action_Intensity'] = df[decision_col].map(lambda x: action_map.get(str(x).strip(), 0))
        
        clean_df = df.dropna(subset=['Threat_Score', 'Action_Intensity'])
        
        if len(clean_df) < 5:
            print(f"Not enough data for {group_name}. Len: {len(clean_df)}")
            return None, None
            
        rho, p_value = spearmanr(clean_df['Threat_Score'], clean_df['Action_Intensity'])
        print(f"Rho: {rho}")
        
        return rho, clean_df
        
    except Exception as e:
        print(f"Error analyzing {group_name}: {e}")
        return None, None

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    
    base_path = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\BENCHMARK_2026\deepseek_r1_8b"
    path_a = f"{base_path}\\Group_A\\Run_1\\simulation_log.csv"
    path_b = f"{base_path}\\Group_B\\Run_1\\simulation_log.csv"
    
    rho_a, df_a = calculate_rho(path_a, "Group A")
    rho_b, df_b = calculate_rho(path_b, "Group B")
    
    # Plotting
    if df_a is not None or df_b is not None:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        if df_a is not None:
            axes[0].scatter(df_a['Threat_Score'], df_a['Action_Intensity'], alpha=0.5, c='blue')
            axes[0].set_title(f"Group A (Control): Rho = {rho_a:.3f}")
            axes[0].set_xlabel("Internal Threat Appraisal")
            axes[0].set_ylabel("Action Intensity (0-4)")
            
        if df_b is not None:
            axes[1].scatter(df_b['Threat_Score'], df_b['Action_Intensity'], alpha=0.5, c='red')
            axes[1].set_title(f"Group B (Governed): Rho = {rho_b:.3f}")
            axes[1].set_xlabel("Internal Threat Appraisal")
            
        plt.tight_layout()
        plt.savefig("rationality_rho_comparison.png")
        print("Saved plot to rationality_rho_comparison.png")

if __name__ == "__main__":
    base_path = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\BENCHMARK_2026\deepseek_r1_8b"
    
    path_a = f"{base_path}\\Group_A\\Run_1\\simulation_log.csv"
    path_b = f"{base_path}\\Group_B\\Run_1\\simulation_log.csv"
    
    print("="*60)
    print("RATIONALITY ALIGNMENT (RHO) ANALYSIS")
    print("Definition: Correlation between Threat Appraisal and Action Intensity")
    print("Hypothesis: Group A (Rho ~ 0) vs Group B (Rho ~ ?)")
    print("="*60)
    
    rho_a = calculate_rho(path_a, "Group A (Control)")
    print("-" * 30)
    rho_b = calculate_rho(path_b, "Group B (Governed)")
    
    print("\n" + "="*60)
    print(f"{'METRIC':<20} | {'GROUP A':<15} | {'GROUP B':<15}")
    print("-" * 60)
    print(f"{'Rho (Rationality)':<20} | {str(rho_a) if rho_a else 'N/A':<15} | {str(rho_b) if rho_b else 'N/A':<15}")
    print("="*60)
