"""
Memory Bridge — Wires Communication Layer outputs into MemoryEngine.

Converts ActionResolution event statements and AgentMessage content
into properly tagged memories for agent retrieval and reflection.
"""
from typing import List, Dict, Any, Optional
from broker.components.memory_engine import MemoryEngine
from broker.interfaces.coordination import ActionResolution, AgentMessage
from broker.utils.logging import logger


# Source mapping: message_type → memory source tag
MESSAGE_SOURCE_MAP = {
    "policy_announcement": "community",
    "market_update": "community",
    "neighbor_warning": "neighbor",
    "neighbor_info": "neighbor",
    "media_broadcast": "community",
    "resolution": "abstract",       # GM resolution
    "direct": "neighbor",
}

# Emotion mapping: message_type → memory emotion tag
MESSAGE_EMOTION_MAP = {
    "policy_announcement": "major",
    "market_update": "observation",
    "neighbor_warning": "critical",
    "neighbor_info": "observation",
    "media_broadcast": "major",
    "resolution": "major",
    "direct": "observation",
}

# Importance mapping: message_type → base importance
MESSAGE_IMPORTANCE_MAP = {
    "policy_announcement": 0.7,
    "market_update": 0.5,
    "neighbor_warning": 0.8,
    "neighbor_info": 0.4,
    "media_broadcast": 0.6,
    "resolution": 0.75,
    "direct": 0.5,
}


class MemoryBridge:
    """Converts Communication Layer outputs into agent memories."""

    def __init__(self, memory_engine: MemoryEngine):
        self.memory_engine = memory_engine

    def store_resolution(self, resolution: ActionResolution, year: int = 0) -> None:
        """Store a GameMaster resolution as agent memory.

        Args:
            resolution: The ActionResolution from GameMaster.resolve_phase()
            year: Current simulation year (for memory prefix)
        """
        # Determine if this resolution should be stored.
        # Store if:
        # 1. It's approved AND has an event statement.
        # 2. It's denied AND has a denial reason.
        should_store = False
        if resolution.approved:
            if resolution.event_statement:
                should_store = True
        else: # Not approved (denied)
            if resolution.denial_reason:
                should_store = True

        if not should_store:
            return

        prefix = f"Year {year}: " if year > 0 else ""

        if resolution.approved:
            content = f"{prefix}{resolution.event_statement}"
            emotion = "positive"
            importance = 0.6
        else:
            content = f"{prefix}My request to {resolution.original_proposal.skill_name} was denied. {resolution.denial_reason}"
            emotion = "shift"
            importance = 0.75  # Denials are more memorable

        self.memory_engine.add_memory(
            resolution.agent_id,
            content,
            metadata={
                "source": "abstract",        # Institutional decision
                "emotion": emotion,
                "importance": importance,
                "type": "resolution",
                "skill_name": resolution.original_proposal.skill_name,
                "approved": resolution.approved,
            }
        )
        logger.debug(f" [MemoryBridge] Stored resolution for {resolution.agent_id}: approved={resolution.approved}")

    def store_resolutions(self, resolutions: List[ActionResolution], year: int = 0) -> int:
        """Store multiple resolutions. Returns count stored."""
        count = 0
        for r in resolutions:
            if r.event_statement or not r.approved:
                self.store_resolution(r, year)
                count += 1
        return count

    def store_message(self, agent_id: str, message: AgentMessage, year: int = 0) -> None:
        """Store a received message as agent memory.

        Args:
            agent_id: The receiving agent
            message: The AgentMessage received
            year: Current simulation year
        """
        prefix = f"Year {year}: " if year > 0 else ""
        source = MESSAGE_SOURCE_MAP.get(message.message_type, "abstract")
        emotion = MESSAGE_EMOTION_MAP.get(message.message_type, "observation")
        importance = MESSAGE_IMPORTANCE_MAP.get(message.message_type, 0.5)

        # Scale importance by message priority (0-10 range → 0.0-0.2 boost)
        importance = min(1.0, importance + message.priority * 0.02)

        sender_label = message.sender_type or message.sender_id
        content = f"{prefix}Received from {sender_label}: {message.content}"

        self.memory_engine.add_memory(
            agent_id,
            content,
            metadata={
                "source": source,
                "emotion": emotion,
                "importance": importance,
                "type": f"message_{message.message_type}",
                "sender_type": message.sender_type,
            }
        )

    def store_unread_messages(self, agent_id: str, messages: List[AgentMessage],
                              year: int = 0, max_store: int = 3) -> int:
        """Store top-priority unread messages as memories.

        Only stores top max_store messages to avoid memory flooding.
        Returns count stored.
        """
        sorted_msgs = sorted(messages, key=lambda m: -m.priority)[:max_store]
        for msg in sorted_msgs:
            self.store_message(agent_id, msg, year)
        return len(sorted_msgs)
