"""
Memory Engine Factory.

PLUGGABLE: To add a new memory system:
1. Import or define your engine class
2. Add a case to create_memory_engine()
3. Register any SDK scorers if needed

No other files need to change.

Supported engines:
- window: Simple sliding window (v1 baseline)
- importance: Keyword-based importance scoring
- humancentric: Emotion × Source weighting (v2, deprecated)
- hierarchical: Core/Episodic/Semantic tiers
- universal: EMA surprise engine (v3)
- unified: New v5 unified cognitive engine (recommended)
"""
from typing import Dict, Any, Optional
from broker.components.memory_engine import (
    WindowMemoryEngine,
    ImportanceMemoryEngine,
    HumanCentricMemoryEngine,
    HierarchicalMemoryEngine,
    create_memory_engine as broker_create_engine
)

# v5 Unified Memory imports
from governed_ai_sdk.memory import (
    UnifiedCognitiveEngine,
    EMASurpriseStrategy,
    SymbolicSurpriseStrategy,
    HybridSurpriseStrategy,
)


class DecisionFilteredMemoryEngine:
    """
    Proxy memory engine that filters out decision memories.
    Maintains parity with baseline experiment.
    """

    def __init__(self, inner):
        self.inner = inner

    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        if "Decided to:" in content:
            return
        return self.inner.add_memory(agent_id, content, metadata)

    def add_memory_for_agent(self, agent, content: str, metadata: Optional[Dict[str, Any]] = None):
        if "Decided to:" in content:
            return
        if hasattr(self.inner, 'add_memory_for_agent'):
            return self.inner.add_memory_for_agent(agent, content, metadata)
        return self.inner.add_memory(agent.id, content, metadata)

    def retrieve(self, agent, query: Optional[str] = None, top_k: int = 3, **kwargs):
        return self.inner.retrieve(agent, query=query, top_k=top_k, **kwargs)

    def clear(self, agent_id: str):
        return self.inner.clear(agent_id)


def create_memory_engine(
    engine_type: str,
    config: Dict[str, Any],
    window_size: int = 5,
    ranking_mode: str = "legacy",
    filter_decisions: bool = True
):
    """
    Factory function for memory engines.

    Args:
        engine_type: One of "window", "importance", "humancentric", "hierarchical", "universal"
        config: YAML config dict (agent_types.yaml content)
        window_size: Memory window size
        ranking_mode: "legacy" or "weighted" for humancentric
        filter_decisions: Whether to filter "Decided to:" memories

    Returns:
        Memory engine instance

    To add a new memory system:
        1. Add a new elif branch here
        2. Import/define your engine class
        3. That's it - no other files need changes
    """
    global_cfg = config.get('global_config', {})
    household_mem = config.get('household', {}).get('memory', {})
    shared_mem = config.get('shared', {}).get('memory_config', {})

    # Merge configs
    final_mem_cfg = {**shared_mem, **household_mem}
    retrieval_w = final_mem_cfg.get('retrieval_weights', {})
    global_mem = global_cfg.get('memory', {})

    engine = None

    if engine_type == "window":
        engine = WindowMemoryEngine(window_size=window_size)
        print(f" Using WindowMemoryEngine (sliding window, size={window_size})")

    elif engine_type == "importance":
        flood_categories = {
            "critical": ["flood", "flooded", "damage", "severe", "destroyed"],
            "high": ["grant", "elevation", "insurance", "protected"],
            "medium": ["neighbor", "relocated", "observed", "pct%"]
        }
        engine = ImportanceMemoryEngine(
            window_size=window_size,
            top_k_significant=global_mem.get('top_k_significant', 2),
            decay_rate=global_mem.get('decay_rate', 0.1),
            categories=flood_categories
        )
        print(f" Using ImportanceMemoryEngine (active retrieval with flood-specific keywords)")

    elif engine_type == "humancentric":
        engine = HumanCentricMemoryEngine(
            window_size=window_size,
            top_k_significant=global_mem.get('top_k_significant', 2),
            consolidation_prob=global_mem.get('consolidation_probability', 0.7),
            consolidation_threshold=global_mem.get('consolidation_threshold', 0.6),
            decay_rate=global_mem.get('decay_rate', 0.1),
            emotional_weights=final_mem_cfg.get("emotional_weights"),
            source_weights=final_mem_cfg.get("source_weights"),
            W_recency=retrieval_w.get("recency", 0.3),
            W_importance=retrieval_w.get("importance", 0.5),
            W_context=retrieval_w.get("context", 0.2),
            ranking_mode=ranking_mode,
            seed=42
        )
        print(f" Using HumanCentricMemoryEngine (emotional encoding, window={window_size})")

    elif engine_type == "hierarchical":
        engine = HierarchicalMemoryEngine(
            window_size=window_size,
            semantic_top_k=3
        )
        print(f" Using HierarchicalMemoryEngine (Tiered: Core, Episodic, Semantic)")

    elif engine_type == "universal":
        engine = broker_create_engine(
            engine_type="universal",
            window_size=window_size,
            top_k_significant=global_mem.get('top_k_significant', 2),
            consolidation_prob=global_mem.get('consolidation_probability', 0.7),
            consolidation_threshold=global_mem.get('consolidation_threshold', 0.6),
            decay_rate=global_mem.get('decay_rate', 0.1),
            emotional_weights=final_mem_cfg.get("emotional_weights"),
            source_weights=final_mem_cfg.get("source_weights"),
            W_recency=retrieval_w.get("recency", 0.3),
            W_importance=retrieval_w.get("importance", 0.5),
            W_context=retrieval_w.get("context", 0.2),
            ranking_mode="dynamic",
            arousal_threshold=final_mem_cfg.get("arousal_threshold", 0.5),
            ema_alpha=final_mem_cfg.get("ema_alpha", 0.3),
            seed=42
        )
        print(f" Using UniversalCognitiveEngine (v3 Surprise Engine, window={window_size})")

    elif engine_type == "unified":
        # v5 Unified Cognitive Engine - recommended for new experiments
        strategy_type = final_mem_cfg.get("surprise_strategy", "ema")
        arousal_threshold = final_mem_cfg.get("arousal_threshold", 0.5)
        ema_alpha = final_mem_cfg.get("ema_alpha", 0.3)

        # Create appropriate surprise strategy
        if strategy_type == "symbolic":
            strategy = SymbolicSurpriseStrategy(default_sensor_key="flood_depth")
        elif strategy_type == "hybrid":
            strategy = HybridSurpriseStrategy(
                ema_weight=0.6,
                symbolic_weight=0.4,
                ema_stimulus_key="flood_depth",
                ema_alpha=ema_alpha
            )
        else:  # default: ema
            strategy = EMASurpriseStrategy(
                stimulus_key="flood_depth",
                alpha=ema_alpha
            )

        engine = UnifiedCognitiveEngine(
            surprise_strategy=strategy,
            arousal_threshold=arousal_threshold,
            emotional_weights=final_mem_cfg.get("emotional_weights"),
            source_weights=final_mem_cfg.get("source_weights"),
            decay_rate=global_mem.get('decay_rate', 0.1),
            seed=42
        )
        print(f" Using UnifiedCognitiveEngine (v5, strategy={strategy_type}, threshold={arousal_threshold})")

    else:
        # Default fallback
        engine = WindowMemoryEngine(window_size=window_size)
        print(f" Using WindowMemoryEngine (default fallback)")

    # Apply decision filter if requested
    if filter_decisions:
        engine = DecisionFilteredMemoryEngine(engine)

    return engine


# =============================================================================
# EXTENSION POINT: Add new memory systems here
# =============================================================================
#
# Example: Adding a new "semantic" memory engine
#
# 1. Import or define:
#    from my_package import SemanticMemoryEngine
#
# 2. Add case in create_memory_engine():
#    elif engine_type == "semantic":
#        engine = SemanticMemoryEngine(
#            embedding_model=config.get("embedding_model", "all-MiniLM-L6-v2"),
#            ...
#        )
#
# 3. Done! Use with: --memory-engine semantic
