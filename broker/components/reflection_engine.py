"""
Reflection Engine - Cognitive consolidation for long-term memory resilience.

Implements "Year-End Reflection" to combat memory erosion (the Goldfish Effect).
Inspired by Park et al. (2023) Generative Agents reflection architecture.
"""
from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from broker.utils.logging import setup_logger
from broker.components.domain_adapters import DomainReflectionAdapter

logger = setup_logger(__name__)

if TYPE_CHECKING:
    from cognitive_governance.v1_prototype.reflection import (
        ReflectionTemplate,
        ReflectionMemoryIntegrator,
    )

@dataclass
class ReflectionInsight:
    """A consolidated semantic insight derived from multiple episodic memories."""
    summary: str                      # Concise high-level insight
    source_memory_count: int = 0      # How many memories contributed
    importance: float = 1.0           # Consolidated importance score (0-1)
    year_created: int = 0             # When this insight was generated
    domain_tags: List[str] = field(default_factory=list)  # e.g., ["event_type", "impact", "response"]


@dataclass
class AgentReflectionContext:
    """Agent identity context for personalized reflection prompts.

    Domain-specific fields (elevated, insured, flood_count) are kept
    for backward compatibility.  New domains should use custom_traits.
    """
    agent_id: str
    agent_type: str = "household"          # household | government | insurance
    name: str = ""                         # Display name if available
    elevated: bool = False                 # flood-domain backward compat
    insured: bool = False                  # flood-domain backward compat
    flood_count: int = 0                   # flood-domain backward compat
    years_in_sim: int = 0                  # Agent age in simulation
    mg_status: bool = False                # Marginalized group
    recent_decision: str = ""              # Last skill chosen
    custom_traits: Dict[str, Any] = field(default_factory=dict)


# DEPRECATED: Hardcoded reflection questions per agent type.
# New domains should define questions in their agent_types.yaml under
# global_config.reflection.questions, which are passed to
# generate_batch_reflection_prompt(reflection_questions=...).
REFLECTION_QUESTIONS: Dict[str, List[str]] = {
    "household": [
        "What risks feel most urgent to your family right now?",
        "Have your neighbors' choices influenced your thinking?",
        "What trade-offs have you faced between cost and safety?",
    ],
    "government": [
        "Which communities are most vulnerable right now?",
        "Are current subsidy and grant programs reaching those who need them?",
        "What policy adjustments would improve equity outcomes?",
    ],
    "insurance": [
        "Which risk segments are underpriced or overpriced?",
        "How has the claims pattern changed over time?",
        "What adjustments to premium models are needed?",
    ],
}

# Legacy flood-domain importance profiles — used by compute_dynamic_importance
# fallback when no DomainReflectionAdapter is set.  New domains should use
# FloodAdapter or IrrigationAdapter instead.
IMPORTANCE_PROFILES: Dict[str, float] = {
    "first_flood": 0.95,      # First flood experience -> very memorable
    "repeated_flood": 0.75,   # Repeated floods -> diminishing impact
    "post_action": 0.80,      # Just took a major action (elevate/relocate)
    "stable_year": 0.60,      # Nothing major happened
    "denied_action": 0.85,    # Governance denial -> memorable frustration
    "mg_agent": 0.90,         # MG agents retain reflections more (limited info)
}


class ReflectionTrigger(Enum):
    """Types of events that can trigger reflection."""
    CRISIS = "crisis"
    PERIODIC = "periodic"
    DECISION = "decision"
    INSTITUTIONAL = "institutional"


@dataclass
class ReflectionTriggerConfig:
    """Configuration for reflection triggers."""
    crisis: bool = True
    periodic_interval: int = 5
    decision_types: List[str] = field(default_factory=list)
    institutional_threshold: float = 0.05
    method: str = "hybrid"
    batch_size: int = 10
    importance_boost: float = 0.85


class ReflectionEngine:
    """
    Triggers periodic cognitive consolidation for agents.
    
    At defined intervals (e.g., end of year), prompts the LLM to synthesize
    past episodic memories into high-level "Lessons Learned". These insights
    are then stored with elevated importance scores to ensure long-term retention.
    """
    
    def __init__(
        self,
        reflection_interval: int = 1,      # Trigger reflection every N years/epochs
        max_insights_per_reflection: int = 2,  # How many insights to generate per cycle
        insight_importance_boost: float = 0.9,  # Importance score for new insights
        output_path: Optional[str] = None,       # Path to save reflection logs
        llm_client=None,
        template: Optional["ReflectionTemplate"] = None,
        integrator: Optional["ReflectionMemoryIntegrator"] = None,
        adapter: Optional[DomainReflectionAdapter] = None,
    ):
        self.reflection_interval = reflection_interval
        self.max_insights = max_insights_per_reflection
        self.importance_boost = insight_importance_boost
        self.reflection_history: Dict[str, List[ReflectionInsight]] = {}
        self.output_path = output_path
        self.llm_client = llm_client
        self.template = template
        self.integrator = integrator
        self.adapter = adapter
        
        # Initialize log file if path provided
        if self.output_path:
            p = Path(self.output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            # Write header if file doesn't exist (for CSV) or just append (for JSONL)
            # We'll use JSONL for flexibility
            if not p.exists():
                with open(p, 'w', encoding='utf-8') as f:
                    pass

    
    def should_reflect(self, agent_id: str, current_year: int) -> bool:
        """Check if it's time for an agent to perform reflection."""
        if self.reflection_interval <= 0:
            return False
        return current_year > 0 and current_year % self.reflection_interval == 0

    def should_reflect_triggered(
        self,
        agent_id: str,
        agent_type: str,
        current_year: int,
        trigger: ReflectionTrigger,
        trigger_config: Optional[ReflectionTriggerConfig] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if reflection should fire based on trigger type and agent type."""
        if trigger_config is None:
            trigger_config = ReflectionTriggerConfig()

        context = context or {}

        if trigger == ReflectionTrigger.CRISIS:
            if not trigger_config.crisis:
                return False
            return True

        if trigger == ReflectionTrigger.PERIODIC:
            interval = trigger_config.periodic_interval
            if interval <= 0:
                return False
            return current_year > 0 and current_year % interval == 0

        if trigger == ReflectionTrigger.DECISION:
            decision = context.get("decision", "")
            return decision in trigger_config.decision_types

        if trigger == ReflectionTrigger.INSTITUTIONAL:
            if agent_type not in ("government", "insurance"):
                return False
            policy_change = abs(context.get("policy_change_magnitude", 0.0))
            return policy_change > trigger_config.institutional_threshold

        return False

    @staticmethod
    def load_trigger_config(config_dict: Optional[Dict[str, Any]] = None) -> ReflectionTriggerConfig:
        """Load ReflectionTriggerConfig from a dict (typically from YAML)."""
        if not config_dict:
            return ReflectionTriggerConfig()

        triggers = config_dict.get("triggers", config_dict)
        return ReflectionTriggerConfig(
            crisis=triggers.get("crisis", True),
            periodic_interval=triggers.get("periodic_interval", 5),
            decision_types=triggers.get("decision_types", []),
            institutional_threshold=triggers.get("institutional_threshold", 0.05),
            method=config_dict.get("method", "hybrid"),
            batch_size=config_dict.get("batch_size", 10),
            importance_boost=config_dict.get("importance_boost", 0.85),
        )
    
    def generate_reflection_prompt(
        self,
        agent_id: str,
        memories: List[str],
        current_year: int
    ) -> str:
        """
        Generate a prompt asking the LLM to synthesize memories into insights.
        
        This is domain-agnostic; the memories themselves contain the domain context.
        """
        if not memories:
            return ""
        
        memories_text = "\n".join([f"- {m}" for m in memories])
        
        return f"""You are reflecting on your experiences from the past {self.reflection_interval} year(s).

**Your Recent Memories:**
{memories_text}

**Task:** Summarize the key lessons you have learned from these experiences. 
Focus on:
1. What patterns or trends have you noticed?
2. What actions proved beneficial or harmful?
3. How will this influence your future decisions?

Provide a concise summary (2-3 sentences) that captures the most important insight.
"""

    @staticmethod
    def extract_agent_context(agent, year: int = 0) -> AgentReflectionContext:
        """Extract reflection context from an agent object.

        Flood-domain backward compatibility: hardcoded fields (elevated,
        insured, flood_count) are retained for existing experiments.
        New domains should use ``custom_traits`` for domain-specific data.
        """
        return AgentReflectionContext(
            agent_id=getattr(agent, 'id', str(agent)),
            agent_type=getattr(agent, 'agent_type', 'household'),
            name=getattr(agent, 'name', ''),
            elevated=getattr(agent, 'elevated', False),
            insured=getattr(agent, 'insured', False),
            flood_count=sum(1 for f in getattr(agent, 'flood_history', []) if f),
            years_in_sim=year,
            mg_status=getattr(agent, 'mg_status', False),
            recent_decision=getattr(agent, 'last_decision', ''),
            custom_traits=getattr(agent, 'custom_traits', {}),
        )

    def generate_personalized_reflection_prompt(
        self,
        context: AgentReflectionContext,
        memories: List[str],
        current_year: int
    ) -> str:
        """Generate a personalized reflection prompt with agent identity.

        Flood-domain backward compatibility: household status lines
        (elevated, insured, flood_count) are retained for existing
        experiments.  New domains should override this method or use
        a DomainReflectionAdapter to build domain-specific prompts.
        """
        if not memories:
            return ""

        memories_text = "\n".join([f"- {m}" for m in memories])

        identity_lines = [f"You are {context.agent_id}"]
        if context.name:
            identity_lines[0] += f" ({context.name})"
        identity_lines[0] += f", a {context.agent_type} agent in Year {current_year}."

        if context.agent_type == "household":
            status_parts = []
            if context.elevated:
                status_parts.append("your house is elevated")
            if context.insured:
                status_parts.append("you have flood insurance")
            if context.flood_count > 0:
                status_parts.append(f"you've been flooded {context.flood_count} time(s)")
            if context.mg_status:
                status_parts.append("you have limited resources")
            if status_parts:
                identity_lines.append(f"Current status: {', '.join(status_parts)}.")

        identity_block = "\n".join(identity_lines)

        questions = REFLECTION_QUESTIONS.get(context.agent_type, REFLECTION_QUESTIONS["household"])
        q_text = "\n".join([f"- {q}" for q in questions])

        return f"""{identity_block}

**Your Recent Memories:**
{memories_text}

**Reflection Questions:**
{q_text}

**Task:** Based on your experiences and situation, provide a 2-3 sentence personal reflection capturing what you've learned and how it will shape your future decisions. Speak in first person.
"""

    def generate_personalized_batch_prompt(
        self,
        batch_data: List[Dict[str, Any]],
        current_year: int
    ) -> str:
        """Generate batch prompt with per-agent identity context."""
        if not batch_data:
            return ""

        lines = [f"### Background\nYou are a Reflection Assistant for {len(batch_data)} agents in Year {current_year}."]
        lines.append("Instructions: Provide a personalized 2-sentence reflection for each agent based on their unique situation and memories.\n")

        lines.append("### Agent Data")
        for item in batch_data:
            agent_id = item.get("agent_id", "Unknown")
            ctx = item.get("context")
            memories = item.get("memories", [])
            mem_text = " ".join(memories) if memories else "(No memories)"

            if ctx:
                identity = f"[{ctx.agent_type}"
                traits = []
                if getattr(ctx, 'elevated', False):
                    traits.append("elevated")
                if getattr(ctx, 'insured', False):
                    traits.append("insured")
                if getattr(ctx, 'flood_count', 0) > 0:
                    traits.append(f"flooded {ctx.flood_count}x")
                if getattr(ctx, 'mg_status', False):
                    traits.append("MG")
                if traits:
                    identity += f", {', '.join(traits)}"
                identity += "]"
            else:
                identity = "[household]"

            lines.append(f"{agent_id} {identity} Memories: {mem_text}")

        lines.append("\n### Output Requirement")
        lines.append("Return ONLY a JSON object mapping Agent IDs to personalized reflection strings. Each reflection should reference the agent's specific situation. No filler.")

        return "\n".join(lines)

    def compute_dynamic_importance(
        self,
        context,
        base_importance: float = 0.9,
    ) -> float:
        """Compute variable importance based on agent state.

        If a DomainReflectionAdapter is attached, delegates to it.
        Otherwise falls back to the legacy flood-specific logic for
        backward compatibility.

        Args:
            context: AgentReflectionContext dataclass **or** plain dict.
            base_importance: Default importance when no rule matches.

        Returns:
            Importance score in [0.0, 1.0].
        """
        # --- Adapter path (domain-agnostic) ---
        if self.adapter is not None:
            # Convert dataclass to dict if needed
            if hasattr(context, "__dataclass_fields__"):
                from dataclasses import asdict
                ctx_dict = asdict(context)
            elif isinstance(context, dict):
                ctx_dict = context
            else:
                ctx_dict = {"context": context}
            return self.adapter.compute_importance(ctx_dict, base_importance)

        # --- Legacy fallback (flood-specific, backward compatible) ---
        importance = base_importance

        flood_count = getattr(context, "flood_count", 0) if not isinstance(context, dict) else context.get("flood_count", 0)
        mg_status = getattr(context, "mg_status", False) if not isinstance(context, dict) else context.get("mg_status", False)
        recent_decision = getattr(context, "recent_decision", "") if not isinstance(context, dict) else context.get("recent_decision", "")

        if flood_count == 1:
            importance = IMPORTANCE_PROFILES["first_flood"]
        elif flood_count > 2:
            importance = IMPORTANCE_PROFILES["repeated_flood"]

        if mg_status:
            importance = max(importance, IMPORTANCE_PROFILES["mg_agent"])

        if recent_decision in ("elevate_house", "relocate", "buy_insurance"):
            importance = max(importance, IMPORTANCE_PROFILES["post_action"])

        if (not mg_status
                and flood_count == 0
                and recent_decision in ("do_nothing", "")):
            importance = min(importance, IMPORTANCE_PROFILES["stable_year"])

        return round(min(1.0, max(0.0, importance)), 2)

    def parse_reflection_response(
        self,
        raw_response: str,
        source_memory_count: int,
        current_year: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ReflectionInsight]:
        """Parse LLM response into a ReflectionInsight.

        If an adapter is attached and *context* is provided, the importance
        score is computed dynamically instead of using the static boost.
        """
        if not raw_response or len(raw_response.strip()) < 10:
            return None

        # Clean and truncate if needed
        summary = raw_response.strip()[:500]

        # Dynamic importance via adapter when context is available
        importance = self.importance_boost
        if self.adapter is not None and context is not None:
            importance = self.adapter.compute_importance(context, self.importance_boost)

        return ReflectionInsight(
            summary=summary,
            source_memory_count=source_memory_count,
            importance=importance,
            year_created=current_year,
            domain_tags=[]
        )

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM client."""
        if self.llm_client is None:
            raise RuntimeError("ReflectionEngine requires llm_client for prompt execution.")
        if callable(self.llm_client):
            return self.llm_client(prompt)
        if hasattr(self.llm_client, "generate"):
            return self.llm_client.generate(prompt)
        raise RuntimeError("ReflectionEngine llm_client is not callable or compatible.")

    def reflect(self, agent_id: str, memories: List[str], context: dict):
        """Legacy reflection flow using built-in prompt + parse."""
        current_year = int(context.get("current_year", 0)) if context else 0
        prompt = self.generate_reflection_prompt(agent_id, memories, current_year)
        if not prompt:
            return None
        response = self._call_llm(prompt)
        return self.parse_reflection_response(response, len(memories), current_year)

    def reflect_v2(self, agent_id: str, memories: list, context: dict):
        """v2 reflection using SDK templates."""
        if self.template:
            prompt = self.template.generate_prompt(agent_id, memories, context)
            response = self._call_llm(prompt)
            insight = self.template.parse_response(response, memories, context)

            if self.integrator:
                self.integrator.process_reflection(agent_id, response, memories, context)

            return insight
        return self.reflect(agent_id, memories, context)
    
    def store_insight(self, agent_id: str, insight: ReflectionInsight) -> None:
        """Store a reflection insight for an agent."""
        if agent_id not in self.reflection_history:
            self.reflection_history[agent_id] = []
        self.reflection_history[agent_id].append(insight)
        
        # Log to file if configured
        if self.output_path:
            import json
            from dataclasses import asdict
            entry = asdict(insight)
            entry["agent_id"] = agent_id
            entry["timestamp"] = datetime.now().isoformat()
            try:
                with open(self.output_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.error(f"[Reflection] Failed to write log: {e}")

        logger.info(f"[Reflection] Agent {agent_id} | New insight stored | Importance: {insight.importance:.2f}")
    
    def get_insights(self, agent_id: str, top_k: int = 3) -> List[ReflectionInsight]:
        """Retrieve top insights for an agent, sorted by importance."""
        insights = self.reflection_history.get(agent_id, [])
        return sorted(insights, key=lambda x: x.importance, reverse=True)[:top_k]
    
    def format_insights_for_context(self, agent_id: str, top_k: int = 2) -> str:
        """Format insights as a string for injection into agent context."""
        insights = self.get_insights(agent_id, top_k)
        if not insights:
            return ""
        
        lines = ["**Long-Term Lessons (Reflections):**"]
        for i, insight in enumerate(insights, 1):
            lines.append(f"{i}. (Year {insight.year_created}) {insight.summary}")
        return "\n".join(lines)
    
    # =========================================================================
    # BATCH REFLECTION (Efficiency Optimization)
    # =========================================================================
    def generate_batch_reflection_prompt(
        self,
        batch_data: List[Dict[str, Any]],
        current_year: int,
        reflection_questions: Optional[List[str]] = None,
    ) -> str:
        """
        Generate a prompt for batch reflection across multiple agents.
        Optimized for smaller models like Llama 3.2.

        Args:
            batch_data: Per-agent dicts with agent_id, memories, and optional context.
            current_year: Current simulation year.
            reflection_questions: Optional domain-specific guidance questions
                from YAML config (global_config.reflection.questions).
        """
        if not batch_data:
            return ""

        lines = [f"### Background\nYou are a Reflection Assistant for {len(batch_data)} agents in a simulation (Year {current_year})."]
        lines.append("Instructions: Summarize each agent's memories into a 2-sentence 'Lesson Learned'.")

        if reflection_questions:
            lines.append("Focus your reflections on:")
            for q in reflection_questions:
                lines.append(f"  - {q}")

        lines.append("")

        lines.append("### Task Data to Process")
        for item in batch_data:
            agent_id = item.get("agent_id", "Unknown")
            memories = item.get("memories", [])
            mem_text = " ".join(memories) if memories else "(No memories recorded)"
            lines.append(f"{agent_id} Memories: {mem_text}")
        
        lines.append("\n### Output Requirement")
        lines.append("Return ONLY the JSON object mapping Agent IDs to strings. No conversational filler.")
        
        return "\n".join(lines)
    
    def parse_batch_reflection_response(
        self,
        raw_response: str,
        batch_agent_ids: List[str],
        current_year: int
    ) -> Dict[str, Optional[ReflectionInsight]]:
        """
        Robust multi-stage parser for batch reflections.
        Handles JSON, Markdown, and Heuristic Line-parsing.
        """
        import json
        import re
        
        results: Dict[str, Optional[ReflectionInsight]] = {aid: None for aid in batch_agent_ids}
        
        if not raw_response or len(raw_response.strip()) < 5:
            logger.warning("[Reflection:Batch] Empty or trivial response.")
            return results
        
        # --- Stage 1: Standard JSON Extraction & Repair ---
        json_content = raw_response
        # Find latest/outermost { } block
        json_match = re.search(r'(\{.*\})', raw_response, re.DOTALL)
        if json_match:
            json_content = json_match.group(1)
        
        success = False
        try:
            # Try to repair common small-model JSON errors
            repaired = json_content.strip()
            # Quote Agent IDs if unquoted (e.g. Agent_001: "...")
            repaired = re.sub(r'(?<!")(\bAgent_\d+\b)(?!")', r'"\1"', repaired)
            # Clean trailing commas (e.g. "key": "val", })
            repaired = re.sub(r',\s*\}', '}', repaired)
            
            data = json.loads(repaired)
            if isinstance(data, dict):
                for aid in batch_agent_ids:
                    # Case-insensitive key lookup for robustness
                    found_key = next((k for k in data.keys() if k.lower() == aid.lower()), None)
                    if found_key and isinstance(data[found_key], str):
                        results[aid] = self._create_insight(data[found_key], current_year)
                
                if any(v is not None for v in results.values()):
                    success = True
                    logger.info("[Reflection:Batch] Stage 1 (JSON) parsing successful.")
        except Exception as e:
            logger.debug(f"[Reflection:Batch] Stage 1 failed: {e}")

        # --- Stage 2: Regex Fallback (Key: Value Pattern) ---
        if not success or any(v is None for v in results.values()):
            logger.info("[Reflection:Batch] Attempting Stage 2 (Regex) parsing...")
            for aid in batch_agent_ids:
                if results[aid] is not None: continue
                # Match "Agent_XXX": "Insight..." or **Agent_XXX**: Insight...
                pattern = rf'["\*\']?{re.escape(aid)}["\*\']?\s*[:\-]\s*["\']?([^"\'\n\r]+)["\']?'
                match = re.search(pattern, raw_response, re.IGNORECASE)
                if match:
                    results[aid] = self._create_insight(match.group(1).strip(), current_year)
            
            if any(v is not None for v in results.values()):
                success = True

        # --- Stage 3: Heuristic Line Parsing (Final Resort) ---
        if not success or any(v is None for v in results.values()):
            logger.info("[Reflection:Batch] Attempting Stage 3 (Heuristic) parsing...")
            lines = raw_response.split('\n')
            for line in lines:
                for aid in batch_agent_ids:
                    if results[aid] is not None: continue
                    if aid.lower() in line.lower() and (':' in line or '-' in line):
                        # Extract everything after the delimiter
                        parts = re.split(r'[:\-]', line, 1)
                        if len(parts) > 1 and len(parts[1].strip()) > 10:
                            results[aid] = self._create_insight(parts[1].strip(), current_year)
        
        return results

    def _create_insight(
        self, text: str, year: int, context: Optional[Dict[str, Any]] = None
    ) -> ReflectionInsight:
        """Helper to create a standard insight object.

        Uses adapter-based importance when context is provided.
        """
        importance = self.importance_boost
        if self.adapter is not None and context is not None:
            importance = self.adapter.compute_importance(context, self.importance_boost)

        return ReflectionInsight(
            summary=text.strip()[:500],
            source_memory_count=0,
            importance=importance,
            year_created=year,
            domain_tags=[]
        )

    def clear(self, agent_id: str) -> None:
        """Clear reflection history for an agent."""
        if agent_id in self.reflection_history:
            del self.reflection_history[agent_id]
