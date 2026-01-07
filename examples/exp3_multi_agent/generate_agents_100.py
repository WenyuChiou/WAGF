
import csv
import random
import os

OUTPUT_FILE = "examples/exp3_multi_agent/data/agents_init.csv"

# Configuration
NUM_AGENTS = 100
REGIONS = ["NJ", "NY"]
GROUPS = [
    # (mg, tenure, count, income_range, prop_range, trust_range)
    (True, "Owner", 25, (30000, 50000), (200000, 300000), (0.3, 0.6)),
    (True, "Renter", 25, (20000, 35000), (0, 0), (0.3, 0.6)),
    (False, "Owner", 35, (60000, 100000), (350000, 600000), (0.5, 0.8)),
    (False, "Renter", 15, (40000, 60000), (0, 0), (0.5, 0.8))
]

def generate():
    agents = []
    agent_count = 1
    
    for mg, tenure, count, income_rng, prop_rng, trust_rng in GROUPS:
        for _ in range(count):
            aid = f"H{agent_count:03d}"
            region = random.choice(REGIONS)
            income = random.randint(income_rng[0], income_rng[1])
            prop = random.randint(prop_rng[0], prop_rng[1]) if tenure == "Owner" else 0
            
            # Trust
            tg = round(random.uniform(trust_rng[0], trust_rng[1]), 2)
            ti = round(random.uniform(trust_rng[0], trust_rng[1]), 2)
            tn = round(random.uniform(trust_rng[0], trust_rng[1]), 2)
            
            agents.append({
                "agent_id": aid,
                "mg": "TRUE" if mg else "FALSE",
                "tenure": tenure,
                "region_id": region,
                "income": income,
                "property_value": prop,
                "trust_gov": tg,
                "trust_ins": ti,
                "trust_neighbors": tn
            })
            agent_count += 1
            
    # Write to CSV
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "agent_id","mg","tenure","region_id","income",
            "property_value","trust_gov","trust_ins","trust_neighbors"
        ])
        writer.writeheader()
        writer.writerows(agents)
        
    print(f"Generated {len(agents)} agents in {OUTPUT_FILE}")

if __name__ == "__main__":
    generate()
