"""Phase 6R-B-4 regression — AgentReflectionContext requires explicit agent_type.

Audit cluster E item #17 — the last cluster-E commit. Pre-fix
``broker/components/cognitive/reflection.py:63`` declared
``agent_type: str = "household"`` (dataclass default) and
``broker/components/cognitive/reflection.py:255`` extracted via
``getattr(agent, 'agent_type', 'household')`` — two flood-domain
default sites in generic reflection code. A malformed agent reaching
the reflection prompt builder silently became a "household" agent in
the LLM-facing identity line.

Phase 6R-B-4 makes ``agent_type`` a required dataclass field +
validates non-emptiness in ``__post_init__``. ``extract_agent_context``
passes ``None`` to the constructor when the agent lacks the attribute,
which surfaces the malformed-agent bug at the next assertion.

This module pins the new contract + the happy-path regression. Matches
the patterns from 6R-B-1 (PerceptionAwareProvider) and 6R-B-2
(get_social_spec).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from broker.components.cognitive.reflection import (
    AgentReflectionContext,
    ReflectionEngine,
)


# ---------------------------------------------------------------------------
# AgentReflectionContext.__post_init__ — raise on missing/empty
# ---------------------------------------------------------------------------

class TestRaiseOnMissingAgentType:
    """Constructing with missing/empty agent_type raises immediately."""

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError, match=r"empty/missing agent_type"):
            AgentReflectionContext(agent_id="X1", agent_type="")

    def test_raises_on_none(self):
        with pytest.raises(ValueError, match=r"empty/missing agent_type"):
            # type: ignore[arg-type]  — None is intentionally passed
            AgentReflectionContext(agent_id="X1", agent_type=None)

    def test_error_names_agent_id(self):
        """Error must surface the offending agent_id so a debugger can
        locate the upstream constructor that forgot to set
        agent_type."""
        with pytest.raises(ValueError, match=r"X_DEBUG_42"):
            AgentReflectionContext(agent_id="X_DEBUG_42", agent_type="")

    def test_error_cites_phase_6r_b_4(self):
        """Trace breadcrumb: future debuggers should locate this commit
        from the error message."""
        with pytest.raises(ValueError, match=r"6R-B-4"):
            AgentReflectionContext(agent_id="X1", agent_type="")

    def test_raises_on_whitespace_only(self):
        """Reviewer S1: a whitespace-only agent_type is the same
        semantic class as empty (no real value), so it must raise.
        Could otherwise sneak past via user-supplied YAML."""
        with pytest.raises(ValueError, match=r"empty/missing agent_type"):
            AgentReflectionContext(agent_id="X1", agent_type="   ")


# ---------------------------------------------------------------------------
# Happy-path regression — explicit agent_type works
# ---------------------------------------------------------------------------

class TestExplicitAgentTypePasses:
    """Real consumers passing explicit agent_type construct cleanly."""

    def test_household_explicit(self):
        ctx = AgentReflectionContext(agent_id="H_001", agent_type="household")
        assert ctx.agent_type == "household"

    def test_non_water_agent_type_explicit(self):
        """A commuter / dispatcher / vaccination-individual is just
        as valid as household — proves no agent_type whitelist."""
        ctx = AgentReflectionContext(agent_id="C1", agent_type="commuter")
        assert ctx.agent_type == "commuter"

    def test_government_explicit(self):
        ctx = AgentReflectionContext(
            agent_id="GOV_1", agent_type="government",
            mg_status=False,
        )
        assert ctx.agent_type == "government"


# ---------------------------------------------------------------------------
# extract_agent_context — propagates malformed-agent bug as raise
# ---------------------------------------------------------------------------

class TestExtractAgentContextPropagates:
    """``ReflectionEngine.extract_agent_context`` passes ``agent_type``
    via ``getattr(..., None)`` — a malformed agent triggers
    AgentReflectionContext's __post_init__ raise."""

    def test_extract_with_attr_succeeds(self):
        agent = MagicMock(spec=[])
        agent.id = "Y1"
        agent.agent_type = "vaccination_individual"
        ctx = ReflectionEngine.extract_agent_context(agent, year=2)
        assert ctx.agent_type == "vaccination_individual"

    def test_extract_without_attr_raises(self):
        """The companion test to
        ``tests/test_reflection_personalization.py::TestAgentReflectionContext::test_extract_missing_attrs_raises``
        — focused unit-level check that the propagation works."""
        agent = MagicMock(spec=[])
        agent.id = "Y2"
        with pytest.raises(ValueError, match=r"empty/missing agent_type"):
            ReflectionEngine.extract_agent_context(agent, year=2)

    def test_extract_empty_string_agent_type_raises(self):
        agent = MagicMock(spec=[])
        agent.id = "Y3"
        agent.agent_type = ""
        with pytest.raises(ValueError, match=r"empty/missing agent_type"):
            ReflectionEngine.extract_agent_context(agent, year=2)
