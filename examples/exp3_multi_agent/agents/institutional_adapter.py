"""
Institutional Agent Adapter for Exp3

This module bridges the gap between the old exp3 agent interface
and the new generic BaseAgent framework.

The adapter allows exp3 to gradually adopt the new framework
while maintaining backward compatibility with existing code.
"""

from typing import Dict, Any, Optional
from pathlib import Path

# Import from generic framework
from agents import BaseAgent, load_agents, normalize, denormalize
from agents.base_agent import AgentConfig
from broker.generic_context_builder import BaseAgentContextBuilder, create_context_builder
from broker.memory import CognitiveMemory


class InstitutionalAgentAdapter:
    """
    Adapter that wraps BaseAgent with exp3-compatible interface.
    
    Provides:
    - Same method signatures as old InsuranceAgent/GovernmentAgent
    - Automatic 0-1 normalization under the hood
    - Access to BaseAgent's objectives/constraints
    """
    
    def __init__(self, base_agent: BaseAgent):
        self.agent = base_agent
        self.memory = CognitiveMemory(base_agent.name)
    
    @property
    def state(self):
        """Return a dict-like object for backward compatibility."""
        return AgentStateProxy(self.agent)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent state (normalized + raw)."""
        return self.agent.to_dict()
    
    def get_skills(self):
        """Get available skills."""
        return self.agent.get_available_skills()
    
    def execute_skill(self, skill_id: str, adjustment: float = 0.05) -> bool:
        """Execute a skill with adjustment."""
        return self.agent.execute_skill(skill_id, adjustment)
    
    def evaluate_objectives(self) -> Dict[str, Dict]:
        """Evaluate current state against objectives."""
        return self.agent.evaluate_objectives()


class AgentStateProxy:
    """
    Proxy object that provides dict-like access to agent state.
    
    Maps old raw field names to normalized values and back.
    """
    
    def __init__(self, agent: BaseAgent):
        self._agent = agent
    
    def __getattr__(self, name: str):
        # Try normalized state first
        if name in self._agent._state_normalized:
            return self._agent.get_state_raw(name)
        # Special properties
        if name == "id":
            return self._agent.name
        if name == "loss_ratio":
            return self._agent.get_state_raw("loss_ratio")
        raise AttributeError(f"'{name}' not found in agent state")
    
    def __setattr__(self, name: str, value):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            # Find the param config to normalize
            param_config = next(
                (p for p in self._agent.config.state_params if p.name == name),
                None
            )
            if param_config:
                normalized = normalize(value, *param_config.raw_range)
                self._agent.set_state(name, normalized)


# ============================================================================
# Compatibility Layer for Exp3
# ============================================================================

class InsuranceAgentAdapter(InstitutionalAgentAdapter):
    """Insurance-specific adapter with old interface methods."""
    
    def reset_annual_metrics(self):
        """Reset annual tracking (premium_collected, claims_paid)."""
        # These would be tracked externally in exp3
        pass
    
    def decide_strategy(self, year: int) -> str:
        """
        Phase 1 decision (backward compatible).
        Returns decision string: raise_premium, lower_premium, maintain_premium
        """
        # Evaluate objectives to determine action
        obj_eval = self.evaluate_objectives()
        
        loss_ratio_info = obj_eval.get("target_loss_ratio", {})
        solvency_info = obj_eval.get("maintain_solvency", {})
        
        # Decision logic based on objectives
        if not loss_ratio_info.get("in_range", True):
            current = loss_ratio_info.get("current", 0.5)
            target = loss_ratio_info.get("target", (0.4, 0.53))
            if current > target[1]:
                decision = "raise_premium"
            else:
                decision = "lower_premium"
        else:
            decision = "maintain_premium"
        
        # Log to memory
        self.memory.add_episodic(
            f"Year {year} Decision: {decision}",
            importance=0.6,
            year=year,
            tags=["strategy"]
        )
        
        return decision


class GovernmentAgentAdapter(InstitutionalAgentAdapter):
    """Government-specific adapter with old interface methods."""
    
    def reset_annual_budget(self, year: int):
        """Reset budget at start of year."""
        self.agent.set_state("budget_used", 0.0)
        self.memory.add_episodic(
            f"Year {year}: Budget reset",
            importance=0.1,
            year=year,
            tags=["budget"]
        )
    
    def decide_policy(self, year: int, flood_occurred_prev_year: bool) -> str:
        """
        Phase 1 decision (backward compatible).
        Returns decision string: increase_subsidy, decrease_subsidy, maintain_subsidy
        """
        obj_eval = self.evaluate_objectives()
        
        mg_info = obj_eval.get("increase_mg_adoption", {})
        budget_info = obj_eval.get("budget_efficiency", {})
        
        # Decision logic
        if flood_occurred_prev_year and not mg_info.get("in_range", True):
            if mg_info.get("current", 0.5) < mg_info.get("target", (0.4, 0.7))[0]:
                decision = "increase_subsidy"
            else:
                decision = "maintain_subsidy"
        elif budget_info.get("current", 0.5) > 0.9:
            decision = "decrease_subsidy"
        else:
            decision = "maintain_subsidy"
        
        self.memory.add_episodic(
            f"Year {year} Decision: {decision}",
            importance=0.6,
            year=year,
            tags=["policy"]
        )
        
        return decision
    
    def update_metrics(self, mg_adopt: float, nmg_adopt: float):
        """Update adoption metrics."""
        self.agent.set_state("mg_adoption", mg_adopt)
        self.agent.set_state("nmg_adoption", nmg_adopt)
        self.agent.set_state("equity_gap", abs(nmg_adopt - mg_adopt))


# ============================================================================
# Factory Function
# ============================================================================

def load_exp3_institutional_agents(
    yaml_path: str = None
) -> Dict[str, InstitutionalAgentAdapter]:
    """
    Load institutional agents from YAML config.
    
    Returns dict with InsuranceCo and StateGov adapters.
    """
    if yaml_path is None:
        yaml_path = Path(__file__).parent / "institutional_agents.yaml"
    
    base_agents = load_agents(str(yaml_path))
    
    adapters = {}
    for name, agent in base_agents.items():
        if agent.agent_type == "insurance":
            adapters[name] = InsuranceAgentAdapter(agent)
        elif agent.agent_type == "government":
            adapters[name] = GovernmentAgentAdapter(agent)
        else:
            adapters[name] = InstitutionalAgentAdapter(agent)
    
    return adapters
