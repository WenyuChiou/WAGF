
import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency
import matplotlib.pyplot as plt
import os
import json

def analyze_model_results(results_dir):
    all_stats = {}
    
    for model_dir in os.listdir(results_dir):
        path = os.path.join(results_dir, model_dir)
        if not os.path.isdir(path): continue
        
        log_file = os.path.join(path, "simulation_log.csv")
        audit_file = os.path.join(path, "household_governance_audit.csv")
        
        if not os.path.isfile(log_file) or not os.path.isfile(audit_file): 
            continue
        
        # Log: agent_id, year, relocated, ...
        # Audit: step_id, agent_id, final_skill, ...
        
        log_df = pd.read_csv(log_file)
        audit_df = pd.read_csv(audit_file)
        
        model_name = model_dir.replace("_strict", "")
        steps = sorted(audit_df['step_id'].unique())
        
        active_adaptation = []
        
        for step in steps:
            # For each step, find who was relocated in the PREVIOUS step
            # Step 1 decision is made when year is 0 (or at the start)
            # Actually, let's look at log_df where year == step - 1 or something
            # If log_df has 'year', and 'relocated' is the state AFTER the step
            
            # Simplified: Find agents who have relocated=True in the log for this year
            # Wait, if relocated is state after decision, we should look at previous year
            
            if step == 1:
                relocated_already = set()
            else:
                relocated_already = set(log_df[(log_df['year'] < step) & (log_df['relocated'] == True)]['agent_id'].unique())
            
            # Filter audit for active agents
            step_active = audit_df[(audit_df['step_id'] == step) & (~audit_df['agent_id'].isin(relocated_already))]
            
            # Exclude technical failures if any
            step_active = step_active[step_active['status'] == 'APPROVED']
            
            decisions = step_active['final_skill'].value_counts().to_dict()
            
            active_adaptation.append({
                "step": int(step),
                "total_active": len(step_active),
                "decisions": decisions
            })
            
        all_stats[model_name] = active_adaptation

    return all_stats

def run_chi_square(all_stats):
    models = list(all_stats.keys())
    if len(models) < 2: 
        print("Not enough models for Chi-Square.")
        return
    
    print("\n=== Chi-Square Test (Adaptation vs Do Nothing) ===")
    
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            m1, m2 = models[i], models[j]
            
            def get_counts(m_stats):
                adapt = 0
                dn = 0
                for s in m_stats:
                    d = s['decisions']
                    dn += d.get('do_nothing', 0)
                    # Anything else is adaptation
                    for k, v in d.items():
                        if k != 'do_nothing':
                            adapt += v
                return [adapt, dn]
                
            c1 = get_counts(all_stats[m1])
            c2 = get_counts(all_stats[m2])
            
            if sum(c1) == 0 or sum(c2) == 0: continue
            
            contingency = [c1, c2]
            try:
                chi2, p, dof, expected = chi2_contingency(contingency)
                print(f"{m1:20} vs {m2:20}: p-value = {p:8.4f} ({'Significant' if p < 0.05 else 'Not Significant'})")
            except Exception as e:
                print(f"Error running Chi2 for {m1} vs {m2}: {e}")

def generate_report(all_stats):
    print("\n=== Descriptive Statistics (Adaptation Rate per Step) ===")
    for model, stats in all_stats.items():
        print(f"\nModel: {model}")
        for s in stats:
            total = s['total_active']
            if total == 0: continue
            dn = s['decisions'].get('do_nothing', 0)
            adapt = total - dn
            rate = adapt / total
            print(f"  Step {s['step']}: Active={total:3}, Adapt={adapt:3}, Rate={rate:6.1%}, Details={s['decisions']}")

def generate_plots(all_stats):
    if not all_stats: return
    plt.figure(figsize=(10, 6))
    
    for model, stats in all_stats.items():
        years = [s['step'] for s in stats]
        rates = []
        for s in stats:
            total = s['total_active']
            if total == 0: 
                rates.append(0)
                continue
            adapted = total - s['decisions'].get('do_nothing', 0)
            rates.append(adapted / total)
            
        plt.plot(years, rates, marker='o', label=model)
        
    plt.title("Annual Adaptation Rate (Excluding Relocated Agents)")
    plt.xlabel("Simulation Year")
    plt.ylabel("Adaptation Proportion (Active Population)")
    plt.ylim(0, 1.05)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.savefig("adaptation_trends_refined.png")
    print("\nPlot saved as adaptation_trends_refined.png")

if __name__ == "__main__":
    results_path = "results_window"
    if os.path.exists(results_path):
        stats = analyze_model_results(results_path)
        generate_report(stats)
        run_chi_square(stats)
        generate_plots(stats)
        with open("analysis_summary.json", "w") as f:
            json.dump(stats, f, indent=2)
    else:
        print(f"Directory {results_path} not found.")
