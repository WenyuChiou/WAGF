"""Integration wiring tests for Task-058F."""
from types import SimpleNamespace
from unittest.mock import MagicMock
import logging

import pytest

from broker.components.coordinator import GameMaster
from broker.components.message_pool import MessagePool
from broker.components.phase_orchestrator import PhaseOrchestrator
from broker.interfaces.artifacts import ArtifactEnvelope
from broker.interfaces.coordination import ActionProposal
from examples.multi_agent.ma_artifacts import PolicyArtifact
from examples.multi_agent.orchestration.lifecycle_hooks import MultiAgentHooks


def _policy_artifact():
    return PolicyArtifact(
        agent_id="GOV_001",
        year=1,
        rationale="test",
        subsidy_rate=0.5,
        mg_priority=True,
        budget_remaining=10000.0,
        target_adoption_rate=0.6,
    )


class TestGameMasterArtifacts:
    def test_submit_artifact_publishes(self):
        pool = MessagePool()
        pool.register_agent("HH_001")

        gm = GameMaster(message_pool=pool)
        envelope = ArtifactEnvelope(
            artifact=_policy_artifact(),
            source_agent="GOV_001",
            timestamp=1,
        )

        gm.submit_artifact(envelope)
        messages = pool.get_messages("HH_001")
        assert messages
        assert messages[0].data["artifact_type"] == "PolicyArtifact"

    def test_cross_validator_logs_warning(self, caplog):
        class DummyResult:
            is_valid = False
            rule_id = "TEST_RULE"
            message = "bad"

        class DummyValidator:
            def validate_round(self, artifacts, resolutions):
                return [DummyResult()]

        pool = MessagePool()
        gm = GameMaster(message_pool=pool, cross_validator=DummyValidator())
        gm.submit_artifact(ArtifactEnvelope(artifact=_policy_artifact(), source_agent="GOV_001"))

        proposal = ActionProposal(agent_id="GOV_001", agent_type="government", skill_name="maintain_subsidy")
        with caplog.at_level(logging.WARNING):
            gm.resolve_phase(proposals=[proposal])

        assert any("CrossValidation" in rec.message for rec in caplog.records)


class TestPhaseOrchestratorSaga:
    def test_saga_advance_called(self):
        saga = MagicMock()
        saga.advance_all.return_value = []
        orchestrator = PhaseOrchestrator(saga_coordinator=saga)

        orchestrator.advance_sagas(current_step=5)
        saga.advance_all.assert_called_once()


class TestLifecycleHooksDrift:
    def test_drift_detector_records(self):
        drift = MagicMock()
        drift.get_alerts.return_value = []

        env = {"subsidy_rate": 0.5, "premium_rate": 0.05}
        hooks = MultiAgentHooks(env, drift_detector=drift)

        agent = SimpleNamespace(
            id="H_001",
            agent_type="household_owner",
            dynamic_state={"elevated": False, "relocated": False, "cumulative_damage": 0},
            fixed_attributes={"rcv_building": 1000.0, "rcv_contents": 500.0},
            last_decision="buy_insurance",
        )

        result = SimpleNamespace(
            outcome=SimpleNamespace(name="SUCCESS"),
            skill_proposal=SimpleNamespace(skill_name="buy_insurance", reasoning={}),
            TP_LABEL="M",
            CP_LABEL="M",
        )

        hooks.post_step(agent, result)
        drift.record_agent_decision.assert_called()

        hooks.post_year(1, {"H_001": agent}, memory_engine=None)
        drift.record_population_snapshot.assert_called_once()


class TestBackwardCompat:
    def test_defaults_optional(self):
        gm = GameMaster()
        assert gm.cross_validator is None

        orchestrator = PhaseOrchestrator()
        assert orchestrator.saga_coordinator is None
