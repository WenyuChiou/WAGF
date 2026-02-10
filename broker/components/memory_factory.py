"""
Shared Memory Engine Factory for SA/MA.

Provides a unified creation API for all supported memory engines.
Delegates to MemoryEngineRegistry for engine resolution.

Supported engines:
- window, humancentric (production)
- universal, unified (advanced research)
- importance, hierarchical (deprecated — use humancentric instead)

External users can register custom engines:
    from broker.components.memory_registry import MemoryEngineRegistry
    MemoryEngineRegistry.register("my_engine", MyEngineClass)
"""
import logging
from typing import Optional, Dict, Any

from broker.components.memory_engine import MemoryEngine
from broker.components.memory_registry import MemoryEngineRegistry

logger = logging.getLogger(__name__)


def create_memory_engine(
    engine_type: str,
    config: Optional[Dict[str, Any]] = None,
    scorer: Optional[Any] = None,
    **kwargs
) -> MemoryEngine:
    """
    Factory function for creating memory engines.

    Args:
        engine_type: Registered engine type name (e.g., "window", "humancentric").
        config: Engine-specific configuration dict.
        scorer: Optional memory scorer to inject.
        **kwargs: Additional engine parameters (merged into config for
                  backward compatibility with the legacy API).

    Returns:
        Configured MemoryEngine instance.

    Raises:
        ValueError: If engine_type is not registered.
    """
    config = {**(config or {}), **kwargs}
    engine = MemoryEngineRegistry.create(engine_type, config)

    if scorer is not None and hasattr(engine, "scorer"):
        engine.scorer = scorer

    return engine
