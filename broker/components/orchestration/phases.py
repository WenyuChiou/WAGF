"""
Phase Orchestrator - Configurable multi-phase agent execution ordering.

Replaces implicit dict-order agent execution with explicit,
configurable phase definitions. Supports:
- Multi-phase execution (institutional → household → resolution → observation)
- Per-phase agent type filtering
- Sequential, parallel, and random ordering within phases
- YAML-based configuration
- Dependency ordering between phases

Design Principles:
1. Non-invasive: works alongside ExperimentRunner via hooks
2. Configurable: phases defined via code or YAML
3. Deterministic: random ordering uses seeded RNG

References:
- AgentSociety (2024). Phase-based execution with time alignment.
- MetaGPT (2023). Schedule Manager for ordered multi-agent execution.

Reference: Task-054 Communication Layer
"""
from typing import Dict, List, Tuple, Optional, Any
import random
import logging

from broker.interfaces.coordination import ExecutionPhase, PhaseConfig

logger = logging.getLogger(__name__)


class PhaseOrchestrator:
    """Orchestrates multi-phase agent execution ordering.

    Defines which agent types execute in which order, replacing
    the implicit dictionary-order execution in ExperimentRunner.

    Args:
        phases: List of PhaseConfig definitions. If None, uses default
            4-phase ordering (institutional → household → resolution → observation).
        seed: Random seed for deterministic "random" ordering.
    """

    def __init__(
        self,
        phases: Optional[List[PhaseConfig]] = None,
        seed: int = 42,
        saga_coordinator: Optional[Any] = None,
    ):
        self.phases = phases or self._default_phases()
        self._rng = random.Random(seed)
        self.saga_coordinator = saga_coordinator
        self._validate_phases()

    @staticmethod
    def _default_phases() -> List[PhaseConfig]:
        """Default 4-phase execution order for flood MAS."""
        return [
            PhaseConfig(
                phase=ExecutionPhase.INSTITUTIONAL,
                agent_types=["government", "insurance"],
                ordering="sequential",
            ),
            PhaseConfig(
                phase=ExecutionPhase.HOUSEHOLD,
                agent_types=[
                    "household_owner", "household_renter",
                    "household_nmg_owner", "household_nmg_renter",
                    "household_mg_owner", "household_mg_renter",
                ],
                ordering="sequential",
            ),
            PhaseConfig(
                phase=ExecutionPhase.RESOLUTION,
                agent_types=[],  # No agents — GM/Coordinator handles this
                depends_on=[ExecutionPhase.INSTITUTIONAL, ExecutionPhase.HOUSEHOLD],
            ),
            PhaseConfig(
                phase=ExecutionPhase.OBSERVATION,
                agent_types=[],  # No agents — observable state updates
                depends_on=[ExecutionPhase.RESOLUTION],
            ),
        ]

    def _validate_phases(self) -> None:
        """Validate phase configuration consistency."""
        phase_names = {p.phase for p in self.phases}
        for pc in self.phases:
            for dep in pc.depends_on:
                if dep not in phase_names:
                    logger.warning(
                        "PhaseOrchestrator: Phase %s depends on %s which is not defined",
                        pc.phase.value, dep.value,
                    )

    # ------------------------------------------------------------------
    # Execution plan generation
    # ------------------------------------------------------------------

    def get_execution_plan(
        self,
        agents: Dict[str, Any],
        current_step: int = 0,
    ) -> List[Tuple[ExecutionPhase, List[str]]]:
        """Generate ordered execution plan for all phases.

        Args:
            agents: Dictionary of agent_id -> agent objects.
                Each agent must have an ``agent_type`` attribute.

        Returns:
            Ordered list of (phase, [agent_ids]) tuples.
            Agent-less phases (resolution, observation) have empty lists.
        """
        plan: List[Tuple[ExecutionPhase, List[str]]] = []

        for pc in self._topological_order():
            agent_ids = self._select_agents(pc, agents)
            agent_ids = self._apply_ordering(agent_ids, pc.ordering)
            plan.append((pc.phase, agent_ids))

        return plan

    def advance_sagas(self, current_step: int = 0) -> None:
        """Advance all active sagas at phase boundaries."""
        if not self.saga_coordinator:
            return
        completed = self.saga_coordinator.advance_all(current_step=current_step)
        for result in completed:
            if result and result.status.value in ("rolled_back", "failed"):
                logger.warning(
                    "[Saga] %s %s: %s",
                    result.saga_name,
                    result.status.value,
                    result.error,
                )

    def get_phase_agents(
        self,
        phase: ExecutionPhase,
        agents: Dict[str, Any],
    ) -> List[str]:
        """Get ordered agent IDs for a specific phase.

        Args:
            phase: Target phase
            agents: All agents

        Returns:
            Ordered list of agent IDs for this phase
        """
        pc = self._get_phase_config(phase)
        if pc is None:
            return []
        agent_ids = self._select_agents(pc, agents)
        return self._apply_ordering(agent_ids, pc.ordering)

    def get_phase_config(self, phase: ExecutionPhase) -> Optional[PhaseConfig]:
        """Get configuration for a specific phase."""
        return self._get_phase_config(phase)

    # ------------------------------------------------------------------
    # YAML loading
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str, seed: int = 42) -> "PhaseOrchestrator":
        """Load phase configuration from a YAML file.

        Expected YAML format::

            phases:
              - phase: institutional
                agent_types: [government, insurance]
                ordering: sequential
              - phase: household
                agent_types: [household_owner, household_renter]
                ordering: sequential
              - phase: resolution
                agent_types: []
                depends_on: [institutional, household]
              - phase: observation
                agent_types: []
                depends_on: [resolution]

        Args:
            path: Path to YAML file
            seed: Random seed

        Returns:
            Configured PhaseOrchestrator
        """
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        phase_map = {e.value: e for e in ExecutionPhase}

        phases = []
        for entry in data.get("phases", []):
            phase_enum = phase_map.get(entry["phase"])
            if phase_enum is None:
                logger.warning("Unknown phase: %s, using CUSTOM", entry["phase"])
                phase_enum = ExecutionPhase.CUSTOM

            depends = []
            for dep_name in entry.get("depends_on", []):
                dep_enum = phase_map.get(dep_name)
                if dep_enum:
                    depends.append(dep_enum)

            phases.append(PhaseConfig(
                phase=phase_enum,
                agent_types=entry.get("agent_types", []),
                ordering=entry.get("ordering", "sequential"),
                max_workers=entry.get("max_workers", 1),
                depends_on=depends,
            ))

        return cls(phases=phases, seed=seed)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_phase_config(self, phase: ExecutionPhase) -> Optional[PhaseConfig]:
        """Find PhaseConfig by phase enum."""
        for pc in self.phases:
            if pc.phase == phase:
                return pc
        return None

    def _select_agents(
        self,
        pc: PhaseConfig,
        agents: Dict[str, Any],
    ) -> List[str]:
        """Select agents matching the phase's agent_types."""
        if not pc.agent_types:
            return []
        return [
            aid for aid, agent in agents.items()
            if getattr(agent, "agent_type", "") in pc.agent_types
        ]

    def _apply_ordering(self, agent_ids: List[str], ordering: str) -> List[str]:
        """Apply ordering within a phase."""
        if ordering == "random":
            ids = list(agent_ids)
            self._rng.shuffle(ids)
            return ids
        elif ordering == "parallel":
            return list(agent_ids)  # Same order; parallelism handled by caller
        else:  # sequential (default)
            return list(agent_ids)

    def _topological_order(self) -> List[PhaseConfig]:
        """Sort phases respecting dependency order (Kahn's algorithm)."""
        phase_map = {pc.phase: pc for pc in self.phases}
        in_degree = {pc.phase: 0 for pc in self.phases}

        for pc in self.phases:
            for dep in pc.depends_on:
                if dep in in_degree:
                    in_degree[pc.phase] += 1

        queue = [ph for ph, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(phase_map[current])
            for pc in self.phases:
                if current in pc.depends_on:
                    in_degree[pc.phase] -= 1
                    if in_degree[pc.phase] == 0:
                        queue.append(pc.phase)

        # Fallback if cycle detected
        if len(result) != len(self.phases):
            logger.warning("PhaseOrchestrator: Cycle detected in phase dependencies, using original order")
            return list(self.phases)

        return result

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Return orchestrator configuration summary."""
        return {
            "num_phases": len(self.phases),
            "phases": [
                {
                    "phase": pc.phase.value,
                    "agent_types": pc.agent_types,
                    "ordering": pc.ordering,
                    "depends_on": [d.value for d in pc.depends_on],
                }
                for pc in self.phases
            ],
        }


__all__ = ["PhaseOrchestrator"]
