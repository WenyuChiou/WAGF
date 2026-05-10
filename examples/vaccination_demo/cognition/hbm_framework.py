"""
Health Belief Model (HBM) framework — registration for WAGF ThinkingValidator.

Reference: Rosenstock (1974), Carpenter (2010). HBM models health behaviour
as a function of perceived susceptibility, severity, benefits, barriers,
self-efficacy, and cues to action.

Phase 6C-v3 Group H integration
================================
WAGF's :class:`broker.validators.governance.thinking_validator.ThinkingValidator`
now strictly verifies that any non-empty ``framework`` string is registered
in ``FRAMEWORK_LABEL_ORDERS`` before construction. Without that registration
the constructor raises ``ValueError`` to surface a silent-wrong-answer bug
where label comparisons would silently use the PMT ordinal scale.

This module calls :func:`register_framework_metadata` at import time, so
importing ``examples.vaccination_demo`` (which transitively imports this
package) is enough to unlock ``ThinkingValidator(framework="hbm")``.
"""
from __future__ import annotations

from typing import Dict


# ─────────────────────────────────────────────────────────────────────
# HBM construct metadata
# ─────────────────────────────────────────────────────────────────────

HBM_CONSTRUCTS: Dict[str, list] = {
    "primary": ["SUSCEPTIBILITY_LABEL"],
    "secondary": ["SELF_EFFICACY_LABEL"],
    "all": ["SUSCEPTIBILITY_LABEL", "SELF_EFFICACY_LABEL"],
}

# HBM shares PMT's 5-level VL–VH ordinal scale (lower = lower belief).
# Documenting this alignment explicitly so a future divergence (e.g., HBM
# adopting a 7-level scale) gets caught loudly.
HBM_LABEL_ORDER: Dict[str, int] = {
    "VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4,
}

# Common LLM label variations normalised to the canonical codes above.
HBM_LABEL_MAPPINGS: Dict[str, str] = {
    "VERY LOW": "VL",
    "VERY-LOW": "VL",
    "LOW": "L",
    "MEDIUM": "M",
    "MEDIUM-LOW": "L",
    "MODERATE": "M",
    "HIGH": "H",
    "VERY HIGH": "VH",
    "VERY-HIGH": "VH",
}


def register_hbm() -> None:
    """Register HBM metadata with WAGF's ThinkingValidator.

    Called automatically from :mod:`examples.vaccination_demo.cognition`'s
    package ``__init__``.  Safe to call repeatedly — the underlying
    registry replaces silently on re-registration.
    """
    from broker.validators.governance.thinking_validator import (
        register_framework_metadata,
    )
    register_framework_metadata(
        name="hbm",
        constructs=HBM_CONSTRUCTS,
        label_order=HBM_LABEL_ORDER,
        label_mappings=HBM_LABEL_MAPPINGS,
    )
