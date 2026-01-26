from broker.components.memory_engine import MemoryEngine


class DummyEngine(MemoryEngine):
    def add_memory(self, agent_id, content, metadata=None):
        return None

    def retrieve(self, agent, **kwargs):
        return ["m1", "m2"]

    def clear(self, agent_id):
        return None


class DummyScore:
    def __init__(self, total):
        self.total = total


class DummyScorer:
    def score(self, memory, context, agent_state):
        return DummyScore(2 if memory == "m2" else 1)


class DummyAgent:
    def __init__(self):
        self.foo = "bar"


def test_retrieve_with_scoring_orders_by_total():
    engine = DummyEngine(scorer=DummyScorer())
    scored = engine.retrieve_with_scoring(DummyAgent(), {"ctx": 1})
    assert scored[0][0] == "m2"
    assert scored[0][1].total == 2
