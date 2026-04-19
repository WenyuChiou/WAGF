"""Tests for MA Reflection Integration (Task-057D)."""
import pytest
from unittest.mock import MagicMock, call

from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from examples.multi_agent.flood.orchestration.lifecycle_hooks import MultiAgentHooks
from broker.interfaces.coordination import ActionResolution, AgentMessage
from broker.components.memory.bridge import MemoryBridge # Import MemoryBridge for context


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
    """Fixture to create a MultiAgentHooks instance with mocked dependencies.

    reflection_config is explicit so tests do not depend on the default
    ``interval=1`` fallback, which would make every year fire reflection.
    Tests that need a no-flood-no-reflection path (e.g. skip-if-no-flood)
    override ``hooks._reflection_config`` locally.
    """
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
        hazard_module=MagicMock(),
        media_hub=MagicMock(),
        per_agent_depth=False,
        year_mapping=MagicMock(),
        reflection_config={
            "interval": 5,
            "triggers": {"crisis": True, "periodic_interval": 5},
        },
    )

    if hasattr(hooks, '_memory_bridge') and hooks._memory_bridge:
        hooks._memory_bridge.memory_engine = mock_memory_engine

    return hooks, mock_memory_engine, mock_game_master, mock_message_pool, mock_agents

class TestMAReflectionIntegration:
    def test_run_ma_reflection_called_in_post_year(self, mock_hooks, mock_memory_engine):
        hooks, mem_engine, gm, mp, agents = mock_hooks

        # Crisis flag without depth drives reflection but avoids the damage
        # loop that would otherwise require flood-damage fields on the mock.
        hooks.env["flood_occurred"] = True
        hooks.env["flood_depth_ft"] = 0.0

        stratified_memories = [
            "Personal: Experienced heavy rain last year.",
            "Neighbor: Neighbor elevated their house.",
            "Community: Policy change regarding subsidies.",
            "Reflection: Last year's flood was a wake-up call.",
        ]
        mem_engine.retrieve_stratified.return_value = stratified_memories

        hooks.post_year(year=6, agents=agents, memory_engine=mem_engine)

        mem_engine.retrieve_stratified.assert_called_once()

        assert mem_engine.add_memory.call_count >= 1
        reflection_calls = [
            c for c in mem_engine.add_memory.call_args_list
            if c.kwargs.get("metadata", {}).get("type") == "reflection"
        ]
        assert len(reflection_calls) == 1, f"Expected 1 reflection call, got {len(reflection_calls)}"
        call_args, call_kwargs = reflection_calls[0]

        added_memory_content = call_args[1]
        added_memory_metadata = call_kwargs["metadata"]

        # Current reflection content is a natural-language summary prefixed
        # with "Year <N>:" (see _run_ma_reflection in lifecycle_hooks.py).
        assert added_memory_content.startswith("Year 6:")
        assert added_memory_metadata["type"] == "reflection"
        assert added_memory_metadata["source"] == "personal"
        assert added_memory_metadata["emotion"] == "major"
        # Importance is 0.45 per current implementation — below flood memories
        # (0.80) and decisions (0.50). Test against the design value.
        assert added_memory_metadata["importance"] == pytest.approx(0.45)


    def test_reflection_uses_stratified_retrieval_params(self, mock_hooks, mock_memory_engine):
        hooks, mem_engine, gm, mp, agents = mock_hooks
        # Flood triggers the crisis reflection path so retrieve_stratified runs.
        hooks.env["flood_occurred"] = True
        hooks.env["crisis_boosters"] = {"emotion:fear": 1.5}

        # _run_ma_reflection currently uses a personal-biased allocation with
        # total_k=5 (see lifecycle_hooks._run_ma_reflection). Crisis years
        # forward env["crisis_boosters"] as contextual boosters.
        expected_allocation = {"personal": 3, "neighbor": 1, "reflection": 1}
        expected_total_k = 5

        hooks.post_year(year=7, agents=agents, memory_engine=mem_engine)

        mem_engine.retrieve_stratified.assert_called_once_with(
            agents["H_001"].id,
            allocation=expected_allocation,
            total_k=expected_total_k,
            contextual_boosters={"emotion:fear": 1.5},
        )

    def test_reflection_logic_skips_if_no_flood(self, mock_hooks, mock_memory_engine):
        hooks, mem_engine, gm, mp, agents = mock_hooks
        hooks.env["flood_occurred"] = False
        # Pick a year that is not a multiple of the periodic trigger (5) so
        # neither the crisis nor the periodic path fires.
        hooks.post_year(year=8, agents=agents, memory_engine=mem_engine)

        mem_engine.retrieve_stratified.assert_not_called()
        reflection_calls = [
            c for c in mem_engine.add_memory.call_args_list
            if c.kwargs.get("metadata", {}).get("type") == "reflection"
        ]
        assert len(reflection_calls) == 0, "No reflection should be triggered without flood"

