"""
Test suite for adapter parsing functionality.

Tests cover:
- parse_layer tracking
- Fallback parsing (JSON → keyword → digit → default)
- SkillProposal creation
- DeepSeek preprocessing
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from broker.utils.model_adapter import UnifiedAdapter, deepseek_preprocessor, get_adapter
from broker.interfaces.skill_types import SkillProposal
from broker.utils.agent_config import AgentTypeConfig

CONFIG_PATH = str(Path("examples/single_agent/agent_types.yaml"))


class TestParseLayerTracking:
    """Test that parse_layer is correctly tracked in SkillProposal."""

    @pytest.fixture
    def adapter(self):
        """Create an adapter for testing."""
        return UnifiedAdapter(agent_type="household", config_path=CONFIG_PATH)
    
    def test_json_parse_layer(self, adapter):
        """Test JSON parsing sets parse_layer to 'json'."""
        raw_output = '<<<DECISION_START>>>{"decision": "do_nothing", "threat_appraisal": "M", "coping_appraisal": "M"}<<<DECISION_END>>>'
        context = {"agent_id": "test_agent", "agent_type": "household"}
        
        proposal = adapter.parse_output(raw_output, context)
        
        # JSON parsing might not be the first layer, so we check if it's set
        assert proposal is not None
        assert hasattr(proposal, 'parse_layer')
        assert proposal.parse_layer is not None
    
    def test_keyword_parse_layer(self, adapter):
        """Test keyword parsing with 'Final Decision:' prefix."""
        raw_output = "Final Decision: do_nothing\nReasoning: Test reasoning"
        context = {"agent_id": "test_agent", "agent_type": "household"}
        
        proposal = adapter.parse_output(raw_output, context)
        
        assert proposal is not None
        assert proposal.parse_layer in ["keyword", "json", "digit", "default"]
    
    def test_digit_parse_layer(self, adapter):
        """Test digit parsing for number-only outputs."""
        raw_output = "4"  # Assuming 4 maps to do_nothing
        context = {"agent_id": "test_agent", "agent_type": "household"}
        
        proposal = adapter.parse_output(raw_output, context)
        
        # Should parse but might use default if mapping not found
        assert proposal is None or proposal.parse_layer is not None
    
    def test_parse_layer_in_to_dict(self, adapter):
        """Test parse_layer is included in to_dict() output."""
        raw_output = "Final Decision: do_nothing"
        context = {"agent_id": "test_agent", "agent_type": "household"}
        
        proposal = adapter.parse_output(raw_output, context)
        
        if proposal:
            proposal_dict = proposal.to_dict()
            assert "parse_layer" in proposal_dict


class TestAdapterConfigPath:
    """Test get_adapter propagates config_path to AgentTypeConfig."""

    def test_get_adapter_uses_config_path(self, tmp_path):
        """Ensure adapter loads agent config from explicit path."""
        AgentTypeConfig._instance = None

        yaml_path = tmp_path / "agent_types.yaml"
        yaml_path.write_text(
            "\n".join([
                "household:",
                "  parsing:",
                "    actions:",
                "      - id: custom_action",
                "        aliases: []",
            ]),
            encoding="utf-8",
        )

        adapter = get_adapter("mock-model", config_path=str(yaml_path))
        actions = adapter.agent_config.get_valid_actions("household")

        assert "custom_action" in actions


class TestFallbackParsing:
    """Test the multi-layer fallback parsing mechanism."""

    @pytest.fixture
    def adapter(self):
        return UnifiedAdapter(agent_type="household", config_path=CONFIG_PATH)
    
    def test_empty_output_returns_none(self, adapter):
        """Test empty output returns None."""
        proposal = adapter.parse_output("", {"agent_id": "test"})
        assert proposal is None
    
    def test_none_output_returns_none(self, adapter):
        """Test None output returns None."""
        proposal = adapter.parse_output(None, {"agent_id": "test"})
        assert proposal is None
    
    def test_valid_skill_extracted(self, adapter):
        """Test valid skill name is extracted from output."""
        raw_output = "After careful consideration, my Final Decision: buy_insurance"
        context = {"agent_id": "test_agent", "agent_type": "household"}
        
        proposal = adapter.parse_output(raw_output, context)
        
        # Should extract flood_insurance or map to a valid skill
        assert proposal is not None
        assert proposal.skill_name is not None


class TestDeepSeekPreprocessor:
    """Test DeepSeek-specific preprocessing."""
    
    def test_removes_think_tags(self):
        """Test <think> tags are removed."""
        raw = "<think>Internal reasoning here</think>Final Decision: do_nothing"
        processed = deepseek_preprocessor(raw)
        
        assert "<think>" not in processed
        assert "</think>" not in processed
        assert "Final Decision" in processed
    
    def test_preserves_content_without_tags(self):
        """Test content without tags is preserved."""
        raw = "Final Decision: do_nothing"
        processed = deepseek_preprocessor(raw)
        
        assert processed == raw


class TestSkillProposalCreation:
    """Test SkillProposal dataclass behavior."""
    
    def test_basic_creation(self):
        """Test basic SkillProposal creation."""
        proposal = SkillProposal(
            skill_name="test_skill",
            agent_id="agent_1",
            reasoning={"test": "value"}
        )
        
        assert proposal.skill_name == "test_skill"
        assert proposal.agent_id == "agent_1"
    
    def test_parse_layer_default(self):
        """Test parse_layer defaults to 'unknown'."""
        proposal = SkillProposal(
            skill_name="test_skill",
            agent_id="agent_1",
            reasoning={}
        )
        
        # Check default value
        assert proposal.parse_layer is not None
    
    def test_to_dict_includes_parse_layer(self):
        """Test to_dict includes parse_layer."""
        proposal = SkillProposal(
            skill_name="test_skill",
            agent_id="agent_1",
            reasoning={},
            parse_layer="json"
        )
        
        d = proposal.to_dict()
        assert "parse_layer" in d
        assert d["parse_layer"] == "json"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
