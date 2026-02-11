"""
Game Master / Coordinator - Central action resolution for MAS.

Implements Concordia-style Game Master that:
1. Collects action proposals from all agents in a phase
2. Detects resource conflicts via ConflictResolver
3. Resolves conflicts using configurable strategies
4. Generates natural language Event Statements for agent memory
5. Publishes resolution outcomes via MessagePool (optional)

Design Principles:
1. Pluggable strategy pattern (CoordinatorStrategy ABC)
2. Non-invasive: works via lifecycle hooks, no ExperimentRunner changes
3. Audit-friendly: full resolution history
4. Optional MessagePool integration for broadcasting resolutions

References:
- Concordia (2024). Game Master (GM) action resolution.
- AgentTorch (2024). Transition function S_next = t(S, A).

Reference: Task-054 Communication Layer
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
import logging

from broker.interfaces.coordination import (
    ActionProposal,
    ActionResolution,
    ResourceConflict,
    AgentMessage,
)
from broker.interfaces.event_generator import EventScope
from .conflict import ConflictResolver, ConflictDetector
from .messages import MessagePool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Coordinator Strategy (ABC)
# ---------------------------------------------------------------------------

class CoordinatorStrategy(ABC):
    """Pluggable strategy for resolving a batch of action proposals.

    Subclass this to implement custom resolution logic.
    The default strategies handle common patterns.
    """

    @abstractmethod
    def resolve(
        self,
        proposals: List[ActionProposal],
        shared_state: Dict[str, Any],
    ) -> List[ActionResolution]:
        """Resolve a batch of proposals.

        Args:
            proposals: All proposals for the current phase
            shared_state: Current environment/shared state

        Returns:
            List of resolutions (one per proposal)
        """
        ...


class PassthroughStrategy(CoordinatorStrategy):
    """Approve all proposals without modification.

    Use when no conflict resolution is needed (e.g., single-agent scenarios
    or phases where agents don't compete for resources).
    """

    def resolve(
        self,
        proposals: List[ActionProposal],
        shared_state: Dict[str, Any],
    ) -> List[ActionResolution]:
        return [
            ActionResolution(
                agent_id=p.agent_id,
                original_proposal=p,
                approved=True,
                event_statement=f"{p.agent_id} proceeds with {p.skill_name}.",
            )
            for p in proposals
        ]


class ConflictAwareStrategy(CoordinatorStrategy):
    """Resolve proposals using ConflictResolver for resource conflicts.

    Non-conflicting proposals are auto-approved. Conflicting proposals
    are resolved via the ConflictResolver's strategy.

    Args:
        resolver: ConflictResolver instance with resource limits
    """

    def __init__(self, resolver: ConflictResolver):
        self.resolver = resolver

    def resolve(
        self,
        proposals: List[ActionProposal],
        shared_state: Dict[str, Any],
    ) -> List[ActionResolution]:
        # Detect and resolve conflicts
        conflict_resolutions, conflicts = self.resolver.resolve_all(proposals)

        # Identify agents involved in conflicts
        conflicted_agents = set()
        for cr in conflict_resolutions:
            conflicted_agents.add(cr.agent_id)

        # Auto-approve non-conflicting proposals
        resolutions = []
        for proposal in proposals:
            if proposal.agent_id in conflicted_agents:
                continue  # Already resolved by ConflictResolver
            resolutions.append(ActionResolution(
                agent_id=proposal.agent_id,
                original_proposal=proposal,
                approved=True,
                event_statement=f"{proposal.agent_id} proceeds with {proposal.skill_name}.",
            ))

        resolutions.extend(conflict_resolutions)
        return resolutions


class CustomStrategy(CoordinatorStrategy):
    """Delegate resolution to a user-provided callable.

    Args:
        resolve_fn: Callable with signature
            (proposals, shared_state) -> List[ActionResolution]
    """

    def __init__(
        self,
        resolve_fn: Callable[
            [List[ActionProposal], Dict[str, Any]],
            List[ActionResolution],
        ],
    ):
        self._resolve_fn = resolve_fn

    def resolve(
        self,
        proposals: List[ActionProposal],
        shared_state: Dict[str, Any],
    ) -> List[ActionResolution]:
        return self._resolve_fn(proposals, shared_state)


# ---------------------------------------------------------------------------
# Game Master
# ---------------------------------------------------------------------------

class GameMaster:
    """Central coordinator for multi-agent action resolution.

    Collects proposals, resolves conflicts, generates event statements,
    and optionally broadcasts outcomes via MessagePool.

    Args:
        strategy: Resolution strategy (default: PassthroughStrategy)
        message_pool: Optional MessagePool for broadcasting resolutions
        event_statement_fn: Optional custom function to generate NL statements.
            Signature: (ActionResolution) -> str
    """

    def __init__(
        self,
        strategy: Optional[CoordinatorStrategy] = None,
        message_pool: Optional[MessagePool] = None,
        event_statement_fn: Optional[Callable[[ActionResolution], str]] = None,
        cross_validator: Optional[Any] = None,
    ):
        self.strategy = strategy or PassthroughStrategy()
        self.message_pool = message_pool
        self._event_statement_fn = event_statement_fn
        self.cross_validator = cross_validator
        self._resolution_history: List[ActionResolution] = []
        self._phase_proposals: List[ActionProposal] = []
        self._round_artifacts: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Proposal collection
    # ------------------------------------------------------------------

    def submit_proposal(self, proposal: ActionProposal) -> None:
        """Submit an action proposal for resolution.

        Call this during agent execution (e.g., in post_step hook)
        to collect proposals before batch resolution.
        """
        self._phase_proposals.append(proposal)

    def submit_proposals(self, proposals: List[ActionProposal]) -> None:
        """Submit multiple proposals at once."""
        self._phase_proposals.extend(proposals)

    def submit_artifact(self, envelope: "ArtifactEnvelope") -> None:
        """Submit a typed artifact and broadcast via MessagePool."""
        from broker.interfaces.artifacts import ArtifactEnvelope

        if not isinstance(envelope, ArtifactEnvelope):
            raise TypeError("submit_artifact expects an ArtifactEnvelope")

        msg = envelope.to_agent_message()
        if self.message_pool:
            self.message_pool.publish(msg)

        artifact = envelope.artifact
        atype = artifact.artifact_type()

        if atype == "HouseholdIntention":
            self._round_artifacts.setdefault("intentions", []).append(artifact)
        elif atype == "PolicyArtifact":
            self._round_artifacts["policy"] = artifact
        elif atype == "MarketArtifact":
            self._round_artifacts["market"] = artifact
        else:
            self._round_artifacts[envelope.source_agent] = envelope

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve_phase(
        self,
        shared_state: Optional[Dict[str, Any]] = None,
        proposals: Optional[List[ActionProposal]] = None,
    ) -> List[ActionResolution]:
        """Resolve all collected proposals for the current phase.

        Can use either proposals submitted via ``submit_proposal()``
        or explicitly passed proposals.

        Args:
            shared_state: Current environment state
            proposals: Optional explicit proposals (overrides submitted ones)

        Returns:
            List of resolutions
        """
        to_resolve = proposals if proposals is not None else self._phase_proposals
        state = shared_state or {}

        if not to_resolve:
            logger.debug("GameMaster: No proposals to resolve")
            return []

        resolutions = self.strategy.resolve(to_resolve, state)
        self._resolution_history.extend(resolutions)

        # Generate event statements
        for resolution in resolutions:
            if not resolution.event_statement and self._event_statement_fn:
                resolution.event_statement = self._event_statement_fn(resolution)

        # Broadcast via MessagePool if available
        if self.message_pool:
            self._broadcast_resolutions(resolutions)

        # Clear phase proposals
        self._phase_proposals.clear()

        logger.info(
            "GameMaster: Resolved %d proposals -> %d approved, %d denied",
            len(to_resolve),
            sum(1 for r in resolutions if r.approved),
            sum(1 for r in resolutions if not r.approved),
        )

        # Cross-agent validation (optional)
        if self.cross_validator and self._round_artifacts:
            results = self.cross_validator.validate_round(self._round_artifacts, resolutions)
            for r in results:
                if not r.is_valid:
                    logger.warning("[CrossValidation] %s: %s", r.rule_id, r.message)
            self._round_artifacts.clear()

        return resolutions

    # ------------------------------------------------------------------
    # Resolution lookup
    # ------------------------------------------------------------------

    def get_resolution(self, agent_id: str) -> Optional[ActionResolution]:
        """Get the most recent resolution for an agent.

        Args:
            agent_id: Agent to look up

        Returns:
            Most recent ActionResolution, or None
        """
        for resolution in reversed(self._resolution_history):
            if resolution.agent_id == agent_id:
                return resolution
        return None

    def get_resolutions_for_step(
        self, step: Optional[int] = None
    ) -> List[ActionResolution]:
        """Get all resolutions, optionally filtered.

        For now returns all resolutions from the most recent
        resolve_phase() call.
        """
        return list(self._resolution_history)

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    def _broadcast_resolutions(self, resolutions: List[ActionResolution]) -> None:
        """Publish resolution outcomes to MessagePool."""
        for resolution in resolutions:
            if not resolution.event_statement:
                continue
            msg = AgentMessage(
                sender_id="game_master",
                sender_type="coordinator",
                message_type="resolution",
                content=resolution.event_statement,
                data=resolution.to_dict(),
                recipients=[resolution.agent_id],
                scope=EventScope.AGENT,
            )
            self.message_pool.publish(msg)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset_phase(self) -> None:
        """Clear current phase proposals (call at start of each step)."""
        self._phase_proposals.clear()

    def reset(self) -> None:
        """Full reset (new simulation)."""
        self._phase_proposals.clear()
        self._resolution_history.clear()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @property
    def resolution_history(self) -> List[ActionResolution]:
        """Full resolution history across all phases."""
        return list(self._resolution_history)

    def summary(self) -> Dict[str, Any]:
        """Return coordinator statistics."""
        total = len(self._resolution_history)
        approved = sum(1 for r in self._resolution_history if r.approved)
        denied = total - approved
        return {
            "total_resolutions": total,
            "approved": approved,
            "denied": denied,
            "approval_rate": approved / total if total > 0 else 0.0,
            "strategy": type(self.strategy).__name__,
            "has_message_pool": self.message_pool is not None,
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_game_master(
    resource_limits: Optional[Dict[str, float]] = None,
    message_pool: Optional[MessagePool] = None,
    strategy_type: str = "passthrough",
    type_priorities: Optional[Dict[str, int]] = None,
) -> GameMaster:
    """Factory function for creating a GameMaster.

    Args:
        resource_limits: Resource constraints (enables conflict-aware strategy)
        message_pool: Optional MessagePool for broadcasting
        strategy_type: "passthrough" | "conflict_aware" | "priority"
        type_priorities: Agent type priority mapping (for conflict resolution)

    Returns:
        Configured GameMaster instance
    """
    if strategy_type == "passthrough" or not resource_limits:
        strategy = PassthroughStrategy()
    elif strategy_type in ("conflict_aware", "priority"):
        from .conflict import PriorityResolution
        detector = ConflictDetector(resource_limits)
        resolution_strategy = PriorityResolution(type_priorities)
        resolver = ConflictResolver(detector, resolution_strategy)
        strategy = ConflictAwareStrategy(resolver)
    else:
        strategy = PassthroughStrategy()

    return GameMaster(strategy=strategy, message_pool=message_pool)


__all__ = [
    "CoordinatorStrategy",
    "PassthroughStrategy",
    "ConflictAwareStrategy",
    "CustomStrategy",
    "GameMaster",
    "create_game_master",
]
