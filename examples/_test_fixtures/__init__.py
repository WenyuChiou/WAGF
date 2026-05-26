"""Internal test fixtures for genericity end-to-end gates.

Phase 6Q-F-2 (2026-05-26): packages here are NOT shipping examples
of paper-1b experiments — they exist solely to exercise the
broker's domain-agnostic claim with non-water fake domains. Keep
these out of any "supported example" documentation.

Current fixtures:
  - ``fake_traffic``: minimum-surface non-water DomainPack for E2E
    genericity tests. Uses the FRAMEWORK_ESCAPE_HATCH path (no
    registered psychometric framework) — the simplest exercise
    of "can a domain without a framework run end-to-end".
"""
