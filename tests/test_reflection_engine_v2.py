from broker.components.reflection_engine import ReflectionEngine


class DummyTemplate:
    def generate_prompt(self, agent_id, memories, context):
        return f"prompt:{agent_id}"

    def parse_response(self, response, memories, context):
        return {"insight": response}


class DummyIntegrator:
    def __init__(self):
        self.calls = []

    def process_reflection(self, agent_id, response, memories, context):
        self.calls.append((agent_id, response))


class DummyEngine(ReflectionEngine):
    def _call_llm(self, prompt):
        return f"response:{prompt}"


def test_reflect_v2_uses_template_and_integrator():
    integrator = DummyIntegrator()
    engine = DummyEngine(template=DummyTemplate(), integrator=integrator)
    insight = engine.reflect_v2("a1", ["m"], {"c": 1})
    assert insight == {"insight": "response:prompt:a1"}
    assert integrator.calls == [("a1", "response:prompt:a1")]
