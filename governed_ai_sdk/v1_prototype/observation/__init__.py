"""
Observation abstractions for agent perception.

Provides domain-agnostic patterns for:
- Environment observation (sensing external world state)
- Social observation (perceiving neighbors) - see social/ module

This module focuses on WHAT can be observed, not HOW it's presented
to the agent (that's the context builder's job in the broker).
"""
from .environment import EnvironmentObserver, EnvironmentObservation
from .registry import EnvironmentObserverRegistry
from .observers import (
    FloodEnvironmentObserver,
    FinanceEnvironmentObserver,
    EducationEnvironmentObserver,
    HealthEnvironmentObserver,
)

__all__ = [
    # Base classes
    "EnvironmentObserver",
    "EnvironmentObservation",
    "EnvironmentObserverRegistry",
    # Domain implementations
    "FloodEnvironmentObserver",
    "FinanceEnvironmentObserver",
    "EducationEnvironmentObserver",
    "HealthEnvironmentObserver",
]
