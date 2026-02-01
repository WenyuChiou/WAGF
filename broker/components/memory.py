"""
Legacy Memory Module — CognitiveMemory for multi-agent examples.

.. deprecated::
    This module is retained only for backward compatibility with
    ``examples/multi_agent/flood/ma_agents/``.  New code should use
    ``broker.components.memory_engine`` (MemoryEngine hierarchy) instead.

    Will be fully removed in Phase 8C of the generalization plan.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


# =============================================================================
# COGNITIVE MEMORY (V2 - Based on Hello-Agents concepts)
# =============================================================================

@dataclass
class MemoryItem:
    """Single memory item with metadata."""
    content: str
    importance: float = 0.5
    year: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)


class CognitiveMemory:
    """
    Version 2: Cognitive memory with working + episodic layers.

    Features:
    - Working Memory: short-term, limited capacity
    - Episodic Memory: long-term, time decay
    - Consolidation: high-importance working -> episodic
    - Retrieval scoring: (recency * importance) weighted
    """

    # Configuration
    WORKING_CAPACITY = 10
    EPISODIC_CAPACITY = 50
    CONSOLIDATION_THRESHOLD = 0.7
    DECAY_RATE = 0.95  # Per year

    def __init__(self, agent_id: str = ""):
        self.agent_id = agent_id
        self._working: List[MemoryItem] = []
        self._episodic: List[MemoryItem] = []

    # ===== Working Memory =====

    def add_working(self, content: str, importance: float = 0.5,
                    year: int = 0, tags: List[str] = None) -> MemoryItem:
        """Add to working memory."""
        # Evict if at capacity
        if len(self._working) >= self.WORKING_CAPACITY:
            self._working.sort(key=lambda x: x.importance)
            self._working.pop(0)

        item = MemoryItem(
            content=content,
            importance=importance,
            year=year,
            tags=tags or []
        )
        self._working.append(item)
        return item

    # ===== Episodic Memory =====

    def add_episodic(self, content: str, importance: float = 0.7,
                     year: int = 0, tags: List[str] = None) -> MemoryItem:
        """Add to episodic memory (permanent)."""
        item = MemoryItem(
            content=content,
            importance=importance,
            year=year,
            tags=tags or []
        )
        self._episodic.append(item)

        # Capacity control
        if len(self._episodic) > self.EPISODIC_CAPACITY:
            self._episodic.sort(key=lambda x: x.importance)
            self._episodic.pop(0)

        return item

    # ===== Consolidation =====

    def consolidate(self) -> int:
        """Transfer high-importance working memories to episodic."""
        transferred = 0
        for item in self._working:
            if item.importance >= self.CONSOLIDATION_THRESHOLD:
                self._episodic.append(MemoryItem(
                    content=item.content,
                    importance=item.importance,
                    year=item.year,
                    tags=item.tags
                ))
                transferred += 1
        return transferred

    # ===== Retrieval =====

    def retrieve(self, top_k: int = 5, current_year: int = 0) -> List[str]:
        """
        Retrieve memories prioritizing working, supplementing with episodic.

        Scoring: recency * importance (working) or decay * importance (episodic)
        """
        results = []

        # Working Memory (most recent first, then by importance)
        working_sorted = sorted(
            self._working,
            key=lambda x: (x.timestamp, x.importance),
            reverse=True
        )
        for item in working_sorted[:top_k]:
            results.append(item.content)

        # Supplement with Episodic Memory
        remaining = top_k - len(results)
        if remaining > 0:
            episodic_scored = []
            for item in self._episodic:
                years_passed = max(0, current_year - item.year)
                decay = self.DECAY_RATE ** years_passed
                score = decay * (0.8 + item.importance * 0.4)
                episodic_scored.append((score, item))

            episodic_sorted = sorted(episodic_scored, key=lambda x: x[0], reverse=True)
            for _, item in episodic_sorted[:remaining]:
                if item.content not in results:
                    results.append(item.content)

        return results[:top_k]

    # ===== Convenience Methods =====

    def add_experience(self, content: str, importance: float = 0.5,
                       year: int = 0, tags: List[str] = None) -> MemoryItem:
        """Add experience (auto-route to working or episodic)."""
        if importance >= self.CONSOLIDATION_THRESHOLD:
            return self.add_episodic(content, importance, year, tags)
        return self.add_working(content, importance, year, tags)


    def format_for_prompt(self, current_year: int = 0) -> str:
        """Format for LLM prompt."""
        memories = self.retrieve(top_k=5, current_year=current_year)
        if not memories:
            return "No memories recalled."
        return "\n".join(f"- {m}" for m in memories)

    def to_list(self, current_year: int = 0) -> List[str]:
        """Return as list (for ContextBuilder compatibility)."""
        return self.retrieve(top_k=5, current_year=current_year)


# =============================================================================
# MEMORY PROVIDER (used by multi-agent flood examples)
# =============================================================================

class MemoryProvider:
    """
    Memory provider for integration with ContextBuilder.

    Wraps CognitiveMemory instances and provides unified interface.
    """

    def __init__(self, memory_type: str = "cognitive", **kwargs):
        self.memory_type = memory_type
        self._memories: Dict[str, CognitiveMemory] = {}

    def get_or_create(self, agent_id: str) -> CognitiveMemory:
        """Get or create memory for agent."""
        if agent_id not in self._memories:
            self._memories[agent_id] = CognitiveMemory(agent_id)
        return self._memories[agent_id]

    def get_memory(self, agent_id: str, current_year: int = 0) -> List[str]:
        """Get memory as list (for ContextBuilder.get_memory())."""
        memory = self.get_or_create(agent_id)
        return memory.to_list(current_year)

    def add_experience(self, agent_id: str, content: str,
                       importance: float = 0.5, year: int = 0,
                       **kwargs) -> None:
        """Add experience to agent's memory."""
        memory = self.get_or_create(agent_id)
        memory.add_experience(content, importance, year)


    def consolidate_all(self) -> Dict[str, int]:
        """Consolidate all cognitive memories."""
        results = {}
        for agent_id, memory in self._memories.items():
            results[agent_id] = memory.consolidate()
        return results

    def format_for_prompt(self, agent_id: str, current_year: int = 0) -> str:
        """Format memory for prompt."""
        memory = self.get_or_create(agent_id)
        return memory.format_for_prompt(current_year)
