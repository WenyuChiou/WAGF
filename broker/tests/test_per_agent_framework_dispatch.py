"""
Phase 6T-B per-agent-type psychological framework dispatch tests.

Closes engineering-audit finding Y6: ``GovernancePack.psychological_framework``
returned a single string for the entire pack — the last agent_type
registered overwrote the rest. In a multi-agent flood domain, a
household decision (PMT) and a government decision (utility) would
both be validated under PMT, which is institutionally inappropriate.

This test suite pins the Phase 6T-B contract:

1. :class:`GovernancePack.framework_for_agent_type` (new method) is
   the per-agent-type resolver.
2. :class:`DefaultDomainPack` delegates to
   :meth:`psychological_framework` for backward compatibility.
3. ``FloodGovernanceMixin`` overrides to route household_owner /
   household_renter → ``"pmt"``, nj_government / government →
   ``"utility"``, fema_nfip / insurance → ``"financial"``.
4. ``build_domain_validators`` accepts the optional ``agent_type``
   parameter and routes through the new method.
5. ``validate_all`` plumbs its existing ``agent_type`` parameter down
   to the dispatcher.
6. Paper-1b byte-identity protection: ``agent_type=None`` returns the
   legacy domain-wide framework label (no behavior change for
   callers that don't plumb agent_type).

Plan: ``~/.claude/plans/swirling-knitting-lighthouse.md`` 6T-B.
"""
from __future__ import annotations

from typing import Optional

import pytest

# Importing the example package registers FloodDomainPack +
# water-framework metadata at import time.
import examples.governed_flood  # noqa: F401

from broker.components.governance.domain_validator_dispatch import (
    build_domain_validators,
)
from broker.domains.default import DefaultDomainPack
from broker.domains.registry import DomainPackRegistry
from broker.validators.governance.thinking_validator import (
    FRAMEWORK_ESCAPE_HATCH,
    ThinkingValidator,
)


# ─────────────────────────────────────────────────────────────────────
# Class 1 — Protocol default behavior
# ─────────────────────────────────────────────────────────────────────


class TestDefaultDelegatesToPsychologicalFramework:
    """A pack that doesn't override ``framework_for_agent_type``
    must return the same value as ``psychological_framework`` for
    every agent_type — preserving pre-6T-B behaviour."""

    class _LegacyPack(DefaultDomainPack):
        name = "legacypack"

        def psychological_framework(self) -> str:
            return "cognitive_appraisal"

    def test_legacy_pack_returns_same_value_for_any_agent_type(self):
        pack = self._LegacyPack()
        assert pack.framework_for_agent_type("anything") == "cognitive_appraisal"
        assert pack.framework_for_agent_type("other") == "cognitive_appraisal"
        assert pack.framework_for_agent_type("household_owner") == "cognitive_appraisal"

    def test_legacy_pack_returns_same_value_for_none_agent_type(self):
        pack = self._LegacyPack()
        assert pack.framework_for_agent_type(None) == "cognitive_appraisal"

    def test_default_pack_returns_escape_hatch(self):
        """No psychological_framework override → escape hatch
        sentinel for every agent_type."""
        pack = DefaultDomainPack()
        assert pack.framework_for_agent_type(None) == FRAMEWORK_ESCAPE_HATCH
        assert pack.framework_for_agent_type("any_type") == FRAMEWORK_ESCAPE_HATCH


# ─────────────────────────────────────────────────────────────────────
# Class 2 — FloodGovernanceMixin per-agent-type table
# ─────────────────────────────────────────────────────────────────────


class TestFloodPackPerAgentTypeFramework:
    """FloodGovernanceMixin must route the 6 multi-agent agent_types
    to their respective frameworks (PMT / utility / financial)."""

    @pytest.fixture
    def pack(self):
        return DomainPackRegistry.get_governance_pack("flood")

    @pytest.mark.parametrize(
        "agent_type, expected_framework",
        [
            ("household_owner", "pmt"),
            ("household_renter", "pmt"),
            ("nj_government", "utility"),
            ("government", "utility"),
            ("fema_nfip", "financial"),
            ("insurance", "financial"),
            # Phase 6T-F prep (2026-05-27): social_media_influencer
            # reasons under narrative_diffusion. Agent_type entry is
            # in the FloodGovernanceMixin _AGENT_TYPE_FRAMEWORK dict
            # even though the agent_type itself isn't in MA-flood YAML
            # yet — that's interface-only forward contract.
            ("social_media_influencer", "narrative_diffusion"),
        ],
    )
    def test_known_agent_types_route_correctly(
        self, pack, agent_type, expected_framework
    ):
        assert pack.framework_for_agent_type(agent_type) == expected_framework

    def test_agent_type_lookup_is_case_insensitive(self, pack):
        """Phase 6T-B normalises agent_type via ``.strip().lower()`` to
        survive caller-side capitalisation variance."""
        assert pack.framework_for_agent_type("HOUSEHOLD_OWNER") == "pmt"
        assert pack.framework_for_agent_type("  nj_government  ") == "utility"
        assert pack.framework_for_agent_type("Insurance") == "financial"

    def test_unknown_agent_type_falls_back_to_pmt(self, pack):
        """An agent_type not in the per-type table must fall back to
        :meth:`psychological_framework` (``"pmt"``) — preserves
        single-agent flood byte-identity for callers that pass
        unrelated agent_type labels."""
        assert pack.framework_for_agent_type("traffic_commuter") == "pmt"
        assert pack.framework_for_agent_type("unknown") == "pmt"

    def test_none_agent_type_falls_back_to_psychological_framework(self, pack):
        """``agent_type=None`` is the SA flood path — must return
        the legacy domain-wide framework."""
        assert pack.framework_for_agent_type(None) == pack.psychological_framework()
        assert pack.framework_for_agent_type(None) == "pmt"


# ─────────────────────────────────────────────────────────────────────
# Class 3 — build_domain_validators routes framework via agent_type
# ─────────────────────────────────────────────────────────────────────


class TestDispatcherRoutesByAgentType:
    """``build_domain_validators(domain, agent_type=...)`` must select
    the per-agent-type framework when agent_type is supplied."""

    def _get_thinking_validator(self, validators):
        """Extract the ThinkingValidator from the validator list."""
        for v in validators:
            if isinstance(v, ThinkingValidator):
                return v
        pytest.fail("No ThinkingValidator in dispatcher output")

    def test_household_owner_dispatch_routes_to_pmt(self):
        validators = build_domain_validators("flood", agent_type="household_owner")
        tv = self._get_thinking_validator(validators)
        assert tv.framework == "pmt"

    def test_nj_government_dispatch_routes_to_utility(self):
        validators = build_domain_validators("flood", agent_type="nj_government")
        tv = self._get_thinking_validator(validators)
        assert tv.framework == "utility"

    def test_fema_nfip_dispatch_routes_to_financial(self):
        validators = build_domain_validators("flood", agent_type="fema_nfip")
        tv = self._get_thinking_validator(validators)
        assert tv.framework == "financial"

    def test_no_agent_type_preserves_legacy_pmt(self):
        """Paper-1b byte-identity guard: omitting agent_type must
        resolve to the legacy domain-wide framework (PMT for flood),
        matching pre-6T-B behaviour."""
        validators = build_domain_validators("flood")
        tv = self._get_thinking_validator(validators)
        assert tv.framework == "pmt"

    def test_unknown_agent_type_falls_back_to_legacy(self):
        """An agent_type the flood pack doesn't recognise must
        resolve to the same value as psychological_framework() so
        callers can pass unrelated agent_types without surprise."""
        validators = build_domain_validators("flood", agent_type="traffic_commuter")
        tv = self._get_thinking_validator(validators)
        assert tv.framework == "pmt"


# ─────────────────────────────────────────────────────────────────────
# Class 4 — validate_all plumbs agent_type to the dispatcher
# ─────────────────────────────────────────────────────────────────────


class TestValidateAllPlumbsAgentType:
    """``validate_all`` accepted ``agent_type`` pre-6T-B but dropped
    it before the dispatcher call. Phase 6T-B plumbs it through —
    asserted here by monkey-patching the dispatcher to capture its
    received args."""

    def test_validate_all_passes_agent_type_to_dispatcher(self, monkeypatch):
        from broker.validators import governance as gov_module
        from broker.config.agent_types.registry import AgentTypeRegistry

        captured = {}

        def _fake_dispatcher(domain, agent_type=None):
            captured["domain"] = domain
            captured["agent_type"] = agent_type
            return []

        monkeypatch.setattr(
            "broker.components.governance.domain_validator_dispatch.build_domain_validators",
            _fake_dispatcher,
        )

        # AgentTypeRegistry required when agent_type is supplied
        # (downstream TypeValidator validates skill eligibility).
        gov_module.validate_all(
            skill_name="elevate_house",
            rules=[],
            context={},
            agent_type="nj_government",
            registry=AgentTypeRegistry(),
            domain="flood",
        )

        assert captured["domain"] == "flood"
        assert captured["agent_type"] == "nj_government"

    def test_validate_all_passes_none_when_agent_type_omitted(self, monkeypatch):
        """SA flood path: validate_all called without agent_type must
        forward agent_type=None to the dispatcher → legacy framework."""
        from broker.validators import governance as gov_module

        captured = {}

        def _fake_dispatcher(domain, agent_type=None):
            captured["domain"] = domain
            captured["agent_type"] = agent_type
            return []

        monkeypatch.setattr(
            "broker.components.governance.domain_validator_dispatch.build_domain_validators",
            _fake_dispatcher,
        )

        gov_module.validate_all(
            skill_name="elevate_house",
            rules=[],
            context={},
            domain="flood",
        )

        assert captured["domain"] == "flood"
        assert captured["agent_type"] is None
