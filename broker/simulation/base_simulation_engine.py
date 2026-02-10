"""
Base Simulation Engine - Optional reference implementation.

This class provides a minimal starting point for simulation engines.
It is NOT required -- ExperimentRunner uses duck typing, not inheritance.
You can implement SimulationEngineProtocol without inheriting from this class.

See Also:
    broker.interfaces.simulation_protocols.SimulationEngineProtocol
    broker.interfaces.simulation_protocols.SkillExecutorProtocol
"""
from typing import Dict, Any, List
from broker.simulation.environment import TieredEnvironment


class BaseSimulationEngine:
    """Optional base class for simulation engines.

    ExperimentRunner uses duck typing with fallback logic:
        1. Try advance_step() first (generic term)
        2. Fallback to advance_year() (temporal models)

    Subclasses should override advance_year() and optionally execute_skill().
    Alternatively, implement the same methods on any class -- no inheritance needed.
    """

    def __init__(self):
        self.env = TieredEnvironment()

    def get_agents(self) -> List[Any]:
        """Return list of agents in the simulation."""
        return []

    def step(self, step_idx: int) -> None:
        """Execute one simulation step."""
        pass

    def advance_year(self) -> Dict[str, Any]:
        """Advance simulation by one year and return environment state.

        Override this method with your domain's time-step logic.

        Returns:
            Dict with at minimum {"current_year": int}.
        """
        return self.env.to_dict()

    def get_state(self) -> Dict[str, Any]:
        """Return current simulation state."""
        return self.env.to_dict()
