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
    "cognitive_appraisal": {"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4},
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
    "cognitive_appraisal": {
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
    "cognitive_appraisal": {
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

    # Phase 6K-C (2026-05-22): register builtin thinking checks now
    # that ThinkingValidator no longer carries hardcoded rule bodies.
    register_water_thinking_checks()

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


# ---------------------------------------------------------------------
# Water-domain builtin thinking checks (Phase 6K-C 2026-05-22)
# ---------------------------------------------------------------------
# Free functions that conform to the BuiltinCheck signature
# ``(skill_name, rules, context) -> List[ValidationResult]``. They were
# previously hardcoded instance methods on
# ``broker.validators.governance.thinking_validator.ThinkingValidator``
# (``_validate_pmt`` / ``_validate_utility`` / ``_validate_financial``);
# moving them here is the inner-layer counterpart to Phase 6J -- generic
# broker no longer carries flood-PMT rule bodies. The rules close over
# the module-level helpers
# ``broker.validators.governance.thinking_validator.normalize_label`` /
# ``has_rule_for`` (extracted in 6K-C). ``_extreme_actions`` is read
# from the context dict (injected by ``ThinkingValidator.validate``
# from its constructor argument).
# ---------------------------------------------------------------------


def _water_pmt_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """PMT framework consistency check (water domain).

    Replaces ``ThinkingValidator._validate_pmt`` (Phase 6K-C, 2026-05-22).
    Three sub-rules: High TP + High CP must not be ``do_nothing``;
    Very High TP with adequate coping must act (risk-perception
    paradox guard); Low TP must not justify any caller-declared
    extreme action.
    """
    from broker.validators.governance.thinking_validator import (
        has_rule_for,
        normalize_label,
    )

    framework = context.get("framework", "pmt")
    if framework != "pmt":
        return []

    results: List[ValidationResult] = []
    reasoning = context.get("reasoning", {})
    tp_label = normalize_label(reasoning.get("TP_LABEL", "M"), "pmt")
    cp_label = normalize_label(reasoning.get("CP_LABEL", "M"), "pmt")
    extreme_actions = context.get("_extreme_actions") or set()

    # Built-in: High TP + High CP should not do nothing
    if tp_label in ("H", "VH") and cp_label in ("H", "VH"):
        if skill_name == "do_nothing":
            results.append(ValidationResult(
                valid=False,
                validator_name="ThinkingValidator",
                errors=["High threat + high coping should lead to protective action"],
                warnings=[],
                metadata={
                    "rule_id": "builtin_high_tp_cp_action",
                    "category": "thinking",
                    "subcategory": "pmt",
                    "framework": "pmt",
                    "hallucination_type": "thinking",
                    "tp_label": tp_label,
                    "cp_label": cp_label,
                },
            ))

    # Built-in: VH threat + adequate coping requires action
    # Allow do_nothing when TP=VH but CP=VL/L (fatalism / resource constraint)
    # This reflects the empirically documented "risk perception paradox"
    # (Wachinger et al. 2013; Bubeck et al. 2012)
    if tp_label == "VH" and cp_label in ("M", "H", "VH") and skill_name == "do_nothing":
        if not has_rule_for(rules, "extreme_threat"):
            results.append(ValidationResult(
                valid=False,
                validator_name="ThinkingValidator",
                errors=["Very High threat with adequate coping requires protective action"],
                warnings=[],
                metadata={
                    "rule_id": "builtin_extreme_threat_action",
                    "category": "thinking",
                    "subcategory": "pmt",
                    "framework": "pmt",
                    "hallucination_type": "thinking",
                    "tp_label": tp_label,
                    "cp_label": cp_label,
                },
            ))

    # Built-in: Low TP should not justify extreme measures
    if tp_label in ("VL", "L") and extreme_actions:
        if skill_name in extreme_actions:
            if not has_rule_for(rules, "low_tp_blocks"):
                results.append(ValidationResult(
                    valid=False,
                    validator_name="ThinkingValidator",
                    errors=[f"Low threat ({tp_label}) does not justify {skill_name}"],
                    warnings=[],
                    metadata={
                        "rule_id": "builtin_low_tp_extreme_action",
                        "category": "thinking",
                        "subcategory": "pmt",
                        "framework": "pmt",
                        "hallucination_type": "thinking",
                        "tp_label": tp_label,
                        "blocked_action": skill_name,
                    },
                ))

    return results


def _water_utility_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Utility framework consistency check (water domain).

    Replaces ``ThinkingValidator._validate_utility`` (Phase 6K-C).
    """
    from broker.validators.governance.thinking_validator import (
        has_rule_for,
        normalize_label,
    )

    framework = context.get("framework", "utility")
    if framework != "utility":
        return []

    results: List[ValidationResult] = []
    reasoning = context.get("reasoning", {})
    budget_util = normalize_label(reasoning.get("BUDGET_UTIL", "M"), "utility")
    equity_gap = normalize_label(reasoning.get("EQUITY_GAP", "M"), "utility")

    # Built-in: High budget impact + high equity gap should trigger action
    if budget_util == "H" and equity_gap == "H":
        if skill_name == "maintain_policy":
            results.append(ValidationResult(
                valid=False,
                validator_name="ThinkingValidator",
                errors=["High budget impact with high equity gap requires policy change"],
                warnings=[],
                metadata={
                    "rule_id": "builtin_high_utility_action",
                    "category": "thinking",
                    "subcategory": "utility",
                    "framework": "utility",
                    "budget_util": budget_util,
                    "equity_gap": equity_gap,
                },
            ))

    # Built-in: Low budget utility should not justify expensive policies
    if budget_util == "L":
        expensive_actions = {"increase_subsidy", "launch_campaign"}
        if skill_name in expensive_actions:
            if not has_rule_for(rules, "low_budget_blocks"):
                results.append(ValidationResult(
                    valid=False,
                    validator_name="ThinkingValidator",
                    errors=[f"Low budget utility ({budget_util}) does not justify {skill_name}"],
                    warnings=[],
                    metadata={
                        "rule_id": "builtin_low_budget_expensive_action",
                        "category": "thinking",
                        "subcategory": "utility",
                        "framework": "utility",
                        "budget_util": budget_util,
                        "blocked_action": skill_name,
                    },
                ))

    return results


def _water_financial_check(
    skill_name: str,
    rules: List[GovernanceRule],
    context: Dict[str, Any],
) -> List[ValidationResult]:
    """Financial framework consistency check (water domain).

    Replaces ``ThinkingValidator._validate_financial`` (Phase 6K-C).
    """
    from broker.validators.governance.thinking_validator import (
        has_rule_for,
        normalize_label,
    )

    framework = context.get("framework", "financial")
    if framework != "financial":
        return []

    results: List[ValidationResult] = []
    reasoning = context.get("reasoning", {})
    risk_appetite = normalize_label(reasoning.get("RISK_APPETITE", "M"), "financial")
    solvency = normalize_label(reasoning.get("SOLVENCY_IMPACT", "M"), "financial")

    # Built-in: High solvency concern with conservative risk should not expand
    if solvency == "A" and risk_appetite == "C":  # A = high impact, C = conservative
        expansion_actions = {"expand_coverage", "lower_premium"}
        if skill_name in expansion_actions:
            results.append(ValidationResult(
                valid=False,
                validator_name="ThinkingValidator",
                errors=["High solvency concern with conservative risk does not justify expansion"],
                warnings=[],
                metadata={
                    "rule_id": "builtin_solvency_conservative_expansion",
                    "category": "thinking",
                    "subcategory": "financial",
                    "framework": "financial",
                    "risk_appetite": risk_appetite,
                    "solvency_impact": solvency,
                },
            ))

    # Built-in: Aggressive risk appetite should not maintain conservative positions
    if risk_appetite == "A":  # Aggressive
        conservative_actions = {"restrict_coverage", "raise_premium"}
        if skill_name in conservative_actions:
            if not has_rule_for(rules, "aggressive_conservative"):
                results.append(ValidationResult(
                    valid=False,
                    validator_name="ThinkingValidator",
                    errors=[f"Aggressive risk appetite conflicts with conservative action {skill_name}"],
                    warnings=[],
                    metadata={
                        "rule_id": "builtin_aggressive_conservative_conflict",
                        "category": "thinking",
                        "subcategory": "financial",
                        "framework": "financial",
                        "risk_appetite": risk_appetite,
                        "blocked_action": skill_name,
                    },
                ))

    return results


def register_water_thinking_checks() -> None:
    """Register the water-domain PMT / Utility / Financial builtin
    thinking checks. Called by :func:`register_water_metadata` so the
    water domain registration triggers everything in one place."""
    from broker.validators.governance.thinking_validator import (
        register_thinking_checks,
    )
    register_thinking_checks("pmt", [_water_pmt_check])
    register_thinking_checks("utility", [_water_utility_check])
    register_thinking_checks("financial", [_water_financial_check])
