"""
Subsidy Module (Environment Layer)

Responsible for calculating government subsidies for mitigation actions.
Allocates funds based on government state (budget, policy) and household eligibility.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List

class SubsidyModule:
    """
    Calculates subsidy amounts for mitigation actions (e.g., elevation).
    """
    
    def __init__(self):
        # Default cost estimates for actions
        self.COST_ESTIMATES = {
            "elevate_house": 150_000,
            "relocate": 50_000,
            "buy_insurance": 1_000 # Usually not subsidized directly, but maybe?
        }
    
    def calculate_subsidy(self, 
                        agent_state: Any, 
                        action_name: str, 
                        government_state: Any) -> Dict[str, float]:
        """
        Calculates the subsidy amount for a given action.
        
        Args:
            agent_state: HouseholdAgentState
            action_name: "elevate_house", "relocate", etc.
            government_state: GovernmentAgentState
            
        Returns:
            Dict: {
                "subsidy_amount": float,
                "cost_basis": float,
                "net_cost": float,
                "approved": bool
            }
        """
        # 1. Determine Cost Basis
        cost_basis = self.COST_ESTIMATES.get(action_name, 0.0)
        
        # 2. Check Budget
        budget_remaining = getattr(government_state, 'budget_remaining', 0.0)
        if budget_remaining <= 0:
             return {
                "subsidy_amount": 0.0,
                "cost_basis": cost_basis,
                "net_cost": cost_basis,
                "approved": False,
                "reason": "Budget Exhausted"
            }
            
        # 3. Determine Subsidy Rate
        base_rate = getattr(government_state, 'subsidy_rate', 0.50) # Default 50%
        
        # Priority Logic (MG Priority)
        mg_priority = getattr(government_state, 'mg_priority', False)
        agent_type = getattr(agent_state, 'agent_type', "NMG_Owner")
        
        # Simple string check for MG status
        # Must ensure NMG doesn't match MG logic (NMG contains string MG)
        is_mg = agent_type.startswith("MG")
        
        final_rate = base_rate
        
        if mg_priority and is_mg:
            # Boost for MG if priority is active (e.g., +25% or up to 100% depending on policy)
            # For now, let's assume priority means +25% bonus
            final_rate = min(1.0, base_rate + 0.25)
        
        # 4. Calculate Amount
        subsidy_amount = cost_basis * final_rate
        
        # 5. Cap by Budget
        if subsidy_amount > budget_remaining:
            subsidy_amount = budget_remaining  # Partial funding? Or deny? 
            # Let's assume partial funding is allowed, or first-come-first-served
        
        return {
            "subsidy_amount": round(subsidy_amount, 2),
            "cost_basis": cost_basis,
            "net_cost": max(0, cost_basis - subsidy_amount),
            "approved": subsidy_amount > 0,
            "applied_rate": final_rate
        }
