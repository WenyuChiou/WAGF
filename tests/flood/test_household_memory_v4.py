from examples.multi_agent.flood.ma_agents.household import HouseholdAgent


def test_household_init_memory_v4_symbolic():
    agent = HouseholdAgent(
        agent_id="h1",
        mg=False,
        tenure="Owner",
        income=50000,
        property_value=200000,
    )
    config = {
        "engine": "symbolic",
        "sensors": [
            {"path": "flood_depth_m", "name": "FLOOD", "bins": [{"label": "SAFE", "max": 0.3}]}
        ],
        "arousal_threshold": 0.5,
    }
    memory = agent._init_memory_v4(config)
    assert memory is not None
    assert memory.__class__.__name__ == "SymbolicMemory"
