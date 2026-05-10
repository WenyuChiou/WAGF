"""Operator CLIs for WAGF (Phase 6C-v4 cycle 3, 2026-05-10).

Currently exposes:
- ``validate_prompt`` — static check that an agent's prompt template + YAML
  config are in sync (placeholders, JSON keys, parsing.constructs, actions).

Run with ``python -m broker.tools.validate_prompt --help``.
"""
