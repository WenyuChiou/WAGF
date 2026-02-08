"""
Environment Protocol Definitions.

Provides Protocol-based interfaces for loose coupling between SDK and Broker.
Environments implementing these protocols can be used interchangeably.

Migrated from: cognitive_governance/simulation/protocols.py
Original: Task-037 SDK-Broker Architecture Separation
"""
from typing import Protocol, Dict, Any, List, Optional, runtime_checkable


@runtime_checkable
class EnvironmentProtocol(Protocol):
    """
    Minimal interface for environments in the water agent governance framework.

    This protocol defines the essential methods that any environment must implement
    to be compatible with the broker's context building and observation systems.

    Example:
        class CustomEnvironment:
            def get_observable(self, path: str, default: Any = None) -> Any:
                return self._data.get(path, default)

            def to_dict(self) -> Dict[str, Any]:
                return {"state": self._data}
    """

    def get_observable(self, path: str, default: Any = None) -> Any:
        """
        Safe retrieval using dot-notation path.

        Examples:
            - "global.year"
            - "local.T001.flood_depth"
            - "institutions.fema.budget"
            - "social.Agent_1.elevated"

        Args:
            path: Dot-notation path to the value
            default: Value to return if path not found

        Returns:
            The value at the path, or default if not found
        """
        ...

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize environment state for audit/logging.

        Returns:
            Dictionary containing all environment state layers
        """
        ...


@runtime_checkable
class TieredEnvironmentProtocol(EnvironmentProtocol, Protocol):
    """
    Extended protocol for tiered (multi-layered) environments.

    Adds methods for accessing specific layers and social state.
    """

    @property
    def global_state(self) -> Dict[str, Any]:
        """Access to global simulation-wide state."""
        ...

    @property
    def local_states(self) -> Dict[str, Dict[str, Any]]:
        """Access to spatial/regional state by location ID."""
        ...

    @property
    def institutions(self) -> Dict[str, Dict[str, Any]]:
        """Access to institutional agent states."""
        ...

    @property
    def social_states(self) -> Dict[str, Dict[str, Any]]:
        """Access to observable neighbor states."""
        ...

    def set_global(self, key: str, value: Any) -> None:
        """Set a global variable."""
        ...

    def set_local(self, location_id: str, key: str, value: Any) -> None:
        """Set a variable for a specific location."""
        ...

    def get_local(self, location_id: str, key: str, default: Any = None) -> Any:
        """Get a variable for a specific location."""
        ...

    def set_social(self, agent_id: str, key: str, value: Any) -> None:
        """Set an observable social state for an agent."""
        ...


@runtime_checkable
class SocialEnvironmentProtocol(EnvironmentProtocol, Protocol):
    """
    Protocol for environments with social network capabilities.

    Used by context builders for neighbor observation aggregation.
    """

    def get_neighbor_observations(
        self,
        agent_id: str,
        observable_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated observations of an agent's neighbors.

        Args:
            agent_id: Center agent
            observable_keys: List of boolean/numeric keys to aggregate

        Returns:
            Dictionary with neighbor_count and aggregated observations
        """
        ...


__all__ = [
    "EnvironmentProtocol",
    "TieredEnvironmentProtocol",
    "SocialEnvironmentProtocol",
]
