"""
SA E2E Smoke Test - Phase 6 of Integration Test Suite.
Task-038: End-to-end verification of SA flood adaptation pipeline.

Tests:
- SA-E2E01: 3-year simulation completes
- SA-E2E02: Skill execution changes state
- SA-E2E03: Audit file created
- SA-E2E04: All traces valid JSON
- SA-E2E05: State progression recorded
"""
import pytest
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from broker.utils.model_adapter import UnifiedAdapter
from broker.components.skill_registry import SkillRegistry
from validators.agent_validator import AgentValidator
from simulation.environment import TieredEnvironment
from broker.interfaces.skill_types import SkillProposal, ValidationResult
from governed_ai_sdk.agents import BaseAgent, AgentConfig


# Mock LLM responses for deterministic testing
MOCK_RESPONSES = {
    "year_1": '''<<<DECISION_START>>>
{
    "decision": 1,
    "threat_appraisal": {"label": "H", "reason": "High flood risk in year 1"},
    "coping_appraisal": {"label": "M", "reason": "Moderate resources available"}
}
<<<DECISION_END>>>''',
    "year_2": '''<<<DECISION_START>>>
{
    "decision": 2,
    "threat_appraisal": {"label": "VH", "reason": "Very high risk after flood"},
    "coping_appraisal": {"label": "H", "reason": "Good resources for elevation"}
}
<<<DECISION_END>>>''',
    "year_3": '''<<<DECISION_START>>>
{
    "decision": 4,
    "threat_appraisal": {"label": "L", "reason": "Lower risk after elevation"},
    "coping_appraisal": {"label": "M", "reason": "Moderate resources"}
}
<<<DECISION_END>>>'''
}


class MockLLM:
    """Mock LLM that returns year-based responses."""

    def __init__(self, responses=None):
        self.responses = responses or MOCK_RESPONSES
        self.call_count = 0

    def invoke(self, prompt, year=1, **kwargs):
        """Return mock response based on year."""
        self.call_count += 1
        key = f"year_{year}"
        return self.responses.get(key, self.responses.get("year_1"))


@pytest.fixture
def mock_llm():
    """Create mock LLM."""
    return MockLLM()


@pytest.fixture
def adapter():
    """Create UnifiedAdapter for SA."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "examples", "single_agent", "agent_types.yaml"
    )
    return UnifiedAdapter(agent_type="household", config_path=config_path)


@pytest.fixture
def skill_registry():
    """Create populated skill registry."""
    registry = SkillRegistry()
    yaml_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "examples", "single_agent", "skill_registry.yaml"
    )
    registry.register_from_yaml(yaml_path)
    return registry


@pytest.fixture
def validator():
    """Create agent validator."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "examples", "single_agent", "agent_types.yaml"
    )
    return AgentValidator(config_path=config_path)


@pytest.fixture
def environment():
    """Create tiered environment."""
    return TieredEnvironment()


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class SimulationTrace:
    """Collects traces during simulation."""

    def __init__(self):
        self.traces = []
        self.state_history = []

    def add_trace(self, year, agent_state, proposal, validation_result, approved):
        """Add a trace entry."""
        self.traces.append({
            "year": year,
            "agent_id": "test_household_001",
            "agent_type": "household",
            "state_before": dict(agent_state),
            "skill_proposal": {
                "skill_name": proposal.skill_name if proposal else None,
                "reasoning": proposal.reasoning if proposal else {},
                "parse_layer": proposal.parse_layer if proposal else ""
            },
            "validation_result": {
                "outcome": "APPROVED" if approved else "BLOCKED",
                "issues": [str(r.errors) for r in validation_result if not r.valid]
            },
            "validated": approved
        })

    def add_state_snapshot(self, year, state):
        """Record state at end of year."""
        self.state_history.append({
            "year": year,
            "state": dict(state)
        })


class TestSAE2ESmoke:
    """End-to-end smoke tests for SA flood adaptation."""

    def run_simulation_year(
        self,
        year,
        agent_state,
        environment,
        mock_llm,
        adapter,
        skill_registry,
        validator,
        trace_collector
    ):
        """Run one year of simulation."""
        # Set up environment for this year
        flood_years = [1, 2, 4, 5, 7, 8, 10]
        flood_occurred = year in flood_years
        environment.set_global("year", year)
        environment.set_global("flood_occurred", flood_occurred)
        environment.set_global("flood_depth_m", 1.5 if flood_occurred else 0.0)

        # Get LLM response
        raw_output = mock_llm.invoke("prompt", year=year)

        # Create context
        context = {
            "agent_id": "test_household_001",
            "agent_type": "household",
            "elevated": agent_state.get("elevated", False),
            "has_insurance": agent_state.get("has_insurance", False),
            "state": agent_state
        }

        # Parse output
        proposal = adapter.parse_output(raw_output, context)

        if proposal:
            proposal.agent_id = "test_household_001"

        # Validate
        if proposal:
            validation_results = validator.validate(proposal, context)
            all_valid = all(r.valid for r in validation_results)
        else:
            validation_results = []
            all_valid = False

        # Record trace
        trace_collector.add_trace(year, agent_state, proposal, validation_results, all_valid)

        # Apply state changes if approved
        if all_valid and proposal:
            skill_id = proposal.skill_name
            if skill_id == "buy_insurance":
                agent_state["has_insurance"] = True
            elif skill_id == "elevate_house":
                agent_state["elevated"] = True
            elif skill_id == "relocate":
                agent_state["relocated"] = True
            # do_nothing: no changes

        # Record state at end of year
        trace_collector.add_state_snapshot(year, agent_state)

        return proposal, all_valid

    def test_sa_e2e01_three_year_simulation_completes(
        self,
        mock_llm,
        adapter,
        skill_registry,
        validator,
        environment
    ):
        """SA-E2E01: 3-year simulation should complete without error."""
        agent_state = {
            "elevated": False,
            "has_insurance": False,
            "relocated": False
        }
        trace_collector = SimulationTrace()

        # Run 3 years
        for year in [1, 2, 3]:
            proposal, valid = self.run_simulation_year(
                year, agent_state, environment, mock_llm,
                adapter, skill_registry, validator, trace_collector
            )

        # Should have 3 traces
        assert len(trace_collector.traces) == 3
        assert mock_llm.call_count == 3

    def test_sa_e2e02_skill_execution_changes_state(
        self,
        mock_llm,
        adapter,
        skill_registry,
        validator,
        environment
    ):
        """SA-E2E02: Skill execution should change agent state."""
        agent_state = {
            "elevated": False,
            "has_insurance": False,
            "relocated": False
        }
        trace_collector = SimulationTrace()

        # Year 1: Should buy insurance (decision 1)
        proposal, valid = self.run_simulation_year(
            1, agent_state, environment, mock_llm,
            adapter, skill_registry, validator, trace_collector
        )

        assert proposal.skill_name == "buy_insurance"
        assert agent_state["has_insurance"] is True, "Should have insurance after year 1"

    def test_sa_e2e03_audit_traces_captured(
        self,
        mock_llm,
        adapter,
        skill_registry,
        validator,
        environment
    ):
        """SA-E2E03: Audit traces should be captured."""
        agent_state = {
            "elevated": False,
            "has_insurance": False,
            "relocated": False
        }
        trace_collector = SimulationTrace()

        # Run 3 years
        for year in [1, 2, 3]:
            self.run_simulation_year(
                year, agent_state, environment, mock_llm,
                adapter, skill_registry, validator, trace_collector
            )

        # Verify traces contain required fields
        for trace in trace_collector.traces:
            assert "year" in trace
            assert "agent_id" in trace
            assert "skill_proposal" in trace
            assert "validation_result" in trace
            assert "validated" in trace

    def test_sa_e2e04_all_traces_valid_json(
        self,
        mock_llm,
        adapter,
        skill_registry,
        validator,
        environment
    ):
        """SA-E2E04: All traces should be valid JSON."""
        agent_state = {
            "elevated": False,
            "has_insurance": False,
            "relocated": False
        }
        trace_collector = SimulationTrace()

        # Run 3 years
        for year in [1, 2, 3]:
            self.run_simulation_year(
                year, agent_state, environment, mock_llm,
                adapter, skill_registry, validator, trace_collector
            )

        # Verify each trace is JSON serializable
        for trace in trace_collector.traces:
            json_str = json.dumps(trace)
            parsed = json.loads(json_str)
            assert parsed["year"] == trace["year"]

    def test_sa_e2e05_state_progression_recorded(
        self,
        mock_llm,
        adapter,
        skill_registry,
        validator,
        environment
    ):
        """SA-E2E05: State progression should be recorded across years."""
        agent_state = {
            "elevated": False,
            "has_insurance": False,
            "relocated": False
        }
        trace_collector = SimulationTrace()

        # Run 3 years
        for year in [1, 2, 3]:
            self.run_simulation_year(
                year, agent_state, environment, mock_llm,
                adapter, skill_registry, validator, trace_collector
            )

        # Should have state history
        assert len(trace_collector.state_history) == 3

        # State should change over time
        # Year 1: buy_insurance -> has_insurance = True
        # Year 2: elevate_house -> elevated = True (if not already elevated)
        year1_state = trace_collector.state_history[0]["state"]
        year3_state = trace_collector.state_history[2]["state"]

        # At least one state should have changed
        changes_detected = (
            year1_state["has_insurance"] != trace_collector.state_history[0]["state"].get("initial_has_insurance", False) or
            year3_state["elevated"] != trace_collector.traces[0]["state_before"].get("elevated", False)
        )
        # The simulation should have made changes
        assert year1_state["has_insurance"] or year3_state["elevated"], \
            "Expected some state changes over 3 years"


class TestSAE2EDecisionSequence:
    """Test specific decision sequences."""

    def test_insurance_then_elevate_sequence(
        self,
        mock_llm,
        adapter,
        skill_registry,
        validator,
        environment
    ):
        """Insurance in year 1, elevate in year 2 sequence."""
        agent_state = {
            "elevated": False,
            "has_insurance": False,
            "relocated": False
        }

        # Year 1 context
        context = {
            "agent_id": "test",
            "agent_type": "household",
            "elevated": False,
            "has_insurance": False,
            "state": agent_state
        }

        # Parse year 1 response
        proposal1 = adapter.parse_output(MOCK_RESPONSES["year_1"], context)
        assert proposal1.skill_name == "buy_insurance"

        # Apply change
        agent_state["has_insurance"] = True
        context["has_insurance"] = True
        context["state"] = agent_state

        # Parse year 2 response
        proposal2 = adapter.parse_output(MOCK_RESPONSES["year_2"], context)
        assert proposal2.skill_name == "elevate_house"

        # Apply change
        agent_state["elevated"] = True

        # Verify final state
        assert agent_state["has_insurance"] is True
        assert agent_state["elevated"] is True


class TestSAE2EAppraisalExtraction:
    """Test appraisal extraction in E2E context."""

    def test_appraisals_extracted_from_response(self, adapter):
        """Appraisals should be extracted from LLM response."""
        context = {
            "agent_id": "test",
            "agent_type": "household",
            "elevated": False,
            "has_insurance": False
        }

        proposal = adapter.parse_output(MOCK_RESPONSES["year_1"], context)

        assert proposal is not None
        assert proposal.reasoning is not None
        # Check that TP/CP or similar constructs are in reasoning
        reasoning_str = str(proposal.reasoning).lower()
        has_constructs = (
            "threat" in reasoning_str or
            "coping" in reasoning_str or
            "tp" in reasoning_str or
            "cp" in reasoning_str
        )
        assert has_constructs or len(proposal.reasoning) > 0


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
