"""
Memory Helpers - Unified Interface

Single entry point: add_memory(memory, event_type, data, year)

Passive: Called automatically by environment/orchestrator
Active: memory.retrieve() called by agent as tool
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass

# Note: This module provides legacy MA-specific memory helpers
# For current memory engine API, use broker.components.memory_engine

# Try importing from the canonical location
try:
    from broker.components.memory_engine import HumanCentricMemoryEngine as CognitiveMemory
    # MemoryItem is now a dict in the new API - create stub for compatibility
    from dataclasses import dataclass as _dataclass
    @_dataclass
    class MemoryItem:
        content: str
        importance: float = 0.5
        year: int = 0
        tags: list = None
except ImportError:
    # Fallback: module not available, create stub
    CognitiveMemory = None
    MemoryItem = None


# =============================================================================
# EVENT CONFIGURATIONS
# =============================================================================

EVENT_CONFIG = {
    # Decision events
    "decision": {
        "buy_insurance": {
            "template": "Year {year}: I purchased flood insurance",
            "importance": 0.7,
            "tags": ["decision", "insurance"]
        },
        "elevate_house": {
            "template": "Year {year}: I elevated my house",
            "importance": 0.8,
            "tags": ["decision", "elevation"]
        },
        "relocate": {
            "template": "Year {year}: I relocated to a safer area",
            "importance": 0.9,
            "tags": ["decision", "relocation"]
        },
        "do_nothing": {
            "template": "Year {year}: I chose to wait",
            "importance": 0.3,
            "tags": ["decision", "inaction"]
        }
    },
    
    # Flood events
    "flood": {
        "major": {
            "template": "Year {year}: A major flood caused ${damage:,.0f} in damages",
            "importance": 0.9,
            "tags": ["flood", "major", "damage"]
        },
        "moderate": {
            "template": "Year {year}: A moderate flood caused ${damage:,.0f} in damages",
            "importance": 0.7,
            "tags": ["flood", "moderate", "damage"]
        },
        "minor": {
            "template": "Year {year}: A minor flood caused ${damage:,.0f} in damages",
            "importance": 0.6,
            "tags": ["flood", "minor", "damage"]
        },
        "no_damage": {
            "template": "Year {year}: A flood occurred but my home was not damaged",
            "importance": 0.4,
            "tags": ["flood", "no_damage"]
        }
    },
    
    # Claim events
    "claim": {
        "approved": {
            "template": "Year {year}: Insurance paid ${payout:,.0f} for my claim",
            "importance": 0.7,
            "tags": ["insurance", "claim", "approved"]
        },
        "denied": {
            "template": "Year {year}: My insurance claim was denied",
            "importance": 0.85,
            "tags": ["insurance", "claim", "denied"]
        },
        "partial": {
            "template": "Year {year}: Insurance paid ${payout:,.0f} but I still owed ${oop:,.0f}",
            "importance": 0.75,
            "tags": ["insurance", "claim", "partial"]
        }
    },
    
    # Social/Neighbor events (triggered at year beginning)
    "neighbor": {
        "elevated": {
            "template": "Year {year}: {count} of my neighbors have elevated their homes",
            "importance": 0.5,
            "tags": ["social", "neighbor", "elevation"]
        },
        "insured": {
            "template": "Year {year}: Most neighbors in my area have flood insurance",
            "importance": 0.4,
            "tags": ["social", "neighbor", "insurance"]
        },
        "relocated": {
            "template": "Year {year}: {count} neighbors have relocated out of the area",
            "importance": 0.5,
            "tags": ["social", "neighbor", "relocation"]
        }
    },
    
    # Policy events (effective next year)
    "policy": {
        "subsidy_increase": {
            "template": "Year {year}: Government announced subsidy increase to {rate:.0%}",
            "importance": 0.6,
            "tags": ["policy", "subsidy"]
        },
        "subsidy_decrease": {
            "template": "Year {year}: Government reduced subsidy rate to {rate:.0%}",
            "importance": 0.7,
            "tags": ["policy", "subsidy"]
        },
        "buyout_offer": {
            "template": "Year {year}: I received a buyout offer of ${amount:,.0f}",
            "importance": 0.85,
            "tags": ["policy", "buyout"]
        }
    },
    
    # Premium events
    "premium": {
        "increase": {
            "template": "Year {year}: Insurance premiums increased by {pct:.0%}",
            "importance": 0.5,
            "tags": ["insurance", "premium"]
        },
        "decrease": {
            "template": "Year {year}: Insurance premiums decreased by {pct:.0%}",
            "importance": 0.4,
            "tags": ["insurance", "premium"]
        }
    }
}


# =============================================================================
# UNIFIED INTERFACE
# =============================================================================

def add_memory(
    memory: CognitiveMemory,
    event_type: str,
    data: Dict[str, Any],
    year: int
) -> Optional[MemoryItem]:
    """
    Unified memory add interface.
    
    Args:
        memory: Agent's cognitive memory
        event_type: "decision", "flood", "claim", "neighbor", "policy", "premium"
        data: Event-specific data dict
        year: Simulation year
        
    Returns:
        MemoryItem if added, None otherwise
    """
    handlers = {
        "decision": _handle_decision,
        "flood": _handle_flood,
        "claim": _handle_claim,
        "neighbor": _handle_neighbor,
        "policy": _handle_policy,
        "premium": _handle_premium,
    }
    
    handler = handlers.get(event_type)
    if handler:
        return handler(memory, data, year)
    return None


# =============================================================================
# EVENT HANDLERS
# =============================================================================

def _handle_decision(memory: CognitiveMemory, data: Dict, year: int) -> Optional[MemoryItem]:
    """Handle decision event."""
    skill_id = data.get("skill_id", "do_nothing")
    config = EVENT_CONFIG["decision"].get(skill_id)
    
    if not config:
        return None
        
    content = config["template"].format(year=year, **data)
    return memory.add_experience(
        content=content,
        importance=config["importance"],
        year=year,
        tags=config["tags"]
    )


def _handle_flood(memory: CognitiveMemory, data: Dict, year: int) -> Optional[MemoryItem]:
    """Handle flood event."""
    damage = data.get("damage", 0)
    occurred = data.get("occurred", damage > 0)
    
    if not occurred and damage == 0:
        return None
    
    # Determine severity
    if damage > 50000:
        subtype = "major"
    elif damage > 10000:
        subtype = "moderate"
    elif damage > 0:
        subtype = "minor"
    else:
        subtype = "no_damage"
    
    config = EVENT_CONFIG["flood"][subtype]
    content = config["template"].format(year=year, damage=damage)
    
    if subtype == "no_damage":
        return memory.add_working(content, config["importance"], year, config["tags"])
    else:
        return memory.add_episodic(content, config["importance"], year, config["tags"])


def _handle_claim(memory: CognitiveMemory, data: Dict, year: int) -> Optional[MemoryItem]:
    """Handle insurance claim event."""
    if not data.get("filed", False):
        return None
    
    approved = data.get("approved", False)
    payout = data.get("payout", 0)
    oop = data.get("oop", 0)
    damage = data.get("damage", 0)
    
    if not approved:
        subtype = "denied"
    elif damage > 0 and oop > damage * 0.2:  # >20% out of pocket
        subtype = "partial"
    else:
        subtype = "approved"
    
    config = EVENT_CONFIG["claim"][subtype]
    content = config["template"].format(year=year, payout=payout, oop=oop)
    
    return memory.add_episodic(content, config["importance"], year, config["tags"])


def _handle_neighbor(memory: CognitiveMemory, data: Dict, year: int) -> Optional[MemoryItem]:
    """Handle neighbor observation event (year beginning)."""
    observation_type = data.get("type", "elevated")
    count = data.get("count", 0)
    
    if count == 0:
        return None
    
    config = EVENT_CONFIG["neighbor"].get(observation_type)
    if not config:
        return None
    
    content = config["template"].format(year=year, count=count)
    return memory.add_working(content, config["importance"], year, config["tags"])


def _handle_policy(memory: CognitiveMemory, data: Dict, year: int) -> Optional[MemoryItem]:
    """Handle policy change event (effective next year)."""
    change_type = data.get("type", "subsidy_increase")
    
    config = EVENT_CONFIG["policy"].get(change_type)
    if not config:
        return None
    
    content = config["template"].format(year=year, **data)
    return memory.add_working(content, config["importance"], year, config["tags"])


def _handle_premium(memory: CognitiveMemory, data: Dict, year: int) -> Optional[MemoryItem]:
    """Handle premium change event."""
    pct = data.get("pct", 0)
    
    if abs(pct) < 0.05:  # Less than 5% change, not memorable
        return None
    
    subtype = "increase" if pct > 0 else "decrease"
    config = EVENT_CONFIG["premium"][subtype]
    
    content = config["template"].format(year=year, pct=abs(pct))
    return memory.add_working(content, config["importance"], year, config["tags"])


# =============================================================================
# CONVENIENCE: YEAR-END UPDATE
# =============================================================================

def add_year_end_memories(
    memory: CognitiveMemory,
    year: int,
    decision: str,
    flood_occurred: bool = False,
    damage: float = 0.0,
    claim_filed: bool = False,
    claim_approved: bool = False,
    payout: float = 0.0,
    oop: float = 0.0
) -> Dict[str, Optional[MemoryItem]]:
    """
    Convenience function for year-end memory updates.
    """
    results = {}
    
    results['decision'] = add_memory(memory, "decision", 
        {"skill_id": decision}, year)
    
    if flood_occurred or damage > 0:
        results['flood'] = add_memory(memory, "flood",
            {"occurred": flood_occurred, "damage": damage}, year)
    
    if claim_filed:
        results['claim'] = add_memory(memory, "claim", {
            "filed": True,
            "approved": claim_approved,
            "payout": payout,
            "oop": oop,
            "damage": damage
        }, year)
    
    return results
