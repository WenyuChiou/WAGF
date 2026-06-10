"""DomainPack for the reservoir-control worked example."""
from __future__ import annotations

from broker.domains.default import DefaultDomainPack


class ReservoirControlDomainPack(DefaultDomainPack):
    name = "reservoir_control"

    def coupling_enabled_default(self) -> bool:
        return False


__all__ = ["ReservoirControlDomainPack"]
