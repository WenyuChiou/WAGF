"""
SurpriseStrategy Protocol - Interface for pluggable surprise calculation.

All surprise strategies must implement this protocol to be compatible
with the UnifiedCognitiveEngine.

Reference: Task-040 Memory Module Optimization
"""

from typing import Dict, Any, Protocol, Optional, runtime_checkable


@runtime_checkable
class SurpriseStrategy(Protocol):
    """
    Protocol for pluggable surprise/arousal calculation strategies.

    Implementations determine how the system computes "surprise" from
    environmental observations, which in turn drives System 1/2 switching.

    Methods:
        update: Update internal state with new observation
        get_surprise: Calculate surprise for a given observation
        get_arousal: Get current arousal/activation level
        reset: Reset internal state for new simulation runs

    Example:
        >>> strategy = EMASurpriseStrategy(alpha=0.3)
        >>> surprise = strategy.update({"flood_depth": 2.5})
        >>> system = "SYSTEM_2" if surprise > threshold else "SYSTEM_1"
    """

    def update(self, observation: Dict[str, Any]) -> float:
        """
        Update internal state and return surprise for observation.

        This is the primary method called during memory operations.
        It should both update any internal tracking state AND return
        the surprise value for the current observation.

        Args:
            observation: Dictionary containing observed values
                        (e.g., {"flood_depth": 2.5, "panic_level": 0.3})

        Returns:
            Surprise value in range [0.0, 1.0] where:
            - 0.0 = completely expected (no surprise)
            - 1.0 = completely unexpected (maximum surprise)
        """
        ...

    def get_surprise(self, observation: Dict[str, Any]) -> float:
        """
        Calculate surprise WITHOUT updating internal state.

        Use this for read-only surprise queries where you don't want
        to affect the strategy's tracking state.

        Args:
            observation: Dictionary containing observed values

        Returns:
            Surprise value in range [0.0, 1.0]
        """
        ...

    def get_arousal(self) -> float:
        """
        Get current arousal/activation level.

        Returns the most recent arousal level computed by the strategy.
        This can be used for logging or external monitoring.

        Returns:
            Current arousal level (typically 0.0-1.0)
        """
        ...

    def get_trace(self) -> Optional[Dict[str, Any]]:
        """
        Get trace data from last operation for explainability.

        Returns a dictionary containing strategy-specific trace data
        that can be used for XAI-ABM integration and debugging.

        Returns:
            Dict with trace data, or None if no observations yet
        """
        ...

    def reset(self) -> None:
        """
        Reset internal state for new simulation runs.

        Clears all accumulated state (expectations, frequency maps, etc.)
        to start fresh for a new simulation episode.
        """
        ...
