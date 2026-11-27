"""
Shared Message Pool - Agent-to-agent structured messaging.

STATUS: EXPERIMENTAL (Multi-Actor / Coordination Extension — Pre-1.0 API).
Wired into multi-actor simulations via ``MultiActorLifecycleBridge`` (``run.coordinator``
slot on ``python -m broker.run``) and ``GameMaster``; inactive on default single-agent runs.

Implements MetaGPT-style shared message pool with pub-sub filtering
and mailbox delivery. Supports:
- Broadcast (global), type-targeted, spatial, and direct messaging
- Subscription-based filtering per agent
- TTL-based message expiration
- SocialGraph integration for neighbor-scoped delivery
- Priority ordering for context window management

Design Principles:
1. Domain-agnostic: No knowledge of specific application domains
2. Compatible with existing SocialGraph and EventScope
3. Pluggable into ContextProvider pipeline via MessagePoolProvider
4. Thread-safe for parallel agent execution

References:
- MetaGPT (2023). Shared Message Pool + Publish-Subscribe.
- AgentSociety (2024). Role-based message filtering.
"""
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Dict, List, Optional, Any, Set, Tuple
import logging

from broker.interfaces.coordination import (
    AgentMessage,
    Subscription,
)
from broker.interfaces.event_generator import EventScope

logger = logging.getLogger(__name__)

DEFAULT_LOCATION_ATTRS: Tuple[str, ...] = ("location", "region_id", "tract_id")


def normalize_location_attrs(
    location_attrs: Optional[Sequence[str]] = None,
) -> Tuple[str, ...]:
    """Validate and normalize an ordered tuple of agent location attribute names."""
    if location_attrs is None:
        return DEFAULT_LOCATION_ATTRS
    if isinstance(location_attrs, str):
        items: Sequence[Any] = (location_attrs,)
    elif isinstance(location_attrs, Sequence) and not isinstance(location_attrs, (bytes, bytearray)):
        items = location_attrs
    else:
        raise ValueError("location_attrs must be a non-empty sequence of attribute names")
    cleaned: List[str] = []
    for attr in items:
        if type(attr) is not str or not attr.strip():
            raise ValueError(f"location_attrs entries must be non-empty strings, got {attr!r}")
        cleaned.append(attr.strip())
    if not cleaned:
        raise ValueError("location_attrs must not be empty")
    return tuple(dict.fromkeys(cleaned))


def coerce_location_value(value: Any) -> Optional[str]:
    """Return a clean string location for a hashable scalar value, else ``None``."""
    if value is None or isinstance(value, (bool, tuple, list, dict, set, frozenset, bytes, bytearray)):
        return None
    try:
        hash(value)
    except TypeError:
        return None
    text = str(value).strip()
    return text or None


def resolve_agent_location(
    agent: Any,
    location_attrs: Sequence[str] = DEFAULT_LOCATION_ATTRS,
) -> Optional[str]:
    """Read the first non-empty scalar location attribute configured for ``agent``."""
    if agent is None:
        return None
    for attr in location_attrs:
        val = coerce_location_value(getattr(agent, attr, None))
        if val is not None:
            return val
    return None


class MessagePool:
    """Shared message pool for multi-agent communication.

    Provides pub-sub messaging with mailbox delivery, supporting
    multiple scopes (global, regional, neighbor, direct) and
    subscription-based filtering.

    Args:
        social_graph: Optional SocialGraph for neighbor-scoped delivery.
            If provided, enables ``send_to_neighbors()`` routing.
        agent_locations: Optional mapping of agent_id -> location string
            for REGIONAL/LOCAL scope filtering.
    """

    def __init__(
        self,
        social_graph: Optional[Any] = None,
        agent_locations: Optional[Dict[str, str]] = None,
        *,
        location_attrs: Optional[Sequence[str]] = None,
    ):
        self._graph = social_graph
        self._location_attrs: Tuple[str, ...] = normalize_location_attrs(location_attrs)
        self._explicit_locations: Dict[str, str] = {}
        self._agent_locations: Dict[str, str] = {}
        for aid, loc in (agent_locations or {}).items():
            cleaned = coerce_location_value(loc)
            if cleaned is not None:
                self._explicit_locations[aid] = cleaned
                self._agent_locations[aid] = cleaned
        self._inferred_location_agents: Set[str] = set()
        self._agent_types: Dict[str, str] = {}

        # Core state
        self._messages: List[AgentMessage] = []
        self._subscriptions: Dict[str, Subscription] = {}
        self._mailboxes: Dict[str, List[AgentMessage]] = defaultdict(list)
        self._read_cursors: Dict[str, int] = defaultdict(int)  # agent_id -> last read index

        # Registered agent IDs (for broadcast resolution)
        self._registered_agents: Set[str] = set()
        self._inactive_agents: Set[str] = set()

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def set_agent_active(self, agent_id: str, active: bool = True) -> None:
        """Track whether ``agent_id`` is active and eligible to receive messages."""
        if active:
            self._inactive_agents.discard(agent_id)
        else:
            self._inactive_agents.add(agent_id)

    def update_agent_location(
        self,
        agent_id: str,
        location: Optional[str],
        *,
        explicit: bool = True,
    ) -> None:
        """Set or clear an agent's cached location."""
        cleaned = coerce_location_value(location)
        if cleaned is None:
            if explicit:
                self._explicit_locations.pop(agent_id, None)
            self._inferred_location_agents.discard(agent_id)
            fallback = None if explicit else self._explicit_locations.get(agent_id)
            if fallback is not None:
                self._agent_locations[agent_id] = fallback
            else:
                self._agent_locations.pop(agent_id, None)
            return

        self._agent_locations[agent_id] = cleaned
        if explicit:
            self._explicit_locations[agent_id] = cleaned
            self._inferred_location_agents.discard(agent_id)
        else:
            self._inferred_location_agents.add(agent_id)

    def refresh_agent_locations(self, agents: Mapping[str, Any]) -> None:
        """Sync inferred locations, types, and active flags from live agent objects."""
        for agent_id, agent in agents.items():
            self.set_agent_active(agent_id, getattr(agent, "is_active", True) is not False)
            atype = getattr(agent, "agent_type", None)
            if isinstance(atype, str) and atype:
                self._agent_types[agent_id] = atype
            live_loc = resolve_agent_location(agent, self._location_attrs)
            if live_loc is not None:
                self.update_agent_location(agent_id, live_loc, explicit=False)
            elif agent_id in self._inferred_location_agents:
                self.update_agent_location(agent_id, None, explicit=False)

    def register_agent(
        self,
        agent_id: str,
        location: Optional[str] = None,
        *,
        agent_type: Optional[str] = None,
        active: bool = True,
    ) -> None:
        """Register an agent to receive messages."""
        self._registered_agents.add(agent_id)
        self.set_agent_active(agent_id, active)
        if isinstance(agent_type, str) and agent_type:
            self._agent_types[agent_id] = agent_type
        if location is not None:
            self.update_agent_location(agent_id, location, explicit=True)

    def register_agents(self, agents: Dict[str, Any]) -> None:
        """Bulk-register agents from agent dict."""
        for agent_id, agent in agents.items():
            atype = getattr(agent, "agent_type", None)
            self.register_agent(
                agent_id,
                agent_type=atype if isinstance(atype, str) and atype else None,
                active=getattr(agent, "is_active", True) is not False,
            )
            live_loc = resolve_agent_location(agent, self._location_attrs)
            if live_loc is not None:
                self.update_agent_location(agent_id, live_loc, explicit=False)
            elif agent_id in self._inferred_location_agents:
                self.update_agent_location(agent_id, None, explicit=False)

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(
        self,
        agent_id: str,
        message_types: Optional[List[str]] = None,
        source_types: Optional[List[str]] = None,
    ) -> None:
        """Register an agent's interest in specific message types.

        Args:
            agent_id: Subscribing agent
            message_types: Message types to receive (None = all)
            source_types: Source agent types to receive from (None = all)
        """
        self._subscriptions[agent_id] = Subscription(
            agent_id=agent_id,
            message_types=message_types or [],
            source_types=source_types or [],
        )

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(self, message: AgentMessage) -> int:
        """Add a message to the pool and distribute to mailboxes.

        Args:
            message: The message to publish

        Returns:
            Number of agents the message was delivered to
        """
        self._messages.append(message)
        recipients = self._resolve_recipients(message)
        delivered = 0
        for agent_id in recipients:
            if self._matches_subscription(agent_id, message):
                self._mailboxes[agent_id].append(message)
                delivered += 1
        logger.debug(
            "MessagePool: %s(%s) published '%s' -> %d recipients",
            message.sender_id, message.sender_type,
            message.message_type, delivered,
        )
        return delivered

    def broadcast(
        self,
        sender_id: str,
        sender_type: str,
        content: str,
        message_type: str = "announcement",
        data: Optional[Dict[str, Any]] = None,
        timestamp: int = 0,
        priority: int = 0,
    ) -> AgentMessage:
        """Convenience: broadcast a message to all registered agents.

        Args:
            sender_id: Sending agent ID
            sender_type: Sending agent type (e.g., "government")
            content: Natural language message body
            message_type: Message category
            data: Structured payload
            timestamp: Simulation step
            priority: Message importance

        Returns:
            The created AgentMessage
        """
        msg = AgentMessage(
            sender_id=sender_id,
            sender_type=sender_type,
            message_type=message_type,
            content=content,
            data=data or {},
            scope=EventScope.GLOBAL,
            timestamp=timestamp,
            priority=priority,
        )
        self.publish(msg)
        return msg

    def send_to_neighbors(
        self,
        sender_id: str,
        content: str,
        message_type: str = "neighbor_info",
        data: Optional[Dict[str, Any]] = None,
        timestamp: int = 0,
    ) -> AgentMessage:
        """Send a message to social graph neighbors only.

        Requires a SocialGraph to be provided at construction time.

        Args:
            sender_id: Sending agent ID
            content: Natural language message body
            message_type: Message category
            data: Structured payload
            timestamp: Simulation step

        Returns:
            The created AgentMessage
        """
        sender_type = ""  # Will be resolved from registration or left empty
        neighbors = []
        if self._graph:
            neighbors = self._graph.get_neighbors(sender_id)

        msg = AgentMessage(
            sender_id=sender_id,
            sender_type=sender_type,
            message_type=message_type,
            content=content,
            data=data or {},
            recipients=neighbors,
            scope=EventScope.AGENT,
            timestamp=timestamp,
        )
        self.publish(msg)
        return msg

    def send_direct(
        self,
        sender_id: str,
        sender_type: str,
        recipient_id: str,
        content: str,
        message_type: str = "direct",
        data: Optional[Dict[str, Any]] = None,
        timestamp: int = 0,
    ) -> AgentMessage:
        """Send a message to a specific agent.

        Args:
            sender_id: Sending agent ID
            sender_type: Sending agent type
            recipient_id: Target agent ID
            content: Natural language message body
            message_type: Message category
            data: Structured payload
            timestamp: Simulation step

        Returns:
            The created AgentMessage
        """
        msg = AgentMessage(
            sender_id=sender_id,
            sender_type=sender_type,
            message_type=message_type,
            content=content,
            data=data or {},
            recipients=[recipient_id],
            scope=EventScope.AGENT,
            timestamp=timestamp,
        )
        self.publish(msg)
        return msg

    # ------------------------------------------------------------------
    # Receiving
    # ------------------------------------------------------------------

    def get_messages(
        self,
        agent_id: str,
        since_step: int = 0,
        message_types: Optional[List[str]] = None,
    ) -> List[AgentMessage]:
        """Retrieve messages for an agent.

        Args:
            agent_id: Requesting agent
            since_step: Only return messages from this step onward
            message_types: Optional filter by message type

        Returns:
            List of messages matching criteria, sorted by priority (desc)
        """
        mailbox = self._mailboxes.get(agent_id, [])
        result = []
        for msg in mailbox:
            if msg.timestamp < since_step:
                continue
            if message_types and msg.message_type not in message_types:
                continue
            result.append(msg)
        # Sort by priority descending, then timestamp descending
        result.sort(key=lambda m: (-m.priority, -m.timestamp))
        return result

    def get_unread(self, agent_id: str) -> List[AgentMessage]:
        """Get messages the agent hasn't consumed yet.

        Tracks a read cursor per agent. Each call returns new messages
        and advances the cursor.

        Returns:
            List of unread messages
        """
        mailbox = self._mailboxes.get(agent_id, [])
        cursor = self._read_cursors.get(agent_id, 0)
        unread = mailbox[cursor:]
        self._read_cursors[agent_id] = len(mailbox)
        return unread

    def peek_count(self, agent_id: str) -> int:
        """Return number of messages in agent's mailbox."""
        return len(self._mailboxes.get(agent_id, []))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def advance_step(self, current_step: int) -> int:
        """Expire messages past their TTL.

        Called at the beginning of each simulation step (e.g., pre_year hook).

        Args:
            current_step: Current simulation step/year

        Returns:
            Number of messages expired
        """
        expired_count = 0
        # Filter global message list
        surviving = []
        for msg in self._messages:
            if msg.ttl > 0 and (current_step - msg.timestamp) >= msg.ttl:
                expired_count += 1
            else:
                surviving.append(msg)
        self._messages = surviving

        # Filter mailboxes
        for agent_id in list(self._mailboxes.keys()):
            before = len(self._mailboxes[agent_id])
            self._mailboxes[agent_id] = [
                m for m in self._mailboxes[agent_id]
                if not (m.ttl > 0 and (current_step - m.timestamp) >= m.ttl)
            ]
            # Adjust read cursors if messages were removed
            after = len(self._mailboxes[agent_id])
            if after < before and self._read_cursors[agent_id] > after:
                self._read_cursors[agent_id] = after

        if expired_count > 0:
            logger.debug("MessagePool: Expired %d messages at step %d", expired_count, current_step)
        return expired_count

    def clear(self) -> None:
        """Reset all messages and mailboxes."""
        self._messages.clear()
        self._mailboxes.clear()
        self._read_cursors.clear()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Return pool statistics."""
        return {
            "total_messages": len(self._messages),
            "registered_agents": len(self._registered_agents),
            "subscriptions": len(self._subscriptions),
            "mailbox_sizes": {
                aid: len(msgs) for aid, msgs in self._mailboxes.items()
                if len(msgs) > 0
            },
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_recipients(self, msg: AgentMessage) -> List[str]:
        """Determine who receives a message based on scope and targeting."""
        # 1. Explicit recipients
        if msg.recipients:
            recipients = [
                r for r in dict.fromkeys(msg.recipients)
                if r in self._registered_agents
                and r not in self._inactive_agents
                and r != msg.sender_id
            ]
            if msg.recipient_types:
                allowed = set(msg.recipient_types)
                return [r for r in recipients if self._agent_types.get(r) in allowed]
            return recipients

        # 2. Scope-based candidate selection
        if msg.scope in (EventScope.REGIONAL, EventScope.LOCAL):
            if not msg.location:
                return []
            candidates = [
                a for a in self._registered_agents
                if a not in self._inactive_agents
                and self._agent_locations.get(a) == msg.location
                and a != msg.sender_id
            ]
        elif msg.scope == EventScope.AGENT:
            return []
        elif msg.scope == EventScope.GLOBAL:
            candidates = [
                a for a in self._registered_agents
                if a not in self._inactive_agents and a != msg.sender_id
            ]
        else:
            return []

        # 3. Type-based filtering
        if msg.recipient_types:
            allowed = set(msg.recipient_types)
            return [a for a in candidates if self._agent_types.get(a) in allowed]

        return candidates

    def _matches_subscription(self, agent_id: str, message: AgentMessage) -> bool:
        """Check if agent's subscription allows this message."""
        sub = self._subscriptions.get(agent_id)
        if sub is None:
            # No subscription = receive all messages
            return True
        return sub.matches(message)


__all__ = [
    "DEFAULT_LOCATION_ATTRS",
    "MessagePool",
    "coerce_location_value",
    "normalize_location_attrs",
    "resolve_agent_location",
]
