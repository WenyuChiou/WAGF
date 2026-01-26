"""
Reflection-Memory Integration Layer.

Provides the feedback loop between reflection system and memory engine,
enabling automatic promotion of insights to long-term memory.

Usage:
    >>> from governed_ai_sdk.v1_prototype.reflection import ReflectionMemoryIntegrator
    >>> integrator = ReflectionMemoryIntegrator(
    ...     template=FloodReflectionTemplate(),
    ...     memory_store_fn=memory_engine.add_memory,
    ...     auto_promote=True
    ... )
    >>> insight = integrator.process_reflection(agent_id, response, memories, context)
"""

from typing import Any, Callable, Dict, List, Optional
import logging
from datetime import datetime

from .insight import ReflectionInsight, ReflectionTrace
from .templates import ReflectionTemplate, get_reflection_template

logger = logging.getLogger(__name__)


class ReflectionMemoryIntegrator:
    """
    Bridge between reflection system and memory engine.

    Handles:
    1. Processing LLM responses through domain templates
    2. Auto-promoting high-importance insights to memory
    3. Tracking reflection traces for explainability

    Attributes:
        template: Domain-specific reflection template
        memory_store_fn: Callback to store memories
        auto_promote: Whether to automatically promote insights
        promotion_threshold: Minimum importance for auto-promotion
    """

    def __init__(
        self,
        template: Optional[ReflectionTemplate] = None,
        memory_store_fn: Optional[Callable[[str, Dict], None]] = None,
        auto_promote: bool = True,
        promotion_threshold: float = 0.7,
        domain: str = "generic",
    ):
        """
        Initialize the integrator.

        Args:
            template: ReflectionTemplate to use (or fetched from domain)
            memory_store_fn: Function to store memories (agent_id, memory_dict)
            auto_promote: Whether to auto-promote insights to memory
            promotion_threshold: Minimum importance for promotion (0-1)
            domain: Domain name if template not provided
        """
        self.template = template or get_reflection_template(domain)
        self.memory_store_fn = memory_store_fn
        self.auto_promote = auto_promote
        self.promotion_threshold = max(0.0, min(1.0, promotion_threshold))
        self._traces: List[ReflectionTrace] = []

    @property
    def domain(self) -> str:
        """Get the domain from the template."""
        return self.template.domain

    def process_reflection(
        self,
        agent_id: str,
        llm_response: str,
        memories: List[str],
        context: Dict[str, Any],
        processing_time_ms: float = 0.0,
    ) -> ReflectionInsight:
        """
        Parse reflection and optionally promote to memory.

        Args:
            agent_id: The reflecting agent's ID
            llm_response: Raw LLM response to parse
            memories: Input memories used for reflection
            context: Context provided for reflection
            processing_time_ms: Time taken for LLM call

        Returns:
            Parsed ReflectionInsight
        """
        start_time = datetime.now()

        # Parse the response using template
        insight = self.template.parse_response(llm_response, memories, context)

        # Create trace for explainability
        trace = ReflectionTrace(
            agent_id=agent_id,
            timestamp=start_time,
            input_memories=memories[:10],
            template_name=self.template.name,
            prompt="",  # Not available at this point
            raw_response=llm_response,
            insight=insight,
            processing_time_ms=processing_time_ms,
        )
        self._traces.append(trace)

        # Auto-promote to memory if configured
        if self.auto_promote and insight.importance >= self.promotion_threshold:
            self._promote_to_memory(agent_id, insight)

        logger.debug(
            f"Processed reflection for {agent_id}: "
            f"importance={insight.importance:.2f}, promoted={insight.importance >= self.promotion_threshold}"
        )

        return insight

    def generate_and_process(
        self,
        agent_id: str,
        memories: List[str],
        context: Dict[str, Any],
        llm_call_fn: Callable[[str], str],
    ) -> ReflectionInsight:
        """
        Generate prompt, call LLM, and process response.

        This is a convenience method that handles the full reflection flow.

        Args:
            agent_id: The reflecting agent's ID
            memories: Memories to reflect on
            context: Context for reflection
            llm_call_fn: Function to call LLM (prompt -> response)

        Returns:
            Parsed ReflectionInsight
        """
        import time

        # Generate prompt
        prompt = self.template.generate_prompt(agent_id, memories, context)

        # Call LLM
        start_time = time.time()
        response = llm_call_fn(prompt)
        processing_time_ms = (time.time() - start_time) * 1000

        # Process response
        insight = self.process_reflection(
            agent_id, response, memories, context, processing_time_ms
        )

        # Update trace with prompt
        if self._traces:
            self._traces[-1].prompt = prompt

        return insight

    def _promote_to_memory(self, agent_id: str, insight: ReflectionInsight) -> bool:
        """
        Promote insight to memory storage.

        Args:
            agent_id: Agent to store memory for
            insight: Insight to promote

        Returns:
            True if promoted successfully
        """
        if not self.memory_store_fn:
            logger.warning(f"No memory_store_fn configured, cannot promote insight for {agent_id}")
            return False

        try:
            memory_dict = insight.to_memory_format()
            self.memory_store_fn(agent_id, memory_dict)
            logger.info(f"Promoted insight to memory for {agent_id}: {insight.summary[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to promote insight for {agent_id}: {e}")
            return False

    def get_traces(self, agent_id: Optional[str] = None) -> List[ReflectionTrace]:
        """
        Get reflection traces for debugging/analysis.

        Args:
            agent_id: Filter by agent ID (None for all)

        Returns:
            List of ReflectionTrace objects
        """
        if agent_id:
            return [t for t in self._traces if t.agent_id == agent_id]
        return self._traces.copy()

    def clear_traces(self) -> None:
        """Clear all stored traces."""
        self._traces.clear()

    def get_promotion_stats(self) -> Dict[str, Any]:
        """
        Get statistics about insight promotions.

        Returns:
            Dict with promotion statistics
        """
        total = len(self._traces)
        promoted = sum(
            1 for t in self._traces
            if t.insight and t.insight.importance >= self.promotion_threshold
        )
        avg_importance = (
            sum(t.insight.importance for t in self._traces if t.insight) / total
            if total > 0 else 0
        )

        return {
            "total_reflections": total,
            "promoted_count": promoted,
            "promotion_rate": promoted / total if total > 0 else 0,
            "average_importance": avg_importance,
            "promotion_threshold": self.promotion_threshold,
        }


class BatchReflectionProcessor:
    """
    Process reflections for multiple agents efficiently.

    Useful for end-of-year or periodic reflection sessions.
    """

    def __init__(
        self,
        domain: str = "generic",
        memory_store_fn: Optional[Callable[[str, Dict], None]] = None,
        auto_promote: bool = True,
        promotion_threshold: float = 0.7,
    ):
        """
        Initialize batch processor.

        Args:
            domain: Domain for all agents
            memory_store_fn: Callback to store memories
            auto_promote: Whether to auto-promote insights
            promotion_threshold: Minimum importance for promotion
        """
        self.integrator = ReflectionMemoryIntegrator(
            domain=domain,
            memory_store_fn=memory_store_fn,
            auto_promote=auto_promote,
            promotion_threshold=promotion_threshold,
        )

    def process_batch(
        self,
        agents_data: List[Dict[str, Any]],
        llm_call_fn: Callable[[str], str],
    ) -> Dict[str, ReflectionInsight]:
        """
        Process reflections for multiple agents.

        Args:
            agents_data: List of dicts with {agent_id, memories, context}
            llm_call_fn: Function to call LLM

        Returns:
            Dict mapping agent_id to ReflectionInsight
        """
        results = {}

        for agent_data in agents_data:
            agent_id = agent_data["agent_id"]
            memories = agent_data.get("memories", [])
            context = agent_data.get("context", {})

            try:
                insight = self.integrator.generate_and_process(
                    agent_id, memories, context, llm_call_fn
                )
                results[agent_id] = insight
            except Exception as e:
                logger.error(f"Failed to process reflection for {agent_id}: {e}")

        return results

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the batch."""
        return self.integrator.get_promotion_stats()
