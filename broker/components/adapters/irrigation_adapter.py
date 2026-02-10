"""Backward-compat re-export — canonical location is examples.irrigation_abm.adapters."""
try:
    from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter
except ImportError:
    IrrigationAdapter = None  # Domain adapter not installed

__all__ = ["IrrigationAdapter"]
