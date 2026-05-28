"""
Generic artifact protocol for inter-agent structured communication.

Provides:
- AgentArtifact: Abstract base for all typed artifacts
- ArtifactEnvelope: Wrapper that converts any artifact into an AgentMessage

Domain-specific artifact subclasses (e.g. PolicyArtifact, MarketArtifact)
should live in the domain module (examples/multi_agent/flood/protocols/artifacts.py),
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


# --- Routing maps (populated by domain modules via register_artifact_routing) ---
_TYPE_MAP: Dict[str, Any] = {}
_SENDER_MAP: Dict[str, str] = {}


# ─────────────────────────────────────────────────────────────────────────
# Phase 6U-E-2: Coordinator artifact-dispatch registry
# ─────────────────────────────────────────────────────────────────────────
#
# Replaces the previously-hardcoded ``if atype == "HouseholdIntention": ...
# elif atype == "PolicyArtifact": ... elif atype == "MarketArtifact":``
# block in ``broker/components/coordination/coordinator.py``. Domain
# modules register their artifact dispatch rules at import time; the
# coordinator iterates the registry rather than naming any specific
# water/flood artifact type.
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ArtifactDispatchRule:
    """How the coordinator should bucket an incoming artifact.

    Attributes:
        artifact_type: The string returned by ``artifact.artifact_type()``
            (e.g. ``"HouseholdIntention"``, ``"PolicyArtifact"``).
        bucket: Key under ``Coordinator._round_artifacts`` where the
            artifact lands (e.g. ``"intentions"``, ``"policy"``, ``"market"``).
        mode: ``"append"`` (list-of-artifacts) or ``"single"``
            (last-write-wins for the bucket).
    """
    artifact_type: str
    bucket: str
    mode: str  # "append" or "single"


_DISPATCH_RULES: Dict[str, ArtifactDispatchRule] = {}


def register_artifact_dispatch_rule(
    artifact_type: str,
    bucket: str,
    mode: str = "single",
    *,
    overwrite: bool = False,
) -> None:
    """Register how the coordinator should bucket an artifact_type.

    Call this from a domain module at import time. ``mode`` is
    ``"append"`` for many-per-round (household intentions accumulate)
    or ``"single"`` for last-write-wins (policy / market). Unknown
    ``mode`` raises ``ValueError``.

    Idempotent re-registration (same ``bucket`` and ``mode``) is a
    no-op — supports the import-time registration pattern where two
    different code paths may import the same domain module. A
    CONFLICTING re-registration (different ``bucket`` or ``mode``)
    raises ``ValueError`` unless ``overwrite=True`` is passed
    explicitly. This guards the v0.88.15-class silent failure where a
    second domain or a misordered reload silently rewires the
    coordinator dispatch and the original domain's cross-validators
    suddenly see ``None`` in their bucket lookup, dropping every
    governance violation in the round without a log entry.
    """
    if mode not in ("append", "single"):
        raise ValueError(
            f"ArtifactDispatchRule mode must be 'append' or 'single', got {mode!r}"
        )
    existing = _DISPATCH_RULES.get(artifact_type)
    if existing is not None and not overwrite:
        if existing.bucket == bucket and existing.mode == mode:
            return  # idempotent re-registration is a no-op
        raise ValueError(
            f"Conflicting ArtifactDispatchRule for {artifact_type!r}: "
            f"existing=(bucket={existing.bucket!r}, mode={existing.mode!r}), "
            f"new=(bucket={bucket!r}, mode={mode!r}). "
            f"Pass overwrite=True to replace intentionally."
        )
    _DISPATCH_RULES[artifact_type] = ArtifactDispatchRule(
        artifact_type=artifact_type, bucket=bucket, mode=mode
    )


def get_artifact_dispatch_rule(artifact_type: str) -> Optional[ArtifactDispatchRule]:
    """Look up the dispatch rule for an artifact type. Returns ``None``
    if no rule is registered (coordinator falls back to per-source
    bucketing)."""
    return _DISPATCH_RULES.get(artifact_type)


def clear_artifact_dispatch_rules() -> None:
    """Test-only helper: clear all registered dispatch rules."""
    _DISPATCH_RULES.clear()


# Stable broker-facing fallbacks. Domain implementations may subclass
# AgentArtifact separately, but the broker should not import example code here.
class _FallbackArtifact(AgentArtifact):
    """Fallback artifact placeholder for broker-facing tests and routing."""

    def __init__(self, **kwargs: Any) -> None:
        agent_id = kwargs.pop("agent_id", "")
        year = kwargs.pop("year", 0)
        rationale = kwargs.pop("rationale", "")
        super().__init__(agent_id=agent_id, year=year, rationale=rationale)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def artifact_type(self) -> str:
        return self.__class__.__name__

    def validate(self) -> List[str]:
        return []


PolicyArtifact = type("PolicyArtifact", (_FallbackArtifact,), {})  # type: ignore
MarketArtifact = type("MarketArtifact", (_FallbackArtifact,), {})  # type: ignore
HouseholdIntention = type("HouseholdIntention", (_FallbackArtifact,), {})  # type: ignore


__all__ = [
    "AgentArtifact",
    "ArtifactEnvelope",
    "register_artifact_routing",
    "PolicyArtifact",
    "MarketArtifact",
    "HouseholdIntention",
]
