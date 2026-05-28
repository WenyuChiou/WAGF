"""Phase 6U-E-2 regression tests for the coordinator's
artifact-dispatch registry.

Verifies:
  - The pre-6U-E-2 hardcoded names (HouseholdIntention / PolicyArtifact
    / MarketArtifact) still route to their original buckets via the
    flood domain's registration.
  - A non-flood domain can register its own artifact_type → bucket
    rule and the coordinator dispatches accordingly without any
    knowledge of water-domain names.
  - Unknown artifact_type (no rule registered) falls back to the
    source-agent bucket, preserving the legacy default.

Note on test isolation: ``tests/test_artifacts.py`` reloads
``broker.interfaces.artifacts`` via ``importlib.reload``, swapping the
module identity mid-session. To stay correct under that pattern this
test file resolves the registry helpers dynamically per-test via
``import broker.interfaces.artifacts as ART`` rather than the
top-level ``from`` import (which would freeze a stale reference).
"""
from dataclasses import dataclass
from typing import List

import pytest

from broker.interfaces.artifacts import AgentArtifact
from broker.components.coordination.coordinator import GameMaster


def _art_module():
    """Dynamic resolver for the artifacts module — survives reloads."""
    import broker.interfaces.artifacts as ART
    return ART


@dataclass
class _TrafficAdvisoryArtifact(AgentArtifact):
    """Minimal non-flood artifact for genericity test."""
    severity: str = "MEDIUM"

    def artifact_type(self) -> str:
        return "TrafficAdvisory"

    def validate(self) -> List[str]:
        return []


@pytest.fixture
def isolated_registry():
    """Snapshot + restore the dispatch-rule registry around the test.
    Resolved dynamically each test to survive module reloads."""
    ART = _art_module()
    snapshot = dict(ART._DISPATCH_RULES)
    yield ART
    ART._DISPATCH_RULES.clear()
    ART._DISPATCH_RULES.update(snapshot)


def test_register_artifact_dispatch_rule_round_trip(isolated_registry):
    ART = isolated_registry
    ART.register_artifact_dispatch_rule(
        "TrafficAdvisory", bucket="advisories", mode="append"
    )
    rule = ART.get_artifact_dispatch_rule("TrafficAdvisory")
    assert rule is not None
    assert rule.bucket == "advisories"
    assert rule.mode == "append"


def test_register_rejects_unknown_mode():
    ART = _art_module()
    with pytest.raises(ValueError, match=r"mode must be 'append' or 'single'"):
        ART.register_artifact_dispatch_rule("X", bucket="x", mode="upsert")


def test_register_idempotent_same_rule(isolated_registry):
    """Idempotent re-registration (same bucket + mode) is a no-op —
    supports the import-time registration pattern where the same domain
    module gets imported via two different code paths."""
    ART = isolated_registry
    ART.register_artifact_dispatch_rule("Foo", bucket="foos", mode="append")
    # Second call with identical args MUST NOT raise
    ART.register_artifact_dispatch_rule("Foo", bucket="foos", mode="append")
    rule = ART.get_artifact_dispatch_rule("Foo")
    assert rule.bucket == "foos"
    assert rule.mode == "append"


def test_register_rejects_conflicting_rule(isolated_registry):
    """Phase 6U-E-2 silent-failure guard: conflicting re-registration
    (different bucket or mode) raises ValueError unless overwrite=True.
    Pre-guard a second domain could silently rewire the coordinator
    dispatch + drop the original domain's cross-validation."""
    ART = isolated_registry
    ART.register_artifact_dispatch_rule("Foo", bucket="foos", mode="append")
    with pytest.raises(ValueError, match=r"Conflicting ArtifactDispatchRule"):
        ART.register_artifact_dispatch_rule("Foo", bucket="other_bucket", mode="append")
    with pytest.raises(ValueError, match=r"Conflicting ArtifactDispatchRule"):
        ART.register_artifact_dispatch_rule("Foo", bucket="foos", mode="single")


def test_register_overwrite_replaces_explicitly(isolated_registry):
    """``overwrite=True`` is the escape-hatch for intentional rebinding."""
    ART = isolated_registry
    ART.register_artifact_dispatch_rule("Foo", bucket="foos", mode="append")
    ART.register_artifact_dispatch_rule(
        "Foo", bucket="new_bucket", mode="single", overwrite=True
    )
    rule = ART.get_artifact_dispatch_rule("Foo")
    assert rule.bucket == "new_bucket"
    assert rule.mode == "single"


def test_unknown_artifact_type_returns_none():
    ART = _art_module()
    assert ART.get_artifact_dispatch_rule("definitely_not_registered_anywhere") is None


def test_coordinator_dispatches_via_registry_append(isolated_registry):
    """Phase 6U-E-2: a non-flood artifact_type can be registered and
    the coordinator routes it without any hardcoded knowledge."""
    ART = isolated_registry
    ART.register_artifact_dispatch_rule(
        "TrafficAdvisory", bucket="advisories", mode="append"
    )
    gm = GameMaster()
    art = _TrafficAdvisoryArtifact(agent_id="signal_42", year=1, rationale="rush hour")
    env = ART.ArtifactEnvelope(artifact=art, source_agent="signal_42")
    gm.submit_artifact(env)
    gm.submit_artifact(env)  # second append should accumulate

    advisories = gm._round_artifacts.get("advisories", [])
    assert len(advisories) == 2
    assert all(a is art for a in advisories)


def test_coordinator_dispatches_via_registry_single(isolated_registry):
    ART = isolated_registry
    ART.register_artifact_dispatch_rule(
        "TrafficPolicy", bucket="policy", mode="single"
    )

    @dataclass
    class _TrafficPolicyArtifact(AgentArtifact):
        zone: str = "core"

        def artifact_type(self) -> str:
            return "TrafficPolicy"

        def validate(self) -> List[str]:
            return []

    gm = GameMaster()
    a1 = _TrafficPolicyArtifact(agent_id="dispatcher", year=1, rationale="r1", zone="core")
    a2 = _TrafficPolicyArtifact(agent_id="dispatcher", year=1, rationale="r2", zone="ring")
    gm.submit_artifact(ART.ArtifactEnvelope(artifact=a1, source_agent="dispatcher"))
    gm.submit_artifact(ART.ArtifactEnvelope(artifact=a2, source_agent="dispatcher"))

    # single-mode: last write wins
    assert gm._round_artifacts["policy"] is a2


def test_coordinator_no_rule_falls_back_to_source_bucket(isolated_registry):
    """Artifact with no registered rule lands under source_agent
    key — preserves the pre-6U-E-2 default fallback."""
    ART = isolated_registry

    @dataclass
    class _UnknownArtifact(AgentArtifact):
        def artifact_type(self) -> str:
            return "UnknownArtifactType"

        def validate(self) -> List[str]:
            return []

    gm = GameMaster()
    art = _UnknownArtifact(agent_id="x", year=1, rationale="r")
    env = ART.ArtifactEnvelope(artifact=art, source_agent="src_007")
    gm.submit_artifact(env)
    assert gm._round_artifacts["src_007"] is env


def test_flood_legacy_rules_still_registered():
    """Importing the flood protocols module registers the 3 legacy
    rules. We re-import to guarantee the rules exist in the currently-
    active ``broker.interfaces.artifacts`` module identity (survives
    test_artifacts.py's importlib.reload pattern)."""
    import importlib

    import examples.multi_agent.flood.protocols.artifacts as flood_artifacts
    importlib.reload(flood_artifacts)

    ART = _art_module()
    expected = ART.ArtifactDispatchRule

    rule_household = ART.get_artifact_dispatch_rule("HouseholdIntention")
    rule_policy = ART.get_artifact_dispatch_rule("PolicyArtifact")
    rule_market = ART.get_artifact_dispatch_rule("MarketArtifact")

    assert rule_household == expected(
        artifact_type="HouseholdIntention", bucket="intentions", mode="append"
    )
    assert rule_policy == expected(
        artifact_type="PolicyArtifact", bucket="policy", mode="single"
    )
    assert rule_market == expected(
        artifact_type="MarketArtifact", bucket="market", mode="single"
    )
