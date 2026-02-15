"""
HallucinationChecker Protocol — domain-agnostic hallucination detection.

Any domain can implement this protocol to define what constitutes
a physically impossible or logically invalid agent action.
"""

from typing import Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class HallucinationChecker(Protocol):
    """Protocol for domain-specific hallucination detection."""

    @property
    def name(self) -> str:
        """Short identifier (e.g., 'flood_physical', 'irrigation_physical')."""
        ...

    def is_hallucination(self, trace: Dict) -> bool:
        """Check if trace contains a hallucination (impossible action)."""
        ...


class NullHallucinationChecker:
    """No-op checker for domains without hallucination rules."""

    @property
    def name(self) -> str:
        return "null"

    def is_hallucination(self, trace: Dict) -> bool:
        return False
