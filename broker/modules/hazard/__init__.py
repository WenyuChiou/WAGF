"""
Hazard module for flood depth data and vulnerability calculations.

This module provides:
- PRBGridLoader: Load ESRI ASCII Grid flood depth data
- DepthSampler: Sample flood depths based on flood experience
- VulnerabilityCalculator: Depth-damage calculations
- RCVGenerator: Generate replacement cost values
"""

from .prb_loader import PRBGridLoader, GridMetadata
from .depth_sampler import DepthSampler, DepthCategory
from .vulnerability import VulnerabilityCalculator, DamageResult
from .rcv_generator import RCVGenerator

__all__ = [
    "PRBGridLoader",
    "GridMetadata",
    "DepthSampler",
    "DepthCategory",
    "VulnerabilityCalculator",
    "DamageResult",
    "RCVGenerator",
]
