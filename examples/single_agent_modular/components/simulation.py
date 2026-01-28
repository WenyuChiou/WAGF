"""
Flood Simulation Environment.

Handles flood event scheduling, grant availability, and skill execution.
"""
import random
from typing import Dict, List, Any
from broker.interfaces.skill_types import ExecutionResult

# Research Constants
FLOOD_PROBABILITY = 0.2
GRANT_PROBABILITY = 0.5


class ResearchSimulation:
    """
    Simulation environment for flood adaptation research.

    Manages:
    - Flood event scheduling (fixed years or probabilistic)
    - Grant availability
    - Skill execution and state changes
    """

    def __init__(
        self,
        agents: Dict[str, Any],
        flood_years: List[int] = None,
        flood_mode: str = "fixed",
        flood_probability: float = FLOOD_PROBABILITY
    ):
        self.agents = agents
        self.flood_years = flood_years or []
        self.flood_mode = flood_mode
        self.flood_probability = flood_probability
        self.current_year = 0
        self.flood_event = False
        self.grant_available = False

    def advance_year(self) -> Dict[str, Any]:
        """Advance simulation by one year and determine events."""
        self.current_year += 1

        if self.flood_mode == "prob":
            self.flood_event = random.random() < self.flood_probability
        else:
            self.flood_event = self.current_year in self.flood_years

        self.grant_available = random.random() < GRANT_PROBABILITY

        return {
            "flood_event": self.flood_event,
            "grant_available": self.grant_available,
            "current_year": self.current_year
        }

    def execute_skill(self, approved_skill) -> ExecutionResult:
        """Execute an approved skill and return state changes."""
        agent_id = approved_skill.agent_id
        agent = self.agents[agent_id]
        skill = approved_skill.skill_name
        state_changes = {}

        if skill == "elevate_house":
            if getattr(agent, "elevated", False):
                return ExecutionResult(success=False, error="House already elevated.")
            state_changes["elevated"] = True

        elif skill == "buy_insurance":
            state_changes["has_insurance"] = True

        elif skill == "relocate":
            state_changes["relocated"] = True
            agent.is_active = False

        # Insurance expiry logic
        if skill != "buy_insurance":
            state_changes["has_insurance"] = False

        return ExecutionResult(success=True, state_changes=state_changes)


def classify_adaptation_state(agent) -> str:
    """Classify agent's current adaptation state for reporting."""
    if getattr(agent, "relocated", False):
        return "Relocate"
    elevated = getattr(agent, "elevated", False)
    has_insurance = getattr(agent, "has_insurance", False)
    if elevated and has_insurance:
        return "Both Flood Insurance and House Elevation"
    elif elevated:
        return "Only House Elevation"
    elif has_insurance:
        return "Only Flood Insurance"
    else:
        return "Do Nothing"
