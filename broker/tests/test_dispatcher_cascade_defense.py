"""Phase 6Q-D-4 (2026-05-26) — cascade-failure defense for
`build_domain_validators`.

Phase 6Q-D-3 follow-up boundary-audit identified the dispatcher →
`ThinkingValidator.__init__` boundary as the highest-leverage
failure point in the governance subsystem: a custom DomainPack
returning a typo'd / unregistered psychological_framework string
caused ThinkingValidator to raise ValueError, which propagated
through validate_all → SkillBrokerEngine retry loop → killed the
entire agent's year-N decision. No graceful fallback existed.

Phase 6Q-D-4 added two defenses to ``build_domain_validators``:

  1. Each DomainPack accessor (``extreme_actions`` /
     ``psychological_framework``) wrapped in its own try/except.
     Broken pack methods now log a warning + fall back to a benign
     default (empty set / escape hatch) instead of crashing.
  2. Pre-construction registry check on the framework string —
     unregistered values downgrade to FRAMEWORK_ESCAPE_HATCH with
     a warn-once-per-(domain, framework) dedup.

These tests pin that contract.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import pytest

import broker.domains.water  # noqa: F401 — ensures water frameworks registered
from broker.components.governance.domain_validator_dispatch import (
    _WARNED_UNREGISTERED_FRAMEWORK,
    build_domain_validators,
)
from broker.domains.default import DefaultDomainPack
from broker.domains.registry import DomainPackRegistry
from broker.validators.governance.thinking_validator import (
    FRAMEWORK_ESCAPE_HATCH,
    FRAMEWORK_LABEL_ORDERS,
    ThinkingValidator,
)


# ─────────────────────────────────────────────────────────────────────
# Fake DomainPack fixtures
# ─────────────────────────────────────────────────────────────────────

class _BrokenFrameworkPack(DefaultDomainPack):
    """Custom pack whose `psychological_framework()` returns a typo
    that is NOT in FRAMEWORK_LABEL_ORDERS."""
    name: str = "test_typo_domain"

    def psychological_framework(self) -> str:
        return "pmtt"  # intentional typo


class _RaisesFrameworkPack(DefaultDomainPack):
    """Custom pack whose `psychological_framework()` raises."""
    name: str = "test_raise_framework_domain"

    def psychological_framework(self) -> str:
        raise RuntimeError("simulated pack breakage in psychological_framework")


class _RaisesExtremePack(DefaultDomainPack):
    """Custom pack whose `extreme_actions()` raises."""
    name: str = "test_raise_extreme_domain"

    def extreme_actions(self) -> set:
        raise RuntimeError("simulated pack breakage in extreme_actions")


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def restore_registries():
    """Save + restore DomainPackRegistry + the warn-once dedup set
    around each test so they don't leak across cases."""
    saved_packs = dict(DomainPackRegistry._packs)
    saved_warned = set(_WARNED_UNREGISTERED_FRAMEWORK)
    _WARNED_UNREGISTERED_FRAMEWORK.clear()
    yield
    DomainPackRegistry.clear()
    for name, pack in saved_packs.items():
        DomainPackRegistry.register(name, pack)
    _WARNED_UNREGISTERED_FRAMEWORK.clear()
    _WARNED_UNREGISTERED_FRAMEWORK.update(saved_warned)


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────

class TestUnregisteredFrameworkDowngrade:
    """Pair #3 from the boundary audit — HIGH cascade risk."""

    def test_typo_framework_downgrades_to_escape_hatch(
        self, restore_registries, caplog
    ):
        # Phase 6Q-D-4: pre-fix this was a HIGH cascade — ValueError
        # propagated through validate_all and crashed the pipeline.
        DomainPackRegistry.register("test_typo_domain", _BrokenFrameworkPack())
        from broker.components.governance.validator_registry import (
            ValidatorRegistry,
        )
        ValidatorRegistry.register("test_typo_domain", "personal", [lambda: None])

        caplog.set_level(
            logging.WARNING,
            logger="broker.components.governance.domain_validator_dispatch",
        )
        validators = build_domain_validators("test_typo_domain")

        assert len(validators) == 5, "dispatch must still build 5 validators"
        thinking = next(v for v in validators if isinstance(v, ThinkingValidator))
        assert thinking.framework == FRAMEWORK_ESCAPE_HATCH, (
            f"typo'd framework should downgrade to escape hatch, "
            f"got {thinking.framework!r}"
        )
        assert any(
            "pmtt" in rec.getMessage() and "FRAMEWORK_ESCAPE_HATCH" in rec.getMessage()
            for rec in caplog.records
        ), "expected a downgrade warning naming the typo and the fallback"

    def test_downgrade_warn_dedup_per_domain_framework(
        self, restore_registries, caplog
    ):
        # Warn-once-per-(domain, framework). 3 dispatch calls = 1 warn.
        DomainPackRegistry.register("test_typo_domain", _BrokenFrameworkPack())
        from broker.components.governance.validator_registry import (
            ValidatorRegistry,
        )
        ValidatorRegistry.register("test_typo_domain", "personal", [lambda: None])

        caplog.set_level(
            logging.WARNING,
            logger="broker.components.governance.domain_validator_dispatch",
        )
        for _ in range(3):
            build_domain_validators("test_typo_domain")

        warn_count = sum(
            1 for rec in caplog.records
            if "pmtt" in rec.getMessage() and "FRAMEWORK_ESCAPE_HATCH" in rec.getMessage()
        )
        assert warn_count == 1, (
            f"warn-once dedup broken: 3 dispatch calls produced "
            f"{warn_count} warnings (expected 1)"
        )


class TestPackMethodRaiseGracefulFallback:
    """Pair #2 from the boundary audit — MED cascade risk."""

    def test_psychological_framework_raise_falls_back_to_escape_hatch(
        self, restore_registries, caplog
    ):
        DomainPackRegistry.register(
            "test_raise_framework_domain", _RaisesFrameworkPack()
        )
        from broker.components.governance.validator_registry import (
            ValidatorRegistry,
        )
        ValidatorRegistry.register("test_raise_framework_domain", "personal", [lambda: None])

        caplog.set_level(
            logging.WARNING,
            logger="broker.components.governance.domain_validator_dispatch",
        )
        validators = build_domain_validators("test_raise_framework_domain")

        thinking = next(v for v in validators if isinstance(v, ThinkingValidator))
        assert thinking.framework == FRAMEWORK_ESCAPE_HATCH
        assert any(
            "psychological_framework() raised" in rec.getMessage()
            for rec in caplog.records
        )

    def test_extreme_actions_raise_falls_back_to_empty_set(
        self, restore_registries, caplog
    ):
        DomainPackRegistry.register(
            "test_raise_extreme_domain", _RaisesExtremePack()
        )
        from broker.components.governance.validator_registry import (
            ValidatorRegistry,
        )
        ValidatorRegistry.register("test_raise_extreme_domain", "personal", [lambda: None])

        caplog.set_level(
            logging.WARNING,
            logger="broker.components.governance.domain_validator_dispatch",
        )
        validators = build_domain_validators("test_raise_extreme_domain")

        thinking = next(v for v in validators if isinstance(v, ThinkingValidator))
        assert thinking._extreme_actions == set()
        assert any(
            "extreme_actions() raised" in rec.getMessage()
            for rec in caplog.records
        )


class TestHappyPathUntouched:
    """Phase 6Q-D-4 defense must not regress the registered-framework
    happy path (i.e. FloodDomainPack → 'pmt' must still work)."""

    def test_registered_pmt_framework_passes_through(self, restore_registries):
        # FloodDomainPack registers "flood" → "pmt" (registered framework).
        import examples.governed_flood  # noqa: F401
        validators = build_domain_validators("flood")
        thinking = next(v for v in validators if isinstance(v, ThinkingValidator))
        assert thinking.framework == "pmt", (
            f"happy path broken: flood domain should resolve to 'pmt', "
            f"got {thinking.framework!r}"
        )
        # Sanity: framework IS in the registered set (no downgrade
        # warning should have fired).
        assert "pmt" in FRAMEWORK_LABEL_ORDERS
