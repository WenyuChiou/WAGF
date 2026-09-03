"""Operator CLIs for WAGF (Phase 6C-v4 cycle 3, 2026-05-10).

Currently exposes:
- ``validate_prompt`` — static check that an agent's prompt template + YAML
  config are in sync (placeholders, JSON keys, parsing.constructs, actions).
- ``ablate_factor`` — replay recorded decisions with one context factor
  neutralised, against a severity-matched paraphrase control, to test
  whether that factor is what the decision used (PR-5). Refuses to report
  a delta-P unless the decider is verified deterministic — which requires
  identical replies that were also actual decisions, so a stopped backend
  returning the same empty string every time fails rather than passes.
- ``calibrate`` — numeric parameter search (nelder-mead or grid) over a
  caller-supplied objective, via ``broker.calibration.optimize`` (PR-7).
  Scoped to non-prompt numeric parameters; refuses a search space whose
  keys look like prompt/template paths.

Run with ``python -m broker.tools.<name> --help``.
"""
