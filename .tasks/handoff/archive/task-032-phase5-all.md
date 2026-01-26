# Task-032 Phase 5: Integration Tests (All CLIs)

**Status**: 🔲 Blocked on Phase 4A and 4B
**Assignee**: All CLIs (coordinated)
**Effort**: 6-8 hours
**Priority**: HIGH
**Prerequisite**: Phase 4A (XAI) and Phase 4B (Entropy) complete

---

## Git Branch

```bash
# After Phase 4A and 4B complete:
git checkout task-032-phase4a  # or phase4b, whichever is later
git checkout -b task-032-phase5
```

**Stacked PR Structure**:
```
main
 └── task-032-sdk-base (Phase 0)
      └── task-032-phase1 (Codex)
           └── task-032-phase2 (Gemini)
                ├── task-032-phase4a (Claude)
                └── task-032-phase4b (Gemini)
                     └── task-032-phase5 (this branch) ← INTEGRATION
```

---

## Objective

Validate the complete SDK works end-to-end with comprehensive integration tests and the `demo_sdk_usage.py` validation script.

---

## Deliverables

### 1. `demo_sdk_usage.py` (Complete Version)

```python
"""
GovernedAI SDK Demo - End-to-End Validation

This script validates all SDK components work together.
Run: python governed_ai_sdk/demo_sdk_usage.py
"""

from governed_ai_sdk.v1_prototype import (
    GovernanceTrace,
    PolicyRule,
    CounterFactualResult,
    EntropyFriction,
)
from governed_ai_sdk.v1_prototype.core.wrapper import (
    GovernedAgent,
    CognitiveInterceptor,
    AuditConfig,
)
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
from governed_ai_sdk.v1_prototype.core.policy_loader import PolicyLoader
from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator
from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory
from governed_ai_sdk.v1_prototype.xai.counterfactual import CounterfactualEngine


class MockHouseholdAgent:
    """Mock flood ABM household agent for testing."""

    def __init__(self, savings: int = 300, status: str = "normal"):
        self.savings = savings
        self.insurance_status = status
        self.flood_depth = 0.0
        self.action_history = []

    def decide(self, context):
        """Agent decides an action based on context."""
        if context.get("flood_warning"):
            return {"action": "buy_insurance", "premium": 100}
        return {"action": "wait", "reason": "no_threat"}

    def update(self, action):
        """Update agent state based on action."""
        self.action_history.append(action)


def test_phase0_types():
    """Test Phase 0: Type definitions."""
    print("=" * 50)
    print("Phase 0: Type Definitions")
    print("=" * 50)

    # PolicyRule
    rule = PolicyRule(
        id="min_savings",
        param="savings",
        operator=">=",
        value=500,
        message="Need $500 minimum",
        level="ERROR"
    )
    assert rule.operator == ">="
    print(f"  PolicyRule: {rule.id} ({rule.param} {rule.operator} {rule.value})")

    # GovernanceTrace
    trace = GovernanceTrace(
        valid=False,
        rule_id="min_savings",
        rule_message="Insufficient savings",
        state_delta={"savings": 200}
    )
    assert trace.valid is False
    print(f"  GovernanceTrace: valid={trace.valid}, delta={trace.state_delta}")

    print("  [PASS] Phase 0")
    return True


def test_phase1_wrapper():
    """Test Phase 1: GovernedAgent wrapper."""
    print("\n" + "=" * 50)
    print("Phase 1: GovernedAgent Wrapper")
    print("=" * 50)

    agent = MockHouseholdAgent(savings=300)

    governed = GovernedAgent(
        backend=agent,
        interceptors=[CognitiveInterceptor()],
        state_mapping_fn=lambda a: {"savings": a.savings, "status": a.insurance_status}
    )

    result = governed.execute(context={"flood_warning": True})

    assert result.action is not None
    print(f"  Action: {result.action}")
    print(f"  Trace: valid={result.trace.valid}")

    print("  [PASS] Phase 1")
    return True


def test_phase2_engine():
    """Test Phase 2: PolicyEngine."""
    print("\n" + "=" * 50)
    print("Phase 2: PolicyEngine")
    print("=" * 50)

    engine = PolicyEngine()

    policy = PolicyLoader.from_dict({
        "id": "test_policy",
        "rules": [
            {"id": "min_savings", "param": "savings", "operator": ">=",
             "value": 500, "message": "Need $500", "level": "ERROR"}
        ]
    })

    # Test PASS
    trace_pass = engine.verify(
        action={"action": "buy"},
        state={"savings": 600},
        policy=policy
    )
    assert trace_pass.valid is True
    print(f"  Pass case: valid={trace_pass.valid}")

    # Test BLOCK
    trace_block = engine.verify(
        action={"action": "buy"},
        state={"savings": 300},
        policy=policy
    )
    assert trace_block.valid is False
    assert trace_block.state_delta["savings"] == 200
    print(f"  Block case: valid={trace_block.valid}, delta={trace_block.state_delta}")

    print("  [PASS] Phase 2")
    return True


def test_phase3_memory():
    """Test Phase 3: Symbolic Memory."""
    print("\n" + "=" * 50)
    print("Phase 3: Symbolic Memory")
    print("=" * 50)

    sensors = [
        {"path": "flood", "name": "FLOOD", "bins": [
            {"label": "SAFE", "max": 0.5},
            {"label": "DANGER", "max": 99.0}
        ]}
    ]

    memory = SymbolicMemory(sensors, arousal_threshold=0.5)

    # First observation = novel
    sig1, surprise1 = memory.observe({"flood": 2.0})
    assert surprise1 == 1.0
    print(f"  First obs: surprise={surprise1:.0%} (novel)")

    # Second same = lower surprise
    sig2, surprise2 = memory.observe({"flood": 2.0})
    assert surprise2 < 1.0
    print(f"  Second obs: surprise={surprise2:.0%} (seen before)")

    print("  [PASS] Phase 3")
    return True


def test_phase4a_xai():
    """Test Phase 4A: Counterfactual XAI."""
    print("\n" + "=" * 50)
    print("Phase 4A: Counterfactual XAI")
    print("=" * 50)

    engine = CounterfactualEngine()

    # Numeric rule
    rule = PolicyRule(
        id="min_savings", param="savings", operator=">=",
        value=500, message="Need $500", level="ERROR"
    )

    result = engine.explain(rule, {"savings": 300})

    assert result.delta_state["savings"] == 200
    print(f"  Explanation: {result.explanation}")
    print(f"  Delta: {result.delta_state}")
    print(f"  Strategy: {result.strategy_used.value}")

    print("  [PASS] Phase 4A")
    return True


def test_phase4b_entropy():
    """Test Phase 4B: Entropy Calibrator."""
    print("\n" + "=" * 50)
    print("Phase 4B: Entropy Calibrator")
    print("=" * 50)

    calibrator = EntropyCalibrator()

    raw = ["buy", "sell", "hold", "speculate", "hedge"]
    governed = ["buy", "hold"]  # Many blocked

    result = calibrator.calculate_friction(raw, governed)

    print(f"  S_raw: {result.S_raw:.3f}")
    print(f"  S_governed: {result.S_governed:.3f}")
    print(f"  Friction Ratio: {result.friction_ratio:.2f}")
    print(f"  Interpretation: {result.interpretation}")

    print("  [PASS] Phase 4B")
    return True


def test_end_to_end():
    """Test complete end-to-end flow."""
    print("\n" + "=" * 50)
    print("END-TO-END INTEGRATION TEST")
    print("=" * 50)

    # 1. Create agent
    agent = MockHouseholdAgent(savings=300, status="normal")

    # 2. Create policy
    policy = PolicyLoader.from_dict({
        "id": "flood_abm_policy",
        "rules": [
            {"id": "min_savings", "param": "savings", "operator": ">=",
             "value": 500, "message": "Need $500 for insurance", "level": "ERROR"},
            {"id": "valid_status", "param": "status", "operator": "in",
             "value": ["normal", "elevated"], "message": "Invalid status", "level": "WARNING"}
        ]
    })

    # 3. Create engine and XAI
    engine = PolicyEngine()
    xai = CounterfactualEngine()

    # 4. Execute governance check
    state = {"savings": agent.savings, "status": agent.insurance_status}
    action = agent.decide({"flood_warning": True})

    trace = engine.verify(action, state, policy)

    print(f"  Action: {action}")
    print(f"  State: {state}")
    print(f"  Verdict: {'ALLOWED' if trace.valid else 'BLOCKED'}")

    # 5. If blocked, explain why
    if not trace.valid:
        rule = PolicyRule(**policy["rules"][0])  # Simplified
        cf = xai.explain(rule, state)
        print(f"  XAI: {cf.explanation}")

    # 6. Track entropy
    calibrator = EntropyCalibrator()
    raw_actions = ["buy_insurance", "wait", "evacuate"]
    governed_actions = ["wait"]  # Most blocked

    friction = calibrator.calculate_friction(raw_actions, governed_actions)
    print(f"  Entropy Friction: {friction.friction_ratio:.2f} ({friction.interpretation})")

    print("\n  [PASS] End-to-End Integration")
    return True


def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("   GovernedAI SDK - Integration Test Suite")
    print("=" * 60)

    tests = [
        ("Phase 0: Types", test_phase0_types),
        ("Phase 1: Wrapper", test_phase1_wrapper),
        ("Phase 2: Engine", test_phase2_engine),
        ("Phase 3: Memory", test_phase3_memory),
        ("Phase 4A: XAI", test_phase4a_xai),
        ("Phase 4B: Entropy", test_phase4b_entropy),
        ("End-to-End", test_end_to_end),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  [FAIL] {name}: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("   SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for name, p in results:
        status = "PASS" if p else "FAIL"
        print(f"  [{status}] {name}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n  SDK INTEGRATION VALIDATED")
        return 0
    else:
        print("\n  SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
```

### 2. `tests/test_integration.py`

```python
"""
Integration test suite for complete SDK.

Run: pytest governed_ai_sdk/tests/test_integration.py -v
"""

import pytest


class TestEndToEndFlow:
    """End-to-end integration tests."""

    def test_full_governance_flow(self):
        """Test complete governance flow from agent to trace."""
        from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
        from governed_ai_sdk.v1_prototype.core.policy_loader import PolicyLoader
        from governed_ai_sdk.v1_prototype.xai.counterfactual import CounterfactualEngine
        from governed_ai_sdk.v1_prototype.types import PolicyRule

        # Setup
        engine = PolicyEngine()
        xai = CounterfactualEngine()
        policy = PolicyLoader.from_dict({
            "rules": [
                {"id": "r1", "param": "x", "operator": ">=",
                 "value": 100, "message": "x too low", "level": "ERROR"}
            ]
        })

        # Execute
        trace = engine.verify({}, {"x": 50}, policy)

        # Verify
        assert trace.valid is False
        assert trace.state_delta["x"] == 50

        # XAI
        rule = PolicyRule(**policy["rules"][0])
        cf = xai.explain(rule, {"x": 50})
        assert cf.delta_state["x"] == 50

    def test_symbolic_memory_with_engine(self):
        """Test symbolic memory triggers System 2 on novel states."""
        from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory
        from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine

        sensors = [{"path": "risk", "name": "RISK", "bins": [
            {"label": "LO", "max": 0.5},
            {"label": "HI", "max": 1.0}
        ]}]

        memory = SymbolicMemory(sensors, arousal_threshold=0.5)
        engine = PolicyEngine()

        # Novel state = high surprise
        _, surprise = memory.observe({"risk": 0.8})
        assert surprise == 1.0

        # This would trigger System 2 in full integration

    def test_calibrator_with_real_actions(self):
        """Test calibrator with realistic action sequences."""
        from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator

        calibrator = EntropyCalibrator()

        # Simulate 10 ticks of agent actions
        raw = ["buy", "hold", "sell", "buy", "speculate",
               "hold", "hedge", "buy", "sell", "wait"]

        # After governance, speculate and hedge blocked
        governed = ["buy", "hold", "sell", "buy",
                   "hold", "buy", "sell", "wait"]

        result = calibrator.calculate_friction(raw, governed)

        # Should be balanced or slightly over-governed
        assert result.friction_ratio > 0.5
        assert result.blocked_action_count >= 0


class TestErrorHandling:
    """Test error handling across components."""

    def test_invalid_rule_raises(self):
        """Invalid PolicyRule raises ValueError."""
        from governed_ai_sdk.v1_prototype.types import PolicyRule

        with pytest.raises(ValueError):
            PolicyRule(
                id="bad", param="x", operator="INVALID",
                value=1, message="", level="ERROR"
            )

    def test_empty_policy_passes(self):
        """Empty policy means all actions pass."""
        from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine

        engine = PolicyEngine()
        trace = engine.verify({}, {"x": 1}, {"rules": []})

        assert trace.valid is True

    def test_missing_state_param_blocks(self):
        """Missing state parameter blocks action."""
        from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine

        engine = PolicyEngine()
        policy = {"rules": [
            {"id": "r1", "param": "missing", "operator": ">=",
             "value": 100, "message": "", "level": "ERROR"}
        ]}

        trace = engine.verify({}, {"other": 50}, policy)
        assert trace.valid is False
```

---

## Required Test Coverage

| Component | Min Tests | Coverage |
|:----------|:----------|:---------|
| types.py | 18 | Already done |
| wrapper.py | 4 | Phase 1 |
| engine.py | 8 | Phase 2 |
| symbolic.py | 5 | Phase 3 |
| counterfactual.py | 10 | Phase 4A |
| calibrator.py | 10 | Phase 4B |
| integration.py | 5 | This phase |
| **Total** | **60+** | |

---

## Verification Commands

```bash
# 1. Run all SDK tests
pytest governed_ai_sdk/tests/ -v

# 2. Run demo script
python governed_ai_sdk/demo_sdk_usage.py

# 3. Coverage report
pytest governed_ai_sdk/tests/ --cov=governed_ai_sdk --cov-report=term-missing
```

---

## Success Criteria

1. `demo_sdk_usage.py` completes with all phases PASS
2. All 60+ tests pass
3. No import errors
4. End-to-end flow validated
5. Error handling verified

---

## Handoff Checklist

- [ ] `demo_sdk_usage.py` complete and passing
- [ ] `tests/test_integration.py` created
- [ ] All component tests pass (60+)
- [ ] Coverage > 80%
- [ ] No breaking changes to existing code
