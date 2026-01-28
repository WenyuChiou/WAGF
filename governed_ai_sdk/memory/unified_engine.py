"""
Unified Cognitive Engine (v5) - Consolidated Memory Architecture.

This module provides the core data structures and main engine for the
unified memory system, consolidating v2/v3/v4 features.

Key classes:
- UnifiedMemoryItem: Standardized memory data structure
- UnifiedCognitiveEngine: Main engine with pluggable strategies

Reference: Task-040 Memory Module Optimization
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class UnifiedMemoryItem:
    """
    Unified memory item structure combining features from v2/v3/v4.

    This dataclass provides a standardized representation for memories
    that includes:
    - Core content and timing (from v1)
    - Importance scoring with emotion/source weights (from v2)
    - Surprise metrics for System 1/2 switching (from v3/v4)
    - Flexible metadata for domain-specific extensions

    Attributes:
        content: The actual memory content (text)
        timestamp: Unix timestamp of when memory was created
        emotion: Emotional valence ("major", "minor", "neutral")
        source: Source category ("personal", "social", "policy")
        base_importance: Initial importance score [0-1]
        surprise_score: Computed surprise at time of encoding (from v3 EMA)
        novelty_score: Frequency-based novelty (from v4 symbolic)
        agent_id: ID of the agent this memory belongs to
        year: Simulation year (for temporal filtering)
        tags: List of semantic tags for retrieval boosting
        metadata: Additional domain-specific data
    """
    content: str
    timestamp: float = field(default_factory=time.time)

    # Importance scoring (from v2 HumanCentric)
    emotion: str = "neutral"  # major/minor/neutral
    source: str = "personal"  # personal/social/policy
    base_importance: float = 0.5

    # Surprise metrics (from v3/v4)
    surprise_score: float = 0.0
    novelty_score: float = 0.0

    # Metadata
    agent_id: str = ""
    year: int = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Computed importance (can be updated by decay)
    _current_importance: Optional[float] = field(default=None, repr=False)

    @property
    def importance(self) -> float:
        """Get current importance (with decay applied if set)."""
        if self._current_importance is not None:
            return self._current_importance
        return self.base_importance

    @importance.setter
    def importance(self, value: float):
        """Set current importance (after decay)."""
        self._current_importance = max(0.0, min(1.0, value))

    def compute_importance(
        self,
        emotional_weights: Optional[Dict[str, float]] = None,
        source_weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Compute importance score using v2-style weighting.

        Args:
            emotional_weights: Weight per emotion type
            source_weights: Weight per source type

        Returns:
            Weighted importance score [0-1]
        """
        e_weights = emotional_weights or {
            "major": 1.0,
            "minor": 0.5,
            "neutral": 0.3
        }
        s_weights = source_weights or {
            "personal": 1.0,
            "social": 0.7,
            "policy": 0.5
        }

        emotion_factor = e_weights.get(self.emotion, 0.3)
        source_factor = s_weights.get(self.source, 0.5)

        # Combine: base * emotion * source, clamped to [0, 1]
        computed = self.base_importance * emotion_factor * source_factor
        return max(0.0, min(1.0, computed))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "content": self.content,
            "timestamp": self.timestamp,
            "emotion": self.emotion,
            "source": self.source,
            "base_importance": self.base_importance,
            "surprise_score": self.surprise_score,
            "novelty_score": self.novelty_score,
            "agent_id": self.agent_id,
            "year": self.year,
            "tags": self.tags,
            "metadata": self.metadata,
            "importance": self.importance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedMemoryItem":
        """Create from dictionary (deserialization)."""
        item = cls(
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            emotion=data.get("emotion", "neutral"),
            source=data.get("source", "personal"),
            base_importance=data.get("base_importance", 0.5),
            surprise_score=data.get("surprise_score", 0.0),
            novelty_score=data.get("novelty_score", 0.0),
            agent_id=data.get("agent_id", ""),
            year=data.get("year", 0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
        if "importance" in data:
            item._current_importance = data["importance"]
        return item


class UnifiedCognitiveEngine:
    """
    Unified Cognitive Engine (v5) - Main memory engine.

    This engine consolidates the best features from previous versions:
    - v1: Simple sliding window (baseline, always available)
    - v2: Emotion × Source importance weighting
    - v3: EMA-based surprise detection and System 1/2 switching
    - v4: Frequency-based symbolic novelty detection

    Key features:
    - Pluggable SurpriseStrategy for flexible arousal computation
    - Working/Long-term memory separation with consolidation
    - Adaptive retrieval that adjusts weights based on arousal
    - Full trace capture for XAI-ABM integration

    Args:
        surprise_strategy: Strategy for computing surprise/arousal
        store: Memory store instance (or creates default)
        retrieval_engine: Retrieval engine instance (or creates default)
        arousal_threshold: Threshold for System 1/2 switching
        emotional_weights: Weight per emotion type for importance
        source_weights: Weight per source type for importance
        decay_rate: Rate of importance decay over time
        auto_consolidate: Whether to auto-consolidate on add

    Example:
        >>> from governed_ai_sdk.memory import (
        ...     UnifiedCognitiveEngine,
        ...     EMASurpriseStrategy,
        ... )
        >>> strategy = EMASurpriseStrategy(alpha=0.3, stimulus_key="flood_depth")
        >>> engine = UnifiedCognitiveEngine(surprise_strategy=strategy)
        >>> engine.add_memory("agent_1", "Got flooded with $10,000 damage")
        >>> memories = engine.retrieve("agent_1", top_k=5)
    """

    def __init__(
        self,
        surprise_strategy: Optional["SurpriseStrategy"] = None,
        store: Optional["UnifiedMemoryStore"] = None,
        retrieval_engine: Optional["AdaptiveRetrievalEngine"] = None,
        arousal_threshold: Optional[float] = None,
        emotional_weights: Optional[Dict[str, float]] = None,
        source_weights: Optional[Dict[str, float]] = None,
        decay_rate: Optional[float] = None,
        auto_consolidate: bool = True,
        seed: Optional[int] = None,
        global_config: Optional["GlobalMemoryConfig"] = None,
        domain_config: Optional["DomainMemoryConfig"] = None,
    ):
        # Import here to avoid circular dependency
        from .store import UnifiedMemoryStore
        from .retrieval import AdaptiveRetrievalEngine
        from .config import GlobalMemoryConfig, DomainMemoryConfig
        from .strategies import EMASurpriseStrategy, SymbolicSurpriseStrategy

        # Core components (lazy-initialized if not provided)
        self._strategy = surprise_strategy
        self._store = store or UnifiedMemoryStore()
        self._retrieval = retrieval_engine or AdaptiveRetrievalEngine()

        # Configuration
        self.global_config = global_config or GlobalMemoryConfig()
        self.domain_config = domain_config or DomainMemoryConfig()

        self.arousal_threshold = (
            arousal_threshold
            if arousal_threshold is not None
            else self.global_config.arousal_threshold
        )
        self.emotional_weights = emotional_weights or {
            "major": 1.0,
            "minor": 0.5,
            "neutral": 0.3
        }
        self.source_weights = source_weights or {
            "personal": 1.0,
            "social": 0.7,
            "policy": 0.5
        }
        self.decay_rate = (
            decay_rate
            if decay_rate is not None
            else self.global_config.decay_rate
        )
        self.auto_consolidate = auto_consolidate

        # Default strategy selection from config (if not provided)
        if self._strategy is None:
            if self.domain_config.sensory_cortex:
                self._strategy = SymbolicSurpriseStrategy(
                    sensors=self.domain_config.sensory_cortex
                )
            elif self.domain_config.stimulus_key:
                self._strategy = EMASurpriseStrategy(
                    stimulus_key=self.domain_config.stimulus_key,
                    alpha=self.global_config.ema_alpha,
                )

        # State tracking
        self.current_system = "SYSTEM_1"
        self.last_surprise = 0.0

        # Random state for reproducibility
        self._seed = seed
        if seed is not None:
            import random
            random.seed(seed)

    @property
    def working(self) -> Dict[str, List[UnifiedMemoryItem]]:
        """Access working memory store."""
        return self._store.working

    @property
    def longterm(self) -> Dict[str, List[UnifiedMemoryItem]]:
        """Access long-term memory store."""
        return self._store.longterm

    @property
    def surprise_strategy(self) -> Optional["SurpriseStrategy"]:
        """Access current surprise strategy."""
        return self._strategy

    def add_memory(
        self,
        agent_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UnifiedMemoryItem:
        """
        Add a memory for an agent.

        Args:
            agent_id: The agent's unique identifier
            content: Memory content string
            metadata: Optional metadata dict with keys like:
                     - emotion: "major"/"minor"/"neutral"
                     - source: "personal"/"social"/"policy"
                     - significance: float importance hint
                     - year: simulation year
                     - tags: list of semantic tags

        Returns:
            The created UnifiedMemoryItem
        """
        meta = metadata or {}

        # Extract structured fields from metadata
        emotion = meta.pop("emotion", "neutral")
        source = meta.pop("source", "personal")
        significance = meta.pop("significance", 0.5)
        year = meta.pop("year", 0)
        tags = meta.pop("tags", [])

        # Compute surprise if strategy is available
        surprise_score = 0.0
        novelty_score = 0.0
        if self._strategy and "world_state" in meta:
            world_state = meta.pop("world_state")
            surprise_score = self._strategy.update(world_state)
            # Some strategies also provide novelty
            trace = self._strategy.get_trace()
            if trace and "is_novel" in trace:
                novelty_score = 1.0 if trace["is_novel"] else 0.0

        # Create memory item
        item = UnifiedMemoryItem(
            content=content,
            timestamp=time.time(),
            emotion=emotion,
            source=source,
            base_importance=significance,
            surprise_score=surprise_score,
            novelty_score=novelty_score,
            agent_id=agent_id,
            year=year,
            tags=tags,
            metadata=meta,
        )

        # Compute final importance
        item._current_importance = item.compute_importance(
            self.emotional_weights,
            self.source_weights
        )

        # Boost importance if high surprise
        if surprise_score > self.arousal_threshold:
            item._current_importance = min(1.0, item.importance * 1.5)

        # Add to store
        self._store.add(item)

        # Auto-consolidate if enabled
        if self.auto_consolidate:
            self._store.consolidate(agent_id)

        logger.debug(
            f"[Memory] Added for {agent_id}: {content[:50]}... "
            f"(importance={item.importance:.2f}, surprise={surprise_score:.2f})"
        )

        return item

    def add_memory_for_agent(
        self,
        agent: Any,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UnifiedMemoryItem:
        """
        Add memory with agent context.

        Extracts agent_id from agent object and delegates to add_memory.

        Args:
            agent: Agent object with 'id' or 'unique_id' attribute
            content: Memory content string
            metadata: Optional metadata dict

        Returns:
            The created UnifiedMemoryItem
        """
        agent_id = str(getattr(agent, 'id', getattr(agent, 'unique_id', 'unknown')))
        return self.add_memory(agent_id, content, metadata)

    def retrieve(
        self,
        agent: Union[str, Any],
        query: Optional[str] = None,
        top_k: int = 5,
        world_state: Optional[Dict[str, Any]] = None,
        contextual_boosters: Optional[Dict[str, float]] = None,
        **kwargs
    ) -> List[str]:
        """
        Retrieve memories with adaptive System 1/2 switching.

        Args:
            agent: Agent object or agent_id string
            query: Optional semantic query (for future embedding support)
            top_k: Number of memories to retrieve
            world_state: Current environment state for surprise calculation
            contextual_boosters: Tag-based score boosters

        Returns:
            List of memory content strings
        """
        # Extract agent_id
        if isinstance(agent, str):
            agent_id = agent
        else:
            agent_id = str(getattr(agent, 'id', getattr(agent, 'unique_id', 'unknown')))

        # Compute surprise if strategy and world_state available
        # Use update() to adapt expectations over time (normalization)
        arousal = 0.0
        if self._strategy and world_state:
            self.last_surprise = self._strategy.update(world_state)
            arousal = self.last_surprise

        # Determine system
        self.current_system = "SYSTEM_2" if arousal > self.arousal_threshold else "SYSTEM_1"

        logger.debug(
            f"[Cognitive] {self.current_system} activated "
            f"(surprise={arousal:.2f}, threshold={self.arousal_threshold})"
        )

        # Delegate to retrieval engine
        items = self._retrieval.retrieve(
            store=self._store,
            agent_id=agent_id,
            top_k=top_k,
            arousal=arousal,
            arousal_threshold=self.arousal_threshold,
            contextual_boosters=contextual_boosters,
        )

        return [item.content for item in items]

    def retrieve_items(
        self,
        agent: Union[str, Any],
        top_k: int = 5,
        world_state: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[UnifiedMemoryItem]:
        """
        Retrieve full memory items (not just content strings).

        Args:
            agent: Agent object or agent_id string
            top_k: Number of memories to retrieve
            world_state: Current environment state

        Returns:
            List of UnifiedMemoryItem objects
        """
        if isinstance(agent, str):
            agent_id = agent
        else:
            agent_id = str(getattr(agent, 'id', getattr(agent, 'unique_id', 'unknown')))

        arousal = 0.0
        if self._strategy and world_state:
            arousal = self._strategy.get_surprise(world_state)

        return self._retrieval.retrieve(
            store=self._store,
            agent_id=agent_id,
            top_k=top_k,
            arousal=arousal,
            arousal_threshold=self.arousal_threshold,
        )

    def clear(self, agent_id: str) -> None:
        """Clear all memories for an agent."""
        self._store.clear(agent_id)
        logger.debug(f"[Memory] Cleared memories for {agent_id}")

    def forget(
        self,
        agent_id: str,
        strategy: str = "importance",
        threshold: float = 0.2
    ) -> int:
        """
        Forget memories below threshold.

        Args:
            agent_id: Agent identifier
            strategy: "importance" or "age"
            threshold: Threshold below which to forget

        Returns:
            Number of memories forgotten
        """
        return self._store.forget(agent_id, strategy, threshold)

    def get_cognitive_state(self) -> Dict[str, Any]:
        """Get current cognitive state for debugging."""
        state = {
            "system": self.current_system,
            "surprise": self.last_surprise,
            "arousal_threshold": self.arousal_threshold,
        }
        if self._strategy:
            trace = self._strategy.get_trace()
            if trace:
                state["strategy_trace"] = trace
        return state

    def apply_decay(self, agent_id: str) -> None:
        """Apply time-based decay to importance scores."""
        current_time = time.time()

        for item in self._store.working.get(agent_id, []):
            age = current_time - item.timestamp
            decay_factor = 1.0 / (1.0 + self.decay_rate * age / 86400)  # Per day
            item.importance = item.base_importance * decay_factor

        for item in self._store.longterm.get(agent_id, []):
            age = current_time - item.timestamp
            decay_factor = 1.0 / (1.0 + self.decay_rate * age / 86400)
            item.importance = item.base_importance * decay_factor

    def reset(self) -> None:
        """Reset engine state for new simulation."""
        self._store.reset()
        if self._strategy:
            self._strategy.reset()
        self.current_system = "SYSTEM_1"
        self.last_surprise = 0.0
