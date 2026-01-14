"""
Catastrophe Module (Environment Layer)

Responsible for calculating the physical and financial impact of flood events.
Separates environmental physics from agent decision logic.
"""

from dataclasses import dataclass
from typing import Dict, Any, Tuple
import numpy as np
from examples.multi_agent.environment.hazard import VulnerabilityModule

@dataclass
class FloodEvent:
    year: int
    severity: float  # 0.0 to 1.0 (representing percentile or magnitude)
    period: int = 100  # Return period (e.g., 100-year flood)

class CatastropheModule:
    """
    Calculates flood damages and insurance payouts based on event severity and agent state.
    """
    
    def __init__(self, random_seed: int = 42):
        self.rng = np.random.default_rng(random_seed)
        
        # Configuration
        self.PROPERTY_VALUE_MEAN = 300_000
        self.PROPERTY_VALUE_STD = 50_000
        self.DAMAGE_LOGNORMAL_SIGMA = 0.5  # Variability in damage for same severity
        self.vuln = VulnerabilityModule()
    
    def calculate_damage_ratio(self, depth_ft: float) -> float:
        """
        Calculates building damage ratio using FEMA curves in VulnerabilityModule.
        """
        # Returns Dict with building_ratio, etc.
        res = self.vuln.calculate_damage(depth_ft=depth_ft, rcv_building=1.0, rcv_contents=0.0, is_elevated=False)
        return res["building_ratio"]

    def calculate_financials(self, 
                           agent_id: str,
                           agent_state: Any,  # HouseholdAgentState-like
                           depth_ft: float,
                           insurance_state: Any) -> Dict[str, float]:
        """
        Calculates financial outcomes using FEMA depth-damage curves.
        """
        # 1. Determine Property Value
        property_value = getattr(agent_state, 'property_value', self.PROPERTY_VALUE_MEAN)
        rcv_contents = property_value * 0.3 # Assumption: Contents = 30% of building
        
        # 2. Calculate Physical Damage using VulnerabilityModule
        elevated = getattr(agent_state, 'elevated', False)
        damage_res = self.vuln.calculate_damage(
            depth_ft=depth_ft,
            rcv_building=property_value,
            rcv_contents=rcv_contents,
            is_elevated=elevated
        )
        
        damage_amount = damage_res["total_damage"]
        damage_ratio = damage_res["building_ratio"] # Primary ratio reference
        
        # 3. Calculate Insurance Payout
        payout_amount = 0.0
        has_insurance = getattr(agent_state, 'has_insurance', False)
        
        if has_insurance:
            # NFIP-like logic from VulnerabilityModule
            coverage_limit = 250_000
            deductible = 2_000
            insurer_payout_ratio = getattr(insurance_state, 'payout_ratio', 1.0)
            
            payout_amount = self.vuln.calculate_payout(
                damage=damage_amount,
                coverage_limit=coverage_limit,
                deductible=deductible,
                payout_ratio=insurer_payout_ratio
            )
            
        # 4. Calculate Out-of-Pocket
        oop_cost = self.vuln.calculate_oop(damage_amount, payout_amount)
        
        return {
            "damage_amount": damage_amount,
            "payout_amount": payout_amount,
            "oop_cost": oop_cost,
            "damage_ratio": damage_ratio,
            "effective_depth": damage_res["effective_depth"]
        }
