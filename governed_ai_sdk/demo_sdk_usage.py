"""
Demo script to validate SDK skeleton works.
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path for direct invocation
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from governed_ai_sdk.v1_prototype.types import PolicyRule
from governed_ai_sdk.v1_prototype.core.wrapper import (
    GovernedAgent,
    CognitiveInterceptor,
    AuditConfig,
)


class MockHouseholdAgent:
    """Mock agent for testing."""

    def __init__(self, savings: int = 300):
        self.savings = savings
        self.insurance_status = "none"

    def decide(self, _context):
        return {"action": "buy_insurance", "premium": 100}


def main() -> None:
    print("=== GovernedAI SDK Demo ===\n")

    agent = MockHouseholdAgent(savings=300)
    print(f"1. Created agent with savings=${agent.savings}")

    def state_fn(a):
        return {"savings": a.savings, "insurance_status": a.insurance_status}

    governed = GovernedAgent(
        backend=agent,
        interceptors=[CognitiveInterceptor(mode="LogicalConsistency")],
        state_mapping_fn=state_fn,
        audit_config=AuditConfig(enabled=True, output_path="demo_audit.jsonl"),
    )
    print("2. Wrapped agent with GovernedAgent")

    result = governed.execute(context={})
    print(f"3. Executed action: {result.action}")
    print(f"   Trace valid: {result.trace.valid}")
    print(f"   Trace message: {result.trace.rule_message}")

    state = governed.get_state()
    print(f"4. Current state: {state}")

    rule = PolicyRule(
        id="min_savings",
        param="savings",
        operator=">=",
        value=500,
        message="Need $500 minimum",
        level="ERROR",
    )
    print(f"5. Created rule: {rule.id} ({rule.param} {rule.operator} {rule.value})")

    print("\n=== Demo Complete ===")
    print("All SDK skeleton components working!")
    print("\nNext: Phase 2 will implement PolicyEngine")


if __name__ == "__main__":
    main()
