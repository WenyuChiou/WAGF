"""
Reflection Engine - Cognitive consolidation for long-term memory resilience.

Implements "Year-End Reflection" to combat memory erosion (the Goldfish Effect).
Inspired by Park et al. (2023) Generative Agents reflection architecture.
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from broker.utils.logging import setup_logger

logger = setup_logger(__name__)


@dataclass
class ReflectionInsight:
    """A consolidated semantic insight derived from multiple episodic memories."""
    summary: str                      # Concise high-level insight
    source_memory_count: int = 0      # How many memories contributed
    importance: float = 1.0           # Consolidated importance score (0-1)
    year_created: int = 0             # When this insight was generated
    domain_tags: List[str] = field(default_factory=list)  # e.g., ["flood", "damage", "adaptation"]


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
        insight_importance_boost: float = 0.9  # Importance score for new insights
    ):
        self.reflection_interval = reflection_interval
        self.max_insights = max_insights_per_reflection
        self.importance_boost = insight_importance_boost
        self.reflection_history: Dict[str, List[ReflectionInsight]] = {}
    
    def should_reflect(self, agent_id: str, current_year: int) -> bool:
        """Check if it's time for an agent to perform reflection."""
        if self.reflection_interval <= 0:
            return False
        return current_year > 0 and current_year % self.reflection_interval == 0
    
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

    def parse_reflection_response(
        self,
        raw_response: str,
        source_memory_count: int,
        current_year: int
    ) -> Optional[ReflectionInsight]:
        """Parse LLM response into a ReflectionInsight."""
        if not raw_response or len(raw_response.strip()) < 10:
            return None
        
        # Clean and truncate if needed
        summary = raw_response.strip()[:500]
        
        return ReflectionInsight(
            summary=summary,
            source_memory_count=source_memory_count,
            importance=self.importance_boost,
            year_created=current_year,
            domain_tags=[]  # Could be enhanced with keyword extraction
        )
    
    def store_insight(self, agent_id: str, insight: ReflectionInsight) -> None:
        """Store a reflection insight for an agent."""
        if agent_id not in self.reflection_history:
            self.reflection_history[agent_id] = []
        self.reflection_history[agent_id].append(insight)
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
        current_year: int
    ) -> str:
        """
        Generate a prompt for batch reflection across multiple agents.
        
        Args:
            batch_data: List of dicts with 'agent_id' and 'memories' keys.
            current_year: The current simulation year.
        
        Returns:
            A prompt instructing the LLM to output a JSON object mapping Agent IDs to insights.
        """
        if not batch_data:
            return ""
        
        lines = [f"You are a reflection assistant helping {len(batch_data)} agents summarize their experiences from Year {current_year}.\n"]
        lines.append("For EACH agent below, write a concise 2-3 sentence lesson learned from their listed memories.\n")
        lines.append("---\n")
        
        for item in batch_data:
            agent_id = item.get("agent_id", "Unknown")
            memories = item.get("memories", [])
            mem_text = "\n".join([f"  - {m}" for m in memories]) if memories else "  (No memories recorded)"
            lines.append(f"**{agent_id} Memories:**\n{mem_text}\n")
        
        lines.append("---\n")
        lines.append("**Output Format:** Return a JSON object where each key is an Agent ID and the value is their insight string.\n")
        lines.append("Example: {\"Agent_001\": \"I learned that...\", \"Agent_002\": \"Floods are...\"}\n")
        lines.append("**IMPORTANT:** Return ONLY the JSON object, no other text.")
        
        return "\n".join(lines)
    
    def parse_batch_reflection_response(
        self,
        raw_response: str,
        batch_agent_ids: List[str],
        current_year: int
    ) -> Dict[str, Optional[ReflectionInsight]]:
        """
        Parse LLM batch response into per-agent ReflectionInsights.
        
        Args:
            raw_response: The raw LLM output (expected to be JSON).
            batch_agent_ids: List of agent IDs that were in the batch.
            current_year: The current simulation year.
        
        Returns:
            Dict mapping agent_id -> ReflectionInsight (or None if parsing failed).
        """
        import json
        import re
        
        results: Dict[str, Optional[ReflectionInsight]] = {aid: None for aid in batch_agent_ids}
        
        if not raw_response:
            logger.warning("[Reflection:Batch] Empty response received.")
            return results
        
        # Try to extract JSON from the response (handle markdown code blocks)
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if not json_match:
            logger.warning(f"[Reflection:Batch] Could not find JSON in response: {raw_response[:200]}...")
            return results
        
        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.warning(f"[Reflection:Batch] JSON parse error: {e}")
            return results
        
        # Map parsed insights to agents
        for agent_id in batch_agent_ids:
            insight_text = data.get(agent_id)
            if insight_text and isinstance(insight_text, str) and len(insight_text.strip()) > 10:
                results[agent_id] = ReflectionInsight(
                    summary=insight_text.strip()[:500],
                    source_memory_count=0,  # Will be updated by caller if needed
                    importance=self.importance_boost,
                    year_created=current_year,
                    domain_tags=[]
                )
                logger.info(f"[Reflection:Batch] {agent_id} | Insight parsed successfully.")
            else:
                logger.warning(f"[Reflection:Batch] {agent_id} | No valid insight found in response.")
        
        return results
    
    def clear(self, agent_id: str) -> None:
        """Clear reflection history for an agent."""
        if agent_id in self.reflection_history:
            del self.reflection_history[agent_id]
