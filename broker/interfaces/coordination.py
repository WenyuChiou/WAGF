"""
Coordination Types - Core type definitions for MAS Communication Layer.

Design Principles:
1. Domain-agnostic: Types support any multi-agent coordination scenario
2. Compatible with existing EventScope from event_generator.py
3. Follows framework dataclass + Enum conventions
4. Supports Concordia-style Game Master and MetaGPT-style Message Pool

References:
- Concordia (2024). Action Resolution via Game Master.
- MetaGPT (2023). Shared Message Pool with Pub-Sub.
- AgentSociety (2024). Phase-based Execution with Time Alignment.

Reference: Task-054 Communication Layer
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

from broker.interfaces.event_generator import EventScope


# ---------------------------------------------------------------------------
# Phase Orchestration
# ---------------------------------------------------------------------------

class ExecutionPhase(Enum):
    """Multi-agent execution phases within a simulation step."""
    INSTITUTIONAL = "institutional"   # Government, Insurance agents
    HOUSEHOLD = "household"           # Household agents (all sub-types)
    RESOLUTION = "resolution"         # Conflict resolution + GM adjudication
    OBSERVATION = "observation"       # Post-action observable state updates
    CUSTOM = "custom"                 # User-defined phase


@dataclass
class PhaseConfig:
    """Configuration for one execution phase.

    Args:
        phase: Which execution phase
        agent_types: Agent types included in this phase
        ordering: How agents execute within the phase
        max_workers: Parallelism for 'parallel' ordering
        depends_on: Phases that must complete before this one
    """
    phase: ExecutionPhase
    agent_types: List[str] = field(default_factory=list)
    ordering: str = "sequential"   # "sequential" | "parallel" | "random"
    max_workers: int = 1
    depends_on: List[ExecutionPhase] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Action Coordination (Game Master)
# ---------------------------------------------------------------------------

@dataclass
class ActionProposal:
    """Agent's proposed action before Game Master resolution.

    Created from SkillProposal after governance validation,
    enriched with resource requirements for conflict detection.

    Args:
        agent_id: Proposing agent
        agent_type: Agent type (for priority ordering)
        skill_name: Proposed skill/action
        reasoning: Decision rationale (from SkillProposal.reasoning)
        resource_requirements: Resources needed (e.g., {"budget": 75000})
        priority: Resolution priority (higher = more priority)
        metadata: Additional context for resolution
    """
    agent_id: str
    agent_type: str
    skill_name: str
    reasoning: Dict[str, str] = field(default_factory=dict)
    resource_requirements: Dict[str, float] = field(default_factory=dict)
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "skill_name": self.skill_name,
            "reasoning": self.reasoning,
            "resource_requirements": self.resource_requirements,
            "priority": self.priority,
        }


@dataclass
class ActionResolution:
    """Game Master's resolution of an action proposal.

    Args:
        agent_id: Agent whose action was resolved
        original_proposal: The proposal being resolved
        approved: Whether the action was approved
        modified_skill: Alternative skill if GM substituted
        event_statement: Natural language consequence description
        state_changes: State mutations to apply
        denial_reason: Why the action was denied (if not approved)
    """
    agent_id: str
    original_proposal: ActionProposal
    approved: bool
    modified_skill: Optional[str] = None
    event_statement: str = ""
    state_changes: Dict[str, Any] = field(default_factory=dict)
    denial_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "approved": self.approved,
            "original_skill": self.original_proposal.skill_name,
            "modified_skill": self.modified_skill,
            "event_statement": self.event_statement,
            "state_changes": self.state_changes,
            "denial_reason": self.denial_reason,
        }


# ---------------------------------------------------------------------------
# Conflict Resolution
# ---------------------------------------------------------------------------

@dataclass
class ResourceConflict:
    """Detected conflict between agent proposals.

    Args:
        resource_key: Contested resource identifier
        total_requested: Sum of all agents' requests
        available: Current available amount
        competing_agents: Agent IDs competing for the resource
        conflict_type: Category of conflict
    """
    resource_key: str
    total_requested: float
    available: float
    competing_agents: List[str] = field(default_factory=list)
    conflict_type: str = "over_allocation"  # "over_allocation" | "mutual_exclusion" | "ordering"

    @property
    def deficit(self) -> float:
        """How much the request exceeds availability."""
        return max(0.0, self.total_requested - self.available)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_key": self.resource_key,
            "total_requested": self.total_requested,
            "available": self.available,
            "deficit": self.deficit,
            "competing_agents": self.competing_agents,
            "conflict_type": self.conflict_type,
        }


# ---------------------------------------------------------------------------
# Agent Messaging (Shared Message Pool)
# ---------------------------------------------------------------------------

class MessageType(Enum):
    """Standard message categories."""
    POLICY_ANNOUNCEMENT = "policy_announcement"
    MARKET_UPDATE = "market_update"
    NEIGHBOR_WARNING = "neighbor_warning"
    NEIGHBOR_INFO = "neighbor_info"
    MEDIA_BROADCAST = "media_broadcast"
    REQUEST = "request"
    RESPONSE = "response"
    CUSTOM = "custom"


@dataclass
class AgentMessage:
    """Structured message between agents.

    Compatible with EnvironmentEvent for integration with existing
    event manager, but designed for agent-to-agent communication.

    Args:
        sender_id: Sending agent identifier
        sender_type: Sending agent type
        message_type: Category of message
        content: Natural language message body
        data: Structured payload (domain-specific)
        recipients: Explicit recipient agent IDs (empty = use scope)
        recipient_types: Target agent types (for type-based filtering)
        scope: Spatial scope (reuses EventScope from event_generator)
        location: Target location for REGIONAL/LOCAL scope
        timestamp: Simulation year/step when sent
        priority: Message importance (higher = more important)
        reliability: Message fidelity 0.0-1.0 (1.0 = perfect)
        ttl: Time-to-live in simulation steps (0 = no expiry)
    """
    sender_id: str
    sender_type: str
    message_type: str
    content: str
    data: Dict[str, Any] = field(default_factory=dict)
    recipients: List[str] = field(default_factory=list)
    recipient_types: List[str] = field(default_factory=list)
    scope: EventScope = EventScope.GLOBAL
    location: Optional[str] = None
    timestamp: int = 0
    priority: int = 0
    reliability: float = 1.0
    ttl: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender_id": self.sender_id,
            "sender_type": self.sender_type,
            "message_type": self.message_type,
            "content": self.content,
            "data": self.data,
            "recipients": self.recipients,
            "recipient_types": self.recipient_types,
            "scope": self.scope.value,
            "location": self.location,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "reliability": self.reliability,
            "ttl": self.ttl,
        }


@dataclass
class Subscription:
    """Agent's subscription to message types.

    Args:
        agent_id: Subscribing agent
        message_types: Interested message types (empty = all)
        source_types: Interested source agent types (empty = all)
    """
    agent_id: str
    message_types: List[str] = field(default_factory=list)
    source_types: List[str] = field(default_factory=list)

    def matches(self, message: AgentMessage) -> bool:
        """Check if a message matches this subscription."""
        if self.message_types and message.message_type not in self.message_types:
            return False
        if self.source_types and message.sender_type not in self.source_types:
            return False
        return True


__all__ = [
    "ExecutionPhase",
    "PhaseConfig",
    "ActionProposal",
    "ActionResolution",
    "ResourceConflict",
    "MessageType",
    "AgentMessage",
    "Subscription",
]
