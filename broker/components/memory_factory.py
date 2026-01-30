"""
Shared Memory Engine Factory for SA/MA.

Provides a unified creation API for all supported memory engines:
- window, importance, humancentric, hierarchical, universal, unified
"""
from typing import Optional, Dict, Any

from broker.components.memory_engine import MemoryEngine
from broker.components.engines.window_engine import WindowMemoryEngine
from broker.components.engines.importance_engine import ImportanceMemoryEngine
from broker.components.engines.humancentric_engine import HumanCentricMemoryEngine
from broker.components.engines.hierarchical_engine import HierarchicalMemoryEngine
from broker.components.universal_memory import UniversalCognitiveEngine
from cognitive_governance.memory.unified_engine import UnifiedCognitiveEngine as UnifiedEngine


def _normalize_engine_type(engine_type: str) -> str:
    normalized = engine_type.lower()
    if normalized == "human_centric":
        return "humancentric"
    return normalized


def create_memory_engine(
    engine_type: str,
    config: Optional[Dict[str, Any]] = None,
    scorer: Optional[Any] = None,
    **kwargs
) -> MemoryEngine:
    """
    Factory function for creating memory engines.

    Args:
        engine_type: One of "window", "importance", "humancentric",
                     "hierarchical", "universal", "unified"
        config: Engine-specific configuration dict
        scorer: Optional memory scorer
        **kwargs: Additional engine parameters

    Returns:
        Configured MemoryEngine instance
    """
    config = config or {}
    engine_type = _normalize_engine_type(engine_type)

    if engine_type == "window":
        engine = WindowMemoryEngine(
            window_size=config.get("window_size", 5),
        )
    elif engine_type == "importance":
        engine = ImportanceMemoryEngine(
            window_size=config.get("window_size", 5),
        )
    elif engine_type == "humancentric":
        engine = HumanCentricMemoryEngine(
            window_size=config.get("window_size", 5),
            top_k_significant=config.get("top_k_significant", 2),
            consolidation_prob=config.get("consolidation_probability", 0.7),
            decay_rate=config.get("decay_rate", 0.1),
        )
    elif engine_type == "hierarchical":
        engine = HierarchicalMemoryEngine(
            window_size=config.get("window_size", 5),
            semantic_top_k=config.get("top_k_significant", 3),
        )
    elif engine_type == "universal":
        engine = UniversalCognitiveEngine(
            stimulus_key=config.get("stimulus_key"),
            sensory_cortex=config.get("sensory_cortex"),
            arousal_threshold=config.get("arousal_threshold", 1.0),
            ema_alpha=config.get("ema_alpha", 0.3),
            window_size=config.get("window_size", 3),
            top_k_significant=config.get("top_k_significant", 2),
            consolidation_prob=config.get("consolidation_probability", 0.7),
            consolidation_threshold=config.get("consolidation_threshold", 0.6),
            decay_rate=config.get("decay_rate", 0.1),
            ranking_mode=config.get("ranking_mode", "weighted"),
            **kwargs,
        )
    elif engine_type == "unified":
        # v5 UnifiedEngine requires explicit strategy creation
        from cognitive_governance.memory.strategies import (
            EMASurpriseStrategy,
            SymbolicSurpriseStrategy,
            HybridSurpriseStrategy,
        )

        # Extract memory config from nested structure if needed
        mem_cfg = config
        if "global_config" in config and "memory" in config.get("global_config", {}):
            mem_cfg = config["global_config"]["memory"]
        elif "memory" in config:
            mem_cfg = config["memory"]

        # Get strategy parameters (ignoring unsupported kwargs like window_size, ranking_mode)
        strategy_type = mem_cfg.get("surprise_strategy", "ema")
        ema_alpha = mem_cfg.get("ema_alpha", 0.3)
        stimulus_key = mem_cfg.get("stimulus_key", "flood_depth")

        if strategy_type == "symbolic":
            strategy = SymbolicSurpriseStrategy(default_sensor_key=stimulus_key)
        elif strategy_type == "hybrid":
            strategy = HybridSurpriseStrategy(
                ema_weight=0.6,
                symbolic_weight=0.4,
                ema_stimulus_key=stimulus_key,
                ema_alpha=ema_alpha,
            )
        else:  # default: ema
            strategy = EMASurpriseStrategy(stimulus_key=stimulus_key, alpha=ema_alpha)

        engine = UnifiedEngine(
            surprise_strategy=strategy,
            arousal_threshold=mem_cfg.get("arousal_threshold", 0.5),
            emotional_weights=mem_cfg.get("emotional_weights"),
            source_weights=mem_cfg.get("source_weights"),
            decay_rate=mem_cfg.get("decay_rate", 0.1),
            seed=mem_cfg.get("seed", kwargs.get("seed", 42)),
        )
    else:
        raise ValueError(f"Unknown engine type: {engine_type}")

    if scorer is not None and hasattr(engine, "scorer"):
        engine.scorer = scorer

    return engine
