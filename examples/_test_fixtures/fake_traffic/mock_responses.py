"""Mock LLM responses for fake_traffic E2E genericity gate (Phase 6Q-F-2).

Mirrors the year-keyed pattern in mock_llm.py::SAMPLE_RESPONSES but
with traffic-domain vocabulary (commuter / congestion / route /
transit). Used by tests/integration/test_e2e_genericity.py to
exercise the broker's LLM-retry loop without ollama running.

The responses use the broker's standard delimiter-bracketed JSON
schema (matches the simple `reasoning + decision` field set declared
in examples/_test_fixtures/fake_traffic/traffic_agent_types.yaml).
Decision indices 1-5 map to traffic_skill_registry.yaml:

  1 = take_alternate_route
  2 = delay_departure
  3 = switch_to_transit
  4 = carpool
  5 = do_nothing
"""

MOCK_TRAFFIC_RESPONSES = {
    "year_1": (
        "<<<DECISION_START>>>\n"
        "{\n"
        '    "reasoning": "Heavy congestion forecast on my usual route '
        "this morning. Trying an alternate detour to test if travel "
        'time improves.",\n'
        '    "decision": 1\n'
        "}\n"
        "<<<DECISION_END>>>"
    ),
    "year_2": (
        "<<<DECISION_START>>>\n"
        "{\n"
        '    "reasoning": "Alternate route helped marginally last year '
        "but added stress. Trying transit this year to fully escape "
        'driving congestion.",\n'
        '    "decision": 3\n'
        "}\n"
        "<<<DECISION_END>>>"
    ),
    "year_3": (
        "<<<DECISION_START>>>\n"
        "{\n"
        '    "reasoning": "Transit was reliable last year. Sticking '
        "with it — no need to switch back to driving while traffic "
        'patterns remain heavy.",\n'
        '    "decision": 3\n'
        "}\n"
        "<<<DECISION_END>>>"
    ),
    "dispatcher_year_1": (
        "<<<DECISION_START>>>\n"
        "{\n"
        '    "reasoning": "Forecast shows elevated congestion. Issuing '
        'an advisory to encourage alternate-route + transit choices.",\n'
        '    "decision": 1\n'
        "}\n"
        "<<<DECISION_END>>>"
    ),
}


class MockTrafficLLM:
    """Mock LLM that returns traffic-domain year-keyed responses.

    Parallel to test_sa_e2e_smoke.py::MockLLM. Tracks invocation
    count + supports per-agent-type dispatch (commuter responses vs
    dispatcher responses).
    """

    def __init__(self, responses=None):
        self.responses = responses or MOCK_TRAFFIC_RESPONSES
        self.call_count = 0

    def invoke(self, prompt, year=1, agent_type="commuter", **kwargs):
        """Return mock response based on year + agent_type."""
        self.call_count += 1
        if agent_type == "dispatcher":
            key = f"dispatcher_year_{year}"
            return self.responses.get(key, self.responses["dispatcher_year_1"])
        key = f"year_{year}"
        return self.responses.get(key, self.responses["year_1"])
