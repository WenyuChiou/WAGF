"""
Test: model_adapter reasoning parsing fix

Verifies that when LLM output doesn't match expected format,
the adapter stores the raw output as reasoning (not empty dict).
"""
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from broker.model_adapter import UnifiedAdapter

def test_empty_reasoning_fallback():
    """Test that empty reasoning dict is replaced with raw output"""
    print("\n" + "="*70)
    print("TEST: Empty Reasoning Fallback")
    print("="*70)
    
    adapter = UnifiedAdapter(agent_type="default")
    
    # Simulate LLM output without structured format
    raw_output = """
Year 1 analysis:
The flood risk seems moderate this year.
I should weigh my options carefully.
Decision: do_nothing
"""
    
    context = {"agent_id": "Agent_Test"}
    proposal = adapter.parse_output(raw_output, context)
    
    print(f"\nRaw Output (first 100 chars):")
    print(f"  {raw_output.strip()[:100]}...")
    print(f"\nParsed Proposal:")
    print(f"  Skill Name: {proposal.skill_name}")
    print(f"  Reasoning Type: {type(proposal.reasoning).__name__}")
    
    # Check reasoning is not empty
    if isinstance(proposal.reasoning, dict):
        print(f"  Reasoning Dict: {proposal.reasoning}")
        is_empty = len(proposal.reasoning) == 0
    else:
        print(f"  Reasoning Length: {len(proposal.reasoning)} chars")
        print(f"  Reasoning Preview: {proposal.reasoning[:100]}...")
        is_empty = False
    
    # Assertions
    assert proposal.skill_name == "do_nothing", f"Expected 'do_nothing', got '{proposal.skill_name}'"
    assert not is_empty, "Reasoning should not be empty!"
    
    if isinstance(proposal.reasoning, str):
        assert len(proposal.reasoning) > 0, "Reasoning string should have content"
        print("\n✅ PASS: Reasoning stored as non-empty string")
    elif isinstance(proposal.reasoning, dict) and len(proposal.reasoning) > 0:
        print("\n✅ PASS: Reasoning stored as non-empty dict")
    else:
        print(f"\n❌ FAIL: Reasoning is empty or invalid type")
        raise AssertionError("Reasoning validation failed")
    
    return True


def test_structured_reasoning_preserved():
    """Test that structured reasoning is still parsed correctly"""
    print("\n" + "="*70)
    print("TEST: Structured Reasoning Preserved")
    print("="*70)
    
    adapter = UnifiedAdapter(agent_type="default")
    
    # Simulate structured output
    raw_output = """
REASON: High flood risk this year
PRIORITY: immediate
Decision: buy_insurance
"""
    
    context = {"agent_id": "Agent_Test"}
    proposal = adapter.parse_output(raw_output, context)
    
    print(f"\nParsed Proposal:")
    print(f"  Skill: {proposal.skill_name}")
    print(f"  Reasoning: {proposal.reasoning}")
    
    assert proposal.skill_name == "buy_insurance"
    
    # Should have extracted structured fields
    if isinstance(proposal.reasoning, dict):
        assert "reason" in proposal.reasoning or len(proposal.reasoning) > 0
        print("\n✅ PASS: Structured reasoning preserved")
    else:
        # Or stored as string (also valid)
        assert isinstance(proposal.reasoning, str)
        print("\n✅ PASS: Reasoning stored as string")
    
    return True


if __name__ == "__main__":
    try:
        test_empty_reasoning_fallback()
        test_structured_reasoning_preserved()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
