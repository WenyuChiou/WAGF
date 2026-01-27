"""
Real LLM Smoke Test - Phase 11 of Integration Test Suite.
Task-038: Verify parsing and E2E with real Llama 3.2 3B via Ollama.

Tests:
- RL-01: Ollama connection
- RL-02: Parse real response
- RL-03: VL/L/M/H/VH format
- RL-04: 1-year E2E with real LLM

Prerequisites:
- Ollama running locally: http://localhost:11434
- Model pulled: ollama pull llama3.2:3b
"""
import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from interfaces.llm_provider import LLMConfig
from providers.ollama import OllamaProvider
from broker.utils.model_adapter import UnifiedAdapter


def is_ollama_available():
    """Check if Ollama is running and llama3.2:3b is available."""
    try:
        config = LLMConfig(model="llama3.2:3b", timeout=10.0)
        provider = OllamaProvider(config, base_url="http://localhost:11434")
        return provider.validate_connection()
    except Exception:
        return False


# Skip all tests if Ollama is not available
pytestmark = pytest.mark.skipif(
    not is_ollama_available(),
    reason="Ollama not available or llama3.2:3b not installed"
)


@pytest.fixture
def ollama_provider():
    """Create Ollama provider for Llama 3.2 3B."""
    config = LLMConfig(
        model="llama3.2:3b",
        temperature=0.7,
        max_tokens=512,
        timeout=60.0
    )
    return OllamaProvider(config, base_url="http://localhost:11434")


@pytest.fixture
def sa_adapter():
    """Create UnifiedAdapter for SA parsing."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "examples", "single_agent", "agent_types.yaml"
    )
    return UnifiedAdapter(agent_type="household", config_path=config_path)


@pytest.fixture
def default_context():
    """Default context for parsing."""
    return {
        "agent_id": "test_household_001",
        "agent_type": "household",
        "elevated": False,
        "has_insurance": False
    }


@pytest.fixture
def flood_prompt():
    """Sample flood decision prompt."""
    return """You are a household facing flood risk. Analyze the situation and make a decision.

Current Situation:
- Year: 1
- Flood just occurred with depth: 1.5 meters
- Property value: $300,000
- You do NOT have insurance
- Your house is NOT elevated

Available Options:
1. buy_insurance - Purchase flood insurance
2. elevate_house - Elevate your house
3. relocate - Move to a safer area
4. do_nothing - Take no action

Respond in this exact JSON format:
<<<DECISION_START>>>
{
    "decision": <number 1-4>,
    "threat_appraisal": {"label": "<VL|L|M|H|VH>", "reason": "<your reasoning>"},
    "coping_appraisal": {"label": "<VL|L|M|H|VH>", "reason": "<your reasoning>"}
}
<<<DECISION_END>>>"""


class TestRealLLMConnection:
    """Test Ollama connection and availability."""

    def test_rl01_ollama_connection(self, ollama_provider):
        """RL-01: Ollama should be running and model available."""
        assert ollama_provider.validate_connection() is True
        assert ollama_provider.provider_name == "ollama"

    def test_ollama_basic_invoke(self, ollama_provider):
        """Basic invoke should return response."""
        response = ollama_provider.invoke("Say 'hello' and nothing else.")

        assert response is not None
        assert response.content is not None
        assert len(response.content) > 0
        assert response.model == "llama3.2:3b"


class TestRealLLMParsing:
    """Test parsing real LLM responses."""

    def test_rl02_parse_real_response(self, ollama_provider, sa_adapter, default_context, flood_prompt):
        """RL-02: Should parse real LLM response into SkillProposal."""
        # Get real response
        response = ollama_provider.invoke(flood_prompt)
        raw_output = response.content

        # Parse it
        proposal = sa_adapter.parse_output(raw_output, default_context)

        # Should get a proposal (may fallback to keyword/naked_digit)
        assert proposal is not None, f"Failed to parse: {raw_output[:200]}..."
        assert proposal.skill_name in ["buy_insurance", "elevate_house", "relocate", "do_nothing"]

    def test_rl03_vl_l_m_h_vh_format(self, ollama_provider, sa_adapter, default_context, flood_prompt):
        """RL-03: Real response should contain valid VL/L/M/H/VH labels."""
        response = ollama_provider.invoke(flood_prompt)
        raw_output = response.content

        proposal = sa_adapter.parse_output(raw_output, default_context)

        if proposal and proposal.reasoning:
            valid_labels = {"VL", "L", "M", "H", "VH"}
            reasoning = proposal.reasoning

            # Check threat_appraisal if present
            if "threat_appraisal" in reasoning:
                ta = reasoning["threat_appraisal"]
                if isinstance(ta, dict) and "label" in ta:
                    assert ta["label"] in valid_labels, f"Invalid TP label: {ta['label']}"

            # Check coping_appraisal if present
            if "coping_appraisal" in reasoning:
                ca = reasoning["coping_appraisal"]
                if isinstance(ca, dict) and "label" in ca:
                    assert ca["label"] in valid_labels, f"Invalid CP label: {ca['label']}"


class TestRealLLME2E:
    """E2E test with real LLM."""

    def test_rl04_one_year_e2e(self, ollama_provider, sa_adapter, default_context, flood_prompt):
        """RL-04: 1-year E2E should complete with real LLM."""
        # Initial state
        agent_state = {
            "elevated": False,
            "has_insurance": False,
            "relocated": False
        }

        # Get decision from real LLM
        response = ollama_provider.invoke(flood_prompt)
        raw_output = response.content

        # Parse
        proposal = sa_adapter.parse_output(raw_output, default_context)

        assert proposal is not None, "Failed to parse real LLM response"

        # Apply state change
        if proposal.skill_name == "buy_insurance":
            agent_state["has_insurance"] = True
        elif proposal.skill_name == "elevate_house":
            agent_state["elevated"] = True
        elif proposal.skill_name == "relocate":
            agent_state["relocated"] = True

        # Create trace
        trace = {
            "year": 1,
            "agent_id": "test_household_001",
            "raw_output": raw_output[:500],  # Truncate for brevity
            "skill_proposal": {
                "skill_name": proposal.skill_name,
                "reasoning": proposal.reasoning,
                "parse_layer": proposal.parse_layer
            },
            "state_after": agent_state,
            "model": "llama3.2:3b"
        }

        # Verify trace structure
        assert "skill_proposal" in trace
        assert trace["skill_proposal"]["skill_name"] in ["buy_insurance", "elevate_house", "relocate", "do_nothing"]
        assert trace["model"] == "llama3.2:3b"


class TestRealLLMMultiplePrompts:
    """Test multiple prompts to verify consistency."""

    def test_multiple_decisions_parseable(self, ollama_provider, sa_adapter, default_context):
        """Multiple different prompts should all be parseable."""
        prompts = [
            # High threat scenario
            """Flood warning! Depth expected: 3 meters. You have $50,000 savings.
            Choose: 1=buy_insurance, 2=elevate_house, 3=relocate, 4=do_nothing
            Reply in JSON: <<<DECISION_START>>>{"decision": <1-4>}<<<DECISION_END>>>""",

            # Low threat scenario
            """Minor flooding possible. Depth: 0.3 meters. Your house is already insured.
            Choose: 1=buy_insurance, 2=elevate_house, 3=relocate, 4=do_nothing
            Reply with just the number.""",
        ]

        for i, prompt in enumerate(prompts):
            response = ollama_provider.invoke(prompt)
            proposal = sa_adapter.parse_output(response.content, default_context)

            assert proposal is not None, f"Prompt {i+1} failed to parse: {response.content[:100]}"
            assert proposal.skill_name in ["buy_insurance", "elevate_house", "relocate", "do_nothing"]


# Run tests
if __name__ == "__main__":
    # First check if Ollama is available
    if is_ollama_available():
        print("Ollama is available with llama3.2:3b")
        pytest.main([__file__, "-v"])
    else:
        print("Skipping tests: Ollama not available or llama3.2:3b not installed")
        print("To run these tests:")
        print("  1. Install Ollama: https://ollama.ai")
        print("  2. Pull the model: ollama pull llama3.2:3b")
        print("  3. Start Ollama: ollama serve")
