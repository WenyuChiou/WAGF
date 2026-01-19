import os
import sys
import argparse
import random
import time
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

# --- 1. Set simulation parameters ---
NUM_AGENTS = 100                    
NUM_YEARS = 10                      
BATCH_SIZE = 25                     
MAX_RETRIES = 3                     
RETRY_DELAY_SECONDS = 5             
FLOOD_PROBABILITY = 0.2             
GRANT_PROBABILITY = 0.5             
RANDOM_MEMORY_RECALL_CHANCE = 0.2   
MEMORY_WINDOW = 5                   

def verbalize_trust(value, category="insurance"):
    if category == "insurance":
        if value >= 0.8: return "strongly trust"
        elif value >= 0.5: return "moderately trust"
        elif value >= 0.2: return "have slight doubts about"
        else: return "deeply distrust"
    elif category == "neighbors":
        if value >= 0.8: return "highly rely on"
        elif value >= 0.5: return "generally trust"
        elif value >= 0.2: return "are skeptical of"
        else: return "completely ignore"
    return "trust"

def initialize_agents_randomly(past_events):
    agents = []
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
    df = pd.read_csv(filepath)
    agents = []
    for _, row in df.iterrows():
        memory = row['memory'].split(' | ') if 'memory' in row and pd.notna(row['memory']) else random.sample(past_events, k=random.randint(2, 3))
        agent = {
            "id": row['id'],
            "elevated": bool(row['elevated']),
            "has_insurance": bool(row['has_insurance']),
            "relocated": bool(row['relocated']),
            "memory": memory,
            "trust_in_insurance": float(row['trust_in_insurance']),
            "trust_in_neighbors": float(row['trust_in_neighbors']),
            "flood_threshold": float(row['flood_threshold']),
            "intends_to_adapt": None, "yearly_decisions": [], "threat_appraisals": [], "coping_appraisals": [], "flood_history": [],
        }
        agents.append(agent)
    return agents

def determine_flood_exposure(agent, year, flood_event):
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
    if agent["relocated"]: return "Relocate"
    elif agent["elevated"] and agent["has_insurance"]: return "Both Flood Insurance and House Elevation"
    elif agent["elevated"]: return "Only House Elevation"
    elif agent["has_insurance"]: return "Only Flood Insurance"
    else: return "Do Nothing"

DECISION_MAP_ELEVATED = {"1": "Buy flood insurance", "2": "Relocate", "3": "Do nothing"}
DECISION_MAP_NOT_ELEVATED = {"1": "Buy flood insurance", "2": "Elevate the house", "3": "Relocate", "4": "Do nothing"}

def run_simulation(model, seed, output_dir):
    random.seed(seed)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    llm = OllamaLLM(model=model)
    past_events = [
        "A flood event about 15 years ago caused $500,000 in city-wide damages; my neighborhood was not impacted at all",
        "Some residents reported delays when processing their flood insurance claims",
        "A few households in the area elevated their homes before recent floods",
        "The city previously introduced a program offering elevation support to residents",
        "News outlets have reported a possible trend of increasing flood frequency and severity in recent years"
    ]

    # Look for files in the parent directory for parity
    AGENT_PROFILE_FILE = Path(__file__).parent / "agent_initial_profiles.csv"
    FLOOD_YEARS_FILE = Path(__file__).parent / "flood_years.csv"

    if AGENT_PROFILE_FILE.exists() and FLOOD_YEARS_FILE.exists():
        agents = load_agents_from_file(AGENT_PROFILE_FILE, past_events)
        flood_years_df = pd.read_csv(FLOOD_YEARS_FILE)
        predefined_flood_years = set(flood_years_df['Flood_Years'])
        run_mode = 'deterministic'
    else:
        agents = initialize_agents_randomly(past_events)
        predefined_flood_years = set()
        run_mode = 'random'

    logs = []
    generated_flood_years = []
    
    for year in tqdm(range(1, NUM_YEARS + 1), desc=f"Simulating {model} Base"):
        flood_event = year in predefined_flood_years if run_mode == 'deterministic' else (random.random() < FLOOD_PROBABILITY)
        if run_mode == 'random' and flood_event: generated_flood_years.append(year)

        grant_available = random.random() < GRANT_PROBABILITY
        active_agents = [agent for agent in agents if not agent["relocated"]]
        if not active_agents: break
            
        total_elevated = sum(1 for a in active_agents if a["elevated"])
        total_relocated = NUM_AGENTS - len(active_agents)

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
                    "options_text": "1. Buy flood insurance\n2. Relocate\n3. Do nothing",
                    "valid_choices_text": "1, 2, or 3"
                })
            else:
                prompt_vars.update({
                    "elevation_status_text": "You have not elevated your home.",
                    "options_text": "1. Buy flood insurance\n2. Elevate your house\n3. Relocate\n4. Do nothing",
                    "valid_choices_text": "1, 2, 3, or 4"
                })
            
            tasks_to_process.append({"agent": agent, "prompt": prompt_template.format(**prompt_vars), "was_elevated": agent["elevated"]})

        for i in range(0, len(tasks_to_process), BATCH_SIZE):
            task_chunk = tasks_to_process[i:i + BATCH_SIZE]
            prompt_chunk = [task['prompt'] for task in task_chunk]
            try:
                responses_chunk = llm.batch(prompt_chunk)
            except:
                responses_chunk = ["Threat Appraisal: Error\nCoping Appraisal: Error\nFinal Decision: 4"] * len(task_chunk)

            for task, response in zip(task_chunk, responses_chunk):
                agent, was_elevated = task['agent'], task['was_elevated']
                threat, coping, decision_code = parse_response(response)
                
                if was_elevated:
                    if decision_code == "1": agent["has_insurance"] = True
                    elif decision_code == "2": agent["relocated"] = True
                    else: agent["has_insurance"] = False
                else:
                    if decision_code == "1": agent["has_insurance"] = True
                    elif decision_code == "2": 
                        agent["elevated"] = True
                        agent["flood_threshold"] = max(0.001, round(agent["flood_threshold"] * 0.2, 2))
                    elif decision_code == "3": agent["relocated"] = True
                    else: agent["has_insurance"] = False

                adaptation_state = classify_adaptation_state(agent)
                logs.append({
                    "agent_id": agent["id"], "year": year, "decision": adaptation_state,
                    "threat_appraisal": threat, "coping_appraisal": coping, "memory": " | ".join(agent["memory"]),
                    "elevated": agent["elevated"], "has_insurance": agent["has_insurance"], "relocated": agent["relocated"],
                })

    df_log = pd.DataFrame(logs)
    df_log.to_csv(output_path / "simulation_log.csv", index=False)
    print(f"Legacy simulation complete. Results in {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="gemma3:4b")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="results/baseline")
    args = parser.parse_args()
    run_simulation(args.model, args.seed, args.output)
