"""
Theory Registry — manages registered BehavioralTheory implementations.
"""

from typing import Dict, Optional

from validation.theories.base import BehavioralTheory


class TheoryRegistry:
    """Registry for BehavioralTheory implementations."""

    def __init__(self):
        self._theories: Dict[str, BehavioralTheory] = {}
        self._default: Optional[str] = None

    def register(self, theory: BehavioralTheory) -> None:
        """Register a theory implementation."""
        self._theories[theory.name] = theory
        if self._default is None:
            self._default = theory.name

    def get(self, name: str) -> Optional[BehavioralTheory]:
        """Get a registered theory by name."""
        return self._theories.get(name)

    def set_default(self, name: str) -> None:
        """Set the default theory."""
        if name not in self._theories:
            raise ValueError(f"Theory '{name}' not registered. Available: {list(self._theories.keys())}")
        self._default = name

    @property
    def default(self) -> Optional[BehavioralTheory]:
        """Get the default theory."""
        if self._default is None:
            return None
        return self._theories.get(self._default)

    @property
    def names(self):
        return list(self._theories.keys())


# =============================================================================
# Module-level default registry
# =============================================================================

_default_registry = None


def get_default_registry() -> TheoryRegistry:
    """Get or create the default registry with PMT pre-registered."""
    global _default_registry
    if _default_registry is None:
        from validation.theories.pmt import PMTTheory
        _default_registry = TheoryRegistry()
        _default_registry.register(PMTTheory())
    return _default_registry
