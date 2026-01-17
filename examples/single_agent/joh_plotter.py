import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
from pathlib import Path
import glob
import os
import time
import sys
from datetime import datetime

# Set Academic Style
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'

def load_rationality_data(root_dirs):
    """
    Scans directories for audit_summary.json to compute Rationality Score (RS).
    RS = (Total Decisions - Interventions) / Total Decisions
    """
    data = []
    
    for root in root_dirs:
        # Recursive search for audit_summary.json
        files = glob.glob(os.path.join(root, "**", "audit_summary.json"), recursive=True)
        
        for p in files:
            path = Path(p)
            try:
                with open(path, 'r') as f:
                    summary = json.load(f)
                
                # Infer Model and Group from specific path structure
                model = "Unknown"
                if "llama" in str(path).lower(): model = "Llama 3.2"
                elif "gemma" in str(path).lower(): model = "Gemma 3"
                elif "gpt" in str(path).lower(): model = "GPT-OSS"
                elif "deepseek" in str(path).lower(): model = "DeepSeek-R1"
                
                group = "Group A (Baseline)"
                if "Group_B" in str(path): group = "Group B (Window)"
                if "Group_C" in str(path): group = "Group C (Reflection)"
                if "old_results" in str(path) or "STRESS" in str(path): group = "Group A (Baseline)"

                total = summary.get("total_evaluations", 0)
                blocked = summary.get("total_blocking_events", 0)
                
                if total > 0:
                    rs = (total - blocked) / total
                    data.append({
                        "Model": model,
                        "Group": group,
                        "Rationality Score": rs,
                        "Interventions": blocked
                    })
            except Exception as e:
                # print(f"Skipping {path}: {e}")
                pass
                
    return pd.DataFrame(data)

def load_adaptation_data(root_dirs):
    """
    Scans for simulation_log.csv to compute Adaptation Density over time.
    """
    all_dfs = []
    
    for root in root_dirs:
        # Priority 1: Check for interim CSVs (Active Runs)
        interim_files = glob.glob(os.path.join(root, "**", "interim_*.csv"), recursive=True)
        # Priority 2: Check for final CSVs
        final_files = glob.glob(os.path.join(root, "**", "simulation_log.csv"), recursive=True)
        
        files = interim_files + final_files
        
        for p in files:
            try:
                df = pd.read_csv(p)
                path = str(p)
                
                model = "Unknown"
                if "llama" in path.lower(): model = "Llama 3.2"
                elif "gemma" in path.lower(): model = "Gemma 3"
                elif "gpt" in path.lower(): model = "GPT-OSS"
                elif "deepseek" in path.lower(): model = "DeepSeek-R1"
                
                group = "Baseline"
                if "Group_B" in path: group = "Group B (Window)"
                if "Group_C" in path: group = "Group C (Reflection)"
                
                yearly = df.groupby('year').apply(
                    lambda x: pd.Series({
                        'Adaptation Rate': len(x[
                            (x['elevated']==True) | 
                            (x['has_insurance']==True) | 
                            (x['relocated']==True)
                        ]) / len(x)
                    })
                ).reset_index()
                
                yearly['Model'] = model
                yearly['Group'] = group
                all_dfs.append(yearly)
                
            except Exception as e:
                pass 
                
    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs)

def plot_rationality(df, output_path="figure_2_rationality.png"):
    if df.empty:
        # print("No data for Rationality Plot.")
        return

    plt.figure(figsize=(10, 6))
    ax = sns.barplot(
        data=df, 
        x="Model", 
        y="Rationality Score", 
        hue="Group", 
        palette="gray", 
        capsize=.1,
        edgecolor="black"
    )
    plt.ylim(0, 1.05)
    plt.title("Constraint Adherence by Model & Architecture", fontsize=14, fontweight='bold')
    plt.ylabel("Rationality Score")
    plt.xlabel("")
    plt.legend(title="Cognitive Architecture", loc='lower right')
    for container in ax.containers:
        ax.bar_label(container, fmt='%.2f', padding=3)
    # print(f"Saving {output_path}...")
    plt.savefig(output_path)
    plt.close()

def plot_adaptation(df, output_path="figure_3_adaptation.png"):
    if df.empty:
        # print("No data for Adaptation Plot.")
        return

    plt.figure(figsize=(12, 6))
    sns.lineplot(
        data=df,
        x="year",
        y="Adaptation Rate",
        hue="Model",
        style="Group",
        markers=True,
        dashes=True,
        linewidth=2.5,
        palette="viridis"
    )
    plt.ylim(0, 1.0)
    plt.xlim(1, 10)
    plt.title("Long-Term Adaptation Density (10-Year Simulation)", fontsize=14, fontweight='bold')
    plt.ylabel("Population Adapted (%)")
    plt.xlabel("Simulation Year")
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)
    # print(f"Saving {output_path}...")
    plt.savefig(output_path)
    plt.close()

# --- REAL-TIME MONITOR ---
class SimulationMonitor:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.file_cursors = {} # path -> file pointer position
        self.agent_states = {} # model_group -> {agent_id -> state_dict}

    def process_trace_file(self, path):
        path_obj = Path(path)
        
        # Identify Model/Group
        # Path: .../results/JOH_FINAL/llama3_2_3b/Group_B_Governance_Window/...
        parts = path_obj.parts
        
        model = "Unknown"
        if "llama" in str(path).lower(): model = "Llama 3.2"
        elif "gemma" in str(path).lower(): model = "Gemma 3"
        elif "gpt" in str(path).lower(): model = "GPT-OSS"
        elif "deepseek" in str(path).lower(): model = "DeepSeek-R1"
        
        group = "Unknown"
        if "Group_B" in str(path): group = "Window (Group B)"
        elif "Group_C" in str(path): group = "Reflection (Group C)"
        
        key = f"{model} - {group}"
        if key not in self.agent_states:
            self.agent_states[key] = {}

        new_data = False
        latest_record = None

        if path not in self.file_cursors:
            self.file_cursors[path] = 0

        try:
            with open(path, 'r') as f:
                f.seek(self.file_cursors[path])
                lines = f.readlines()
                self.file_cursors[path] = f.tell()
                
                for line in lines:
                    try:
                        data = json.loads(line)
                        agent_id = data.get('agent_id')
                        step = data.get('step_id')
                        
                        if agent_id:
                            if agent_id not in self.agent_states[key]:
                                self.agent_states[key][agent_id] = {
                                    "elevated": False, "relocated": False, "has_insurance": False
                                }
                            
                            st = self.agent_states[key][agent_id]
                            
                            # Update from state_changes
                            changes = data.get('execution_result', {}).get('state_changes', {})
                            if changes:
                                for k, v in changes.items():
                                    st[k] = v
                            
                            latest_record = data
                            new_data = True
                    except:
                        pass
        except Exception as e:
            pass
            
        return key, latest_record if new_data else None

    def print_status(self):
        # Find all trace files
        trace_files = glob.glob(os.path.join(self.root_dir, "**", "household_traces.jsonl"), recursive=True)
        
        updates = []
        for tf in trace_files:
            k, data = self.process_trace_file(tf)
            if data:
                outcome = data.get('outcome')
                skill = data.get('approved_skill', {})
                decision = skill.get('skill_name') if skill else "Unknown"
                agent = data.get('agent_id')
                updates.append(f"[{k}] {agent} -> {decision} ({outcome})")
        
        # Only print if something happened or periodically
        if updates:
            print(f"\n[Latest Activity at {datetime.now().strftime('%H:%M:%S')}]")
            for u in updates[-3:]: # Show last 3
                print(u)
        
        # Periodic Summary Table (every time function called implies loop)
        # To avoid spam, we can print table only if updates existed
        if updates:
            print(f"\n{'Model Group':<40} | {'Agents':<8} | {'Elevated':<8} | {'Relocated':<9}")
            print("-" * 75)
            
            # Sort keys for consistent display
            for key in sorted(self.agent_states.keys()):
                agents = self.agent_states[key]
                active_count = len(agents)
                n_elev = sum(1 for a in agents.values() if a['elevated'])
                n_reloc = sum(1 for a in agents.values() if a['relocated'])
                print(f"{key:<40} | {active_count:<8} | {n_elev:<8} | {n_reloc:<9}")

if __name__ == "__main__":
    target_dirs = ["results/JOH_FINAL", "results/JOH_STRESS"]
    monitor = SimulationMonitor("results/JOH_FINAL")
    
    print("--- JOH Live Monitor & Plotter ---")
    print("Tracking 8 concurrent simulations...")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            # 1. Update Monitor
            monitor.print_status()
            
            # 2. Update Plots silently
            df_rs = load_rationality_data(target_dirs)
            df_ad = load_adaptation_data(target_dirs)
            
            if not df_ad.empty:
                plot_adaptation(df_ad)
            
            if not df_rs.empty:
                plot_rationality(df_rs)
            
            time.sleep(5) 
            
    except KeyboardInterrupt:
        print("\nStopped.")
