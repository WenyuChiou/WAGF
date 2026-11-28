"""
Event-lifecycle persistence policy for the multi-agent event subsystem.

:class:`EventPersistence` lets each domain pack declare, per ``event_type``,
whether a generated event is wiped at the period boundary (``EPHEMERAL``),
survives across periods with weighted age decay (``STICKY_YEAR_DECAY``, used
by social-media propagation), or persists indefinitely (``STICKY_INDEFINITE``).
Consumed via :meth:`DomainPack.event_persistence_policy` and
``broker/simulation/environment.py`` (``TieredEnvironment``).
"""
from __future__ import annotations

from enum import Enum


class EventPersistence(Enum):
    """Lifecycle policy for a generated event in :class:`TieredEnvironment`.

    - ``EPHEMERAL``: cleared at period boundaries.
    - ``STICKY_YEAR_DECAY``: retained across periods with age-decay weighting.
    - ``STICKY_INDEFINITE``: retained until explicitly cleared.
    """

    EPHEMERAL = "ephemeral"
    STICKY_YEAR_DECAY = "sticky_year_decay"
    STICKY_INDEFINITE = "sticky_indefinite"


__all__ = [
    "EventPersistence",
]
