"""
Initial Memory Generator

Generates 5 initial memories per household agent based on survey responses:
1. Flood experience memory (Q14, Q15, Q17)
2. Insurance awareness memory (Q23)
3. Social/neighbor observation (based on SC score)
4. Government interaction (Q18, SP score)
5. Place attachment (PA score, generations)

Memory Categories:
- flood_event: Direct flood experience
- insurance_claim: NFIP/insurance interactions
- social_interaction: Neighbor discussions
- government_notice: NJDEP/Blue Acres/FEMA notices
- adaptation_action: Adaptation decisions and outcomes

References:
- SM_clean_vr.docx: PMT construct mapping
- ABM_Summary.pdf: Memory system design
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import json

# Configuration
DATA_DIR = Path(__file__).parent / "data"
SEED = 42


@dataclass
class Memory:
    """Memory entry structure."""
    content: str
    category: str
    importance: float
    source: str = "survey"  # "survey", "simulation", "social"
    year: int = 0  # Simulation year (0 = initial)


# ============================================================================
# MEMORY TEMPLATES
# ============================================================================

def generate_flood_experience_memory(
    flood_experience: bool,
    flood_frequency: int,
    recent_flood_text: str,
    flood_zone: str
) -> Memory:
    """
    Generate memory #1: Flood experience.

    Based on Q14 (flood experience), Q15 (recent flood timing), Q17 (frequency).
    """
    if flood_experience:
        # Experienced flooding
        freq_text = {
            0: "once",
            1: "once",
            2: "twice",
            3: "three times",
            4: "four times",
            5: "five or more times"
        }.get(flood_frequency, "multiple times")

        timing = recent_flood_text if recent_flood_text else "in the past"

        content = (
            f"I have experienced flooding at my home {freq_text}. "
            f"The most recent flood event was {timing}. "
            f"Living in a {flood_zone.lower()} risk zone, I understand the real threat floods pose to my property."
        )
        importance = min(0.9, 0.7 + flood_frequency * 0.05)
    else:
        # No direct experience
        content = (
            f"I have not personally experienced flooding at my current address. "
            f"However, I am aware that I live in an area classified as {flood_zone.lower()} flood risk "
            f"based on FEMA flood maps."
        )
        importance = 0.5

    return Memory(
        content=content,
        category="flood_event",
        importance=round(importance, 2)
    )


def generate_insurance_memory(
    insurance_type: str,
    sfha_awareness: bool,
    tenure: str
) -> Memory:
    """
    Generate memory #2: Insurance awareness.

    Based on Q23 (insurance type), Q7 (SFHA awareness).
    """
    insurance_lower = str(insurance_type).lower()

    if "national flood" in insurance_lower or "nfip" in insurance_lower:
        content = (
            "I have flood insurance through the National Flood Insurance Program (NFIP) "
            "administered by FEMA. The premium is based on my property's flood risk "
            "under the Risk Rating 2.0 methodology."
        )
        importance = 0.75
    elif "private" in insurance_lower:
        content = (
            "I have private flood insurance coverage separate from the NFIP. "
            "I chose this option after comparing rates and coverage options."
        )
        importance = 0.7
    elif sfha_awareness:
        if tenure == "Owner":
            content = (
                "I know my property is in a Special Flood Hazard Area (SFHA) and flood insurance "
                "may be required for my mortgage. I have considered purchasing NFIP coverage "
                "but have not yet done so."
            )
        else:
            content = (
                "I am aware that this rental is in a flood-prone area. "
                "I should consider getting renters flood insurance to protect my belongings, "
                "but I haven't purchased a policy yet."
            )
        importance = 0.6
    else:
        content = (
            "I am aware that FEMA offers flood insurance through the NFIP program. "
            "I do not currently have flood insurance but have seen information about it."
        )
        importance = 0.5

    return Memory(
        content=content,
        category="insurance_claim",
        importance=round(importance, 2)
    )


def generate_social_memory(
    sc_score: float,
    flood_experience: bool,
    mg: bool
) -> Memory:
    """
    Generate memory #3: Social/neighbor observation.

    Based on SC (Social Capital) score from Q21_1-6.
    """
    if sc_score >= 4.0:
        # High social capital
        if flood_experience:
            content = (
                "My community has strong social ties. After the last flood, neighbors helped "
                "each other with cleanup and shared information about recovery resources. "
                "Several families have discussed elevating their homes or other protective measures."
            )
        else:
            content = (
                "I have good relationships with my neighbors. We often discuss community issues "
                "including flood preparedness. Some neighbors have taken adaptation measures "
                "like elevating their homes or installing sump pumps."
            )
        importance = 0.75
    elif sc_score >= 3.0:
        # Moderate social capital
        content = (
            "I occasionally interact with neighbors about local issues. "
            "There have been some community meetings about flood risks, but attendance varies. "
            "A few neighbors have flood insurance or have made home improvements."
        )
        importance = 0.55
    else:
        # Low social capital
        if mg:
            content = (
                "I don't interact much with neighbors about flood issues. "
                "Information about assistance programs doesn't always reach our community. "
                "I mostly rely on my own research for flood preparedness information."
            )
        else:
            content = (
                "I keep to myself and don't discuss flood risks with neighbors much. "
                "I occasionally see FEMA or local government flyers about flood preparedness."
            )
        importance = 0.4

    return Memory(
        content=content,
        category="social_interaction",
        importance=round(importance, 2)
    )


def generate_government_memory(
    sp_score: float,
    flood_experience: bool,
    post_flood_action: str,
    mg: bool
) -> Memory:
    """
    Generate memory #4: Government interaction.

    Based on SP (Stakeholder Perception) score and post-flood actions (Q19).
    """
    received_assistance = "assistance" in str(post_flood_action).lower() or \
                         "government" in str(post_flood_action).lower()

    if received_assistance:
        content = (
            "After experiencing flooding, I received government assistance. "
            "The NJ Department of Environmental Protection (NJDEP) runs the Blue Acres "
            "buyout program for flood-prone properties. FEMA also provided disaster relief "
            "information. The process was lengthy but helpful."
        )
        importance = 0.8
    elif sp_score >= 3.5:
        # Trust government
        content = (
            "The New Jersey state government and FEMA provide resources for flood mitigation. "
            "NJDEP administers the Blue Acres program which offers voluntary buyouts for "
            "repetitive loss properties. I believe these programs genuinely aim to help residents."
        )
        importance = 0.65
    elif sp_score >= 2.5:
        # Neutral toward government
        content = (
            "I am aware of government flood mitigation programs like NJ Blue Acres and FEMA's "
            "mitigation grants. However, I'm not sure how effective or accessible these programs "
            "really are for homeowners like me."
        )
        importance = 0.55
    else:
        # Low trust in government
        if mg:
            content = (
                "Government flood programs like Blue Acres exist, but historically our community "
                "has not always benefited equally from such assistance. I'm skeptical that these "
                "programs will prioritize our neighborhood's needs."
            )
        else:
            content = (
                "I've heard about government buyout and elevation programs, but I'm not convinced "
                "they work in practice. Bureaucracy and delays make these programs less appealing."
            )
        importance = 0.5

    return Memory(
        content=content,
        category="government_notice",
        importance=round(importance, 2)
    )


def generate_place_attachment_memory(
    pa_score: float,
    generations: int,
    tenure: str,
    mg: bool
) -> Memory:
    """
    Generate memory #5: Place attachment.

    Based on PA (Place Attachment) score from Q21_7-15 and generations in area.
    """
    gen_text = {
        1: "I am the first generation",
        2: "My family has lived here for two generations",
        3: "My family has lived here for three generations",
        4: "My family has been rooted here for four or more generations"
    }.get(generations, "I live")

    if pa_score >= 4.0:
        # High place attachment
        if generations >= 2:
            content = (
                f"{gen_text} in this community. I have deep emotional ties to this place - "
                f"family memories, established relationships, and a sense of belonging. "
                f"Leaving would mean losing a part of my identity. I would rather adapt in place "
                f"than relocate, even with flood risks."
            )
        else:
            content = (
                "Even though I haven't lived here long, I feel a strong connection to this community. "
                "The neighborhood, local amenities, and my daily routines are important to me. "
                "I want to stay and make this place work despite the flood challenges."
            )
        importance = 0.8
    elif pa_score >= 3.0:
        # Moderate place attachment
        content = (
            f"{gen_text} in this area. I consider it my home and feel comfortable here, "
            f"though I recognize I could potentially adapt to living elsewhere if necessary. "
            f"The decision to stay or leave would depend on many factors beyond just flood risk."
        )
        importance = 0.6
    else:
        # Low place attachment
        if tenure == "Renter":
            content = (
                "I live in this area primarily for practical reasons like work or affordability. "
                "As a renter, I have more flexibility to relocate if flood risks become too high. "
                "I don't have strong roots tying me to this specific location."
            )
        else:
            content = (
                "I live here mainly for practical reasons - proximity to work, schools, or affordability. "
                "If a good opportunity came up to move to a lower-risk area, I would seriously consider it."
            )
        importance = 0.5

    return Memory(
        content=content,
        category="adaptation_action",
        importance=round(importance, 2)
    )


# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def generate_initial_memories(agent_row: pd.Series) -> List[Memory]:
    """
    Generate 5 initial memories for a household agent.

    Args:
        agent_row: Row from agent_profiles.csv with all profile data

    Returns:
        List of 5 Memory objects
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
                       "adaptation_action": 0}

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
