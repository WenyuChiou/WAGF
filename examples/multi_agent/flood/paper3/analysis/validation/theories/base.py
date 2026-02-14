"""
BehavioralTheory Protocol — extensible interface for construct-action theories.

Two paradigms supported:
  - Paradigm A (Construct-Action Mapping): PMT, TPB, HBM → lookup table
  - Paradigm B (Frame-Conditional): Prospect Theory, Nudge → tendency matching

Any theory implementing this protocol can be plugged into compute_l1_metrics().
"""

from typing import Dict, List, Protocol, runtime_checkable


@runtime_checkable
class BehavioralTheory(Protocol):
    """Protocol for behavioral theory implementations."""

    @property
    def name(self) -> str:
        """Short identifier (e.g., 'pmt', 'tpb', 'irrigation_wsa')."""
        ...

    @property
    def dimensions(self) -> List[str]:
        """Construct dimension names (e.g., ['TP', 'CP'] for PMT)."""
        ...

    @property
    def agent_types(self) -> List[str]:
        """Supported agent types (e.g., ['owner', 'renter'])."""
        ...

    def get_coherent_actions(
        self, construct_levels: Dict[str, str], agent_type: str
    ) -> List[str]:
        """Return list of coherent actions for given construct levels and agent type.

        Args:
            construct_levels: e.g., {"TP": "VH", "CP": "H"}
            agent_type: e.g., "owner" or "renter"

        Returns:
            List of valid action names, or empty list if unknown combination.
        """
        ...

    def extract_constructs(self, trace: Dict) -> Dict[str, str]:
        """Extract construct levels from a decision trace.

        Args:
            trace: Decision trace dictionary.

        Returns:
            Dict mapping dimension name to level string,
            e.g., {"TP": "VH", "CP": "H"}.
            Missing dimensions should map to "UNKNOWN".
        """
        ...

    def is_sensible_action(
        self, construct_levels: Dict[str, str], action: str, agent_type: str
    ) -> bool:
        """Fallback check: is action sensible even if not in exact rule table?

        Used when construct combination is not in the lookup table.
        """
        ...
