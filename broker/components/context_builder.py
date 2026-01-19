"""
Generic Context Builder - Builds bounded context for any agent type.

Works with BaseAgent to provide 0-1 normalized state in prompts.
Supports multi-agent scenarios where agents observe each other.
"""
from typing import Dict, List, Any, Optional, Callable
from abc import ABC, abstractmethod
import string
from broker.utils.logging import setup_logger

logger = setup_logger(__name__)

from .memory_engine import MemoryEngine
from .interaction_hub import InteractionHub

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

    def format_field(self, value, format_spec):
        try:
            return super().format_field(value, format_spec)
        except (ValueError, TypeError):
            # Fallback to string representation if formatting fails (e.g. string vs numeric code)
            return str(value)


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


class ContextProvider:
    """Interface for context providers."""
    def provide(self, agent_id: str, agents: Dict[str, Any], context: Dict[str, Any], **kwargs):
        pass

class SystemPromptProvider(ContextProvider):
    """Provides mandatory system-level formatting instructions."""
    def provide(self, agent_id, agents, context, **kwargs):
        context["system_prompt"] = (
            "### [STRICT FORMATTING RULE]\n"
            "You MUST wrap your final decision JSON in <decision> and </decision> tags.\n"
            "Example: <decision>{{\"strategy\": \"...\", \"confidence\": 0.8, \"decision\": 1}}</decision>\n"
            "DO NOT include any commentary outside these tags."
        )

class AttributeProvider(ContextProvider):
    """Provides internal state from agent attributes."""
    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent: return
        
        state = context.setdefault("state", {})
        # Reflective discovery of public attributes
        for k, v in agent.__dict__.items():
            if not k.startswith('_') and isinstance(v, (str, int, float, bool)) and k not in state:
                state[k] = v
        
        if hasattr(agent, 'get_observable_state'):
            state.update(agent.get_observable_state())
        if hasattr(agent, 'fixed_attributes'):
             state.update({k: v for k, v in agent.fixed_attributes.items() 
                           if isinstance(v, (str, int, float, bool))})
        if hasattr(agent, 'dynamic_state'):
             state.update({k: v for k, v in agent.dynamic_state.items() 
                           if isinstance(v, (str, int, float, bool))})
        if hasattr(agent, 'custom_attributes'):
            state.update(agent.custom_attributes)
        
        # Inject capabilities
        if hasattr(agent, 'get_available_skills'):
            context["available_skills"] = agent.get_available_skills()


class PrioritySchemaProvider(ContextProvider):
    """
    Provider that applies domain-specific priority weights to context attributes.
    
    Loads weights from YAML config to maintain domain-agnosticism.
    Example config:
        priority_schema:
          hydrology: {damage: 1.0, elevated: 0.9, flood_threshold: 0.8}
          finance: {liquidity_ratio: 1.0, yield: 0.9}
    """
    def __init__(self, schema: Dict[str, float] = None):
        self.schema = schema or {}
    
    def provide(self, agent_id, agents, context, **kwargs):
        if not self.schema:
            return
        
        state = context.get("state", {})
        priority_items = []
        
        for attr, priority in sorted(self.schema.items(), key=lambda x: -x[1]):
            if attr in state:
                priority_items.append({
                    "attribute": attr,
                    "value": state[attr],
                    "priority": priority
                })
        
        context["priority_schema"] = priority_items
        context["_priority_attributes"] = list(self.schema.keys())


class EnvironmentProvider(ContextProvider):
    """Provides perception signals from the environment."""
    def __init__(self, environment: Dict[str, float]):
        self.environment = environment
        
    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent or not hasattr(agent, 'observe'): return
        
        # Perception bucket
        context["perception"] = agent.observe(self.environment, agents)

class MemoryProvider(ContextProvider):
    """Provides historical traces via MemoryEngine."""
    def __init__(self, engine: Optional[MemoryEngine]):
        self.engine = engine
        
    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent or not self.engine: return
        
        # Memory bucket
        context["memory"] = self.engine.retrieve(agent, top_k=3)

class BaseAgentContextBuilder(ContextBuilder):
    """
    Context builder that uses a pipeline of providers for true generality.
    """
    
    def __init__(
        self,
        agents: Dict[str, Any],
        environment: Dict[str, float] = None,
        prompt_templates: Dict[str, str] = None,
        memory_engine: Optional[MemoryEngine] = None,
        providers: List[ContextProvider] = None,
        extend_providers: List[ContextProvider] = None,  # New: additive providers
        semantic_thresholds: tuple = (0.3, 0.7),
        yaml_path: Optional[str] = None,
        max_prompt_tokens: int = 16384
    ):
        self.agents = agents
        self.prompt_templates = prompt_templates or {}
        self.semantic_thresholds = semantic_thresholds
        self.yaml_path = yaml_path
        self.max_prompt_tokens = max_prompt_tokens

        
        # Standard: Enforce 0-1 normalization for universal parameters
        if any(t < 0.0 or t > 1.0 for t in semantic_thresholds):
            logger.warning(f"[Universality:Warning] semantic_thresholds {semantic_thresholds} are outside 0-1 range. Standardizing to [0,1] is recommended.")
        
        # Initialize provider pipeline
        # Option 1: providers=None → use defaults + extend_providers
        # Option 2: providers=List → replace defaults entirely (legacy behavior)
        if providers is not None:
            self.providers = providers
        else:
            self.providers = [
                SystemPromptProvider(),
                AttributeProvider(),
                EnvironmentProvider(environment or {}),
                MemoryProvider(memory_engine)
            ]
        
        # Add any extension providers (Phase 25 PR5)
        if extend_providers:
            self.providers.extend(extend_providers)
    
    def build(
        self, 
        agent_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Run the provider pipeline to build context."""
        agent = self.agents.get(agent_id)
        if not agent:
            return {"agent_id": agent_id, "error": "Agent not found"}
        
        context = {
            "agent_id": agent_id,
            "agent_name": getattr(agent, 'name', agent_id),
            "agent_type": getattr(agent, 'agent_type', 'default'),
            "available_skills": [],
        }
        
        # Trigger all providers in sequence
        for provider in self.providers:
            provider.provide(agent_id, self.agents, context, **kwargs)
            
        return context
    
    def _get_neighbor_summary(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get summary of neighbor agents' observable state."""
        summaries = []
        for name, agent in self.agents.items():
            if name != agent_id:
                summaries.append({
                    "agent_name": name,
                    "agent_type": agent.agent_type,
                    "state_summary": {
                        k: (round(v, 2) if isinstance(v, (int, float)) else v) 
                        for k, v in list(agent.get_all_state().items())[:3]
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
        
        # Phase 28: Support RAG-based skill descriptions
        retrieved_defs = context.get("retrieved_skill_definitions")
        if retrieved_defs:
            skills_str = "\n".join([f"- {s.skill_id}: {s.description}" for s in retrieved_defs])
        else:
            # Fallback to simple comma-separated list
            skills_str = ", ".join(context.get("available_skills", []))
        memory_val = context.get("memory", [])
        if isinstance(memory_val, dict) and "episodic" in memory_val:
            # Phase 28: Hierarchical Memory Formatting
            core = memory_val.get("core", {})
            episodic = memory_val.get("episodic", [])
            semantic = memory_val.get("semantic", [])
            
            lines = []
            if core:
                core_str = " ".join([f"{k}={v}" for k, v in core.items()])
                lines.append(f"CORE: {core_str}")
            if semantic:
                lines.append("HISTORIC:")
                lines.extend([f"  - {m}" for m in semantic])
            if episodic:
                lines.append("RECENT:")
                lines.extend([f"  - {m}" for m in episodic])
            
            memory_str = "\n".join(lines) if lines else "No memory available"
        elif isinstance(memory_val, list):
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
        # e.g. {income_level}, {risk_tolerance}, etc.
        for k, v in state.items():
            if isinstance(v, (str, int, float, bool)):
                template_vars[k] = v
        
        # Add perception variables
        perception = context.get("perception", {})
        for k, v in perception.items():
             if isinstance(v, (str, int, float, bool)):
                template_vars[k] = v
            
        # Add extra context keys (top-level attributes like 'budget_remaining')
        template_vars.update({k: v for k, v in context.items() 
                            if k not in template_vars and isinstance(v, (str, int, float, bool))})
        
        # Inject shared rating_scale from config (if available)
        from broker.utils.agent_config import load_agent_config
        try:
            # Use yaml_path if available (stored in subclasses usually, but check self)
            yaml_path = getattr(self, 'yaml_path', None)
            agent_cfg = load_agent_config(yaml_path)
            rating_scale = agent_cfg.get_shared("rating_scale", "")
            if rating_scale:
                template_vars["rating_scale"] = rating_scale
        except:
            pass  # Fallback silently if config loading fails

        
        # Format the prompt
        formatted = SafeFormatter().format(template, **template_vars)
        
        # Context size monitoring (Phase 25 PR4)
        # Rough token estimate: ~4 chars per token for English text
        token_estimate = len(formatted) // 4
        if token_estimate > self.max_prompt_tokens:
            logger.warning(
                f"[Context:Warning] Prompt exceeds limit for {context.get('agent_id', 'unknown')}: "
                f"~{token_estimate} tokens (limit {self.max_prompt_tokens})"
            )
            raise RuntimeError(
                f"Prompt token estimate {token_estimate} exceeds limit {self.max_prompt_tokens}"
            )
        
        return formatted
    
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
        """
        Convert 0-1 value to semantic label (5 levels).
        
        Thresholds:
            VL (Very Low): v < 0.2
            L  (Low):      0.2 <= v < 0.4
            M  (Medium):   0.4 <= v < 0.6
            H  (High):     0.6 <= v < 0.8
            VH (Very High): v >= 0.8
        """
        if v < 0.2: return "VL"
        if v < 0.4: return "L"
        if v < 0.6: return "M"
        if v < 0.8: return "H"
        return "VH"
    
    def _format_perception(self, perception: Dict[str, float], compact: bool = True) -> str:
        """Format perception signals."""
        if compact:
            return " ".join(f"{k}={v:.2f}" for k, v in perception.items() if isinstance(v, (int, float))) or "-"
        return "\n".join(f"- {k}: {v:.2f}" for k, v in perception.items() if isinstance(v, (int, float))) or "No signals"
    
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

class SocialProvider(ContextProvider):
    """Provides T1 Social/Spatial context from InteractionHub."""
    def __init__(self, hub: 'InteractionHub'):
        self.hub = hub
        
    def provide(self, agent_id, agents, context, **kwargs):
        # Adds 'local' bucket with spatial/social sub-keys
        spatial = self.hub.get_spatial_context(agent_id, agents)
        social = self.hub.get_social_context(agent_id, agents)
        
        local = context.setdefault("local", {})
        local["spatial"] = spatial
        local["social"] = social

class InstitutionalProvider(ContextProvider):
    """Provides T2/T3 Regional/Institutional context from environment."""
    def __init__(self, environment: 'TieredEnvironment'):
        self.environment = environment
        
    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent: return
        
        # Pull global, local-env, and institutional-env based on agent location/type
        global_news = list(self.environment.global_state.values())
        context["global"] = global_news
        
        local = context.setdefault("local", {})
        tract_id = getattr(agent, 'tract_id', None) or getattr(agent, 'location', None)
        if tract_id:
            local["environment"] = self.environment.local_states.get(tract_id, {})
            
        inst_id = getattr(agent, 'institution_id', None) or getattr(agent, 'agent_type', None)
        if inst_id:
            context["institutional"] = self.environment.institutions.get(inst_id, {})

class DynamicStateProvider(ContextProvider):
    """
    Universally injects dynamic environment state into context.
    Uses a whitelist to prevent context pollution.
    """
    def __init__(self, whitelist: List[str] = None):
        self.whitelist = whitelist or []

    def provide(self, agent_id, agents, context, **kwargs):
        """Inject whitelisted env_context variables into top-level context."""
        env_context = kwargs.get("env_context", {})
        if not env_context: return

        # Inject only whitelisted keys directly into context 
        # (so they are picked up by flattened template_vars)
        for key in self.whitelist:
            if key in env_context:
                context[key] = env_context[key]

class NarrativeProvider(ContextProvider):
    """
    Consolidates raw attributes into qualitative narrative strings based on config mapping.
    Prevents prompt bloat by summarizing multiple fields.
    """
    def provide(self, agent_id, agents, context, **kwargs):
        agent = agents.get(agent_id)
        if not agent: return
        
        fixed = getattr(agent, 'fixed_attributes', {})
        if not fixed: return

        # Generic approach: If a mapping is provided in agent_types.yaml, use it.
        # Otherwise, look for common 'persona' or 'history' patterns.
        
        # 1. Narrative Persona (Generic)
        # Build persona from all non-internal fixed attributes
        persona_parts = []
        # Exclude internal/computed fields
        exclude_keys = {"id", "agent_type", "config", "skills", "custom_attributes"}
        for k, v in fixed.items():
            if k not in exclude_keys and isinstance(v, (str, int, float)):
                label = k.replace('_', ' ').capitalize()
                persona_parts.append(f"{label}: {v}")
        
        if persona_parts:
            context["narrative_persona"] = " | ".join(persona_parts)
        
        # 2. History Summary (Generic)
        # Look for any dictionary named '*_history'
        history_key = next((k for k in fixed.keys() if "history" in k.lower()), None)
        if history_key:
            hist = fixed.get(history_key, {})
            if isinstance(hist, dict):
                hist_parts = [f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in hist.items()]
                context["history_summary"] = "; ".join(hist_parts)
            else:
                context["history_summary"] = str(hist)

class TieredContextBuilder(BaseAgentContextBuilder):
    """
    Modular Tiered Context Builder using the Provider pipeline.
    """
    def __init__(
        self,
        agents: Dict[str, Any],
        hub: InteractionHub,
        skill_registry: Optional[Any] = None,
        global_news: List[str] = None,
        prompt_templates: Dict[str, str] = None,
        memory_engine: Optional[MemoryEngine] = None,
        trust_verbalizer: Optional[Callable[[float, str], str]] = None,
        dynamic_whitelist: List[str] = None,
        yaml_path: Optional[str] = None,
        max_prompt_tokens: int = 16384,
        enable_financial_constraints: bool = False # New parameter
    ):
        providers = [
            DynamicStateProvider(dynamic_whitelist),
            AttributeProvider(),
            MemoryProvider(memory_engine),
            SocialProvider(hub),
            NarrativeProvider()
        ]
        
        if hasattr(hub, 'environment') and hub.environment:
            providers.append(InstitutionalProvider(hub.environment))
            
        super().__init__(
            agents=agents, 
            prompt_templates=prompt_templates, 
            providers=providers,
            yaml_path=yaml_path,
            max_prompt_tokens=max_prompt_tokens
        )

        self.hub = hub
        self.skill_registry = skill_registry
        self.global_news = global_news or []
        self.trust_verbalizer = trust_verbalizer
        self.yaml_path = yaml_path
        self.enable_financial_constraints = enable_financial_constraints # Store the flag


    def build(self, agent_id: str, **kwargs) -> Dict[str, Any]:
        """Build context using the InteractionHub's tiered logic and any additional providers."""
        agent = self.agents.get(agent_id)
        context = self.hub.build_tiered_context(agent_id, self.agents, self.global_news)
        
        # Ensure critical metadata is at top level for providers/formatter
        context["agent_id"] = agent_id
        context["agent_type"] = getattr(agent, 'agent_type', 'default') if agent else 'default'
        
        # Trigger all providers in sequence (e.g. SystemPromptProvider)
        for provider in self.providers:
            provider.provide(agent_id, self.agents, context, **kwargs)
            
        return context


    def format_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format the tiered context into a grounded prompt (Generic).
        Flattens Personal, Local, and Global tiers into template variables.
        """
        # 1. Prepare template variables
        template_vars = {}
        
        # Robust Agent Type Extraction (Priority: Context top-level -> Personal)
        agent_type = context.get('agent_type') or context.get('personal', {}).get('agent_type', 'default')
        
        # Flatten System (Strategic)
        template_vars["system_prompt"] = context.get('system_prompt', "")


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
        
        # Flatten Institutional (T3)
        inst = context.get('institutional', {})
        for k, v in inst.items():
            template_vars[k] = v
            template_vars[f"inst_{k}"] = v
            
        # Add extra context keys (top-level attributes like dynamic variables)
        template_vars.update({k: v for k, v in context.items() 
                            if k not in template_vars and isinstance(v, (str, int, float, bool))})
        
        # Add special sections for modular UI templates
        template_vars["personal_section"] = self._format_generic_section("MY STATUS & HISTORY", p)
        template_vars["local_section"] = self._format_generic_section("LOCAL NEIGHBORHOOD", l)
        template_vars["global_section"] = self._format_generic_section("WORLD EVENTS", {"news": g})
        template_vars["institutional_section"] = self._format_generic_section("INSTITUTIONAL & POLICY", inst)

        # Phase 29: Pillar 3 - Priority Schema Rendering
        # Explicitly render Priority Schema items as a "CRITICAL FACTORS" block
        priority_items = context.get("priority_schema", [])
        if priority_items:
            priority_lines = ["### [CRITICAL FACTORS (Focus Here)]"]
            for item in priority_items:
                attr = item.get("attribute", "unknown").upper()
                val = item.get("value", "N/A")
                prio = item.get("priority", 0.0)
                priority_lines.append(f"- {attr}: {val} (Priority: {prio:.1f})")
            template_vars["priority_section"] = "\n".join(priority_lines)
        else:
            template_vars["priority_section"] = ""

        # 2. Options Section (Universal)
        agent_id = p.get('id')
        agent = self.agents.get(agent_id)
        
        # Prefer pre-formatted options if provided (e.g. from custom build() override)
        options_text = p.get('options_text', "")
        valid_choices_text = p.get('valid_choices_text', "")
        
        if not options_text and agent:
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
        
        # 3. Response Format & Rating Scale (from YAML config)
        try:
            from broker.components.response_format import ResponseFormatBuilder
            from broker.utils.agent_config import load_agent_config
            yaml_path = getattr(self, 'yaml_path', None)
            cfg = load_agent_config(yaml_path)
            
            # Inject rating_scale (Shared)
            rating_scale = cfg.get_shared("rating_scale", "")
            if rating_scale:
                template_vars["rating_scale"] = rating_scale
                
            # Build Response Format
            # Use canonical agent_type for config lookup
            agent_config = cfg.get(agent_type)
            if agent_config:
                shared_config = {"response_format": cfg.get_shared("response_format", {})}
                rfb = ResponseFormatBuilder(agent_config, shared_config)
                response_format_block = rfb.build(valid_choices_text=valid_choices_text)
                if response_format_block:
                    template_vars["response_format"] = response_format_block
            else:
                logger.warning(f"[Context:Warning] No config found for agent_type '{agent_type}' in {yaml_path}")
        except Exception as e:
            logger.error(f"[Context:Error] Failed to inject response_format/rating_scale: {e}")
            pass



        
        # 4. Use template (Generic lookup)
        agent_type = p.get('agent_type', 'default')
        default_template = "{system_prompt}\n\n{priority_section}\n\n{personal_section}\n\n{local_section}\n\n{institutional_section}\n\n{global_section}\n\n### [AVAILABLE OPTIONS]\n{options_text}"
        template = self.prompt_templates.get(agent_type, default_template)
        
        # If the template doesn't include {system_prompt}, prepend it
        if "{system_prompt}" not in template:
            template = "{system_prompt}\n\n{priority_section}\n\n" + template
            
        formatted = SafeFormatter().format(template, **template_vars)
        token_estimate = len(formatted) // 4
        if token_estimate > self.max_prompt_tokens:
            logger.warning(
                f"[Context:Warning] Prompt exceeds limit for {context.get('agent_id', 'unknown')}: "
                f"~{token_estimate} tokens (limit {self.max_prompt_tokens})"
            )
            raise RuntimeError(
                f"Prompt token estimate {token_estimate} exceeds limit {self.max_prompt_tokens}"
            )
        return formatted


    def _format_generic_section(self, title: str, data: Dict[str, Any]) -> str:
        """Formats a piece of context data into a readable markdown section."""
        lines = [f"### [{title}]"]
        
        def format_dict(d, prefix="- "):
            for k, v in d.items():
                if k in ["memory", "news", "social"]:
                     continue # Handled as blocks
                if isinstance(v, (str, int, float, bool)):
                     label = k.replace('_', ' ').capitalize()
                     lines.append(f"{prefix}{label}: {v}")
                elif isinstance(v, dict):
                     # Recursively format one level for groups like 'environment' or 'spatial'
                     format_dict(v, prefix + "  ")

        format_dict(data)
        
        # Add list-based content (social gossip, global news)
        if "news" in data:
            lines.extend([f"- {item}" for item in data["news"]])
        if "social" in data:
             lines.extend([f"- {item}" for item in data["social"]])
        if "memory" in data:
            memory_val = data["memory"]
            if isinstance(memory_val, dict) and "episodic" in memory_val:
                # Hierarchical Memory Formatting
                core = memory_val.get("core", {})
                episodic = memory_val.get("episodic", [])
                semantic = memory_val.get("semantic", [])
                
                if core:
                    core_val = " ".join([f"{k}={v}" for k, v in core.items()])
                    lines.append(f"  - CORE: {core_val}")
                if semantic:
                    lines.append("  - HISTORIC:")
                    lines.extend([f"    - {m}" for m in semantic])
                if episodic:
                    lines.append("  - RECENT:")
                    lines.extend([f"    - {m}" for m in episodic])
            elif isinstance(memory_val, list):
                lines.append("Recent History:")
                lines.extend([f"  - {m}" for m in memory_val])
            
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
    memory_engine: Optional[MemoryEngine] = None,
    semantic_thresholds: tuple = (0.3, 0.7),
    hub: Optional['InteractionHub'] = None,
    max_prompt_tokens: int = 16384
) -> 'BaseAgentContextBuilder':
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
    
    if hub:
        return TieredContextBuilder(
            agents=agents,
            hub=hub,
            prompt_templates=templates,
            memory_engine=memory_engine,
            yaml_path=yaml_path,
            max_prompt_tokens=max_prompt_tokens
        )

    
    return BaseAgentContextBuilder(
        agents=agents,
        environment=environment,
        prompt_templates=templates,
        memory_engine=memory_engine,
        semantic_thresholds=semantic_thresholds,
        max_prompt_tokens=max_prompt_tokens
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
            if isinstance(value, dict):
                if 'prompt_template' in value:
                    templates[key] = value['prompt_template']
                elif 'template' in value:
                    templates[key] = value['template']
            elif isinstance(value, str):
                templates[key] = value
        
        return templates
    except FileNotFoundError:
        return {}

