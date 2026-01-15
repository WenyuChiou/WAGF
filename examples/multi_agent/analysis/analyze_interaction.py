import pandas as pd
import json
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import numpy as np

def analyze_ma_results(output_path: str):
    output_dir = Path(output_path)
    # 1. Load Simulation Log (Institutional States)
    sim_log_path = output_dir / "simulation_log.csv"
    if not sim_log_path.exists():
        print(f"Error: {sim_log_path} not found.")
        return
    
    df_sim = pd.read_csv(sim_log_path)
    
    # 2. Load Household Traces (Cognitive States)
    trace_files = list(output_dir.glob("**/household_owner_traces.jsonl"))
    if not trace_files:
        print("Warning: No household_owner_traces.jsonl found. checking deeper...")
        trace_files = list(output_dir.glob("**/*/raw/household_owner_traces.jsonl"))
    
    if not trace_files:
        print("Error: No trace files found.")
        return
    
    all_traces = []
    for f in trace_files:
        with open(f, 'r', encoding='utf-8') as fh:
            for line in fh:
                all_traces.append(json.loads(line))
    
    df_traces = pd.DataFrame(all_traces)
    
    # Map appraisals to numeric
    label_map = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
    def get_appraisal(row, key):
        if not isinstance(row, dict): return np.nan
        val = row.get(key)
        if isinstance(val, dict): val = val.get("label")
        return label_map.get(val, np.nan)

    if "skill_proposal" in df_traces.columns:
        df_traces["tp_score"] = df_traces["skill_proposal"].apply(lambda x: get_appraisal(x, "threat_appraisal"))
        df_traces["cp_score"] = df_traces["skill_proposal"].apply(lambda x: get_appraisal(x, "coping_appraisal"))
    
    # Aggregate by Year
    yearly_cognitive = df_traces.groupby("step_id")[["tp_score", "cp_score"]].mean().reset_index()
    yearly_cognitive.rename(columns={"step_id": "Year"}, inplace=True)
    
    # 3. Plotting
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    # Panel 1: Institutional Policies
    ax1.plot(df_sim["Year"], df_sim["subsidy_rate"], 'b-o', label="Subsidy Rate")
    ax1_twin = ax1.twinx()
    ax1_twin.plot(df_sim["Year"], df_sim["premium_rate"], 'r-s', label="Premium Rate")
    ax1.set_ylabel("Subsidy Rate", color='b')
    ax1_twin.set_ylabel("Premium Rate", color='r')
    ax1.set_title("Institutional Policy Dynamics (SQ3)")
    ax1.grid(True, alpha=0.3)
    
    # Panel 2: Community Response
    if not yearly_cognitive.empty:
        ax2.plot(yearly_cognitive["Year"], yearly_cognitive["tp_score"], 'orange', label="Avg Threat Appraisal")
        ax2.plot(yearly_cognitive["Year"], yearly_cognitive["cp_score"], 'green', label="Avg Coping Appraisal")
        ax2.set_ylabel("Cognitive Score (1-5)")
        ax2.set_ylim(0, 6)
        ax2.legend(loc="upper left")
    
    ax2_twin = ax2.twinx()
    # Calculate elevation percentage from sim_log if available (or use placeholders)
    # Note: sim_log might not have elevated_count if we didn't add it to CSV logging yet
    # We can infer it from traces by checking decisions
    if "approved_skill" in df_traces.columns:
        df_traces["is_elevated"] = df_traces["approved_skill"].apply(lambda x: 1 if x and x.get("skill_name") == "elevate_house" else 0)
        cum_elevated = df_traces.groupby("step_id")["is_elevated"].sum().cumsum()
        ax2_twin.bar(cum_elevated.index, cum_elevated.values, alpha=0.2, label="Cumulative Elevations", color='gray')
        ax2_twin.set_ylabel("Elevation Count")

    ax2.set_title("Community Perception & Adaptation (SQ2/SQ3)")
    ax2.set_xlabel("Year")
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plot_path = output_dir / "ma_interaction_summary.png"
    plt.savefig(plot_path)
    print(f"Success: Chart saved to {plot_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()
    analyze_ma_results(args.output)
