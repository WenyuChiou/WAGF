"""
Memory Helpers Unit Tests

Tests the skill-based and event-based memory update functions.
"""

import sys
sys.path.insert(0, '.')

from broker.memory import CognitiveMemory
from examples.exp3_multi_agent.memory_helpers import (
    update_memory_from_skill,
    update_memory_from_flood,
    update_memory_from_claim,
    update_memory_from_oop,
    update_memory_after_year,
    SKILL_MEMORY_MAP
)


def test_skill_memory_map_exists():
    """Test SKILL_MEMORY_MAP has all expected skills."""
    expected = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]
    for skill in expected:
        assert skill in SKILL_MEMORY_MAP, f"Missing skill: {skill}"
    print("✓ test_skill_memory_map_exists passed")


def test_update_memory_from_skill_simple():
    """Test skill memory update without context."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_skill(mem, "buy_insurance", year=3)
    
    assert item is not None
    assert "Year 3" in item.content
    assert "insurance" in item.content.lower()
    assert item.importance == 0.7
    assert "decision" in item.tags
    print("✓ test_update_memory_from_skill_simple passed")


def test_update_memory_from_skill_with_context():
    """Test skill memory update with context."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_skill(
        mem, 
        "elevate_house", 
        year=5, 
        context={"subsidy_pct": 0.5}
    )
    
    assert item is not None
    assert "50%" in item.content
    assert item.importance == 0.8
    print("✓ test_update_memory_from_skill_with_context passed")


def test_update_memory_from_skill_do_nothing():
    """Test do_nothing has low importance."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_skill(mem, "do_nothing", year=2)
    
    assert item is not None
    assert item.importance == 0.3  # Low importance
    assert "inaction" in item.tags
    print("✓ test_update_memory_from_skill_do_nothing passed")


def test_update_memory_from_flood_major():
    """Test major flood creates high-importance episodic memory."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_flood(
        mem, 
        flood_occurred=True, 
        damage=75000, 
        year=3
    )
    
    assert item is not None
    assert "major" in item.content.lower()
    assert "$75,000" in item.content
    assert item.importance == 0.9
    assert len(mem._episodic) == 1
    print("✓ test_update_memory_from_flood_major passed")


def test_update_memory_from_flood_minor():
    """Test minor flood creates lower-importance memory."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_flood(
        mem, 
        flood_occurred=True, 
        damage=5000, 
        year=2
    )
    
    assert item is not None
    assert "minor" in item.content.lower()
    assert item.importance == 0.6
    print("✓ test_update_memory_from_flood_minor passed")


def test_update_memory_from_flood_no_damage():
    """Test flood with no damage goes to working memory."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_flood(
        mem, 
        flood_occurred=True, 
        damage=0, 
        year=4
    )
    
    assert item is not None
    assert "not damaged" in item.content.lower()
    assert item.importance == 0.4
    assert len(mem._working) == 1
    print("✓ test_update_memory_from_flood_no_damage passed")


def test_update_memory_from_flood_none():
    """Test no flood returns None."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_flood(
        mem, 
        flood_occurred=False, 
        damage=0, 
        year=5
    )
    
    assert item is None
    assert len(mem._working) == 0
    assert len(mem._episodic) == 0
    print("✓ test_update_memory_from_flood_none passed")


def test_update_memory_from_claim_approved():
    """Test approved claim creates memory."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_claim(
        mem,
        claim_filed=True,
        claim_approved=True,
        payout=40000,
        damage=50000,
        out_of_pocket=10000,
        year=3
    )
    
    assert item is not None
    assert "$40,000" in item.content
    assert "approved" in item.tags
    print("✓ test_update_memory_from_claim_approved passed")


def test_update_memory_from_claim_denied():
    """Test denied claim has high importance."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_claim(
        mem,
        claim_filed=True,
        claim_approved=False,
        payout=0,
        damage=50000,
        out_of_pocket=50000,
        year=3
    )
    
    assert item is not None
    assert "denied" in item.content.lower()
    assert item.importance == 0.85
    assert "denied" in item.tags
    print("✓ test_update_memory_from_claim_denied passed")


def test_update_memory_from_oop_high():
    """Test high out-of-pocket creates memory."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_oop(mem, out_of_pocket=25000, year=3)
    
    assert item is not None
    assert "$25,000" in item.content
    assert "major" in item.tags
    assert item.importance == 0.85
    print("✓ test_update_memory_from_oop_high passed")


def test_update_memory_from_oop_low():
    """Test low out-of-pocket returns None."""
    mem = CognitiveMemory(agent_id="H001")
    
    item = update_memory_from_oop(mem, out_of_pocket=3000, year=3)
    
    assert item is None
    print("✓ test_update_memory_from_oop_low passed")


def test_update_memory_after_year():
    """Test combined year-end memory update."""
    mem = CognitiveMemory(agent_id="H001")
    
    results = update_memory_after_year(
        mem,
        year=3,
        decision="buy_insurance",
        decision_context={"premium": 1200},
        flood_occurred=True,
        damage=30000,
        claim_filed=True,
        claim_approved=True,
        payout=25000,
        out_of_pocket=5000
    )
    
    assert results['decision'] is not None
    assert results['flood'] is not None
    assert results['claim'] is not None
    
    # Verify memories were added
    all_memories = mem.retrieve(top_k=10, current_year=3)
    assert len(all_memories) >= 2
    print("✓ test_update_memory_after_year passed")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MEMORY HELPERS UNIT TESTS")
    print("=" * 60 + "\n")
    
    test_skill_memory_map_exists()
    test_update_memory_from_skill_simple()
    test_update_memory_from_skill_with_context()
    test_update_memory_from_skill_do_nothing()
    test_update_memory_from_flood_major()
    test_update_memory_from_flood_minor()
    test_update_memory_from_flood_no_damage()
    test_update_memory_from_flood_none()
    test_update_memory_from_claim_approved()
    test_update_memory_from_claim_denied()
    test_update_memory_from_oop_high()
    test_update_memory_from_oop_low()
    test_update_memory_after_year()
    
    print("\n" + "=" * 60)
    print("✅ ALL 13 TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
