"""
Plugin registry for memory engines.

Allows external users to register custom memory engines without
modifying framework source code.

Usage:
    from broker.components.memory_registry import MemoryEngineRegistry

    # Register a custom engine
    MemoryEngineRegistry.register("my_engine", MyCustomMemoryEngine)

    # Create from registry
    engine = MemoryEngineRegistry.create("my_engine", {"window_size": 10})
"""
import logging
from typing import Dict, Type, Any, Optional, Callable

from broker.components.memory_engine import MemoryEngine

logger = logging.getLogger(__name__)


class MemoryEngineRegistry:
    """Central registry for memory engine types.

    Built-in engines are auto-registered at module load.
    External users can register additional engines before creating
    their experiment.
    """
    _engines: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str, engine_factory: Callable, *,
                 override: bool = False) -> None:
        """Register a memory engine type.

        Args:
            name: Engine type name (case-insensitive).
            engine_factory: Callable that accepts a config dict and returns
                a MemoryEngine instance. Can be a class or a factory function.
            override: If True, allow overwriting existing registrations.
        """
        key = name.lower()
        if key in cls._engines and not override:
            logger.warning(
                f"[MemoryRegistry] Engine '{name}' already registered. "
                f"Use override=True to replace."
            )
            return
        cls._engines[key] = engine_factory
        logger.debug(f"[MemoryRegistry] Registered engine: {name}")

    @classmethod
    def create(cls, engine_type: str, config: Optional[Dict[str, Any]] = None
               ) -> MemoryEngine:
        """Create a memory engine from the registry.

        Args:
            engine_type: Registered engine type name (case-insensitive).
            config: Engine-specific configuration dict.

        Returns:
            Configured MemoryEngine instance.

        Raises:
            ValueError: If engine_type is not registered.
        """
        key = engine_type.lower()
        if key == "human_centric":
            key = "humancentric"  # normalize legacy alias

        factory = cls._engines.get(key)
        if factory is None:
            available = sorted(cls._engines.keys())
            raise ValueError(
                f"Unknown memory engine type: '{engine_type}'. "
                f"Available engines: {', '.join(available)}. "
                f"Register custom engines with MemoryEngineRegistry.register()."
            )
        return factory(**(config or {}))

    @classmethod
    def list_engines(cls) -> list:
        """Return sorted list of registered engine type names."""
        return sorted(cls._engines.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if an engine type is registered."""
        return name.lower() in cls._engines


# ---------------------------------------------------------------------------
# Auto-register built-in engines
# ---------------------------------------------------------------------------

def _register_builtins():
    """Register all built-in memory engines."""
    from broker.components.engines.window_engine import WindowMemoryEngine
    from broker.components.engines.importance_engine import ImportanceMemoryEngine
    from broker.components.engines.humancentric_engine import HumanCentricMemoryEngine
    from broker.components.engines.hierarchical_engine import HierarchicalMemoryEngine

    def _window_factory(window_size: int = 5, **kwargs):
        return WindowMemoryEngine(window_size=window_size)

    def _importance_factory(window_size: int = 5, **kwargs):
        logger.warning(
            "ImportanceMemoryEngine is deprecated. "
            "Use engine_type='humancentric' instead."
        )
        return ImportanceMemoryEngine(window_size=window_size)

    def _humancentric_factory(window_size: int = 5, top_k_significant: int = 2,
                              consolidation_probability: float = 0.7,
                              decay_rate: float = 0.1, **kwargs):
        return HumanCentricMemoryEngine(
            window_size=window_size,
            top_k_significant=top_k_significant,
            consolidation_prob=consolidation_probability,
            decay_rate=decay_rate,
        )

    def _hierarchical_factory(window_size: int = 5, top_k_significant: int = 3,
                              **kwargs):
        logger.warning(
            "HierarchicalMemoryEngine is deprecated. "
            "Use engine_type='humancentric' instead."
        )
        return HierarchicalMemoryEngine(
            window_size=window_size,
            semantic_top_k=top_k_significant,
        )

    MemoryEngineRegistry.register("window", _window_factory)
    MemoryEngineRegistry.register("importance", _importance_factory)
    MemoryEngineRegistry.register("humancentric", _humancentric_factory)
    MemoryEngineRegistry.register("hierarchical", _hierarchical_factory)

    # Advanced engines — optional imports (may not be installed)
    try:
        from broker.components.universal_memory import UniversalCognitiveEngine

        def _universal_factory(**kwargs):
            return UniversalCognitiveEngine(**kwargs)

        MemoryEngineRegistry.register("universal", _universal_factory)
    except ImportError:
        pass

    try:
        from cognitive_governance.memory.unified_engine import UnifiedCognitiveEngine as UnifiedEngine
        from cognitive_governance.memory.strategies import (
            EMASurpriseStrategy,
            SymbolicSurpriseStrategy,
            HybridSurpriseStrategy,
        )

        def _unified_factory(**config):
            mem_cfg = config
            if "global_config" in config and "memory" in config.get("global_config", {}):
                mem_cfg = config["global_config"]["memory"]
            elif "memory" in config:
                mem_cfg = config["memory"]

            strategy_type = mem_cfg.get("surprise_strategy", "ema")
            stimulus_key = mem_cfg.get("stimulus_key")
            ema_alpha = mem_cfg.get("ema_alpha", 0.3)

            if strategy_type == "symbolic":
                strategy = SymbolicSurpriseStrategy(default_sensor_key=stimulus_key)
            elif strategy_type == "hybrid":
                strategy = HybridSurpriseStrategy(
                    ema_weight=0.6, symbolic_weight=0.4,
                    ema_stimulus_key=stimulus_key, ema_alpha=ema_alpha,
                )
            else:
                strategy = EMASurpriseStrategy(stimulus_key=stimulus_key, alpha=ema_alpha)

            return UnifiedEngine(
                surprise_strategy=strategy,
                arousal_threshold=mem_cfg.get("arousal_threshold", 0.5),
                emotional_weights=mem_cfg.get("emotional_weights"),
                source_weights=mem_cfg.get("source_weights"),
                decay_rate=mem_cfg.get("decay_rate", 0.1),
                seed=mem_cfg.get("seed", config.get("seed", 42)),
            )

        MemoryEngineRegistry.register("unified", _unified_factory)
    except ImportError:
        pass


_register_builtins()
