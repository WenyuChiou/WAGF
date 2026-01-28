"""
Unified Memory Store - Working/Long-term memory with consolidation.

Provides a two-tier memory storage system with automatic consolidation
of important memories from working to long-term storage.

Reference: Task-040 Memory Module Optimization
"""

from typing import Dict, List, Optional, Any
import time

from .unified_engine import UnifiedMemoryItem


class UnifiedMemoryStore:
    """
    Unified memory store with working/long-term separation.

    Implements a two-tier memory system inspired by cognitive science:
    - Working Memory: Recent, actively processed memories (limited capacity)
    - Long-term Memory: Consolidated important memories (persistent)

    Features:
    - Automatic capacity management for working memory
    - Importance-based consolidation to long-term
    - Configurable thresholds and capacity
    - Full agent isolation

    Args:
        working_capacity: Max items in working memory per agent (default: 10)
        consolidation_threshold: Importance threshold for consolidation (default: 0.6)
        auto_consolidate_overflow: Auto-consolidate when working overflows (default: True)

    Example:
        >>> store = UnifiedMemoryStore(working_capacity=10)
        >>> store.add(memory_item)
        >>> store.consolidate("agent_1")  # Move important items to long-term
        >>> items = store.get_all("agent_1")
    """

    def __init__(
        self,
        working_capacity: int = 10,
        consolidation_threshold: float = 0.6,
        auto_consolidate_overflow: bool = True,
    ):
        self.working_capacity = working_capacity
        self.consolidation_threshold = consolidation_threshold
        self.auto_consolidate_overflow = auto_consolidate_overflow

        # Memory stores: agent_id -> List[UnifiedMemoryItem]
        self._working: Dict[str, List[UnifiedMemoryItem]] = {}
        self._longterm: Dict[str, List[UnifiedMemoryItem]] = {}

    @property
    def working(self) -> Dict[str, List[UnifiedMemoryItem]]:
        """Access working memory store."""
        return self._working

    @property
    def longterm(self) -> Dict[str, List[UnifiedMemoryItem]]:
        """Access long-term memory store."""
        return self._longterm

    def add(self, item: UnifiedMemoryItem) -> None:
        """
        Add memory item to working memory.

        Args:
            item: UnifiedMemoryItem to add

        Note:
            If working memory exceeds capacity and auto_consolidate_overflow
            is enabled, oldest items will be checked for consolidation.
        """
        agent_id = item.agent_id

        # Initialize if needed
        if agent_id not in self._working:
            self._working[agent_id] = []

        # Add to working memory
        self._working[agent_id].append(item)

        # Handle overflow
        if len(self._working[agent_id]) > self.working_capacity:
            if self.auto_consolidate_overflow:
                self._handle_overflow(agent_id)
            else:
                # Simple FIFO removal
                self._working[agent_id] = self._working[agent_id][-self.working_capacity:]

    def _handle_overflow(self, agent_id: str) -> None:
        """
        Handle working memory overflow by consolidating or discarding.

        Oldest items above capacity are either:
        1. Consolidated to long-term (if importance >= threshold)
        2. Discarded (if importance < threshold)
        """
        working = self._working.get(agent_id, [])
        overflow_count = len(working) - self.working_capacity

        if overflow_count <= 0:
            return

        # Process oldest items first
        to_remove = working[:overflow_count]
        self._working[agent_id] = working[overflow_count:]

        # Consolidate important ones
        for item in to_remove:
            if item.importance >= self.consolidation_threshold:
                if agent_id not in self._longterm:
                    self._longterm[agent_id] = []
                self._longterm[agent_id].append(item)

    def consolidate(
        self,
        agent_id: str,
        threshold: Optional[float] = None
    ) -> int:
        """
        Consolidate important memories from working to long-term.

        Args:
            agent_id: Agent to consolidate
            threshold: Override consolidation threshold (optional)

        Returns:
            Number of memories consolidated
        """
        thresh = threshold if threshold is not None else self.consolidation_threshold
        working = self._working.get(agent_id, [])

        if not working:
            return 0

        # Find items to consolidate
        to_consolidate = [item for item in working if item.importance >= thresh]

        if not to_consolidate:
            return 0

        # Initialize long-term if needed
        if agent_id not in self._longterm:
            self._longterm[agent_id] = []

        # Move to long-term
        for item in to_consolidate:
            self._longterm[agent_id].append(item)
            working.remove(item)

        return len(to_consolidate)

    def get_all(self, agent_id: str) -> List[UnifiedMemoryItem]:
        """Get all memories (working + long-term) for an agent."""
        working = self._working.get(agent_id, [])
        longterm = self._longterm.get(agent_id, [])
        return working + longterm

    def get_working(self, agent_id: str) -> List[UnifiedMemoryItem]:
        """Get only working memories for an agent."""
        return self._working.get(agent_id, [])

    def get_longterm(self, agent_id: str) -> List[UnifiedMemoryItem]:
        """Get only long-term memories for an agent."""
        return self._longterm.get(agent_id, [])

    def clear(self, agent_id: str) -> None:
        """Clear all memories for an agent."""
        if agent_id in self._working:
            del self._working[agent_id]
        if agent_id in self._longterm:
            del self._longterm[agent_id]

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
            strategy: "importance" (forget low importance) or "age" (forget old)
            threshold: Threshold for forgetting

        Returns:
            Number of memories forgotten
        """
        forgotten = 0

        if strategy == "importance":
            # Forget low importance from working
            working = self._working.get(agent_id, [])
            remaining = [m for m in working if m.importance >= threshold]
            forgotten += len(working) - len(remaining)
            self._working[agent_id] = remaining

            # Forget from long-term too
            longterm = self._longterm.get(agent_id, [])
            remaining_lt = [m for m in longterm if m.importance >= threshold]
            forgotten += len(longterm) - len(remaining_lt)
            self._longterm[agent_id] = remaining_lt

        elif strategy == "age":
            # Forget old memories (threshold = max age in seconds)
            current_time = time.time()
            max_age = threshold * 86400  # threshold in days

            working = self._working.get(agent_id, [])
            remaining = [m for m in working if (current_time - m.timestamp) < max_age]
            forgotten += len(working) - len(remaining)
            self._working[agent_id] = remaining

            longterm = self._longterm.get(agent_id, [])
            remaining_lt = [m for m in longterm if (current_time - m.timestamp) < max_age]
            forgotten += len(longterm) - len(remaining_lt)
            self._longterm[agent_id] = remaining_lt

        return forgotten

    def get_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get memory statistics for an agent."""
        working = self._working.get(agent_id, [])
        longterm = self._longterm.get(agent_id, [])

        return {
            "working_count": len(working),
            "longterm_count": len(longterm),
            "total_count": len(working) + len(longterm),
            "working_capacity": self.working_capacity,
            "avg_working_importance": (
                sum(m.importance for m in working) / len(working)
                if working else 0.0
            ),
            "avg_longterm_importance": (
                sum(m.importance for m in longterm) / len(longterm)
                if longterm else 0.0
            ),
        }

    def reset(self) -> None:
        """Reset all memory stores."""
        self._working.clear()
        self._longterm.clear()
