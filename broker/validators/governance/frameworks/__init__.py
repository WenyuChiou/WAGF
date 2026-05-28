"""
Generic-framework registry — auto-registers cross-domain psychological /
analytical frameworks at module import time.

Closes a Phase-6P-A-class genericity leak: pre-this-commit the
``utility`` and ``financial`` framework METADATA lived in
``broker/domains/water/thinking_checks.py`` even though their construct
vocabulary (``BUDGET_UTIL`` / ``EQUITY_GAP`` / ``ADOPTION_RATE`` for
utility; ``RISK_APPETITE`` / ``SOLVENCY_IMPACT`` / ``MARKET_SHARE`` for
financial) is genuinely cross-domain — a vaccination-funding agent or
a transit-fare-policy agent could legitimately use utility theory; an
insurance / pension / catastrophe-bond agent could use financial.

Phase 6T-F prep (2026-05-27): the audit-doc design rule "tier
vocabulary lives in the DomainPack, not in broker/" generalises to
"generic-framework metadata lives in a generic broker/ home, not in
``broker/domains/<one-specific-domain>/``." This module is that
generic home.

Scope decisions
================
**Moved (this module)**:

- Metadata (``FRAMEWORK_LABEL_ORDERS`` / ``FRAMEWORK_CONSTRUCTS`` /
  ``_LABEL_MAPPINGS`` registrations) for ``utility``, ``financial``,
  and the new ``narrative_diffusion`` (Phase 6T-F).
- The ``NarrativeDiffusionFramework`` class (new — no pre-existing
  home).

**Deliberately NOT moved**:

- The ``UtilityFramework`` and ``FinancialFramework`` CLASSES stay in
  ``broker/domains/water/{utility,financial}.py``. Their
  ``get_expected_behavior()`` method returns flood-paper-3-flavoured
  skill names (e.g. ``"increase_subsidy"`` / ``"reduce_subsidy"``)
  which couple the BEHAVIOR layer to flood. The construct VOCABULARY
  is generic; the EXPECTED-BEHAVIOR mapping is flood-coupled.
- Calibration tooling at
  ``broker/domains/water/calibration/micro_validator.py`` calls
  ``get_expected_behavior`` — that's the load-bearing caller forcing
  the class to stay in water. A full extraction would require
  splitting each Framework into a generic-base + flood-specific
  subclass; that's deferred to a separate refactor.

**Audit-locked design (per `.research/social_media_genericity_audit.md`)**:

- ``narrative_diffusion`` framework constructs are deliberately
  generic (salience / virality / audience_fit /
  narrative_consistency) — applicable to any domain modeling
  narrative-amplification dynamics, not just paper-3 flood social
  media.
- A future vaccination-misinformation framework or a
  traffic-news-propagation framework can register their OWN names
  with the same construct shape via ``register_framework_metadata``
  without needing to fork or extend this module.

Genericity invariant
====================
This module MUST NOT import from ``broker.domains.water`` or
``examples.*``. Verified by
``broker/tests/test_generic_frameworks_registration.py``.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Dict, Set

from broker.validators.governance.thinking_validator import (
    FRAMEWORK_LABEL_ORDERS,
    register_framework_metadata,
)

# Phase 6U-F (2026-05-28): PMT_* re-exported eagerly at module top so
# the bindings exist BEFORE any subsequent import (e.g.
# NarrativeDiffusionFramework at the bottom of this file). Pre-fix the
# re-export sat at the bottom, creating a partial-import window where
# ``__all__`` listed PMT_LABEL_ORDER as exported while the binding had
# not yet executed — if an import between failed mid-way, downstream
# ThinkingValidator construction would silently fall back to the
# generic _GENERIC_LABEL_MAPPINGS for any "VERY HIGH" / "VERY LOW"
# label, biasing TP/CP normalization on every PMT-framework agent in
# the batch.
from broker.validators.governance.frameworks.pmt import (
    PMT_LABEL_ORDER,
    PMT_CONSTRUCTS,
    PMT_LABEL_MAPPINGS,
)

FRAMEWORK_REGISTRY: Dict[str, Any] = MappingProxyType(FRAMEWORK_LABEL_ORDERS)


def list_registered_frameworks() -> Set[str]:
    """Return framework names registered at runtime.

    Includes ``""`` (the Phase 6Q-D FRAMEWORK_ESCAPE_HATCH sentinel)
    so a YAML with ``psychological_framework: ""`` passes registry
    validation explicitly instead of being silent-cased inside the
    field validator.
    """
    return set(FRAMEWORK_LABEL_ORDERS) | {"generic", ""}


# ─────────────────────────────────────────────────────────────────────
# Utility framework metadata (moved from broker/domains/water/thinking_checks.py)
# ─────────────────────────────────────────────────────────────────────

UTILITY_LABEL_ORDER = {"L": 0, "M": 1, "H": 2}

UTILITY_CONSTRUCTS = {
    "primary": "BUDGET_UTIL",
    "secondary": "EQUITY_GAP",
    "all": ["BUDGET_UTIL", "EQUITY_GAP", "ADOPTION_RATE"],
}

UTILITY_LABEL_MAPPINGS = {
    "LOW": "L", "LOW PRIORITY": "L", "LOW_PRIORITY": "L",
    "MEDIUM": "M", "MED": "M", "MEDIUM PRIORITY": "M",
    "HIGH": "H", "HIGH PRIORITY": "H", "HIGH_PRIORITY": "H",
}


# ─────────────────────────────────────────────────────────────────────
# Financial framework metadata (moved from broker/domains/water/thinking_checks.py)
# ─────────────────────────────────────────────────────────────────────

FINANCIAL_LABEL_ORDER = {"C": 0, "M": 1, "A": 2}

FINANCIAL_CONSTRUCTS = {
    "primary": "RISK_APPETITE",
    "secondary": "SOLVENCY_IMPACT",
    "all": ["RISK_APPETITE", "SOLVENCY_IMPACT", "MARKET_SHARE"],
}

FINANCIAL_LABEL_MAPPINGS = {
    "CONSERVATIVE": "C", "CONS": "C", "LOW": "C",
    "MODERATE": "M", "MOD": "M", "MEDIUM": "M",
    "AGGRESSIVE": "A", "AGG": "A", "HIGH": "A",
}


# ─────────────────────────────────────────────────────────────────────
# Narrative diffusion framework metadata (NEW — Phase 6T-F prep)
# ─────────────────────────────────────────────────────────────────────
#
# Per the Phase 6T-D audit doc:
#
#   narrative_diffusion (constructs: salience, virality, audience_fit,
#   narrative_consistency)
#
# Constructs deliberately generic — applicable to any narrative-
# amplification context. A vaccination-misinformation
# narrative_diffusion influencer + a traffic-news-propagation
# influencer would use the same construct vocabulary.
#
# Labels use 5-point Likert (VL/L/M/H/VH) matching PMT — that's the
# de-facto standard the ThinkingValidator + audit-CSV row-builders
# already understand.

NARRATIVE_DIFFUSION_LABEL_ORDER = {
    "VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4,
}

NARRATIVE_DIFFUSION_CONSTRUCTS = {
    "primary": "SALIENCE",
    "secondary": "VIRALITY",
    "all": [
        "SALIENCE",
        "VIRALITY",
        "AUDIENCE_FIT",
        "NARRATIVE_CONSISTENCY",
    ],
}

NARRATIVE_DIFFUSION_LABEL_MAPPINGS = {
    "VERY LOW": "VL", "VERYLOW": "VL", "VERY_LOW": "VL",
    "LOW": "L",
    "MEDIUM": "M", "MED": "M", "MODERATE": "M",
    "HIGH": "H",
    "VERY HIGH": "VH", "VERYHIGH": "VH", "VERY_HIGH": "VH",
}


# ─────────────────────────────────────────────────────────────────────
# Auto-registration (fires at module import time)
# ─────────────────────────────────────────────────────────────────────
# Imported by broker/validators/governance/__init__.py so the
# generic-framework metadata is available without explicit
# water-domain import. This makes utility / financial / narrative_diffusion
# available to ANY domain pack via register_framework_metadata's
# global FRAMEWORK_LABEL_ORDERS / FRAMEWORK_CONSTRUCTS / _LABEL_MAPPINGS
# dictionaries.

def _register_generic_frameworks() -> None:
    """Idempotent registration of all generic frameworks.

    Phase 6U-F (2026-05-28): PMT metadata moved from
    ``broker/domains/water/thinking_checks.py`` to
    ``broker/validators/governance/frameworks/pmt.py`` so callers
    can validate ``psychological_framework: pmt`` YAML without first
    importing ``broker.domains.water``. The water domain's
    ``register_water_metadata`` no longer registers PMT metadata; it
    still registers the skill-dependent ``_water_pmt_check`` builtin
    body via ``register_thinking_checks``.
    """
    register_framework_metadata(
        "pmt",
        PMT_CONSTRUCTS,
        PMT_LABEL_ORDER,
        PMT_LABEL_MAPPINGS,
    )
    register_framework_metadata(
        "utility",
        UTILITY_CONSTRUCTS,
        UTILITY_LABEL_ORDER,
        UTILITY_LABEL_MAPPINGS,
    )
    register_framework_metadata(
        "financial",
        FINANCIAL_CONSTRUCTS,
        FINANCIAL_LABEL_ORDER,
        FINANCIAL_LABEL_MAPPINGS,
    )
    register_framework_metadata(
        "narrative_diffusion",
        NARRATIVE_DIFFUSION_CONSTRUCTS,
        NARRATIVE_DIFFUSION_LABEL_ORDER,
        NARRATIVE_DIFFUSION_LABEL_MAPPINGS,
    )


# Import-time side effect. Idempotent — re-import is safe because
# register_framework_metadata just overwrites the dict entries.
_register_generic_frameworks()


# Also register the NarrativeDiffusionFramework CLASS in the
# psychometric framework registry so callers can do
# ``get_framework("narrative_diffusion")`` and get behavioural
# methods. The class lives in narrative_diffusion.py to keep this
# module's surface narrow (metadata only).
from broker.validators.governance.frameworks.narrative_diffusion import (  # noqa: E402
    NarrativeDiffusionFramework,
)
from broker.core.psychometric import register_framework  # noqa: E402

register_framework("narrative_diffusion", NarrativeDiffusionFramework)


__all__ = [
    "PMT_LABEL_ORDER",
    "PMT_CONSTRUCTS",
    "PMT_LABEL_MAPPINGS",
    "UTILITY_LABEL_ORDER",
    "UTILITY_CONSTRUCTS",
    "UTILITY_LABEL_MAPPINGS",
    "FINANCIAL_LABEL_ORDER",
    "FINANCIAL_CONSTRUCTS",
    "FINANCIAL_LABEL_MAPPINGS",
    "NARRATIVE_DIFFUSION_LABEL_ORDER",
    "NARRATIVE_DIFFUSION_CONSTRUCTS",
    "NARRATIVE_DIFFUSION_LABEL_MAPPINGS",
    "NarrativeDiffusionFramework",
    "FRAMEWORK_REGISTRY",
    "list_registered_frameworks",
]
