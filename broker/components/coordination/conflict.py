"""
Conflict Resolver - Detect and resolve multi-agent resource conflicts.

Handles scenarios where multiple agents compete for limited resources
(e.g., government budget for subsidies, physical elevation capacity).

Design Principles:
1. Separation of detection (ConflictDetector) and resolution (ResolutionStrategy)
2. Pluggable resolution strategies (Priority, Auction, Proportional)
3. Audit-friendly: all conflicts and resolutions are logged
4. Compatible with GameMaster (coordinator.py)

References:
- Concordia (2024). Action Resolution with constraint checking.
- MetaGPT (2023). Schedule Manager for conflict-free execution.

Reference: Task-054 Communication Layer
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional, Any
import logging

from broker.interfaces.coordination import (
    ActionProposal,
    ActionResolution,
    ResourceConflict,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conflict Detection
# ---------------------------------------------------------------------------

class ConflictDetector:
    """Detect resource conflicts from a set of action proposals.

    Scans proposals for resource over-allocation by summing
    ``resource_requirements`` across all proposals and comparing
    against known resource limits.

    Args:
        resource_limits: Mapping of resource_key -> available amount.
            Example: {"govt_budget": 500000, "elevation_slots": 10}
    """

    def __init__(self, resource_limits: Dict[str, float]):
        self.resource_limits = dict(resource_limits)

    def detect(self, proposals: List[ActionProposal]) -> List[ResourceConflict]:
        """Scan proposals for resource conflicts.

        Args:
            proposals: List of action proposals to check

        Returns:
            List of detected conflicts (empty if no conflicts)
        """
        # Aggregate resource demands per resource key
        demands: Dict[str, Dict[str, float]] = {}  # resource -> {agent_id: amount}

        for proposal in proposals:
            for resource_key, amount in proposal.resource_requirements.items():
                if resource_key not in demands:
                    demands[resource_key] = {}
                demands[resource_key][proposal.agent_id] = amount

        conflicts = []
        for resource_key, agent_demands in demands.items():
            limit = self.resource_limits.get(resource_key)
            if limit is None:
                continue  # No limit set for this resource

            total_requested = sum(agent_demands.values())
            if total_requested > limit:
                conflict = ResourceConflict(
                    resource_key=resource_key,
                    total_requested=total_requested,
                    available=limit,
                    competing_agents=list(agent_demands.keys()),
                    conflict_type="over_allocation",
                )
                conflicts.append(conflict)
                logger.info(
                    "ConflictDetector: %s over-allocation: %.0f requested vs %.0f available (%d agents)",
                    resource_key, total_requested, limit, len(agent_demands),
                )

        return conflicts

    def update_limit(self, resource_key: str, new_limit: float) -> None:
        """Update a resource limit (e.g., after budget replenishment)."""
        self.resource_limits[resource_key] = new_limit


# ---------------------------------------------------------------------------
# Resolution Strategies (ABC + Concrete)
# ---------------------------------------------------------------------------

class ResolutionStrategy(ABC):
    """Abstract resolution strategy for resource conflicts."""

    @abstractmethod
    def resolve(
        self,
        conflict: ResourceConflict,
        proposals: List[ActionProposal],
    ) -> List[ActionResolution]:
        """Resolve a single conflict.

        Args:
            conflict: The detected conflict
            proposals: All proposals competing for this resource

        Returns:
            List of ActionResolutions (one per competing agent)
        """
        ...


class PriorityResolution(ResolutionStrategy):
    """Resolve conflicts by agent priority (higher priority wins).

    Default priority order:
    - Government/Institutional agents: priority 100
    - MG households: priority 50
    - NMG households: priority 10

    When priority is equal, first-come-first-served by list order.

    Args:
        type_priorities: Optional mapping of agent_type -> base priority.
            Overrides proposal.priority for ordering.
    """

    def __init__(self, type_priorities: Optional[Dict[str, int]] = None):
        self.type_priorities = type_priorities or {
            "government": 100,
            "insurance": 90,
            "household_mg_owner": 50,
            "household_mg_renter": 50,
            "household_nmg_owner": 10,
            "household_nmg_renter": 10,
            "household_owner": 10,
            "household_renter": 10,
        }

    def resolve(
        self,
        conflict: ResourceConflict,
        proposals: List[ActionProposal],
    ) -> List[ActionResolution]:
        # Filter to competing proposals only
        competing = [
            p for p in proposals
            if p.agent_id in conflict.competing_agents
            and conflict.resource_key in p.resource_requirements
        ]

        # Sort by effective priority (descending)
        competing.sort(
            key=lambda p: self.type_priorities.get(p.agent_type, p.priority),
            reverse=True,
        )

        remaining = conflict.available
        resolutions = []

        for proposal in competing:
            needed = proposal.resource_requirements.get(conflict.resource_key, 0)
            if remaining >= needed:
                # Approved: enough resources
                resolutions.append(ActionResolution(
                    agent_id=proposal.agent_id,
                    original_proposal=proposal,
                    approved=True,
                    event_statement=(
                        f"{proposal.agent_id} was approved for {proposal.skill_name} "
                        f"(resource: {conflict.resource_key}, allocated: {needed:.0f})"
                    ),
                ))
                remaining -= needed
            else:
                # Denied: insufficient resources
                resolutions.append(ActionResolution(
                    agent_id=proposal.agent_id,
                    original_proposal=proposal,
                    approved=False,
                    denial_reason=(
                        f"Insufficient {conflict.resource_key}: "
                        f"needed {needed:.0f}, only {remaining:.0f} remaining"
                    ),
                    event_statement=(
                        f"{proposal.agent_id} was denied {proposal.skill_name} "
                        f"due to insufficient {conflict.resource_key}"
                    ),
                ))

        return resolutions


class ProportionalResolution(ResolutionStrategy):
    """Split contested resources proportionally among requesters.

    Each agent receives a share proportional to their request size.
    All proposals are approved but with reduced allocation.
    """

    def resolve(
        self,
        conflict: ResourceConflict,
        proposals: List[ActionProposal],
    ) -> List[ActionResolution]:
        competing = [
            p for p in proposals
            if p.agent_id in conflict.competing_agents
            and conflict.resource_key in p.resource_requirements
        ]

        total_requested = sum(
            p.resource_requirements.get(conflict.resource_key, 0)
            for p in competing
        )

        resolutions = []
        for proposal in competing:
            requested = proposal.resource_requirements.get(conflict.resource_key, 0)
            share = (requested / total_requested) * conflict.available if total_requested > 0 else 0

            resolutions.append(ActionResolution(
                agent_id=proposal.agent_id,
                original_proposal=proposal,
                approved=True,
                state_changes={f"{conflict.resource_key}_allocated": share},
                event_statement=(
                    f"{proposal.agent_id} received proportional allocation "
                    f"for {proposal.skill_name}: {share:.0f}/{requested:.0f} "
                    f"of {conflict.resource_key}"
                ),
            ))

        return resolutions


# ---------------------------------------------------------------------------
# Main Resolver
# ---------------------------------------------------------------------------

class ConflictResolver:
    """Top-level conflict resolution orchestrator.

    Combines ConflictDetector and ResolutionStrategy to process
    a batch of action proposals and return resolved outcomes.

    Args:
        detector: ConflictDetector with resource limits
        strategy: Resolution strategy (default: PriorityResolution)
    """

    def __init__(
        self,
        detector: ConflictDetector,
        strategy: Optional[ResolutionStrategy] = None,
    ):
        self.detector = detector
        self.strategy = strategy or PriorityResolution()
        self._conflict_history: List[ResourceConflict] = []

    def resolve_all(
        self,
        proposals: List[ActionProposal],
    ) -> Tuple[List[ActionResolution], List[ResourceConflict]]:
        """Detect conflicts and resolve them.

        Args:
            proposals: All action proposals for the current step

        Returns:
            Tuple of (resolutions, detected_conflicts).
            Resolutions only cover agents in conflicts.
            Non-conflicting agents are not included (pass-through).
        """
        conflicts = self.detector.detect(proposals)
        self._conflict_history.extend(conflicts)

        if not conflicts:
            return [], []

        all_resolutions: List[ActionResolution] = []
        for conflict in conflicts:
            resolutions = self.strategy.resolve(conflict, proposals)
            all_resolutions.extend(resolutions)

        logger.info(
            "ConflictResolver: %d conflicts detected, %d resolutions generated",
            len(conflicts), len(all_resolutions),
        )
        return all_resolutions, conflicts

    @property
    def conflict_history(self) -> List[ResourceConflict]:
        """All conflicts detected across the simulation."""
        return list(self._conflict_history)

    def summary(self) -> Dict[str, Any]:
        """Return resolver statistics."""
        return {
            "total_conflicts": len(self._conflict_history),
            "resource_limits": dict(self.detector.resource_limits),
            "strategy": type(self.strategy).__name__,
        }


__all__ = [
    "ConflictDetector",
    "ResolutionStrategy",
    "PriorityResolution",
    "ProportionalResolution",
    "ConflictResolver",
]
