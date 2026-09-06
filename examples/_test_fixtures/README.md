# _test_fixtures

Not a paper-shipping example. Holds `DomainPack` fixtures proving the
broker is genuinely domain-generic (not water-shaped by accident).

## `fake_traffic/`

A non-water `DomainPack` (Phase 6Q-F-2) used by
`tests/integration/test_e2e_genericity.py` to drive `ExperimentBuilder`
end to end via the framework-escape-hatch path (no registered
psychometric framework). Vocabulary: agent types `commuter` /
`dispatcher`; skills `take_alternate_route` / `delay_departure` /
`switch_to_transit` / `carpool` / `do_nothing`. Deliberately minimal —
no calibrated reflection text, importance profiles, or domain-specific
validators — so everything not overridden exercises `DefaultDomainPack`.

- `pack.py` — `FakeTrafficDomainPack`.
- `mock_responses.py` — canned LLM responses keyed by year.
- `traffic_agent_types.yaml`, `traffic_skill_registry.yaml` — config.
- `prompts/` — prompt templates for this fixture.

Not runnable standalone (no `run_*.py`) — exercise via
`tests/integration/test_e2e_genericity.py`.
