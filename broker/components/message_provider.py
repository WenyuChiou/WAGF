"""
Message Pool Context Provider - Injects agent messages into LLM context.

Follows the existing ContextProvider pattern from context_providers.py.
Plugs into the BaseAgentContextBuilder provider pipeline.

Reference: Task-054 Communication Layer
"""
from typing import Dict, Any, List, Optional
import logging

from broker.components.message_pool import MessagePool

logger = logging.getLogger(__name__)


class MessagePoolProvider:
    """Context provider that injects unread messages into agent context.

    Compatible with the ContextProvider interface used by
    BaseAgentContextBuilder / TieredContextBuilder.

    Args:
        pool: The shared MessagePool instance
        max_messages: Maximum messages to inject (prevents context overflow)
        include_data: Whether to include structured data payloads
    """

    def __init__(
        self,
        pool: MessagePool,
        max_messages: int = 5,
        include_data: bool = False,
    ):
        self.pool = pool
        self.max_messages = max_messages
        self.include_data = include_data

    def provide(
        self,
        agent_id: str,
        agents: Dict[str, Any],
        context: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Inject messages into agent context.

        Adds a ``messages`` key to the context dict containing
        the agent's top-priority unread messages formatted for
        LLM consumption.
        """
        messages = self.pool.get_messages(agent_id)
        top = sorted(messages, key=lambda m: (-m.priority, -m.timestamp))
        top = top[:self.max_messages]

        lines = self._format_artifact_messages(top)
        formatted: List[Dict[str, Any]] = []
        for msg, line in zip(top, lines):
            entry: Dict[str, Any] = {
                "from": msg.sender_type or msg.sender_id,
                "type": msg.message_type,
                "content": line,
            }
            if self.include_data and msg.data:
                entry["data"] = msg.data
            formatted.append(entry)

        context["messages"] = formatted

        if formatted:
            logger.debug(
                "MessagePoolProvider: Injected %d messages for %s",
                len(formatted), agent_id,
            )

    def _format_artifact_messages(self, messages):
        """Format artifact-carrying messages with structured data summaries."""
        lines = []
        for msg in messages:
            if msg.data and msg.data.get("artifact_type"):
                atype = msg.data["artifact_type"]
                skip_keys = {"artifact_type", "agent_id", "year", "rationale"}
                fields = {k: v for k, v in msg.data.items() if k not in skip_keys}
                summary = ", ".join(f"{k}={v}" for k, v in fields.items())
                lines.append(f"[{atype}] {summary}".strip())
            else:
                lines.append(msg.content)
        return lines


__all__ = ["MessagePoolProvider"]
