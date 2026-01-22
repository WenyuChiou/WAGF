
"""
Flood Agents for Multi-Agent Simulation (Phase 18).
Implements logic-driven Government and Insurance agents.
"""
from typing import Dict, Any
from examples.multi_agent.environment.risk_rating import RiskRating2Calculator, R1K_STRUCTURE, R1K_CONTENTS, LIMIT_STRUCTURE, LIMIT_CONTENTS

class BaseInstitutionAgent:
    def __init__(self, id: str):
        self.id = id
        self.type = "institution"

    def step(self, global_stats: Dict[str, float]) -> Dict[str, Any]:
        """Output decision changes based on global stats."""
        raise NotImplementedError

class NJStateAgent(BaseInstitutionAgent):
    """
    Government Agent: Manages Blue Acres Buyout Subsidies.
    Reference: NJDEP (2023) Blue Acres Guidelines.
    Goal: Target relocation for repetitive loss properties (Severe Zones).
    """
    def __init__(self):
        super().__init__("NJ_STATE")
        self.buyout_subsidy_rate = 0.50 # Base 50% for Blue Acres
        self.target_relocation_rate = 0.10
        self.agent_type = "government"

    def step(self, global_stats: Dict[str, float]) -> Dict[str, Any]:
        relocation_rate = global_stats.get("relocation_rate", 0.0)
        avg_depth_ft = global_stats.get("avg_depth_ft", 0.0)
        
        # Blue Acres Logic: If floods are severe, increase buyout availability
        prev_rate = self.buyout_subsidy_rate
        if avg_depth_ft > 2.0:
            self.buyout_subsidy_rate = min(0.95, self.buyout_subsidy_rate + 0.10)
        elif relocation_rate > self.target_relocation_rate:
            self.buyout_subsidy_rate = max(0.20, self.buyout_subsidy_rate - 0.05)
            
        return {
            "decision": "blue_acres_update", 
            "subsidy_level": round(self.buyout_subsidy_rate, 2),
            "priority_zone": "Severe",
            "message": "NJ Blue Acres is prioritizing high-risk buyouts after recent flooding."
        }

class FemaNfipAgent(BaseInstitutionAgent):
    """
    Insurance Agent: Manages Premiums inspired by Risk Rating 2.0.
    Reference: FEMA (2021) Risk Rating 2.0 System.
    Goal: Solvency + encouraging community-level mitigation.
    """
    def __init__(self):
        super().__init__("FEMA_NFIP")
        self.base_premium_rate = 0.005 # Base 0.5% of house value
        self.revenue = 1000000.0 # Virtual reserve
        self.agent_type = "insurance"
        self.risk_calculator = RiskRating2Calculator()
        
    def step(self, global_stats: Dict[str, float]) -> Dict[str, Any]:
        """
        Insurance Agent: Manages Premiums inspired by Risk Rating 2.0.
        Reference: FEMA (2021) Risk Rating 2.0 System.
        Goal: Solvency + encouraging community-level mitigation.
        """
        claims = global_stats.get("total_claims", 0.0)
        premiums = global_stats.get("total_premiums", 10000.0)
        elevation_rate = global_stats.get("elevation_rate", 0.0)
        
        self.revenue += (premiums - claims)
        
        # 1. Solvency check and adjustment factor
        solvency_ratio = self.revenue / 1000000.0
        solvency_adjustment_factor = 1.0
        if solvency_ratio < 0.8:
            solvency_adjustment_factor = 1.10 # Increase rates if solvency is low
        elif solvency_ratio > 1.2:
            solvency_adjustment_factor = 0.95 # Decrease rates if solvency is high
            
        # 2. Determine CRS discount from elevation rate
        # Elevation rate is a proxy for community mitigation efforts, impacting CRS discount
        # Max 20% CRS-style discount from elevation rate in original logic; let's use this directly as CRS discount
        crs_discount = min(0.45, elevation_rate * 0.20) # Cap at max NFIP CRS discount of 45%

        # 3. Instantiate RiskRating2Calculator with adjusted base rates and CRS discount
        # The agent's base_premium_rate adjustments are now reflected in modified base rates
        # We use hardcoded typical values for property characteristics to calculate an average effective rate
        
        # Initialize calculator with adjusted base rates and CRS discount
        calculator = RiskRating2Calculator(
            r1k_structure=R1K_STRUCTURE * solvency_adjustment_factor,
            r1k_contents=R1K_CONTENTS * solvency_adjustment_factor,
            crs_discount=crs_discount
        )
        
        # Assume average property characteristics for calculation
        # These are placeholders and could be made more sophisticated if property data were available
        avg_rcv_structure = LIMIT_STRUCTURE * 0.8 # Assume 80% of max structure coverage
        avg_rcv_contents = LIMIT_CONTENTS * 0.8 # Assume 80% of max contents coverage
        avg_flood_zone = "AE" # Common high-risk zone
        avg_is_elevated = True # Assume elevated due to mitigation efforts
        avg_is_owner = True
        avg_distance_to_water_ft = 100 # Arbitrary distance
        avg_prior_claims = 0 # Assume no prior claims for average calculation

        # Calculate premium using RR2.0 methodology
        premium_result = calculator.calculate_premium(
            rcv_structure=avg_rcv_structure,
            rcv_contents=avg_rcv_contents,
            flood_zone=avg_flood_zone,
            is_elevated=avg_is_elevated,
            is_owner=avg_is_owner,
            distance_to_water_ft=avg_distance_to_water_ft,
            prior_claims=avg_prior_claims
        )
        
        # Return the effective rate as the premium rate
        return {
            "decision": "premium_adjustment",
            "premium_rate": premium_result.effective_rate, # This is the rate per dollar of coverage
            "solvency_status": "CRITICAL" if solvency_ratio < 0.5 else "STABLE",
            "mitigation_benefit": round(1 - crs_discount, 2) # Reflecting the applied CRS discount
        }
