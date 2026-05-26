"""FakeTrafficDomainPack — non-water E2E genericity fixture (Phase 6Q-F-2).

This package is NOT a paper-1b shipping example. It exists so the
genericity gates at
``tests/integration/test_e2e_genericity.py`` can drive the broker
end-to-end with a domain that has zero water-coupling. The traffic
metaphor (commuters choosing congestion-response actions) is
arbitrary — it just needs to be:

  1. non-water in vocabulary and ontology;
  2. simple enough to scaffold without external simulator coupling;
  3. realistic enough that the broker's reflection / memory /
     governance paths actually fire (not no-op).

Phase 6Q-F-2-a (foundation, this commit): register the pack +
provide YAML configs. The actual 1-year ``ExperimentRunner.run`` is
deferred to Phase 6Q-F-2-b. The foundation lets the E2E test
construct the experiment graph and assert sys.modules cleanliness.

Registration pattern mirrors examples.governed_flood / .vaccination_demo
— explicit ``DomainPackRegistry.register`` at package import time
(Phase 6Q-G removed broker.domains auto-discovery, so consumers
must import this package to trigger registration).

Phase 6Q-F-2-b TODOs (carry-forward from 6Q-F-2-a reviewer):
  - **W1 (MUST)**: ``mock_responses.MockTrafficLLM.invoke`` returns
    a bare ``str`` and takes ``year=`` / ``agent_type=`` kwargs that
    the real broker pipeline never passes. The broker LLM contract
    is ``invoke(prompt) -> (str, LLMStats)``. Refactor before the
    actual ``ExperimentRunner.run`` exercise — year-dispatch logic
    needs to inject year via a different mechanism (callable
    passed at construction OR external state tracker).
  - **S1**: import-side-effect ``DomainPackRegistry.register("traffic", …)``
    persists for the pytest session. Add a session-scoped autouse
    fixture for clean teardown before 6Q-F-2-b adds list-domains
    assertions.
  - **Q1**: ``traffic_agent_types.yaml`` declares
    ``prompt_template_file: null`` for both agent types. Confirm
    ``ExperimentBuilder`` has a graceful null-file path before
    construction-time test — otherwise add a minimal generic
    template file.
"""
try:
    from broker.domains.registry import DomainPackRegistry
    from examples._test_fixtures.fake_traffic.pack import FakeTrafficDomainPack
    DomainPackRegistry.register("traffic", FakeTrafficDomainPack())
except ImportError:
    # Broker package may not be importable at fixture-load time in
    # partial-bring-up scenarios. Silent skip matches the
    # examples.governed_flood pattern.
    pass
