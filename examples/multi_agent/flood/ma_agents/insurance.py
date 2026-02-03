"""
Insurance / CRS Agent (Exp3)

The Insurance Agent works in Phase 1 (Institutional Decisions).
Responsibility:
- Manage Community Rating System (CRS) class for premium discounts
- Monitor risk pool and solvency
- Premiums are set federally via Risk Rating 2.0; CRS discount is local
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from broker.components.memory import CognitiveMemory
from broker.utils.agent_config import AgentTypeConfig
from ..environment.risk_rating import calculate_individual_premium

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

    def calculate_premium_for_agent(self, agent: Any) -> float:
        """
        Calculate individualized premium using Risk Rating 2.0 factors.
        """
        return calculate_individual_premium(
            agent_profile={
                "building_rcv": getattr(agent, "building_rcv", getattr(agent, "property_value", 250000)),
                "flood_zone": getattr(agent, "flood_zone", "MEDIUM"),
                "flood_depth_m": getattr(agent, "max_flood_depth", 0.0),
                "house_type": getattr(agent, "house_type", "single_family"),
                "elevated": getattr(agent, "elevated", False),
                "claim_count": getattr(agent, "claim_count", 0),
            },
            community_crs=getattr(self, "crs_discount", 0.0),
        )

    def decide_strategy(self, year: int) -> str:
        """
        Phase 1 Decision: Adjust CRS class (community discount).

        Premiums are set federally via Risk Rating 2.0. This agent manages
        the Community Rating System (CRS) discount, which ranges from 0%
        (Class 10) to 45% (Class 1) in 5% increments.
        """
        loss_ratio = self.state.loss_ratio
        decision = "maintain_crs"
        reasoning = "CRS class appropriate for current conditions"

        crs_discount = getattr(self, "crs_discount", 0.0)

        # Simple Rules (to be replaced/augmented by LLM)
        if loss_ratio < self.params.get("loss_ratio_threshold_low", 0.30) and self.state.uptake_rate < self.params.get("uptake_threshold_low", 0.40):
            decision = "improve_crs"
            reasoning = f"Loss ratio {loss_ratio:.2f} low, improving CRS to attract uptake"
        elif loss_ratio > self.params.get("loss_ratio_threshold_high", 0.80):
            decision = "reduce_crs"
            reasoning = f"Loss ratio {loss_ratio:.2f} too high, scaling back CRS investment"

        # Execute Decision
        if decision == "improve_crs":
            self.crs_discount = min(0.45, crs_discount + 0.05)
        elif decision == "reduce_crs":
            self.crs_discount = max(0.0, crs_discount - 0.05)

        # Log Decision
        self.memory.add_episodic(
            f"Year {year} Decision: {decision} ({reasoning}). CRS discount: {self.crs_discount:.0%}",
            importance=0.7 if decision != "maintain_crs" else 0.2,
            year=year,
            tags=["strategy", "crs"]
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
        return ["IMPROVE", "REDUCE", "MAINTAIN"]
    
    def observe(self, environment: Dict[str, float], agents: Dict[str, Any]) -> Dict[str, float]:
        """Observe environment."""
        return {}
