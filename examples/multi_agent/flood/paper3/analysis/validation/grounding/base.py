"""
GroundingStrategy Protocol — domain-agnostic construct grounding.

Grounding derives expected construct levels from objective state variables,
breaking the circularity of evaluating LLM-assigned labels against the LLM's
own outputs (CACR circularity).
"""

from typing import Dict, Protocol, runtime_checkable


@runtime_checkable
class GroundingStrategy(Protocol):
    """Protocol for domain-specific construct grounding."""

    @property
    def name(self) -> str:
        """Short identifier (e.g., 'flood_pmt', 'irrigation_wsa')."""
        ...

    def ground_constructs(self, state_before: Dict) -> Dict[str, str]:
        """Derive expected construct levels from objective state.

        Args:
            state_before: Agent state dictionary with domain-specific fields.

        Returns:
            Dict mapping construct dimension to expected ordinal level.
            E.g., {"TP": "VH", "CP": "L"} for PMT flood domain.
        """
        ...
