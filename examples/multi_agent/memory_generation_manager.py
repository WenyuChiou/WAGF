"""
Memory Generation Manager

This module orchestrates the generation of initial memories for agents
and provides utilities for formatting and saving these memories.
It acts as the main entry point for memory generation scripts.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import json

# Import necessary components from other modules
from .memory_dataclass import Memory
from .memory_generators import (
    generate_flood_experience_memory,
    generate_insurance_memory,
    generate_social_memory,
    generate_government_memory,
    generate_place_attachment_memory,
    generate_flood_zone_memory
)

# Configuration
DATA_DIR = Path(__file__).parent / "data"
SEED = 42


# ============================================================================ 
# MAIN FUNCTIONS
# ============================================================================ 

def generate_initial_memories(agent_row: pd.Series) -> List[Memory]:
    """
    Generate 6 initial memories for a household agent.

    Memory categories:
    1. Flood experience (Q14, Q15, Q17)
    2. Insurance awareness (Q23)
    3. Social/neighbor observation (SC score)
    4. Government interaction (SP score)
    5. Place attachment (PA score)
    6. Flood zone risk awareness (FEMA maps, Q7)

    Args:
        agent_row: Row from agent_profiles.csv with all profile data

    Returns:
        List of 6 Memory objects
    """
    memories = []

    # Extract agent attributes
    flood_experience = bool(agent_row.get("flood_experience", False))
    flood_frequency = int(agent_row.get("flood_frequency", 0))
    recent_flood_text = str(agent_row.get("recent_flood_text", ""))
    flood_zone = str(agent_row.get("flood_zone", "MEDIUM"))
    insurance_type = str(agent_row.get("insurance_type", ""))
    sfha_awareness = bool(agent_row.get("sfha_awareness", False))
    tenure = str(agent_row.get("tenure", "Owner"))
    sc_score = float(agent_row.get("sc_score", 3.0))
    pa_score = float(agent_row.get("pa_score", 3.0))
    sp_score = float(agent_row.get("sp_score", 3.0))
    generations = int(agent_row.get("generations", 1))
    mg = bool(agent_row.get("mg", False))
    post_flood_action = str(agent_row.get("post_flood_action", ""))

    # Memory 1: Flood experience
    memories.append(generate_flood_experience_memory(
        flood_experience, flood_frequency, recent_flood_text, flood_zone
    ))

    # Memory 2: Insurance awareness
    memories.append(generate_insurance_memory(
        insurance_type, sfha_awareness, tenure
    ))

    # Memory 3: Social/neighbor observation
    memories.append(generate_social_memory(
        sc_score, flood_experience, mg
    ))

    # Memory 4: Government interaction
    memories.append(generate_government_memory(
        sp_score, flood_experience, post_flood_action, mg
    ))

    # Memory 5: Place attachment
    memories.append(generate_place_attachment_memory(
        pa_score, generations, tenure, mg
    ))

    # Memory 6: Flood zone risk awareness
    memories.append(generate_flood_zone_memory(
        flood_zone, sfha_awareness, tenure
    ))

    return memories


def generate_all_memories(
    agents_csv: Optional[Path] = None,
    output_json: Optional[Path] = None
) -> Dict[str, List[Dict]]:
    """
    Generate initial memories for all agents.

    Args:
        agents_csv: Path to agent_profiles.csv
        output_json: Path for output JSON file

    Returns:
        Dictionary mapping agent_id to list of memories
    """
    if agents_csv is None:
        agents_csv = DATA_DIR / "agent_profiles.csv"
    if output_json is None:
        output_json = DATA_DIR / "initial_memories.json"

    print(f"[INFO] Loading agents from {agents_csv}")
    df = pd.read_csv(agents_csv)

    all_memories = {}
    category_counts = {"flood_event": 0, "insurance_claim": 0,
                       "social_interaction": 0, "government_notice": 0,
                       "adaptation_action": 0, "risk_awareness": 0}

    for idx, row in df.iterrows():
        agent_id = row.get("agent_id", f"H{idx+1:04d}")
        memories = generate_initial_memories(row)

        all_memories[agent_id] = [asdict(m) for m in memories]

        for m in memories:
            category_counts[m.category] += 1

    # Save to JSON
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_memories, f, indent=2, ensure_ascii=False)

    print(f"[OK] Generated {len(df) * 5} memories for {len(df)} agents")
    print(f"[OK] Saved to {output_json}")

    print(f"\n=== Memory Category Summary ===")
    for cat, count in category_counts.items():
        print(f"  {cat}: {count}")

    return all_memories


def get_agent_memories_text(agent_id: str, memories_dict: Dict) -> str:
    """
    Format agent memories as text for prompt injection.

    Args:
        agent_id: Agent identifier (e.g., "H0001")
        memories_dict: Dictionary from generate_all_memories()

    Returns:
        Formatted text of memories
    """
    if agent_id not in memories_dict:
        return "No prior memories recorded."

    lines = ["Your relevant memories and experiences:"]
    for i, mem in enumerate(memories_dict[agent_id], 1):
        importance = mem.get("importance", 0.5)
        category = mem.get("category", "general")
        content = mem.get("content", "")

        # Format with importance indicator
        if importance >= 0.7:
            strength = "[Strong memory]"
        elif importance >= 0.5:
            strength = "[Moderate memory]"
        else:
            strength = "[Faint memory]"

        lines.append(f"\n{i}. {strength} ({category})")
        lines.append(f"   {content}")

    return "\n".join(lines)


# ============================================================================ 
# MAIN
# ============================================================================ 

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate initial memories for agents")
    parser.add_argument("--agents", type=str, default=None, help="Input agent profiles CSV")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    agents_csv = Path(args.agents) if args.agents else None
    output_json = Path(args.output) if args.output else None

    memories = generate_all_memories(agents_csv, output_json)

    # Show sample
    sample_agent = list(memories.keys())[0]
    print(f"\n=== Sample memories for {sample_agent} ===")
    print(get_agent_memories_text(sample_agent, memories))