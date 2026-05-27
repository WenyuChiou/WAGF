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
from broker.components.events.exceptions import (
    InvalidPhaseConfigError,
    PhaseDependencyCycleError,
)

logger = logging.getLogger(__name__)


class PhaseOrchestrator:
    """Orchestrates multi-phase agent execution ordering.

    Defines which agent types execute in which order, replacing
    the implicit dictionary-order execution in ExperimentRunner.

    Args:
        phases: List of PhaseConfig definitions. If None, uses the
            generic 3-phase layout (CUSTOM → RESOLUTION → OBSERVATION).
            For the water-domain 4-phase layout use from_domain("flood")
            or pass phases= explicitly.
        seed: Random seed for deterministic "random" ordering.
    """

    def __init__(
        self,
        phases: Optional[List[PhaseConfig]] = None,
        seed: int = 42,
        saga_coordinator: Optional[Any] = None,
    ):
        self.phases = phases or self._generic_phases()
        self._rng = random.Random(seed)
        self.saga_coordinator = saga_coordinator
        self._validate_phases()

    # Phase 6Q-A (2026-05-26): removed ``_default_phases()`` — a
    # static-method compatibility wrapper that did ``from
    # broker.domains.water.phase_layouts import water_default_phases``.
    # Post-Phase-6P-B (2026-05-25) the only caller, ``from_domain``,
    # was rewritten to route through ``DomainPackRegistry`` instead,
    # leaving ``_default_phases`` as dead code carrying a generic-→
    # water-namespace reverse import. Grep-confirmed zero external
    # callers (`PhaseOrchestrator._default_phases` / `cls._default_phases` /
    # `self._default_phases` all return no matches). The flood phase
    # layout still ships via ``FloodDomainPack.phase_layout()`` →
    # ``water_default_phases()`` — examples/water-pack importing
    # from broker.domains.water is in-namespace.

    @staticmethod
    def _generic_phases() -> List[PhaseConfig]:
        """Domain-agnostic default — single agent phase + resolution/observation.

        Uses :class:`PhaseConfig` with ``agent_types=None`` (auto-discover) so
        the orchestrator runs ALL agents regardless of agent_type vocabulary.
        Use this when you don't want flood-specific household/government
        defaults and don't have a domain-tailored YAML phase config yet.

        Added 2026-05-10 (Phase 6C-v4 G1a) to remove the flood-only assumption
        previously baked into the now-deleted ``_default_phases()`` static
        method.
        """
        return [
            PhaseConfig(
                phase=ExecutionPhase.CUSTOM,
                agent_types=None,  # auto-discover all agents
                ordering="sequential",
            ),
            PhaseConfig(
                phase=ExecutionPhase.RESOLUTION,
                agent_types=[],
                depends_on=[ExecutionPhase.CUSTOM],
            ),
            PhaseConfig(
                phase=ExecutionPhase.OBSERVATION,
                agent_types=[],
                depends_on=[ExecutionPhase.RESOLUTION],
            ),
        ]

    @classmethod
    def from_domain(
        cls,
        domain: Optional[str] = None,
        seed: int = 42,
        saga_coordinator: Optional[Any] = None,
    ) -> "PhaseOrchestrator":
        """Construct an orchestrator with domain-appropriate default phases.

        Args:
            domain: Domain name (e.g. "flood", "irrigation", "vaccination").
                Phase 6Q-J (2026-05-26): ``None``/empty now resolves
                directly to the generic 3-phase layout (was a "flood"
                backward-compat default pre-6Q-J — a Phase 6P-B
                carryover). Explicit ``"flood"`` still returns the
                4-phase water layout via ``FloodDomainPack.phase_layout()``.
                Any other registered domain → its
                ``DomainPack.phase_layout()`` if non-``None``, else the
                generic layout. New domains work out-of-the-box without
                YAML by inheriting ``DefaultDomainPack.phase_layout() ->
                None``.
            seed: Random seed for "random" ordering inside phases.
            saga_coordinator: Optional saga coordinator.

        Returns:
            A configured PhaseOrchestrator. To override phase structure
            entirely, use :meth:`from_yaml` or pass ``phases=`` to ``__init__``.
        """
        # Phase 6P-B (2026-05-25): generic-broker → water-namespace
        # coupling closed. Layout selection now goes through DomainPack
        # registry — no more hardcoded ``if domain == "flood":`` branch.
        # Domains that need a custom multi-agent split override
        # ``DomainPack.phase_layout()``.
        #
        # Phase 6Q-J (2026-05-26): the ``None → "flood"`` legacy default
        # (a Phase 6P-B backward-compat carryover) is removed.
        # ``None``/empty now resolves to the generic 3-phase layout
        # directly, matching the rest of the dispatch layer where
        # missing-domain falls through to the generic path. The only
        # callers passing ``None`` were tests (grep confirmed); they
        # update in lockstep with this change. Explicit
        # ``from_domain("flood")`` still works via the FloodDomainPack
        # registry lookup.
        from broker.domains.registry import DomainPackRegistry

        resolved = (domain or "").strip().lower() or None

        if resolved is not None:
            # Phase 6R-D-4 (2026-05-26): SetupPack-narrowed accessor.
            pack = DomainPackRegistry.get_setup_pack(resolved)
            layout = pack.phase_layout()
            if layout is not None:
                return cls(phases=layout, seed=seed,
                           saga_coordinator=saga_coordinator)

        return cls(phases=cls._generic_phases(), seed=seed,
                   saga_coordinator=saga_coordinator)

    def _validate_phases(self) -> None:
        """Validate phase configuration consistency.

        Phase 6T-A (2026-05-27): broken dependencies now raise
        :class:`InvalidPhaseConfigError`. Pre-6T-A the validator emitted
        ``logger.warning`` and continued, leaving ``depends_on``
        pointing at a non-existent phase — the ``_topological_order``
        Kahn pass treated the broken edge as satisfied (since
        ``in_degree`` ignored unknown deps) and produced a meaningless
        order. Phase 6T's institutional-diversity work (social-media
        influencer phase depending on observer phase) is the trigger
        for the hard-fail.
        """
        phase_names = {p.phase for p in self.phases}
        for pc in self.phases:
            for dep in pc.depends_on:
                if dep not in phase_names:
                    raise InvalidPhaseConfigError(
                        f"PhaseConfig {pc.phase.value!r} declares "
                        f"depends_on={dep.value!r} which is not defined "
                        f"in this orchestrator. Declared phases: "
                        f"{sorted(p.value for p in phase_names)!r}. "
                        f"Fix by either adding the missing phase or "
                        f"removing the dangling dependency."
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
                # Phase 6T-A: hard-fail. Pre-6T-A behaviour silently
                # rewrote unknown phases to ExecutionPhase.CUSTOM,
                # collapsing distinct YAML phases into a single bucket
                # and masking typos. New domains adding phase names
                # via Phase 6T-F (social_media_influencer phase) must
                # register the enum value first; silent CUSTOM
                # fallback would have buried the missing-enum bug.
                raise InvalidPhaseConfigError(
                    f"Unknown phase {entry['phase']!r} in {path}. "
                    f"Known phases: {sorted(phase_map.keys())!r}. "
                    f"Fix by adding the phase to ExecutionPhase or "
                    f"correcting the YAML entry."
                )

            depends = []
            for dep_name in entry.get("depends_on", []):
                dep_enum = phase_map.get(dep_name)
                if dep_enum is None:
                    raise InvalidPhaseConfigError(
                        f"Phase {entry['phase']!r} in {path} declares "
                        f"depends_on={dep_name!r} which is not a known "
                        f"phase. Known phases: "
                        f"{sorted(phase_map.keys())!r}."
                    )
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
        """Select agents matching the phase's agent_types.

        Semantics per PhaseConfig.agent_types:
        - ``None`` → auto-discover ALL agents (domain-agnostic mode)
        - ``[]``   → skip phase (agent-less, e.g. RESOLUTION / OBSERVATION)
        - non-empty list → explicit allow-list by agent_type
        """
        # None sentinel: include all agents — used by generic / domain-agnostic
        # default phases so PhaseOrchestrator works without prior knowledge of
        # the domain's agent_type vocabulary (Phase 6C-v4 G1a, 2026-05-10).
        if pc.agent_types is None:
            return list(agents.keys())
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

        # Phase 6T-A (2026-05-27): cycle detection now hard-fails.
        # Pre-6T-A behaviour returned the original (unsorted) phase
        # list, producing meaningless execution order (e.g. household
        # phase running before institutional phase that supplies its
        # subsidy context). Phase 6T-F's social_media_influencer phase
        # introduces a cycle risk (influencer depends on observer,
        # observer depends on household — if household is configured
        # to depend on influencer the cycle closes); silent fallback
        # would mask the YAML bug.
        if len(result) != len(self.phases):
            unresolved = [
                pc.phase.value for pc in self.phases
                if phase_map[pc.phase] not in result
            ]
            raise PhaseDependencyCycleError(
                f"PhaseOrchestrator: cycle detected in phase "
                f"dependencies. Unresolved phases: {unresolved!r}. "
                f"Declared phases: "
                f"{[pc.phase.value for pc in self.phases]!r}. "
                f"Fix by breaking the cycle in depends_on."
            )

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
