"""
Adaptive Retrieval Engine - Dynamic weight adjustment based on arousal.

Implements System 1/2 aware retrieval that adjusts weights dynamically
based on the current cognitive state (arousal level).

Reference: Task-040 Memory Module Optimization
"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from .store import UnifiedMemoryStore
    from .unified_engine import UnifiedMemoryItem


class AdaptiveRetrievalEngine:
    """
    Adaptive retrieval engine with arousal-based weight adjustment.

    Implements dual-mode retrieval inspired by System 1/2 theory:
    - System 1 (Low arousal): Recency-biased, fast, automatic
    - System 2 (High arousal): Importance-weighted, deliberate

    Features:
    - Dynamic weight interpolation based on arousal level
    - Contextual boosting via tag matching
    - Working/Long-term memory fusion
    - Full scoring trace for explainability

    Args:
        base_weights: Default retrieval weights
            - recency: Weight for time-based recency [0-1]
            - importance: Weight for importance score [0-1]
            - context: Weight for contextual boosting [0-1]
        system1_weights: Weights for low-arousal (routine) mode
        system2_weights: Weights for high-arousal (crisis) mode

    Example:
        >>> engine = AdaptiveRetrievalEngine()
        >>> memories = engine.retrieve(
        ...     store=memory_store,
        ...     agent_id="agent_1",
        ...     top_k=5,
        ...     arousal=0.8  # High arousal -> importance-biased
        ... )
    """

    def __init__(
        self,
        base_weights: Optional[Dict[str, float]] = None,
        system1_weights: Optional[Dict[str, float]] = None,
        system2_weights: Optional[Dict[str, float]] = None,
    ):
        # Default base weights (balanced)
        self.base_weights = base_weights or {
            "recency": 0.3,
            "importance": 0.5,
            "context": 0.2,
        }

        # System 1: Recency-focused (routine, automatic)
        self.system1_weights = system1_weights or {
            "recency": 0.6,
            "importance": 0.3,
            "context": 0.1,
        }

        # System 2: Importance-focused (crisis, deliberate)
        self.system2_weights = system2_weights or {
            "recency": 0.2,
            "importance": 0.6,
            "context": 0.2,
        }

        # Trace data
        self._last_trace: Optional[Dict[str, Any]] = None

    def _compute_recency_score(
        self,
        item: "UnifiedMemoryItem",
        current_time: float
    ) -> float:
        """
        Compute recency score for a memory item.

        Uses exponential decay: score = e^(-age * decay_factor)

        Args:
            item: Memory item
            current_time: Current timestamp

        Returns:
            Recency score [0-1]
        """
        age = current_time - item.timestamp
        # Decay over 1 hour to ~0.37, 3 hours to ~0.05
        decay_factor = 1.0 / 3600  # per second
        score = 2.71828 ** (-age * decay_factor)
        return max(0.0, min(1.0, score))

    def _compute_contextual_boost(
        self,
        item: "UnifiedMemoryItem",
        boosters: Optional[Dict[str, float]]
    ) -> float:
        """
        Compute contextual boost based on tag matching.

        Args:
            item: Memory item
            boosters: Dict mapping tags to boost values

        Returns:
            Contextual boost score [0-1]
        """
        if not boosters:
            return 0.0

        boost = 0.0
        for tag in item.tags:
            if tag in boosters:
                boost += boosters[tag]

        return min(1.0, boost)

    def _interpolate_weights(
        self,
        arousal: float,
        threshold: float
    ) -> Dict[str, float]:
        """
        Interpolate between System 1 and System 2 weights.

        Uses smooth interpolation based on distance from threshold.

        Args:
            arousal: Current arousal level [0-1]
            threshold: Arousal threshold for System 2 activation

        Returns:
            Interpolated weight dict
        """
        if arousal <= threshold * 0.5:
            # Deep System 1: use pure System 1 weights
            return self.system1_weights.copy()
        elif arousal >= threshold:
            # System 2: use pure System 2 weights
            return self.system2_weights.copy()
        else:
            # Transition zone: interpolate
            t = (arousal - threshold * 0.5) / (threshold * 0.5)  # [0, 1]
            weights = {}
            for key in self.base_weights:
                w1 = self.system1_weights.get(key, self.base_weights[key])
                w2 = self.system2_weights.get(key, self.base_weights[key])
                weights[key] = w1 * (1 - t) + w2 * t
            return weights

    def retrieve(
        self,
        store: "UnifiedMemoryStore",
        agent_id: str,
        top_k: int = 5,
        arousal: float = 0.0,
        arousal_threshold: float = 0.5,
        contextual_boosters: Optional[Dict[str, float]] = None,
        include_scoring: bool = False,
    ) -> List["UnifiedMemoryItem"]:
        """
        Retrieve memories with adaptive weight adjustment.

        Args:
            store: UnifiedMemoryStore instance
            agent_id: Agent to retrieve for
            top_k: Number of memories to retrieve
            arousal: Current arousal level [0-1]
            arousal_threshold: Threshold for System 2 activation
            contextual_boosters: Tag-based score boosters
            include_scoring: Include scoring details in trace

        Returns:
            List of top-k UnifiedMemoryItem objects
        """
        # Get all memories
        all_items = store.get_all(agent_id)

        if not all_items:
            self._last_trace = {
                "agent_id": agent_id,
                "arousal": arousal,
                "system": "SYSTEM_1",
                "weights": self.system1_weights,
                "items_scored": 0,
                "items_returned": 0,
            }
            return []

        # Determine weights based on arousal
        weights = self._interpolate_weights(arousal, arousal_threshold)
        system = "SYSTEM_2" if arousal > arousal_threshold else "SYSTEM_1"

        current_time = time.time()
        scored_items = []

        # Score each item
        for item in all_items:
            recency_score = self._compute_recency_score(item, current_time)
            importance_score = item.importance
            context_score = self._compute_contextual_boost(item, contextual_boosters)

            # Weighted combination
            final_score = (
                weights["recency"] * recency_score +
                weights["importance"] * importance_score +
                weights["context"] * context_score
            )

            scored_items.append({
                "item": item,
                "final_score": final_score,
                "recency": recency_score,
                "importance": importance_score,
                "context": context_score,
            })

        # Sort by score descending
        scored_items.sort(key=lambda x: x["final_score"], reverse=True)

        # Take top-k
        top_items = scored_items[:top_k]

        # Build trace
        self._last_trace = {
            "agent_id": agent_id,
            "arousal": arousal,
            "arousal_threshold": arousal_threshold,
            "system": system,
            "weights": weights,
            "items_scored": len(all_items),
            "items_returned": len(top_items),
        }

        if include_scoring:
            self._last_trace["scoring_details"] = [
                {
                    "content": s["item"].content[:50] + "...",
                    "final": s["final_score"],
                    "recency": s["recency"],
                    "importance": s["importance"],
                    "context": s["context"],
                }
                for s in top_items
            ]

        return [s["item"] for s in top_items]

    def get_trace(self) -> Optional[Dict[str, Any]]:
        """Get trace from last retrieval operation."""
        return self._last_trace

    def explain_last(self) -> str:
        """Human-readable explanation of last retrieval."""
        if not self._last_trace:
            return "No retrieval performed yet."

        t = self._last_trace
        lines = [
            f"Agent: {t['agent_id']}",
            f"System: {t['system']} (arousal={t['arousal']:.2f})",
            f"Weights: R={t['weights']['recency']:.2f}, "
            f"I={t['weights']['importance']:.2f}, "
            f"C={t['weights']['context']:.2f}",
            f"Scored: {t['items_scored']}, Returned: {t['items_returned']}",
        ]

        if "scoring_details" in t:
            lines.append("Top items:")
            for i, s in enumerate(t["scoring_details"]):
                lines.append(
                    f"  #{i+1} [{s['final']:.2f}] \"{s['content']}\" "
                    f"(R={s['recency']:.2f}, I={s['importance']:.2f})"
                )

        return "\n".join(lines)
