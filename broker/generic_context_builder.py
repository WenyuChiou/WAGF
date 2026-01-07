"""
Generic Context Builder - Builds bounded context for any agent type.

Works with BaseAgent to provide 0-1 normalized state in prompts.
Supports multi-agent scenarios where agents observe each other.
"""
from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod


class ContextBuilder(ABC):
    """
    Abstract base class for building LLM context.
    
    All values in context should be 0-1 normalized when possible.
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
            observable: Optional list of observable categories
        
        Returns:
            Dict with observable signals only (0-1 normalized where applicable).
        """
        pass
    
    @abstractmethod
    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format context into LLM prompt."""
        pass


class BaseAgentContextBuilder(ContextBuilder):
    """
    Context builder that works with BaseAgent instances.
    
    Features:
    - Automatically uses 0-1 normalized state
    - Supports multi-agent observation
    - Works with any user-defined agent type
    """
    
    def __init__(
        self,
        agents: Dict[str, Any],  # Dict[str, BaseAgent]
        environment: Dict[str, float] = None,
        prompt_templates: Dict[str, str] = None
    ):
        """
        Args:
            agents: Dict mapping agent names to BaseAgent instances
            environment: Shared environment state (0-1 normalized)
            prompt_templates: Dict mapping agent_type to prompt template
        """
        self.agents = agents
        self.environment = environment or {}
        self.prompt_templates = prompt_templates or {}
    
    def build(
        self, 
        agent_id: str,
        observable: Optional[List[str]] = None,
        include_memory: bool = True,
        include_raw: bool = False
    ) -> Dict[str, Any]:
        """Build context from agent's normalized state and perception.
        
        Args:
            agent_id: Agent to build context for
            observable: Optional categories to include
            include_memory: Include formatted memory
            include_raw: Include raw (denormalized) values alongside 0-1
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return {"agent_id": agent_id, "error": "Agent not found"}
        
        # Get agent's normalized state
        context = {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "agent_type": agent.agent_type,
            "state": agent.get_all_state(),  # 0-1 normalized
        }
        
        # Optionally add raw values for readability
        if include_raw:
            context["state_raw"] = agent.get_all_state_raw()
        
        # Add perception from environment and other agents
        perception = agent.observe(self.environment, self.agents)
        context["perception"] = perception
        
        # Add objectives evaluation
        context["objectives"] = agent.evaluate_objectives()
        
        # Add available skills
        context["available_skills"] = agent.get_available_skills()
        
        # Add memory if available
        if include_memory:
            context["memory"] = self._get_memory(agent)
        
        # Add neighbor summary if observable
        observable = observable or []
        if "neighbors" in observable:
            context["neighbors"] = self._get_neighbor_summary(agent_id)
        
        return context
    
    def _get_memory(self, agent) -> str:
        """Get formatted memory from agent's memory module."""
        if hasattr(agent, 'memory') and agent.memory:
            if hasattr(agent.memory, 'format_for_prompt'):
                return agent.memory.format_for_prompt()
            elif hasattr(agent.memory, 'retrieve'):
                memories = agent.memory.retrieve(top_k=5)
                return "\n".join([m[0] if isinstance(m, tuple) else str(m) for m in memories])
        return "No memory available"
    
    def _get_neighbor_summary(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get summary of neighbor agents' observable state."""
        summaries = []
        for name, agent in self.agents.items():
            if name != agent_id:
                summaries.append({
                    "agent_name": name,
                    "agent_type": agent.agent_type,
                    "state_summary": {
                        k: round(v, 2) for k, v in list(agent.get_all_state().items())[:3]
                    }
                })
        return summaries[:5]  # Limit to 5 neighbors
    
    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format using agent-type-specific template."""
        agent_type = context.get("agent_type", "default")
        template = self.prompt_templates.get(agent_type, DEFAULT_PROMPT_TEMPLATE)
        
        # Build formatted sections
        state_str = self._format_state(context.get("state", {}))
        perception_str = self._format_perception(context.get("perception", {}))
        objectives_str = self._format_objectives(context.get("objectives", {}))
        skills_str = ", ".join(context.get("available_skills", []))
        memory_str = context.get("memory", "No memory available")
        
        return template.format(
            agent_name=context.get("agent_name", "Agent"),
            agent_type=agent_type,
            state=state_str,
            perception=perception_str,
            objectives=objectives_str,
            skills=skills_str,
            memory=memory_str
        )
    
    def _format_state(self, state: Dict[str, float]) -> str:
        """Format normalized state for prompt."""
        lines = []
        for param, value in state.items():
            # Show as percentage or decimal
            lines.append(f"- {param}: {value:.2f}")
        return "\n".join(lines) if lines else "No state"
    
    def _format_perception(self, perception: Dict[str, float]) -> str:
        """Format perception signals."""
        lines = []
        for signal, value in perception.items():
            lines.append(f"- {signal}: {value:.2f}")
        return "\n".join(lines) if lines else "No external signals"
    
    def _format_objectives(self, objectives: Dict[str, Dict]) -> str:
        """Format objectives with status."""
        lines = []
        for name, info in objectives.items():
            status = "✓" if info.get("in_range") else "✗"
            current = info.get("current", 0)
            target = info.get("target", (0, 1))
            lines.append(f"- {name}: {current:.2f} (target: {target[0]:.2f}-{target[1]:.2f}) {status}")
        return "\n".join(lines) if lines else "No objectives defined"


# Default prompt template for any agent type
DEFAULT_PROMPT_TEMPLATE = """You are {agent_name}, a {agent_type} agent.

=== CURRENT STATE (0-1 scale) ===
{state}

=== OBSERVATIONS ===
{perception}

=== MEMORY ===
{memory}

=== OBJECTIVES ===
{objectives}

=== AVAILABLE ACTIONS ===
{skills}

=== YOUR TASK ===
Based on your current state, memory, and objectives, decide your next action.

=== OUTPUT FORMAT ===
Decision: [one of the available actions]
Adjustment: [0.00-0.15 if applicable]
Justification: [brief explanation]
"""


# Convenience function to create context builder from agents
def create_context_builder(
    agents: Dict[str, Any],
    environment: Dict[str, float] = None,
    custom_templates: Dict[str, str] = None
) -> BaseAgentContextBuilder:
    """
    Create a context builder for a set of agents.
    
    Args:
        agents: Dict of agent_name -> BaseAgent instances
        environment: Shared environment state
        custom_templates: Optional custom prompt templates per agent_type
    
    Returns:
        Configured BaseAgentContextBuilder
    """
    return BaseAgentContextBuilder(
        agents=agents,
        environment=environment,
        prompt_templates=custom_templates or {}
    )
