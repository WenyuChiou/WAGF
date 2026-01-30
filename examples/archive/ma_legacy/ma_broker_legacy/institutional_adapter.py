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
from cognitive_governance.agents import BaseAgent, load_agents, normalize, denormalize, AgentConfig
from broker.components.context_builder import BaseAgentContextBuilder, create_context_builder
from broker.components.memory import CognitiveMemory


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
    Handles legacy field names used in run_experiment.py.
    """
    
    # Legacy field mappings: old_name -> (new_name, raw_range for denormalization)
    LEGACY_MAPPINGS = {
        # Government fields
        "annual_budget": ("budget_used", (0, 500000), 500000),  # Fixed value
        "budget_remaining": ("budget_used", (0, 500000), "invert"),  # 500k - spent
        "subsidy_rate": ("subsidy_rate", (0.20, 0.95), None),  # Direct mapping
        "mg_priority": None,  # Not in BaseAgent, return True
        "mg_adoption_rate": ("mg_adoption", (0, 1), None),
        "nmg_adoption_rate": ("nmg_adoption", (0, 1), None),
        
        # Insurance fields
        "risk_pool": ("solvency", (0, 2000000), None),
        "premium_rate": ("premium_rate", (0.02, 0.15), None),
        "premium_collected": None,  # Track externally
        "claims_paid": None,  # Track externally
        "total_policies": None,
        "uptake_rate": ("market_share", (0, 1), None),
    }
    
    def __init__(self, agent: BaseAgent):
        self._agent = agent
        # Storage for fields not in BaseAgent
        self._external = {
            "mg_priority": True,
            "premium_collected": 0,
            "claims_paid": 0,
            "total_policies": 0,
        }
    
    def __getattr__(self, name: str):
        # Special id property
        if name == "id":
            return self._agent.name
        
        # Check external storage
        if name in self._external:
            return self._external[name]
        
        # Check legacy mappings
        if name in self.LEGACY_MAPPINGS:
            mapping = self.LEGACY_MAPPINGS[name]
            if mapping is None:
                return self._external.get(name, None)
            
            new_name, raw_range, special = mapping
            normalized = self._agent.get_state(new_name)
            
            if special == "invert":
                # budget_remaining = annual - spent
                return raw_range[1] - denormalize(normalized, *raw_range)
            elif special is not None:
                return special  # Fixed value
            else:
                return denormalize(normalized, *raw_range)
        
        # Try direct normalized state access
        if name in self._agent._state_normalized:
            return self._agent.get_state_raw(name)
        
        raise AttributeError(f"'{name}' not found in agent state")
    
    def __setattr__(self, name: str, value):
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        
        # Check external storage
        if name in getattr(self, '_external', {}):
            self._external[name] = value
            return
        
        # Check legacy mappings
        if name in self.LEGACY_MAPPINGS:
            mapping = self.LEGACY_MAPPINGS[name]
            if mapping is None:
                self._external[name] = value
                return
            
            new_name, raw_range, special = mapping
            if special == "invert":
                # Setting budget_remaining -> calculate budget_used
                spent = raw_range[1] - value
                normalized = normalize(spent, *raw_range)
            else:
                normalized = normalize(value, *raw_range)
            self._agent.set_state(new_name, normalized)
            return
        
        # Try direct state access
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
    
    def build_prompt_compact(self) -> str:
        """Build token-efficient prompt for LLM decision-making."""
        from examples.exp3_multi_agent.prompts import build_insurance_prompt_compact
        
        # Build state dict compatible with prompt function
        state = {
            'loss_ratio': self.agent.get_state('loss_ratio'),
            'solvency': self.agent.get_state('solvency'),
            'premium_rate': self.agent.get_state_raw('premium_rate'),
            'market_share': self.agent.get_state('market_share'),
            'total_policies': self.state.total_policies,
            'risk_pool': self.state.risk_pool,
        }
        
        # Retrieve memory
        memory = self.memory.retrieve(top_k=3)
        memory_texts = [m[0] if isinstance(m, tuple) else str(m) for m in memory]
        
        return build_insurance_prompt_compact(state, memory_texts)
    
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
    
    def build_prompt_compact(self) -> str:
        """Build token-efficient prompt for LLM decision-making."""
        from examples.exp3_multi_agent.prompts import build_government_prompt_compact
        
        # Build state dict compatible with prompt function
        state = {
            'annual_budget': 500000,  # Fixed
            'budget_remaining': self.state.budget_remaining,
            'subsidy_rate': self.agent.get_state_raw('subsidy_rate'),
            'mg_adoption_rate': self.agent.get_state('mg_adoption'),
            'nmg_adoption_rate': self.agent.get_state('nmg_adoption'),
        }
        
        # Retrieve memory
        memory = self.memory.retrieve(top_k=3)
        events = [m[0] if isinstance(m, tuple) else str(m) for m in memory]
        
        return build_government_prompt_compact(state, events)
    
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
