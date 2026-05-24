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

# L3-1B (2026-05-23): expanded from 2 to 6 constructs.
# Carpenter (2010) meta-analysis (J. Health Communication 25(8):661-669,
# 18 studies pooled): mean weighted odds ratios rank the original four
# HBM constructs BARRIERS 3.00 > BENEFITS 2.54 > SEVERITY 2.18 >
# SUSCEPTIBILITY 2.00, with CUES_TO_ACTION 1.73 as the weakest of the
# five Rosenstock-1974 constructs. SELF_EFFICACY was added in the
# Extended HBM (Bandura 1977) and is not directly ranked in Carpenter's
# original five-construct analysis; we retain it in ``primary`` per the
# Extended-HBM literature convention because the existing
# thinking-validator rules depend on it. CUES_TO_ACTION → ``secondary``
# because Carpenter reports it less consistently in primary studies
# (often unmeasured); it's carried as a contextual signal rather than a
# load-bearing predictor.
HBM_CONSTRUCTS: Dict[str, list] = {
    "primary": [
        "SUSCEPTIBILITY_LABEL",
        "SEVERITY_LABEL",
        "BENEFITS_LABEL",
        "BARRIERS_LABEL",
        "SELF_EFFICACY_LABEL",
    ],
    "secondary": ["CUES_TO_ACTION_LABEL"],
    "all": [
        "SUSCEPTIBILITY_LABEL",
        "SEVERITY_LABEL",
        "BENEFITS_LABEL",
        "BARRIERS_LABEL",
        "SELF_EFFICACY_LABEL",
        "CUES_TO_ACTION_LABEL",
    ],
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
