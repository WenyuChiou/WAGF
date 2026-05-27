"""
Phase 6T-A (2026-05-27): typed exceptions, persistence policy enum, and
event-dispatch metrics for the multi-agent event subsystem.

These replace two silent-failure paths the engineering audit
(2026-05-26, plan: ``~/.claude/plans/swirling-knitting-lighthouse.md``)
flagged as BLOCKERs for Phase 6T social-media + institutional-diversity
work:

1. ``MAEventManager._sync_event_to_env`` previously silently skipped any
   event_type with no registered handler. Pre-6T this was tolerable —
   only the flood pack used the dispatcher and unknown events were
   either typos or test fixtures. Under Phase 6T this becomes a
   debugging black hole: social-media post handlers, institutional
   utility-framework handlers, and follower-network observers would all
   silently disappear on a typo. Replaced with
   :class:`UnhandledEventError` + an explicit per-pack opt-in
   ``silent_skip_event_types()`` allowlist.

2. ``MAEventManager.clear_year`` previously cleared everything
   unconditionally. Pattern B (Phase 6T-E) social-media posts must
   survive across year boundaries with weighted age decay; flood/no-flood
   events must NOT. The :class:`EventPersistence` enum + the new
   ``DomainPack.event_persistence_policy(event_type)`` hook let each
   pack declare lifecycle behaviour per event_type.

3. ``PhaseOrchestrator._validate_phases`` and ``_topological_order`` (and
   ``MAEventManager._topological_sort``) previously emitted
   ``logger.warning`` and proceeded with broken configs / unsorted
   order. Under Phase 6T's institutional-diversity work, an
   institutional phase that depends on a missing observer phase, or a
   dependency cycle introduced by a social-media-influencer phase,
   would silently degrade execution ordering — masking a config bug
   until the headline experiment is months in. Replaced with
   :class:`InvalidPhaseConfigError` and :class:`PhaseDependencyCycleError`.

The exception messages all include the user-actionable repair path —
either register the missing handler, opt into silent-skip, fix the
phase YAML, or break the dependency cycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


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


class UnhandledEventError(RuntimeError):
    """Raised by :meth:`MAEventManager._sync_event_to_env` and
    :meth:`MAEventManager.get_agent_impact` when an event's
    ``event_type`` has no registered handler AND no domain pack lists
    it in :meth:`DomainPack.silent_skip_event_types`.

    Pre-6T-A behaviour was silent skip — unknown event types fell
    through unmodified, leaving the year's environment state stale and
    masking dispatch bugs. The Phase 6T-A hard-fail surfaces typos /
    forgotten handler registrations at the first occurrence.

    Domains that emit observational / metrics-only events they do not
    handle (e.g. an audit-only ``social_media_post_engaged`` event with
    no global-state mutation) opt into the legacy behaviour explicitly
    via the pack's ``silent_skip_event_types()`` allowlist. The
    explicit opt-in keeps the failure-mode surface visible — silent
    skip is a property of the pack, not of the dispatcher.
    """

    def __init__(
        self,
        event_type: str,
        domain_name: Optional[str],
        registered_domains: List[str],
    ) -> None:
        self.event_type = event_type
        self.domain_name = domain_name
        self.registered_domains = list(registered_domains)
        msg = (
            f"No handler registered for event_type={event_type!r}. "
            f"env.domain={domain_name!r}; "
            f"registered_domains={self.registered_domains!r}. "
            f"Fix by EITHER registering a handler in your DomainPack's "
            f"event_handlers() / agent_impact_handlers(), OR adding "
            f"{event_type!r} to the pack's silent_skip_event_types() if "
            f"the event is intentionally observational only."
        )
        super().__init__(msg)


@dataclass
class BrokerHandlerError:
    """Structured record of a handler exception. Emitted into the
    dispatch metrics (:class:`EventDispatchMetrics.errors`) and logged
    when a handler invocation raises.

    NOT a Python exception — it is a serialisable dataclass that the
    audit writer can persist. The corresponding RAISED exception is
    caught + logged by :meth:`MAEventManager._sync_event_to_env`; the
    handler's failure does not crash the year, but it IS recorded so a
    post-hoc audit can detect the silent-failure mode.
    """

    event_type: str
    handler_qualname: str
    exception_type: str
    exception_message: str
    year: int = -1
    agent_id: Optional[str] = None


class InvalidPhaseConfigError(ValueError):
    """Raised by :class:`PhaseOrchestrator` when the phase configuration
    is structurally broken:

    - A :class:`PhaseConfig.depends_on` entry names a phase not declared
      in the same orchestrator (the dependency target is unreachable).
    - A YAML phase entry names an :class:`ExecutionPhase` value that
      doesn't exist in the enum.

    Pre-6T-A behaviour was ``logger.warning`` + silent fallback (unknown
    phase → ``ExecutionPhase.CUSTOM``; broken dep → leave depends_on
    pointing at a non-existent phase). The new hard-fail surfaces the
    misconfiguration at config-load time, before any agent runs.
    """


class PhaseDependencyCycleError(InvalidPhaseConfigError):
    """Raised by :meth:`PhaseOrchestrator._topological_order` and
    :meth:`MAEventManager._topological_sort` when the dependency graph
    contains a cycle (Kahn's algorithm produces a smaller result set
    than the input).

    Pre-6T-A behaviour was ``logger.warning`` + return the original
    (unsorted) order. The unsorted order is meaningless under Phase 6T
    — dependent generators / phases see stale context from prior years
    when the topological sort silently fails, masking the cycle until
    headline metrics diverge.
    """


@dataclass
class EventDispatchMetrics:
    """Year-scoped event-dispatch counters surfaced by
    :class:`MAEventManager`. Reset on
    :meth:`MAEventManager.clear_ephemeral_events` (the new
    year-boundary clear).

    Surfaced in the audit metadata by Phase 6T-G (cross-channel dedup +
    Y1 fix + metrics emission); used in Phase 6T-A's regression tests
    to assert that silent-skip paths are accounted for.

    Fields:

    - ``handlers_invoked`` — successful handler calls.
    - ``handlers_failed`` — handler raised an exception; recorded in
      ``errors`` and logged but did NOT propagate.
    - ``handlers_silently_skipped`` — event_type matched a pack's
      ``silent_skip_event_types()`` allowlist; no handler was called
      and no error was raised.
    - ``errors`` — list of :class:`BrokerHandlerError` records, one
      per failed handler call.
    """

    handlers_invoked: int = 0
    handlers_failed: int = 0
    handlers_silently_skipped: int = 0
    errors: List[BrokerHandlerError] = field(default_factory=list)

    def record_invoke(self) -> None:
        self.handlers_invoked += 1

    def record_failure(self, error: BrokerHandlerError) -> None:
        self.handlers_failed += 1
        self.errors.append(error)

    def record_silent_skip(self) -> None:
        self.handlers_silently_skipped += 1

    def reset(self) -> None:
        self.handlers_invoked = 0
        self.handlers_failed = 0
        self.handlers_silently_skipped = 0
        self.errors.clear()


__all__ = [
    "EventPersistence",
    "UnhandledEventError",
    "BrokerHandlerError",
    "InvalidPhaseConfigError",
    "PhaseDependencyCycleError",
    "EventDispatchMetrics",
]
