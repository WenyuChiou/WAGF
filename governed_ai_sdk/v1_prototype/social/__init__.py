"""
Social observation abstraction module.

Provides domain-agnostic patterns for modeling peer influence
across different research domains (flood, finance, education, health).
"""
from .observer import SocialObserver, ObservationResult
from .registry import ObserverRegistry
from .observers import FloodObserver, FinanceObserver, EducationObserver

__all__ = [
    "SocialObserver",
    "ObservationResult",
    "ObserverRegistry",
    "FloodObserver",
    "FinanceObserver",
    "EducationObserver",
]
