"""Tests for MA Reflection Integration (Task-057D)."""
import pytest
from unittest.mock import MagicMock, call

from broker.components.engines.humancentric_engine import HumanCentricMemoryEngine
from examples.multi_agent.flood.orchestration.lifecycle_hooks import MultiAgentHooks
from broker.interfaces.coordination import ActionResolution, AgentMessage
from broker.components.memory_bridge import MemoryBridge # Import MemoryBridge for context


@pytest.fixture
def mock_memory_engine():
    # Mock HumanCentricMemoryEngine to control its behavior during tests
    engine = MagicMock(spec=HumanCentricMemoryEngine)
    engine.add_memory = MagicMock()
    # Mock retrieve_stratified method as it's crucial for reflection
    engine.retrieve_stratified = MagicMock()
    return engine

@pytest.fixture
def mock_game_master():
    # Mock GameMaster to provide resolution data if needed for reflection context
    gm = MagicMock()
    gm.get_resolution = MagicMock()
    return gm

@pytest.fixture
def mock_message_pool():
    # Mock MessagePool to provide unread messages if needed for reflection context
    mp = MagicMock()
    mp.get_unread = MagicMock()
    return mp

@pytest.fixture
def mock_hooks(mock_memory_engine, mock_game_master, mock_message_pool):
    """Fixture to create a MultiAgentHooks instance with mocked dependencies."""
    # Mock environment and other required parameters
    mock_env = {"year": 5}
    mock_agents = {
        "H_001": MagicMock(id="H_001", agent_type="household_owner",
                           dynamic_state={"years_since_flood": 0, "relocated": False}),
        "GOV_001": MagicMock(id="GOV_001", agent_type="government", dynamic_state={}),
    }
    
    hooks = MultiAgentHooks(
        environment=mock_env,
        memory_engine=mock_memory_engine,
        game_master=mock_game_master,
        message_pool=mock_message_pool,
        # Add other required parameters with default/mock values
        hazard_module=MagicMock(),
        media_hub=MagicMock(),
        per_agent_depth=False,
        year_mapping=MagicMock()
    )
    
    # Set the mock memory bridge if it's initialized
    if hasattr(hooks, '_memory_bridge') and hooks._memory_bridge:
        hooks._memory_bridge.memory_engine = mock_memory_engine # Ensure bridge uses the mocked engine
    
    return hooks, mock_memory_engine, mock_game_master, mock_message_pool, mock_agents

class TestMAReflectionIntegration:
    def test_run_ma_reflection_called_in_post_year(self, mock_hooks, mock_memory_engine):
        hooks, mem_engine, gm, mp, agents = mock_hooks

        # Mock retrieve_stratified to return some memories
        stratified_memories = [
            "Personal: Experienced heavy rain last year.",
            "Neighbor: Neighbor elevated their house.",
            "Community: Policy change regarding subsidies.",
            "Reflection: Last year's flood was a wake-up call."
        ]
        mem_engine.retrieve_stratified.return_value = stratified_memories

        # Call post_year which should trigger reflection
        hooks.post_year(year=6, agents=agents, memory_engine=mem_engine)

        # Verify that retrieve_stratified was called
        mem_engine.retrieve_stratified.assert_called_once()
        
        # Verify add_memory was called:
        #   1) no-flood memory (since community_depth_ft=0, agent not actually flooded)
        #   2) reflection memory
        assert mem_engine.add_memory.call_count >= 1
        # Find the reflection call (has "type": "reflection" in metadata)
        reflection_calls = [
            c for c in mem_engine.add_memory.call_args_list
            if c.kwargs.get("metadata", {}).get("type") == "reflection"
               or (len(c.args) > 1 and "Consolidated Reflection" in str(c.args[1]))
        ]
        assert len(reflection_calls) == 1, f"Expected 1 reflection call, got {len(reflection_calls)}"
        call_args, call_kwargs = reflection_calls[0]

        added_memory_content = call_args[1]
        added_memory_metadata = call_kwargs["metadata"]

        assert "Year 6:" in added_memory_content # Check for year prefix
        assert "Consolidated Reflection:" in added_memory_content # Check for generated reflection content
        assert added_memory_metadata["type"] == "reflection"
        assert added_memory_metadata["source"] == "personal" # Assuming reflection defaults to personal
        assert added_memory_metadata["emotion"] == "major" # Based on reflection's importance
        assert added_memory_metadata["importance"] > 0.5 # Reflection should have notable importance


    def test_reflection_uses_stratified_retrieval_params(self, mock_hooks, mock_memory_engine):
        hooks, mem_engine, gm, mp, agents = mock_hooks
        
        # Define custom allocation for testing
        custom_allocation = {"personal": 1, "neighbor": 1, "reflection": 3}
        total_k = 5

        hooks.post_year(year=7, agents=agents, memory_engine=mem_engine)

        # Verify retrieve_stratified was called with correct parameters
        mem_engine.retrieve_stratified.assert_called_once_with(
            pytest.approx(agents["H_001"].id), # Agent ID
            allocation=custom_allocation,
            total_k=total_k,
            contextual_boosters={"emotion:fear": 1.5} # From env if flood occurred
        )
        
    def test_reflection_logic_skips_if_no_flood(self, mock_hooks, mock_memory_engine):
        hooks, mem_engine, gm, mp, agents = mock_hooks
        hooks.env["flood_occurred"] = False # Ensure no flood

        hooks.post_year(year=8, agents=agents, memory_engine=mem_engine)

        # Reflection should not be triggered if no flood occurred (and year 8 % 5 != 0)
        mem_engine.retrieve_stratified.assert_not_called()
        # No-flood memories ARE expected (memory-mediated TP decline),
        # but no reflection memories should be added.
        reflection_calls = [
            c for c in mem_engine.add_memory.call_args_list
            if c.kwargs.get("metadata", {}).get("type") == "reflection"
        ]
        assert len(reflection_calls) == 0, "No reflection should be triggered without flood"

