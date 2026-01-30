"""Tests for CrossAgentValidator (Task-058B).

Tests generic checks (echo_chamber, deadlock) and domain rule injection.
"""
import pytest
from unittest.mock import MagicMock

from broker.interfaces.artifacts import AgentArtifact, ArtifactEnvelope
from broker.interfaces.coordination import ActionResolution
from broker.validators.governance.cross_agent_validator import (
    CrossAgentValidator,
    CrossValidationResult,
    ValidationLevel,
)

from examples.multi_agent.flood.protocols.artifacts import (
    PolicyArtifact,
    MarketArtifact,
    HouseholdIntention,
)
from examples.multi_agent.flood.protocols.cross_validators import (
    flood_perverse_incentive_check,
    flood_budget_coherence_check,
    FLOOD_VALIDATION_RULES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _policy(subsidy_rate=0.5, budget_remaining=10000.0) -> PolicyArtifact:
    return PolicyArtifact(
        agent_id="GOV_001", year=1, rationale="test",
        subsidy_rate=subsidy_rate, mg_priority=True,
        budget_remaining=budget_remaining, target_adoption_rate=0.6,
    )


def _market(premium_rate=0.1, loss_ratio=0.5) -> MarketArtifact:
    return MarketArtifact(
        agent_id="INS_001", year=1, rationale="test",
        premium_rate=premium_rate, payout_ratio=0.7,
        solvency_ratio=1.1, loss_ratio=loss_ratio,
        risk_assessment="Stable",
    )


def _intention(skill: str = "buy_insurance") -> HouseholdIntention:
    return HouseholdIntention(
        agent_id="H_001", year=1, rationale="test",
        chosen_skill=skill, tp_level="M", cp_level="M", confidence=0.8,
    )


def _resolution(approved: bool, agent_id: str = "Agent1") -> ActionResolution:
    return ActionResolution(
        agent_id=agent_id,
        approved=approved,
        event_statement="Action was processed.",
        original_proposal=MagicMock(),
        denial_reason="" if approved else "Denied.",
    )


@pytest.fixture
def validator():
    return CrossAgentValidator(echo_threshold=0.8, entropy_threshold=0.5,
                               deadlock_threshold=0.5)


@pytest.fixture
def flood_validator():
    return CrossAgentValidator(echo_threshold=0.8, entropy_threshold=0.5,
                               deadlock_threshold=0.5,
                               domain_rules=FLOOD_VALIDATION_RULES)


# ---------------------------------------------------------------------------
# Echo Chamber (generic)
# ---------------------------------------------------------------------------

class TestEchoChamberCheck:
    def test_echo_chamber_detected(self, validator):
        intentions = [_intention("invest_in_solar") for _ in range(9)] + \
                     [_intention("buy_insurance")]
        result = validator.echo_chamber_check(intentions)
        assert not result.is_valid
        assert result.rule_id == "ECHO_CHAMBER_DETECTED"
        assert "90%" in result.message

    def test_low_entropy_detected(self):
        # Need high entropy_threshold so that diverse-but-not-diverse-enough triggers
        v = CrossAgentValidator(echo_threshold=0.95, entropy_threshold=2.6)
        # 6 distinct skills across 10 agents -> ~2.52 bits entropy < 2.6
        intentions = [_intention(f"skill_{i}") for i in range(4)] * 2 + \
                     [_intention("unique_1"), _intention("unique_2")]
        result = v.echo_chamber_check(intentions)
        assert not result.is_valid
        assert result.rule_id == "LOW_DECISION_ENTROPY"

    def test_diverse_decisions_pass(self, validator):
        intentions = [_intention(f"skill_{i}") for i in range(10)]
        result = validator.echo_chamber_check(intentions)
        assert result.is_valid

    def test_empty_intentions(self, validator):
        result = validator.echo_chamber_check([])
        assert result.is_valid
        assert result.rule_id == "ECHO_CHAMBER"


# ---------------------------------------------------------------------------
# Deadlock (generic)
# ---------------------------------------------------------------------------

class TestDeadlockCheck:
    def test_deadlock_detected(self, validator):
        resolutions = [_resolution(False) for _ in range(6)] + \
                      [_resolution(True) for _ in range(4)]
        result = validator.deadlock_check(resolutions)
        assert not result.is_valid
        assert result.rule_id == "DEADLOCK_RISK"
        assert "60%" in result.message

    def test_mostly_approved_passes(self, validator):
        resolutions = [_resolution(True) for _ in range(9)] + [_resolution(False)]
        result = validator.deadlock_check(resolutions)
        assert result.is_valid

    def test_empty_resolutions(self, validator):
        result = validator.deadlock_check([])
        assert result.is_valid
        assert result.rule_id == "DEADLOCK"


# ---------------------------------------------------------------------------
# Domain rules: Perverse Incentive (flood-specific)
# ---------------------------------------------------------------------------

class TestFloodPerverseIncentive:
    def test_cancellation_warning(self):
        artifacts = {"policy": _policy(subsidy_rate=0.6), "market": _market(premium_rate=0.12)}
        prev = {"policy": _policy(subsidy_rate=0.5), "market": _market(premium_rate=0.1)}
        result = flood_perverse_incentive_check(artifacts, prev)
        assert result is not None
        assert not result.is_valid
        assert result.rule_id == "PERVERSE_INCENTIVE_CANCELLATION"

    def test_abandonment_warning(self):
        artifacts = {"policy": _policy(subsidy_rate=0.4), "market": _market(loss_ratio=0.75)}
        prev = {"policy": _policy(subsidy_rate=0.6), "market": _market(loss_ratio=0.4)}
        result = flood_perverse_incentive_check(artifacts, prev)
        assert result is not None
        assert not result.is_valid
        assert result.rule_id == "PERVERSE_INCENTIVE_ABANDONMENT"

    def test_no_warning_single_change(self):
        artifacts = {"policy": _policy(subsidy_rate=0.6), "market": _market(premium_rate=0.1)}
        prev = {"policy": _policy(subsidy_rate=0.5), "market": _market(premium_rate=0.1)}
        result = flood_perverse_incentive_check(artifacts, prev)
        assert result is None

    def test_skips_without_prev(self):
        artifacts = {"policy": _policy(), "market": _market()}
        result = flood_perverse_incentive_check(artifacts, None)
        assert result is None


# ---------------------------------------------------------------------------
# Domain rules: Budget Coherence (flood-specific)
# ---------------------------------------------------------------------------

class TestFloodBudgetCoherence:
    def test_budget_shortfall_detected(self):
        policy = _policy(subsidy_rate=0.8, budget_remaining=39999.0)
        intentions = [_intention() for _ in range(10)]
        artifacts = {"policy": policy, "intentions": intentions}
        result = flood_budget_coherence_check(artifacts, None, avg_subsidy_cost=5000.0)
        assert result is not None
        assert not result.is_valid
        assert result.rule_id == "BUDGET_SHORTFALL"

    def test_budget_sufficient(self):
        policy = _policy(subsidy_rate=0.8, budget_remaining=50000.0)
        intentions = [_intention() for _ in range(10)]
        artifacts = {"policy": policy, "intentions": intentions}
        result = flood_budget_coherence_check(artifacts, None, avg_subsidy_cost=5000.0)
        assert result is None

    def test_skips_without_policy(self):
        artifacts = {"intentions": [_intention()]}
        result = flood_budget_coherence_check(artifacts, None)
        assert result is None


# ---------------------------------------------------------------------------
# validate_round (integration of generic + domain)
# ---------------------------------------------------------------------------

class TestValidateRound:
    def test_generic_only_returns_echo_and_deadlock(self, validator):
        artifacts = {
            "intentions": [_intention("same_skill") for _ in range(10)],
        }
        resolutions = [_resolution(False) for _ in range(6)] + \
                      [_resolution(True) for _ in range(4)]
        results = validator.validate_round(artifacts, resolutions=resolutions)
        rule_ids = {r.rule_id for r in results}
        assert "ECHO_CHAMBER_DETECTED" in rule_ids
        assert "DEADLOCK_RISK" in rule_ids
        assert len(validator.history) == 1

    def test_with_flood_domain_rules(self, flood_validator):
        policy = _policy(subsidy_rate=0.6, budget_remaining=1000.0)
        market = _market(premium_rate=0.12)
        prev = {
            "policy": _policy(subsidy_rate=0.5),
            "market": _market(premium_rate=0.1),
        }
        intentions = [_intention("same_skill") for _ in range(10)]
        artifacts = {
            "policy": policy, "market": market,
            "intentions": intentions,
        }
        results = flood_validator.validate_round(
            artifacts, prev_artifacts=prev,
        )
        rule_ids = {r.rule_id for r in results}
        # Should have echo chamber + perverse incentive + budget shortfall
        assert "ECHO_CHAMBER_DETECTED" in rule_ids
        assert "PERVERSE_INCENTIVE_CANCELLATION" in rule_ids
        assert "BUDGET_SHORTFALL" in rule_ids

    def test_empty_returns_no_errors(self, validator):
        results = validator.validate_round({})
        assert results == []
        assert len(validator.history) == 1

    def test_no_resolutions_skips_deadlock(self, validator):
        artifacts = {"intentions": [_intention(f"s_{i}") for i in range(10)]}
        results = validator.validate_round(artifacts)
        assert not any(r.rule_id == "DEADLOCK_RISK" for r in results)
