"""Tests for structured artifacts (Task-058A).

Tests the generic AgentArtifact ABC in broker/interfaces/artifacts.py
and the flood-domain subclasses in examples/multi_agent/flood/protocols/artifacts.py.
"""
from broker.interfaces.artifacts import AgentArtifact, ArtifactEnvelope
from broker.interfaces.coordination import MessageType
from examples.multi_agent.flood.protocols.artifacts import (
    PolicyArtifact,
    MarketArtifact,
    HouseholdIntention,
)


# ---------------------------------------------------------------------------
# AgentArtifact ABC contract
# ---------------------------------------------------------------------------

def test_agent_artifact_is_abstract():
    """AgentArtifact cannot be instantiated directly."""
    import pytest
    with pytest.raises(TypeError):
        AgentArtifact(agent_id="X", year=1, rationale="test")  # type: ignore[abstract]


def test_subclass_has_artifact_type():
    p = PolicyArtifact(agent_id="GOV", year=1, rationale="r",
                       subsidy_rate=0.5, mg_priority=True,
                       budget_remaining=1000.0, target_adoption_rate=0.6)
    assert p.artifact_type() == "PolicyArtifact"
    assert isinstance(p, AgentArtifact)


# ---------------------------------------------------------------------------
# PolicyArtifact validation
# ---------------------------------------------------------------------------

def test_policy_artifact_validation():
    artifact = PolicyArtifact(
        agent_id="GOV_001", year=1,
        subsidy_rate=0.5, mg_priority=True,
        budget_remaining=1000.0, target_adoption_rate=0.6,
        rationale="Increase subsidy to improve adoption.",
    )
    assert artifact.validate() == []


def test_policy_artifact_validation_errors():
    invalid = PolicyArtifact(
        agent_id="GOV_001", year=1,
        subsidy_rate=1.5, mg_priority=True,
        budget_remaining=-5.0, target_adoption_rate=2.0,
        rationale="Bad values.",
    )
    errors = invalid.validate()
    assert any("subsidy_rate out of range" in e for e in errors)
    assert any("negative budget" in e for e in errors)
    assert any("target_adoption_rate out of range" in e for e in errors)


# ---------------------------------------------------------------------------
# MarketArtifact validation
# ---------------------------------------------------------------------------

def test_market_artifact_validation():
    artifact = MarketArtifact(
        agent_id="INS_001", year=1,
        premium_rate=0.2, payout_ratio=0.7,
        solvency_ratio=1.1, loss_ratio=0.4,
        risk_assessment="Stable.",
        rationale="Maintain current rates.",
    )
    assert artifact.validate() == []


def test_market_artifact_validation_errors():
    invalid = MarketArtifact(
        agent_id="INS_001", year=1,
        premium_rate=-0.1, payout_ratio=0.7,
        solvency_ratio=-0.5, loss_ratio=0.4,
        risk_assessment="Bad values.",
        rationale="Bad values.",
    )
    errors = invalid.validate()
    assert any("premium_rate out of range" in e for e in errors)
    assert any("negative solvency" in e for e in errors)


# ---------------------------------------------------------------------------
# HouseholdIntention validation
# ---------------------------------------------------------------------------

def test_household_intention_validation():
    artifact = HouseholdIntention(
        agent_id="H_001", year=1,
        chosen_skill="buy_insurance",
        tp_level="M", cp_level="H",
        confidence=0.8,
        rationale="Feels manageable.",
    )
    assert artifact.validate() == []


def test_household_intention_validation_errors():
    invalid = HouseholdIntention(
        agent_id="H_001", year=1,
        chosen_skill="do_nothing",
        tp_level="INVALID", cp_level="LOW",
        confidence=1.5,
        rationale="Bad values.",
    )
    errors = invalid.validate()
    assert any("invalid tp_level" in e for e in errors)
    assert any("invalid cp_level" in e for e in errors)
    assert any("confidence out of range" in e for e in errors)


# ---------------------------------------------------------------------------
# Payload round-trip (to_message_payload)
# ---------------------------------------------------------------------------

def test_policy_artifact_payload_round_trip():
    artifact = PolicyArtifact(
        agent_id="GOV_002", year=2,
        subsidy_rate=0.4, mg_priority=False,
        budget_remaining=500.0, target_adoption_rate=0.3,
        rationale="Maintain baseline.",
    )
    payload = artifact.to_message_payload()
    assert payload["artifact_type"] == "PolicyArtifact"
    assert payload["agent_id"] == "GOV_002"
    assert payload["year"] == 2
    assert payload["subsidy_rate"] == 0.4
    assert payload["mg_priority"] is False
    assert payload["budget_remaining"] == 500.0
    assert payload["target_adoption_rate"] == 0.3
    assert payload["rationale"] == "Maintain baseline."


def test_market_artifact_payload_round_trip():
    artifact = MarketArtifact(
        agent_id="INS_002", year=3,
        premium_rate=0.12, payout_ratio=0.5,
        solvency_ratio=0.9, loss_ratio=0.3,
        risk_assessment="Improving.",
        rationale="Improving conditions.",
    )
    payload = artifact.to_message_payload()
    assert payload["artifact_type"] == "MarketArtifact"
    assert payload["agent_id"] == "INS_002"
    assert payload["year"] == 3
    assert payload["premium_rate"] == 0.12
    assert payload["payout_ratio"] == 0.5
    assert payload["solvency_ratio"] == 0.9
    assert payload["loss_ratio"] == 0.3
    assert payload["risk_assessment"] == "Improving."


def test_household_intention_payload_round_trip():
    artifact = HouseholdIntention(
        agent_id="H_002", year=4,
        chosen_skill="relocate",
        tp_level="H", cp_level="M",
        confidence=0.65,
        rationale="Too risky to stay.",
    )
    payload = artifact.to_message_payload()
    assert payload["artifact_type"] == "HouseholdIntention"
    assert payload["agent_id"] == "H_002"
    assert payload["year"] == 4
    assert payload["chosen_skill"] == "relocate"
    assert payload["tp_level"] == "H"
    assert payload["cp_level"] == "M"
    assert payload["confidence"] == 0.65
    assert payload["rationale"] == "Too risky to stay."


# ---------------------------------------------------------------------------
# ArtifactEnvelope -> AgentMessage
# ---------------------------------------------------------------------------

def test_artifact_envelope_to_agent_message():
    artifact = PolicyArtifact(
        agent_id="GOV_003", year=5,
        subsidy_rate=0.25, mg_priority=True,
        budget_remaining=250.0, target_adoption_rate=0.2,
        rationale="Reduce subsidy.",
    )
    envelope = ArtifactEnvelope(
        artifact=artifact,
        source_agent="GOV_003",
        target_scope="global",
        timestamp=10,
    )
    msg = envelope.to_agent_message()
    assert msg.sender == "GOV_003"
    assert msg.message_type == MessageType.POLICY_ANNOUNCEMENT
    assert "[PolicyArtifact]" in msg.content
    assert msg.data["artifact_type"] == "PolicyArtifact"
    assert msg.step == 10


def test_artifact_envelope_message_type_mapping():
    market = MarketArtifact(
        agent_id="INS_003", year=6,
        premium_rate=0.3, payout_ratio=0.6,
        solvency_ratio=1.0, loss_ratio=0.5,
        risk_assessment="Watchlist.",
        rationale="Watchlist.",
    )
    market_msg = ArtifactEnvelope(
        artifact=market, source_agent="INS_003", timestamp=2,
    ).to_agent_message()
    assert market_msg.message_type == MessageType.MARKET_UPDATE

    household = HouseholdIntention(
        agent_id="H_003", year=6,
        chosen_skill="elevate_house",
        tp_level="H", cp_level="H",
        confidence=0.9,
        rationale="High threat.",
    )
    household_msg = ArtifactEnvelope(
        artifact=household, source_agent="H_003", timestamp=3,
    ).to_agent_message()
    assert household_msg.message_type == MessageType.NEIGHBOR_WARNING


def test_artifact_envelope_with_overrides():
    """Test message_type_override and sender_type_override."""
    artifact = PolicyArtifact(
        agent_id="GOV_004", year=7,
        subsidy_rate=0.1, mg_priority=False,
        budget_remaining=100.0, target_adoption_rate=0.1,
        rationale="Custom routing test.",
    )
    envelope = ArtifactEnvelope(
        artifact=artifact,
        source_agent="GOV_004",
        timestamp=20,
        message_type_override="MARKET_UPDATE",
        sender_type_override="custom_agent",
    )
    msg = envelope.to_agent_message()
    assert msg.message_type == MessageType.MARKET_UPDATE
    assert msg.sender_type == "custom_agent"
