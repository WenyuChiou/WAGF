import random
from types import SimpleNamespace

import pytest

from broker.components.analytics.interaction import InteractionHub


class _OrderedGraph:
    def __init__(self, neighbors):
        self._neighbors = neighbors

    def get_neighbors(self, agent_id):
        return list(self._neighbors.get(agent_id, []))


class _Memory:
    def retrieve(self, agent, top_k=1):
        return [{"content": f"update from {agent.agent_id}"}]


def _agents(*agent_ids):
    return {agent_id: SimpleNamespace(agent_id=agent_id) for agent_id in agent_ids}


def _mentioned_ids(context):
    return [snippet.split()[1] for snippet in context["gossip"]]


@pytest.mark.parametrize("pass_none", [False, True])
def test_legacy_sampling_preserves_output_and_global_rng_consumption(pass_none):
    neighbors = ["member_d", "member_b", "member_a", "member_c"]
    graph = _OrderedGraph({"observer": neighbors})
    agents = _agents("observer", *neighbors)
    seed = 1942

    random.seed(seed)
    expected = random.sample(neighbors, 2)
    expected_state = random.getstate()

    random.seed(seed)
    kwargs = {"rng_for": None} if pass_none else {}
    hub = InteractionHub(graph=graph, memory_engine=_Memory(), **kwargs)
    actual = hub.get_social_context("observer", agents, max_gossip=2)

    assert _mentioned_ids(actual) == expected
    assert random.getstate() == expected_state


def test_keyed_sampling_is_order_and_interleaving_independent():
    candidates = ["member_d", "member_b", "member_a", "member_c"]
    agents = _agents("observer", "colleague", *candidates)
    calls = []

    def rng_for(agent_id, purpose):
        calls.append((agent_id, purpose))
        seeds = {"observer": 71, "colleague": 903}
        return random.Random(seeds[agent_id])

    forward = InteractionHub(
        graph=_OrderedGraph({"observer": candidates, "colleague": candidates}),
        memory_engine=_Memory(),
        rng_for=rng_for,
    )
    reversed_graph = InteractionHub(
        graph=_OrderedGraph(
            {"observer": list(reversed(candidates)), "colleague": list(reversed(candidates))}
        ),
        memory_engine=_Memory(),
        rng_for=rng_for,
    )

    random.seed(8821)
    global_state = random.getstate()
    first = _mentioned_ids(forward.get_social_context("observer", agents, max_gossip=2))
    forward.get_social_context("colleague", agents, max_gossip=2)
    repeated = _mentioned_ids(forward.get_social_context("observer", agents, max_gossip=2))
    reversed_graph.get_social_context("colleague", agents, max_gossip=2)
    reordered = _mentioned_ids(
        reversed_graph.get_social_context("observer", agents, max_gossip=2)
    )

    assert len(first) == 2
    assert first == repeated == reordered
    assert random.getstate() == global_state
    assert calls == [
        ("observer", "gossip"),
        ("colleague", "gossip"),
        ("observer", "gossip"),
        ("colleague", "gossip"),
        ("observer", "gossip"),
    ]
