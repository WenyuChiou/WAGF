"""
State Manager - Multi-level state management for single and multi-agent scenarios.

State Levels:
- Individual: Per-agent state (elevated, has_insurance, damage_history)
- Shared: Environment state visible to all agents (flood_occurred, year)
- Institutional: Policy/rule state (subsidy_rate, policy_mode)
- Aggregated: Computed stats (community_elevated_pct)

This design supports both:
- Single-agent: All agents share same type, use default methods
- Multi-agent: Different agent types with different state access rules
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Type


@dataclass
class IndividualState:
    """Base class for per-agent state. Extend for domain-specific state."""
    agent_id: str
    agent_type: str = "default"
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass 
class SharedState:
    """Environment state visible to all agents."""
    step: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class InstitutionalState:
    """Policy/rule state that can be modified by specific agent types."""
    policy_mode: str = "default"
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class StateManager:
    """
    Manages multi-level state for ABM simulations.
    
    Usage:
        # Single-agent scenario
        manager = StateManager()
        manager.register_agent("Agent_1")
        state = manager.get_individual("Agent_1")
        
        # Multi-agent scenario
        manager = StateManager()
        manager.register_agent("Resident_1", agent_type="resident")
        manager.register_agent("Gov_1", agent_type="government")
        
        # Get context for agent (includes observable state)
        context = manager.get_agent_context("Resident_1")
    """
    
    def __init__(
        self,
        individual_cls: Type[IndividualState] = IndividualState,
        shared_cls: Type[SharedState] = SharedState,
        institutional_cls: Type[InstitutionalState] = InstitutionalState
    ):
        self._individual: Dict[str, IndividualState] = {}
        self._shared: SharedState = shared_cls()
        self._institutional: InstitutionalState = institutional_cls()
        self._individual_cls = individual_cls
        
        # Access rules: which agent types can modify which state levels
        self._write_access = {
            "institutional": ["government", "admin"],  # Only these can modify institutional
        }
    
    # ==================== Registration ====================
    
    def register_agent(self, agent_id: str, agent_type: str = "default", **kwargs) -> IndividualState:
        """Register a new agent with individual state."""
        state = self._individual_cls(agent_id=agent_id, agent_type=agent_type, **kwargs)
        self._individual[agent_id] = state
        return state
    
    def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent."""
        if agent_id in self._individual:
            del self._individual[agent_id]
    
    # ==================== Individual State ====================
    
    def get_individual(self, agent_id: str) -> Optional[IndividualState]:
        """Get individual state for an agent."""
        return self._individual.get(agent_id)
    
    def update_individual(self, agent_id: str, **updates) -> bool:
        """Update individual state. Agent can only update own state."""
        state = self._individual.get(agent_id)
        if state is None:
            return False
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return True
    
    # ==================== Shared State ====================
    
    @property
    def shared(self) -> SharedState:
        """Get shared environment state (read-only for agents)."""
        return self._shared
    
    def update_shared(self, **updates) -> None:
        """Update shared state. System-only, not callable by agents."""
        for key, value in updates.items():
            if hasattr(self._shared, key):
                setattr(self._shared, key, value)
    
    # ==================== Institutional State ====================
    
    @property
    def institutional(self) -> InstitutionalState:
        """Get institutional state."""
        return self._institutional
    
    def update_institutional(self, agent_type: str, **updates) -> bool:
        """
        Update institutional state. Only authorized agent types can update.
        
        Args:
            agent_type: Type of agent attempting update
            **updates: State updates to apply
            
        Returns:
            True if update was allowed and applied
        """
        allowed_types = self._write_access.get("institutional", [])
        if agent_type not in allowed_types and "*" not in allowed_types:
            return False
        
        for key, value in updates.items():
            if hasattr(self._institutional, key):
                setattr(self._institutional, key, value)
        return True
    
    # ==================== Aggregated State ====================
    
    def get_aggregated(self, key: str) -> Any:
        """
        Get computed aggregate statistics.
        
        Override in subclass for domain-specific aggregations.
        """
        if key == "agent_count":
            return len(self._individual)
        elif key == "agent_types":
            return list(set(s.agent_type for s in self._individual.values()))
        return None
    
    # ==================== Context Building ====================
    
    def get_agent_context(
        self, 
        agent_id: str, 
        include_neighbors: bool = False,
        neighbor_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        Build complete context for an agent's decision-making.
        
        Args:
            agent_id: Agent to build context for
            include_neighbors: Whether to include neighbor states
            neighbor_ids: Specific neighbors to include (optional)
            
        Returns:
            Context dict with individual, shared, institutional state
        """
        individual = self.get_individual(agent_id)
        if individual is None:
            return {}
        
        context = {
            "agent_id": agent_id,
            "agent_type": individual.agent_type,
            "individual": individual.to_dict(),
            "shared": self._shared.to_dict(),
            "institutional": self._institutional.to_dict(),
        }
        
        # Optional neighbor observation
        if include_neighbors and neighbor_ids:
            neighbor_states = []
            for nid in neighbor_ids:
                neighbor = self.get_individual(nid)
                if neighbor and nid != agent_id:
                    # Only include observable fields
                    neighbor_states.append({
                        "agent_id": nid,
                        "agent_type": neighbor.agent_type,
                    })
            context["neighbors"] = neighbor_states
        
        return context
    
    # ==================== Utilities ====================
    
    def list_agents(self, agent_type: Optional[str] = None) -> List[str]:
        """List all agent IDs, optionally filtered by type."""
        if agent_type is None:
            return list(self._individual.keys())
        return [aid for aid, state in self._individual.items() 
                if state.agent_type == agent_type]
    
    def get_all_individual(self) -> Dict[str, IndividualState]:
        """Get all individual states."""
        return self._individual.copy()
