"""
Shared Memory Engine Factory for SA/MA.

Provides a unified creation API for all supported memory engines.
Delegates to MemoryEngineRegistry for engine resolution.

Supported engines:
- humancentric (production, metadata-bearing — Invariant 1 conformant)
- window (production, CONTENT-ONLY — returns List[str]; documented Invariant-1
  exemption, see broker/INVARIANTS.md. Use humancentric for any
  emotion/importance/source-dependent path.)
- universal, unified (advanced research)
- importance, hierarchical (deprecated — use humancentric instead)

External users can register custom engines:
    from .registry import MemoryEngineRegistry
    MemoryEngineRegistry.register("my_engine", MyEngineClass)
"""
import logging
from numbers import Real
from typing import Optional, Dict, Any

from .engine import MemoryEngine
from .registry import MemoryEngineRegistry

logger = logging.getLogger(__name__)

# Fractions read by memory engines and reflection configuration. Defaults stay
# with their consumers; only explicitly supplied configuration is validated.
# arousal_threshold is not here: the universal engine compares it with an
# unbounded surprise score (default 2.0; 99.0 keeps every year in System 1).
FRACTION_PARAMETERS = frozenset({
    "decay_rate", "consolidation_prob", "consolidation_probability",
    "consolidation_threshold", "forgetting_threshold",
    "W_recency", "W_importance", "W_context", "importance_boost", "base_importance",
})


def validate_fraction(name: str, value: Any) -> None:
    """Refuse nonnumeric values and fractions outside the closed unit interval."""
    if isinstance(value, bool) or not isinstance(value, Real) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a real number in [0, 1], got {value!r}")


def _pack_memory_defaults(pack: Any) -> Dict[str, Any]:
    """Derive engine defaults from a DomainPack's MemoryPack hooks (Wave 3 / 3-4).

    Pre-3-4 the hooks (``retrieval_weights`` / ``emotional_keywords``) were
    declared on the Protocol but had ZERO factory consumers — a domain using
    the generic construction path silently got the generic defaults (the
    2026-06-09 architecture-review declaration-consumption gap, memory-cognition
    P1). Adopted shapes:

    * ``retrieval_weights() -> {"W_recency": x, "W_importance": y, "W_context": z}``
      — adopted only when ALL three keys are present (a partial declaration is
      a pack bug, not a tuning choice).
    * ``emotional_keywords() -> {keyword: emotion}`` — INVERTED into the
      engine's ``{emotion: [keywords]}`` lexicon shape.

    ``importance_profiles()`` is deliberately NOT threaded here: importance
    scoring is consumed by the reflection pipeline via
    ``pack.compute_importance``, not by engine construction.
    Hook failures degrade to {} (a broken pack must not block construction).
    """
    out: Dict[str, Any] = {}
    try:
        rw = pack.retrieval_weights() or {}
        if all(k in rw for k in ("W_recency", "W_importance", "W_context")):
            out.update({k: float(rw[k]) for k in ("W_recency", "W_importance", "W_context")})
    except Exception as exc:
        logger.debug(f"[MemoryFactory] pack.retrieval_weights() skipped: {exc}")
    try:
        ek = pack.emotional_keywords() or {}
        if ek:
            inverted: Dict[str, list] = {}
            for keyword, emotion in ek.items():
                inverted.setdefault(str(emotion), []).append(str(keyword))
            out["emotion_keywords"] = inverted
    except Exception as exc:
        logger.debug(f"[MemoryFactory] pack.emotional_keywords() skipped: {exc}")
    return out


def create_memory_engine(
    engine_type: str,
    config: Optional[Dict[str, Any]] = None,
    scorer: Optional[Any] = None,
    pack: Optional[Any] = None,
    **kwargs
) -> MemoryEngine:
    """
    Factory function for creating memory engines.

    Args:
        engine_type: Registered engine type name (e.g., "window", "humancentric").
        config: Engine-specific configuration dict.
        scorer: Optional memory scorer to inject.
        pack: Optional DomainPack whose MemoryPack hooks (retrieval_weights /
              emotional_keywords) supply engine DEFAULTS. Precedence:
              explicit config/kwargs > pack hooks > engine built-ins — a YAML
              tuning value always wins over the pack's domain default
              (Wave 3 / 3-4; omitting ``pack`` reproduces pre-3-4 behavior
              exactly, so frozen callers are untouched).
        **kwargs: Additional engine parameters (merged into config for
                  backward compatibility with the legacy API).

    Returns:
        Configured MemoryEngine instance.

    Raises:
        ValueError: If engine_type is not registered.
    """
    pack_defaults = _pack_memory_defaults(pack) if pack is not None else {}
    config = {**pack_defaults, **(config or {}), **kwargs}
    for name in FRACTION_PARAMETERS & config.keys():
        validate_fraction(name, config[name])
    if isinstance(config.get("retrieval"), dict) and "min_score" in config["retrieval"]:
        validate_fraction("retrieval.min_score", config["retrieval"]["min_score"])
    engine = MemoryEngineRegistry.create(engine_type, config)

    if scorer is not None and hasattr(engine, "scorer"):
        engine.scorer = scorer

    return engine
