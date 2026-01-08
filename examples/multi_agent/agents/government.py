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
from broker.agent_config import AgentTypeConfig

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
        
        # Load config parameters
        self.config_loader = AgentTypeConfig.load()
        self.params = self.config_loader.get_parameters("government")
        
        # Skill definitions could be dynamic, but hardcoded for now
        self.skills = ["increase_subsidy", "decrease_subsidy", "maintain_subsidy"]

    def reset_annual_budget(self, year: int):
        """Resets the budget at the start of the year."""
        self.state.budget_remaining = self.state.annual_budget
        
        # Log budget reset
        self.memory.add_episodic(
            f"Budget reset to ${self.state.annual_budget:,.0f}", 
            importance=0.1, 
            year=year,
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
        
        if flood_occurred_prev_year and self.state.mg_adoption_rate < self.params.get("mg_adoption_threshold", 0.30):
            decision = "increase_subsidy"
            reasoning = "Flood occurred and MG adoption is low"
        elif self.state.budget_remaining < self.params.get("budget_tight_threshold", 50_000) and self.state.subsidy_rate > self.params.get("min_subsidy", 0.30):
            decision = "decrease_subsidy"
            reasoning = "Budget is tight"
            
        # Execute decision (State Update)
        if decision == "increase_subsidy":
            self.state.subsidy_rate = min(self.params.get("max_subsidy", 0.90), self.state.subsidy_rate + self.params.get("rate_adj_step", 0.10))
        elif decision == "decrease_subsidy":
            self.state.subsidy_rate = max(self.params.get("min_subsidy", 0.30), self.state.subsidy_rate - self.params.get("rate_adj_step", 0.10))
            
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

    # =========================================================================
    # BaseAgent Compatibility Interface
    # =========================================================================
    
    @property
    def agent_type(self) -> str:
        return "government"
    
    @property
    def name(self) -> str:
        return self.state.id

    def get_all_state(self) -> Dict[str, float]:
        """Normalized state (0-1)."""
        return {
            "budget_remaining": self.state.budget_remaining / self.state.annual_budget,
            "subsidy_rate": self.state.subsidy_rate,
            "mg_adoption_rate": self.state.mg_adoption_rate,
            "nmg_adoption_rate": self.state.nmg_adoption_rate,
            "equity_gap": abs(self.state.mg_adoption_rate - self.state.nmg_adoption_rate)
        }

    def get_all_state_raw(self) -> Dict[str, float]:
        """Raw state values."""
        return {
            "budget_remaining": self.state.budget_remaining,
            "subsidy_rate": self.state.subsidy_rate,
            "mg_adoption_rate": self.state.mg_adoption_rate,
            "nmg_adoption_rate": self.state.nmg_adoption_rate,
            "annual_budget": self.state.annual_budget
        }

    def evaluate_objectives(self) -> Dict[str, Dict]:
        """Government objectives: Adoption and Equity."""
        equity_gap = abs(self.state.mg_adoption_rate - self.state.nmg_adoption_rate)
        return {
            "adoption": {
                "current": self.state.mg_adoption_rate,
                "target": (0.3, 1.0),
                "in_range": self.state.mg_adoption_rate > 0.3
            },
            "equity": {
                "current": equity_gap,
                "target": (0.0, 0.2),
                "in_range": equity_gap < 0.2
            },
            "budget": {
                "current": self.state.budget_remaining / self.state.annual_budget,
                "target": (0.0, 1.0),
                "in_range": self.state.budget_remaining > 0
            }
        }

    def get_available_skills(self) -> List[str]:
        return ["INCREASE", "DECREASE", "MAINTAIN", "OUTREACH"]
    
    def observe(self, environment: Dict[str, float], agents: Dict[str, Any]) -> Dict[str, float]:
        """Observe environment."""
        return {}
