"""
Broker Interfaces Package

Generic protocols and interfaces for dependency injection.
Allows domain-specific implementations to be provided without
coupling the broker framework to specific application domains.
"""
from .enrichment import (
    PositionData,
    PositionEnricher,
    ValueData,
    ValueEnricher,
)

__all__ = [
    "PositionData",
    "PositionEnricher",
    "ValueData",
    "ValueEnricher",
]
