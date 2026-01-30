"""
Generic artifact protocol for inter-agent structured communication.

Provides:
- AgentArtifact: Abstract base for all typed artifacts
- ArtifactEnvelope: Wrapper that converts any artifact into an AgentMessage

Domain-specific artifact subclasses (e.g. PolicyArtifact, MarketArtifact)
should live in the domain module (examples/multi_agent/ma_artifacts.py),
NOT in this file.

Reference: Task-058A (Structured Artifact Protocols)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentArtifact(ABC):
    """Base class for all typed inter-agent artifacts.

    Subclasses must implement:
    - artifact_type() -> str: Return a unique type identifier
    - validate() -> List[str]: Return validation error strings (empty = valid)

    Common fields shared by all artifact types:
    - agent_id: The agent that produced this artifact
    - year: Simulation year / step
    - rationale: Free-text explanation of the decision
    """
    agent_id: str
    year: int
    rationale: str

    @abstractmethod
    def artifact_type(self) -> str:
        """Return a unique identifier for this artifact type (e.g. 'PolicyArtifact')."""
        ...

    @abstractmethod
    def validate(self) -> List[str]:
        """Return a list of validation error strings. Empty list = valid."""
        ...

    def to_message_payload(self) -> Dict[str, Any]:
        """Serialize all fields to a dict payload for transport.

        Default implementation dumps all instance vars.
        Subclasses may override for custom serialization.
        """
        payload: Dict[str, Any] = {"artifact_type": self.artifact_type()}
        for k, v in vars(self).items():
            if not k.startswith("_"):
                payload[k] = v
        return payload


@dataclass
class ArtifactEnvelope:
    """Wrapper that converts any AgentArtifact into an AgentMessage.

    Args:
        artifact: The typed artifact to wrap
        source_agent: ID of the sending agent
        target_scope: "global" | "regional" | "direct"
        timestamp: Simulation step number
        message_type_override: Override automatic MessageType routing
        sender_type_override: Override automatic sender_type inference
    """
    artifact: AgentArtifact
    source_agent: str
    target_scope: str = "global"
    timestamp: int = 0
    message_type_override: Optional[str] = None
    sender_type_override: Optional[str] = None

    def to_agent_message(self):
        """Convert to AgentMessage for MessagePool integration.

        Routing is determined by:
        1. message_type_override / sender_type_override if set
        2. Otherwise, artifact.artifact_type() maps through _TYPE_MAP / _SENDER_MAP
        3. Falls back to POLICY_ANNOUNCEMENT / "unknown"
        """
        from broker.interfaces.coordination import AgentMessage, MessageType

        payload = self.artifact.to_message_payload()
        atype = self.artifact.artifact_type()
        rationale = getattr(self.artifact, "rationale", "")

        # Determine message type
        if self.message_type_override:
            msg_type = getattr(MessageType, self.message_type_override,
                               MessageType.POLICY_ANNOUNCEMENT)
        else:
            msg_type = _TYPE_MAP.get(atype, MessageType.POLICY_ANNOUNCEMENT)

        # Determine sender type
        sender_type = self.sender_type_override or _SENDER_MAP.get(atype, "unknown")

        msg = AgentMessage(
            sender_id=self.source_agent,
            sender_type=sender_type,
            message_type=msg_type,
            content=f"[{atype}] {rationale}",
            data=payload,
            timestamp=self.timestamp,
        )
        # Backwards-compat attributes for tests / legacy usage.
        setattr(msg, "sender", self.source_agent)
        setattr(msg, "step", self.timestamp)
        return msg


def register_artifact_routing(artifact_type: str, message_type_name: str,
                               sender_type: str) -> None:
    """Register a new artifact type for automatic message routing.

    Call this from domain modules to wire their artifact subclasses
    into the ArtifactEnvelope routing without modifying this file.

    Args:
        artifact_type: The string returned by artifact.artifact_type()
        message_type_name: Name of a MessageType enum member (e.g. "POLICY_ANNOUNCEMENT")
        sender_type: Sender type string (e.g. "government")
    """
    from broker.interfaces.coordination import MessageType
    _TYPE_MAP[artifact_type] = getattr(MessageType, message_type_name)
    _SENDER_MAP[artifact_type] = sender_type


# --- Default routing maps (populated by domain modules via register_artifact_routing) ---
# Importing MessageType at module level would create a circular import,
# so we lazy-populate these on first use.
_TYPE_MAP: Dict[str, Any] = {}
_SENDER_MAP: Dict[str, str] = {}


def _ensure_default_routing() -> None:
    """Populate default routing maps if empty.

    Called internally; domain modules should call register_artifact_routing()
    to add their own mappings.
    """
    if not _TYPE_MAP:
        from broker.interfaces.coordination import MessageType
        _TYPE_MAP.update({
            "PolicyArtifact": MessageType.POLICY_ANNOUNCEMENT,
            "MarketArtifact": MessageType.MARKET_UPDATE,
            "HouseholdIntention": MessageType.NEIGHBOR_WARNING,
        })
        _SENDER_MAP.update({
            "PolicyArtifact": "government",
            "MarketArtifact": "insurance",
            "HouseholdIntention": "household",
        })


# Ensure defaults on import (lazy — only resolves MessageType when first accessed)
try:
    _ensure_default_routing()
except ImportError:
    pass  # coordination module not yet available; will populate on first use


# --- Optional re-exports for domain artifacts (test convenience) ---
# Some test modules import PolicyArtifact/MarketArtifact/HouseholdIntention
# directly from broker.interfaces.artifacts. Re-export if available.
try:
    from examples.multi_agent.ma_artifacts import (  # type: ignore
        PolicyArtifact,
        MarketArtifact,
        HouseholdIntention,
    )
except Exception:
    # Keep imports optional to avoid hard dependency on example modules.
    PolicyArtifact = None  # type: ignore
    MarketArtifact = None  # type: ignore
    HouseholdIntention = None  # type: ignore


__all__ = [
    "AgentArtifact",
    "ArtifactEnvelope",
    "register_artifact_routing",
    "PolicyArtifact",
    "MarketArtifact",
    "HouseholdIntention",
]
