"""
Water-domain thinking-validator metadata and builtin checks.

Registers framework label orders, construct mappings, label normalization
mappings, and builtin check implementations for:
- PMT (Protection Motivation Theory) — flood household agents
- Dual Appraisal (WSA/ACA) — irrigation agents
- Utility — government agents
- Financial — insurance agents

Called by ``broker.domains.water.__init__.register()`` at import time.
"""

from typing import Dict, List, Any, Optional

from broker.interfaces.skill_types import ValidationResult
from broker.governance.rule_types import GovernanceRule


# ───────────────────────────────────────────────────────────────────
# Framework metadata — registered into ThinkingValidator's registry
# ───────────────────────────────────────────────────────────────────

WATER_FRAMEWORK_LABEL_ORDERS: Dict[str, Dict[str, int]] = {
    "pmt": {"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4},
    "dual_appraisal": {"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4},
    "utility": {"L": 0, "M": 1, "H": 2},
    "financial": {"C": 0, "M": 1, "A": 2},
}

WATER_FRAMEWORK_CONSTRUCTS: Dict[str, dict] = {
    "pmt": {
        "primary": "TP_LABEL",
        "secondary": "CP_LABEL",
        "all": ["TP_LABEL", "CP_LABEL", "SP_LABEL", "SC_LABEL", "PA_LABEL"],
    },
    "dual_appraisal": {
        "primary": "WSA_LABEL",
        "secondary": "ACA_LABEL",
        "all": ["WSA_LABEL", "ACA_LABEL"],
    },
    "utility": {
        "primary": "BUDGET_UTIL",
        "secondary": "EQUITY_GAP",
        "all": ["BUDGET_UTIL", "EQUITY_GAP", "ADOPTION_RATE"],
    },
    "financial": {
        "primary": "RISK_APPETITE",
        "secondary": "SOLVENCY_IMPACT",
        "all": ["RISK_APPETITE", "SOLVENCY_IMPACT", "MARKET_SHARE"],
    },
}

WATER_LABEL_MAPPINGS: Dict[str, Dict[str, str]] = {
    "pmt": {
        "VERY LOW": "VL", "VERYLOW": "VL", "VERY_LOW": "VL",
        "LOW": "L",
        "MEDIUM": "M", "MED": "M", "MODERATE": "M",
        "HIGH": "H",
        "VERY HIGH": "VH", "VERYHIGH": "VH", "VERY_HIGH": "VH",
    },
    "dual_appraisal": {
        "VERY LOW": "VL", "VERYLOW": "VL", "VERY_LOW": "VL",
        "LOW": "L",
        "MEDIUM": "M", "MED": "M", "MODERATE": "M",
        "HIGH": "H",
        "VERY HIGH": "VH", "VERYHIGH": "VH", "VERY_HIGH": "VH",
    },
    "utility": {
        "LOW": "L", "LOW PRIORITY": "L", "LOW_PRIORITY": "L",
        "MEDIUM": "M", "MED": "M", "MEDIUM PRIORITY": "M",
        "HIGH": "H", "HIGH PRIORITY": "H", "HIGH_PRIORITY": "H",
    },
    "financial": {
        "CONSERVATIVE": "C", "CONS": "C", "LOW": "C",
        "MODERATE": "M", "MOD": "M", "MEDIUM": "M",
        "AGGRESSIVE": "A", "AGG": "A", "HIGH": "A",
    },
}


def register_water_metadata() -> None:
    """Register all water-domain metadata with ThinkingValidator and rule_types."""
    from broker.validators.governance.thinking_validator import (
        register_framework_metadata,
    )
    from broker.governance.rule_types import register_rule_type_defaults

    # ThinkingValidator metadata
    for fw_name, label_order in WATER_FRAMEWORK_LABEL_ORDERS.items():
        constructs = WATER_FRAMEWORK_CONSTRUCTS.get(fw_name, {})
        label_mappings = WATER_LABEL_MAPPINGS.get(fw_name, {})
        register_framework_metadata(fw_name, constructs, label_order, label_mappings)

    # Rule categorization defaults
    register_rule_type_defaults(
        thinking_constructs=frozenset({
            "TP_LABEL", "CP_LABEL", "WSA_LABEL", "ACA_LABEL",
            "BUDGET_UTIL", "EQUITY_GAP", "RISK_APPETITE", "SOLVENCY_IMPACT",
        }),
        personal_fields=frozenset({
            "savings", "income", "cost", "budget", "water_right",
        }),
    )
