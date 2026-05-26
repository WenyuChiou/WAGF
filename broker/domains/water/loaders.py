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
    ``has_insurance``, ``elevated`` PLUS the 5 PMT score columns
    (Phase 6R-C — relocated from base CSVLoader). Populates them on
    :class:`FloodAgentProfile` instances.
    """

    _PROFILE_CLASS = FloodAgentProfile

    DEFAULT_COLUMNS = {
        **CSVLoader.DEFAULT_COLUMNS,
        "flood_experience": ["flood_experience", "has_flood_experience"],
        "flood_zone": ["flood_zone", "zone"],
        "has_insurance": ["has_insurance", "insurance"],
        "elevated": ["elevated", "is_elevated"],
        # Phase 6R-C: PMT score column aliases — relocated from base
        # ``CSVLoader.DEFAULT_COLUMNS`` (audit cluster A #3 / #4).
        "tp_score": ["tp_score", "TP", "threat_perception"],
        "cp_score": ["cp_score", "CP", "coping_perception"],
        "sp_score": ["sp_score", "SP", "stakeholder_perception"],
        "sc_score": ["sc_score", "SC", "social_capital"],
        "pa_score": ["pa_score", "PA", "place_attachment"],
    }

    def _populate_domain_fields(
        self, profile: FloodAgentProfile, get_val: Callable
    ) -> None:
        # Phase 6R-C: PMT scores now populated here (relocated from
        # base CSVLoader._parse_row's profile-construction kwargs).
        profile.tp_score = float(get_val("tp_score", 3.0))
        profile.cp_score = float(get_val("cp_score", 3.0))
        profile.sp_score = float(get_val("sp_score", 3.0))
        profile.sc_score = float(get_val("sc_score", 3.0))
        profile.pa_score = float(get_val("pa_score", 3.0))

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
      - PMT score distributions (Phase 6R-C, relocated from base
        SyntheticLoader — PMT framework is water-domain specific).
      - Flood-zone probability mix biased by MG status (HIGH/MEDIUM/LOW)
      - Flood experience / frequency / SFHA awareness probabilities
      - Asset value defaults
      - Passaic River Basin geographic bounding box
        (lon ∈ [-74.3, -74.2], lat ∈ [40.9, 41.0]) for synthetic agents
    """

    _PROFILE_CLASS = FloodAgentProfile

    # Phase 6R-C: agent_id prefix override — "H" (household) + 1-indexed
    # to preserve paper-1b byte-identity. Base SyntheticLoader uses
    # "A" + 0-indexed (domain-neutral). The 1-indexed offset cannot be
    # expressed via the prefix alone — see ``_build_agent_id`` override.
    _AGENT_ID_PREFIX = "H"

    def _build_agent_id(self, idx: int) -> str:
        """Paper-1b convention: ``H0001``, ``H0002``, ... (1-indexed).
        Uses the class-level ``_AGENT_ID_PREFIX`` so a single source
        of truth governs the prefix; the +1 offset is the paper-1b
        legacy convention (synthetic agents start at H0001, not H0000).
        """
        return f"{self._AGENT_ID_PREFIX}{idx + 1:04d}"

    # Phase 6R-C: PMT score distributions by MG status — relocated
    # from base SyntheticLoader.PMT_PARAMS (audit cluster A #4). These
    # values were the Phase 6C-v3 paper-1b calibration for the flood
    # household population; non-water domains define their own
    # distributions in their own SyntheticLoader subclass.
    PMT_PARAMS = {
        "mg": {
            "tp": (3.5, 0.8),  # Higher threat perception
            "cp": (2.5, 0.7),  # Lower coping perception
            "sp": (2.3, 0.6),  # Lower stakeholder perception
            "sc": (3.8, 0.6),  # Higher social capital (within community)
            "pa": (3.5, 0.7),  # Moderate place attachment
        },
        "nmg": {
            "tp": (2.8, 0.7),
            "cp": (3.2, 0.6),
            "sp": (3.0, 0.5),
            "sc": (3.2, 0.6),
            "pa": (3.0, 0.7),
        },
    }

    _SPATIAL_BBOX = {
        "x_min": 0, "x_max": 456,
        "y_min": 0, "y_max": 410,
        # Passaic River Basin, NJ — used by flood-zone enrichment
        "lon_min": -74.3, "lon_max": -74.2,
        "lat_min": 40.9, "lat_max": 41.0,
    }

    def _pre_generate_rng(self, is_mg, is_owner):
        """Phase 6R-C: sample PMT scores BEFORE base's RNG calls.

        Paper-1b reproducibility requires the original RNG sequence:
        TP → CP → SP → SC → PA → income → family_size → ... If PMT
        sampling moved to ``_populate_domain_fields`` (after base
        RNG calls), the np.random / random state would diverge and
        synthetic agents would differ. This hook restores the order.
        """
        params = self.PMT_PARAMS["mg" if is_mg else "nmg"]
        return {
            "tp": round(float(np.clip(np.random.normal(*params["tp"]), 1.0, 5.0)), 2),
            "cp": round(float(np.clip(np.random.normal(*params["cp"]), 1.0, 5.0)), 2),
            "sp": round(float(np.clip(np.random.normal(*params["sp"]), 1.0, 5.0)), 2),
            "sc": round(float(np.clip(np.random.normal(*params["sc"]), 1.0, 5.0)), 2),
            "pa": round(float(np.clip(np.random.normal(*params["pa"]), 1.0, 5.0)), 2),
        }

    def _populate_domain_fields(
        self, profile: FloodAgentProfile, is_mg: bool, is_owner: bool,
        pre=None,
    ) -> None:
        # Phase 6R-C: PMT scores were pre-sampled in
        # ``_pre_generate_rng`` to preserve paper-1b RNG ordering;
        # transfer them onto the typed FloodAgentProfile here.
        # Use ``pre is not None`` (NOT ``if pre:``) so an explicit
        # empty dict from a subclass still applies — reviewer Critical:
        # truthy-guard silently drops PMT for empty pre-dict.
        if pre is not None:
            profile.tp_score = pre["tp"]
            profile.cp_score = pre["cp"]
            profile.sp_score = pre["sp"]
            profile.sc_score = pre["sc"]
            profile.pa_score = pre["pa"]
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
