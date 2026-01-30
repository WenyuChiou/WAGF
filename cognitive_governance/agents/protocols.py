"""
Agent Protocol Definitions for SDK.

Provides Protocol-based interfaces for loose coupling between SDK and Broker.
Agents implementing these protocols can be used interchangeably across the framework.

Task-037: SDK-Broker Architecture Separation
"""
from typing import Protocol, Dict, List, Any, Tuple, Optional, runtime_checkable


@runtime_checkable
class AgentProtocol(Protocol):
    """
    Minimal interface for agents in the governed broker framework.

    This protocol defines the essential methods that any agent must implement
    to be compatible with the broker's memory, context, and execution systems.

    Example:
        class CustomAgent:
            @property
            def id(self) -> str:
                return self._id

            @property
            def agent_type(self) -> str:
                return "custom"

            def get_state(self, param: str) -> float:
                return self._state.get(param, 0.5)

            # ... implement other methods
    """

    @property
    def id(self) -> str:
        """Unique identifier for this agent."""
        ...

    @property
    def agent_type(self) -> str:
        """Type/category of this agent (e.g., 'household_owner', 'government')."""
        ...

    def get_state(self, param: str) -> float:
        """
        Get normalized state value (0-1 scale).

        Args:
            param: State parameter name

        Returns:
            Normalized value in range [0, 1], defaults to 0.5 if not found
        """
        ...

    def get_all_state(self) -> Dict[str, float]:
        """
        Get all normalized state as dictionary.

        Returns:
            Dictionary mapping parameter names to normalized values
        """
        ...

    def get_available_skills(self) -> List[str]:
        """
        Get list of skill IDs available to this agent.

        Returns:
            List of skill identifiers this agent can execute
        """
        ...

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize agent state for prompts, audit, or persistence.

        Returns:
            Dictionary containing agent name, type, state, and other relevant info
        """
        ...


@runtime_checkable
class StatefulAgentProtocol(AgentProtocol, Protocol):
    """
    Extended protocol for agents with mutable state.

    Adds methods for state modification used by skill execution
    and simulation updates.
    """

    def set_state(self, param: str, normalized_value: float) -> None:
        """
        Set state using normalized value (0-1).

        Args:
            param: State parameter name
            normalized_value: Value to set (will be clamped to [0, 1])
        """
        ...

    def apply_delta(self, state_changes: Dict[str, Any]) -> None:
        """
        Apply execution result state changes to agent.

        This is the canonical method for updating agent state from
        skill execution results.

        Args:
            state_changes: Dictionary of {attribute_name: new_value}
        """
        ...

    def check_constraint(self, param: str, proposed_change: float) -> Tuple[bool, str]:
        """
        Check if proposed change violates constraints.

        Args:
            param: Parameter to modify
            proposed_change: Proposed change amount

        Returns:
            Tuple of (is_valid, message)
        """
        ...


@runtime_checkable
class MemoryCapableAgentProtocol(AgentProtocol, Protocol):
    """
    Protocol for agents with memory capabilities.

    Used by memory engines and context builders.
    """

    @property
    def memory(self) -> List[Any]:
        """Access to agent's memory store."""
        ...

    @property
    def memory_config(self) -> Dict[str, Any]:
        """Memory configuration (weights, keywords, etc.)."""
        ...


__all__ = [
    "AgentProtocol",
    "StatefulAgentProtocol",
    "MemoryCapableAgentProtocol",
]
