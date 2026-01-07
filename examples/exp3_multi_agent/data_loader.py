"""
Agent Data Loader (Exp3)

Loads agent initialization data from CSV/Excel files.
Provides default data if file not found.
"""

import os
import pandas as pd
from typing import List, Optional
from examples.exp3_multi_agent.agents import HouseholdAgent, GovernmentAgent, InsuranceAgent


DEFAULT_DATA_PATH = os.path.join(
    os.path.dirname(__file__), 
    "data", 
    "agents_init.csv"
)


def load_households_from_csv(
    filepath: Optional[str] = None,
    seed: int = 42
) -> List[HouseholdAgent]:
    """
    Load household agents from CSV file.
    
    Expected columns:
    - agent_id: str (e.g., "H001")
    - mg: bool (TRUE/FALSE)
    - tenure: str ("Owner" or "Renter")
    - region_id: str ("NJ" or "NY")
    - income: float
    - property_value: float (0 for renters)
    - trust_gov: float (0.0-1.0)
    - trust_ins: float (0.0-1.0)
    - trust_neighbors: float (0.0-1.0)
    
    Args:
        filepath: Path to CSV file. Uses default if None.
        seed: Random seed for any randomization.
        
    Returns:
        List of HouseholdAgent instances.
    """
    if filepath is None:
        filepath = DEFAULT_DATA_PATH
    
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found. Using generated defaults.")
        return _generate_default_households(seed)
    
    print(f"Loading agents from: {filepath}")
    df = pd.read_csv(filepath)
    
    households = []
    
    import random # Ensure random is available in local scope if needed or rely on outer import
    
    for _, row in df.iterrows():
        # Generate defaults if column missing
        default_gen = random.choices([1, 2, 3], weights=[0.5, 0.3, 0.2])[0]
        default_size = random.randint(1, 5)
        default_vehicle = random.random() > 0.2  # 80% have car
        
        agent = HouseholdAgent(
            agent_id=str(row['agent_id']),
            mg=_parse_bool(row['mg']),
            tenure=str(row['tenure']),
            income=float(row['income']),
            property_value=float(row['property_value']),
            region_id=str(row.get('region_id', 'NJ')),
            generations=int(row.get('generations', default_gen)),
            household_size=int(row.get('household_size', default_size)),
            has_vehicle=_parse_bool(row.get('has_vehicle', default_vehicle))
        )
        
        # Override randomized trust if provided
        if 'trust_gov' in row:
            agent.state.trust_in_government = float(row['trust_gov'])
        if 'trust_ins' in row:
            agent.state.trust_in_insurance = float(row['trust_ins'])
        if 'trust_neighbors' in row:
            agent.state.trust_in_neighbors = float(row['trust_neighbors'])
        
        households.append(agent)
    
    print(f"Loaded {len(households)} household agents")
    return households


def load_households_from_excel(
    filepath: str,
    sheet_name: str = "Agents",
    seed: int = 42
) -> List[HouseholdAgent]:
    """
    Load household agents from Excel file.
    
    Same column structure as CSV loader.
    """
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found. Using generated defaults.")
        return _generate_default_households(seed)
    
    print(f"Loading agents from Excel: {filepath} (sheet: {sheet_name})")
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    
    households = []
    for _, row in df.iterrows():
        # Generate defaults if column missing
        default_gen = random.choices([1, 2, 3], weights=[0.5, 0.3, 0.2])[0]
        default_size = random.randint(1, 5)
        default_vehicle = random.random() > 0.2  # 80% have car
        
        agent = HouseholdAgent(
            agent_id=str(row['agent_id']),
            mg=_parse_bool(row['mg']),
            tenure=str(row['tenure']),
            income=float(row['income']),
            property_value=float(row['property_value']),
            region_id=str(row.get('region_id', 'NJ')),
            generations=int(row.get('generations', default_gen)),
            household_size=int(row.get('household_size', default_size)),
            has_vehicle=_parse_bool(row.get('has_vehicle', default_vehicle))
        )
        
        if 'trust_gov' in row:
            agent.state.trust_in_government = float(row['trust_gov'])
        if 'trust_ins' in row:
            agent.state.trust_in_insurance = float(row['trust_ins'])
        if 'trust_neighbors' in row:
            agent.state.trust_in_neighbors = float(row['trust_neighbors'])
        
        households.append(agent)
    
    print(f"Loaded {len(households)} household agents from Excel")
    return households


def _parse_bool(value) -> bool:
    """Parse various boolean representations."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.upper() in ['TRUE', 'YES', '1', 'T', 'Y']
    return bool(value)


def _generate_default_households(seed: int = 42) -> List[HouseholdAgent]:
    """Generate default household agents (fallback)."""
    import random
    random.seed(seed)
    
    households = []
    count = 0
    
    # Distribution: 30% MG Owner, 20% MG Renter, 40% NMG Owner, 10% NMG Renter
    distribution = [
        (True, "Owner", 15),
        (True, "Renter", 10),
        (False, "Owner", 20),
        (False, "Renter", 5)
    ]
    
    for mg, tenure, num in distribution:
        for i in range(num):
            count += 1
            if tenure == "Owner":
                income = random.gauss(60000, 15000) * (0.7 if mg else 1.0)
                prop_val = random.gauss(300000, 50000) * (0.8 if mg else 1.0)
            else:
                income = random.gauss(40000, 10000) * (0.7 if mg else 1.0)
                prop_val = 0
            
            region = "NJ" if i % 5 < 3 else "NY"
            
            # Demographic logic
            generations = 1
            if tenure == "Owner":
                generations = random.choices([1, 2, 3, 4], weights=[0.4, 0.3, 0.2, 0.1])[0]
            else:
                generations = random.choices([1, 2], weights=[0.8, 0.2])[0]
                
            household_size = random.randint(1, 5)
            
            # MG households less likely to have vehicle
            has_vehicle = random.random() < (0.6 if mg else 0.95)
            
            agent = HouseholdAgent(
                agent_id=f"H{count:03d}",
                mg=mg,
                tenure=tenure,
                income=max(income, 20000),
                property_value=max(prop_val, 0),
                region_id=region,
                generations=generations,
                household_size=household_size,
                has_vehicle=has_vehicle
            )
            households.append(agent)
    
    print(f"Generated {len(households)} default household agents")
    return households


def initialize_all_agents(
    households_path: Optional[str] = None,
    seed: int = 42
) -> tuple:
    """
    Initialize all agent types.
    
    Args:
        households_path: Path to household CSV
        seed: Random seed
    
    Returns:
        (households, governments, insurance)
    """
    households = load_households_from_csv(households_path, seed)
    
    # Initialize Institutional Agents
    # Now using compatible agents directly
    
    # Governments per region
    governments = {
        "NJ": GovernmentAgent("Gov_NJ"),
        "NY": GovernmentAgent("Gov_NY")
    }
    governments["NJ"].state.annual_budget = 500_000
    
    governments["NY"].state.annual_budget = 600_000
    governments["NY"].state.budget_remaining = 600_000
    
    # Insurance Agent
    insurance = InsuranceAgent("InsuranceCo")
    
    print("[INFO] Initialized agents (Consolidated Framework)")
    
    return households, governments, insurance

