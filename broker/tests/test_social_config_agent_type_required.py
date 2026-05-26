"""Phase 6R-B-2 regression — get_social_spec requires explicit agent_type.

Audit cluster E item #14. Pre-fix, ``broker.components.social.config.py``
lines 121, 125, and 130 silently fell back to the literal string
``"household"`` for any agent missing the ``agent_type`` attribute. That
fallback misrouted non-water-domain malformed agents into the
``household_nmg_owner`` spatial-graph lookup — a flood-shaped social
topology with no semantic meaning for traffic / vaccination / generic
agents.

This module pins the new raise-on-None contract + the happy-path
regressions (real agents with explicit agent_type continue to route).
Companion to ``test_social_graph_config.py::test_missing_agent_type_raises``
in the existing tests file (which was updated from the old silent-fallback
expectation).
"""
from __future__ import annotations

import pytest

from broker.components.social.config import get_social_spec, DEFAULT_SOCIAL_SPEC


class _ObjAgent:
    """Object-shaped agent with arbitrary attributes."""

    def __init__(self, **attrs):
        for key, value in attrs.items():
            setattr(self, key, value)


# ---------------------------------------------------------------------------
# Raise-on-missing tests
# ---------------------------------------------------------------------------

class TestRaiseOnMissingAgentType:
    """Both dict and object agents must raise when agent_type is
    missing or empty. Matches the Phase 6R-B-1 pattern in
    ``PerceptionAwareProvider``."""

    def test_raises_for_dict_agent_no_key(self):
        with pytest.raises(ValueError, match=r"no `agent_type`"):
            get_social_spec({"name": "x"})

    def test_raises_for_dict_agent_empty_string(self):
        with pytest.raises(ValueError, match=r"no `agent_type`"):
            get_social_spec({"agent_type": ""})

    def test_raises_for_dict_agent_none_value(self):
        with pytest.raises(ValueError, match=r"no `agent_type`"):
            get_social_spec({"agent_type": None})

    def test_raises_for_object_no_attr(self):
        with pytest.raises(ValueError, match=r"no `agent_type`"):
            get_social_spec(_ObjAgent(name="x"))

    def test_raises_for_object_empty_string(self):
        with pytest.raises(ValueError, match=r"no `agent_type`"):
            get_social_spec(_ObjAgent(agent_type=""))

    def test_raises_for_object_none_value(self):
        with pytest.raises(ValueError, match=r"no `agent_type`"):
            get_social_spec(_ObjAgent(agent_type=None))

    def test_error_message_cites_phase_6r_b_2(self):
        """Trace breadcrumb: future debuggers should locate this commit
        from the error message alone."""
        with pytest.raises(ValueError, match=r"6R-B-2"):
            get_social_spec({"name": "x"})


# ---------------------------------------------------------------------------
# Happy-path regression — real agents continue to dispatch
# ---------------------------------------------------------------------------

class TestExplicitAgentTypePasses:
    """Existing real-domain agents (always set agent_type) must still
    route. Tests both household and institutional paths."""

    def test_household_dict_agent_routes(self):
        spec = get_social_spec({
            "agent_type": "household",
            "is_mg": False,
            "tenure": "owner",
        })
        assert spec is not None
        # Spec routes via the household composition path —
        # graph_type "spatial" is the canonical household social-graph
        # shape (the AGENT_SOCIAL_SPECS["household_nmg_owner"] entry).
        # A future regression that re-introduces the silent fallback
        # would still pass this assertion, but the non-water tests
        # below would surface it.
        assert spec.graph_type == "spatial"

    def test_household_object_agent_routes(self):
        agent = _ObjAgent(agent_type="household", is_mg=True, tenure="renter")
        spec = get_social_spec(agent)
        assert spec is not None

    def test_government_routes_via_agent_type_registry(self):
        """Institutional agent types route via AGENT_SOCIAL_SPECS
        registry directly, not through household composition."""
        spec = get_social_spec({"agent_type": "government"})
        assert spec is not None


# ---------------------------------------------------------------------------
# Non-water agent regression — the actual leak this fix closes
# ---------------------------------------------------------------------------

class TestNonWaterAgentTypeRoutes:
    """A non-water agent_type with no matching AGENT_SOCIAL_SPECS
    entry must fall through to DEFAULT_SOCIAL_SPEC — NOT silently
    aliased to the household composition path."""

    def test_unknown_agent_type_returns_default_spec(self):
        # 'commuter' is not in AGENT_SOCIAL_SPECS by default; the
        # function should return DEFAULT_SOCIAL_SPEC (line 152) rather
        # than trying to compose a household_X_Y key.
        spec = get_social_spec({"agent_type": "commuter"})
        assert spec is DEFAULT_SOCIAL_SPEC

    def test_traffic_dispatcher_returns_default_spec(self):
        spec = get_social_spec({"agent_type": "dispatcher"})
        assert spec is DEFAULT_SOCIAL_SPEC

    def test_unknown_agent_type_does_not_compose_household_key(self):
        """Critical regression: pre-Phase-6R-B-2 a malformed agent
        could trigger composition of ``household_nmg_owner`` even
        when its agent_type was 'commuter'. Now: if agent_type is
        not in the household synonyms, the household path is
        skipped entirely."""
        # Even if is_mg + tenure are set, an unknown agent_type
        # must NOT compose them into a household lookup.
        spec = get_social_spec({
            "agent_type": "commuter",
            "is_mg": True,
            "tenure": "renter",
        })
        # The commuter agent_type isn't in AGENT_SOCIAL_SPECS, and
        # it's not in the household synonym set, so it should fall
        # through to DEFAULT_SOCIAL_SPEC — proving the household
        # composition path is correctly gated.
        assert spec is DEFAULT_SOCIAL_SPEC
