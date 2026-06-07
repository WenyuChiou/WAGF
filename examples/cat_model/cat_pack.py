"""CatModelDomainPack — the DomainPack for the catastrophe-model example.

Subclasses :class:`broker.domains.default.DefaultDomainPack` and adds only what
the cat-model coupling needs:
  * ``coupling_enabled_default() -> False`` so the coupling layer is OFF unless a
    YAML config opts in (``global_config.coupling.enable: true``) — mirrors the
    social-feeds two-layer flag, keeping any frozen config byte-identical.

The insurer's governance is the physical-slot payout-solvency check
(registered with ValidatorRegistry in ``__init__.py``); it needs no behavioural
framework, so the DefaultDomainPack escape-hatch framework is fine.
"""
from __future__ import annotations

from broker.domains.default import DefaultDomainPack


class CatModelDomainPack(DefaultDomainPack):
    def coupling_enabled_default(self) -> bool:
        # OFF by default; a YAML ``global_config.coupling.enable: true`` turns it on.
        return False


__all__ = ["CatModelDomainPack"]
