"""Event generator implementations.

Provides domain-specific event generators that implement EventGeneratorProtocol:

- FloodEventGenerator: Simple flood events (fixed/probabilistic/historical)
- HazardEventGenerator: Wrapper for HazardModule (PRB grid, per-agent depth)
- ImpactEventGenerator: Financial impact from hazard events
- PolicyEventGenerator: Institutional policy changes
"""
from .flood import FloodEventGenerator, FloodConfig
from .hazard import HazardEventGenerator, HazardEventConfig
from .impact import ImpactEventGenerator, ImpactEventConfig
from .policy import PolicyEventGenerator, PolicyEventConfig

__all__ = [
    # Simple flood (SA-style)
    "FloodEventGenerator",
    "FloodConfig",
    # Hazard adapter (MA-style)
    "HazardEventGenerator",
    "HazardEventConfig",
    # Impact calculator
    "ImpactEventGenerator",
    "ImpactEventConfig",
    # Policy events
    "PolicyEventGenerator",
    "PolicyEventConfig",
]
