"""
Generic Institutional Agent Framework

Core Principle: ALL parameters are 0-1 normalized for consistency.
Agent types are user-defined via YAML configuration, not hardcoded.

Literature Support:
- Abebe 2019 (CLAIM): Coupled flood-agent-institution framework
- Shrestha 2019: Organizational AI decision structures
- Tzavella 2025: Crisis-aware AI modeling

Task-037: Migrated from agents/base_agent.py to SDK
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional


# =============================================================================
# NORMALIZATION UTILITIES
# =============================================================================

def normalize(value: float, min_val: float, max_val: float) -> float:
    """Convert any value to 0-1 scale."""
    if max_val == min_val:
        return 0.5
    return max((min((value - min_val) / (max_val - min_val), 1.0)), 0.0)


def denormalize(normalized: float, min_val: float, max_val: float) -> float:
    """Convert 0-1 value back to original scale."""
    return normalized * (max_val - min_val) + min_val


# =============================================================================
# CONFIGURATION CLASSES
# =============================================================================

@dataclass
class StateParam:
    """
    User-defined state parameter with normalization.

    Example:
        StateParam(
            name="loss_ratio",
            raw_range=(0, 1.5),
            initial_raw=0.6,
            description="Claims / Premiums"
        )
    """
    name: str
    raw_range: Tuple[float, float]  # Original min/max
    initial_raw: float              # Initial value in raw scale
    description: str = ""

    @property
    def initial_normalized(self) -> float:
        return normalize(self.initial_raw, *self.raw_range)


@dataclass
class Objective:
    """
    User-defined objective with 0-1 target range.

    Literature: Dong 1996 (solvency), Siders 2021 (equity)
    """
    name: str
    param: str                      # Which state param this applies to
    target: Tuple[float, float]     # Target range in 0-1 scale
    weight: float                   # Importance (sum should = 1)
    literature: str = ""            # Citation


@dataclass
class Constraint:
    """
    User-defined constraint on actions.

    Literature: NFIP regulations, FEMA HMGP rules
    """
    name: str
    param: str                      # Which param this constrains
    max_change: float               # Max change per period (0-1 scale)
    bounds: Tuple[float, float]     # Hard limits (0-1 scale)
    literature: str = ""


@dataclass
class PerceptionSource:
    """What agent observes from another source."""
    source_type: str                # "environment" or "agent"
    source_name: str                # e.g., "Household", "flood_events"
    params: List[str]               # List of params to observe


@dataclass
class Skill:
    """
    User-defined skill (action).

    Literature: Seifert-Dähnn 2018, Mach 2019
    """
    skill_id: str
    description: str
    affected_param: Optional[str]   # Which state param is modified
    direction: str                  # "increase", "decrease", "none"
    literature: str = ""


@dataclass
class AgentConfig:
    """
    Complete configuration for a generic institutional agent.
    All values should be in 0-1 normalized scale.
    """
    name: str
    agent_type: str                 # User-defined type label

    # Core components
    state_params: List[StateParam]
    objectives: List[Objective]
    constraints: List[Constraint]
    skills: List[Skill]

    # Perception (what this agent observes)
    perception: List[PerceptionSource] = field(default_factory=list)

    # Persona for LLM prompts
    persona: str = ""
    role_description: str = ""


# =============================================================================
# BASE AGENT CLASS
# =============================================================================

class BaseAgent:
    """
    Generic base agent with 0-1 normalized state.

    Can be instantiated for any domain (flood, healthcare, supply chain)
    by providing appropriate AgentConfig.

    Implements:
        - AgentProtocol (minimal interface)
        - StatefulAgentProtocol (state modification)
        - MemoryCapableAgentProtocol (memory access)
    """

    def __init__(self, config: AgentConfig, memory=None):
        self.config = config
        self._id = config.name  # Use config name as default ID
        self.name = config.name
        self._agent_type = config.agent_type

        # Initialize normalized state
        self._state_raw: Dict[str, float] = {}
        self._state_normalized: Dict[str, float] = {}

        # PR 9: Explicit State Partitioning (Personal vs Environmental)
        self.fixed_attributes: Dict[str, Any] = {}  # Immutable (e.g., Demographics)
        self.dynamic_state: Dict[str, Any] = {}     # Mutable (e.g., Savings, Damage)

        self._init_state()

        # Memory (compatible with CognitiveMemory)
        self._memory = memory or []

        # Custom Attributes (Legacy support)
        self.custom_attributes: Dict[str, Any] = {}

        # Phase 12: Generic Memory Config (keywords, weights)
        self._memory_config: Dict[str, Any] = {}

    def _init_state(self):
        """Initialize state from config."""
        for param in self.config.state_params:
            self._state_raw[param.name] = param.initial_raw
            self._state_normalized[param.name] = param.initial_normalized
            # Populate Personal Dynamic State
            self.dynamic_state[param.name] = param.initial_raw

    # -------------------------------------------------------------------------
    # Protocol Properties
    # -------------------------------------------------------------------------

    @property
    def id(self) -> str:
        """Unique identifier for this agent."""
        return self._id

    @property
    def agent_type(self) -> str:
        """Type/category of this agent."""
        return self._agent_type

    @property
    def memory(self) -> List[Any]:
        """Access to agent's memory store."""
        return self._memory

    @memory.setter
    def memory(self, value: List[Any]):
        """Set agent's memory store."""
        self._memory = value

    @property
    def memory_config(self) -> Dict[str, Any]:
        """Memory configuration (weights, keywords, etc.)."""
        return self._memory_config

    @memory_config.setter
    def memory_config(self, value: Dict[str, Any]):
        """Set memory configuration."""
        self._memory_config = value

    # -------------------------------------------------------------------------
    # State Access (always 0-1)
    # -------------------------------------------------------------------------

    def get_state(self, param: str) -> float:
        """Get normalized state value (0-1)."""
        return self._state_normalized.get(param, 0.5)

    def get_state_raw(self, param: str) -> float:
        """Get raw state value (original scale)."""
        return self._state_raw.get(param, 0)

    def set_state(self, param: str, normalized_value: float):
        """Set state using normalized value (0-1)."""
        # Find param config
        param_config = next(
            (p for p in self.config.state_params if p.name == param),
            None
        )
        if param_config:
            # Clamp to 0-1
            normalized_value = max(0.0, min(1.0, normalized_value))
            self._state_normalized[param] = normalized_value
            self._state_raw[param] = denormalize(
                normalized_value, *param_config.raw_range
            )

    def get_all_state(self) -> Dict[str, float]:
        """Get all normalized state as dict."""
        return self._state_normalized.copy()

    def get_all_state_raw(self) -> Dict[str, float]:
        """Get all raw (denormalized) state as dict."""
        return self._state_raw.copy()

    # -------------------------------------------------------------------------
    # Perception
    # -------------------------------------------------------------------------

    def observe(
        self,
        environment: Dict[str, float],
        agents: Dict[str, 'BaseAgent']
    ) -> Dict[str, float]:
        """
        Gather perception from environment and other agents.
        All values returned in 0-1 scale.
        """
        perception = {}

        for source in self.config.perception:
            if source.source_type == "environment":
                for param in source.params:
                    perception[param] = environment.get(param, 0.0)

            elif source.source_type == "agent":
                if source.source_name in agents:
                    other_agent = agents[source.source_name]
                    for param in source.params:
                        key = f"{source.source_name}_{param}"
                        perception[key] = other_agent.get_state(param)

        return perception

    # -------------------------------------------------------------------------
    # Objectives & Constraints
    # -------------------------------------------------------------------------

    def evaluate_objectives(self) -> Dict[str, Dict]:
        """
        Evaluate current state against objectives.
        Returns dict with scores and whether in target range.
        """
        results = {}
        for obj in self.config.objectives:
            current = self.get_state(obj.param)
            in_range = obj.target[0] <= current <= obj.target[1]

            # Distance from target midpoint
            midpoint = (obj.target[0] + obj.target[1]) / 2
            distance = abs(current - midpoint)

            results[obj.name] = {
                "current": current,
                "target": obj.target,
                "in_range": in_range,
                "distance": distance,
                "weight": obj.weight
            }

        return results

    def check_constraint(self, param: str, proposed_change: float) -> Tuple[bool, str]:
        """
        Check if proposed change violates constraints.
        Returns (valid, message).
        """
        for c in self.config.constraints:
            if c.param == param:
                # Check max change
                if abs(proposed_change) > c.max_change:
                    return False, f"Change {proposed_change:.2f} exceeds max {c.max_change:.2f}"

                # Check bounds
                new_value = self.get_state(param) + proposed_change
                if not (c.bounds[0] <= new_value <= c.bounds[1]):
                    return False, f"New value {new_value:.2f} outside bounds {c.bounds}"

        return True, "OK"

    # -------------------------------------------------------------------------
    # Skills
    # -------------------------------------------------------------------------

    def get_available_skills(self) -> List[str]:
        """Get list of available skill IDs."""
        try:
            if not self.config.skills:
                return []

            first_skill = self.config.skills[0]

            if isinstance(first_skill, str):
                return self.config.skills

            return [s.skill_id for s in self.config.skills]
        except Exception as e:
            print(f"CRITICAL ERROR in get_available_skills: {e}")
            import traceback
            traceback.print_exc()
            raise e

    def execute_skill(self, skill_id: str, adjustment: float = 0.0) -> bool:
        """
        Execute a skill with given adjustment (0-1 scale).
        Returns True if successful.
        """
        skill = next(
            (s for s in self.config.skills if s.skill_id == skill_id),
            None
        )

        if not skill:
            return False

        if skill.affected_param and skill.direction != "none":
            # Check constraint
            change = adjustment if skill.direction == "increase" else -adjustment
            valid, msg = self.check_constraint(skill.affected_param, change)

            if not valid:
                return False

            # Apply change
            current = self.get_state(skill.affected_param)
            self.set_state(skill.affected_param, current + change)

        return True

    def apply_delta(self, state_changes: Dict[str, Any]) -> None:
        """
        Apply execution result state changes to agent attributes.

        This is the CANONICAL method for updating agent state from
        skill execution results. Applications SHOULD NOT use setattr
        directly.

        Args:
            state_changes: Dict of {attribute_name: new_value}
        """
        if not state_changes:
            return
        for key, value in state_changes.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                # Store in dynamic_state for new attributes
                self.dynamic_state[key] = value

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent state for prompts/audit."""
        return {
            "name": self.name,
            "agent_type": self.agent_type,
            "state": self.get_all_state(),
            "state_raw": self._state_raw.copy(),
            "objectives_eval": self.evaluate_objectives()
        }
