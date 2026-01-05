"""
Household Agent (Exp3)

The Household Agent works in Phase 2 (Household Decisions).
Responsibility:
- Evaluate flood risk (Threat Appraisal)
- Evaluate mitigation options (Coping Appraisal)
- Make decisions: Do Nothing, Buy Insurance, Elevate, Relocate
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from broker.memory import CognitiveMemory

@dataclass
class HouseholdAgentState:
    id: str
    agent_type: str = "NMG_Owner"    # MG_Owner, MG_Renter, NMG_Owner, NMG_Renter
    income: float = 50_000
    property_value: float = 300_000
    
    # Adaptation Status
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    
    # Trust & Perception (0.0 - 1.0)
    trust_in_government: float = 0.5
    trust_in_insurance: float = 0.5
    trust_in_neighbors: float = 0.5
    
    # Financial Tracking
    cumulative_damage: float = 0.0
    cumulative_oop: float = 0.0      # Out-of-pocket costs
    
    # Memory
    memory: Optional[CognitiveMemory] = None

class HouseholdAgent:
    """
    Household Agent implementation.
    """
    
    def __init__(self, agent_id: str, agent_type: str, income: float, property_value: float):
        self.state = HouseholdAgentState(
            id=agent_id, 
            agent_type=agent_type,
            income=income,
            property_value=property_value
        )
        self.memory = CognitiveMemory(agent_id)
        self.state.memory = self.memory

    def make_decision(self, year: int, context: Dict[str, Any]) -> str:
        """
        Phase 2 Decision: Choose adaptation action.
        This normally involves the LLM (ContextBuilder -> LLM -> Validator).
        Here we define the method signature and perhaps a simple heuristic fallback.
        """
        # In full experiment:
        # prompt = context_builder.build(self, context)
        # response = llm.generate(prompt)
        # return response.skill
        
        # Placeholder Heuristic
        if not self.state.has_insurance and self.state.trust_in_insurance > 0.6:
            return "buy_insurance"
        elif not self.state.elevated and "Owner" in self.state.agent_type and self.state.property_value > 200_000:
            # Maybe elevate if subsidy is good? (Need to check context)
            subsidy_available = context.get("government_subsidy_rate", 0) > 0.6
            if subsidy_available:
                return "elevate_house"
                
        return "do_nothing"

    def apply_decision(self, decision: str, year: int):
        """Updates state based on decision execution."""
        if decision == "buy_insurance":
            self.state.has_insurance = True
            # Cost/Deductible handling usually in Settlement or here? 
            # Usually strict state update here, financial flow in Settlement.
            
        elif decision == "elevate_house":
            self.state.elevated = True
            
        elif decision == "relocate":
            self.state.relocated = True
            
        # Log to memory
        self.memory.add_episodic(
            f"Year {year}: Decided to {decision}",
            importance=0.5,
            year=year,
            tags=["decision"]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.state.id,
            "agent_type": self.state.agent_type,
            "elevated": self.state.elevated,
            "has_insurance": self.state.has_insurance,
            "trust_insurance": self.state.trust_in_insurance,
            "memory": self.memory.format_for_prompt()
        }
