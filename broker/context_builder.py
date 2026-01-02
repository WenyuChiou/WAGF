"""
Context Builder - Builds bounded context for LLM.

Responsibilities:
- Fetch observable signals (READ-ONLY)
- Format prompt with bounded information
- Enforce information boundaries
"""
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod


class ContextBuilder(ABC):
    """
    Abstract base class for building LLM context.
    
    Subclass this for domain-specific context building.
    """
    
    @abstractmethod
    def build(
        self, 
        agent_id: str,
        observable: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build bounded context for an agent.
        
        Args:
            agent_id: The agent to build context for
            observable: Optional list of observable categories:
                - "neighbors": Include neighbor actions
                - "community": Include community statistics
                - "institutional": Include policy state
        
        Returns:
            Dict with observable signals only.
            Must NOT include hidden state variables.
        """
        pass
    
    def build_with_neighbors(
        self,
        agent_id: str,
        neighbor_ids: List[str],
        include_actions: bool = True
    ) -> Dict[str, Any]:
        """
        Build context with neighbor observation.
        
        Default implementation delegates to build() with neighbors.
        Override for custom neighbor handling.
        """
        context = self.build(agent_id, observable=["neighbors", "community"])
        context["neighbor_ids"] = neighbor_ids
        return context
    
    @abstractmethod
    def format_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format context into LLM prompt.
        
        Args:
            context: Bounded context from build()
            
        Returns:
            Formatted prompt string
        """
        pass
    
    @abstractmethod
    def get_memory(self, agent_id: str) -> List[str]:
        """
        Get current memory state for agent.
        
        Used for audit trail (memory_post).
        """
        pass


class SimpleContextBuilder(ContextBuilder):
    """
    Simple implementation for toy domains.
    
    Supports observable categories:
    - neighbors: Include neighbor recent actions
    - community: Include aggregated community stats
    - institutional: Include policy/rule state
    """
    
    def __init__(
        self,
        state_provider: Any,
        prompt_template: str,
        observable_fields: List[str],
        neighbor_provider: Optional[Any] = None
    ):
        self.state_provider = state_provider
        self.prompt_template = prompt_template
        self.observable_fields = observable_fields
        self.neighbor_provider = neighbor_provider
    
    def build(
        self, 
        agent_id: str,
        observable: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Build context from observable fields only."""
        full_state = self.state_provider.get_agent_state(agent_id)
        
        # Filter to observable fields only
        context = {
            k: v for k, v in full_state.items() 
            if k in self.observable_fields
        }
        context["agent_id"] = agent_id
        
        # Add observable categories if requested
        observable = observable or []
        
        if "neighbors" in observable and self.neighbor_provider:
            context["neighbor_actions"] = self._get_neighbor_actions(agent_id)
        
        if "community" in observable and self.neighbor_provider:
            context["community_stats"] = self._get_community_stats()
        
        if "institutional" in observable:
            context["institutional"] = self._get_institutional_state()
        
        return context
    
    def _get_neighbor_actions(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get recent actions of neighbors."""
        if not self.neighbor_provider:
            return []
        neighbor_ids = self.neighbor_provider.get_neighbors(agent_id)
        return [
            {
                "agent_id": nid,
                "last_action": self.neighbor_provider.get_last_action(nid)
            }
            for nid in neighbor_ids[:5]  # Limit to 5 neighbors
        ]
    
    def _get_community_stats(self) -> Dict[str, Any]:
        """Get aggregated community statistics."""
        if not self.neighbor_provider:
            return {}
        return self.neighbor_provider.get_community_stats()
    
    def _get_institutional_state(self) -> Dict[str, Any]:
        """Get institutional/policy state."""
        if hasattr(self.state_provider, 'get_institutional_state'):
            return self.state_provider.get_institutional_state()
        return {}
    
    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format using template."""
        return self.prompt_template.format(**context)
    
    def get_memory(self, agent_id: str) -> List[str]:
        """Get agent memory."""
        state = self.state_provider.get_agent_state(agent_id)
        return state.get("memory", [])

