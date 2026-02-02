"""
Memory template generation for agent initialization (flood domain).

Generates seed memories from survey-derived agent profiles for flood
adaptation experiments.  Domain-specific to the flood/household use case.
For new domains, create a parallel template provider following the same
MemoryTemplate dataclass structure.

Moved from examples/multi_agent/memory/templates.py for SA/MA reuse.
"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class MemoryTemplate:
    """Generated memory with metadata."""
    content: str
    category: str
    emotion: str = "neutral"
    source: str = "personal"


class MemoryTemplateProvider:
    """
    Provides seed memory templates for the flood adaptation domain.

    Generates first-person memories from survey-derived agent profiles.
    New domains should create a parallel provider class.

    Categories:
    - flood_event: Direct flood experience
    - insurance_claim: Insurance interactions
    - social_interaction: Neighbor discussions
    - government_notice: Government communications
    - adaptation_action: Past adaptation decisions
    - risk_awareness: Flood zone awareness
    """

    @staticmethod
    def flood_experience(profile: Dict[str, Any]) -> MemoryTemplate:
        flood_experience = bool(profile.get("flood_experience", False))
        flood_frequency = int(profile.get("flood_frequency", 0))
        recent_flood_text = str(profile.get("recent_flood_text", ""))
        flood_zone = str(profile.get("flood_zone", "MEDIUM"))

        if flood_experience:
            freq_text = {
                0: "once",
                1: "once",
                2: "twice",
                3: "three times",
                4: "four times",
                5: "five or more times",
            }.get(flood_frequency, "multiple times")
            timing = recent_flood_text if recent_flood_text else "in the past"
            content = (
                f"I have experienced flooding at my home {freq_text}. "
                f"The most recent flood event was {timing}. "
                f"Living in a {flood_zone.lower()} risk zone, I understand the real threat floods pose to my property."
            )
            return MemoryTemplate(
                content=content,
                category="flood_event",
                emotion="major",
                source="personal",
            )

        content = (
            f"I have not personally experienced flooding at my current address. "
            f"However, I am aware that I live in an area classified as {flood_zone.lower()} flood risk "
            f"based on FEMA flood maps."
        )
        return MemoryTemplate(
            content=content,
            category="flood_event",
            emotion="neutral",
            source="personal",
        )

    @staticmethod
    def insurance_interaction(profile: Dict[str, Any]) -> MemoryTemplate:
        insurance_type = str(profile.get("insurance_type", ""))
        sfha_awareness = bool(profile.get("sfha_awareness", False))
        tenure = str(profile.get("tenure", "Owner"))

        insurance_lower = insurance_type.lower()
        if "national flood" in insurance_lower or "nfip" in insurance_lower:
            content = (
                "I have flood insurance through the National Flood Insurance Program (NFIP) "
                "administered by FEMA. The premium is based on my property's flood risk "
                "under the Risk Rating 2.0 methodology."
            )
            emotion = "minor"
        elif "private" in insurance_lower:
            content = (
                "I have private flood insurance coverage separate from the NFIP. "
                "I chose this option after comparing rates and coverage options."
            )
            emotion = "minor"
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
            emotion = "neutral"
        else:
            content = (
                "I am aware that FEMA offers flood insurance through the NFIP program. "
                "I do not currently have flood insurance but have seen information about it."
            )
            emotion = "neutral"

        return MemoryTemplate(
            content=content,
            category="insurance_claim",
            emotion=emotion,
            source="personal",
        )

    @staticmethod
    def social_interaction(profile: Dict[str, Any]) -> MemoryTemplate:
        sc_score = float(profile.get("sc_score", 3.0))
        flood_experience = bool(profile.get("flood_experience", False))
        mg = bool(profile.get("mg", False))

        if sc_score >= 4.0:
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
        elif sc_score >= 3.0:
            content = (
                "I occasionally interact with neighbors about local issues. "
                "There have been some community meetings about flood risks, but attendance varies. "
                "A few neighbors have flood insurance or have made home improvements."
            )
        else:
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

        return MemoryTemplate(
            content=content,
            category="social_interaction",
            emotion="neutral",
            source="neighbor",
        )

    @staticmethod
    def government_notice(profile: Dict[str, Any]) -> MemoryTemplate:
        sp_score = float(profile.get("sp_score", 3.0))
        flood_experience = bool(profile.get("flood_experience", False))
        post_flood_action = str(profile.get("post_flood_action", ""))
        mg = bool(profile.get("mg", False))

        received_assistance = (
            "assistance" in post_flood_action.lower()
            or "government" in post_flood_action.lower()
        )

        if received_assistance:
            content = (
                "After experiencing flooding, I received government assistance. "
                "The NJ Department of Environmental Protection (NJDEP) runs the Blue Acres "
                "buyout program for flood-prone properties. FEMA also provided disaster relief "
                "information. The process was lengthy but helpful."
            )
        elif sp_score >= 3.5:
            content = (
                "The New Jersey state government and FEMA provide resources for flood mitigation. "
                "NJDEP administers the Blue Acres program which offers voluntary buyouts for "
                "repetitive loss properties. I believe these programs genuinely aim to help residents."
            )
        elif sp_score >= 2.5:
            content = (
                "I am aware of government flood mitigation programs like NJ Blue Acres and FEMA's "
                "mitigation grants. However, I'm not sure how effective or accessible these programs "
                "really are for homeowners like me."
            )
        else:
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

        return MemoryTemplate(
            content=content,
            category="government_notice",
            emotion="neutral",
            source="community",
        )

    @staticmethod
    def adaptation_action(profile: Dict[str, Any]) -> MemoryTemplate:
        pa_score = float(profile.get("pa_score", 3.0))
        generations = int(profile.get("generations", 1))
        tenure = str(profile.get("tenure", "Owner"))
        mg = bool(profile.get("mg", False))

        gen_text = {
            1: "I am the first generation",
            2: "My family has lived here for two generations",
            3: "My family has lived here for three generations",
            4: "My family has been rooted here for four or more generations",
        }.get(generations, "I live")

        if pa_score >= 4.0:
            if generations >= 2:
                content = (
                    f"{gen_text} in this community. I have deep emotional ties to this place - "
                    "family memories, established relationships, and a sense of belonging. "
                    "Leaving would mean losing a part of my identity. I would rather adapt in place "
                    "than relocate, even with flood risks."
                )
            else:
                content = (
                    "Even though I haven't lived here long, I feel a strong connection to this community. "
                    "The neighborhood, local amenities, and my daily routines are important to me. "
                    "I want to stay and make this place work despite the flood challenges."
                )
        elif pa_score >= 3.0:
            content = (
                f"{gen_text} in this area. I consider it my home and feel comfortable here, "
                "though I recognize I could potentially adapt to living elsewhere if necessary. "
                "The decision to stay or leave would depend on many factors beyond just flood risk."
            )
        else:
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

        return MemoryTemplate(
            content=content,
            category="adaptation_action",
            emotion="neutral",
            source="personal",
        )

    @staticmethod
    def risk_awareness(profile: Dict[str, Any]) -> MemoryTemplate:
        flood_zone = str(profile.get("flood_zone", "MEDIUM"))
        sfha_awareness = bool(profile.get("sfha_awareness", False))
        tenure = str(profile.get("tenure", "Owner"))

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
            f"flood risk zone classified as {flood_zone}",
        )

        high_risk_zones = ["AE", "VE", "A", "AO", "AH", "HIGH"]
        is_high_risk = flood_zone.upper() in high_risk_zones

        if is_high_risk and sfha_awareness:
            content = (
                f"I am aware that my property is located in a {zone_text}. "
                "According to FEMA flood maps, I face significant flood risk. "
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
        elif is_high_risk and not sfha_awareness:
            content = (
                "I live in an area that may be at risk of flooding. "
                "I'm not entirely sure about the official flood zone classification, "
                "but I've heard this neighborhood has experienced floods before."
            )
        elif sfha_awareness:
            content = (
                f"I've checked the FEMA flood maps and my property is in a {zone_text}. "
                "While not in a high-risk zone, I understand that floods can still occur "
                "outside designated flood zones."
            )
        else:
            content = (
                f"I live in what I believe is a {zone_text}. "
                "I haven't looked closely at FEMA flood maps, but the area seems "
                "relatively safe from major flooding."
            )

        return MemoryTemplate(
            content=content,
            category="risk_awareness",
            emotion="neutral",
            source="community",
        )

    @classmethod
    def generate_all(cls, profile: Dict[str, Any]) -> List[MemoryTemplate]:
        return [
            cls.flood_experience(profile),
            cls.insurance_interaction(profile),
            cls.social_interaction(profile),
            cls.government_notice(profile),
            cls.adaptation_action(profile),
            cls.risk_awareness(profile),
        ]
