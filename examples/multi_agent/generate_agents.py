"""
Multi-Agent Profile Generator

Generates household agent profiles with:
- Demographics: income, household_size, tenure, MG status
- Trust values: trust_gov, trust_ins, trust_neighbors
- RCV: Building and contents replacement cost values
- Dynamic state initialization: elevated, insured, relocated

Output: agent_profiles.csv for multi-agent experiment

References:
- ABM_Summary.pdf: Coupled model design
- Chapter 8: Memory system integration
"""

import random
import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal

# Seed for reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# Configuration
DEFAULT_N_AGENTS = 100
OUTPUT_DIR = Path("examples/multi_agent/data")

# ============================================================================
# SCHEMA DEFINITIONS
# ============================================================================

@dataclass
class HouseholdProfile:
    """Household agent profile with steady-state and initial dynamic variables."""
    
    # ---- Identifiers ----
    agent_id: str
    tract_id: str = "T001"
    
    # ---- Steady-State Demographics (from survey) ----
    mg: bool = False                              # Marginalized Group
    tenure: Literal["Owner", "Renter"] = "Owner"
    income: float = 50_000                        # Annual income ($)
    household_size: int = 3                       # Number of people
    generations: int = 1                          # Generations in area (1-4)
    has_vehicle: bool = True                      # Evacuation capability
    has_children: bool = False                    # Under 18 in household
    has_elderly: bool = False                     # Over 65 in household
    housing_cost_burden: bool = False             # >30% income on housing
    
    # ---- Generated Values ----
    rcv_building: float = 0.0                     # Replacement cost - building ($)
    rcv_contents: float = 0.0                     # Replacement cost - contents ($)
    
    # ---- Trust Values (0-1 normalized) ----
    trust_gov: float = 0.5                        # Trust in government
    trust_ins: float = 0.5                        # Trust in insurance/FEMA
    trust_neighbors: float = 0.5                  # Trust in neighbors
    
    # ---- Dynamic State (initial) ----
    elevated: bool = False                        # House elevated (+5 ft)
    has_insurance: bool = False                   # Current insurance status
    relocated: bool = False                       # Has relocated
    cumulative_damage: float = 0.0                # Total damage to date ($)
    cumulative_oop: float = 0.0                   # Out-of-pocket costs ($)

# ============================================================================
# GENERATION FUNCTIONS
# ============================================================================

def generate_rcv(tenure: str, income: float, mg: bool) -> tuple:
    """
    Generate Replacement Cost Values using log-normal distribution.
    
    Building RCV:
    - Owners: µ=$280K (MG) or $400K (NMG), σ=0.3
    - Renters: $0 (don't own structure)
    
    Contents RCV:
    - 30-50% of building value for owners
    - $20K-$60K for renters (based on income)
    """
    if tenure == "Owner":
        mu_bld = 280_000 if mg else 400_000
        sigma = 0.3
        rcv_bld = np.random.lognormal(np.log(mu_bld), sigma)
        rcv_bld = min(max(rcv_bld, 100_000), 1_000_000)  # Clamp
        
        contents_ratio = random.uniform(0.30, 0.50)
        rcv_cnt = rcv_bld * contents_ratio
    else:
        # Renters: no building, contents only
        rcv_bld = 0.0
        base_contents = 20_000 + (income / 100_000) * 40_000
        rcv_cnt = np.random.normal(base_contents, 5_000)
        rcv_cnt = min(max(rcv_cnt, 10_000), 80_000)
    
    return round(rcv_bld, 2), round(rcv_cnt, 2)


def generate_trust_values(mg: bool) -> tuple:
    """
    Generate trust values (0-1) based on MG status.
    
    MG households tend to have lower institutional trust.
    """
    if mg:
        trust_gov = np.clip(np.random.beta(2, 5), 0.1, 0.9)
        trust_ins = np.clip(np.random.beta(2, 5), 0.1, 0.9)
        trust_neighbors = np.clip(np.random.beta(4, 3), 0.2, 0.95)  # Higher SC
    else:
        trust_gov = np.clip(np.random.beta(4, 3), 0.2, 0.9)
        trust_ins = np.clip(np.random.beta(4, 3), 0.2, 0.9)
        trust_neighbors = np.clip(np.random.beta(3, 3), 0.3, 0.8)
    
    return round(trust_gov, 3), round(trust_ins, 3), round(trust_neighbors, 3)


def generate_demographics(mg: bool, tenure: str) -> dict:
    """Generate demographic attributes based on MG and tenure."""
    
    # Income distribution (MG typically lower)
    if mg:
        income = np.random.lognormal(np.log(40_000), 0.4)
        income = min(max(income, 20_000), 80_000)
    else:
        income = np.random.lognormal(np.log(85_000), 0.4)
        income = min(max(income, 40_000), 200_000)
    
    # Household size
    household_size = np.random.choice([1, 2, 3, 4, 5, 6], p=[0.15, 0.25, 0.25, 0.20, 0.10, 0.05])
    
    # Generations in area (owners tend to have more)
    if tenure == "Owner":
        generations = np.random.choice([1, 2, 3, 4], p=[0.3, 0.35, 0.25, 0.1])
    else:
        generations = np.random.choice([1, 2, 3, 4], p=[0.6, 0.25, 0.10, 0.05])
    
    # Vehicle access (lower for MG)
    has_vehicle = random.random() > (0.25 if mg else 0.05)
    
    # Household composition
    has_children = random.random() < (0.35 if household_size >= 3 else 0.15)
    has_elderly = random.random() < 0.20
    
    # Housing cost burden (>30% income on housing)
    housing_cost_burden = mg and random.random() < 0.45
    
    return {
        "income": round(income, 2),
        "household_size": int(household_size),
        "generations": int(generations),
        "has_vehicle": has_vehicle,
        "has_children": has_children,
        "has_elderly": has_elderly,
        "housing_cost_burden": housing_cost_burden
    }


def generate_agents(
    n_agents: int = DEFAULT_N_AGENTS,
    mg_ratio: float = 0.4,
    owner_ratio: float = 0.6,
    tract_id: str = "T001"
) -> List[HouseholdProfile]:
    """
    Generate household agent profiles.
    
    Args:
        n_agents: Number of agents to generate
        mg_ratio: Proportion of MG households (0-1)
        owner_ratio: Proportion of owners (0-1)
        tract_id: Tract identifier
    
    Returns:
        List of HouseholdProfile objects
    """
    agents = []
    
    for i in range(n_agents):
        agent_id = f"H{i+1:04d}"
        
        # Determine MG and tenure status
        mg = random.random() < mg_ratio
        tenure = "Owner" if random.random() < owner_ratio else "Renter"
        
        # Generate demographics
        demo = generate_demographics(mg, tenure)
        
        # Generate RCV
        rcv_bld, rcv_cnt = generate_rcv(tenure, demo["income"], mg)
        
        # Generate trust values
        trust_gov, trust_ins, trust_neighbors = generate_trust_values(mg)
        
        # Create profile
        profile = HouseholdProfile(
            agent_id=agent_id,
            tract_id=tract_id,
            mg=mg,
            tenure=tenure,
            income=demo["income"],
            household_size=demo["household_size"],
            generations=demo["generations"],
            has_vehicle=demo["has_vehicle"],
            has_children=demo["has_children"],
            has_elderly=demo["has_elderly"],
            housing_cost_burden=demo["housing_cost_burden"],
            rcv_building=rcv_bld,
            rcv_contents=rcv_cnt,
            trust_gov=trust_gov,
            trust_ins=trust_ins,
            trust_neighbors=trust_neighbors,
            # Dynamic state initialized to defaults
            elevated=False,
            has_insurance=random.random() < 0.15,  # ~15% initial take-up
            relocated=False,
            cumulative_damage=0.0,
            cumulative_oop=0.0
        )
        
        agents.append(profile)
    
    return agents


def save_agents_to_csv(agents: List[HouseholdProfile], output_path: Path) -> None:
    """Save agent profiles to CSV."""
    records = [asdict(a) for a in agents]
    df = pd.DataFrame(records)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_csv(output_path, index=False)
    print(f"[OK] Saved {len(agents)} agent profiles to {output_path}")
    
    # Print summary
    print(f"\n=== Agent Profile Summary ===")
    print(f"Total agents: {len(agents)}")
    print(f"MG ratio: {df['mg'].mean():.1%}")
    print(f"Owner ratio: {(df['tenure'] == 'Owner').mean():.1%}")
    print(f"Mean income: ${df['income'].mean():,.0f}")
    print(f"Mean RCV (building): ${df['rcv_building'].mean():,.0f}")
    print(f"Mean RCV (contents): ${df['rcv_contents'].mean():,.0f}")
    print(f"Initial insurance uptake: {df['has_insurance'].mean():.1%}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate multi-agent household profiles")
    parser.add_argument("--n", type=int, default=100, help="Number of agents")
    parser.add_argument("--mg-ratio", type=float, default=0.4, help="MG proportion")
    parser.add_argument("--owner-ratio", type=float, default=0.6, help="Owner proportion")
    parser.add_argument("--tract", type=str, default="T001", help="Tract ID")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    
    # Set seed
    random.seed(args.seed)
    np.random.seed(args.seed)
    
    # Generate agents
    agents = generate_agents(
        n_agents=args.n,
        mg_ratio=args.mg_ratio,
        owner_ratio=args.owner_ratio,
        tract_id=args.tract
    )
    
    # Save to CSV
    output_path = Path(args.output) if args.output else OUTPUT_DIR / "agent_profiles.csv"
    save_agents_to_csv(agents, output_path)
