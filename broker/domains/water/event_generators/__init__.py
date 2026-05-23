"""Water-domain event generators.

Phase 6K-B (2026-05-22): the flood hazard generator (``FloodEventGenerator`` +
``FloodConfig``) relocated here from generic
``broker/components/events/generators/`` so that ``broker/`` no longer
names the water domain. Its generic siblings (``hazard.py`` /
``impact.py`` / ``policy.py``) stay under the broker tree — they are
already domain-agnostic.
"""
from .flood import FloodConfig, FloodEventGenerator

__all__ = ["FloodConfig", "FloodEventGenerator"]
