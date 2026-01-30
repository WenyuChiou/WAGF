"""
Multi-Agent Profile Generator

Supports two modes:
1. survey: Initialize from questionnaire data (100 NJ households)
2. random: Generate synthetic profiles (legacy mode)

Output: agent_profiles.csv for multi-agent experiment

References:
- ABM_Summary.pdf: Coupled model design
- SM_clean_vr.docx: PMT construct mapping (Table 12)
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
DATA_DIR = Path(__file__).parent / "data"
INPUT_DIR = Path(__file__).parent / "input"


# ============================================================================
# NEW SCHEMA (PMT-based, no trust variables)
# ============================================================================

@dataclass
class HouseholdProfile:
    """Household agent profile with PMT constructs (no trust variables)."""

    # ---- Identifiers ----
    agent_id: str
    survey_id: str = ""                               # Original ResponseId (survey mode)
    tract_id: str = "T001"

    # ---- Demographics (from survey or generated) ----
    mg: bool = False                                  # Marginalized Group
    tenure: Literal["Owner", "Renter"] = "Owner"
    income_bracket: str = "$50,000 - $74,999"         # Survey bracket
    income: float = 62_500                            # Estimated midpoint ($)
    household_size: int = 3                           # Number of people
    generations: int = 1                              # Generations in area (1-4)
    has_vehicle: bool = True                          # Evacuation capability
    has_children: bool = False                        # Under 18 in household
    has_elderly: bool = False                         # Over 65 in household
    housing_cost_burden: bool = False                 # >30% income on housing
    mg_criteria_met: bool = False                     # Survey MG criteria flag
    zipcode: str = ""                                 # ZIP code (survey)

    # ---- Flood Experience (from survey) ----
    flood_experience: bool = False                    # Q14: Has experienced flooding
    flood_frequency: int = 0                          # Number of flood events (0-7+)
    sfha_awareness: bool = False                      # Q7: Knows about SFHA

    # ---- PMT Constructs (1-5 scale) ----
    sc_score: float = 3.0                             # Social Capital (Q21_1-6)
    pa_score: float = 3.0                             # Place Attachment (Q21_7-15)
    tp_score: float = 3.0                             # Threat Perception (Q22_1-11)
    cp_score: float = 3.0                             # Coping Perception (Q24, Q25)
    sp_score: float = 3.0                             # Stakeholder Perception (Q25_3,6,9)

    # ---- RCV (generated based on income/tenure) ----
    rcv_building: float = 0.0                         # Replacement cost - building ($)
    rcv_contents: float = 0.0                         # Replacement cost - contents ($)

    # ---- Spatial (assigned by flood zone) ----
    grid_x: int = 0
    grid_y: int = 0
    flood_zone: str = "MEDIUM"                        # HIGH, MEDIUM, LOW
    flood_depth: float = 0.0                          # Meters
    longitude: float = 0.0
    latitude: float = 0.0

    # ---- Dynamic State (initial) ----
    elevated: bool = False                            # House elevated (+5 ft)
    has_insurance: bool = False                       # Current NFIP status
    relocated: bool = False                           # Has relocated
    cumulative_damage: float = 0.0                    # Total damage to date ($)
    cumulative_oop: float = 0.0                       # Out-of-pocket costs ($)

    # ---- Survey metadata (for memory generation) ----
    recent_flood_text: str = ""                       # Q15: Last flood timing
    insurance_type: str = ""                          # Q23: Insurance type
    post_flood_action: str = ""                       # Q19: Action after flood


# ============================================================================
# SURVEY-BASED INITIALIZATION
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
        rcv_bld = min(max(rcv_bld, 100_000), 1_000_000)

        contents_ratio = random.uniform(0.30, 0.50)
        rcv_cnt = rcv_bld * contents_ratio
    else:
        rcv_bld = 0.0
        base_contents = 20_000 + (income / 100_000) * 40_000
        rcv_cnt = np.random.normal(base_contents, 5_000)
        rcv_cnt = min(max(rcv_cnt, 10_000), 80_000)

    return round(rcv_bld, 2), round(rcv_cnt, 2)


def load_survey_agents(
    survey_csv: Optional[Path] = None,
    location_csv: Optional[Path] = None,
    tract_id: str = "T001",
    seed: int = SEED
) -> List[HouseholdProfile]:
    """
    Load agents from survey data with assigned locations.

    Args:
        survey_csv: Path to cleaned_survey.csv (from survey_loader.py)
        location_csv: Path to agents_with_location.csv (from flood_zone_assigner.py)
        tract_id: Tract identifier
        seed: Random seed for RCV generation

    Returns:
        List of HouseholdProfile objects
    """
    random.seed(seed)
    np.random.seed(seed)

    # Use location CSV if available (has all survey fields + spatial)
    if location_csv is None:
        location_csv = DATA_DIR / "agents_with_location.csv"

    if survey_csv is None:
        survey_csv = DATA_DIR / "cleaned_survey.csv"

    # Prefer location CSV (includes spatial data)
    if location_csv.exists():
        print(f"[INFO] Loading from {location_csv}")
        df = pd.read_csv(location_csv)
    elif survey_csv.exists():
        print(f"[INFO] Loading from {survey_csv} (no spatial data)")
        df = pd.read_csv(survey_csv)
    else:
        raise FileNotFoundError(
            f"Neither {location_csv} nor {survey_csv} found. "
            "Run survey_loader.py and flood_zone_assigner.py first."
        )

    agents = []
    for idx, row in df.iterrows():
        agent_id = f"H{idx+1:04d}"

        # Generate RCV based on survey data
        tenure = row.get("tenure", "Owner")
        income = float(row.get("income", 50000))
        mg = bool(row.get("mg", False))
        rcv_bld, rcv_cnt = generate_rcv(tenure, income, mg)

        # Determine initial insurance status from survey
        insurance_type = str(row.get("insurance_type", ""))
        has_insurance = "flood" in insurance_type.lower() or "nfip" in insurance_type.lower()

        profile = HouseholdProfile(
            agent_id=agent_id,
            survey_id=str(row.get("survey_id", "")),
            tract_id=tract_id,

            # Demographics
            mg=mg,
            tenure=tenure,
            income_bracket=str(row.get("income_bracket", "$50,000 - $74,999")),
            income=income,
            household_size=int(row.get("household_size", 3)),
            generations=int(row.get("generations", 1)),
            has_vehicle=bool(row.get("has_vehicle", True)),
            has_children=bool(row.get("has_children", False)),
            has_elderly=bool(row.get("has_elderly", False)),
            housing_cost_burden=bool(row.get("housing_cost_burden", False)),
            mg_criteria_met=bool(row.get("mg_criteria_met", False)),
            zipcode=str(row.get("zipcode", "")),

            # Flood experience
            flood_experience=bool(row.get("flood_experience", False)),
            flood_frequency=int(row.get("flood_frequency", 0)),
            sfha_awareness=bool(row.get("sfha_awareness", False)),

            # PMT constructs
            sc_score=float(row.get("sc_score", 3.0)),
            pa_score=float(row.get("pa_score", 3.0)),
            tp_score=float(row.get("tp_score", 3.0)),
            cp_score=float(row.get("cp_score", 3.0)),
            sp_score=float(row.get("sp_score", 3.0)),

            # RCV
            rcv_building=rcv_bld,
            rcv_contents=rcv_cnt,

            # Spatial (if available)
            grid_x=int(row.get("grid_x", 0)),
            grid_y=int(row.get("grid_y", 0)),
            flood_zone=str(row.get("flood_zone", "MEDIUM")),
            flood_depth=float(row.get("flood_depth", 0.5)),
            longitude=float(row.get("longitude", -74.3)),
            latitude=float(row.get("latitude", 40.9)),

            # Dynamic state
            elevated=False,
            has_insurance=has_insurance,
            relocated=False,
            cumulative_damage=0.0,
            cumulative_oop=0.0,

            # Survey metadata
            recent_flood_text=str(row.get("recent_flood_text", "")),
            insurance_type=insurance_type,
            post_flood_action=str(row.get("post_flood_action", ""))
        )

        agents.append(profile)

    print(f"[INFO] Loaded {len(agents)} agents from survey data")
    return agents


# ============================================================================
# RANDOM GENERATION (LEGACY MODE)
# ============================================================================

def generate_pmt_scores(mg: bool) -> dict:
    """
    Generate PMT construct scores (1-5 scale) based on MG status.

    MG households tend to have:
    - Lower institutional trust (SP)
    - Higher threat perception (TP)
    - Lower coping perception (CP)
    - Higher social capital within community (SC)
    """
    if mg:
        sc = np.clip(np.random.normal(3.8, 0.6), 1.5, 5.0)   # Higher SC
        pa = np.clip(np.random.normal(3.5, 0.7), 1.5, 5.0)   # Moderate PA
        tp = np.clip(np.random.normal(3.5, 0.8), 1.5, 5.0)   # Higher TP
        cp = np.clip(np.random.normal(2.5, 0.7), 1.0, 4.5)   # Lower CP
        sp = np.clip(np.random.normal(2.3, 0.6), 1.0, 4.0)   # Lower SP
    else:
        sc = np.clip(np.random.normal(3.2, 0.6), 1.5, 5.0)
        pa = np.clip(np.random.normal(3.0, 0.7), 1.5, 5.0)
        tp = np.clip(np.random.normal(2.8, 0.7), 1.5, 5.0)
        cp = np.clip(np.random.normal(3.2, 0.6), 1.5, 5.0)
        sp = np.clip(np.random.normal(3.0, 0.5), 1.5, 5.0)

    return {
        "sc_score": round(sc, 2),
        "pa_score": round(pa, 2),
        "tp_score": round(tp, 2),
        "cp_score": round(cp, 2),
        "sp_score": round(sp, 2)
    }


def generate_demographics_random(mg: bool, tenure: str) -> dict:
    """Generate demographic attributes for random mode."""

    # Income distribution (MG typically lower)
    if mg:
        income = np.random.lognormal(np.log(40_000), 0.4)
        income = min(max(income, 20_000), 80_000)
        income_bracket = "$25,000 - $49,999" if income < 50000 else "$50,000 - $74,999"
    else:
        income = np.random.lognormal(np.log(85_000), 0.4)
        income = min(max(income, 40_000), 200_000)
        if income < 75000:
            income_bracket = "$50,000 - $74,999"
        elif income < 100000:
            income_bracket = "$75,000 - $99,999"
        else:
            income_bracket = "$100,000 or more"

    # Household size
    household_size = np.random.choice([1, 2, 3, 4, 5, 6], p=[0.15, 0.25, 0.25, 0.20, 0.10, 0.05])

    # Generations in area
    if tenure == "Owner":
        generations = np.random.choice([1, 2, 3, 4], p=[0.3, 0.35, 0.25, 0.1])
    else:
        generations = np.random.choice([1, 2, 3, 4], p=[0.6, 0.25, 0.10, 0.05])

    # Other attributes
    has_vehicle = random.random() > (0.25 if mg else 0.05)
    has_children = random.random() < (0.35 if household_size >= 3 else 0.15)
    has_elderly = random.random() < 0.20
    housing_cost_burden = mg and random.random() < 0.45

    return {
        "income": round(income, 2),
        "income_bracket": income_bracket,
        "household_size": int(household_size),
        "generations": int(generations),
        "has_vehicle": has_vehicle,
        "has_children": has_children,
        "has_elderly": has_elderly,
        "housing_cost_burden": housing_cost_burden
    }


def generate_agents_random(
    n_agents: int = DEFAULT_N_AGENTS,
    mg_ratio: float = 0.16,
    owner_ratio: float = 0.65,
    tract_id: str = "T001"
) -> List[HouseholdProfile]:
    """
    Generate synthetic household agent profiles (legacy mode).

    Args:
        n_agents: Number of agents to generate
        mg_ratio: Proportion of MG households (default: 16% from NJ survey)
        owner_ratio: Proportion of owners (default: 65% from NJ survey)
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
        demo = generate_demographics_random(mg, tenure)

        # Generate RCV
        rcv_bld, rcv_cnt = generate_rcv(tenure, demo["income"], mg)

        # Generate PMT scores
        pmt = generate_pmt_scores(mg)

        # Generate flood experience
        flood_experience = random.random() < 0.25  # ~25% have experience
        flood_frequency = np.random.choice([0, 1, 2, 3, 4, 5], p=[0.4, 0.25, 0.15, 0.10, 0.05, 0.05]) if flood_experience else 0

        # Create profile
        profile = HouseholdProfile(
            agent_id=agent_id,
            survey_id="",
            tract_id=tract_id,

            # Demographics
            mg=mg,
            tenure=tenure,
            income_bracket=demo["income_bracket"],
            income=demo["income"],
            household_size=demo["household_size"],
            generations=demo["generations"],
            has_vehicle=demo["has_vehicle"],
            has_children=demo["has_children"],
            has_elderly=demo["has_elderly"],
            housing_cost_burden=demo["housing_cost_burden"],
            mg_criteria_met=mg,
            zipcode="",

            # Flood experience
            flood_experience=flood_experience,
            flood_frequency=flood_frequency,
            sfha_awareness=random.random() < 0.6,

            # PMT constructs
            sc_score=pmt["sc_score"],
            pa_score=pmt["pa_score"],
            tp_score=pmt["tp_score"],
            cp_score=pmt["cp_score"],
            sp_score=pmt["sp_score"],

            # RCV
            rcv_building=rcv_bld,
            rcv_contents=rcv_cnt,

            # Spatial (placeholder for random mode)
            grid_x=random.randint(0, 456),
            grid_y=random.randint(0, 410),
            flood_zone=random.choice(["HIGH", "MEDIUM", "LOW"]),
            flood_depth=round(random.uniform(0.1, 2.0), 3),
            longitude=round(-74.3 + random.uniform(0, 0.1), 6),
            latitude=round(40.9 + random.uniform(0, 0.1), 6),

            # Dynamic state
            elevated=False,
            has_insurance=random.random() < 0.15,
            relocated=False,
            cumulative_damage=0.0,
            cumulative_oop=0.0,

            # Survey metadata (empty for random mode)
            recent_flood_text="",
            insurance_type="",
            post_flood_action=""
        )

        agents.append(profile)

    return agents


# ============================================================================
# OUTPUT FUNCTIONS
# ============================================================================

def save_agents_to_csv(agents: List[HouseholdProfile], output_path: Path) -> None:
    """Save agent profiles to CSV."""
    records = [asdict(a) for a in agents]
    df = pd.DataFrame(records)

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
    print(f"Flood experience: {df['flood_experience'].mean():.1%}")
    print(f"Initial insurance: {df['has_insurance'].mean():.1%}")

    print(f"\n=== PMT Construct Averages ===")
    print(f"SC (Social Capital): {df['sc_score'].mean():.2f}")
    print(f"PA (Place Attachment): {df['pa_score'].mean():.2f}")
    print(f"TP (Threat Perception): {df['tp_score'].mean():.2f}")
    print(f"CP (Coping Perception): {df['cp_score'].mean():.2f}")
    print(f"SP (Stakeholder Perception): {df['sp_score'].mean():.2f}")

    if "flood_zone" in df.columns:
        print(f"\n=== Flood Zone Distribution ===")
        for zone in ["HIGH", "MEDIUM", "LOW"]:
            count = (df["flood_zone"] == zone).sum()
            pct = count / len(df) * 100
            print(f"  {zone}: {count} ({pct:.1f}%)")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate multi-agent household profiles")
    parser.add_argument("--mode", type=str, choices=["survey", "random"], default="survey",
                        help="Initialization mode (survey: from questionnaire, random: synthetic)")
    parser.add_argument("--n", type=int, default=100, help="Number of agents (random mode only)")
    parser.add_argument("--mg-ratio", type=float, default=0.16, help="MG proportion (random mode)")
    parser.add_argument("--owner-ratio", type=float, default=0.65, help="Owner proportion (random mode)")
    parser.add_argument("--tract", type=str, default="T001", help="Tract ID")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    # Set seed
    random.seed(args.seed)
    np.random.seed(args.seed)

    # Generate agents
    if args.mode == "survey":
        agents = load_survey_agents(tract_id=args.tract, seed=args.seed)
    else:
        agents = generate_agents_random(
            n_agents=args.n,
            mg_ratio=args.mg_ratio,
            owner_ratio=args.owner_ratio,
            tract_id=args.tract
        )

    # Save to CSV
    output_path = Path(args.output) if args.output else DATA_DIR / "agent_profiles.csv"
    save_agents_to_csv(agents, output_path)
