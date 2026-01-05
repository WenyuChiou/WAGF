"""
Validator Rules Unit Tests

Tests all validation rules R1-R7 for household agents.
"""

import sys
sys.path.insert(0, '.')

from dataclasses import dataclass, field
from typing import Optional, List

# Import validators
from examples.exp3_multi_agent.validators import (
    ValidationResult,
    R1_HighTPCPDoNothing,
    R2_LowTPAction,
    R3_NoRedundantElevation,
    R4_RenterNoElevate,
    R5_AffordabilityCheck,
    R6_RelocatedNoAction,
    R7_FullPARelocate,
)


# =============================================================================
# MOCK DATA CLASS
# =============================================================================

@dataclass
class MockHouseholdOutput:
    """Mock HouseholdOutput for testing."""
    agent_id: str = "H001"
    mg: bool = True
    tenure: str = "Owner"
    year: int = 1
    decision_skill: str = "do_nothing"
    decision_number: int = 4
    tp_level: str = "MODERATE"
    tp_explanation: str = ""
    cp_level: str = "MODERATE"
    cp_explanation: str = ""
    sp_level: str = "MODERATE"
    sp_explanation: str = ""
    sc_level: str = "MODERATE"
    sc_explanation: str = ""
    pa_level: str = "NONE"
    pa_explanation: str = ""
    justification: str = "Test"
    validated: bool = True
    validation_errors: List[str] = field(default_factory=list)
    raw_response: str = ""


# =============================================================================
# RULE TESTS
# =============================================================================

def test_r1_high_tp_cp_do_nothing():
    """R1: High TP + High CP but doing nothing -> Warning."""
    rule = R1_HighTPCPDoNothing()
    output = MockHouseholdOutput(decision_skill="do_nothing", tp_level="HIGH", cp_level="HIGH")
    result = rule.check(output, {})
    assert result is not None
    print("✓ R1: do_nothing with HIGH TP/CP -> Warning")


def test_r1_high_tp_cp_action():
    """R1: High TP + High CP taking action -> Pass."""
    rule = R1_HighTPCPDoNothing()
    output = MockHouseholdOutput(decision_skill="buy_insurance", tp_level="HIGH", cp_level="HIGH")
    result = rule.check(output, {})
    assert result is None
    print("✓ R1: action with HIGH TP/CP -> Pass")


def test_r2_low_tp_action():
    """R2: Low TP but taking action -> Warning."""
    rule = R2_LowTPAction()
    output = MockHouseholdOutput(decision_skill="buy_insurance", tp_level="LOW")
    result = rule.check(output, {})
    assert result is not None
    print("✓ R2: action with LOW TP -> Warning")


def test_r2_low_tp_do_nothing():
    """R2: Low TP doing nothing -> Pass."""
    rule = R2_LowTPAction()
    output = MockHouseholdOutput(decision_skill="do_nothing", tp_level="LOW")
    result = rule.check(output, {})
    assert result is None
    print("✓ R2: do_nothing with LOW TP -> Pass")


def test_r3_already_elevated():
    """R3: Already elevated trying to elevate -> Error."""
    rule = R3_NoRedundantElevation()
    output = MockHouseholdOutput(decision_skill="elevate_house")
    result = rule.check(output, {"elevated": True})
    assert result is not None
    print("✓ R3: elevate when already elevated -> Error")


def test_r3_not_elevated():
    """R3: Not elevated, can elevate -> Pass."""
    rule = R3_NoRedundantElevation()
    output = MockHouseholdOutput(decision_skill="elevate_house")
    result = rule.check(output, {"elevated": False})
    assert result is None
    print("✓ R3: elevate when not elevated -> Pass")


def test_r4_renter_elevate():
    """R4: Renter trying to elevate -> Error."""
    rule = R4_RenterNoElevate()
    output = MockHouseholdOutput(decision_skill="elevate_house")
    result = rule.check(output, {})
    assert result is not None
    print("✓ R4: renter elevate -> Error")


def test_r5_low_cp_high_cost():
    """R5: Low CP with elevation -> Warning."""
    rule = R5_AffordabilityCheck()
    output = MockHouseholdOutput(decision_skill="elevate_house", cp_level="LOW")
    result = rule.check(output, {})
    assert result is not None
    print("✓ R5: elevate with LOW CP -> Warning")


def test_r5_high_cp_high_cost():
    """R5: High CP with elevation -> Pass."""
    rule = R5_AffordabilityCheck()
    output = MockHouseholdOutput(decision_skill="elevate_house", cp_level="HIGH")
    result = rule.check(output, {})
    assert result is None
    print("✓ R5: elevate with HIGH CP -> Pass")


def test_r6_already_relocated():
    """R6: Relocated agent taking action -> Error."""
    rule = R6_RelocatedNoAction()
    output = MockHouseholdOutput(decision_skill="buy_insurance")
    result = rule.check(output, {"relocated": True})
    assert result is not None
    print("✓ R6: action when relocated -> Error")


def test_r6_not_relocated():
    """R6: Not relocated, can act -> Pass."""
    rule = R6_RelocatedNoAction()
    output = MockHouseholdOutput(decision_skill="buy_insurance")
    result = rule.check(output, {"relocated": False})
    assert result is None
    print("✓ R6: action when not relocated -> Pass")


def test_r7_full_pa_relocate():
    """R7: Full PA but relocating -> Warning."""
    rule = R7_FullPARelocate()
    output = MockHouseholdOutput(decision_skill="relocate", pa_level="FULL")
    result = rule.check(output, {})
    assert result is not None
    print("✓ R7: relocate with FULL PA -> Warning")


def test_r7_no_pa_relocate():
    """R7: No PA, relocating -> Pass."""
    rule = R7_FullPARelocate()
    output = MockHouseholdOutput(decision_skill="relocate", pa_level="NONE")
    result = rule.check(output, {})
    assert result is None
    print("✓ R7: relocate with NONE PA -> Pass")


def test_validation_result_merge():
    """ValidationResult merge: False wins."""
    result1 = ValidationResult(valid=True, errors=[], warnings=["W1"])
    result2 = ValidationResult(valid=False, errors=["E1"], warnings=["W2"])
    merged = result1.merge(result2)  # merge() returns new object
    assert merged.valid == False
    assert "E1" in merged.errors
    print("✓ ValidationResult merge works")


def main():
    print("\n" + "=" * 60)
    print("VALIDATOR RULES UNIT TESTS")
    print("=" * 60 + "\n")
    
    test_r1_high_tp_cp_do_nothing()
    test_r1_high_tp_cp_action()
    test_r2_low_tp_action()
    test_r2_low_tp_do_nothing()
    test_r3_already_elevated()
    test_r3_not_elevated()
    test_r4_renter_elevate()
    test_r5_low_cp_high_cost()
    test_r5_high_cp_high_cost()
    test_r6_already_relocated()
    test_r6_not_relocated()
    test_r7_full_pa_relocate()
    test_r7_no_pa_relocate()
    test_validation_result_merge()
    
    print("\n" + "=" * 60)
    print("✅ ALL 14 TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
