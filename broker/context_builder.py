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
        state = context.get("state", {})
        state_str = self._format_state(state)
        perception_str = self._format_perception(context.get("perception", {}))
        objectives_str = self._format_objectives(context.get("objectives", {}))
        skills_str = ", ".join(context.get("available_skills", []))
        memory_str = context.get("memory", "No memory available")
        
        # Prepare template variables
        # Base variables
        template_vars = {
            "agent_name": context.get("agent_name", "Agent"),
            "agent_type": agent_type,
            "state": state_str,
            "perception": perception_str,
            "objectives": objectives_str,
            "skills": skills_str,
            "memory": memory_str
        }
        
        # Add individual state variables (for custom templates)
        # e.g. {loss_ratio}
        template_vars.update(state)
        
        # Add raw state variables if present (prioritize over normalized?)
        # Usually we want normalized in prompt, but maybe raw for specific metrics
        if "state_raw" in context:
            template_vars.update(context["state_raw"])
            
        # Add perception variables
        if "perception" in context:
            template_vars.update(context["perception"])
            
        # Add extra context keys (like 'budget_remaining' if passed in context root)
        template_vars.update({k: v for k, v in context.items() 
                            if k not in template_vars and isinstance(v, (str, int, float))})
            
        return template.format(**template_vars)
    
    def _format_state(self, state: Dict[str, float], compact: bool = True) -> str:
        """Format normalized state. Compact: inline, Verbose: multiline."""
        if compact:
            # Add semantic labels: LOW(<0.3), MED(0.3-0.7), HIGH(>0.7)
            # Filter distinct numeric values only
            return " ".join(
                f"{k}={v:.2f}({self._semantic(v)})" 
                for k, v in state.items() 
                if isinstance(v, (int, float))
            )
        return "\n".join(f"- {k}: {v:.2f}" for k, v in state.items()) or "No state"
    
    def _semantic(self, v: float) -> str:
        """Convert 0-1 value to semantic label."""
        if v < 0.3: return "L"
        if v > 0.7: return "H"
        return "M"
    
    def _format_perception(self, perception: Dict[str, float], compact: bool = True) -> str:
        """Format perception signals."""
        if compact:
            return " ".join(f"{k}={v:.2f}" for k, v in perception.items()) or "-"
        return "\n".join(f"- {k}: {v:.2f}" for k, v in perception.items()) or "No signals"
    
    def _format_objectives(self, objectives: Dict[str, Dict], compact: bool = True) -> str:
        """Format objectives with status."""
        if compact:
            # Show: name=current(status) where status is ✓=in_range, ✗=out
            return " ".join(
                f"{n}={info.get('current',0):.2f}{'✓' if info.get('in_range') else '✗'}"
                for n, info in objectives.items()
            ) or "-"
        # Verbose format
        lines = []
        for name, info in objectives.items():
            status = "✓" if info.get("in_range") else "✗"
            current = info.get("current", 0)
            target = info.get("target", (0, 1))
            lines.append(f"- {name}: {current:.2f} ({target[0]:.2f}-{target[1]:.2f}) {status}")
        return "\n".join(lines) if lines else "No objectives"


# Compact token-efficient prompt template with LLM interpretation
DEFAULT_PROMPT_TEMPLATE = """[{agent_type}:{agent_name}]

STATE:{state}
OBS:{perception}
MEM:{memory}
OBJ:{objectives}
ACT:{skills}

OUTPUT:
INTERPRET:[1-line summary of your situation]
DECIDE:[action] ADJ:[0-0.15] REASON:[1-line]"""


# Verbose template for debugging/analysis
VERBOSE_PROMPT_TEMPLATE = """You are {agent_name}, a {agent_type} agent.

=== STATE (0-1) ===
{state}

=== OBSERVATIONS ===
{perception}

=== MEMORY ===
{memory}

=== OBJECTIVES ===
{objectives}

=== ACTIONS ===
{skills}

DECIDE: action, adjustment(0.00-0.15), justification
"""


# Convenience function to create context builder from agents
def create_context_builder(
    agents: Dict[str, Any],
    environment: Dict[str, float] = None,
    custom_templates: Dict[str, str] = None,
    load_yaml: bool = True,
    yaml_path: str = None
) -> BaseAgentContextBuilder:
    """
    Create a context builder for a set of agents.
    
    Args:
        agents: Dict of agent_name -> BaseAgent instances
        environment: Shared environment state
        custom_templates: Optional custom prompt templates per agent_type
        load_yaml: If True, load templates from YAML file
        yaml_path: Optional path to YAML file (default: broker/prompt_templates.yaml)
    
    Returns:
        Configured BaseAgentContextBuilder
    """
    templates = {}
    
    # Load from YAML if requested
    if load_yaml:
        templates = load_prompt_templates(yaml_path)
    
    # Override with custom templates
    if custom_templates:
        templates.update(custom_templates)
    
    return BaseAgentContextBuilder(
        agents=agents,
        environment=environment,
        prompt_templates=templates
    )


def load_prompt_templates(
    yaml_path: str = None
) -> Dict[str, str]:
    """
    Load prompt templates from YAML file.
    
    Args:
        yaml_path: Path to YAML file (default: broker/prompt_templates.yaml)
    
    Returns:
        Dict mapping agent_type to template string
    """
    import yaml
    from pathlib import Path
    
    if yaml_path is None:
        yaml_path = Path(__file__).parent / "prompt_templates.yaml"
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Extract template strings from YAML structure
        templates = {}
        for key, value in data.items():
            if isinstance(value, dict) and 'template' in value:
                templates[key] = value['template']
            elif isinstance(value, str):
                templates[key] = value
        
        return templates
    except FileNotFoundError:
        return {}

