"""
Multi-Agent Event Manager - Orchestrates events with dependencies.

Extends EnvironmentEventManager to handle:
1. Event dependencies (impact events depend on hazard events)
2. Phase-based generation (pre_year, per_step, post_year)
3. TieredEnvironment synchronization

Phase 6T-A (2026-05-27): dispatch safety + lifecycle policy. The
pre-6T-A scan-all-silent-skip dispatch and unconditional
``clear_year`` are replaced with:

- Explicit per-pack ownership via :meth:`DomainPack.event_type_to_domain`
  + hard-fail via :class:`UnhandledEventError` on unmatched event_type.
- Per-pack ``silent_skip_event_types()`` opt-in allowlist for
  legitimately observational events.
- Handler exception capture via :class:`BrokerHandlerError` records +
  :class:`EventDispatchMetrics` counters; failed handlers no longer
  crash the year.
- ``clear_year`` split into :meth:`clear_ephemeral_events` (year
  boundary; honours :class:`EventPersistence` per pack) and
  :meth:`clear_all_events` (hard reset).
- Topological-cycle silent fallback replaced with
  :class:`PhaseDependencyCycleError`.

Rationale + audit trail: ``~/.claude/plans/swirling-knitting-lighthouse.md``
(Phase 6T-A scope) + ``broker/components/events/exceptions.py`` (per-class
docstrings).
"""
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from broker.interfaces.event_generator import EnvironmentEvent, EventScope
from broker.domains.protocol import EventHandler
from broker.domains.registry import DomainPackRegistry
from .exceptions import (
    BrokerHandlerError,
    EventDispatchMetrics,
    EventPersistence,
    PhaseDependencyCycleError,
    UnhandledEventError,
)
from .manager import EnvironmentEventManager

logger = logging.getLogger(__name__)


class EventPhase(Enum):
    """When events should be generated in simulation cycle."""
    PRE_YEAR = "pre_year"      # At start of year (hazard determination)
    PER_STEP = "per_step"      # After each agent step (policy changes)
    POST_YEAR = "post_year"    # At end of year (damage calculation)
    ON_DEMAND = "on_demand"    # Manually triggered


@dataclass
class GeneratorSpec:
    """Specification for a registered generator."""
    domain: str
    generator: Any
    phase: EventPhase = EventPhase.PRE_YEAR
    depends_on: List[str] = field(default_factory=list)
    provides: str = ""  # What context key this generator provides

    def __post_init__(self):
        if not self.provides:
            self.provides = f"{self.domain}_events"


class MAEventManager(EnvironmentEventManager):
    """Event manager for multi-agent simulations with dependencies.

    Features:
    - Phase-based event generation (pre_year, per_step, post_year)
    - Dependency resolution between generators
    - TieredEnvironment synchronization
    - Per-agent event filtering

    Usage:
        manager = MAEventManager()

        # Register with dependencies
        manager.register_with_deps(
            domain="hazard",
            generator=MyHazardEventGenerator(...),  # domain-specific subclass
            phase=EventPhase.PRE_YEAR,
        )
        manager.register_with_deps(
            domain="impact",
            generator=ImpactEventGenerator(...),
            phase=EventPhase.POST_YEAR,
            depends_on=["hazard"],  # Needs hazard events first
        )
        manager.register_with_deps(
            domain="policy",
            generator=PolicyEventGenerator(...),
            phase=EventPhase.PER_STEP,
        )

        # Generate by phase
        manager.generate_phase(EventPhase.PRE_YEAR, year=1, context={...})
        # ... agent decisions happen ...
        manager.generate_phase(EventPhase.POST_YEAR, year=1, context={...})
    """

    def __init__(self):
        super().__init__()
        self._specs: Dict[str, GeneratorSpec] = {}
        self._phase_order: Dict[EventPhase, List[str]] = {
            phase: [] for phase in EventPhase
        }
        self._event_context: Dict[str, List[EnvironmentEvent]] = {}
        # Phase 6T-A: per-year dispatch counters. Reset on
        # clear_ephemeral_events (year boundary) and on hard
        # clear_all_events. Read by the audit writer (Phase 6T-G).
        self.metrics: EventDispatchMetrics = EventDispatchMetrics()

    def register_with_deps(
        self,
        domain: str,
        generator: Any,
        phase: EventPhase = EventPhase.PRE_YEAR,
        depends_on: List[str] = None,
        provides: str = None,
    ) -> None:
        """Register a generator with phase and dependency info.

        Args:
            domain: Domain identifier
            generator: Event generator instance
            phase: When to generate events
            depends_on: List of domains this depends on
            provides: Context key for generated events
        """
        spec = GeneratorSpec(
            domain=domain,
            generator=generator,
            phase=phase,
            depends_on=depends_on or [],
            provides=provides or f"{domain}_events",
        )
        self._specs[domain] = spec
        self._generators[domain] = generator

        # Add to phase order (respecting dependencies)
        self._update_phase_order(domain, phase)

    def _update_phase_order(self, domain: str, phase: EventPhase) -> None:
        """Update phase order with topological sort for dependencies."""
        if domain not in self._phase_order[phase]:
            self._phase_order[phase].append(domain)

        # Re-sort based on dependencies
        order = self._phase_order[phase]
        sorted_order = self._topological_sort(order, phase)
        self._phase_order[phase] = sorted_order

    def _topological_sort(
        self,
        domains: List[str],
        phase: EventPhase
    ) -> List[str]:
        """Sort domains by dependencies within a phase."""
        # Build dependency graph for this phase
        in_phase = set(domains)
        graph: Dict[str, Set[str]] = {d: set() for d in domains}

        for domain in domains:
            spec = self._specs.get(domain)
            if spec:
                for dep in spec.depends_on:
                    if dep in in_phase:
                        graph[domain].add(dep)

        # Kahn's algorithm
        in_degree = {d: len(graph[d]) for d in domains}
        queue = [d for d in domains if in_degree[d] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for d in domains:
                if node in graph[d]:
                    graph[d].remove(node)
                    in_degree[d] -= 1
                    if in_degree[d] == 0:
                        queue.append(d)

        # Phase 6T-A (2026-05-27): cycle detection now hard-fails.
        # Pre-6T-A behaviour returned the original (unsorted) order,
        # silently producing a meaningless ordering where dependent
        # generators saw stale context from prior years. The audit
        # plan (~/.claude/plans/swirling-knitting-lighthouse.md, R3)
        # flagged this as a Phase 6T BLOCKER — institutional /
        # social-media generators can introduce cycles via shared
        # dependencies, and silent fallback masks the misconfig until
        # headline metrics diverge.
        if len(result) != len(domains):
            unresolved = [d for d in domains if d not in result]
            raise PhaseDependencyCycleError(
                f"Generator dependency cycle detected in phase "
                f"{phase.value!r}. Unresolved domains: {unresolved!r}. "
                f"Phase order requested: {domains!r}. Fix by breaking "
                f"the cycle in your generator's depends_on declarations."
            )

        return result

    def generate_phase(
        self,
        phase: EventPhase,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> Dict[str, List[EnvironmentEvent]]:
        """Generate all events for a specific phase.

        Phase 6T-G (2026-05-28): the caller's ``context`` dict is NO
        LONGER mutated. Previously this method called
        ``context.update(self._event_context)`` and
        ``context[provides_key] = …``, leaking dependency-chain state
        into the caller's mapping (engineering audit Y1). The method
        now copies ``context`` into a private ``working`` dict, mutates
        ``working``, and returns ``phase_events`` unchanged. The
        ``_event_context`` accumulation across phases still happens via
        ``self`` so dependent generators see prior outputs.

        Args:
            phase: Which phase to generate
            year: Simulation year
            step: Step within year (for PER_STEP)
            context: Shared context (agents, environment, etc.) — not
                mutated. Callers that need dependency-chain values must
                read them from the returned dict's generators or from
                ``self._event_context`` directly.

        Returns:
            Dict mapping domain to events
        """
        # Phase 6T-G: copy in. Mutating ``working`` leaves the caller's
        # dict pristine.
        working: Dict[str, Any] = dict(context or {})
        phase_events = {}

        # Add previously generated events to the working copy
        working.update(self._event_context)

        for domain in self._phase_order[phase]:
            spec = self._specs.get(domain)
            if not spec:
                continue

            generator = spec.generator

            # Add dependency events to the working copy
            for dep in spec.depends_on:
                dep_spec = self._specs.get(dep)
                if dep_spec:
                    provides_key = dep_spec.provides
                    if provides_key in self._event_context:
                        working[provides_key] = self._event_context[provides_key]

            # Generate events
            events = generator.generate(year, step, working)
            phase_events[domain] = events
            self._current_events[domain] = events
            self._event_history.extend(events)

            # Store for dependent generators
            self._event_context[spec.provides] = events

        return phase_events

    def generate_all(
        self,
        year: int,
        step: int = 0,
        context: Dict[str, Any] = None
    ) -> Dict[str, List[EnvironmentEvent]]:
        """Generate events for appropriate phase based on step.

        For step=0: PRE_YEAR phase
        For step>0: PER_STEP phase
        """
        if step == 0:
            return self.generate_phase(EventPhase.PRE_YEAR, year, step, context)
        else:
            return self.generate_phase(EventPhase.PER_STEP, year, step, context)

    def generate_post_year(
        self,
        year: int,
        context: Dict[str, Any] = None
    ) -> Dict[str, List[EnvironmentEvent]]:
        """Generate POST_YEAR phase events."""
        return self.generate_phase(EventPhase.POST_YEAR, year, 0, context)

    # ------------------------------------------------------------------
    # Year-boundary clear (Phase 6T-A split)
    # ------------------------------------------------------------------

    def clear_year(self) -> None:
        """Phase 6T-A: alias for :meth:`clear_ephemeral_events`.

        Kept as a back-compat shim so existing callers continue to
        get year-boundary behaviour. New code should call
        :meth:`clear_ephemeral_events` (year boundary, honours
        ``EventPersistence``) or :meth:`clear_all_events` (hard reset)
        explicitly.
        """
        self.clear_ephemeral_events()

    def clear_ephemeral_events(self) -> None:
        """Phase 6T-A: clear at year boundary, honouring per-event
        :class:`EventPersistence`.

        Events tagged ``EPHEMERAL`` (the default for every event_type
        unless its owning pack overrides
        :meth:`DomainPack.event_persistence_policy`) are discarded.
        ``STICKY_YEAR_DECAY`` and ``STICKY_INDEFINITE`` events survive
        — consumers (Phase 6T-E social-media feed retrieval) read them
        across year boundaries with weighted age decay.

        Also resets :attr:`metrics` so a new year starts with clean
        dispatch counters.
        """
        self._current_events = self._filter_persistent(self._current_events)
        self._event_context = self._filter_persistent(self._event_context)
        self.metrics.reset()

    def clear_all_events(self) -> None:
        """Phase 6T-A: hard reset — discard ALL events regardless of
        persistence policy.

        Used by test teardown + experiment restart paths where retained
        state would pollute the next run. Pre-6T-A this was the
        unconditional behaviour of :meth:`clear_year`.
        """
        self._event_context.clear()
        self._current_events.clear()
        self.metrics.reset()

    def _filter_persistent(
        self,
        store: Dict[str, List[EnvironmentEvent]],
    ) -> Dict[str, List[EnvironmentEvent]]:
        """Phase 6T-A helper — return a copy of ``store`` keeping only
        events whose owning pack flags them as non-EPHEMERAL.

        An event with no resolvable owning pack (no registered pack
        claims the event_type) is treated as EPHEMERAL and dropped.
        Conservative default — Phase 6T-A's new dispatch path already
        raises :class:`UnhandledEventError` for unhandled events at
        sync time, so we should never see truly-unknown events here.
        """
        kept: Dict[str, List[EnvironmentEvent]] = {}
        for key, events in store.items():
            persistent: List[EnvironmentEvent] = []
            for event in events:
                if self._is_persistent(event):
                    persistent.append(event)
            if persistent:
                kept[key] = persistent
        return kept

    def _is_persistent(self, event: EnvironmentEvent) -> bool:
        """Return True iff a registered pack tags this event_type as
        non-EPHEMERAL via :meth:`DomainPack.event_persistence_policy`.
        """
        for name in DomainPackRegistry.domains():
            pack = DomainPackRegistry.get_event_pack(name)
            if pack.event_type_to_domain(event.event_type) is None:
                continue
            policy = pack.event_persistence_policy(event.event_type)
            return policy != EventPersistence.EPHEMERAL
        return False

    def sync_to_environment(
        self,
        env: Any,
        domains: List[str] = None
    ) -> None:
        """Sync event data to TieredEnvironment.

        Updates ``env.global_state`` with event summaries. The exact keys
        written are domain-specific — each registered ``DomainPack``
        supplies them via ``event_handlers()`` (e.g. the water domain
        writes hazard-occurrence and policy-rate keys). Generic code
        here names none.

        Args:
            env: TieredEnvironment instance
            domains: Domains to sync (default: all)
        """
        if not hasattr(env, "global_state"):
            return

        domains = domains or list(self._current_events.keys())

        for domain, events in self._current_events.items():
            if domains and domain not in domains:
                continue

            for event in events:
                self._sync_event_to_env(env, event)

    def _sync_event_to_env(self, env: Any, event: EnvironmentEvent) -> None:
        """Sync a single event to environment state.

        Phase 6T-A (2026-05-27) — DISPATCH SAFETY OVERHAUL.

        Pre-6T-A behaviour: ``env.domain`` look-up, falling back to a
        scan-all-packs-and-silently-skip-if-nothing-matches path. Bugs
        (typos, forgotten registrations) disappeared into a black hole.

        New behaviour:

        1. If ``env.domain`` is set, resolve the pack via
           :meth:`DomainPackRegistry.get_event_pack` and look up
           ``event_handlers()[event.event_type]``.
        2. Otherwise, scan registered packs and pick the first whose
           :meth:`DomainPack.event_type_to_domain` claims this
           ``event_type``.
        3. Handler invocation is wrapped in ``try/except`` — exceptions
           are captured as :class:`BrokerHandlerError` records in
           :attr:`metrics`, logged, and SUPPRESSED so the year
           continues. Pre-6T-A any uncaught handler exception killed
           the year. Counts increment :attr:`metrics.handlers_failed`.
        4. If no pack handles + no pack lists ``event_type`` in
           :meth:`silent_skip_event_types`, raise
           :class:`UnhandledEventError`. Explicit silent skip ⇒
           :attr:`metrics.handlers_silently_skipped` increments and
           dispatch continues.
        """
        gs = env.global_state
        domain_name = getattr(env, "domain", None)

        handler, owning_domain = self._resolve_handler(event.event_type, domain_name)

        if handler is None:
            # No handler — check the per-pack silent-skip allowlist
            # before raising. Phase 6T-A explicit opt-in for
            # observational / metrics-only event types.
            if self._is_silent_skip(event.event_type):
                self.metrics.record_silent_skip()
                return
            # Phase 6T-G: record before raising so the audit trail can
            # surface the unhandled type even if a higher layer catches
            # the exception.
            self.metrics.record_unhandled(event.event_type)
            raise UnhandledEventError(
                event_type=event.event_type,
                domain_name=domain_name,
                registered_domains=DomainPackRegistry.domains(),
            )

        try:
            handler(event, gs)
        except Exception as exc:  # noqa: BLE001 — dispatch safety net
            error = BrokerHandlerError(
                event_type=event.event_type,
                handler_qualname=getattr(handler, "__qualname__", repr(handler)),
                exception_type=type(exc).__name__,
                exception_message=str(exc),
            )
            self.metrics.record_failure(error)
            logger.error(
                "[MAEventManager] handler for event_type=%r (domain=%r) raised "
                "%s: %s. Year continues; failure recorded in EventDispatchMetrics.",
                event.event_type, owning_domain, type(exc).__name__, exc,
                exc_info=True,
            )
            return

        self.metrics.record_invoke()

        # Phase 6T-E.B (2026-05-28): optional post-emission hook.
        # Packs implementing ``emit_posts_for_event(event, env) ->
        # Iterable[Post]`` opt into the social-media propagation
        # channel; the dispatcher feeds each yielded Post to
        # ``env.add_post``. Default DomainPack does NOT implement the
        # method — generic broker code references no domain-specific
        # names here. When the social-feeds flag is OFF (paper-3
        # default), the pack's hook is responsible for early-returning
        # an empty iterator to keep byte-identity. Exceptions inside
        # the hook are SUPPRESSED (same dispatch-safety pattern as
        # the handler path); the event itself already succeeded.
        owning_pack = (
            DomainPackRegistry.get(owning_domain)
            if owning_domain is not None
            else None
        )
        emit = getattr(owning_pack, "emit_posts_for_event", None)
        if emit is not None and hasattr(env, "add_post"):
            try:
                for post in emit(event, env) or ():
                    env.add_post(post)
            except Exception as exc:  # noqa: BLE001 — dispatch safety net
                logger.error(
                    "[MAEventManager] emit_posts_for_event for event_type=%r "
                    "(domain=%r) raised %s: %s. Original handler already "
                    "succeeded; continuing.",
                    event.event_type, owning_domain, type(exc).__name__, exc,
                    exc_info=True,
                )

    def _resolve_handler(
        self,
        event_type: str,
        domain_name: Optional[str],
    ) -> Tuple[Optional[EventHandler], Optional[str]]:
        """Phase 6T-A: resolve ``(handler, owning_domain)`` for an
        event_type.

        Strategy:

        1. If ``domain_name`` is set, narrow directly via
           :meth:`DomainPackRegistry.get_event_pack`.
        2. Otherwise, scan registered packs and accept the first
           whose :meth:`event_type_to_domain` claims ownership.

        Returns ``(None, None)`` when no pack claims ownership —
        caller decides whether to silently skip or raise.
        """
        if domain_name is not None:
            pack = DomainPackRegistry.get_event_pack(domain_name)
            handler = pack.event_handlers().get(event_type)
            if handler is not None:
                return handler, domain_name
            # env.domain was set but the pack doesn't handle this type
            # — fall through to scan-all so a cross-domain event
            # (e.g. a social-media post emitted by the flood pack and
            # handled by a social-media pack) still finds its handler.

        for name in DomainPackRegistry.domains():
            pack = DomainPackRegistry.get_event_pack(name)
            claimed = pack.event_type_to_domain(event_type)
            if claimed is None:
                continue
            handler = pack.event_handlers().get(event_type)
            if handler is not None:
                return handler, name
            # Pack claims ownership but has no handler — keep scanning
            # in case another pack (an observer / handler split) does.

        return None, None

    def _is_silent_skip(self, event_type: str) -> bool:
        """Phase 6T-A: union of every registered pack's
        :meth:`silent_skip_event_types` allowlist."""
        for name in DomainPackRegistry.domains():
            pack = DomainPackRegistry.get_event_pack(name)
            if event_type in pack.silent_skip_event_types():
                return True
        return False

    def get_events_by_type(
        self,
        event_type: str,
        domain: str = None
    ) -> List[EnvironmentEvent]:
        """Get all events of a specific type."""
        events = []
        sources = [domain] if domain else list(self._current_events.keys())

        for d in sources:
            for event in self._current_events.get(d, []):
                if event.event_type == event_type:
                    events.append(event)

        return events

    @staticmethod
    def _resolve_impact_handlers() -> Dict[str, EventHandler]:
        """Merge ``agent_impact_handlers()`` across every registered
        domain. First-registered domain wins on an event-type collision,
        mirroring the domain-scan order in :meth:`_sync_event_to_env`."""
        handlers: Dict[str, EventHandler] = {}
        for name in DomainPackRegistry.domains():
            pack = DomainPackRegistry.get(name)
            if pack is None:
                continue
            for event_type, handler in pack.agent_impact_handlers().items():
                handlers.setdefault(event_type, handler)
        return handlers

    def get_agent_impact(self, agent_id: str) -> Dict[str, Any]:
        """Aggregate per-agent impact across all current events.

        Phase 6T-A (2026-05-27): handler invocations are wrapped in
        try/except — exceptions captured into :attr:`metrics` rather
        than propagated, matching the safety semantics of
        :meth:`_sync_event_to_env`. An event whose ``event_type`` has
        no impact handler is treated as no-op (impact handlers are
        opt-in per pack); the explicit-skip path lives on the env-sync
        side, not here, because impact handlers are inherently sparse.

        Phase 6J-B (2026-05-22): the hardcoded flood event-type chain
        was replaced by ``DomainPack.agent_impact_handlers()`` dispatch.
        The impact dict shape is now domain-defined — a domain's handlers
        populate it. With no domain registered (or no event affecting the
        agent) the result is an empty dict; callers MUST read keys with
        ``.get(key, default)`` — an absent key means zero/False, not an
        error.
        """
        impact: Dict[str, Any] = {}
        # _resolve_impact_handlers re-scans the registry on every call.
        # Acceptable: MAEventManager is a test-only path (no production
        # lifecycle caller). Cache the merged table if it is ever wired
        # into a production loop.
        handlers = self._resolve_impact_handlers()
        if not handlers:
            return impact

        for events in self._current_events.values():
            for event in events:
                if not event.affects_agent(agent_id):
                    continue
                handler = handlers.get(event.event_type)
                if handler is None:
                    continue
                try:
                    handler(event, impact)
                except Exception as exc:  # noqa: BLE001 — dispatch safety
                    error = BrokerHandlerError(
                        event_type=event.event_type,
                        handler_qualname=getattr(handler, "__qualname__", repr(handler)),
                        exception_type=type(exc).__name__,
                        exception_message=str(exc),
                        agent_id=agent_id,
                    )
                    self.metrics.record_failure(error)
                    logger.error(
                        "[MAEventManager] agent-impact handler for "
                        "event_type=%r agent=%r raised %s: %s",
                        event.event_type, agent_id, type(exc).__name__, exc,
                        exc_info=True,
                    )
                    continue
                self.metrics.record_invoke()

        return impact


__all__ = [
    "MAEventManager",
    "EventPhase",
    "GeneratorSpec",
    # Phase 6T-A re-exports for callers building on the dispatch
    # subsystem — fewer cross-package imports for downstream code.
    "BrokerHandlerError",
    "EventDispatchMetrics",
    "EventPersistence",
    "PhaseDependencyCycleError",
    "UnhandledEventError",
]
