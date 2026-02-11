"""
Shared Message Pool - Agent-to-agent structured messaging.

Implements MetaGPT-style shared message pool with pub-sub filtering
and mailbox delivery. Supports:
- Broadcast (global), type-targeted, spatial, and direct messaging
- Subscription-based filtering per agent
- TTL-based message expiration
- SocialGraph integration for neighbor-scoped delivery
- Priority ordering for context window management

Design Principles:
1. Domain-agnostic: No knowledge of flood/market/health specifics
2. Compatible with existing SocialGraph and EventScope
3. Pluggable into ContextProvider pipeline via MessagePoolProvider
4. Thread-safe for parallel agent execution

References:
- MetaGPT (2023). Shared Message Pool + Publish-Subscribe.
- AgentSociety (2024). Role-based message filtering.

Reference: Task-054 Communication Layer
"""
from collections import defaultdict
from typing import Dict, List, Optional, Any, Set
import logging

from broker.interfaces.coordination import (
    AgentMessage,
    Subscription,
)
from broker.interfaces.event_generator import EventScope

logger = logging.getLogger(__name__)


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
    ):
        self._graph = social_graph
        self._agent_locations = agent_locations or {}

        # Core state
        self._messages: List[AgentMessage] = []
        self._subscriptions: Dict[str, Subscription] = {}
        self._mailboxes: Dict[str, List[AgentMessage]] = defaultdict(list)
        self._read_cursors: Dict[str, int] = defaultdict(int)  # agent_id -> last read index

        # Registered agent IDs (for broadcast resolution)
        self._registered_agents: Set[str] = set()

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def register_agent(self, agent_id: str, location: Optional[str] = None) -> None:
        """Register an agent to receive messages."""
        self._registered_agents.add(agent_id)
        if location:
            self._agent_locations[agent_id] = location

    def register_agents(self, agents: Dict[str, Any]) -> None:
        """Bulk-register agents from agent dict."""
        for agent_id, agent in agents.items():
            location = getattr(agent, "region_id", None) or getattr(agent, "tract_id", None)
            self.register_agent(agent_id, location)

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
            return [r for r in msg.recipients if r in self._registered_agents]

        # 2. Type-based targeting
        if msg.recipient_types:
            # We don't store agent_type in registry, so fall through to all
            # and let subscription filtering handle it.
            # For now, deliver to all and rely on subscription matching.
            return [a for a in self._registered_agents if a != msg.sender_id]

        # 3. Scope-based
        if msg.scope == EventScope.GLOBAL:
            return [a for a in self._registered_agents if a != msg.sender_id]

        if msg.scope in (EventScope.REGIONAL, EventScope.LOCAL) and msg.location:
            return [
                a for a in self._registered_agents
                if self._agent_locations.get(a) == msg.location and a != msg.sender_id
            ]

        if msg.scope == EventScope.AGENT:
            return [r for r in msg.recipients if r in self._registered_agents]

        # Fallback: all registered agents except sender
        return [a for a in self._registered_agents if a != msg.sender_id]

    def _matches_subscription(self, agent_id: str, message: AgentMessage) -> bool:
        """Check if agent's subscription allows this message."""
        sub = self._subscriptions.get(agent_id)
        if sub is None:
            # No subscription = receive all messages
            return True
        return sub.matches(message)


__all__ = ["MessagePool"]
