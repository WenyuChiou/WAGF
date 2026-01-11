"""
Generic Context Builder - Builds bounded context for any agent type.

Works with BaseAgent to provide 0-1 normalized state in prompts.
Supports multi-agent scenarios where agents observe each other.
"""
from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod
import string

from .memory_engine import MemoryEngine

class SafeFormatter(string.Formatter):
    """
    Formatter that handles missing keys gracefully by returning a placeholder.
    Essential for heterogeneous demographic data.
    """
    def __init__(self, placeholder: str = "[N/A]"):
        self.placeholder = placeholder
        super().__init__()

    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            return kwargs.get(key, self.placeholder)
        return super().get_value(key, args, kwargs)


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
        prompt_templates: Dict[str, str] = None,
        memory_engine: Optional[MemoryEngine] = None
    ):
        """
        Args:
            agents: Dict mapping agent names to BaseAgent instances
            environment: Shared environment state (0-1 normalized)
            prompt_templates: Dict mapping agent_type to prompt template
            memory_engine: Engine for retrieving agent memory
        """
        self.agents = agents
        self.environment = environment or {}
        self.prompt_templates = prompt_templates or {}
        self.memory_engine = memory_engine
    
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
            
        # Add flood-specific attributes to context if present on agent
        for attr in ['elevated', 'has_insurance', 'relocated', 'flood_threshold', 'trust_in_insurance', 'trust_in_neighbors', 'flood']:
            if hasattr(agent, attr):
                context[attr] = getattr(agent, attr)
                
        # Add custom attributes if present
        if hasattr(agent, 'custom_attributes') and agent.custom_attributes:
            context.update(agent.custom_attributes)
        
        return context
    
    def _get_memory(self, agent) -> List[str]:
        """Get formatted memory via MemoryEngine."""
        if self.memory_engine:
            return self.memory_engine.retrieve(agent, top_k=3)
        
        # Fallback to direct attribute if engine not set (for standalone tests)
        if hasattr(agent, 'memory') and isinstance(agent.memory, list):
            return agent.memory[-3:]
            
        return []
    
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
        memory_val = context.get("memory", [])
        if isinstance(memory_val, list):
            # Baseline uses: "- {item}" prefix for each memory line
            memory_str = "\n".join(f"- {m}" for m in memory_val) if memory_val else "No memory available"
        else:
            memory_str = str(memory_val)
        
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
            
        return SafeFormatter().format(template, **template_vars)
    
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

from .interaction_hub import InteractionHub

class TieredContextBuilder(BaseAgentContextBuilder):
    """
    PR 2: Hierarchical Context Builder (T0, T1, T2).
    
    Tiers:
    - Tier 0: Personal (Internal state/memory)
    - Tier 1: Local (Social Gossip & Spatial Observation)
    - Tier 2: Global (Institutional/Public News)
    """
    def __init__(
        self,
        agents: Dict[str, Any],
        hub: InteractionHub,
        skill_registry: Optional[Any] = None,
        global_news: List[str] = None,
        prompt_templates: Dict[str, str] = None,
        memory_engine: Optional[MemoryEngine] = None
    ):
        super().__init__(agents=agents, prompt_templates=prompt_templates, memory_engine=memory_engine)
        self.hub = hub
        self.skill_registry = skill_registry
        self.global_news = global_news or []

    def _verbalize_trust(self, trust_value: float, category: str) -> str:
        """Converts a float (0-1) into a natural language description (Legacy Parity)."""
        if category == "insurance":
            if trust_value >= 0.8: return "strongly trust"
            elif trust_value >= 0.5: return "moderately trust"
            elif trust_value >= 0.2: return "have slight doubts about"
            else: return "deeply distrust"
        elif category == "neighbors":
            if trust_value >= 0.8: return "highly rely on"
            elif trust_value >= 0.5: return "generally trust"
            elif trust_value >= 0.2: return "are skeptical of"
            else: return "completely ignore"
        return "trust"

    def build(self, agent_id: str, **kwargs) -> Dict[str, Any]:
        """Build context using the InteractionHub's tiered logic."""
        return self.hub.build_tiered_context(agent_id, self.agents, self.global_news)

    def format_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format the tiered context into a grounded prompt (Generic).
        Flattens Personal, Local, and Global tiers into template variables.
        """
        # 1. Prepare template variables
        template_vars = {}
        
        # Flatten Personal (Tier 0)
        p = context.get('personal', {})
        for k, v in p.items():
            if isinstance(v, (str, int, float, bool)):
                template_vars[k] = v
                template_vars[f"p_{k}"] = v # Explicit prefix
        
        # Add status from nested dict if present
        if isinstance(p.get('status'), dict):
            for k, v in p['status'].items():
                if k not in template_vars:
                    template_vars[k] = v
        
        # Flatten Local (Tier 1)
        l = context.get('local', {})
        spatial = l.get('spatial', {})
        for k, v in spatial.items():
            template_vars[k] = v
            template_vars[f"spatial_{k}"] = v
            
        social = l.get('social', [])
        template_vars["social_gossip"] = "\n".join([f"- {s}" for s in social]) if social else ""
        
        # Flatten Global (Tier 2)
        g = context.get('global', [])
        template_vars["global_news"] = "\n".join([f"- {news}" for news in g]) if g else ""
        
        # Add special sections for modular UI templates
        template_vars["personal_section"] = self._format_generic_section("MY STATUS & HISTORY", p)
        template_vars["local_section"] = self._format_generic_section("LOCAL NEIGHBORHOOD", l)
        template_vars["global_section"] = self._format_generic_section("WORLD EVENTS", {"news": g})

        # 2. Options Section (Universal)
        agent_id = p.get('id')
        agent = self.agents.get(agent_id)
        
        options_text = ""
        valid_choices_text = ""
        
        if agent:
            available_skills = agent.get_available_skills()
            formatted_options = []
            for i, skill_item in enumerate(available_skills, 1):
                # Format: "1. Skill Description"
                skill_id = skill_item.split(": ", 1)[0] if ": " in skill_item else skill_item
                skill_def = self.skill_registry.get(skill_id) if self.skill_registry else None
                desc = skill_def.description if skill_def else skill_item
                formatted_options.append(f"{i}. {desc}")
            
            options_text = "\n".join(formatted_options)
            
            # Helper for "1, 2, or 3"
            indices = [str(i+1) for i in range(len(available_skills))]
            if len(indices) > 1:
                valid_choices_text = ", ".join(indices[:-1]) + ", or " + indices[-1]
            elif indices:
                valid_choices_text = indices[0]

        template_vars["options_text"] = options_text
        template_vars["valid_choices_text"] = valid_choices_text
        template_vars["skills_text"] = options_text # Alias
        
        # 3. Use template (Generic lookup)
        agent_type = p.get('agent_type', 'default')
        default_template = "{personal_section}\n\n{local_section}\n\n{global_section}\n\n### [AVAILABLE OPTIONS]\n{options_text}"
        template = self.prompt_templates.get(agent_type, default_template)
        
        return SafeFormatter().format(template, **template_vars)

    def _format_generic_section(self, title: str, data: Dict[str, Any]) -> str:
        """Formats a piece of context data into a readable markdown section."""
        lines = [f"### [{title}]"]
        for k, v in data.items():
            if k in ["memory", "news", "social"]:
                 continue # Handled as blocks
            if isinstance(v, (str, int, float, bool)):
                 lines.append(f"- {k.replace('_', ' ').capitalize()}: {v}")
        
        # Add list-based content at the end
        if "news" in data:
            lines.extend([f"- {item}" for item in data["news"]])
        if "social" in data:
             lines.extend([f"- {item}" for item in data["social"]])
        if "memory" in data and isinstance(data["memory"], list):
            lines.append("Recent History:")
            lines.extend([f"  - {m}" for m in data["memory"]])
            
        return "\n".join(lines)


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
    yaml_path: str = None,
    memory_engine: Optional[MemoryEngine] = None
) -> BaseAgentContextBuilder:
    """
    Create a context builder for a set of agents.
    
    Args:
        agents: Dict of agent_name -> BaseAgent instances
        environment: Shared environment state
        custom_templates: Optional custom prompt templates per agent_type
        load_yaml: If True, load templates from YAML file
        yaml_path: Optional path to YAML file (default: broker/prompt_templates.yaml)
        memory_engine: Engine for retrieving agent memory
    
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
        prompt_templates=templates,
        memory_engine=memory_engine
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

