"""Phase 6U-F (2026-05-28): PMT framework metadata — generic home.

Protection Motivation Theory metadata (label order, construct vocab,
label normalisation mappings) is now part of the broker's generic
framework registry alongside ``utility``, ``financial``, and
``narrative_diffusion``. Pre-6U-F this metadata lived in
``broker/domains/water/thinking_checks.py:WATER_FRAMEWORK_*`` — a
Phase-6P-A-class leak because PMT (Rogers 1975) is a cross-domain
behavioural framework, not a water-specific construct.

WHAT MOVED HERE (purely declarative, skill-agnostic):
  - PMT_LABEL_ORDER: VL/L/M/H/VH ordinal mapping
  - PMT_CONSTRUCTS: TP/CP primary, SP/SC/PA optional constructs
  - PMT_LABEL_MAPPINGS: "VERY LOW" → "VL" etc. normalization

WHAT STAYS IN ``broker/domains/water/`` (skill-coupled):
  - ``PMTFramework`` class (constructor defaults reference
    water-domain skill names — see ``broker/domains/water/pmt.py``)
  - ``_water_pmt_check`` builtin check body (reads
    ``extreme_actions`` from context, skill-name dependent)

Auto-registration: ``broker/validators/governance/frameworks/__init__.py``
imports this module at package load and calls
``register_framework_metadata("pmt", ...)`` so callers can validate
``psychological_framework: pmt`` in YAML configs without first
importing ``broker.domains.water``.
"""
from __future__ import annotations

from typing import Dict


PMT_LABEL_ORDER: Dict[str, int] = {
    "VL": 0,
    "L": 1,
    "M": 2,
    "H": 3,
    "VH": 4,
}


PMT_CONSTRUCTS: Dict[str, object] = {
    "primary": "TP_LABEL",
    "secondary": "CP_LABEL",
    "all": ["TP_LABEL", "CP_LABEL", "SP_LABEL", "SC_LABEL", "PA_LABEL"],
}


PMT_LABEL_MAPPINGS: Dict[str, str] = {
    "VERY LOW": "VL",
    "VERYLOW": "VL",
    "VERY_LOW": "VL",
    "LOW": "L",
    "MEDIUM": "M",
    "MED": "M",
    "MODERATE": "M",
    "HIGH": "H",
    "VERY HIGH": "VH",
    "VERYHIGH": "VH",
    "VERY_HIGH": "VH",
}


__all__ = [
    "PMT_LABEL_ORDER",
    "PMT_CONSTRUCTS",
    "PMT_LABEL_MAPPINGS",
]
