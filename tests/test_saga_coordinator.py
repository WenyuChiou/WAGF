"""Tests for SagaCoordinator (Task-058D).

Tests saga execution, rollback, timeout, and domain definitions.
"""
import pytest
from broker.components.saga_coordinator import (
    SagaCoordinator,
    SagaStep,
    SagaDefinition,
    SagaStatus,
    SagaResult,
)


# ---------------------------------------------------------------------------
# Helpers: simple 3-step saga
# ---------------------------------------------------------------------------

def _step_a(ctx):
    ctx["a"] = True
    return ctx

def _comp_a(ctx):
    ctx["a"] = False

def _step_b(ctx):
    ctx["b"] = True
    return ctx

def _comp_b(ctx):
    ctx["b"] = False

def _step_c(ctx):
    ctx["c"] = True
    return ctx

def _comp_c(ctx):
    ctx["c"] = False

def _step_fail(ctx):
    raise ValueError("Intentional failure")

def _comp_noop(ctx):
    pass


SIMPLE_SAGA = SagaDefinition(
    name="simple_test",
    steps=[
        SagaStep("step_a", _step_a, _comp_a),
        SagaStep("step_b", _step_b, _comp_b),
        SagaStep("step_c", _step_c, _comp_c),
    ],
)

FAILING_SAGA = SagaDefinition(
    name="failing_test",
    steps=[
        SagaStep("step_a", _step_a, _comp_a),
        SagaStep("step_fail", _step_fail, _comp_noop),
        SagaStep("step_c", _step_c, _comp_c),
    ],
)

TIMEOUT_SAGA = SagaDefinition(
    name="timeout_test",
    steps=[
        SagaStep("step_a", _step_a, _comp_a),
        SagaStep("step_b", _step_b, _comp_b),
    ],
    timeout_steps=2,
)


@pytest.fixture
def coordinator():
    c = SagaCoordinator()
    c.register_saga(SIMPLE_SAGA)
    c.register_saga(FAILING_SAGA)
    c.register_saga(TIMEOUT_SAGA)
    return c


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_complete_saga(self, coordinator):
        saga_id = coordinator.start_saga("simple_test")
        assert coordinator.get_status(saga_id) == SagaStatus.PENDING

        # Advance 3 steps
        r1 = coordinator.advance(saga_id)
        assert r1 is None  # step_a done, still in progress
        r2 = coordinator.advance(saga_id)
        assert r2 is None  # step_b done
        r3 = coordinator.advance(saga_id)
        assert r3 is not None  # step_c done, completed!

        assert r3.status == SagaStatus.COMPLETED
        assert r3.saga_name == "simple_test"
        assert r3.context["a"] is True
        assert r3.context["b"] is True
        assert r3.context["c"] is True
        assert r3.completed_steps == ["step_a", "step_b", "step_c"]

    def test_initial_context(self, coordinator):
        saga_id = coordinator.start_saga("simple_test", context={"x": 42})
        coordinator.advance(saga_id)
        coordinator.advance(saga_id)
        result = coordinator.advance(saga_id)
        assert result.context["x"] == 42
        assert result.context["a"] is True

    def test_advance_all(self, coordinator):
        id1 = coordinator.start_saga("simple_test", context={"tag": "saga1"})
        id2 = coordinator.start_saga("simple_test", context={"tag": "saga2"})

        # Advance all 3 times
        for _ in range(3):
            completed = coordinator.advance_all()

        # Both should be completed
        assert coordinator.get_status(id1) == SagaStatus.COMPLETED
        assert coordinator.get_status(id2) == SagaStatus.COMPLETED


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

class TestRollback:
    def test_rollback_on_failure(self, coordinator):
        saga_id = coordinator.start_saga("failing_test")

        # step_a succeeds
        r1 = coordinator.advance(saga_id)
        assert r1 is None

        # step_fail fails -> rollback
        r2 = coordinator.advance(saga_id)
        assert r2 is not None
        assert r2.status == SagaStatus.ROLLED_BACK
        assert "step_fail" in r2.error
        assert r2.completed_steps == ["step_a"]
        # Compensation should have set a=False
        assert r2.context["a"] is False

    def test_rollback_preserves_completed_steps(self, coordinator):
        saga_id = coordinator.start_saga("failing_test")
        coordinator.advance(saga_id)  # step_a OK
        result = coordinator.advance(saga_id)  # step_fail -> rollback
        assert result.completed_steps == ["step_a"]
        assert result.status == SagaStatus.ROLLED_BACK


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

class TestTimeout:
    def test_timeout_triggers_rollback(self, coordinator):
        saga_id = coordinator.start_saga("timeout_test", step=0)
        coordinator.advance(saga_id, current_step=0)  # step_a at step 0

        # Now at step 5, timeout_steps=2, started_at=0 -> 5-0 > 2 -> timeout
        result = coordinator.advance(saga_id, current_step=5)
        assert result is not None
        assert result.status == SagaStatus.ROLLED_BACK
        assert "Timeout" in result.error

    def test_no_timeout_within_window(self, coordinator):
        saga_id = coordinator.start_saga("timeout_test", step=0)
        r1 = coordinator.advance(saga_id, current_step=1)  # step_a, within window
        assert r1 is None  # Still running
        r2 = coordinator.advance(saga_id, current_step=2)  # step_b, within window
        assert r2 is not None
        assert r2.status == SagaStatus.COMPLETED


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_unknown_saga_raises(self, coordinator):
        with pytest.raises(ValueError, match="Unknown saga"):
            coordinator.start_saga("nonexistent_saga")

    def test_advance_unknown_id(self, coordinator):
        assert coordinator.advance("saga_999") is None

    def test_advance_completed_saga(self, coordinator):
        saga_id = coordinator.start_saga("simple_test")
        for _ in range(3):
            coordinator.advance(saga_id)
        # Saga is completed, advancing again returns None
        assert coordinator.advance(saga_id) is None

    def test_max_concurrent(self):
        c = SagaCoordinator(max_concurrent=1)
        c.register_saga(SIMPLE_SAGA)
        c.start_saga("simple_test")
        with pytest.raises(ValueError, match="Max concurrent"):
            c.start_saga("simple_test")

    def test_results_property(self, coordinator):
        saga_id = coordinator.start_saga("simple_test")
        for _ in range(3):
            coordinator.advance(saga_id)
        assert len(coordinator.results) == 1
        assert coordinator.results[0].saga_name == "simple_test"


# ---------------------------------------------------------------------------
# Domain definitions (flood)
# ---------------------------------------------------------------------------

class TestFloodSagas:
    def test_subsidy_saga_happy_path(self):
        from examples.multi_agent.ma_saga_definitions import SUBSIDY_APPLICATION_SAGA
        c = SagaCoordinator()
        c.register_saga(SUBSIDY_APPLICATION_SAGA)
        saga_id = c.start_saga("subsidy_application", context={
            "household_id": "H_001",
            "budget_remaining": 50000,
            "subsidy_cost": 5000,
        })
        for _ in range(3):
            result = c.advance(saga_id)
        assert result is not None
        assert result.status == SagaStatus.COMPLETED
        assert result.context["subsidy_received"] is True
        assert result.context["budget_remaining"] == 45000

    def test_subsidy_saga_insufficient_budget(self):
        from examples.multi_agent.ma_saga_definitions import SUBSIDY_APPLICATION_SAGA
        c = SagaCoordinator()
        c.register_saga(SUBSIDY_APPLICATION_SAGA)
        saga_id = c.start_saga("subsidy_application", context={
            "household_id": "H_001",
            "budget_remaining": 100,  # Not enough
            "subsidy_cost": 5000,
        })
        c.advance(saga_id)  # step 1: application
        result = c.advance(saga_id)  # step 2: government review -> fail
        assert result is not None
        assert result.status == SagaStatus.ROLLED_BACK
        assert "Insufficient budget" in result.error
        # Compensation: application cancelled
        assert result.context["application_submitted"] is False

    def test_insurance_claim_below_deductible(self):
        from examples.multi_agent.ma_saga_definitions import INSURANCE_CLAIM_SAGA
        c = SagaCoordinator()
        c.register_saga(INSURANCE_CLAIM_SAGA)
        saga_id = c.start_saga("insurance_claim", context={
            "household_id": "H_002",
            "damage_amount": 500,  # Below deductible
            "deductible": 1000,
        })
        c.advance(saga_id)  # file claim
        result = c.advance(saga_id)  # evaluate -> fail
        assert result is not None
        assert result.status == SagaStatus.ROLLED_BACK
        assert "deductible" in result.error.lower()
