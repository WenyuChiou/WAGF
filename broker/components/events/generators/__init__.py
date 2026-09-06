"""Generic event generators.

Org-3 note (2026-09): the ``impact`` (ImpactEventGenerator) and
``policy`` (PolicyEventGenerator) modules that used to live here were
deleted as dead code — reachable only via the also-deleted
``broker.components.events.ma_manager.MAEventManager`` (no production
runner instantiated either generator).

Domain-specific generators live under their respective domain trees —
the water-domain hazard generators are at
``broker.domains.water.event_generators.flood`` (Phase 6K-B,
2026-05-22) and ``broker.domains.water.event_generators.hazard_per_agent``
(Phase 6Q-B, 2026-05-26; previously ``hazard.py`` under this package,
relocated when its zero-non-test-caller + flood-implicit
payload-schema status was confirmed by the Phase 6P-E follow-up
audit).
"""
