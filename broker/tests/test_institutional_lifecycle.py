"""
Phase 6T-C tests for the institutional-lifecycle extension point.

Closes engineering-audit findings R5 (no per-agent-type lifecycle
extension point) + R6 (bespoke MultiAgentHooks class bloats with
every new institutional type). Phase 6T-C scope is INTERFACE-ONLY —
the extraction of existing flood gov/insurance code from
``examples/multi_agent/flood/orchestration/lifecycle_hooks.py`` is
deferred to Phase 6T-F (when the ``social_media_influencer``
agent_type becomes the second consumer of the pattern).

This test suite pins the Phase 6T-C contract:

1. :class:`InstitutionalLifecycleHandler` ABC carries three no-op
   lifecycle hooks (``pre_year``, ``post_decision``, ``post_year``);
   subclasses can override zero or more.
2. :meth:`SetupPack.institutional_lifecycle_handlers` returns a
   ``Dict[str, InstitutionalLifecycleHandler]`` keyed by agent_type;
   default empty.
3. :meth:`SetupPack.multi_agent_env_keys` returns ``Set[str]`` of
   env-dict keys the domain owns; default empty.
4. broker/ generic invariant preserved (no domain tokens in the new
   abstractions).

Inline-mock-pack budget: stays under the
``TestNoExcessiveInlineMockPacks`` ≤3 limit by consolidating fixture
behaviour into 2 multi-purpose packs (``_DemoPackWithHandlers`` +
``_DemoPackEnvOnly``) instead of one-pack-per-test.

Plan: ``~/.claude/plans/swirling-knitting-lighthouse.md`` 6T-C.
"""
from __future__ import annotations

from typing import Any, Dict, Set

import pytest

from broker.components.orchestration.institutional_lifecycle import (
    InstitutionalLifecycleHandler,
)
from broker.domains.default import DefaultDomainPack
from broker.domains.protocol import SetupPack


# ─────────────────────────────────────────────────────────────────────
# Fixture packs (kept under the ≤3 inline-mock-pack invariant)
# ─────────────────────────────────────────────────────────────────────


_GOV_DECISIONS: list = []
_INS_DECISIONS: list = []


class _GovHandler(InstitutionalLifecycleHandler):
    """Demo handler — records post_decision calls for assertions."""

    def post_decision(self, agent, decision, year, env):
        _GOV_DECISIONS.append((decision, year))


class _InsHandler(InstitutionalLifecycleHandler):
    """Demo handler — records post_decision calls for assertions."""

    def post_decision(self, agent, decision, year, env):
        _INS_DECISIONS.append((decision, year))


class _DemoPackWithHandlers(DefaultDomainPack):
    """Multi-purpose demo pack covering: Protocol structural typing,
    handler dispatch by agent_type, KeyError on unknown lookup, and
    one half of the env-keys-union test."""

    name = "demopackhandlers"

    def institutional_lifecycle_handlers(self) -> Dict[str, Any]:
        return {
            "government": _GovHandler(),
            "insurance": _InsHandler(),
        }

    def multi_agent_env_keys(self) -> Set[str]:
        return {"subsidy_rate", "govt_budget_remaining"}


class _DemoPackEnvOnly(DefaultDomainPack):
    """Multi-purpose demo pack covering: empty-handlers behaviour
    via inherited DefaultDomainPack default, and the other half of
    the env-keys-union test."""

    name = "demopackenvonly"

    def multi_agent_env_keys(self) -> Set[str]:
        return {"premium_rate", "crs_discount"}


@pytest.fixture(autouse=True)
def _reset_demo_state():
    """Clear module-level handler logs between tests."""
    _GOV_DECISIONS.clear()
    _INS_DECISIONS.clear()
    yield
    _GOV_DECISIONS.clear()
    _INS_DECISIONS.clear()


# ─────────────────────────────────────────────────────────────────────
# Class 1 — InstitutionalLifecycleHandler ABC contract
# ─────────────────────────────────────────────────────────────────────


class TestInstitutionalLifecycleHandlerContract:
    """The ABC must accept subclasses that override zero or more
    lifecycle hooks, and its default no-op hooks must accept the
    canonical arguments without raising."""

    def test_base_class_instantiable_when_subclassed(self):
        """Subclassing the ABC + calling the no-op defaults must
        not raise. The base class itself has no abstract methods
        (all three hooks have default no-op impls)."""

        class _Plain(InstitutionalLifecycleHandler):
            pass

        handler = _Plain()
        handler.pre_year(agent=object(), year=1, env={})
        handler.post_decision(agent=object(), decision="maintain", year=1, env={})
        handler.post_year(agent=object(), year=1, env={})

    def test_subclass_can_override_single_hook(self):
        """A subclass overriding only ``post_decision`` keeps the
        no-op defaults for ``pre_year`` + ``post_year``."""
        invocations = []

        class _OnlyPostDecision(InstitutionalLifecycleHandler):
            def post_decision(self, agent, decision, year, env):
                invocations.append(("post_decision", decision, year))

        handler = _OnlyPostDecision()
        handler.pre_year(agent=object(), year=1, env={})  # no-op default
        handler.post_decision(
            agent=object(), decision="approve_buyout", year=2, env={}
        )
        handler.post_year(agent=object(), year=3, env={})  # no-op default

        assert invocations == [("post_decision", "approve_buyout", 2)]

    def test_subclass_can_mutate_env_in_post_decision(self):
        """post_decision is the canonical state-mutation hook —
        subclasses MAY mutate env. The runner makes no thread-safety
        guarantee for parallel dispatch (single-threaded contract)."""

        class _BudgetHandler(InstitutionalLifecycleHandler):
            def post_decision(self, agent, decision, year, env):
                env["budget_remaining"] = env.get("budget_remaining", 100) - 10

        handler = _BudgetHandler()
        env = {"budget_remaining": 50}
        handler.post_decision(agent=object(), decision="x", year=1, env=env)
        assert env["budget_remaining"] == 40

    def test_module_does_not_import_domain_specific_code(self):
        """Phase 6T-C genericity invariant: the institutional_lifecycle
        module must not import broker.domains.water, examples, or any
        domain-specific module. Verified by AST-scanning the module
        source for forbidden import patterns."""
        import ast
        from pathlib import Path

        import broker.components.orchestration.institutional_lifecycle as module
        source_path = Path(module.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        forbidden_prefixes = (
            "broker.domains.water",
            "broker.components.events.water",
            "examples.",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        f"institutional_lifecycle imports forbidden "
                        f"module {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith(forbidden_prefixes), (
                    f"institutional_lifecycle imports from forbidden "
                    f"module {mod!r}"
                )


# ─────────────────────────────────────────────────────────────────────
# Class 2 — DefaultDomainPack provides empty extension-point defaults
# ─────────────────────────────────────────────────────────────────────


class TestDefaultDomainPackExtensionDefaults:
    """A pack without per-agent-type lifecycle specialisation must
    return empty dispatch tables — preserving pre-6T-C behaviour for
    every existing domain (single-agent flood, irrigation,
    vaccination, custom packs)."""

    def test_default_pack_returns_empty_handlers_dict(self):
        pack = DefaultDomainPack()
        handlers = pack.institutional_lifecycle_handlers()
        assert handlers == {}
        assert isinstance(handlers, dict)

    def test_default_pack_returns_empty_env_keys_set(self):
        pack = DefaultDomainPack()
        env_keys = pack.multi_agent_env_keys()
        assert env_keys == set()
        assert isinstance(env_keys, set)


# ─────────────────────────────────────────────────────────────────────
# Class 3 — SetupPack Protocol structural typing
# ─────────────────────────────────────────────────────────────────────


class TestSetupPackProtocolStructural:
    """The two new methods are declared on the SetupPack Protocol;
    structural-typing membership is exercised here so a future
    refactor can't silently drop them."""

    def test_default_pack_is_setup_pack(self):
        """DefaultDomainPack satisfies the SetupPack Protocol after
        the Phase 6T-C additions."""
        pack = DefaultDomainPack()
        assert isinstance(pack, SetupPack)

    def test_custom_pack_with_handlers_is_setup_pack(self):
        """A pack that overrides the new methods also satisfies the
        SetupPack Protocol."""
        pack = _DemoPackWithHandlers()
        assert isinstance(pack, SetupPack)
        assert "government" in pack.institutional_lifecycle_handlers()
        assert "subsidy_rate" in pack.multi_agent_env_keys()


# ─────────────────────────────────────────────────────────────────────
# Class 4 — End-to-end dispatch shape (no production wiring yet)
# ─────────────────────────────────────────────────────────────────────


class TestDispatchShape:
    """Demonstrates the intended Phase 6T-C dispatch shape: a runner
    looks up the handler via the pack and invokes the matching
    lifecycle phase. No production multi-agent runner consumes this
    yet (deferred to Phase 6T-F); this test pins the shape for the
    future wiring."""

    def test_dispatch_via_pack_routes_to_correct_handler(self):
        """A pack registering two handler instances (one per
        agent_type) — the dispatcher pattern looks up by agent_type
        + invokes the matching handler."""
        pack = _DemoPackWithHandlers()
        handlers = pack.institutional_lifecycle_handlers()

        # Shape: runner does handlers[agent.agent_type].post_decision(...)
        handlers["government"].post_decision(
            agent=object(), decision="large_increase_subsidy", year=1, env={}
        )
        handlers["insurance"].post_decision(
            agent=object(), decision="improve_crs", year=1, env={}
        )

        assert _GOV_DECISIONS == [("large_increase_subsidy", 1)]
        assert _INS_DECISIONS == [("improve_crs", 1)]

    def test_unknown_agent_type_lookup_raises_keyerror(self):
        """The pack returns a dict — looking up an unregistered
        agent_type raises KeyError. The runner is responsible for
        falling back to its bespoke dispatch when the handler is
        missing; the pack contract is just the lookup table."""
        pack = _DemoPackWithHandlers()
        with pytest.raises(KeyError):
            pack.institutional_lifecycle_handlers()["unknown_type"]

    def test_env_keys_whitelist_supports_union_across_packs(self):
        """multi_agent_env_keys is a set so multiple packs can
        report their owned keys and the runner can compute the
        union to validate cross-domain env state."""
        pack_a = _DemoPackWithHandlers()
        pack_b = _DemoPackEnvOnly()
        all_keys = pack_a.multi_agent_env_keys() | pack_b.multi_agent_env_keys()
        assert all_keys == {
            "subsidy_rate",
            "govt_budget_remaining",
            "premium_rate",
            "crs_discount",
        }
