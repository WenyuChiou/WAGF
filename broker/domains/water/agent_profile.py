"""
FloodAgentProfile — water-domain (flood) extension of base AgentProfile.

Phase 6C-v3 (2026-05-10): the 12 flood-specific fields previously baked
into the universal :class:`broker.core.agent_initializer.AgentProfile`
dataclass are relocated here. Base ``AgentProfile`` now carries only
domain-neutral demographic / psychometric / spatial fields plus an
``extensions: Dict`` escape hatch for new domains.

Why this split?
===============
A non-water domain (vaccination, traffic, finance, education, etc.) had
to either (a) accept that every agent unconditionally carries
``flood_zone``, ``elevated``, ``has_insurance``, ``flood_depth``, etc.
with meaningless defaults (silent leak into prompts), or (b) subclass
``AgentProfile`` and shadow those fields. Both choices are awkward.

After Phase 6C-v3:
  - ``AgentProfile`` has no flood vocabulary
  - Flood example (``examples/governed_flood``) and irrigation example
    (``examples/irrigation_abm``) both use this subclass when they need
    flood-specific fields. Irrigation actually doesn't — irrigation
    state lives in the env, not the profile — but the subclass exists
    here for any flood-derived domain.
  - New domains either (a) define their own ``XxxAgentProfile(AgentProfile)``
    subclass adding their fields, or (b) put domain state in
    ``profile.extensions`` dict.
"""
from __future__ import annotations

from dataclasses import dataclass

from broker.core.agent_initializer import AgentProfile


@dataclass
class FloodAgentProfile(AgentProfile):
    """Flood-risk household profile.

    Extends base :class:`AgentProfile` with flood-specific demographic,
    physical, and behavioural state fields. Used by the flood and
    multi-agent flood examples.
    """

    # --- Flood exposure history ---
    flood_experience: bool = False
    flood_frequency: int = 0
    sfha_awareness: bool = False     # SFHA = Special Flood Hazard Area
    flood_zone: str = "MEDIUM"       # HIGH, MEDIUM, LOW
    flood_depth: float = 0.0

    # --- Adaptation state ---
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    cumulative_damage: float = 0.0

    # --- Asset values (replacement cost, NFIP-style) ---
    rcv_building: float = 0.0        # Building replacement cost ($)
    rcv_contents: float = 0.0        # Contents replacement cost ($)

    # --- Narrative metadata ---
    recent_flood_text: str = ""
    insurance_type: str = ""
    post_flood_action: str = ""
