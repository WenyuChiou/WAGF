"""Phase 6Q-D-5 (2026-05-26) — cascade-defense for the remaining
two open boundary-audit pairs.

Pair #4b (MED): ``UnifiedCognitiveEngine.__init__`` now wraps
surprise-strategy construction in try/except, falling back to
``self._strategy = None`` if Phase 6Q-C's strict-required-kwarg
ValueError fires from an edge case.

Pair #5 (MED-HIGH): ``DomainPackRegistry.register`` now smoke-tests
a representative subset of DomainPack methods at registration time
so broken packs surface at module-import (where the trace points at
the registration call site) instead of mysteriously during a
multi-hour experiment run.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import pytest

import broker.domains.water  # noqa: F401
from broker.domains.default import DefaultDomainPack
from broker.domains.registry import DomainPackRegistry


# ─────────────────────────────────────────────────────────────────────
# Pair #4b — UnifiedCognitiveEngine
# ─────────────────────────────────────────────────────────────────────

class TestUnifiedEngineStrategyConstructionGuard:
    def test_invalid_stimulus_key_falls_back_to_null_strategy(
        self, caplog, monkeypatch
    ):
        """Force a strategy-construction raise via monkey-patch of the
        EMASurpriseStrategy class itself. Pre-6Q-D-5 this would have
        crashed UnifiedCognitiveEngine; post-6Q-D-5 the engine logs +
        falls back to ``self._strategy = None``. The engine's local
        ``from .strategies import EMASurpriseStrategy`` line 229
        picks up the patched class because Python's `from X import Y`
        re-binds at call time when the import is inside a function."""
        from broker.memory.unified_engine import UnifiedCognitiveEngine
        from broker.memory.config import GlobalMemoryConfig, DomainMemoryConfig
        import broker.memory.strategies as strategies_mod

        class _RaisingEMA:
            def __init__(self, *args, **kwargs):
                raise ValueError("simulated 6Q-C strict-required raise")

        monkeypatch.setattr(
            strategies_mod, "EMASurpriseStrategy", _RaisingEMA, raising=True
        )

        caplog.set_level(
            logging.WARNING, logger="broker.memory.unified_engine"
        )
        engine = UnifiedCognitiveEngine(
            global_config=GlobalMemoryConfig(),
            domain_config=DomainMemoryConfig(stimulus_key="depth_m"),
        )
        # Engine constructed despite strategy raise → null fallback.
        assert engine._strategy is None
        assert any(
            "null strategy" in rec.getMessage()
            for rec in caplog.records
        ), "expected fallback warning"

    def test_explicit_strategy_bypass_guard(self):
        """If caller passes an explicit `surprise_strategy=`, the
        guard never fires (no construction needed)."""
        from broker.memory.strategies.ema import EMASurpriseStrategy
        from broker.memory.unified_engine import UnifiedCognitiveEngine
        from broker.memory.config import GlobalMemoryConfig, DomainMemoryConfig

        strategy = EMASurpriseStrategy(stimulus_key="x")
        engine = UnifiedCognitiveEngine(
            global_config=GlobalMemoryConfig(),
            domain_config=DomainMemoryConfig(),
            surprise_strategy=strategy,
        )
        assert engine._strategy is strategy


# ─────────────────────────────────────────────────────────────────────
# Pair #5 — DomainPackRegistry smoke at registration
# ─────────────────────────────────────────────────────────────────────

class _BrokenAtRegistrationPack(DefaultDomainPack):
    """Custom pack whose `psychological_framework()` raises — meant to
    simulate a partial-init / circular-import / typo'd-attribute
    failure that DefaultDomainPack inheritance would normally mask."""
    name: str = "test_broken_at_registration"

    def psychological_framework(self) -> str:
        raise RuntimeError("simulated post-import broken state")


class _MissingMethodPack:
    """Custom pack with the required `name` attr but missing methods.

    Important: NOT a DefaultDomainPack subclass — doesn't inherit any
    of the safe defaults. Mimics a third-party pack written from
    scratch against the Protocol without using the base class.
    """
    name: str = "test_missing_method_pack"


@pytest.fixture
def restore_registry():
    saved = dict(DomainPackRegistry._packs)
    yield
    DomainPackRegistry.clear()
    for k, v in saved.items():
        DomainPackRegistry._packs[k] = v  # bypass smoke-test on restore


class TestDomainPackRegistrySmokeTest:
    def test_broken_method_logs_warning_but_still_registers(
        self, restore_registry, caplog
    ):
        """A pack whose `psychological_framework()` raises gets a
        warning at registration time, but is still registered (Phase
        6Q-D-4 graceful-fallback in dispatchers handles it
        downstream). The point of the smoke is EARLIER detection."""
        caplog.set_level(logging.WARNING, logger="broker.domains.registry")
        pack = _BrokenAtRegistrationPack()
        DomainPackRegistry.register("test_broken_at_registration", pack)

        # Pack IS registered.
        assert (
            DomainPackRegistry.get("test_broken_at_registration") is pack
        )
        # Warning fired with method name + exception type.
        assert any(
            "psychological_framework() raised RuntimeError" in rec.getMessage()
            and "test_broken_at_registration" in rec.getMessage()
            for rec in caplog.records
        )

    def test_missing_method_logs_warning(self, restore_registry, caplog):
        """A pack that doesn't have a smoke-tested method gets a
        'missing method' warning."""
        caplog.set_level(logging.WARNING, logger="broker.domains.registry")
        pack = _MissingMethodPack()
        DomainPackRegistry.register("test_missing_method_pack", pack)

        # Pack IS registered.
        assert DomainPackRegistry.get("test_missing_method_pack") is pack
        # Warning lists missing methods.
        msgs = [rec.getMessage() for rec in caplog.records]
        assert any(
            "missing method 'psychological_framework'" in m
            or 'missing method "psychological_framework"' in m
            for m in msgs
        )

    def test_happy_path_pack_registers_silently(self, restore_registry, caplog):
        """Phase 6Q-D-5 contract: a well-behaved pack should register
        with ZERO warnings from the smoke test. FloodDomainPack /
        DefaultDomainPack / IrrigationDomainPack are well-behaved."""
        caplog.set_level(logging.WARNING, logger="broker.domains.registry")

        # FloodDomainPack already registered by examples.governed_flood
        # auto-import in this test session — re-register it to trigger
        # the smoke explicitly.
        from examples.governed_flood.adapters.flood_pack import FloodDomainPack
        DomainPackRegistry.register("test_happy_flood", FloodDomainPack())

        # Zero warnings from the registry logger for the happy path.
        registry_warns = [
            rec for rec in caplog.records
            if rec.name == "broker.domains.registry"
            and "test_happy_flood" in rec.getMessage()
        ]
        assert not registry_warns, (
            f"happy-path pack triggered unexpected warnings: "
            f"{[w.getMessage() for w in registry_warns]}"
        )
