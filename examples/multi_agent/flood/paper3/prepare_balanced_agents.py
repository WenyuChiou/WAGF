"""
Paper 3: Balanced 4-Cell Agent Preparation Pipeline.

End-to-end pipeline that:
1. Loads cleaned_survey_full.csv (all NJ respondents)
2. Applies BalancedSampler (25 per cell: MG/NMG x Owner/Renter)
3. Generates RCV values (replacement cost)
4. Assigns flood zones + spatial locations
5. Generates initial memories from survey answers
6. Saves agent_profiles_balanced.csv + initial_memories_balanced.json

Usage:
    python paper3/prepare_balanced_agents.py --seed 42
    python paper3/prepare_balanced_agents.py --seed 42 --n-per-cell 25
"""

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent dirs to path
FLOOD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FLOOD_DIR))

from survey.balanced_sampler import BalancedSampler
from generate_agents import (
    HouseholdProfile,
    generate_rcv,
    save_agents_to_csv,
)


def assign_flood_zones(
    profiles: list,
    mg_flood_prone_pct: float = 0.70,
    nmg_flood_prone_pct: float = 0.50,
    rng: random.Random = None,
) -> list:
    """Assign flood zones based on MG status (MG more likely flood-prone).

    Per Paper 3 design:
    - MG agents: ~70% in flood-prone areas (HIGH zone)
    - NMG agents: ~50% in flood-prone areas

    Also assigns approximate grid coordinates within PRB.
    """
    if rng is None:
        rng = random.Random(42)

    # PRB approximate grid dimensions (from .asc files)
    grid_cols, grid_rows = 457, 411

    for p in profiles:
        mg = p.mg if hasattr(p, "mg") else p.get("mg", False)
        flood_prone_pct = mg_flood_prone_pct if mg else nmg_flood_prone_pct

        if rng.random() < flood_prone_pct:
            p_zone = "HIGH"
            p_depth = round(rng.uniform(0.5, 3.0), 3)
        elif rng.random() < 0.6:
            p_zone = "MEDIUM"
            p_depth = round(rng.uniform(0.1, 0.5), 3)
        else:
            p_zone = "LOW"
            p_depth = 0.0

        # Assign approximate grid location
        gx = rng.randint(0, grid_cols - 1)
        gy = rng.randint(0, grid_rows - 1)

        # PRB approximate lat/lon bounds
        lon = round(-74.45 + (gx / grid_cols) * 0.25, 6)
        lat = round(40.82 + (gy / grid_rows) * 0.15, 6)

        if hasattr(p, "flood_zone"):
            p.flood_zone = p_zone
            p.flood_depth = p_depth
            p.grid_x = gx
            p.grid_y = gy
            p.longitude = lon
            p.latitude = lat
        elif isinstance(p, dict):
            p["flood_zone"] = p_zone
            p["flood_depth"] = p_depth
            p["grid_x"] = gx
            p["grid_y"] = gy
            p["longitude"] = lon
            p["latitude"] = lat

    return profiles


def generate_initial_memory(profile: HouseholdProfile) -> list:
    """Generate 6 initial memories from survey-derived agent profile.

    Memory categories:
    1. flood_experience: Personal flood history
    2. insurance_history: Insurance awareness/status
    3. social_connections: Neighbor/community interactions
    4. government_trust: Trust in institutions
    5. place_attachment: Connection to home/community
    6. flood_zone: Risk awareness
    """
    memories = []
    mg_label = "marginalized" if profile.mg else "non-marginalized"
    tenure_label = "homeowner" if profile.tenure == "Owner" else "renter"

    # 1. Flood experience memory
    if profile.flood_experience:
        timing = profile.recent_flood_text if profile.recent_flood_text and profile.recent_flood_text != "nan" else "in past years"
        content = (
            f"I experienced flooding at my home {timing}. "
            f"{'The damage was significant and caused financial stress.' if profile.mg else 'I managed to recover, though it was disruptive.'} "
            f"This experience stays with me when I think about flood risks."
        )
        importance = 0.8
    else:
        content = (
            f"I have not personally experienced flooding at my current home, "
            f"though I{'am aware my area is in a flood zone' if profile.sfha_awareness else ' am not sure about my flood risk'}."
        )
        importance = 0.3
    memories.append({
        "content": content,
        "category": "flood_experience",
        "importance": importance,
        "source": "survey",
    })

    # 2. Insurance history
    ins_type = profile.insurance_type if profile.insurance_type and profile.insurance_type != "nan" else ""
    if "NFIP" in ins_type or "insurance" in ins_type.lower():
        content = f"I have {ins_type} flood insurance for my property."
        importance = 0.6
    elif "None" in ins_type or not ins_type:
        content = (
            f"I do not currently have flood insurance. "
            f"{'The premiums seem expensive relative to my income.' if profile.mg else 'I have been considering whether it is worth the cost.'}"
        )
        importance = 0.5
    else:
        content = f"My insurance situation: {ins_type}."
        importance = 0.5
    memories.append({
        "content": content,
        "category": "insurance_history",
        "importance": importance,
        "source": "survey",
    })

    # 3. Social connections (based on SC score)
    if profile.sc_score >= 4.0:
        content = "I have strong connections with my neighbors. We look out for each other and share information about community matters."
        importance = 0.7
    elif profile.sc_score >= 3.0:
        content = "I know some of my neighbors and we occasionally talk about local issues."
        importance = 0.5
    else:
        content = "I mostly keep to myself and don't interact much with neighbors."
        importance = 0.4
    memories.append({
        "content": content,
        "category": "social_connections",
        "importance": importance,
        "source": "survey",
    })

    # 4. Government trust (based on SP score)
    if profile.sp_score >= 4.0:
        content = "I trust that government programs like Blue Acres and FEMA can help people recover from floods."
        importance = 0.6
    elif profile.sp_score >= 3.0:
        content = "I have mixed feelings about government flood assistance programs."
        importance = 0.5
    else:
        content = (
            f"I don't have much faith in government flood programs. "
            f"{'Past experience has shown they are slow to respond to communities like mine.' if profile.mg else 'The process seems bureaucratic and unreliable.'}"
        )
        importance = 0.7
    memories.append({
        "content": content,
        "category": "government_trust",
        "importance": importance,
        "source": "survey",
    })

    # 5. Place attachment (based on PA score)
    gen_text = f"{profile.generations} generation{'s' if profile.generations > 1 else ''}"
    if profile.pa_score >= 4.0:
        content = f"This community is my home. My family has been here for {gen_text}. I cannot imagine living anywhere else."
        importance = 0.7
    elif profile.pa_score >= 3.0:
        content = f"I have been living here for {gen_text}. I feel comfortable but could see moving if necessary."
        importance = 0.5
    else:
        content = f"I am a {tenure_label} here but don't feel strongly tied to this specific location."
        importance = 0.4
    memories.append({
        "content": content,
        "category": "place_attachment",
        "importance": importance,
        "source": "survey",
    })

    # 6. Flood zone awareness
    if profile.flood_zone == "HIGH":
        content = f"My property is in a high-risk flood zone. {'I know this area floods regularly.' if profile.sfha_awareness else 'I recently learned this is a Special Flood Hazard Area.'}"
        importance = 0.7
    elif profile.flood_zone == "MEDIUM":
        content = "My area has moderate flood risk. Some nearby areas flood but my specific location has been mostly safe."
        importance = 0.5
    else:
        content = "My property is in a low-risk area for flooding."
        importance = 0.3
    memories.append({
        "content": content,
        "category": "flood_zone",
        "importance": importance,
        "source": "survey",
    })

    return memories


def prepare_balanced_agents(
    survey_csv: str,
    output_dir: str,
    n_per_cell: int = 25,
    seed: int = 42,
):
    """Full pipeline: survey → balanced sample → profiles + memories."""
    rng = random.Random(seed)
    np.random.seed(seed)

    # Step 1: Load full survey data
    print(f"[Step 1] Loading survey data from {survey_csv}")
    df = pd.read_csv(survey_csv)
    profiles_dict = df.to_dict("records")
    print(f"  Loaded {len(profiles_dict)} respondents")

    # Step 2: Balanced sampling
    print(f"\n[Step 2] Balanced sampling ({n_per_cell} per cell)")
    sampler = BalancedSampler(n_per_cell=n_per_cell, seed=seed, allow_oversample=True)
    result = sampler.sample(profiles_dict, seed=seed)
    sampled = result.profiles
    print(f"  Sampled {len(sampled)} profiles")
    print(f"  Cell counts: {result.cell_counts}")
    if result.shortfalls:
        print(f"  [WARN] Shortfalls: {result.shortfalls}")

    # Step 3: Create HouseholdProfile objects with RCV
    print(f"\n[Step 3] Generating agent profiles with RCV")
    agents = []
    for idx, row in enumerate(sampled):
        agent_id = f"H{idx+1:04d}"
        tenure = row.get("tenure", "Owner")
        income = float(row.get("income", 50000))
        mg = bool(row.get("mg", False))
        rcv_bld, rcv_cnt = generate_rcv(tenure, income, mg)

        insurance_type = str(row.get("insurance_type", ""))
        has_insurance = "flood" in insurance_type.lower() or "nfip" in insurance_type.lower()

        profile = HouseholdProfile(
            agent_id=agent_id,
            survey_id=str(row.get("survey_id", "")),
            tract_id="PRB",
            mg=mg,
            tenure=tenure,
            income_bracket=str(row.get("income_bracket", "")),
            income=income,
            household_size=int(row.get("household_size", 3)),
            generations=int(row.get("generations", 1)),
            has_vehicle=bool(row.get("has_vehicle", True)),
            has_children=bool(row.get("has_children", False)),
            has_elderly=bool(row.get("has_elderly", False)),
            housing_cost_burden=bool(row.get("housing_cost_burden", False)),
            mg_criteria_met=bool(row.get("mg_criteria_met", False)),
            zipcode=str(row.get("zipcode", "")),
            flood_experience=bool(row.get("flood_experience", False)),
            flood_frequency=int(row.get("flood_frequency", 0)),
            sfha_awareness=bool(row.get("sfha_awareness", False)),
            sc_score=float(row.get("sc_score", 3.0)),
            pa_score=float(row.get("pa_score", 3.0)),
            tp_score=float(row.get("tp_score", 3.0)),
            cp_score=float(row.get("cp_score", 3.0)),
            sp_score=float(row.get("sp_score", 3.0)),
            rcv_building=rcv_bld,
            rcv_contents=rcv_cnt,
            elevated=False,
            has_insurance=has_insurance,
            relocated=False,
            cumulative_damage=0.0,
            cumulative_oop=0.0,
            recent_flood_text=str(row.get("recent_flood_text", "")),
            insurance_type=insurance_type,
            post_flood_action=str(row.get("post_flood_action", "")),
        )
        agents.append(profile)

    # Step 4: Assign flood zones
    print(f"\n[Step 4] Assigning flood zones (MG: 70% flood-prone, NMG: 50%)")
    agents = assign_flood_zones(agents, rng=rng)

    # Step 5: Save agent profiles
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profiles_path = out_dir / "agent_profiles_balanced.csv"
    save_agents_to_csv(agents, profiles_path)

    # Step 6: Generate initial memories
    print(f"\n[Step 6] Generating initial memories (6 per agent)")
    all_memories = {}
    for agent in agents:
        mems = generate_initial_memory(agent)
        all_memories[agent.agent_id] = mems

    memories_path = out_dir / "initial_memories_balanced.json"
    with open(memories_path, "w", encoding="utf-8") as f:
        json.dump(all_memories, f, indent=2, ensure_ascii=False)
    print(f"  Saved {sum(len(v) for v in all_memories.values())} memories to {memories_path}")

    # Summary
    zones = [a.flood_zone for a in agents]
    print(f"\n{'='*60}")
    print(f"  Paper 3 Agent Preparation Complete (seed={seed})")
    print(f"{'='*60}")
    print(f"  Total agents: {len(agents)}")
    print(f"  MG-Owner (Cell A): {sum(1 for a in agents if a.mg and a.tenure == 'Owner')}")
    print(f"  MG-Renter (Cell B): {sum(1 for a in agents if a.mg and a.tenure == 'Renter')}")
    print(f"  NMG-Owner (Cell C): {sum(1 for a in agents if not a.mg and a.tenure == 'Owner')}")
    print(f"  NMG-Renter (Cell D): {sum(1 for a in agents if not a.mg and a.tenure == 'Renter')}")
    print(f"  Flood-prone (HIGH): {zones.count('HIGH')} ({zones.count('HIGH')/len(zones)*100:.0f}%)")
    print(f"  Files:")
    print(f"    {profiles_path}")
    print(f"    {memories_path}")

    return agents, all_memories


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paper 3: Balanced Agent Preparation")
    parser.add_argument("--survey", type=str, default=None,
                        help="Path to cleaned_survey_full.csv")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory for profiles and memories")
    parser.add_argument("--n-per-cell", type=int, default=25,
                        help="Agents per cell (default: 25)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")
    args = parser.parse_args()

    # Default paths
    if args.survey is None:
        args.survey = str(FLOOD_DIR / "data" / "cleaned_survey_full.csv")
    if args.output_dir is None:
        args.output_dir = str(FLOOD_DIR / "data")

    prepare_balanced_agents(
        survey_csv=args.survey,
        output_dir=args.output_dir,
        n_per_cell=args.n_per_cell,
        seed=args.seed,
    )
