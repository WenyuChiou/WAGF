"""Phase 6R-B-1 regression — PerceptionAwareProvider requires explicit agent_type.

Audit cluster E item #15. Pre-fix, ``broker.components.context.providers.py``
lines 506/508 silently defaulted to the literal string ``"household"`` when
an agent's ``agent_type`` attribute was missing or empty. That fallback
masked the upstream bug (agent constructor forgot to set agent_type) AND
misrouted non-water domain agents through the flood-domain-named filter
slot.

Phase 6R-B-1 removes the silent fallback: a missing/empty agent_type now
raises ``ValueError`` at perception-filter dispatch time. This module pins
both the raise behavior AND the happy-path (existing real agents continue
to work) so future refactors can't silently re-introduce the household
default.
"""
from __future__ import annotations

import pytest

from broker.components.context.providers import PerceptionAwareProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _ObjAgentWithType:
    """Object-shaped agent with explicit ``agent_type`` attribute —
    the canonical valid form."""

    def __init__(self, agent_type: str):
        self.agent_type = agent_type


class _ObjAgentWithoutType:
    """Object-shaped agent that forgot to set agent_type — the
    malformed form the new guard catches."""


# ---------------------------------------------------------------------------
# Raise-on-missing tests
# ---------------------------------------------------------------------------

class TestRaiseOnMissingAgentType:
    """Both dict-shaped and object-shaped agents must raise when
    agent_type is missing/empty. Mirrors providers.py:489-518 contract."""

    def test_raises_for_dict_agent_missing_agent_type(self):
        provider = PerceptionAwareProvider()
        # Non-empty agent dict missing only ``agent_type``. An empty
        # dict ``{}`` would short-circuit via the ``if not agent:
        # return`` guard at providers.py:501 (pre-existing falsy-skip
        # behaviour); the agent_type check only fires for truthy
        # agents.
        agents = {"agent_1": {"name": "agent_1", "id": 1}}
        with pytest.raises(ValueError, match=r"no `agent_type`"):
            provider.provide("agent_1", agents, {})

    def test_raises_for_object_agent_missing_agent_type(self):
        provider = PerceptionAwareProvider()
        agents = {"agent_1": _ObjAgentWithoutType()}
        with pytest.raises(ValueError, match=r"no `agent_type`"):
            provider.provide("agent_1", agents, {})

    def test_raises_for_dict_agent_empty_agent_type(self):
        # Empty string is treated the same as missing — falsy.
        provider = PerceptionAwareProvider()
        agents = {"agent_1": {"agent_type": ""}}
        with pytest.raises(ValueError, match=r"no `agent_type`"):
            provider.provide("agent_1", agents, {})

    def test_raises_for_object_agent_none_agent_type(self):
        provider = PerceptionAwareProvider()
        obj = _ObjAgentWithType("placeholder")
        obj.agent_type = None  # explicitly set to None
        agents = {"agent_1": obj}
        with pytest.raises(ValueError, match=r"no `agent_type`"):
            provider.provide("agent_1", agents, {})

    def test_error_message_names_the_agent_id(self):
        """Error must surface the offending agent_id so the upstream
        bug (which constructor forgot to set agent_type) is locatable."""
        provider = PerceptionAwareProvider()
        agents = {"my_test_agent_42": {"name": "x"}}
        with pytest.raises(ValueError, match="my_test_agent_42"):
            provider.provide("my_test_agent_42", agents, {})

    def test_error_message_mentions_phase_6r_b_1(self):
        """Trace breadcrumb: the error message names the closing
        sub-phase so a future debugger can find the rationale."""
        provider = PerceptionAwareProvider()
        agents = {"x": {"name": "x"}}
        with pytest.raises(ValueError, match=r"6R-B-1"):
            provider.provide("x", agents, {})


# ---------------------------------------------------------------------------
# Happy-path regression
# ---------------------------------------------------------------------------

class TestExplicitAgentTypePasses:
    """Real agents with explicit agent_type continue to route through
    the filter registry without error. Ensures the guard isn't too
    strict."""

    def test_dict_agent_with_agent_type_dispatches_cleanly(self):
        provider = PerceptionAwareProvider()
        agents = {"agent_1": {"agent_type": "household"}}
        context = {"x": 1.0}
        # Should not raise; filter may transform context but never crash.
        provider.provide("agent_1", agents, context)
        assert "_perception" in context  # provider adds the audit-trail key
        assert context["_perception"]["agent_type"] == "household"

    def test_object_agent_with_agent_type_dispatches_cleanly(self):
        provider = PerceptionAwareProvider()
        agents = {"agent_1": _ObjAgentWithType("government")}
        context = {"x": 1.0}
        provider.provide("agent_1", agents, context)
        assert context["_perception"]["agent_type"] == "government"

    def test_missing_agent_silently_returns(self):
        """Pre-existing behavior preserved: if the agent isn't in the
        ``agents`` dict, provider returns silently (used for partial
        runs where some agents are skipped)."""
        provider = PerceptionAwareProvider()
        provider.provide("nonexistent", {}, {})  # no raise


# ---------------------------------------------------------------------------
# Non-water domain regression — the actual leak this fix closes
# ---------------------------------------------------------------------------

class TestNonWaterAgentTypeRoutes:
    """Phase 6R-B-1 motivating case: a non-water domain agent
    (``agent_type="commuter"``) must route through the filter registry
    based on its actual type, never silently aliased to 'household'.

    This is what the 6Q-F-2-c traffic E2E gate proves at runtime; this
    test pins the same property at the unit-level."""

    def test_commuter_agent_type_routes_as_commuter(self):
        provider = PerceptionAwareProvider()
        agents = {"c1": _ObjAgentWithType("commuter")}
        context = {"congestion_level": 0.7}
        provider.provide("c1", agents, context)
        assert context["_perception"]["agent_type"] == "commuter"
        # Specifically NOT aliased to household.
        assert context["_perception"]["agent_type"] != "household"
