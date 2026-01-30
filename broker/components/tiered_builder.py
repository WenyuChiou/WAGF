"""Tiered context builder implementations.

Phase 8: Added SDK observer support for domain-agnostic observation.
"""
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING

from broker.utils.logging import setup_logger
from broker.utils.agent_config import load_agent_config

from .context_builder import ContextBuilder, SafeFormatter
from .context_providers import (
    ContextProvider,
    SystemPromptProvider,
    AttributeProvider,
    PrioritySchemaProvider,
    EnvironmentProvider,
    EnvironmentObservationProvider,  # Phase 8: SDK observer
    MemoryProvider,
    SocialProvider,
    InstitutionalProvider,
    DynamicStateProvider,
    NarrativeProvider,
)
from .memory_engine import MemoryEngine
from .interaction_hub import InteractionHub
from .neighbor_utils import get_neighbor_summary

# SDK observer imports (optional, for Phase 8)
if TYPE_CHECKING:
    from cognitive_governance.v1_prototype.social import SocialObserver
    from cognitive_governance.v1_prototype.observation import EnvironmentObserver

logger = setup_logger(__name__)


class BaseAgentContextBuilder(ContextBuilder):
    """Context builder that uses a pipeline of providers for generality."""

    def __init__(
        self,
        agents: Dict[str, Any],
        environment: Dict[str, float] = None,
        prompt_templates: Dict[str, str] = None,
        memory_engine: Optional[MemoryEngine] = None,
        providers: List[ContextProvider] = None,
        extend_providers: List[ContextProvider] = None,
        semantic_thresholds: tuple = (0.3, 0.7),
        yaml_path: Optional[str] = None,
        max_prompt_tokens: int = 16384,
    ):
        self.agents = agents
        self.prompt_templates = prompt_templates or {}
        self.semantic_thresholds = semantic_thresholds
        self.yaml_path = yaml_path
        self.max_prompt_tokens = max_prompt_tokens

        if any(t < 0.0 or t > 1.0 for t in semantic_thresholds):
            logger.warning(
                f"[Universality:Warning] semantic_thresholds {semantic_thresholds} are outside 0-1 range."
            )

        if providers is not None:
            self.providers = providers
        else:
            self.providers = [
                SystemPromptProvider(),
                AttributeProvider(),
                EnvironmentProvider(environment or {}),
                MemoryProvider(memory_engine),
            ]

        if extend_providers:
            self.providers.extend(extend_providers)

    def build(self, agent_id: str, **kwargs) -> Dict[str, Any]:
        agent = self.agents.get(agent_id)
        if not agent:
            return {"agent_id": agent_id, "error": "Agent not found"}

        context = {
            "agent_id": agent_id,
            "agent_name": getattr(agent, "name", agent_id),
            "agent_type": getattr(agent, "agent_type", "default"),
            "available_skills": [],
        }

        for provider in self.providers:
            provider.provide(agent_id, self.agents, context, **kwargs)

        return context

    def _get_neighbor_summary(self, agent_id: str) -> List[Dict[str, Any]]:
        return get_neighbor_summary(self.agents, agent_id)

    def format_prompt(self, context: Dict[str, Any]) -> str:
        agent_type = context.get("agent_type", "default")
        template = self.prompt_templates.get(agent_type, DEFAULT_PROMPT_TEMPLATE)

        state = context.get("state", {})
        state_str = self._format_state(state)
        perception_str = self._format_perception(context.get("perception", {}))
        objectives_str = self._format_objectives(context.get("objectives", {}))

        retrieved_defs = context.get("retrieved_skill_definitions")
        if retrieved_defs:
            skills_str = "\n".join([f"- {s.skill_id}: {s.description}" for s in retrieved_defs])
        else:
            skills_str = ", ".join(context.get("available_skills", []))

        memory_val = context.get("memory", [])
        if isinstance(memory_val, dict) and "episodic" in memory_val:
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
            memory_str = "\n".join(f"- {m}" for m in memory_val) if memory_val else "No memory available"
        else:
            memory_str = str(memory_val)

        template_vars = {
            "agent_name": context.get("agent_name", "Agent"),
            "agent_type": agent_type,
            "state": state_str,
            "perception": perception_str,
            "objectives": objectives_str,
            "skills": skills_str,
            "memory": memory_str,
        }

        for k, v in state.items():
            if isinstance(v, (str, int, float, bool)):
                template_vars[k] = v

        perception = context.get("perception", {})
        for k, v in perception.items():
            if isinstance(v, (str, int, float, bool)):
                template_vars[k] = v

        template_vars.update(
            {k: v for k, v in context.items() if k not in template_vars and isinstance(v, (str, int, float, bool))}
        )

        try:
            yaml_path = getattr(self, "yaml_path", None)
            agent_cfg = load_agent_config(yaml_path)
            rating_scale = agent_cfg.get_shared("rating_scale", "")
            if rating_scale:
                template_vars["rating_scale"] = rating_scale
        except Exception:
            pass

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

    def _format_state(self, state: Dict[str, float], compact: bool = True) -> str:
        if compact:
            return " ".join(
                f"{k}={v:.2f}({self._semantic(v)})"
                for k, v in state.items()
                if isinstance(v, (int, float))
            )
        return "\n".join(f"- {k}: {v:.2f}" for k, v in state.items()) or "No state"

    def _semantic(self, v: float) -> str:
        if v < 0.2:
            return "VL"
        if v < 0.4:
            return "L"
        if v < 0.6:
            return "M"
        if v < 0.8:
            return "H"
        return "VH"

    def _format_perception(self, perception: Dict[str, float], compact: bool = True) -> str:
        if compact:
            return " ".join(
                f"{k}={v:.2f}" for k, v in perception.items() if isinstance(v, (int, float))
            ) or "-"
        return "\n".join(
            f"- {k}: {v:.2f}" for k, v in perception.items() if isinstance(v, (int, float))
        ) or "No signals"

    def _format_objectives(self, objectives: Dict[str, Dict], compact: bool = True) -> str:
        if compact:
            return " ".join(
                f"{n}={info.get('current', 0):.2f}{'IN' if info.get('in_range') else 'OUT'}"
                for n, info in objectives.items()
            ) or "-"

        lines = []
        for name, info in objectives.items():
            status = "IN" if info.get("in_range") else "OUT"
            current = info.get("current", 0)
            target = info.get("target", (0, 1))
            lines.append(f"- {name}: {current:.2f} ({target[0]:.2f}-{target[1]:.2f}) {status}")
        return "\n".join(lines) if lines else "No objectives"


class TieredContextBuilder(BaseAgentContextBuilder):
    """Modular Tiered Context Builder using the Provider pipeline.

    Phase 8: Supports SDK observers for domain-agnostic observation.
    Pass `social_observer` and/or `environment_observer` for SDK integration.
    """

    def __init__(
        self,
        agents: Dict[str, Any],
        hub: InteractionHub,
        skill_registry: Optional[Any] = None,
        global_news: List[str] = None,
        media_hub: Optional[Any] = None,
        prompt_templates: Dict[str, str] = None,
        memory_engine: Optional[MemoryEngine] = None,
        trust_verbalizer: Optional[Callable[[float, str], str]] = None,
        dynamic_whitelist: List[str] = None,
        yaml_path: Optional[str] = None,
        max_prompt_tokens: int = 16384,
        enable_financial_constraints: bool = False,
        # Phase 8: SDK observer support
        social_observer: Optional["SocialObserver"] = None,
        environment_observer: Optional["EnvironmentObserver"] = None,
    ):
        # Phase 8: Store observers for potential use
        self.social_observer = social_observer
        self.environment_observer = environment_observer

        providers = [
            DynamicStateProvider(dynamic_whitelist),
            AttributeProvider(),
            MemoryProvider(memory_engine),
            # Phase 8: Pass SDK observer to SocialProvider if available
            SocialProvider(hub, observer=social_observer),
            NarrativeProvider(),
        ]

        if getattr(hub, "environment", None):
            providers.append(InstitutionalProvider(hub.environment))

        # Phase 8: Add EnvironmentObservationProvider if SDK observer provided
        if environment_observer and getattr(hub, "environment", None):
            providers.append(
                EnvironmentObservationProvider(environment_observer, hub.environment)
            )

        super().__init__(
            agents=agents,
            prompt_templates=prompt_templates,
            providers=providers,
            yaml_path=yaml_path,
            max_prompt_tokens=max_prompt_tokens,
        )

        self.hub = hub
        self.skill_registry = skill_registry
        self.global_news = global_news or []
        self.media_hub = media_hub
        self.trust_verbalizer = trust_verbalizer
        self.yaml_path = yaml_path
        self.enable_financial_constraints = enable_financial_constraints

    def build(self, agent_id: str, **kwargs) -> Dict[str, Any]:
        agent = self.agents.get(agent_id)
        context = self.hub.build_tiered_context(agent_id, self.agents, self.global_news)

        context["agent_id"] = agent_id
        context["agent_type"] = getattr(agent, "agent_type", "default") if agent else "default"

        env_context = kwargs.get("env_context", {})
        if (not env_context) and getattr(self.hub, "environment", None):
            env_context = self.hub.environment.global_state

        env_context = env_context or kwargs.get("env_context", {})
        contextual_boosters_for_memory = {}

        if env_context.get("crisis_event") or env_context.get("crisis_boosters"):
            crisis_boosters = env_context.get("crisis_boosters", {})
            for tag, weight in crisis_boosters.items():
                contextual_boosters_for_memory[tag] = weight

        kwargs["contextual_boosters"] = contextual_boosters_for_memory

        for provider in self.providers:
            provider.provide(agent_id, self.agents, context, **kwargs)

        if self.media_hub:
            year = env_context.get("year", 1)
            media_context = self.media_hub.get_media_context(agent_id, year)
            if media_context:
                broadcast = media_context.get("broadcast", media_context.get("news", []))
                peer_messages = media_context.get("peer_messages", media_context.get("social_media", []))

                if broadcast:
                    context["global"] = broadcast
                if peer_messages:
                    local = context.get("local") or {}
                    local_social = local.get("social", [])
                    local["social"] = local_social + peer_messages
                    context["local"] = local

        return context

    def format_prompt(self, context: Dict[str, Any]) -> str:
        template_vars: Dict[str, Any] = {}
        agent_type = context.get("agent_type") or context.get("personal", {}).get("agent_type", "default")

        template_vars["system_prompt"] = context.get("system_prompt", "")

        p = context.get("personal", {})
        for k, v in p.items():
            if isinstance(v, (str, int, float, bool)):
                template_vars[k] = v
                template_vars[f"p_{k}"] = v

        if isinstance(p.get("status"), dict):
            for k, v in p["status"].items():
                if k not in template_vars:
                    template_vars[k] = v

        l = context.get("local", {})
        spatial = l.get("spatial", {})
        for k, v in spatial.items():
            template_vars[k] = v
            template_vars[f"spatial_{k}"] = v

        social = l.get("social", [])
        template_vars["social_gossip"] = "\n".join([f"- {s}" for s in social]) if social else ""

        g = context.get("global", [])
        template_vars["global_news"] = "\n".join([f"- {news}" for news in g]) if g else ""

        inst = context.get("institutional", {})
        for k, v in inst.items():
            template_vars[k] = v
            template_vars[f"inst_{k}"] = v

        template_vars.update(
            {k: v for k, v in context.items() if k not in template_vars and isinstance(v, (str, int, float, bool))}
        )

        template_vars["personal_section"] = self._format_generic_section("MY STATUS & HISTORY", p)
        template_vars["local_section"] = self._format_generic_section("LOCAL NEIGHBORHOOD", l)
        template_vars["global_section"] = self._format_generic_section("WORLD EVENTS", {"news": g})
        template_vars["institutional_section"] = self._format_generic_section("INSTITUTIONAL & POLICY", inst)

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

        agent_id = p.get("id")
        agent = self.agents.get(agent_id)

        options_text = p.get("options_text", "")
        valid_choices_text = p.get("valid_choices_text", "")

        if not options_text and agent:
            available_skills = list(agent.get_available_skills())

            # Anti-positional-bias: shuffle skill ordering (Task-060B)
            shuffle_enabled = context.get("_shuffle_skills", False)
            if shuffle_enabled and available_skills:
                import random as _rng
                shuffle_seed = context.get("_shuffle_seed")
                if shuffle_seed is not None:
                    _rng.Random(shuffle_seed).shuffle(available_skills)
                else:
                    _rng.shuffle(available_skills)

            formatted_options = []
            dynamic_skill_map = {}

            for i, skill_item in enumerate(available_skills, 1):
                skill_id = skill_item.split(": ", 1)[0] if ": " in skill_item else skill_item
                skill_def = self.skill_registry.get(skill_id) if self.skill_registry else None
                desc = skill_def.description if skill_def else skill_item
                formatted_options.append(f"{i}. {desc}")
                dynamic_skill_map[str(i)] = skill_id

            options_text = "\n".join(formatted_options)

            # Inject dynamic_skill_map for parser (Priority 1 in get_skill_map)
            personal = context.setdefault("personal", {})
            personal["dynamic_skill_map"] = dynamic_skill_map

            indices = [str(i + 1) for i in range(len(available_skills))]
            if len(indices) > 1:
                valid_choices_text = ", ".join(indices[:-1]) + ", or " + indices[-1]
            elif indices:
                valid_choices_text = indices[0]

        template_vars["options_text"] = options_text
        template_vars["valid_choices_text"] = valid_choices_text
        template_vars["skills_text"] = options_text
        # Task-060A: Forward insurance cost disclosure from provider
        template_vars["insurance_cost_text"] = p.get(
            "insurance_cost_text", context.get("personal", {}).get("insurance_cost_text", "")
        )

        try:
            from broker.components.response_format import ResponseFormatBuilder

            yaml_path = getattr(self, "yaml_path", None)
            cfg = load_agent_config(yaml_path)

            rating_scale = cfg.get_shared("rating_scale", "")
            if rating_scale:
                template_vars["rating_scale"] = rating_scale

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

        # KV Cache Optimization: Static sections (System, Institutional, Global) placed first
        # to maximize prefix sharing across agents within the same simulation year.
        default_template = (
            "{system_prompt}\n\n{institutional_section}\n\n{global_section}\n\n"
            "{priority_section}\n\n{personal_section}\n\n{local_section}\n\n### [AVAILABLE OPTIONS]\n{options_text}"
        )
        template = self.prompt_templates.get(agent_type, default_template)
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
        lines = [f"### [{title}]"]

        def format_dict(d, prefix="- "):
            for k, v in d.items():
                if k in ["memory", "news", "social"]:
                    continue
                if isinstance(v, (str, int, float, bool)):
                    label = k.replace("_", " ").capitalize()
                    lines.append(f"{prefix}{label}: {v}")
                elif isinstance(v, dict):
                    format_dict(v, prefix + "  ")

        format_dict(data)

        if "news" in data:
            lines.extend([f"- {item}" for item in data["news"]])
        if "social" in data:
            lines.extend([f"- {item}" for item in data["social"]])
        if "memory" in data:
            memory_val = data["memory"]
            if isinstance(memory_val, dict) and "episodic" in memory_val:
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


DEFAULT_PROMPT_TEMPLATE = """[{agent_type}:{agent_name}]

STATE:{state}
OBS:{perception}
MEM:{memory}
OBJ:{objectives}
ACT:{skills}

OUTPUT:
INTERPRET:[1-line summary of your situation]
DECIDE:[action] ADJ:[0-0.15] REASON:[1-line]"""


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


def create_context_builder(
    agents: Dict[str, Any],
    environment: Dict[str, float] = None,
    custom_templates: Dict[str, str] = None,
    load_yaml: bool = True,
    yaml_path: str = None,
    memory_engine: Optional[MemoryEngine] = None,
    semantic_thresholds: tuple = (0.3, 0.7),
    hub: Optional["InteractionHub"] = None,
    max_prompt_tokens: int = 16384,
) -> "BaseAgentContextBuilder":
    templates = {}

    if load_yaml:
        templates = load_prompt_templates(yaml_path)

    if custom_templates:
        templates.update(custom_templates)

    if hub:
        return TieredContextBuilder(
            agents=agents,
            hub=hub,
            prompt_templates=templates,
            memory_engine=memory_engine,
            yaml_path=yaml_path,
            max_prompt_tokens=max_prompt_tokens,
        )

    return BaseAgentContextBuilder(
        agents=agents,
        environment=environment,
        prompt_templates=templates,
        memory_engine=memory_engine,
        semantic_thresholds=semantic_thresholds,
        max_prompt_tokens=max_prompt_tokens,
    )


def load_prompt_templates(yaml_path: str = None) -> Dict[str, str]:
    import yaml
    from pathlib import Path

    if yaml_path is None:
        yaml_path = Path(__file__).parent / "prompt_templates.yaml"

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        templates = {}
        for key, value in data.items():
            if isinstance(value, dict):
                if "prompt_template" in value:
                    templates[key] = value["prompt_template"]
                elif "template" in value:
                    templates[key] = value["template"]
            elif isinstance(value, str):
                templates[key] = value

        return templates
    except FileNotFoundError:
        return {}
