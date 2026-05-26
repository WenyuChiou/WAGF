"""Generic event generators.

Modules:
    impact — ImpactEventGenerator, ImpactEventConfig
    policy — PolicyEventGenerator, PolicyEventConfig

Domain-specific generators live under their respective domain trees —
the water-domain hazard generators are at
``broker.domains.water.event_generators.flood`` (Phase 6K-B,
2026-05-22) and ``broker.domains.water.event_generators.hazard_per_agent``
(Phase 6Q-B, 2026-05-26; previously ``hazard.py`` under this package,
relocated when its zero-non-test-caller + flood-implicit
payload-schema status was confirmed by the Phase 6P-E follow-up
audit).
"""
