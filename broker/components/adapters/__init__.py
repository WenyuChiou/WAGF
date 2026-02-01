"""Domain-specific reflection adapters — backward-compat re-exports.

Canonical locations:
    FloodAdapter      → examples.governed_flood.adapters.flood_adapter
    IrrigationAdapter → examples.irrigation_abm.adapters.irrigation_adapter

The DomainReflectionAdapter protocol lives in
``broker.components.domain_adapters`` (framework-level interface).
"""

from examples.governed_flood.adapters.flood_adapter import FloodAdapter
from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter

__all__ = ["FloodAdapter", "IrrigationAdapter"]
