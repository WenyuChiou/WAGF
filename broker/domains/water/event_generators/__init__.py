"""Water-domain event generators.

Phase 6K-B (2026-05-22): the flood hazard generator (``FloodEventGenerator`` +
``FloodConfig``) relocated here from generic
``broker/components/events/generators/`` so that ``broker/`` no longer
names the water domain.

Phase 6Q-B (2026-05-26): the per-agent hazard generator
(``HazardEventGenerator`` + ``HazardEventConfig``) relocated here as
``hazard_per_agent`` after the Phase 6P-E follow-up audit confirmed
it carried a flood-implicit payload schema (``depth_m`` / ``depth_ft``
/ ``m → ft`` conversion / ``hazard_module.get_flood_event`` API) and
zero non-test production callers. Its generic siblings
(``impact.py`` / ``policy.py``) stay under the broker tree — they are
already domain-agnostic.
"""
from .flood import FloodConfig, FloodEventGenerator
from .hazard_per_agent import HazardEventConfig, HazardEventGenerator

__all__ = [
    "FloodConfig",
    "FloodEventGenerator",
    "HazardEventConfig",
    "HazardEventGenerator",
]
