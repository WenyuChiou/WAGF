"""
Test suite for broker core functionality.

Tests cover:
- SkillBrokerEngine initialization
- process_step with both legacy (str) and new (tuple) llm_invoke
- Validator import paths
- Stats collection
"""
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

# Import core components
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.components.skill_registry import SkillRegistry
from broker.utils.model_adapter import UnifiedAdapter
from broker.validators import AgentValidator
from broker.utils.llm_utils import LLMStats


class MockSimulationEngine:
    """Mock simulation engine for testing."""
    def execute_skill(self, approved_skill):
        from broker.interfaces.skill_types import ExecutionResult
        return ExecutionResult(success=True, state_changes={"test": True})


class MockContextBuilder:
    """Mock context builder for testing."""
    def build(self, agent_id, env_context=None, **kwargs):
        return {
            "agent_id": agent_id,
            "personal": {"memory": []},
            "environment": {}
        }
    
    def format_prompt(self, context):
        return f"Mock prompt for {context.get('agent_id', 'unknown')}"


class TestSkillBrokerEngineInit:
    """Test SkillBrokerEngine initialization."""
    
    @patch("broker.core.skill_broker_engine.load_agent_config")
    def test_basic_init(self, mock_load):
        """Test basic broker initialization."""
        mock_load.return_value = MagicMock()
        registry = SkillRegistry()
        adapter = MagicMock()
        validators = []
        sim_engine = MockSimulationEngine()
        ctx_builder = MockContextBuilder()
        
        broker = SkillBrokerEngine(
            skill_registry=registry,
            model_adapter=adapter,
            validators=validators,
            simulation_engine=sim_engine,
            context_builder=ctx_builder
        )
        
        assert broker.skill_registry is registry
        assert broker.model_adapter is adapter
        assert broker.stats["total"] == 0
    
    @patch("broker.core.skill_broker_engine.load_agent_config")
    def test_stats_tracking(self, mock_load):
        """Test that broker tracks stats correctly."""
        mock_load.return_value = MagicMock()
        broker = SkillBrokerEngine(
            skill_registry=SkillRegistry(),
            model_adapter=MagicMock(),
            validators=[],
            simulation_engine=MockSimulationEngine(),
            context_builder=MockContextBuilder()
        )
        
        assert "total" in broker.stats
        assert "approved" in broker.stats
        assert "rejected" in broker.stats
        assert "aborted" in broker.stats


class TestProcessStepLLMInvokeAPI:
    """Test process_step handles both legacy and new llm_invoke APIs."""
    
    @pytest.fixture
    def broker(self):
        """Create a broker for testing."""
        from broker.interfaces.skill_types import SkillDefinition
        registry = SkillRegistry()
        registry.register(SkillDefinition(
            skill_id="do_nothing", 
            description="Default",
            eligible_agent_types=["*"],
            preconditions=[],
            institutional_constraints={},
            allowed_state_changes=[],
            implementation_mapping="do_nothing"
        ))
        
        adapter = MagicMock()
        # Mock parse_output to return a valid proposal
        from broker.interfaces.skill_types import SkillProposal
        adapter.parse_output.return_value = SkillProposal(
            skill_name="do_nothing",
            agent_id="test_agent",
            reasoning={"test": "value"},
            parse_layer="mock"
        )
        adapter.format_retry_prompt.return_value = "retry prompt"
        
        validator = MagicMock()
        from broker.interfaces.skill_types import ValidationResult
        validator.validate.return_value = ValidationResult(
            valid=True, 
            validator_name="test_validator",
            errors=[], 
            metadata={}
        )
        
        mock_config = MagicMock()
        mock_config.get_log_fields.return_value = ["test"]
        
        return SkillBrokerEngine(
            skill_registry=registry,
            model_adapter=adapter,
            validators=[validator],
            simulation_engine=MockSimulationEngine(),
            context_builder=MockContextBuilder(),
            config=mock_config
        )
    
    def test_legacy_string_return(self, broker):
        """Test llm_invoke returning a string (legacy API)."""
        def legacy_invoke(prompt: str) -> str:
            return "Final Decision: do_nothing"
        
        result = broker.process_step(
            agent_id="test_agent",
            step_id=1,
            run_id="test_run",
            seed=42,
            llm_invoke=legacy_invoke,
            agent_type="default"
        )
        
        assert result.skill_proposal is not None
        assert result.skill_proposal.skill_name == "do_nothing"
    
    def test_tuple_return(self, broker):
        """Test llm_invoke returning a (content, stats) tuple (new API)."""
        def tuple_invoke(prompt: str):
            return ("Final Decision: do_nothing", LLMStats(retries=1, success=True))
        
        result = broker.process_step(
            agent_id="test_agent",
            step_id=1,
            run_id="test_run",
            seed=42,
            llm_invoke=tuple_invoke,
            agent_type="default"
        )
        
        assert result.skill_proposal is not None
        assert result.skill_proposal.skill_name == "do_nothing"


class TestValidatorImport:
    """Test that validator can be imported from broker namespace."""
    
    def test_import_from_broker_validators(self):
        """Test import from broker.validators."""
        from broker.validators import AgentValidator
        assert AgentValidator is not None
    
    def test_import_from_broker_root(self):
        """Test import from broker root."""
        from broker import AgentValidator
        assert AgentValidator is not None


class TestOutputSchemaValidation:
    """Test that validate_output_schema is called in _run_validators."""

    @pytest.fixture
    def broker_with_schema(self):
        """Create a broker with a skill that has output_schema."""
        from broker.interfaces.skill_types import SkillDefinition
        registry = SkillRegistry()
        registry.register(SkillDefinition(
            skill_id="increase_demand",
            description="Request more water",
            eligible_agent_types=["*"],
            preconditions=[],
            institutional_constraints={},
            allowed_state_changes=["request"],
            implementation_mapping="env.execute_skill",
            output_schema={
                "type": "object",
                "required": ["decision"],
                "properties": {
                    "decision": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                    "magnitude_pct": {"type": "number", "minimum": 1, "maximum": 30},
                },
            },
        ))
        registry.register(SkillDefinition(
            skill_id="do_nothing",
            description="Default",
            eligible_agent_types=["*"],
            preconditions=[],
            institutional_constraints={},
            allowed_state_changes=[],
            implementation_mapping="do_nothing",
        ))

        adapter = MagicMock()
        from broker.interfaces.skill_types import SkillProposal
        adapter.parse_output.return_value = SkillProposal(
            skill_name="increase_demand",
            agent_id="test_agent",
            reasoning={"test": "value"},
            parse_layer="mock",
            magnitude_pct=50.0,  # Out of range: max is 30
        )
        adapter.format_retry_prompt.return_value = "retry prompt"

        mock_config = MagicMock()
        mock_config.get_log_fields.return_value = []

        return SkillBrokerEngine(
            skill_registry=registry,
            model_adapter=adapter,
            validators=[],
            simulation_engine=MockSimulationEngine(),
            context_builder=MockContextBuilder(),
            config=mock_config,
            max_retries=0,  # No retries — just check initial validation
        )

    def test_out_of_range_magnitude_triggers_schema_error(self, broker_with_schema):
        """magnitude_pct=50 exceeds schema max=30 → validation error."""
        from broker.interfaces.skill_types import SkillProposal, ValidationResult
        proposal = SkillProposal(
            skill_name="increase_demand",
            agent_id="test",
            reasoning={},
            magnitude_pct=50.0,
        )
        context = {
            "agent_state": {
                "personal": {
                    "dynamic_skill_map": {"1": "increase_demand"},
                },
                "state": {},
            },
        }
        results = broker_with_schema._run_validators(proposal, context)
        schema_results = [r for r in results if r.validator_name == "SkillRegistry.output_schema"]
        assert len(schema_results) == 1
        assert not schema_results[0].valid
        assert any("maximum" in e for e in schema_results[0].errors)

    def test_valid_magnitude_passes_schema(self, broker_with_schema):
        """magnitude_pct=15 within schema range → no error."""
        from broker.interfaces.skill_types import SkillProposal
        proposal = SkillProposal(
            skill_name="increase_demand",
            agent_id="test",
            reasoning={},
            magnitude_pct=15.0,
        )
        context = {
            "agent_state": {
                "personal": {
                    "dynamic_skill_map": {"1": "increase_demand"},
                },
                "state": {},
            },
        }
        results = broker_with_schema._run_validators(proposal, context)
        schema_results = [r for r in results if r.validator_name == "SkillRegistry.output_schema"]
        assert len(schema_results) == 1
        assert schema_results[0].valid

    def test_no_schema_skill_passes(self, broker_with_schema):
        """Skill without output_schema → valid=True."""
        from broker.interfaces.skill_types import SkillProposal
        proposal = SkillProposal(
            skill_name="do_nothing",
            agent_id="test",
            reasoning={},
        )
        context = {"agent_state": {"personal": {}, "state": {}}}
        results = broker_with_schema._run_validators(proposal, context)
        schema_results = [r for r in results if r.validator_name == "SkillRegistry.output_schema"]
        assert len(schema_results) == 1
        assert schema_results[0].valid

    def test_nonexistent_skill_skips_schema(self, broker_with_schema):
        """Proposal with unregistered skill_name → no schema result."""
        from broker.interfaces.skill_types import SkillProposal
        proposal = SkillProposal(
            skill_name="nonexistent_skill",
            agent_id="test",
            reasoning={},
        )
        context = {"agent_state": {"personal": {}, "state": {}}}
        results = broker_with_schema._run_validators(proposal, context)
        schema_results = [r for r in results if r.validator_name == "SkillRegistry.output_schema"]
        assert len(schema_results) == 0  # Skipped because skill not in registry

    def test_missing_dynamic_skill_map_fails_required_decision(self, broker_with_schema):
        """Schema requires 'decision' but no dynamic_skill_map → missing field error."""
        from broker.interfaces.skill_types import SkillProposal
        proposal = SkillProposal(
            skill_name="increase_demand",
            agent_id="test",
            reasoning={},
            magnitude_pct=15.0,
        )
        context = {"agent_state": {"personal": {}, "state": {}}}
        results = broker_with_schema._run_validators(proposal, context)
        schema_results = [r for r in results if r.validator_name == "SkillRegistry.output_schema"]
        assert len(schema_results) == 1
        assert not schema_results[0].valid
        assert any("decision" in e for e in schema_results[0].errors)

    def test_invalid_decision_enum_value(self, broker_with_schema):
        """Decision=99 not in enum [1,2,3,4,5] → schema error."""
        from broker.interfaces.skill_types import SkillProposal
        proposal = SkillProposal(
            skill_name="increase_demand",
            agent_id="test",
            reasoning={},
            magnitude_pct=15.0,
        )
        context = {
            "agent_state": {
                "personal": {"dynamic_skill_map": {"99": "increase_demand"}},
                "state": {},
            },
        }
        results = broker_with_schema._run_validators(proposal, context)
        schema_results = [r for r in results if r.validator_name == "SkillRegistry.output_schema"]
        assert len(schema_results) == 1
        assert not schema_results[0].valid
        assert any("allowed values" in e for e in schema_results[0].errors)

    def test_none_agent_state_no_crash(self, broker_with_schema):
        """None agent_state in context should not crash."""
        from broker.interfaces.skill_types import SkillProposal
        proposal = SkillProposal(
            skill_name="increase_demand",
            agent_id="test",
            reasoning={},
            magnitude_pct=15.0,
        )
        context = {"agent_state": None}
        results = broker_with_schema._run_validators(proposal, context)
        assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
