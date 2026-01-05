"""
Government Agent (Exp3)

The Government Agent works in Phase 1 (Institutional Decisions).
Responsibility:
- Manage annual budget ($500k/year)
- Set subsidy rates for mitigation (Elevation/Relocation)
- Target vulnerability reduction (MG priority)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from broker.memory import CognitiveMemory, MemoryProvider

@dataclass
class GovernmentAgentState:
    id: str = "Government"
    
    # Financials
    annual_budget: float = 500_000
    budget_remaining: float = 500_000
    total_spent: float = 0
    
    # Policy Parameters
    subsidy_rate: float = 0.50          # Base rate (50%)
    mg_priority: bool = True            # Priority for Marginalized Groups
    
    # Performance Metrics
    mg_adoption_rate: float = 0.0
    nmg_adoption_rate: float = 0.0
    overall_risk_reduction: float = 0.0
    
    # Memory
    memory: Optional[CognitiveMemory] = None

class GovernmentAgent:
    """
    Government Agent implementation.
    """
    
    def __init__(self, agent_id: str = "Government"):
        self.state = GovernmentAgentState(id=agent_id)
        # Initialize Memory
        # Using a specialized memory or standard CognitiveMemory
        self.memory = CognitiveMemory(agent_id)
        self.state.memory = self.memory
        
        # Skill definitions could be dynamic, but hardcoded for now
        self.skills = ["increase_subsidy", "decrease_subsidy", "maintain_subsidy"]

    def reset_annual_budget(self):
        """Resets the budget at the start of the year."""
        self.state.budget_remaining = self.state.annual_budget
        
        # Log budget reset
        self.memory.add_episodic(
            f"Budget reset to ${self.state.annual_budget:,.0f}", 
            importance=0.1, 
            year=self.memory.current_year,
            tags=["budget"]
        )

    def decide_policy(self, year: int, flood_occurred_prev_year: bool) -> str:
        """
        Phase 1 Decision: Determine policy adjustments.
        In a full LLM implementations, this would call the LLM.
        Here we implement the 'Rule-Based' logic from the Spec/Research first,
        or prepare the context for the LLM.
        """
        # Logic from Spec:
        # - Increase subsidy if flood occurred + low adoption
        # - Decrease subsidy if budget tight or adoption high
        
        decision = "maintain_subsidy"
        reasoning = "Status quo"
        
        # Access memory to see past trends (simulating cognitive lookup)
        # Access memory to see past trends (simulating cognitive lookup)
        past_policies = self.memory.retrieve(top_k=2)
        
        if flood_occurred_prev_year and self.state.mg_adoption_rate < 0.30:
            decision = "increase_subsidy"
            reasoning = "Flood occurred and MG adoption is low"
        elif self.state.budget_remaining < 50_000 and self.state.subsidy_rate > 0.50:
            decision = "decrease_subsidy"
            reasoning = "Budget is tight"
            
        # Execute decision (State Update)
        if decision == "increase_subsidy":
            self.state.subsidy_rate = min(0.90, self.state.subsidy_rate + 0.10)
        elif decision == "decrease_subsidy":
            self.state.subsidy_rate = max(0.30, self.state.subsidy_rate - 0.10)
            
        # Log decision
        self.memory.add_episodic(
            f"Year {year} Decision: {decision} (${reasoning}). Rate: {self.state.subsidy_rate:.0%}",
            importance=0.6,
            year=year,
            tags=["policy", "decision"]
        )
        
        return decision

    def update_metrics(self, mg_adopt: float, nmg_adopt: float):
        self.state.mg_adoption_rate = mg_adopt
        self.state.nmg_adoption_rate = nmg_adopt

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for ContextBuilder."""
        return {
            "id": self.state.id,
            "budget_remaining": self.state.budget_remaining,
            "subsidy_rate": self.state.subsidy_rate,
            "mg_priority": self.state.mg_priority,
            "memory": self.memory.format_for_prompt() # Or send raw list
        }
