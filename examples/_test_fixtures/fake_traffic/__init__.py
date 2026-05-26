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

The 6Q-F-2-a reviewer's W1 / S1 / Q1 carry-forward TODOs were closed
by Phase 6Q-F-2-b (commit ``565148b``); the actual 1-year
``ExperimentRunner.run`` drive-through landed in Phase 6Q-F-2-c
(``tests/integration/test_e2e_genericity.py::TestTrafficE2ERuntime``).
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
