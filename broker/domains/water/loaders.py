"""
Flood-domain agent loaders.

Phase 6C-v3 (2026-05-10): :class:`FloodCSVLoader` and
:class:`FloodSyntheticLoader` add flood-specific fields on top of the
domain-neutral base loaders in :mod:`broker.core.agent_initializer`.

Why these subclasses?
=====================
Base ``CSVLoader`` and ``SyntheticLoader`` produce
:class:`AgentProfile` instances without any flood vocabulary
(``flood_zone``, ``elevated``, ``has_insurance``, etc.). The flood
example needs those fields, so it instantiates these subclasses
which:

  - Set ``_PROFILE_CLASS = FloodAgentProfile`` so the typed flood
    fields exist on returned profiles.
  - Override ``_populate_domain_fields`` to populate flood-specific
    fields from CSV columns or synthetic distributions.
  - For synthetic generation, set ``_SPATIAL_BBOX`` to the
    Passaic-NJ geographic bounding box so test agents have realistic
    coordinates for flood-zone enrichment.

Other domains (vaccination, traffic, etc.) define their own analogous
subclasses with their own profile class and field synthesis.
"""
from __future__ import annotations

import random
from typing import Any, Callable

import numpy as np

from broker.core.agent_initializer import CSVLoader, SyntheticLoader
from broker.domains.water.agent_profile import FloodAgentProfile


# ─────────────────────────────────────────────────────────────────────
# CSV loader — flood field column reads
# ─────────────────────────────────────────────────────────────────────


class FloodCSVLoader(CSVLoader):
    """CSVLoader for flood-risk household experiments.

    Adds column aliases for ``flood_experience``, ``flood_zone``,
    ``has_insurance``, ``elevated`` and populates them on
    :class:`FloodAgentProfile` instances.
    """

    _PROFILE_CLASS = FloodAgentProfile

    DEFAULT_COLUMNS = {
        **CSVLoader.DEFAULT_COLUMNS,
        "flood_experience": ["flood_experience", "has_flood_experience"],
        "flood_zone": ["flood_zone", "zone"],
        "has_insurance": ["has_insurance", "insurance"],
        "elevated": ["elevated", "is_elevated"],
    }

    def _populate_domain_fields(
        self, profile: FloodAgentProfile, get_val: Callable
    ) -> None:
        profile.flood_experience = bool(get_val("flood_experience", False))
        profile.flood_zone = str(get_val("flood_zone", "MEDIUM"))
        profile.has_insurance = bool(get_val("has_insurance", False))
        profile.elevated = bool(get_val("elevated", False))


# ─────────────────────────────────────────────────────────────────────
# Synthetic loader — flood field distributions + Passaic geography
# ─────────────────────────────────────────────────────────────────────


class FloodSyntheticLoader(SyntheticLoader):
    """SyntheticLoader for flood-risk household experiments.

    Adds:
      - Flood-zone probability mix biased by MG status (HIGH/MEDIUM/LOW)
      - Flood experience / frequency / SFHA awareness probabilities
      - Asset value defaults
      - Passaic River Basin geographic bounding box
        (lon ∈ [-74.3, -74.2], lat ∈ [40.9, 41.0]) for synthetic agents
    """

    _PROFILE_CLASS = FloodAgentProfile

    _SPATIAL_BBOX = {
        "x_min": 0, "x_max": 456,
        "y_min": 0, "y_max": 410,
        # Passaic River Basin, NJ — used by flood-zone enrichment
        "lon_min": -74.3, "lon_max": -74.2,
        "lat_min": 40.9, "lat_max": 41.0,
    }

    def _populate_domain_fields(
        self, profile: FloodAgentProfile, is_mg: bool, is_owner: bool
    ) -> None:
        # Flood zone — MG biased toward HIGH/MEDIUM, NMG toward LOW
        if is_mg:
            flood_zone = np.random.choice(
                ["HIGH", "MEDIUM", "LOW"], p=[0.4, 0.4, 0.2]
            )
        else:
            flood_zone = np.random.choice(
                ["HIGH", "MEDIUM", "LOW"], p=[0.2, 0.4, 0.4]
            )

        profile.flood_experience = random.random() < 0.25
        profile.flood_frequency = (
            int(np.random.choice([0, 1, 2, 3])) if random.random() < 0.25 else 0
        )
        profile.sfha_awareness = random.random() < 0.6
        profile.flood_zone = str(flood_zone)
        profile.flood_depth = round(random.uniform(0.1, 2.0), 3)
        profile.has_insurance = random.random() < 0.15
