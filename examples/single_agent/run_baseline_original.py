# -*- coding: utf-8 -*-
# =============================================================================
# run_baseline_original.py - Long-term Flood Adaptation with LLM via Ollama
# (Modified from LLMABMPMT-Final.py to support CLI arguments for Benchmarking)
# =============================================================================
# Original Author: Dr. Y. C. Ethan Yang @ Lehigh University
# =============================================================================

import pandas as pd  # For handling tabular data
import random  # For randomness in agent attributes and flood events
import time  # To track simulation runtime
import os # For checking if files exist
from pathlib import Path
from langchain_ollama import OllamaLLM  # LangChain wrapper to call Ollama LLM
from langchain_core.prompts import PromptTemplate  # For formatting LLM prompts
from tqdm import tqdm  # Progress bar for loops
import matplotlib.pyplot as plt  # For plotting 
import numpy as np # For plotting
import argparse

# --- 1. Set simulation parameters ---
NUM_AGENTS = 100                    # Number of agents in the simulation
NUM_YEARS = 10                      # Number of simulation years
NUM_SAMPLED_AGENTS = 5              # Number of agents to select for prompts and plots
NUM_SAMPLED_YEARS = 3               # Number of years to sample for prompts
BATCH_SIZE = 25                     # Max number of prompts to send to the LLM in one batch
MAX_RETRIES = 3                     # Number of times to retry a failed LLM batch
RETRY_DELAY_SECONDS = 5             # Seconds to wait between retries
FLOOD_PROBABILITY = 0.2             # 20% chance of a flood event in any given year
GRANT_PROBABILITY = 0.5             # 50% chance of an elevation grant being available
RANDOM_MEMORY_RECALL_CHANCE = 0.2   # 20% chance to recall a random past event each year
MEMORY_WINDOW = 5                   # Number of recent memories an agent retains 

# --- Verbalize Trust Function---
def verbalize_trust(value, category="insurance"):
    """Converts a float (0-1) into a natural language description."""
    if category == "insurance":
        if value >= 0.8:
            return "strongly trust"
        elif value >= 0.5:
            return "moderately trust"
        elif value >= 0.2:
            return "have slight doubts about"
        else:
            return "deeply distrust"
    
    elif category == "neighbors":
        if value >= 0.8:
            return "highly rely on"
        elif value >= 0.5:
            return "generally trust"
        elif value >= 0.2:
            return "are skeptical of"
        else:
            return "completely ignore"
    return "trust"

# --- 2. Initialize the agents with random attributes and memory ---
def initialize_agents_randomly(past_events):
    """Creates the initial population of agents."""
    agents = [] # List to hold all initialized agents
    for i in range(NUM_AGENTS):
        agent = {
            "id": f"Agent_{i+1}",
            "elevated": False,
            "has_insurance": random.choice([True, False]),
            "relocated": False,
            "memory": random.sample(past_events, k=random.randint(2, 3)),
            "trust_in_insurance": round(random.uniform(0.2, 0.5), 2),
            "trust_in_neighbors": round(random.uniform(0.35, 0.55), 2),
            "intends_to_adapt": None,
            "yearly_decisions": [],
            "threat_appraisals": [],
            "coping_appraisals": [],
            "flood_history": [],
            "flood_threshold": round(random.uniform(0.4, 0.9), 2)
        }
        agents.append(agent)
    return agents

def load_agents_from_file(filepath, past_events):
    """Loads agent profiles from a CSV file."""
    df = pd.read_csv(filepath)
    agents = []
    for _, row in df.iterrows():
        if 'memory' in row and pd.notna(row['memory']):
            memory = row['memory'].split(' | ')
        else:
            memory = random.sample(past_events, k=random.randint(2, 3))

        agent = {
            "id": row['id'],
            "elevated": bool(row['elevated']),
            "has_insurance": bool(row['has_insurance']),
            "relocated": bool(row['relocated']),
            "memory": memory,
            "trust_in_insurance": float(row['trust_in_insurance']),
            "trust_in_neighbors": float(row['trust_in_neighbors']),
            "flood_threshold": float(row['flood_threshold']),
            "intends_to_adapt": None,
            "yearly_decisions": [],
            "threat_appraisals": [],
            "coping_appraisals": [],
            "flood_history": [],
        }
        agents.append(agent)
    return agents

# --- 3. Agent-specific flood exposure calculation ---
def determine_flood_exposure(agent, year, flood_event):
    """Determines if an agent is flooded and updates their memory."""
    flooded = False
    if flood_event and not agent["elevated"]:
        if random.random() < agent["flood_threshold"]:
            flooded = True
            agent["memory"].append(f"Year {year}: Got flooded with $10,000 damage on my house.")
        else:
            agent["memory"].append(f"Year {year}: A flood occurred, but my house was spared damage.")
    elif flood_event and agent["elevated"]:
        if random.random() < agent["flood_threshold"]:
            flooded = True
            agent["memory"].append(f"Year {year}: Despite elevation, the flood was severe enough to cause damage.")
        else:
            agent["memory"].append(f"Year {year}: A flood occurred, but my house was protected by its elevation.")
    elif not flood_event:
        agent["memory"].append(f"Year {year}: No flood occurred this year.")
    agent["flood_history"].append(flooded)
    return flooded

# --- 4. Define the LLM prompt using Protection Motivation Theory (PMT) ---
prompt_template = PromptTemplate.from_template("""
You are a homeowner in a city, with a strong attachment to your community. {elevation_status_text}
Your memory includes:
{memory}

You currently {insurance_status} flood insurance.
You {trust_insurance_text} the insurance company. You {trust_neighbors_text} your neighbors' judgment.

Using the Protection Motivation Theory, evaluate your current situation by considering the following factors:
- Perceived Severity: How serious the consequences of flooding feel to you.
- Perceived Vulnerability: How likely you think you are to be affected.
- Response Efficacy: How effective you believe each action is.
- Self-Efficacy: Your confidence in your ability to take that action.
- Response Cost: The financial and emotional cost of the action.
- Maladaptive Rewards: The benefit of doing nothing immediately.

Now, choose one of the following actions:
{options_text}
Note: If no flood occurred this year, since no immediate threat, most people would choose “Do Nothing.” 
                                                                                              
Please respond using the exact format below. Do NOT include any markdown symbols:
Threat Appraisal: [One sentence summary of how threatened you feel by any remaining flood risks.]
Coping Appraisal: [One sentence summary of how well you think you can cope or act.]
Final Decision: [Choose {valid_choices_text} only]
""")

def parse_response(response):
    """Extracts threat, coping, and decision from the LLM's text response."""
    lines = response.splitlines()
    threat, coping, decision = "", "", "4" 
    for line in lines:
        if "Threat Appraisal:" in line: threat = line.split("Threat Appraisal:")[-1].strip()
        elif "Coping Appraisal:" in line: coping = line.split("Coping Appraisal:")[-1].strip()
        elif "Final Decision:" in line:
            for code in ["1", "2", "3", "4"]:
                if code in line:
                    decision = code
                    break
    return threat, coping, decision

def classify_adaptation_state(agent):
    if agent["relocated"]:
        return "Relocate"
    elif agent["elevated"] and agent["has_insurance"]:
        return "Both Flood Insurance and House Elevation"
    elif agent["elevated"]:
        return "Only House Elevation"
    elif agent["has_insurance"]:
        return "Only Flood Insurance"
    else:
        return "Do Nothing"

DECISION_MAP_ELEVATED = {"1": "Buy flood insurance", "2": "Relocate", "3": "Do nothing"}
DECISION_MAP_NOT_ELEVATED = {"1": "Buy flood insurance", "2": "Elevate the house", "3": "Relocate", "4": "Do nothing"}

# --- 7. Main simulation function ---
def run_simulation(model_name, output_dir):
    start_time = time.time()
    llm = OllamaLLM(model=model_name)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    past_events = [
        "A flood event about 15 years ago caused $500,000 in city-wide damages; my neighborhood was not impacted at all",
        "Some residents reported delays when processing their flood insurance claims",
        "A few households in the area elevated their homes before recent floods",
        "The city previously introduced a program offering elevation support to residents",
        "News outlets have reported a possible trend of increasing flood frequency and severity in recent years"
    ]

    AGENT_PROFILE_FILE = "agent_initial_profiles.csv"
    FLOOD_YEARS_FILE = "flood_years.csv"

    if os.path.exists(AGENT_PROFILE_FILE) and os.path.exists(FLOOD_YEARS_FILE):
        print(f"[OK] Input files found. Loading simulation from '{AGENT_PROFILE_FILE}' and '{FLOOD_YEARS_FILE}'.")
        agents = load_agents_from_file(AGENT_PROFILE_FILE, past_events)
        flood_years_df = pd.read_csv(FLOOD_YEARS_FILE)
        predefined_flood_years = set(flood_years_df['Flood_Years'])
        run_mode = 'deterministic'
    else:
        print(f"[WARNING] Input files not found. Generating a new random simulation.")
        agents = initialize_agents_randomly(past_events)
        init_df = pd.DataFrame([{**{k: a[k] for k in ['id', 'elevated', 'has_insurance', 'relocated', 'trust_in_insurance', 'trust_in_neighbors']}, "memory": " | ".join(a["memory"]), "flood_threshold": a["flood_threshold"]} for a in agents])
        init_df.to_csv(output_path / AGENT_PROFILE_FILE, index=False)
        predefined_flood_years = set()
        run_mode = 'random'

    logs = []
    generated_flood_years = []
    selected_agent_ids = [f"Agent_{i+1}" for i in random.sample(range(NUM_AGENTS), NUM_SAMPLED_AGENTS)]
    sampled_years = random.sample(range(1, NUM_YEARS + 1), NUM_SAMPLED_YEARS)
    
    with open(output_path / "example_llm_prompts.txt", "w", encoding="utf-8") as prompt_file:
        for year in tqdm(range(1, NUM_YEARS + 1), desc="Simulating Years"):
            if run_mode == 'random':
                flood_event = random.random() < FLOOD_PROBABILITY
                if flood_event:
                    generated_flood_years.append(year)
            else:
                flood_event = year in predefined_flood_years

            grant_available = random.random() < GRANT_PROBABILITY
            active_agents = [agent for agent in agents if not agent["relocated"]]
            if not active_agents:
                break
                
            total_community_size = len(active_agents)
            total_elevated = sum(1 for a in active_agents if a["elevated"])
            total_relocated = NUM_AGENTS - total_community_size

            tasks_to_process = []
            for agent in active_agents:
                determine_flood_exposure(agent, year, flood_event)
                if grant_available: agent["memory"].append(f"Year {year}: Elevation grants are available.")
                
                num_neighbors = NUM_AGENTS - 1
                if num_neighbors > 0:
                    elevated_pct = round(((total_elevated - (1 if agent["elevated"] else 0)) / num_neighbors) * 100)
                    agent["memory"].append(f"Year {year}: I observe {elevated_pct}% of my neighbors have elevated homes.")
                    relocated_pct = round((total_relocated / num_neighbors) * 100)
                    agent["memory"].append(f"Year {year}: I observe {relocated_pct}% of my neighbors have relocated.")
                
                if random.random() < RANDOM_MEMORY_RECALL_CHANCE:
                    agent["memory"].append(f"Suddenly recalled: '{random.choice(past_events)}'.")
                agent["memory"] = agent["memory"][-MEMORY_WINDOW:]

                ins_text = verbalize_trust(agent["trust_in_insurance"], "insurance")
                neigh_text = verbalize_trust(agent["trust_in_neighbors"], "neighbors")

                prompt_vars = {
                    "memory": "\n".join(f"- {item}" for item in agent["memory"]),
                    "insurance_status": "have" if agent["has_insurance"] else "do not have",
                    "trust_insurance_text": ins_text,   
                    "trust_neighbors_text": neigh_text  
                }

                if agent["elevated"]:
                    prompt_vars.update({
                        "elevation_status_text": "Your house is already elevated, which provides very good protection.",
                        "options_text": ("1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)\n"
                                         "2. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)\n"
                                         "3. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"),
                        "valid_choices_text": "1, 2, or 3"
                    })
                else:
                    prompt_vars.update({
                        "elevation_status_text": "You have not elevated your home.",
                        "options_text": ("1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)\n"
                                         "2. Elevate your house (High upfront cost but can prevent most physical damage.)\n"
                                         "3. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)\n"
                                         "4. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"),
                        "valid_choices_text": "1, 2, 3, or 4"
                    })
                
                prompt = prompt_template.format(**prompt_vars)
                tasks_to_process.append({"agent": agent, "prompt": prompt, "was_elevated": agent["elevated"]})
                
                if agent["id"] in selected_agent_ids and year in sampled_years:
                    prompt_file.write(f"\n--- {agent['id']} | Year {year} (Elevated: {agent['elevated']}) ---\n{prompt}\n\n")

            for i in tqdm(range(0, len(tasks_to_process), BATCH_SIZE), desc=f"Year {year} Batches", leave=False):
                task_chunk = tasks_to_process[i:i + BATCH_SIZE]
                prompt_chunk = [task['prompt'] for task in task_chunk]
                
                responses_chunk = None
                for attempt in range(MAX_RETRIES):
                    try:
                        responses_chunk = llm.batch(prompt_chunk)
                        break
                    except Exception as e:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_DELAY_SECONDS)

                if responses_chunk is None:
                    default_response = "Threat Appraisal: Error\nCoping Appraisal: Error\nFinal Decision: 4"
                    responses_chunk = [default_response] * len(task_chunk)

                for task, response in zip(task_chunk, responses_chunk):
                    agent, was_elevated = task['agent'], task['was_elevated']
                    threat, coping, decision_code = parse_response(response)
                    
                    if was_elevated:
                        raw_llm_decision = DECISION_MAP_ELEVATED.get(decision_code, "Unknown")
                    else:
                        raw_llm_decision = DECISION_MAP_NOT_ELEVATED.get(decision_code, "Unknown")

                    if was_elevated:
                        if decision_code == "1": agent["has_insurance"] = True
                        elif decision_code == "2": agent["relocated"] = True
                        else: agent["has_insurance"] = False
                    else:
                        if decision_code == "1": agent["has_insurance"] = True
                        elif decision_code == "2":
                            agent["elevated"] = True
                            agent["flood_threshold"] = round(agent["flood_threshold"] * 0.2, 2)
                            agent["flood_threshold"] = max(0.001, agent["flood_threshold"])
                        elif decision_code == "3": agent["relocated"] = True
                        else: agent["has_insurance"] = False

                    adaptation_state = classify_adaptation_state(agent)
                    agent["yearly_decisions"].append(adaptation_state)
                    agent["threat_appraisals"].append(threat)
                    agent["coping_appraisals"].append(coping)
                    
                    if agent["has_insurance"]:
                        if agent["flood_history"][-1]: agent["trust_in_insurance"] -= 0.10
                        else: agent["trust_in_insurance"] += 0.02
                    else:
                        if agent["flood_history"][-1]: agent["trust_in_insurance"] += 0.05
                        else: agent["trust_in_insurance"] -= 0.02

                    community_action_rate = (total_elevated + total_relocated) / NUM_AGENTS
                    if community_action_rate > 0.30: agent["trust_in_neighbors"] += 0.04
                    elif agent["flood_history"][-1] and community_action_rate < 0.10: agent["trust_in_neighbors"] -= 0.05
                    else: agent["trust_in_neighbors"] -= 0.01

                    agent["trust_in_insurance"] = max(0.0, min(1.0, agent["trust_in_insurance"]))
                    agent["trust_in_neighbors"] = max(0.0, min(1.0, agent["trust_in_neighbors"]))
                    
                    logs.append({
                        "agent_id": agent["id"], "year": year,
                        "decision": adaptation_state,
                        "raw_llm_code": decision_code,
                        "raw_llm_decision": raw_llm_decision,
                        "threat_appraisal": threat, "coping_appraisal": coping,
                        "memory": " | ".join(agent["memory"]),
                        "trust_in_insurance": round(agent["trust_in_insurance"], 2),
                        "trust_in_neighbors": round(agent["trust_in_neighbors"], 2),
                        "elevated": agent["elevated"], "has_insurance": agent["has_insurance"],
                        "relocated": agent["relocated"], "flooded_this_year": agent["flood_history"][-1],
                    })
            
            for agent in agents:
                if agent["relocated"] and len(agent["yearly_decisions"]) < year:
                    agent["yearly_decisions"].append("Already relocated")
                    logs.append({"agent_id": agent["id"], "year": year, "decision": "Already relocated"})
            
            df_log_yearly = pd.DataFrame(logs)
            df_log_yearly.to_csv(output_path / "flood_adaptation_simulation_log.csv", index=False, encoding="utf-8-sig")

    total_time = time.time() - start_time
    final_flood_years = generated_flood_years if run_mode == 'random' else list(predefined_flood_years)
    if run_mode == 'random':
        pd.DataFrame({"Flood_Years": final_flood_years}).to_csv(output_path / FLOOD_YEARS_FILE, index=False)

    return agents, logs, total_time, selected_agent_ids, final_flood_years

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="gemma3:4b")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="results/baseline_original")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    agents, logs, sim_time, agent_ids_to_plot, flood_years = run_simulation(args.model, args.output)
    
    output_path = Path(args.output)
    df_log = pd.DataFrame(logs)
    df_log.fillna({"threat_appraisal": "N/A", "coping_appraisal": "N/A"}, inplace=True)
    df_log.to_csv(output_path / "flood_adaptation_simulation_log.csv", index=False, encoding="utf-8-sig")

    print(f"\nTotal simulation time: {sim_time:.2f} seconds\n")

    # --- Plotting ---
    state_counts = (
        df_log.groupby(["year", "decision"])
        .size().unstack(fill_value=0)
        .reindex(columns=["Do Nothing", "Only Flood Insurance", "Only House Elevation", "Both Flood Insurance and House Elevation", "Relocate"], fill_value=0)
    )
    state_counts.plot(kind='bar', stacked=True, figsize=(12, 6))
    plt.title("Adaptation States by Year")
    plt.legend(title="Adaptation State", bbox_to_anchor=(1.05, 1))
    plt.tight_layout()
    plt.savefig(output_path / "overall_adaptation_by_year.jpg", dpi=300)

    decision_map_numeric = {"Do Nothing": 0, "Only Flood Insurance": 1, "Only House Elevation": 2, "Both Flood Insurance and House Elevation": 3, "Relocate": 4}
    for agent_id in agent_ids_to_plot:
        agent_df = df_log[df_log["agent_id"] == agent_id].sort_values("year")
        fig, ax = plt.subplots(figsize=(12, 6))
        y_series = agent_df["decision"].map(decision_map_numeric)
        ax.plot(agent_df["year"], y_series, marker='o', linestyle='-', label=f"{agent_id} Decisions")
        for fy in flood_years:
            ax.axvspan(fy - 0.5, fy + 0.5, color='red', alpha=0.15, label='Flood Year' if fy == (flood_years[0] if flood_years else None) else "")
        flooded_rows = agent_df[agent_df["flooded_this_year"] == True]
        if not flooded_rows.empty:
            ax.scatter(flooded_rows["year"], flooded_rows["decision"].map(decision_map_numeric), marker='^', s=90, label="Agent flooded")
        ax.set_yticks(list(decision_map_numeric.values()))
        ax.set_yticklabels(list(decision_map_numeric.keys()))
        ax.set_title(f"Yearly Adaptation Decisions for {agent_id}")
        ax.legend()
        plt.tight_layout()
        plt.savefig(output_path / f"agent_decision_{agent_id}.jpg", dpi=300)
    plt.close('all')
