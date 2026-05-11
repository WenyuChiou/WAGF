"""DomainPack for multi-agent vaccination demo (Phase 6E).

Subclasses VaccinationDomainPack from the single-agent demo and extends
reflection_status_text to handle 3 agent types (health_authority,
community_org, individual). All other DomainPack hooks fall through to
defaults.

Pattern reused from `examples/vaccination_demo/adapters/vaccination_pack.py`
plus the multi-agent reflection-status idiom from
`examples/multi_agent/flood/orchestration/lifecycle_hooks.py`.
"""
from __future__ import annotations

from typing import Any, Optional

from examples.vaccination_demo.adapters.vaccination_pack import (
    VaccinationDomainPack,
)


class VaccinationMADomainPack(VaccinationDomainPack):
    """Multi-agent vaccination DomainPack — extends single-agent with role text."""

    name: str = "vaccination_ma"

    def reflection_status_text(self, context: Any) -> Optional[str]:
        atype = getattr(context, "agent_type", None)
        if atype == "individual":
            # Reuse parent's individual logic — it already handles
            # vaccinated/weeks_since_dose narrative.
            return super().reflection_status_text(context)
        if atype == "health_authority":
            last = getattr(context, "dynamic_state", {}).get(
                "last_advisory_strength", "none"
            )
            return f"You are the public health authority. Your last advisory level was '{last}'."
        if atype == "community_org":
            last = getattr(context, "dynamic_state", {}).get(
                "last_outreach", "none"
            )
            return f"You are a community organization. Your last outreach action was '{last}'."
        return None
