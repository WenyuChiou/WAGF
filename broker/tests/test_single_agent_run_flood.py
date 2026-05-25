from types import SimpleNamespace

from examples.single_agent.run_flood import _limit_agents_for_run


def test_limit_agents_for_run_respects_natural_agent_order():
    agents = {
        "Agent_10": SimpleNamespace(id="Agent_10"),
        "Agent_2": SimpleNamespace(id="Agent_2"),
        "Agent_1": SimpleNamespace(id="Agent_1"),
    }

    limited = _limit_agents_for_run(agents, 2)

    assert list(limited) == ["Agent_1", "Agent_2"]

