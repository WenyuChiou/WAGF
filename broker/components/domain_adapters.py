"""
Domain Reflection Adapters — Plugin interface for domain-specific reflection & memory.

Decouples the ReflectionEngine from domain-specific concepts (flood_count, drought_severity,
etc.) by defining a Protocol that any domain can implement. The core engine delegates
importance computation, emotional classification, and retrieval weight configuration
to the active adapter.

Architecture:
    ReflectionEngine (core)
        └── uses DomainReflectionAdapter (protocol)
                ├── FloodAdapter        (examples/single_agent)
                ├── IrrigationAdapter   (examples/irrigation_abm)
                └── <user-defined>      (new domains)

Usage:
    from broker.components.domain_adapters import DomainReflectionAdapter
    from examples.governed_flood.adapters import FloodAdapter

    adapter = FloodAdapter()
    engine = ReflectionEngine(adapter=adapter)
"""

from __future__ import annotations

from typing import Dict, Any, Protocol, runtime_checkable


@runtime_checkable
class DomainReflectionAdapter(Protocol):
    """Protocol for domain-specific reflection behaviour.

    Implementations provide:
    - importance_profiles: named float values for event categories
    - emotional_keywords: mapping from keyword categories to emotion labels
    - retrieval_weights: W_recency / W_importance / W_context for memory retrieval
    - compute_importance(): context → dynamic importance score
    - classify_emotion(): decision + context → emotion label for memory encoding
    """

    importance_profiles: Dict[str, float]
    emotional_keywords: Dict[str, str]
    retrieval_weights: Dict[str, float]

    def compute_importance(
        self, context: Dict[str, Any], base: float = 0.9
    ) -> float:
        """Compute dynamic importance from domain-specific agent context.

        Args:
            context: Dict of domain-specific fields (e.g. flood_count, supply_ratio).
            base: Default importance when no domain rule matches.

        Returns:
            Importance score in [0.0, 1.0].
        """
        ...

    def classify_emotion(
        self, decision: str, context: Dict[str, Any]
    ) -> str:
        """Classify emotional valence for memory encoding.

        Args:
            decision: The skill/action the agent just took.
            context: Domain-specific agent context.

        Returns:
            Emotion label string (e.g. "major", "minor", "critical").
        """
        ...
