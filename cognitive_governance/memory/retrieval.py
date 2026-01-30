"""
Adaptive Retrieval Engine - Dynamic weight adjustment based on arousal.

Implements System 1/2 aware retrieval that adjusts weights dynamically
based on the current cognitive state (arousal level).

Memory capacity constraints are based on cognitive science literature:
- Miller, G. A. (1956). The magical number seven, plus or minus two.
  Psychological Review, 63(2), 81-97. DOI: 10.1037/h0043158
- Cowan, N. (2001). The magical number 4 in short-term memory.
  Behavioral and Brain Sciences, 24(1), 87-114. DOI: 10.1017/S0140525X01003922

Reference: Task-040 Memory Module Optimization, Task-050E Cognitive Constraints
"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING
import time
import numpy as np  # Explicitly import numpy

from .config.cognitive_constraints import CognitiveConstraints, MILLER_STANDARD

if TYPE_CHECKING:
    from .store import UnifiedMemoryStore
    from .unified_engine import UnifiedMemoryItem
    # Assume EmbeddingProvider protocol is defined elsewhere or imported if needed here.
    # For this modification, we'll rely on the protocol definition being accessible.
    from cognitive_governance.memory.embeddings import EmbeddingProvider


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
    - Embedding-based semantic similarity

    Args:
        base_weights: Default retrieval weights
            - recency: Weight for time-based recency [0-1]
            - importance: Weight for importance score [0-1]
            - context: Weight for contextual boosting [0-1]
            - semantic: Weight for semantic similarity [0-1] (New)
        system1_weights: Weights for low-arousal (routine) mode
        system2_weights: Weights for high-arousal (crisis) mode
        embedding_provider: Optional provider for generating text embeddings.

    Example:
        >>> # Assuming SentenceTransformerProvider is available and imported
        >>> # from cognitive_governance.memory.embeddings import SentenceTransformerProvider
        >>> # provider = SentenceTransformerProvider()
        >>> # engine = AdaptiveRetrievalEngine(embedding_provider=provider)
        >>> # memories = engine.retrieve(
        >>> #     store=memory_store,
        >>> #     agent_id="agent_1",
        >>> #     top_k=5,
        >>> #     arousal=0.8,  # High arousal -> importance-biased
        >>> #     query="What about flood damage?"
        >>> # )
    """

    def __init__(
        self,
        base_weights: Optional[Dict[str, float]] = None,
        system1_weights: Optional[Dict[str, float]] = None,
        system2_weights: Optional[Dict[str, float]] = None,
        embedding_provider: Optional["EmbeddingProvider"] = None,
        cognitive_constraints: Optional[CognitiveConstraints] = None,
    ):
        # Default base weights (balanced)
        self.base_weights = base_weights or {
            "recency": 0.3,
            "importance": 0.5,
            "context": 0.2,
            "semantic": 0.0  # Default semantic weight to 0 if not provided
        }

        # System 1: Recency-focused (routine, automatic)
        self.system1_weights = system1_weights or {
            "recency": 0.6,
            "importance": 0.3,
            "context": 0.1,
            "semantic": 0.0,
        }

        # System 2: Importance-focused (crisis, deliberate)
        self.system2_weights = system2_weights or {
            "recency": 0.2,
            "importance": 0.6,
            "context": 0.2,
            "semantic": 0.1,  # New weight for semantic in System 2
        }

        # Ensure semantic weight key exists in all weight dictionaries, defaulting to 0 if absent
        for weights_dict in [self.base_weights, self.system1_weights, self.system2_weights]:
            weights_dict.setdefault("semantic", 0.0)

        # Store embedding provider
        self.embedding_provider = embedding_provider

        # Cognitive constraints for memory capacity (Task-050E)
        # Based on Miller (1956) and Cowan (2001)
        self.constraints = cognitive_constraints or MILLER_STANDARD

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
        score = np.exp(-age * decay_factor) # Using np.exp for consistency with numpy
        return max(0.0, min(1.0, float(score))) # Ensure float output and clamp to [0, 1]

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
        # Define transition factor 't' based on arousal level relative to threshold
        # t=0 means pure System 1, t=1 means pure System 2
        if arousal <= threshold * 0.5:
            t = 0.0
        elif arousal >= threshold:
            t = 1.0
        else:
            # Linear interpolation within the transition zone
            t = (arousal - threshold * 0.5) / (threshold * 0.5)

        weights = {}
        # Interpolate each weight dimension
        for key in self.base_weights: # Ensure all base keys are covered
            w1 = self.system1_weights.get(key, self.base_weights[key])
            w2 = self.system2_weights.get(key, self.base_weights[key])
            weights[key] = w1 * (1 - t) + w2 * t
        return weights

    def _compute_semantic_score(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Computes cosine similarity between two embeddings.

        Args:
            embedding1: First embedding (numpy array)
            embedding2: Second embedding (numpy array)

        Returns:
            Cosine similarity score [0-1], or 0.0 if computation is not possible.
        """
        if embedding1 is None or embedding2 is None or embedding1.shape != embedding2.shape:
            return 0.0  # Cannot compute similarity if embeddings are missing or mismatched

        # Ensure numpy arrays for calculation
        emb1 = np.array(embedding1)
        emb2 = np.array(embedding2)

        # Cosine similarity formula
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0 or norm2 == 0:
            return 0.0  # Avoid division by zero

        similarity = dot_product / (norm1 * norm2)
        # Cosine similarity can range from -1 to 1. For retrieval, we often map it to [0, 1].
        # Clamping to [0, 1] assumes embeddings are non-negative or we're interested in positive similarity.
        return max(0.0, min(1.0, float(similarity)))

    def retrieve(
        self,
        store: "UnifiedMemoryStore",
        agent_id: str,
        top_k: Optional[int] = None,
        arousal: float = 0.0,
        arousal_threshold: float = 0.5,
        contextual_boosters: Optional[Dict[str, float]] = None,
        include_scoring: bool = False,
        query: Optional[str] = None,  # Query text for semantic search
    ) -> List["UnifiedMemoryItem"]:
        """
        Retrieve memories with adaptive weight adjustment, incorporating semantic similarity.

        Memory count is determined by cognitive constraints based on arousal level
        (Miller 1956, Cowan 2001) unless explicitly specified via top_k.

        Args:
            store: UnifiedMemoryStore instance
            agent_id: Agent to retrieve for
            top_k: Number of memories to retrieve. If None, uses cognitive constraints
                   based on arousal level (System 1: ~5, System 2: ~7)
            arousal: Current arousal level [0-1]
            arousal_threshold: Threshold for System 2 activation
            contextual_boosters: Tag-based score boosters
            include_scoring: Include scoring details in trace
            query: The text query for semantic similarity search.

        Returns:
            List of top-k UnifiedMemoryItem objects

        Note:
            When top_k is None, memory count is determined by CognitiveConstraints:
            - System 1 (low arousal): 5 memories (Cowan 2001: 4±1)
            - System 2 (high arousal): 7 memories (Miller 1956: 7±2)
        """
        # Determine memory count from cognitive constraints if not specified
        if top_k is None:
            top_k = self.constraints.get_memory_count(arousal, arousal_threshold)

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

        # Embed query if provided and provider exists
        query_embedding = None
        if query and self.embedding_provider:
            try:
                # Assume embed returns List[List[float]] or List[np.ndarray]
                query_embedding_list = self.embedding_provider.embed([query])
                if query_embedding_list:
                    query_embedding = np.array(query_embedding_list[0]) # Convert to numpy array
            except Exception as e:
                print(f"Warning: Failed to embed query '{query[:30]}...': {e}")
                # Continue without semantic score if embedding fails

        # Score each item
        for item in all_items:
            recency_score = self._compute_recency_score(item, current_time)
            importance_score = item.importance
            context_score = self._compute_contextual_boost(item, contextual_boosters)

            semantic_score = 0.0
            # Check if item has embedding and provider/query embedding is available
            # Assume item.embedding is in a format compatible with np.ndarray or convertible
            if query_embedding is not None and hasattr(item, 'embedding') and item.embedding is not None:
                try:
                    # Ensure item.embedding is a numpy array for calculation
                    item_embedding_np = np.array(item.embedding)
                    semantic_score = self._compute_semantic_score(query_embedding, item_embedding_np)
                except Exception as e:
                    print(f"Warning: Failed to compute semantic score for item {item.id}: {e}")
                    semantic_score = 0.0 # Default to 0 if computation fails

            # Weighted combination
            final_score = (
                weights["recency"] * recency_score +
                weights["importance"] * importance_score +
                weights["context"] * context_score +
                weights.get("semantic", 0.0) * semantic_score # Added semantic score with weight
            )
            # Normalization might be needed if weights sum > 1.0, or normalize scores independently.
            # For now, assume weights are balanced or user intends raw weighted sum.

            scored_items.append({
                "item": item,
                "final_score": final_score,
                "recency": recency_score,
                "importance": importance_score,
                "context": context_score,
                "semantic": semantic_score # Store semantic score for trace
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
            "cognitive_constraints": {
                "system1_count": self.constraints.system1_memory_count,
                "system2_count": self.constraints.system2_memory_count,
                "top_k_used": top_k,
            },
        }

        if include_scoring:
            self._last_trace["scoring_details"] = [
                {
                    "content": s["item"].content[:50] + "...",
                    "final": s["final_score"],
                    "recency": s["recency"],
                    "importance": s["importance"],
                    "context": s["context"],
                    "semantic": s["semantic"], # Include semantic score in trace details
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
        ]
        if 'semantic' in t['weights'] and t['weights']['semantic'] > 0:
            lines[-1] += f", S={t['weights']['semantic']:.2f}"

        # Cognitive constraints info (Task-050E)
        if 'cognitive_constraints' in t:
            cc = t['cognitive_constraints']
            lines.append(
                f"Capacity: S1={cc['system1_count']}, S2={cc['system2_count']}, "
                f"used={cc['top_k_used']} (Miller/Cowan)"
            )

        lines.append(f"Scored: {t['items_scored']}, Returned: {t['items_returned']}")

        if "scoring_details" in t:
            lines.append("Top items:")
            for i, s in enumerate(t["scoring_details"]):
                recency_info = f"R={s['recency']:.2f}"
                importance_info = f"I={s['importance']:.2f}"
                context_info = f"C={s['context']:.2f}"
                semantic_info = f"S={s['semantic']:.2f}" if s['semantic'] > 0 else ""
                
                lines.append(
                    f"  #{i+1} [{s['final']:.2f}] \"{s['content']}\" "
                    f"({recency_info}, {importance_info}, {context_info}{', '+semantic_info if semantic_info else ''})"
                )

        return "\n".join(lines)
