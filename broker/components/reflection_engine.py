"""
Reflection Engine - Cognitive consolidation for long-term memory resilience.

Implements "Year-End Reflection" to combat memory erosion (the Goldfish Effect).
Inspired by Park et al. (2023) Generative Agents reflection architecture.
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from broker.utils.logging import setup_logger

logger = setup_logger(__name__)


@dataclass
class ReflectionInsight:
    """A consolidated semantic insight derived from multiple episodic memories."""
    summary: str                      # Concise high-level insight
    source_memory_count: int = 0      # How many memories contributed
    importance: float = 1.0           # Consolidated importance score (0-1)
    year_created: int = 0             # When this insight was generated
    domain_tags: List[str] = field(default_factory=list)  # e.g., ["event_type", "impact", "response"]


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
        output_path: Optional[str] = None       # Path to save reflection logs
    ):
        self.reflection_interval = reflection_interval
        self.max_insights = max_insights_per_reflection
        self.importance_boost = insight_importance_boost
        self.reflection_history: Dict[str, List[ReflectionInsight]] = {}
        self.output_path = output_path
        
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
        current_year: int
    ) -> str:
        """
        Generate a prompt for batch reflection across multiple agents.
        Optimized for smaller models like Llama 3.2.
        """
        if not batch_data:
            return ""
        
        lines = [f"### Background\nYou are a Reflection Assistant for {len(batch_data)} agents in a simulation (Year {current_year})."]
        lines.append("Instructions: Summarize each agent's memories into a 2-sentence 'Lesson Learned'.\n")

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

    def _create_insight(self, text: str, year: int) -> ReflectionInsight:
        """Helper to create a standard insight object."""
        return ReflectionInsight(
            summary=text.strip()[:500],
            source_memory_count=0,
            importance=self.importance_boost,
            year_created=year,
            domain_tags=[]
        )

    def clear(self, agent_id: str) -> None:
        """Clear reflection history for an agent."""
        if agent_id in self.reflection_history:
            del self.reflection_history[agent_id]
