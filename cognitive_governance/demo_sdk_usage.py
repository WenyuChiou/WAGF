"""
GovernedAI SDK Demo - End-to-End Validation

Run: python cognitive_governance/demo_sdk_usage.py
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path for direct invocation
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cognitive_governance.v1_prototype.types import (
    GovernanceTrace,
    PolicyRule,
    CounterFactualResult,
    EntropyFriction,
)
from cognitive_governance.v1_prototype.core.wrapper import GovernedAgent
from cognitive_governance.v1_prototype.core.engine import PolicyEngine
from cognitive_governance.v1_prototype.core.policy_loader import PolicyLoader
from cognitive_governance.v1_prototype.core.calibrator import EntropyCalibrator
from cognitive_governance.v1_prototype.memory.symbolic import SymbolicMemory
from cognitive_governance.v1_prototype.xai.counterfactual import CounterfactualEngine


def test_all_phases() -> None:
    print("=" * 60)
    print("   GovernedAI SDK - Integration Test Suite")
    print("=" * 60)

    # Phase 0: Types
    print("\n[Phase 0] Types...")
    rule = PolicyRule(
        id="min_savings",
        param="savings",
        operator=">=",
        value=500,
        message="Need $500",
        level="ERROR",
    )
    assert rule.operator == ">="
    print("  ? PolicyRule OK")

    # Phase 1: Wrapper
    print("\n[Phase 1] Wrapper...")

    class MockAgent:
        def __init__(self):
            self.savings = 300

        def decide(self, _ctx):
            return {"action": "buy"}

    agent = MockAgent()
    governed = GovernedAgent(
        backend=agent,
        interceptors=[],
        state_mapping_fn=lambda a: {"savings": a.savings},
    )
    print("  ? GovernedAgent OK")

    # Phase 2: PolicyEngine
    print("\n[Phase 2] PolicyEngine...")
    engine = PolicyEngine()
    policy = PolicyLoader.from_dict(
        {
            "rules": [
                {
                    "id": "r1",
                    "param": "savings",
                    "operator": ">=",
                    "value": 500,
                    "message": "Need $500",
                    "level": "ERROR",
                }
            ]
        }
    )
    trace = engine.verify({}, {"savings": 600}, policy)
    assert trace.valid is True
    print("  ? PolicyEngine PASS case OK")

    trace = engine.verify({}, {"savings": 300}, policy)
    assert trace.valid is False
    print("  ? PolicyEngine BLOCK case OK")

    # Phase 3: SymbolicMemory
    print("\n[Phase 3] SymbolicMemory...")
    sensors = [
        {
            "path": "flood",
            "name": "FLOOD",
            "bins": [
                {"label": "SAFE", "max": 0.5},
                {"label": "DANGER", "max": 99.0},
            ],
        }
    ]
    memory = SymbolicMemory(sensors)
    sig, surprise = memory.observe({"flood": 2.0})
    assert surprise == 1.0
    print(f"  ? SymbolicMemory novelty detection OK (surprise={surprise})")

    # Phase 4A: Counterfactual XAI
    print("\n[Phase 4A] CounterfactualEngine...")
    xai = CounterfactualEngine()
    cf_result = xai.explain(rule, {"savings": 300})
    assert cf_result.delta_state["savings"] == 200
    print(f"  ? Counterfactual: {cf_result.explanation}")

    # Phase 4B: EntropyCalibrator
    print("\n[Phase 4B] EntropyCalibrator...")
    calibrator = EntropyCalibrator()
    raw = ["buy", "sell", "hold", "speculate", "hedge"]
    governed_actions = ["buy", "hold"]
    friction = calibrator.calculate_friction(raw, governed_actions)
    print(f"  ? Friction ratio: {friction.friction_ratio:.2f} ({friction.interpretation})")

    # End-to-End
    print("\n[End-to-End] Full Flow...")
    state = {"savings": 300, "status": "normal"}
    action = {"action": "buy_insurance"}
    trace = engine.verify(action, state, policy)
    if not trace.valid:
        cf = xai.explain(PolicyRule(**policy["rules"][0]), state)
        print(f"  Action BLOCKED: {trace.rule_message}")
        print(f"  XAI: {cf.explanation}")

    print("\n" + "=" * 60)
    print("   ALL PHASES PASSED")
    print("=" * 60)


if __name__ == "__main__":
    test_all_phases()
