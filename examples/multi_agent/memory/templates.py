from dataclasses import dataclass
from typing import List

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


def generate_flood_zone_memory(
    flood_zone: str,
    sfha_awareness: bool,
    tenure: str
) -> Memory:
    """
    Generate memory #6: Flood zone risk awareness.

    Based on FEMA flood zone classification and SFHA awareness (Q7).
    Real-world grounding: FEMA flood maps are publicly available, and
    households in SFHAs are often informed through mortgage requirements.

    Literature: PMC (2024) - Social vulnerability affects flood insurance uptake
    """
    # Map flood zones to human-readable descriptions
    zone_descriptions = {
        "AE": "high-risk Special Flood Hazard Area (SFHA) with base flood elevations",
        "VE": "very high-risk coastal flood zone with wave action",
        "A": "high-risk flood zone without detailed analysis",
        "AO": "shallow flooding area with sheet flow",
        "AH": "shallow flooding area with ponding",
        "X": "moderate to low risk zone outside the SFHA",
        "X500": "moderate risk zone with 0.2% annual chance of flooding",
        "HIGH": "high-risk flood area",
        "MEDIUM": "moderate flood risk area",
        "LOW": "low flood risk area",
    }

    zone_text = zone_descriptions.get(
        flood_zone.upper(),
        f"flood risk zone classified as {flood_zone}"
    )

    # High-risk zones
    high_risk_zones = ["AE", "VE", "A", "AO", "AH", "HIGH"]
    is_high_risk = flood_zone.upper() in high_risk_zones

    if is_high_risk and sfha_awareness:
        content = (
            f"I am aware that my property is located in a {zone_text}. "
            f"According to FEMA flood maps, I face significant flood risk. "
        )
        if tenure == "Owner":
            content += (
                "My mortgage lender informed me that flood insurance may be required. "
                "I should consider protective measures like elevation or flood-proofing."
            )
        else:
            content += (
                "As a renter, I should consider contents insurance to protect my belongings "
                "in case of flooding."
            )
        importance = 0.7
    elif is_high_risk and not sfha_awareness:
        content = (
            f"I live in an area that may be at risk of flooding. "
            f"I'm not entirely sure about the official flood zone classification, "
            f"but I've heard this neighborhood has experienced floods before."
        )
        importance = 0.55
    elif sfha_awareness:
        content = (
            f"I've checked the FEMA flood maps and my property is in a {zone_text}. "
            f"While not in a high-risk zone, I understand that floods can still occur "
            f"outside designated flood zones."
        )
        importance = 0.5
    else:
        content = (
            f"I live in what I believe is a {zone_text}. "
            f"I haven't looked closely at FEMA flood maps, but the area seems "
            f"relatively safe from major flooding."
        )
        importance = 0.4

    return Memory(
        content=content,
        category="risk_awareness",
        importance=round(importance, 2)
    )


# ============================================================================
