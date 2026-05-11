"""DomainPack for gossip_demo (Phase 6F).

Minimal — extends DefaultDomainPack with role-specific reflection text
for the 3 agent types. Other DomainPack hooks fall through to no-op
defaults.
"""
from __future__ import annotations

from typing import Any, Optional

from broker.domains.default import DefaultDomainPack


class GossipDomainPack(DefaultDomainPack):
    """DomainPack for social-media gossip simulation."""

    @property
    def name(self) -> str:
        return "gossip"

    def reflection_status_text(self, context: Any) -> Optional[str]:
        atype = getattr(context, "agent_type", None)
        last = getattr(context, "dynamic_state", {}).get("last_decision", "none")
        if atype == "platform_moderator":
            return (
                f"You moderate this platform's community feed. Your last "
                f"moderation action was '{last}'."
            )
        if atype == "influencer":
            return (
                f"You are a content creator with an audience here. Your "
                f"last posting decision was '{last}'."
            )
        if atype == "casual_user":
            return (
                f"You are a regular user of this community platform. Your "
                f"last engagement action was '{last}'."
            )
        return None
