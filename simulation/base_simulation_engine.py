"""
Base Simulation Engine - Minimal interface for simulation classes.
"""
from typing import Dict, Any, List
from simulation.environment import TieredEnvironment

class BaseSimulationEngine:
    """Base class for simulation engines."""
    
    def __init__(self):
        self.env = TieredEnvironment()

    def get_agents(self) -> List[Any]:
        """Return list of agents in the simulation."""
        return []
    
    def step(self, step_idx: int) -> None:
        """Execute one simulation step."""
        pass
    
    def get_state(self) -> Dict[str, Any]:
        """Return current simulation state."""
        return self.env.to_dict()

