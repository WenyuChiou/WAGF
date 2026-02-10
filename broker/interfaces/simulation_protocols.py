"""
Simulation Engine Protocols - Duck-typed interfaces for environment advancement.

The framework uses duck typing with intelligent fallback for simulation engines:
    1. Try advance_step() (generic term for any time-step model)
    2. Fallback to advance_year() (domain-specific term for temporal models)
    3. Return empty dict if neither exists

Usage:
    class MySimulation:
        def advance_year(self) -> Dict[str, Any]:
            self.year += 1
            return {"current_year": self.year, "event_occurred": ...}

        def execute_skill(self, approved_skill: ApprovedSkill) -> ExecutionResult:
            # Apply state changes to agent
            return ExecutionResult(success=True, state_changes={...})

    # Type hint for IDE support:
    sim: SimulationEngineProtocol = MySimulation(...)
"""
from typing import Protocol, Dict, Any, runtime_checkable

from ..interfaces.skill_types import ApprovedSkill, ExecutionResult


@runtime_checkable
class SimulationEngineProtocol(Protocol):
    """Minimal interface for simulation time advancement.

    Implementations should provide EITHER advance_step() OR advance_year().
    ExperimentRunner tries advance_step() first, then advance_year().

    Returns:
        Dict with at minimum {"current_year": int}.
        Additional keys are domain-specific (e.g., flood_event, drought_level).
    """

    def advance_year(self) -> Dict[str, Any]:
        """Advance simulation by one year/step and return environment state."""
        ...


@runtime_checkable
class SkillExecutorProtocol(Protocol):
    """Optional interface for executing approved skills.

    If the simulation class implements this, ExperimentRunner calls it
    to apply state changes after governance validation.
    """

    def execute_skill(self, approved_skill: ApprovedSkill) -> ExecutionResult:
        """Apply approved skill to agent state and environment.

        Args:
            approved_skill: Validated skill with agent_id, skill_name, parameters.

        Returns:
            ExecutionResult with success flag and state_changes dict.
        """
        ...


__all__ = [
    "SimulationEngineProtocol",
    "SkillExecutorProtocol",
]
