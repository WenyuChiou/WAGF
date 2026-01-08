
import csv
import random
import os

def generate_profiles(num_agents, output_file):
    header = ["agent_id", "elevated", "has_insurance", "relocated", "trust_ins", "trust_neighbors", "flood_threshold", "memory"]
    
    # Sample memories
    past_events = [
        "A flood event about 15 years ago caused $500,000 in city-wide damages; my neighborhood was not impacted at all",
        "Some residents reported delays when processing their flood insurance claims",
        "A few households in the area elevated their homes before recent floods",
        "The city previously introduced a program offering elevation support to residents",
        "News outlets have reported a possible trend of increasing flood frequency and severity in recent years"
    ]
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        
        for i in range(1, num_agents + 1):
            agent_id = f"Agent_{i}"
            elevated = False 
            has_insurance = random.choice([True, False])
            relocated = False
            trust_ins = round(random.uniform(0.2, 0.5), 2)
            trust_neighbors = round(random.uniform(0.35, 0.55), 2)
            flood_threshold = round(random.uniform(0.4, 0.9), 2)
            
            # Select 2-3 random memories
            memories = random.sample(past_events, k=random.randint(2, 3))
            memory_str = " | ".join(memories)
            
            writer.writerow([agent_id, elevated, has_insurance, relocated, trust_ins, trust_neighbors, flood_threshold, memory_str])
            
    print(f"Generated {output_file} with {num_agents} agents.")

if __name__ == "__main__":
    generate_profiles(100, "H:/我的雲端硬碟/github/governed_broker_framework/examples/v2-2_clean_skill_governed/agent_initial_profiles.csv")
