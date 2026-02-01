"""Domain-specific reflection adapters.

Each adapter implements the DomainReflectionAdapter protocol and provides
domain-tuned importance profiles, emotional keywords, and retrieval weights.

Available adapters:
    FloodAdapter        — flood-risk household decisions
    IrrigationAdapter   — water-resource irrigation decisions
"""

from broker.components.adapters.flood_adapter import FloodAdapter
from broker.components.adapters.irrigation_adapter import IrrigationAdapter

__all__ = ["FloodAdapter", "IrrigationAdapter"]
