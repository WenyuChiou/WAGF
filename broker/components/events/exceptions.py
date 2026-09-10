"""
Phase 6T-A (2026-05-27): event-lifecycle persistence policy for the
multi-agent event subsystem.

:class:`EventPersistence` lets each domain pack declare, per
event_type, whether a generated event is wiped at the year boundary
(``EPHEMERAL`` — the default, matching pre-6T-A behaviour), survives
across years with weighted age decay (``STICKY_YEAR_DECAY``, Phase
6T-E social-media propagation), or is never wiped
(``STICKY_INDEFINITE``). Consumed via
:meth:`DomainPack.event_persistence_policy` — see
``broker/domains/default.py`` and ``broker/simulation/environment.py``.

This module originally also carried typed exceptions
(``UnhandledEventError``, ``BrokerHandlerError``,
``InvalidPhaseConfigError``, ``PhaseDependencyCycleError``) and an
``EventDispatchMetrics`` dataclass — guardrails for
``MAEventManager``'s event-dispatch loop and ``PhaseOrchestrator``'s
phase-config validation. Both ``MAEventManager`` and
``PhaseOrchestrator`` were deleted as dead code (org-3 cleanup,
2026-09; no production runner ever instantiated either). All five
guardrail classes had one of those two as their sole raise/record
site; all five are removed as of org-4 cleanup (2026-09) —
grep-confirmed zero importers outside this module, including tests.
"""
from __future__ import annotations

from enum import Enum


class EventPersistence(Enum):
    """Lifecycle policy for a generated event.

    Consumed by:

    - :meth:`broker.components.events.ma_manager.MAEventManager.clear_ephemeral_events`
      — wipes only events tagged ``EPHEMERAL`` (the pre-6T-A default
      behaviour of ``clear_year``).
    - :meth:`broker.components.events.ma_manager.MAEventManager.clear_all_events`
      — wipes everything regardless of policy. Used by hard-resets
      (test teardown, experiment restart) where retained state would
      pollute the next run.
    - Future Phase 6T-E social-media propagation
      (``STICKY_YEAR_DECAY`` posts get weighted age-decay sampling
      across years).

    Default: ``EPHEMERAL`` — every pre-6T-A event type implicitly had
    this policy because ``clear_year`` discarded everything.
    """

    EPHEMERAL = "ephemeral"
    STICKY_YEAR_DECAY = "sticky_year_decay"
    STICKY_INDEFINITE = "sticky_indefinite"


__all__ = [
    "EventPersistence",
]
