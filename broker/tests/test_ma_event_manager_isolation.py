"""Phase 6T-G regression: ``MAEventManager.generate_phase`` no longer
mutates the caller's ``context`` dict.

Pre-6T-G the method called ``context.update(self._event_context)`` and
``context[provides_key] = …``, silently leaking dependency-chain state
into the caller's mapping. Callers that relied on that leak are
undocumented; this test locks the new (non-mutating) contract.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from broker.components.events.ma_manager import (
    EventPhase,
    MAEventManager,
)
from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventScope,
    EventSeverity,
)


class _StubGenerator:
    """Minimal generator that emits one event and observes the
    dependency-chain context value if one is provided. Used to verify
    that dependency state still flows internally even after the
    Phase 6T-G non-mutation refactor."""

    def __init__(self, name: str, depends_on_key: Optional[str] = None):
        self.name = name
        self.depends_on_key = depends_on_key
        self.observed_dep_value: Any = "<unset>"

    def generate(self, year: int, step: int, context: Dict[str, Any]) -> List[EnvironmentEvent]:
        if self.depends_on_key is not None:
            self.observed_dep_value = context.get(self.depends_on_key, "<missing>")
        return [
            EnvironmentEvent(
                event_type=self.name,
                severity=EventSeverity.MINOR,
                scope=EventScope.GLOBAL,
                description=f"{self.name} fired",
                data={},
                affected_agents=[],
                domain=self.name,
            )
        ]


@pytest.fixture
def manager():
    """A MAEventManager with two stub generators in a dependency
    chain. ``second`` depends on ``first``'s output via the
    ``first_events`` context key."""
    mgr = MAEventManager()
    mgr.register_with_deps(
        domain="first",
        generator=_StubGenerator("first"),
        phase=EventPhase.PRE_YEAR,
        depends_on=[],
        provides="first_events",
    )
    mgr.register_with_deps(
        domain="second",
        generator=_StubGenerator("second", depends_on_key="first_events"),
        phase=EventPhase.PRE_YEAR,
        depends_on=["first"],
        provides="second_events",
    )
    return mgr


def test_generate_phase_does_not_mutate_caller_context(manager):
    """The caller's ``context`` dict must be byte-identical (no new
    keys, no overwritten values) after ``generate_phase`` returns."""
    sentinel = object()
    original = {"agents": {"a1": sentinel}, "environment": {"temp": 20}}
    snapshot_keys_before = set(original)
    snapshot_agents = original["agents"]
    snapshot_env = original["environment"]

    manager.generate_phase(EventPhase.PRE_YEAR, year=1, context=original)

    assert set(original) == snapshot_keys_before, (
        f"caller's context dict gained new keys: "
        f"{set(original) - snapshot_keys_before}"
    )
    # The nested dicts must be the same objects (no replacement) and
    # their contents unchanged.
    assert original["agents"] is snapshot_agents
    assert original["environment"] is snapshot_env
    assert original["agents"]["a1"] is sentinel
    assert original["environment"]["temp"] == 20
    # Pre-6T-G this assertion would fail: ``first_events`` would have
    # leaked into the caller's dict.
    assert "first_events" not in original, (
        "caller's context was mutated with internal _event_context key — "
        "pre-6T-G Y1 leak regression"
    )


def test_generate_phase_still_passes_deps_through_working_copy(manager):
    """Dependency-chain state still flows internally — the second
    generator sees the first's output in the working copy even though
    the caller's dict is no longer mutated."""
    manager.generate_phase(EventPhase.PRE_YEAR, year=1, context={})

    second_gen = manager._generators["second"]
    assert second_gen.observed_dep_value != "<unset>", (
        "second generator never received its dependency — chain broken"
    )
    assert second_gen.observed_dep_value != "<missing>", (
        "second generator's working context lacked first_events — "
        "dependency injection broke during the Y1 refactor"
    )
    assert isinstance(second_gen.observed_dep_value, list)
    assert len(second_gen.observed_dep_value) == 1
    assert second_gen.observed_dep_value[0].event_type == "first"
