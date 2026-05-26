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
    """Mock LLM matching the broker's legacy ``Callable[[str], str]``
    contract (per ``broker.utils.llm_utils.create_legacy_invoke``).

    Phase 6Q-F-2-b (2026-05-26): re-signed to match the canonical
    broker contract — ``invoke(prompt) -> str``. Pre-fix the
    signature was ``invoke(prompt, year=1, agent_type="commuter",
    **kwargs)`` — the real broker pipeline never passes year/
    agent_type kwargs, so year-dispatch was silently inert.

    Year + agent_type routing now uses **external state**: the test
    driver sets ``mock.current_year`` and ``mock.current_agent_type``
    before each invocation batch (lifecycle hooks handle this in a
    real run). ``call_count`` still tracks invocations.
    """

    def __init__(self, responses=None):
        self.responses = responses or MOCK_TRAFFIC_RESPONSES
        self.call_count = 0
        # External-state knobs the test driver sets between batches.
        self.current_year: int = 1
        self.current_agent_type: str = "commuter"

    def invoke(self, prompt: str) -> str:
        """Broker contract: ``Callable[[str], str]``.

        Year + agent_type selection driven by the instance's
        ``current_year`` / ``current_agent_type`` attributes (mutate
        them between invocation batches to drive the year dispatch).
        """
        self.call_count += 1
        if self.current_agent_type == "dispatcher":
            key = f"dispatcher_year_{self.current_year}"
            return self.responses.get(key, self.responses["dispatcher_year_1"])
        key = f"year_{self.current_year}"
        return self.responses.get(key, self.responses["year_1"])
