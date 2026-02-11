"""Domain-specific reflection adapters — backward-compat re-exports.

Canonical locations:
    FloodAdapter      → examples.governed_flood.adapters.flood_adapter
    IrrigationAdapter → examples.irrigation_abm.adapters.irrigation_adapter

The DomainReflectionAdapter protocol lives in
``broker.components.domain_adapters`` (framework-level interface).
"""

try:
    from examples.governed_flood.adapters.flood_adapter import FloodAdapter
except ImportError:
    FloodAdapter = None  # Domain adapter not installed

try:
    from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter
except ImportError:
    IrrigationAdapter = None  # Domain adapter not installed

__all__ = ["FloodAdapter", "IrrigationAdapter"]
