"""Backward-compat re-export — canonical location is examples.governed_flood.adapters."""
try:
    from examples.governed_flood.adapters.flood_adapter import FloodAdapter
except ImportError:
    FloodAdapter = None  # Domain adapter not installed

__all__ = ["FloodAdapter"]
