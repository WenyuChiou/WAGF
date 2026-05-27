"""
Phase 6T-A safety tests for the multi-agent event dispatcher.

Closes engineering-audit R1/R2/R3/Y2/Y3/O4/O5 — verifies the new
hard-fail-on-unknown-event-type + handler-exception-isolation +
ephemeral-vs-sticky persistence + phase-config-misconfig hard-fail
behaviour shipped in Phase 6T-A (plan:
``~/.claude/plans/swirling-knitting-lighthouse.md``).

Test layout — 8 tests across 4 classes:

- ``TestUnhandledEventDispatch`` — explicit hard-fail vs opt-in silent-skip
- ``TestHandlerExceptionIsolation`` — exception capture into metrics
- ``TestEventLifecycle`` — clear_ephemeral / clear_all + persistence policy
- ``TestPhaseConfigHardFail`` — InvalidPhaseConfigError / PhaseDependencyCycleError

These tests do NOT exercise the real Flood/Irrigation/Vaccination
packs end-to-end (the MA flood smoke at
``examples/multi_agent/flood/paper3/tests/test_ma_flood_6r_regression.py``
covers that path). They use a minimal in-test fake pack registered
via ``DomainPackRegistry`` to isolate the dispatcher contract.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Set

import pytest

from broker.components.events.exceptions import (
    BrokerHandlerError,
    EventDispatchMetrics,
    EventPersistence,
    InvalidPhaseConfigError,
    PhaseDependencyCycleError,
    UnhandledEventError,
)
from broker.components.events.ma_manager import MAEventManager
from broker.components.orchestration.phases import PhaseOrchestrator
from broker.domains.default import DefaultDomainPack
from broker.domains.registry import DomainPackRegistry
from broker.interfaces.coordination import ExecutionPhase, PhaseConfig
from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventScope,
    EventSeverity,
)


# ─────────────────────────────────────────────────────────────────────
# Fake DomainPack — minimal pack the dispatcher can route to
# ─────────────────────────────────────────────────────────────────────


class _RaisingPack(DefaultDomainPack):
    """Pack whose ``known_event`` handler always raises. Exercises the
    Phase 6T-A handler-exception-capture path."""

    name = "raisingpack"

    def __init__(self) -> None:
        self.handler_calls = 0

    def _bad_handler(self, event: EnvironmentEvent, state: Dict[str, Any]) -> None:
        self.handler_calls += 1
        raise RuntimeError("simulated handler failure")

    def event_handlers(self):
        return {"known_event": self._bad_handler}


class _GoodPack(DefaultDomainPack):
    """Pack exercising every dispatch path: a working env-sync
    handler (``good_event``), an impact-only event_type that requires
    silent-skip-via-allowlist (``impact_only_type``), and an
    observational silent-skip-only event (``audit_only_event``).

    Merges three concerns into one pack to stay under the
    ``TestNoExcessiveInlineMockPacks`` framework-invariant limit of
    ≤3 inline mock packs per test file.
    """

    name = "goodpack"

    def __init__(self) -> None:
        self.invocations = 0

    def _good_handler(self, event: EnvironmentEvent, state: Dict[str, Any]) -> None:
        self.invocations += 1
        state["good_seen"] = True

    def _impact_handler(self, event: EnvironmentEvent, impact: Dict[str, Any]) -> None:
        impact["damage"] = impact.get("damage", 0) + 1

    def event_handlers(self):
        return {"good_event": self._good_handler}

    def agent_impact_handlers(self):
        # Phase 6T-A code-review P1 regression coverage: impact-only
        # event_type registered HERE but NOT in event_handlers must
        # silently skip env-sync via the silent_skip allowlist below.
        return {"impact_only_type": self._impact_handler}

    def silent_skip_event_types(self) -> Set[str]:
        return {"audit_only_event", "impact_only_type"}


class _StickyPack(DefaultDomainPack):
    """Pack whose ``sticky_event`` is tagged STICKY_YEAR_DECAY — used
    to verify clear_ephemeral_events keeps non-EPHEMERAL events."""

    name = "stickypack"

    def _noop_handler(self, event: EnvironmentEvent, state: Dict[str, Any]) -> None:
        return None

    def event_handlers(self):
        return {
            "sticky_event": self._noop_handler,
            "ephemeral_event": self._noop_handler,
        }

    def event_persistence_policy(self, event_type: str):
        if event_type == "sticky_event":
            return EventPersistence.STICKY_YEAR_DECAY
        return EventPersistence.EPHEMERAL


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


class _MockEnv:
    """Stand-in for TieredEnvironment exposing ``global_state``."""

    def __init__(self, domain: Optional[str] = None) -> None:
        self.global_state: Dict[str, Any] = {}
        if domain is not None:
            self.domain = domain


def _make_event(event_type: str) -> EnvironmentEvent:
    return EnvironmentEvent(
        event_type=event_type,
        severity=EventSeverity.INFO,
        scope=EventScope.GLOBAL,
        description=f"test event {event_type}",
    )


@pytest.fixture
def registry_isolation():
    """Snapshot + restore the DomainPackRegistry around each test so
    fake packs don't leak across tests."""
    saved = dict(DomainPackRegistry._packs)
    saved_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry.clear()
    yield
    DomainPackRegistry.clear()
    for name, pack in saved.items():
        DomainPackRegistry._packs[name] = pack
    DomainPackRegistry._missing_warned.update(saved_warned)


# ─────────────────────────────────────────────────────────────────────
# Class 1 — Unhandled-event dispatch
# ─────────────────────────────────────────────────────────────────────


class TestUnhandledEventDispatch:
    """R1/R2: hard-fail on unknown event_type, honour silent-skip allowlist."""

    def test_raises_unhandled_event_error_when_no_pack_claims_type(
        self, registry_isolation
    ):
        """An event_type that no registered pack handles AND no pack
        lists in silent_skip_event_types() must raise
        UnhandledEventError. Pre-6T-A this silently no-op'd."""
        DomainPackRegistry.register("goodpack", _GoodPack())
        manager = MAEventManager()
        env = _MockEnv()  # no .domain attribute

        with pytest.raises(UnhandledEventError) as exc:
            manager._sync_event_to_env(env, _make_event("totally_unknown_type"))

        assert exc.value.event_type == "totally_unknown_type"
        assert "goodpack" in exc.value.registered_domains
        assert "silent_skip_event_types" in str(exc.value)

    def test_silent_skip_allowlist_records_metric_and_continues(
        self, registry_isolation
    ):
        """When a pack lists event_type in silent_skip_event_types(),
        the dispatcher must NOT raise — it records
        handlers_silently_skipped on the metrics counter and returns."""
        DomainPackRegistry.register("goodpack", _GoodPack())
        manager = MAEventManager()
        env = _MockEnv()

        # Should not raise:
        manager._sync_event_to_env(env, _make_event("audit_only_event"))

        assert manager.metrics.handlers_silently_skipped == 1
        assert manager.metrics.handlers_invoked == 0
        assert manager.metrics.handlers_failed == 0

    def test_impact_only_event_silently_skips_env_sync(
        self, registry_isolation
    ):
        """Phase 6T-A code-review P1 regression test: an event_type
        registered ONLY in ``agent_impact_handlers`` (not
        ``event_handlers``) must NOT raise from ``_sync_event_to_env``
        when the pack lists it in ``silent_skip_event_types``.

        Pre-6T-A behaviour was implicit silent-skip (the if check
        ``if event.event_type in pack.event_handlers()`` failed); the
        6T-A explicit-opt-in contract preserves the same end-state
        via the silent_skip allowlist. The FloodEventMixin's
        ``flood_damage`` + ``insurance_payout`` impact-only types
        are the production motivator — this test pins the contract
        using ``_GoodPack``'s ``impact_only_type`` which mirrors the
        same shape."""
        DomainPackRegistry.register("goodpack", _GoodPack())
        manager = MAEventManager()
        env = _MockEnv()

        # Impact-only event must silent-skip, NOT raise:
        manager._sync_event_to_env(env, _make_event("impact_only_type"))

        assert manager.metrics.handlers_silently_skipped == 1
        assert manager.metrics.handlers_invoked == 0
        assert manager.metrics.handlers_failed == 0

        # And get_agent_impact still routes the same event_type
        # through its separate dispatch path:
        impact_event = EnvironmentEvent(
            event_type="impact_only_type",
            severity=EventSeverity.INFO,
            scope=EventScope.AGENT,
            description="impact",
            affected_agents=["H001"],
        )
        manager._current_events["x"] = [impact_event]
        impact = manager.get_agent_impact("H001")
        assert impact.get("damage") == 1


# ─────────────────────────────────────────────────────────────────────
# Class 2 — Handler exception isolation
# ─────────────────────────────────────────────────────────────────────


class TestHandlerExceptionIsolation:
    """R3: a raising handler must NOT crash the year — capture into
    EventDispatchMetrics + log + continue."""

    def test_handler_exception_captured_as_broker_handler_error(
        self, registry_isolation, caplog
    ):
        """A handler that raises is caught, recorded as a
        BrokerHandlerError on the metrics counter, and logged at ERROR
        level — but does NOT propagate to the caller."""
        bad_pack = _RaisingPack()
        DomainPackRegistry.register("raisingpack", bad_pack)
        manager = MAEventManager()
        env = _MockEnv()

        import logging

        with caplog.at_level(logging.ERROR):
            # Must not raise:
            manager._sync_event_to_env(env, _make_event("known_event"))

        assert bad_pack.handler_calls == 1
        assert manager.metrics.handlers_failed == 1
        assert manager.metrics.handlers_invoked == 0
        assert len(manager.metrics.errors) == 1
        err = manager.metrics.errors[0]
        assert isinstance(err, BrokerHandlerError)
        assert err.event_type == "known_event"
        assert err.exception_type == "RuntimeError"
        assert "simulated handler failure" in err.exception_message
        assert "RuntimeError" in caplog.text

    def test_successful_handler_increments_invoked_counter(
        self, registry_isolation
    ):
        """Sanity-check: a non-raising handler increments
        handlers_invoked, NOT handlers_failed."""
        DomainPackRegistry.register("goodpack", _GoodPack())
        manager = MAEventManager()
        env = _MockEnv()

        manager._sync_event_to_env(env, _make_event("good_event"))

        assert manager.metrics.handlers_invoked == 1
        assert manager.metrics.handlers_failed == 0
        assert env.global_state == {"good_seen": True}


# ─────────────────────────────────────────────────────────────────────
# Class 3 — Event lifecycle / persistence policy
# ─────────────────────────────────────────────────────────────────────


class TestEventLifecycle:
    """R4/Y2: clear_ephemeral_events honours per-event EventPersistence;
    clear_all_events wipes regardless."""

    def test_clear_ephemeral_preserves_sticky_drops_ephemeral(
        self, registry_isolation
    ):
        DomainPackRegistry.register("stickypack", _StickyPack())
        manager = MAEventManager()

        sticky = _make_event("sticky_event")
        ephemeral = _make_event("ephemeral_event")
        manager._current_events["x"] = [sticky, ephemeral]
        manager._event_context["x_events"] = [sticky, ephemeral]

        manager.clear_ephemeral_events()

        # sticky_event survives, ephemeral_event dropped:
        assert "x" in manager._current_events
        assert len(manager._current_events["x"]) == 1
        assert manager._current_events["x"][0].event_type == "sticky_event"
        assert "x_events" in manager._event_context
        assert len(manager._event_context["x_events"]) == 1
        # Metrics reset on year boundary:
        assert manager.metrics.handlers_invoked == 0

    def test_clear_all_events_drops_everything(self, registry_isolation):
        DomainPackRegistry.register("stickypack", _StickyPack())
        manager = MAEventManager()

        manager._current_events["x"] = [_make_event("sticky_event")]
        manager._event_context["x_events"] = [_make_event("sticky_event")]
        manager.metrics.record_invoke()

        manager.clear_all_events()

        assert manager._current_events == {}
        assert manager._event_context == {}
        assert manager.metrics.handlers_invoked == 0


# ─────────────────────────────────────────────────────────────────────
# Class 4 — Phase config hard-fail
# ─────────────────────────────────────────────────────────────────────


class TestPhaseConfigHardFail:
    """O4/O5: PhaseOrchestrator raises on misconfig instead of warning."""

    def test_invalid_phase_config_on_missing_dependency_in_yaml(
        self, tmp_path
    ):
        """from_yaml must raise InvalidPhaseConfigError when a YAML
        entry's depends_on names a phase not in the same orchestrator.
        Pre-6T-A this silently dropped the unknown dep."""
        yaml_path = tmp_path / "phases.yaml"
        yaml_path.write_text(
            "phases:\n"
            "  - phase: observation\n"
            "    agent_types: []\n"
            "    depends_on:\n"
            "      - definitely_not_a_real_phase\n",
            encoding="utf-8",
        )
        with pytest.raises(InvalidPhaseConfigError, match="definitely_not_a_real_phase"):
            PhaseOrchestrator.from_yaml(str(yaml_path))

    def test_phase_dependency_cycle_error_on_topological_cycle(self):
        """A → B → A dependency loop must raise PhaseDependencyCycleError
        when get_execution_plan triggers topological_order. Pre-6T-A
        this returned phases in the original (unsorted) order."""
        # Build a cycle via two CUSTOM-class phases — Python enum dedupe
        # would normally prevent this in practice, but the orchestrator
        # used to silently fall through cycles in mixed-enum configs.
        phases = [
            PhaseConfig(
                phase=ExecutionPhase.CUSTOM,
                agent_types=[],
                depends_on=[ExecutionPhase.RESOLUTION],
            ),
            PhaseConfig(
                phase=ExecutionPhase.RESOLUTION,
                agent_types=[],
                depends_on=[ExecutionPhase.CUSTOM],
            ),
        ]
        orch = PhaseOrchestrator(phases=phases)
        with pytest.raises(PhaseDependencyCycleError, match="cycle"):
            orch.get_execution_plan(agents={})
