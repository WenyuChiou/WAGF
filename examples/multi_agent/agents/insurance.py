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
from broker.agent_config import AgentTypeConfig

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
        
        # Load config parameters
        self.config_loader = AgentTypeConfig.load()
        self.params = self.config_loader.get_parameters("insurance")

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
        if loss_ratio > self.params.get("loss_ratio_threshold_high", 0.80):
            decision = "raise_premium"
            reasoning = f"Loss ratio {loss_ratio:.2f} is too high (>0.8)"
        elif loss_ratio < self.params.get("loss_ratio_threshold_low", 0.30) and self.state.uptake_rate < self.params.get("uptake_threshold_low", 0.40):
            decision = "lower_premium"
            reasoning = f"Loss ratio {loss_ratio:.2f} low, trying to increase uptake"
            
        # Execute Decision
        if decision == "raise_premium":
            self.state.premium_rate *= self.params.get("rate_adj_raise", 1.10)
        elif decision == "lower_premium":
            self.state.premium_rate *= self.params.get("rate_adj_lower", 0.95)
            
        # Log Decision
        self.memory.add_episodic(
            f"Year {year} Decision: {decision} ({reasoning}). New Rate: {self.state.premium_rate:.2%}",
            importance=0.7 if decision != "maintain_premium" else 0.2,
            year=year,
            tags=["strategy", "pricing"]
        )
        
        return decision

    @property
    def solvency(self) -> float:
        """Solvency ratio (Risk Pool / Target reserve)."""
        target = self.params.get("solvency_target", 1_000_000)
        return min(1.0, self.state.risk_pool / target)

    @property
    def market_ratio(self) -> float:
        """Market uptake rate."""
        return self.state.uptake_rate

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for ContextBuilder."""
        return {
            "id": self.state.id,
            "risk_pool": self.state.risk_pool,
            "premium_rate": self.state.premium_rate,
            "solvency": self.solvency,
            "loss_ratio": self.state.loss_ratio,
            "total_policies": self.state.total_policies,
            "market_share": self.state.uptake_rate,
            "memory": self.memory.format_for_prompt()
        }

    # =========================================================================
    # BaseAgent Compatibility Interface
    # =========================================================================
    
    @property
    def agent_type(self) -> str:
        return "insurance"
    
    @property
    def name(self) -> str:
        return self.state.id

    def get_all_state(self) -> Dict[str, float]:
        """Normalized state (0-1)."""
        return {
            "loss_ratio": self.state.loss_ratio,
            "solvency": self.solvency,
            "premium_rate": self.state.premium_rate * 10, # Normalize 0.05 -> 0.5
            "market_share": self.state.uptake_rate,
            "risk_pool_norm": max(0.0, min(1.0, self.state.risk_pool / 2_000_000))
        }

    def get_all_state_raw(self) -> Dict[str, float]:
        """Raw state values."""
        return {
            "loss_ratio": self.state.loss_ratio,
            "solvency": self.solvency,
            "premium_rate": self.state.premium_rate,
            "market_share": self.state.uptake_rate,
            "risk_pool": self.state.risk_pool,
            "total_policies": self.state.total_policies
        }

    def evaluate_objectives(self) -> Dict[str, Dict]:
        """Insurance objectives: Assessment of solvency and loss ratio."""
        return {
            "solvency": {
                "current": self.solvency,
                "target": (0.5, 1.0),
                "in_range": self.solvency >= 0.5
            },
            "profitability": {
                "current": self.state.loss_ratio,
                "target": (0.0, 0.7),
                "in_range": self.state.loss_ratio < 0.7
            }
        }

    def get_available_skills(self) -> List[str]:
        return ["RAISE", "LOWER", "MAINTAIN"]
    
    def observe(self, environment: Dict[str, float], agents: Dict[str, Any]) -> Dict[str, float]:
        """Observe environment."""
        return {}
