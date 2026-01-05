"""
Insurance Agent (Exp3)

The Insurance Agent works in Phase 1 (Institutional Decisions).
Responsibility:
- Manage risk pool and solvency
- Set premium rates based on Loss Ratio
- (Future) Send risk alerts and offering discounts
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from broker.memory import CognitiveMemory

@dataclass
class InsuranceAgentState:
    id: str = "InsuranceCo"
    
    # Financials
    risk_pool: float = 1_000_000        # Capital reserve
    premium_collected: float = 0        # Annual revenue
    claims_paid: float = 0              # Annual payout
    
    # Policy Parameters
    premium_rate: float = 0.05          # 5% of coverage amount
    payout_ratio: float = 1.0           # 100% of claim paid (minus deductible)
    
    # Market Metrics
    total_policies: int = 0
    uptake_rate: float = 0.0
    
    # Memory
    memory: Optional[CognitiveMemory] = None
    
    @property
    def loss_ratio(self) -> float:
        """Calculates Loss Ratio (Claims / Premiums)."""
        if self.premium_collected == 0:
            return 0.0
        return self.claims_paid / self.premium_collected

class InsuranceAgent:
    """
    Insurance Agent implementation.
    """
    
    def __init__(self, agent_id: str = "InsuranceCo"):
        self.state = InsuranceAgentState(id=agent_id)
        self.memory = CognitiveMemory(agent_id)
        self.state.memory = self.memory

    def reset_annual_metrics(self):
        """Resets annual tracking metrics."""
        self.state.premium_collected = 0
        self.state.claims_paid = 0

    def decide_strategy(self, year: int) -> str:
        """
        Phase 1 Decision: Adjust premiums or coverage.
        """
        loss_ratio = self.state.loss_ratio
        decision = "maintain_premium"
        reasoning = "Loss ratio within acceptable range"
        
        # Simple Rules (to be replaced/augmented by LLM)
        if loss_ratio > 0.80:
            decision = "raise_premium"
            reasoning = f"Loss ratio {loss_ratio:.2f} is too high (>0.8)"
        elif loss_ratio < 0.30 and self.state.uptake_rate < 0.40:
            decision = "lower_premium"
            reasoning = f"Loss ratio {loss_ratio:.2f} low, trying to increase uptake"
            
        # Execute Decision
        if decision == "raise_premium":
            self.state.premium_rate *= 1.10
        elif decision == "lower_premium":
            self.state.premium_rate *= 0.95
            
        # Log Decision
        self.memory.add_episodic(
            f"Year {year} Decision: {decision} ({reasoning}). New Rate: {self.state.premium_rate:.2%}",
            importance=0.7 if decision != "maintain_premium" else 0.2,
            year=year,
            tags=["strategy", "pricing"]
        )
        
        return decision

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.state.id,
            "premium_rate": self.state.premium_rate,
            "loss_ratio": self.state.loss_ratio,
            "risk_pool": self.state.risk_pool,
            "memory": self.memory.format_for_prompt()
        }
