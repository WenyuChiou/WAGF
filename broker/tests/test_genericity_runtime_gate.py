"""Phase 6Q-F-1 (2026-05-26) — runtime genericity gate.

The static AST guards at ``test_framework_invariants.py``
(``TestNoReverseDomainImport``, ``TestNoFloodVocabInGenericEventGenerators``)
catch module-level reverse imports + flood-vocab leaks in generic
broker source. They do NOT catch the runtime case where a non-water
domain calls ``build_domain_validators`` and the dispatcher silently
pulls in water-namespace code at call time.

This file is the runtime complement: it registers a `FakeTrafficDomainPack`
(a deliberately minimal non-water DomainPack), runs the full
governance-dispatch path, and asserts the result is domain-agnostic.
Together with the existing AST guards this forms a 3-layer gate.

Full Phase 6Q-F E2E (synthetic 1-year run with mock LLM) is deferred
to 6Q-F-2; this file is the lower-cost first pass that catches the
common runtime regressions without needing the agent pipeline.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from broker.domains.default import DefaultDomainPack
from broker.domains.registry import DomainPackRegistry


# ─────────────────────────────────────────────────────────────────────
# Fake non-water DomainPack
# ─────────────────────────────────────────────────────────────────────

class FakeTrafficDomainPack(DefaultDomainPack):
    """Minimum-surface non-water DomainPack for the genericity gate.

    Overrides only `name` — every other DomainPack method falls
    through to the DefaultDomainPack no-op. The point of the gate is
    to exercise the *generic broker* code path with a domain whose
    pack supplies the bare-minimum identifier; if any generic broker
    module silently falls back to water-namespace behaviour, this
    test will surface it (either via the sys.modules check below or
    via a structural-validator assertion).
    """
    name: str = "traffic"


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_traffic_registry():
    """Save + restore DomainPackRegistry around the test."""
    saved = dict(DomainPackRegistry._packs)
    DomainPackRegistry.register("traffic", FakeTrafficDomainPack())
    yield
    DomainPackRegistry.clear()
    for name, pack in saved.items():
        DomainPackRegistry.register(name, pack)


# ─────────────────────────────────────────────────────────────────────
# Structural gate — in-process
# ─────────────────────────────────────────────────────────────────────

class TestTrafficDomainStructuralGate:
    """Runtime structural assertions on the validator graph built for
    a non-water domain. Same-process; does not test sys.modules
    (because the test runner may already have water modules loaded
    from a prior test in the suite — see the subprocess gate below
    for that check)."""

    def test_psychological_framework_is_escape_hatch(self):
        """A non-water DomainPack inherits DefaultDomainPack's
        psychological_framework() — the FRAMEWORK_ESCAPE_HATCH
        sentinel, NOT silently "pmt"."""
        from broker.validators.governance.thinking_validator import (
            FRAMEWORK_ESCAPE_HATCH,
        )
        pack = FakeTrafficDomainPack()
        assert pack.psychological_framework() == FRAMEWORK_ESCAPE_HATCH

    def test_extreme_actions_is_empty(self):
        """Non-water DomainPack default extreme_actions is empty set —
        no silent {"relocate", "elevate_house"} flood inheritance."""
        pack = FakeTrafficDomainPack()
        assert pack.extreme_actions() == set()

    def test_csv_loader_class_is_none(self):
        """Non-water DomainPack default csv_loader_class is None →
        broker uses generic CSVLoader, not FloodCSVLoader."""
        pack = FakeTrafficDomainPack()
        assert pack.csv_loader_class() is None
        assert pack.synthetic_loader_class() is None

    def test_phase_layout_is_none(self):
        """Non-water DomainPack default phase_layout is None →
        broker uses generic 3-phase layout, not water 4-phase."""
        pack = FakeTrafficDomainPack()
        assert pack.phase_layout() is None

    def test_dispatcher_returns_empty_validators_for_unregistered_traffic(
        self, fresh_traffic_registry
    ):
        """The DomainPack is registered but `ValidatorRegistry` has
        no traffic-domain checks → dispatcher returns ``_empty_validators()``
        (5 validators with no builtin_checks + framework="")."""
        from broker.components.governance.domain_validator_dispatch import (
            build_domain_validators,
        )
        from broker.validators.governance.thinking_validator import (
            ThinkingValidator,
            FRAMEWORK_ESCAPE_HATCH,
        )

        validators = build_domain_validators("traffic")
        assert len(validators) == 5
        thinking = next(v for v in validators if isinstance(v, ThinkingValidator))
        assert thinking.framework == FRAMEWORK_ESCAPE_HATCH, (
            f"non-water domain inherited framework={thinking.framework!r} — "
            f"silently fell back to PMT/flood?"
        )
        assert not thinking._builtin_checks


# ─────────────────────────────────────────────────────────────────────
# Subprocess gate — sys.modules check
# ─────────────────────────────────────────────────────────────────────

GATE_SCRIPT = r"""
import sys, json

# Step 1: import broker minimally (registry + dispatcher).
from broker.domains.registry import DomainPackRegistry
from broker.domains.default import DefaultDomainPack

class FakeTrafficDomainPack(DefaultDomainPack):
    name = "traffic"

DomainPackRegistry.clear()
DomainPackRegistry.register("traffic", FakeTrafficDomainPack())

# Step 2: build validators for traffic.
from broker.components.governance.domain_validator_dispatch import build_domain_validators
validators = build_domain_validators("traffic")
assert len(validators) == 5, f"expected 5 validators, got {len(validators)}"

# Step 3: dump sys.modules entries under broker.domains.water.
water_modules = sorted(m for m in sys.modules if m.startswith("broker.domains.water"))
print(json.dumps({"water_modules": water_modules, "validator_count": len(validators)}))
"""


class TestTrafficDomainSysModulesGate:
    """Subprocess-isolated sys.modules check.

    Spawns a fresh Python interpreter, imports only the bare-minimum
    broker layers needed to register + dispatch the traffic domain,
    and asserts ``sys.modules`` contains zero ``broker.domains.water.*``
    entries. This is the runtime version of the Phase 6N-F-7 AST
    guard — it catches any *lazy* (function-local / on-demand)
    import that the AST scan misses.

    Currently **xfails** by design — Phase 6Q-F-1 (this commit)
    surfaces the root cause: ``broker/domains/__init__.py`` runs
    ``_discover_domain_packs()`` at module-load time, which scans
    every sub-package under ``broker/domains/`` (currently only
    ``water``) and calls its ``register()`` function. Even a bare
    ``from broker.domains.protocol import DomainPack`` triggers the
    package ``__init__``, which loads water's framework + thinking
    checks unconditionally.

    The fix (Phase 6Q-G):
      - Remove the auto-discovery loop OR make it opt-in via env var.
      - Have ``broker.domains.water`` register itself only when an
        ``examples/`` package or test fixture explicitly imports it,
        same as `examples.governed_flood`, `examples.irrigation_abm`,
        `examples.vaccination_demo` already do for ``DomainPackRegistry``.
      - The water psychometric-framework registry then becomes lazy:
        ``broker.core.psychometric.get_framework("pmt")`` triggers
        the load only when needed.

    When 6Q-G lands, remove the ``xfail`` marker below; the test
    becomes the regression guard.
    """

    @pytest.mark.xfail(
        reason="Phase 6Q-G pending: broker/domains/__init__.py "
               "auto-discovery loads water at module-load time. "
               "Gate intentionally fails today to document the "
               "violation; fix lands in 6Q-G.",
        strict=False,
    )
    def test_traffic_dispatch_does_not_load_water_modules(self):
        repo = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-c", GATE_SCRIPT],
            capture_output=True,
            text=True,
            cwd=str(repo),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"gate script failed (rc={result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        import json
        payload = json.loads(result.stdout.strip().split("\n")[-1])
        assert payload["validator_count"] == 5
        assert not payload["water_modules"], (
            f"`broker.domains.water.*` modules leaked into a "
            f"non-water domain's runtime dispatch path: "
            f"{payload['water_modules']}. The AST guard at "
            f"TestNoReverseDomainImport caught load-time leaks; "
            f"this gate catches lazy / function-local imports the "
            f"AST scan misses."
        )
