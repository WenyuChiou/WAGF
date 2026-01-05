"""
Memory Module - Simple memory and retrieval for agents.

This is the simplified version that integrates with ContextBuilder.
Can be extended for more advanced features later.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
import random


# =============================================================================
# SIMPLE MEMORY (V1 - Compatible with single-agent experiment)
# =============================================================================

class SimpleMemory:
    """
    Version 1: Simple list-based memory (compatible with v2_skill_governed).
    
    Features:
    - FIFO replacement when capacity exceeded
    - Random recall of historical events
    - Compatible with existing ContextBuilder.get_memory()
    """
    
    MEMORY_WINDOW = 5
    RANDOM_RECALL_CHANCE = 0.2
    
    PAST_EVENTS = [
        "A flood event about 15 years ago caused $500,000 in city-wide damages",
        "Some residents reported delays when processing their flood insurance claims",
        "A few households in the area elevated their homes before recent floods",
        "The city previously introduced a program offering elevation support",
        "News outlets have reported increasing flood frequency and severity"
    ]
    
    def __init__(self, agent_id: str = ""):
        self.agent_id = agent_id
        self._memories: List[str] = []
    
    def add(self, content: str) -> None:
        """Add memory (FIFO when exceeding window)."""
        self._memories.append(content)
        if len(self._memories) > self.MEMORY_WINDOW:
            self._memories.pop(0)
    
    def retrieve(self) -> List[str]:
        """Retrieve memories (with random historical recall)."""
        memories = self._memories.copy()
        
        # 20% chance to recall random historical event
        if random.random() < self.RANDOM_RECALL_CHANCE:
            random_event = random.choice(self.PAST_EVENTS)
            if random_event not in memories:
                memories.append(random_event)
        
        return memories
    
    def update_after_flood(self, damage: float, year: int = 0) -> None:
        """Update memory after flood event."""
        if year:
            self.add(f"Year {year}: A flood occurred causing ${damage:,.0f} in damages")
        else:
            self.add(f"A flood occurred causing ${damage:,.0f} in damages")
    
    def update_after_decision(self, decision: str, year: int = 0) -> None:
        """Update memory after decision."""
        if year:
            self.add(f"Year {year}: I chose to {decision}")
        else:
            self.add(f"I chose to {decision}")
    
    def format_for_prompt(self) -> str:
        """Format memories for LLM prompt."""
        memories = self.retrieve()
        if not memories:
            return "No past events recalled."
        return "\n".join(f"- {m}" for m in memories)
    
    def to_list(self) -> List[str]:
        """Return as list (for ContextBuilder compatibility)."""
        return self.retrieve()


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
    
    def update_after_flood(self, damage: float, year: int) -> MemoryItem:
        """Add flood experience (high importance -> episodic)."""
        content = f"Year {year}: A flood occurred causing ${damage:,.0f} in damages"
        return self.add_episodic(content, importance=0.9, year=year, tags=["flood"])
    
    def update_after_decision(self, decision: str, year: int) -> MemoryItem:
        """Add decision (medium importance -> working)."""
        content = f"Year {year}: I decided to {decision}"
        importance = 0.7 if decision != "do_nothing" else 0.3
        return self.add_working(content, importance, year, tags=["decision"])
    
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
# MEMORY CONTEXT BUILDER INTEGRATION
# =============================================================================

class MemoryProvider:
    """
    Memory provider for integration with ContextBuilder.
    
    Wraps memory instances and provides unified interface.
    """
    
    def __init__(self, memory_type: str = "simple"):
        """
        Args:
            memory_type: "simple" or "cognitive"
        """
        self.memory_type = memory_type
        self._memories: Dict[str, Any] = {}  # agent_id -> Memory instance
    
    def get_or_create(self, agent_id: str) -> Any:
        """Get or create memory for agent."""
        if agent_id not in self._memories:
            if self.memory_type == "cognitive":
                self._memories[agent_id] = CognitiveMemory(agent_id)
            else:
                self._memories[agent_id] = SimpleMemory(agent_id)
        return self._memories[agent_id]
    
    def get_memory(self, agent_id: str, current_year: int = 0) -> List[str]:
        """Get memory as list (for ContextBuilder.get_memory())."""
        memory = self.get_or_create(agent_id)
        if isinstance(memory, CognitiveMemory):
            return memory.to_list(current_year)
        return memory.to_list()
    
    def add_experience(self, agent_id: str, content: str, 
                       importance: float = 0.5, year: int = 0) -> None:
        """Add experience to agent's memory."""
        memory = self.get_or_create(agent_id)
        if isinstance(memory, CognitiveMemory):
            memory.add_experience(content, importance, year)
        else:
            memory.add(content)
    
    def update_after_flood(self, agent_id: str, damage: float, year: int = 0) -> None:
        """Update memory after flood."""
        memory = self.get_or_create(agent_id)
        memory.update_after_flood(damage, year)
    
    def update_after_decision(self, agent_id: str, decision: str, year: int = 0) -> None:
        """Update memory after decision."""
        memory = self.get_or_create(agent_id)
        memory.update_after_decision(decision, year)
    
    def consolidate_all(self) -> Dict[str, int]:
        """Consolidate all cognitive memories."""
        results = {}
        for agent_id, memory in self._memories.items():
            if isinstance(memory, CognitiveMemory):
                results[agent_id] = memory.consolidate()
        return results
    
    def format_for_prompt(self, agent_id: str, current_year: int = 0) -> str:
        """Format memory for prompt."""
        memory = self.get_or_create(agent_id)
        if isinstance(memory, CognitiveMemory):
            return memory.format_for_prompt(current_year)
        return memory.format_for_prompt()


# =============================================================================
# SIMPLE RETRIEVAL (V1 - Keyword-based)
# =============================================================================

class SimpleRetrieval:
    """
    Simple retrieval for external knowledge.
    
    V1: Keyword-based matching (no vector DB required).
    Can be extended to vector search later.
    """
    
    def __init__(self):
        self._documents: Dict[str, str] = {}  # doc_id -> content
        self._tags: Dict[str, List[str]] = {}  # doc_id -> tags
    
    def add_document(self, doc_id: str, content: str, 
                     tags: List[str] = None) -> None:
        """Add document to knowledge base."""
        self._documents[doc_id] = content
        self._tags[doc_id] = tags or []
    
    def retrieve_by_tags(self, tags: List[str], top_k: int = 3) -> List[str]:
        """Retrieve documents matching any tag."""
        results = []
        for doc_id, doc_tags in self._tags.items():
            if any(t in doc_tags for t in tags):
                results.append(self._documents[doc_id])
        return results[:top_k]
    
    def retrieve_by_keyword(self, keyword: str, top_k: int = 3) -> List[str]:
        """Retrieve documents containing keyword."""
        results = []
        keyword_lower = keyword.lower()
        for doc_id, content in self._documents.items():
            if keyword_lower in content.lower():
                results.append(content)
        return results[:top_k]
    
    def format_for_prompt(self, tags: List[str] = None, 
                          keyword: str = None) -> str:
        """Format retrieved documents for prompt."""
        results = []
        if tags:
            results.extend(self.retrieve_by_tags(tags))
        if keyword:
            results.extend(self.retrieve_by_keyword(keyword))
        
        # Deduplicate
        unique_results = list(dict.fromkeys(results))
        
        if not unique_results:
            return "No relevant information found."
        return "\n".join(f"- {r}" for r in unique_results[:5])


# =============================================================================
# MEMORY AWARE CONTEXT BUILDER
# =============================================================================

from broker.context_builder import ContextBuilder


class MemoryAwareContextBuilder(ContextBuilder):
    """
    Context Builder with integrated memory support.
    
    Extends base ContextBuilder with:
    - Memory provider integration
    - Retrieval support
    - Year-aware memory retrieval
    """
    
    def __init__(
        self,
        state_provider: Any,
        prompt_template: str,
        observable_fields: List[str],
        memory_provider: Optional[MemoryProvider] = None,
        retrieval: Optional[SimpleRetrieval] = None
    ):
        self.state_provider = state_provider
        self.prompt_template = prompt_template
        self.observable_fields = observable_fields
        self.memory_provider = memory_provider or MemoryProvider("simple")
        self.retrieval = retrieval
        self._current_year = 0
    
    def set_year(self, year: int) -> None:
        """Set current simulation year."""
        self._current_year = year
    
    def build(
        self,
        agent_id: str,
        observable: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Build context with memory."""
        # Get base state
        full_state = self.state_provider.get_agent_state(agent_id)
        
        # Filter to observable fields
        context = {
            k: v for k, v in full_state.items()
            if k in self.observable_fields
        }
        context["agent_id"] = agent_id
        context["year"] = self._current_year
        
        # Add memory
        context["memory"] = self.memory_provider.get_memory(
            agent_id, self._current_year
        )
        context["memory_formatted"] = self.memory_provider.format_for_prompt(
            agent_id, self._current_year
        )
        
        # Add retrieval if available
        if self.retrieval and observable and "knowledge" in observable:
            agent_type = full_state.get("agent_type", "")
            tags = self._get_relevant_tags(agent_type)
            context["knowledge"] = self.retrieval.format_for_prompt(tags=tags)
        
        return context
    
    def _get_relevant_tags(self, agent_type: str) -> List[str]:
        """Get relevant retrieval tags for agent type."""
        base_tags = ["flood", "adaptation"]
        if "MG" in agent_type:
            base_tags.append("subsidy")
        if "Owner" in agent_type:
            base_tags.extend(["elevation", "insurance"])
        return base_tags
    
    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format with memory section."""
        return self.prompt_template.format(**context)
    
    def get_memory(self, agent_id: str) -> List[str]:
        """Get agent memory (ContextBuilder interface)."""
        return self.memory_provider.get_memory(agent_id, self._current_year)
    
    # ===== Memory Operations =====
    
    def add_experience(self, agent_id: str, content: str,
                       importance: float = 0.5) -> None:
        """Add experience to agent memory."""
        self.memory_provider.add_experience(
            agent_id, content, importance, self._current_year
        )
    
    def update_after_flood(self, agent_id: str, damage: float) -> None:
        """Update memory after flood."""
        self.memory_provider.update_after_flood(
            agent_id, damage, self._current_year
        )
    
    def update_after_decision(self, agent_id: str, decision: str) -> None:
        """Update memory after decision."""
        self.memory_provider.update_after_decision(
            agent_id, decision, self._current_year
        )
    
    def consolidate_memories(self) -> Dict[str, int]:
        """Consolidate all memories (for cognitive memory)."""
        return self.memory_provider.consolidate_all()
