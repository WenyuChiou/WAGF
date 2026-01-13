
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
    Government Agent: Manages Subsidy Levels.
    Goal: Encourage relocation from high-risk zones if rate is too low.
    """
    def __init__(self):
        super().__init__("NJ_STATE")
        self.subsidy_level = 0.0
        self.target_relocation_rate = 0.15 # Target: 15% population move
        self.agent_type = "government"

    def step(self, global_stats: Dict[str, float]) -> Dict[str, Any]:
        relocation_rate = global_stats.get("relocation_rate", 0.0)
        
        prev_level = self.subsidy_level
        
        # Simple Feedback Loop
        if relocation_rate < self.target_relocation_rate:
            # Increase subsidy to encourage movement
            self.subsidy_level = min(1.0, self.subsidy_level + 0.05)
        elif relocation_rate > self.target_relocation_rate * 1.5:
             # Reduce subsidy if overshoot
            self.subsidy_level = max(0.0, self.subsidy_level - 0.02)
            
        return {
            "decision": "adjust_subsidy", 
            "subsidy_level": round(self.subsidy_level, 2),
            "change": round(self.subsidy_level - prev_level, 2)
        }

class FemaNfipAgent(BaseInstitutionAgent):
    """
    Insurance Agent: Manages Premium Rates.
    Goal: Maintain solvency (Premiums > Claims).
    """
    def __init__(self):
        super().__init__("FEMA_NFIP")
        self.premium_rate = 0.02 # Base 2% of property value
        self.revenue = 0.0
        self.payouts = 0.0
        self.agent_type = "insurance"
        
    def step(self, global_stats: Dict[str, float]) -> Dict[str, Any]:
        # Logic: If running deficit, increase premiums
        claims = global_stats.get("total_claims", 0.0)
        premiums = global_stats.get("total_premiums", 0.0)
        
        self.payouts += claims
        self.revenue += premiums
        
        # Calculate solvency ratio (avoid div/0)
        balance_ratio = (self.revenue / self.payouts) if self.payouts > 1000 else 1.2
        
        prev_rate = self.premium_rate
        
        if balance_ratio < 1.0:
            # Deficit: Hike premiums aggressive
            self.premium_rate = min(0.15, self.premium_rate * 1.2)
        elif balance_ratio > 1.5:
            # Surplus: Stable or slight cut
            self.premium_rate = max(0.01, self.premium_rate * 0.95)
        
        # Ensure minimum floor
        self.premium_rate = max(0.01, self.premium_rate)
            
        return {
            "decision": "adjust_premium",
            "premium_rate": round(self.premium_rate, 4),
            "change": round(self.premium_rate - prev_rate, 4)
        }
