"""
Catastrophe Module (Environment Layer)

Responsible for calculating the physical and financial impact of flood events.
Separates environmental physics from agent decision logic.
"""

from dataclasses import dataclass
from typing import Dict, Any, Tuple
import numpy as np

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
    
    def calculate_damage_ratio(self, severity: float, elevated: bool) -> float:
        """
        Calculates damage as a percentage of property value.
        
        Args:
            severity (float): 0.0 - 1.0
            elevated (bool): Whether the house is elevated
            
        Returns:
            float: Damage ratio (0.0 - 1.0)
        """
        # Base damage driven by severity (e.g., severity 0.5 -> 20% damage base)
        # Using a power curve to simulate non-linear damage increase
        base_damage = severity ** 2.0
        
        # Add stochastic variability (log-normal noise)
        # We ensure damage doesn't exceed 1.0
        noise = self.rng.lognormal(mean=0, sigma=0.2)
        damage_ratio = np.clip(base_damage * noise, 0.0, 1.0)
        
        # Elevation benefit
        # Assumption: Elevation reduces damage magnitude significantly
        if elevated:
            # If severity is extremely high (>.9), elevation might be overtopped
            if severity > 0.9:
                reduction_factor = 0.5  # Overtopped but still some help
            else:
                reduction_factor = 0.95 # Almost full protection
            
            damage_ratio *= (1.0 - reduction_factor)
            
        return float(damage_ratio)

    def calculate_financials(self, 
                           agent_id: str,
                           agent_state: Any,  # HouseholdAgentState-like
                           flood_event: FloodEvent,
                           insurance_state: Any) -> Dict[str, float]:
        """
        Calculates financial outcomes: Damage, Payout, Out-of-Pocket.
        
        Returns:
            Dict: {
                "damage_amount": float,
                "payout_amount": float,
                "oop_cost": float, # Out of pocket
                "damage_ratio": float
            }
        """
        # 1. Determine Property Value (Simplified: could be in agent state)
        # Using a fixed mean for now or assume checked from state if available
        property_value = getattr(agent_state, 'property_value', self.PROPERTY_VALUE_MEAN)
        
        # 2. Calculate Physical Damage
        elevated = getattr(agent_state, 'elevated', False)
        damage_ratio = self.calculate_damage_ratio(flood_event.severity, elevated)
        damage_amount = property_value * damage_ratio
        
        # 3. Calculate Insurance Payout
        payout_amount = 0.0
        has_insurance = getattr(agent_state, 'has_insurance', False)
        
        if has_insurance:
            # NFIP-like logic: Coverage limit and deductible
            coverage_limit = 250_000  # Standard NFIP building limit
            deductible = 2_000        # Typical deductible
            
            # Payout depends on Insurance Agent's payout ratio (claim acceptance rate/fairness)
            # But usually it's deterministic based on policy. Let's use simple logic first.
            claimable = min(damage_amount, coverage_limit)
            payout_raw = max(0, claimable - deductible)
            
            # Insurance Agent might have a payout_ratio (e.g., 0.8 if insolvent or strict)
            # Default to 1.0 unless specified in insurance_state
            insurer_payout_ratio = getattr(insurance_state, 'payout_ratio', 1.0)
            payout_amount = payout_raw * insurer_payout_ratio
            
        # 4. Calculate Out-of-Pocket
        oop_cost = damage_amount - payout_amount
        
        return {
            "damage_amount": round(damage_amount, 2),
            "payout_amount": round(payout_amount, 2),
            "oop_cost": round(oop_cost, 2),
            "damage_ratio": round(damage_ratio, 4)
        }
