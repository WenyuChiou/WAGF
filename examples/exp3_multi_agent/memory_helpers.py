"""
Memory Helpers - Skill-based and Event-based Memory Updates

This module provides helper functions for updating agent memory based on:
1. Skill execution (decisions)
2. Environment events (floods, claims)

These are meant to be called from run_experiment.py after actions/events.
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass

# Import from broker
import sys
sys.path.insert(0, '.')
from broker.memory import CognitiveMemory, MemoryItem


# =============================================================================
# SKILL → MEMORY MAPPING
# =============================================================================

SKILL_MEMORY_MAP = {
    "buy_insurance": {
        "template": "Year {year}: I purchased flood insurance (premium: ${premium:.0f})",
        "template_simple": "Year {year}: I purchased flood insurance",
        "importance": 0.7,
        "tags": ["decision", "insurance"]
    },
    "elevate_house": {
        "template": "Year {year}: I elevated my house with {subsidy_pct:.0%} subsidy",
        "template_simple": "Year {year}: I elevated my house",
        "importance": 0.8,
        "tags": ["decision", "elevation"]
    },
    "relocate": {
        "template": "Year {year}: I relocated to a safer area",
        "template_simple": "Year {year}: I relocated to a safer area",
        "importance": 0.9,
        "tags": ["decision", "relocation"]
    },
    "do_nothing": {
        "template": "Year {year}: I chose to wait and not take protective action",
        "template_simple": "Year {year}: I chose to wait",
        "importance": 0.3,
        "tags": ["decision", "inaction"]
    }
}


def update_memory_from_skill(
    memory: CognitiveMemory,
    skill_id: str,
    year: int,
    context: Optional[Dict[str, Any]] = None
) -> Optional[MemoryItem]:
    """
    Add memory based on skill (decision) executed.
    
    Args:
        memory: Agent's cognitive memory
        skill_id: The decision/skill ID (e.g., 'buy_insurance')
        year: Simulation year
        context: Optional context dict with skill parameters
                (e.g., {'premium': 1200, 'subsidy_pct': 0.5})
    
    Returns:
        MemoryItem if added, None if skill not found
    """
    config = SKILL_MEMORY_MAP.get(skill_id)
    if not config:
        return None
    
    # Try to use full template with context, fall back to simple
    try:
        if context:
            content = config["template"].format(year=year, **context)
        else:
            content = config["template_simple"].format(year=year)
    except KeyError:
        content = config["template_simple"].format(year=year)
    
    return memory.add_experience(
        content=content,
        importance=config["importance"],
        year=year,
        tags=config["tags"]
    )


# =============================================================================
# FLOOD EVENT → MEMORY
# =============================================================================

def update_memory_from_flood(
    memory: CognitiveMemory,
    flood_occurred: bool,
    damage: float,
    year: int
) -> Optional[MemoryItem]:
    """
    Add memory based on flood experience.
    
    Args:
        memory: Agent's cognitive memory
        flood_occurred: Whether flood occurred this year
        damage: Total damage to this agent
        year: Simulation year
    
    Returns:
        MemoryItem if added, None if no memory-worthy event
    """
    if damage > 0:
        # Damage occurred - significant event
        if damage > 50000:
            severity = "major"
            importance = 0.9
        elif damage > 10000:
            severity = "moderate"
            importance = 0.7
        else:
            severity = "minor"
            importance = 0.6
        
        content = f"Year {year}: A {severity} flood caused ${damage:,.0f} in damages to my home"
        return memory.add_episodic(
            content=content,
            importance=importance,
            year=year,
            tags=["flood", severity, "damage"]
        )
    
    elif flood_occurred:
        # Flood but no damage (maybe elevated or lucky)
        content = f"Year {year}: A flood occurred but my home was not damaged"
        return memory.add_working(
            content=content,
            importance=0.4,
            year=year,
            tags=["flood", "no_damage"]
        )
    
    return None


# =============================================================================
# INSURANCE CLAIM → MEMORY
# =============================================================================

def update_memory_from_claim(
    memory: CognitiveMemory,
    claim_filed: bool,
    claim_approved: bool,
    payout: float,
    damage: float,
    out_of_pocket: float,
    year: int
) -> Optional[MemoryItem]:
    """
    Add memory based on insurance claim experience.
    
    Args:
        memory: Agent's cognitive memory
        claim_filed: Whether a claim was filed
        claim_approved: Whether claim was approved
        payout: Insurance payout amount
        damage: Total damage amount
        out_of_pocket: Out-of-pocket payment
        year: Simulation year
    
    Returns:
        MemoryItem if added, None if no claim filed
    """
    if not claim_filed:
        return None
    
    if claim_approved:
        if payout > 0:
            coverage_pct = payout / damage if damage > 0 else 0
            if coverage_pct >= 0.8:
                content = f"Year {year}: Insurance fully covered my ${payout:,.0f} claim"
                importance = 0.7
            else:
                content = f"Year {year}: Insurance paid ${payout:,.0f} but I still owed ${out_of_pocket:,.0f}"
                importance = 0.75
            
            return memory.add_episodic(
                content=content,
                importance=importance,
                year=year,
                tags=["insurance", "claim", "approved"]
            )
    else:
        # Claim denied - very memorable
        content = f"Year {year}: My insurance claim was denied"
        return memory.add_episodic(
            content=content,
            importance=0.85,
            year=year,
            tags=["insurance", "claim", "denied"]
        )
    
    return None


# =============================================================================
# HIGH OUT-OF-POCKET → MEMORY
# =============================================================================

def update_memory_from_oop(
    memory: CognitiveMemory,
    out_of_pocket: float,
    year: int
) -> Optional[MemoryItem]:
    """
    Add memory for significant out-of-pocket expenses.
    
    Args:
        memory: Agent's cognitive memory
        out_of_pocket: Out-of-pocket payment amount
        year: Simulation year
    
    Returns:
        MemoryItem if OOP is significant, None otherwise
    """
    if out_of_pocket <= 5000:
        return None  # Not significant enough
    
    if out_of_pocket > 20000:
        content = f"Year {year}: I paid ${out_of_pocket:,.0f} out-of-pocket, a major financial burden"
        importance = 0.85
        tags = ["expense", "out_of_pocket", "major"]
    else:
        content = f"Year {year}: I paid ${out_of_pocket:,.0f} out-of-pocket for repairs"
        importance = 0.6
        tags = ["expense", "out_of_pocket"]
    
    return memory.add_experience(
        content=content,
        importance=importance,
        year=year,
        tags=tags
    )


# =============================================================================
# COMBINED: YEAR-END MEMORY UPDATE
# =============================================================================

def update_memory_after_year(
    memory: CognitiveMemory,
    year: int,
    decision: str,
    decision_context: Optional[Dict] = None,
    flood_occurred: bool = False,
    damage: float = 0.0,
    claim_filed: bool = False,
    claim_approved: bool = False,
    payout: float = 0.0,
    out_of_pocket: float = 0.0
) -> Dict[str, Optional[MemoryItem]]:
    """
    Update all memories at year end.
    
    This is the main function to call from run_experiment.py.
    
    Returns:
        Dict with keys: 'decision', 'flood', 'claim', 'oop'
    """
    results = {}
    
    # 1. Decision memory
    results['decision'] = update_memory_from_skill(
        memory, decision, year, decision_context
    )
    
    # 2. Flood memory
    results['flood'] = update_memory_from_flood(
        memory, flood_occurred, damage, year
    )
    
    # 3. Claim memory
    if claim_filed:
        results['claim'] = update_memory_from_claim(
            memory, claim_filed, claim_approved, payout, damage, out_of_pocket, year
        )
    else:
        results['claim'] = None
    
    # 4. OOP memory (only if not already covered by claim memory)
    if not claim_filed and out_of_pocket > 5000:
        results['oop'] = update_memory_from_oop(memory, out_of_pocket, year)
    else:
        results['oop'] = None
    
    return results
