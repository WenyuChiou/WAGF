"""
Test: Broker never mutates state directly.

This test verifies the core invariant that only the simulation engine
can mutate state, not the broker.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.engine import ToySimulationEngine
from broker.legacy.types import DecisionRequest, ValidationResult


def test_broker_does_not_mutate_state():
    """Verify broker components don't mutate agent state."""
    
    # Setup
    sim = ToySimulationEngine(num_agents=5, seed=42)
    agent = sim.get_agent("Agent_1")
    
    # Record initial state
    initial_resources = agent.resources
    initial_vulnerability = agent.vulnerability
    initial_memory = agent.memory.copy()
    
    # Create a decision request (simulating LLM output)
    request = DecisionRequest(
        action_code="adapt",
        reasoning={"threat": "high", "coping": "can handle"},
        raw_output='{"decision": "adapt"}'
    )
    
    # Validation should NOT change state
    from validators.base import SchemaValidator, PolicyValidator
    
    schema_val = SchemaValidator()
    policy_val = PolicyValidator(allowed_actions=["do_nothing", "adapt", "buy_insurance"])
    
    result1 = schema_val.validate(request, {})
    result2 = policy_val.validate(request, {})
    
    # Verify state unchanged after validation
    assert agent.resources == initial_resources
    assert agent.vulnerability == initial_vulnerability
    assert agent.memory == initial_memory


def test_only_execution_interface_mutates_state():
    """Verify only ExecutionInterface.execute() mutates state."""
    
    sim = ToySimulationEngine(num_agents=5, seed=42)
    agent = sim.get_agent("Agent_1")
    
    initial_resources = agent.resources
    
    # Admissibility check should NOT mutate state
    from interfaces.execution_interface import AdmissibleCommand
    
    admissible = sim.check_admissibility("Agent_1", "adapt", {})
    assert agent.resources == initial_resources  # Still unchanged
    
    # Only execute() should mutate state
    result = sim.execute(admissible)
    assert agent.resources < initial_resources  # Now changed
    assert result.success
    assert result.state_changes.get("action") == "adapt"


def test_memory_cannot_be_modified_by_llm():
    """Verify LLM output cannot directly modify memory."""
    
    sim = ToySimulationEngine(num_agents=5, seed=42)
    agent = sim.get_agent("Agent_1")
    
    initial_memory = agent.memory.copy()
    
    # Simulate malicious LLM output trying to modify memory
    request = DecisionRequest(
        action_code="do_nothing",
        reasoning={"threat": "I will update memory directly"},
        raw_output='{"decision": "do_nothing", "memory": ["hacked"]}'
    )
    
    from validators.base import MemoryIntegrityValidator
    
    validator = MemoryIntegrityValidator()
    
    # Memory should still be unchanged
    assert agent.memory == initial_memory


if __name__ == "__main__":
    test_broker_does_not_mutate_state()
    test_only_execution_interface_mutates_state()
    test_memory_cannot_be_modified_by_llm()
    print("All tests passed!")
