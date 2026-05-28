"""Phase 6U-G (2026-05-28): regression test that the broker-facing
``_FallbackArtifact`` + water-domain placeholder classes
(``PolicyArtifact``, ``MarketArtifact``, ``HouseholdIntention``) are
REMOVED from ``broker/interfaces/artifacts.py``.

Pre-6U-G this file tested the OPPOSITE — that the placeholders were
present. The placeholders existed so generic broker code could
reference water-domain artifact-type names without importing
``examples/``. Phase 6U-E-2 made the coordinator dispatch
registry-driven (no class-identity dispatch); Phase 6U-G then
removed the placeholders themselves. Callers needing the real
classes import them from
``examples.multi_agent.flood.protocols.artifacts`` (the canonical
home).
"""
import inspect

from broker.interfaces import artifacts as artifacts_module


def test_artifacts_module_has_no_example_reexport_import():
    """The broker interfaces module MUST NOT import from
    ``examples/`` — that would invert the layering rule."""
    source = inspect.getsource(artifacts_module)
    assert "from examples.multi_agent.flood.protocols.artifacts" not in source


def test_water_domain_placeholder_classes_are_gone():
    """Phase 6U-G: the 3 broker-side placeholder classes were the
    last identifiable water-domain leak in broker/interfaces/.
    Removed in commit ____; this test ensures they don't quietly
    return in a future revert."""
    assert not hasattr(artifacts_module, "PolicyArtifact"), (
        "PolicyArtifact placeholder must stay removed — import the real "
        "class from examples.multi_agent.flood.protocols.artifacts"
    )
    assert not hasattr(artifacts_module, "MarketArtifact"), (
        "MarketArtifact placeholder must stay removed — import the real "
        "class from examples.multi_agent.flood.protocols.artifacts"
    )
    assert not hasattr(artifacts_module, "HouseholdIntention"), (
        "HouseholdIntention placeholder must stay removed — import the real "
        "class from examples.multi_agent.flood.protocols.artifacts"
    )
    assert not hasattr(artifacts_module, "_FallbackArtifact"), (
        "_FallbackArtifact base class was the placeholder substrate; "
        "must stay removed alongside its subclasses."
    )


def test_water_domain_names_absent_from_all():
    """The 3 water-domain names must not appear in the broker
    artifacts module's __all__ either."""
    exported = set(artifacts_module.__all__)
    for water_name in ("PolicyArtifact", "MarketArtifact", "HouseholdIntention"):
        assert water_name not in exported, (
            f"{water_name} re-introduced into broker/interfaces/artifacts.py:__all__"
        )


def test_real_classes_still_available_from_examples():
    """The real domain classes are still importable from
    ``examples.multi_agent.flood.protocols.artifacts`` — only the
    broker-side fallback shim is gone. Each class is exercised so a
    silent regression that breaks its constructor / artifact_type /
    validate semantics surfaces here, not only at import."""
    from examples.multi_agent.flood.protocols.artifacts import (
        PolicyArtifact,
        MarketArtifact,
        HouseholdIntention,
    )

    p = PolicyArtifact(
        agent_id="GOV",
        year=1,
        rationale="test",
        subsidy_rate=0.1,
    )
    assert p.artifact_type() == "PolicyArtifact"
    assert p.validate() == []

    m = MarketArtifact(
        agent_id="INS",
        year=1,
        rationale="test",
        premium_rate=0.1,
    )
    assert m.artifact_type() == "MarketArtifact"
    assert m.validate() == []

    h = HouseholdIntention(
        agent_id="H_001",
        year=1,
        rationale="test",
        chosen_skill="buy_insurance",
        tp_level="M",
        cp_level="M",
        confidence=0.8,
    )
    assert h.artifact_type() == "HouseholdIntention"
    assert h.validate() == []
