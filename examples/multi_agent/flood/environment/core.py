"""
Environment Core - Unified Interface

Single entry point: process(event_type, data) -> Dict

Pure functions: No side effects, returns results only.
State mutations happen in orchestrator (run_experiment.py).
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import numpy as np
from examples.multi_agent.flood.environment.hazard import VulnerabilityModule


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FloodEvent:
    """Flood hazard event."""
    year: int
    occurred: bool
    severity: float = 0.0  # 0.0 - 1.0
    depth_ft: float = 0.0  # Flood depth in feet
    

@dataclass 
class DamageResult:
    """Damage calculation result."""
    damage_ratio: float
    damage_amount: float
    building_damage: float
    contents_damage: float


@dataclass
class ClaimResult:
    """Insurance claim result."""
    filed: bool
    approved: bool
    payout: float
    deductible: float
    out_of_pocket: float


@dataclass
class SubsidyResult:
    """Subsidy calculation result."""
    approved: bool
    subsidy_amount: float
    cost_basis: float
    net_cost: float
    applied_rate: float


# =============================================================================
# CONFIGURATION - NFIP Compliant Parameters
# =============================================================================
# Sources:
# [1] FEMA NFIP: https://www.fema.gov/flood-insurance
# [2] Forbes (2024): Flood Insurance Deductible Guide
# [3] Congress.gov: Risk Rating 2.0 Analysis
# [4] eCFR 44 CFR 61.6: Deductible Schedule
# [5] NerdWallet (2025): Average NFIP rates ~$899/year

ENV_CONFIG = {
    # Flood parameters
    "flood": {
        "base_probability": 0.2,  # Typical for high-risk zones (SFHAs)
        "min_severity": 0.1,
        "max_severity": 1.0,
    },
    
    # Damage parameters
    # FLOODABM Table S2
    "damage": {
        "elevation_reduction": 0.95,  # BFE+1ft reduces damage by ~95%
        "elevation_overtop_reduction": 0.5,  # When overtopped (severity > 0.9)
        "contents_ratio": 0.3,  # Contents = 30% of building damage
        # TP Gain Threshold (FLOODABM Supplementary)
        "damage_ratio_threshold": 0.5,  # theta: flood damage ratio for TP gain
        "shock_scale": 0.3,  # cs: shock scaling factor
    },
    
    # Insurance parameters - NFIP compliant [1][2][4]
    # FLOODABM Supplementary Table S2
    "insurance": {
        # Coverage Limits (Residential) [1]
        "nfip_building_limit": 250_000,  # Max building coverage (Ls)
        "nfip_contents_limit": 100_000,  # Max contents coverage (Lc)

        # Deductible Options [2][4]
        # FLOODABM: DDs = DDc = $1,000
        "default_deductible": 1_000,  # FLOODABM Table S2
        "default_deductible_structure": 1_000,  # DDs
        "default_deductible_contents": 1_000,  # DDc
        "min_deductible": 1_000,
        "max_deductible": 10_000,

        # Premium Rate (Risk Rating 2.0) [3][5]
        # FLOODABM: r1k,s = 3.56, r1k,c = 4.90 (per $1K coverage)
        "base_premium_rate": 0.004,  # Legacy: ~$1,000/yr on $250K coverage
        "r1k_structure": 3.56,  # FLOODABM: $/1K structure coverage
        "r1k_contents": 4.90,  # FLOODABM: $/1K contents coverage

        # Reserve and fees (FLOODABM Table S2)
        "reserve_fund_factor": 1.15,  # R = 1.15
        "small_fee": 100,  # F = $100 (federal policy fee, ICC, etc.)
    },
    
    # Subsidy parameters (FEMA Hazard Mitigation Assistance)
    "subsidy": {
        "elevate_house_cost": 150_000,  # Average elevation cost
        "relocate_cost": 50_000,  # Buyout/relocation assistance
        "default_rate": 0.50,  # 50% federal cost share
        "mg_priority_bonus": 0.25,  # Up to 75% for MG communities
    }
}


# =============================================================================
# UNIFIED INTERFACE
# =============================================================================

def process(
    event_type: str,
    data: Dict[str, Any],
    config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Unified environment processing interface.
    
    Args:
        event_type: "flood", "damage", "claim", "subsidy"
        data: Event-specific input data
        config: Optional config overrides
        
    Returns:
        Dict with results (varies by event_type)
    """
    cfg = {**ENV_CONFIG, **(config or {})}
    
    handlers = {
        "flood": _process_flood,
        "damage": _process_damage,
        "claim": _process_claim,
        "subsidy": _process_subsidy,
    }
    
    handler = handlers.get(event_type)
    if handler:
        return handler(data, cfg)
    
    raise ValueError(f"Unknown event_type: {event_type}")


# =============================================================================
# EVENT HANDLERS (Pure Functions)
# =============================================================================

def _process_flood(data: Dict, cfg: Dict) -> Dict:
    """
    Generate flood event.
    
    Input: {"year": int, "rng": np.random.Generator}
    Output: FloodEvent as dict
    """
    year = data.get("year", 0)
    rng = data.get("rng", np.random.default_rng())
    flood_cfg = cfg.get("flood", ENV_CONFIG["flood"])
    
    # Determine if flood occurs
    occurred = rng.random() < flood_cfg["base_probability"]
    
    if occurred:
        # Severity between min and max
        severity = flood_cfg["min_severity"] + (
            rng.random() * (flood_cfg["max_severity"] - flood_cfg["min_severity"])
        )
        # Depth roughly proportional to severity
        depth_ft = severity * 10  # 0-10 feet
    else:
        severity = 0.0
        depth_ft = 0.0
    
    event = FloodEvent(
        year=year,
        occurred=occurred,
        severity=severity,
        depth_ft=depth_ft
    )
    return asdict(event)


def _process_damage(data: Dict, cfg: Dict) -> Dict:
    """
    Calculate damage from flood.
    
    Input: {"depth_ft": float, "property_value": float, "elevated": bool}
    Output: DamageResult as dict
    """
    depth_ft = data.get("depth_ft", 0.0)
    property_value = data.get("property_value", 300_000)
    elevated = data.get("elevated", False)
    
    if depth_ft <= 0:
        return asdict(DamageResult(
            damage_ratio=0.0,
            damage_amount=0.0,
            building_damage=0.0,
            contents_damage=0.0
        ))
    
    vuln = VulnerabilityModule()
    rcv_contents = property_value * 0.3
    
    res = vuln.calculate_damage(
        depth_ft=depth_ft,
        rcv_building=property_value,
        rcv_contents=rcv_contents,
        is_elevated=elevated
    )
    
    return asdict(DamageResult(
        damage_ratio=res["building_ratio"],
        damage_amount=res["total_damage"],
        building_damage=res["building_damage"],
        contents_damage=res["contents_damage"]
    ))


def _process_claim(data: Dict, cfg: Dict) -> Dict:
    """
    Process insurance claim.
    
    Input: {"damage_amount": float, "has_insurance": bool, "payout_ratio": float}
    Output: ClaimResult as dict
    """
    damage = data.get("damage_amount", 0.0)
    has_insurance = data.get("has_insurance", False)
    payout_ratio = data.get("payout_ratio", 1.0)
    ins_cfg = cfg.get("insurance", ENV_CONFIG["insurance"])
    
    if not has_insurance or damage == 0:
        return asdict(ClaimResult(
            filed=False,
            approved=False,
            payout=0.0,
            deductible=0.0,
            out_of_pocket=damage
        ))
    
    vuln = VulnerabilityModule()
    payout = vuln.calculate_payout(
        damage=damage,
        coverage_limit=ins_cfg["nfip_building_limit"],
        deductible=ins_cfg["default_deductible"],
        payout_ratio=payout_ratio
    )
    
    out_of_pocket = vuln.calculate_oop(damage, payout)
    
    return asdict(ClaimResult(
        filed=True,
        approved=payout > 0,
        payout=payout,
        deductible=ins_cfg["default_deductible"],
        out_of_pocket=out_of_pocket
    ))


def _process_subsidy(data: Dict, cfg: Dict) -> Dict:
    """
    Calculate subsidy for mitigation action.
    
    Input: {"action": str, "is_mg": bool, "mg_priority": bool, "budget": float}
    Output: SubsidyResult as dict
    """
    action = data.get("action", "elevate_house")
    is_mg = data.get("is_mg", False)
    mg_priority = data.get("mg_priority", False)
    budget = data.get("budget", float('inf'))
    subsidy_cfg = cfg.get("subsidy", ENV_CONFIG["subsidy"])
    
    # Cost basis
    cost_map = {
        "elevate_house": subsidy_cfg["elevate_house_cost"],
        "relocate": subsidy_cfg["relocate_cost"],
    }
    cost_basis = cost_map.get(action, 0)
    
    if cost_basis == 0 or budget <= 0:
        return asdict(SubsidyResult(
            approved=False,
            subsidy_amount=0.0,
            cost_basis=cost_basis,
            net_cost=cost_basis,
            applied_rate=0.0
        ))
    
    # Calculate rate
    base_rate = subsidy_cfg["default_rate"]
    if mg_priority and is_mg:
        applied_rate = min(1.0, base_rate + subsidy_cfg["mg_priority_bonus"])
    else:
        applied_rate = base_rate
    
    # Calculate amount
    subsidy_amount = cost_basis * applied_rate
    
    # Cap by budget
    if subsidy_amount > budget:
        subsidy_amount = budget
        # Recalculate rate based on actual subsidy
        applied_rate = subsidy_amount / cost_basis if cost_basis > 0 else 0
    
    return asdict(SubsidyResult(
        approved=subsidy_amount > 0,
        subsidy_amount=round(subsidy_amount, 2),
        cost_basis=cost_basis,
        net_cost=round(max(0, cost_basis - subsidy_amount), 2),
        applied_rate=round(applied_rate, 4)
    ))
