
"""
Flood Agents for Multi-Agent Simulation (Phase 18).
Implements logic-driven Government and Insurance agents.
"""
from typing import Dict, Any

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
        
    def step(self, global_stats: Dict[str, float]) -> Dict[str, Any]:
        claims = global_stats.get("total_claims", 0.0)
        premiums = global_stats.get("total_premiums", 10000.0)
        elevation_rate = global_stats.get("elevation_rate", 0.0)
        
        self.revenue += (premiums - claims)
        
        # Risk Rating 2.0 logic: 
        # 1. Solvency check (base trend)
        solvency_ratio = self.revenue / 1000000.0
        
        # 2. Mitigation discount: If community elevation is high, lower rates for all
        mitigation_discount = 1.0 - (elevation_rate * 0.2) # Max 20% CRS-style discount
        
        prev_rate = self.base_premium_rate
        
        # Direct rate targeting based on balance
        if solvency_ratio < 0.8:
            self.base_premium_rate *= 1.10 # 10% hike
        elif solvency_ratio > 1.2:
            self.base_premium_rate *= 0.95 # 5% decrease
            
        # Apply community-wide mitigation discount to the final rate
        final_rate = max(0.001, min(0.05, self.base_premium_rate * mitigation_discount))
            
        return {
            "decision": "premium_adjustment",
            "premium_rate": round(final_rate, 5),
            "solvency_status": "CRITICAL" if solvency_ratio < 0.5 else "STABLE",
            "mitigation_benefit": round(1 - mitigation_discount, 2)
        }
