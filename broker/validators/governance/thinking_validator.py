"""
Thinking Validator - Multi-framework construct validation and reasoning coherence.

Task-041: Universal Prompt/Context/Governance Framework

Validates:
- PMT label consistency (TP/CP combinations)
- Utility framework consistency (budget/equity)
- Financial framework consistency (risk/solvency)
- Reasoning coherence (action matches appraisal)

The YAML-driven condition engine (_validate_yaml_rules, _evaluate_conditions,
_evaluate_single_condition) is fully domain-agnostic.  Framework-specific
built-in checks (_validate_pmt, _validate_utility, _validate_financial) are
registered as ``builtin_checks`` and default to flood/MA domain.  Pass
``builtin_checks=[]`` to use YAML rules only, or supply domain-specific checks.
"""
from typing import List, Dict, Any, Optional
from broker.interfaces.skill_types import ValidationResult
from broker.interfaces.rating_scales import RatingScaleRegistry, FrameworkType
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck


# Framework-specific label orderings
FRAMEWORK_LABEL_ORDERS = {
    "pmt": {"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4},
    "utility": {"L": 0, "M": 1, "H": 2},
    "financial": {"C": 0, "M": 1, "A": 2},  # Conservative, Moderate, Aggressive
}

# PMT label ordering for backward compatibility
PMT_LABEL_ORDER = FRAMEWORK_LABEL_ORDERS["pmt"]

# Framework-specific construct mappings
FRAMEWORK_CONSTRUCTS = {
    "pmt": {
        "primary": "TP_LABEL",      # Threat Perception
        "secondary": "CP_LABEL",    # Coping Perception
        "all": ["TP_LABEL", "CP_LABEL", "SP_LABEL", "SC_LABEL", "PA_LABEL"],
    },
    "utility": {
        "primary": "BUDGET_UTIL",   # Budget Utility
        "secondary": "EQUITY_GAP",  # Equity Assessment
        "all": ["BUDGET_UTIL", "EQUITY_GAP", "ADOPTION_RATE"],
    },
    "financial": {
        "primary": "RISK_APPETITE", # Risk Appetite
        "secondary": "SOLVENCY_IMPACT",  # Solvency Impact
        "all": ["RISK_APPETITE", "SOLVENCY_IMPACT", "MARKET_SHARE"],
    },
}


class ThinkingValidator(BaseValidator):
    """
    Validates reasoning consistency for multiple psychological frameworks.

    Task-041: Universal Prompt/Context/Governance Framework

    Supports:
    - PMT (Protection Motivation Theory): TP/CP construct validation
    - Utility: Budget/Equity construct validation
    - Financial: Risk/Solvency construct validation

    The YAML-driven condition engine is fully generic and works with any
    framework.  Framework-specific built-in checks are registered via
    ``builtin_checks``.  Defaults provide PMT/Utility/Financial checks
    for flood and multi-agent domains.

    Examples (PMT):
    - High TP + High CP should not result in do_nothing
    - Low TP should not justify extreme measures (relocate, elevate)
    - VH TP requires action, not inaction

    Examples (Utility):
    - High budget impact with high equity gap should trigger action
    - Low budget utility should not justify expensive policies

    Examples (Financial):
    - Aggressive risk appetite should not maintain conservative positions
    - High solvency concern should trigger defensive actions
    """

    def __init__(
        self,
        framework: str = "pmt",
        builtin_checks: Optional[List[BuiltinCheck]] = None,
    ):
        """
        Initialize ThinkingValidator with a specific framework.

        Args:
            framework: Psychological framework ("pmt", "utility", "financial")
            builtin_checks: Domain-specific checks.  None = flood/MA defaults.
        """
        self.framework = framework.lower()
        self._label_order = FRAMEWORK_LABEL_ORDERS.get(self.framework, PMT_LABEL_ORDER)
        self._constructs = FRAMEWORK_CONSTRUCTS.get(self.framework, FRAMEWORK_CONSTRUCTS["pmt"])
        super().__init__(builtin_checks=builtin_checks)

    @property
    def category(self) -> str:
        return "thinking"

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Flood/MA domain defaults: PMT + Utility + Financial framework checks.

        These are instance-bound closures so they can access ``self`` for
        label normalization and rule deduplication helpers.
        """
        return [
            self._builtin_pmt_check,
            self._builtin_utility_check,
            self._builtin_financial_check,
        ]

    # Wrappers that conform to BuiltinCheck signature (skill, rules, ctx)
    def _builtin_pmt_check(
        self, skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
    ) -> List[ValidationResult]:
        framework = context.get("framework", self.framework)
        if framework != "pmt":
            return []
        return self._validate_pmt(skill_name, rules, context)

    def _builtin_utility_check(
        self, skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
    ) -> List[ValidationResult]:
        framework = context.get("framework", self.framework)
        if framework != "utility":
            return []
        return self._validate_utility(skill_name, rules, context)

    def _builtin_financial_check(
        self, skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
    ) -> List[ValidationResult]:
        framework = context.get("framework", self.framework)
        if framework != "financial":
            return []
        return self._validate_financial(skill_name, rules, context)

    def validate(
        self,
        skill_name: str,
        rules: List[GovernanceRule],
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate thinking rules with framework-specific consistency checks.

        Evaluation order:
        1. YAML-driven rules (via base class — domain-agnostic)
        2. YAML-driven multi-condition rules (Task-041 Phase 3 — domain-agnostic)
        3. Domain-specific built-in checks (injected or defaults)

        Args:
            skill_name: Proposed skill name
            rules: List of governance rules
            context: Must include 'reasoning' with framework-specific constructs

        Returns:
            List of ValidationResult objects
        """
        # Step 1 + 3: Base class handles YAML rules + builtin_checks
        results = super().validate(skill_name, rules, context)

        # Step 2: YAML multi-condition rules (always runs, domain-agnostic)
        framework = context.get("framework", self.framework)
        results.extend(self._validate_yaml_rules(skill_name, rules, context, framework))

        return results

    def _validate_yaml_rules(
        self,
        skill_name: str,
        rules: List[GovernanceRule],
        context: Dict[str, Any],
        framework: str
    ) -> List[ValidationResult]:
        """
        Task-041 Phase 3: Validate YAML-driven rules with multi-condition support.

        Args:
            skill_name: Proposed skill name
            rules: List of governance rules from YAML
            context: Context including reasoning and state
            framework: Current framework

        Returns:
            List of ValidationResult objects for violated rules
        """
        results = []
        reasoning = context.get("reasoning", {})

        for rule in rules:
            # Skip non-thinking rules (use getattr for compatibility with both dataclass and Pydantic)
            rule_category = getattr(rule, 'category', 'thinking')
            if rule_category and rule_category != "thinking":
                continue

            # Skip rules for other frameworks (use getattr for compatibility)
            rule_framework = getattr(rule, 'framework', None)
            if rule_framework and rule_framework != framework:
                continue

            # Skip if skill not in blocked list
            blocked_skills = getattr(rule, 'blocked_skills', [])
            if skill_name not in blocked_skills:
                continue

            # Check if rule is violated
            violated = False
            matched_conditions = []

            # Multi-condition check (AND logic) - Task-041 Phase 3
            rule_conditions = getattr(rule, 'conditions', None)
            if rule_conditions:
                violated = self._evaluate_conditions(
                    rule_conditions, reasoning, context, framework, matched_conditions
                )

            if violated:
                rule_message = getattr(rule, 'message', '') or f"Rule {rule.id} violated"
                results.append(ValidationResult(
                    valid=False,
                    validator_name="ThinkingValidator",
                    errors=[rule_message],
                    warnings=[],
                    metadata={
                        "rule_id": rule.id,
                        "category": "thinking",
                        "framework": framework,
                        "conditions_matched": matched_conditions,
                        "blocked_skill": skill_name
                    }
                ))

        return results

    def _evaluate_conditions(
        self,
        conditions: List[Any],
        reasoning: Dict[str, Any],
        context: Dict[str, Any],
        framework: str,
        matched_conditions: List[str]
    ) -> bool:
        """
        Task-041 Phase 3: Evaluate all conditions with AND logic.

        Args:
            conditions: List of RuleCondition objects or dicts
            reasoning: Agent reasoning dict with construct labels
            context: Full context including state
            framework: Current framework for label normalization
            matched_conditions: Output list to record which conditions matched

        Returns:
            True if ALL conditions match (rule is violated), False otherwise
        """
        for cond in conditions:
            # Handle multiple RuleCondition formats:
            # 1. Pydantic model (broker/config/schema.py): construct, variable, operator, values, value
            # 2. Dataclass (broker/governance/rule_types.py): type, field, operator, values
            # 3. Dict

            # Normalize to dict format
            if hasattr(cond, 'evaluate'):
                # Dataclass RuleCondition with evaluate method - delegate directly
                if not cond.evaluate(context):
                    return False
                matched_conditions.append(getattr(cond, 'field', 'unknown'))
                continue

            if hasattr(cond, 'type') and hasattr(cond, 'field'):
                # Dataclass format: type + field
                cond_type = getattr(cond, 'type', 'construct')
                cond_dict = {
                    "construct": cond.field if cond_type == "construct" else None,
                    "variable": cond.field if cond_type in ("expression", "precondition") else None,
                    "operator": getattr(cond, 'operator', 'in'),
                    "values": getattr(cond, 'values', []),
                    "value": getattr(cond, 'values', [None])[0] if getattr(cond, 'values', []) else None
                }
            elif hasattr(cond, 'construct'):
                # Pydantic model format: construct, variable
                cond_dict = {
                    "construct": getattr(cond, 'construct', None),
                    "variable": getattr(cond, 'variable', None),
                    "operator": getattr(cond, 'operator', 'in'),
                    "values": getattr(cond, 'values', []),
                    "value": getattr(cond, 'value', None)
                }
            elif isinstance(cond, dict):
                cond_dict = cond
            else:
                continue  # Skip unknown format

            if not self._evaluate_single_condition(cond_dict, reasoning, context, framework):
                return False  # AND logic: if any condition fails, rule doesn't apply

            # Record matched condition
            cond_desc = cond_dict.get("construct") or cond_dict.get("variable", "unknown")
            matched_conditions.append(cond_desc)

        return True  # All conditions matched

    def _evaluate_single_condition(
        self,
        cond: Dict[str, Any],
        reasoning: Dict[str, Any],
        context: Dict[str, Any],
        framework: str
    ) -> bool:
        """
        Task-041 Phase 3: Evaluate a single condition.

        Args:
            cond: Condition dict with construct/variable, operator, values/value
            reasoning: Agent reasoning dict
            context: Full context
            framework: Current framework

        Returns:
            True if condition matches, False otherwise
        """
        # Get the value to compare
        if cond.get("construct"):
            raw_value = reasoning.get(cond["construct"], "M")
            value = self._normalize_label(raw_value, framework)
        elif cond.get("variable"):
            state = context.get("state", {})
            value = state.get(cond["variable"])
            if value is None:
                value = context.get(cond["variable"])
            if value is None:
                return False  # Variable not found, condition doesn't match
        else:
            return False  # No construct or variable specified

        # Apply operator
        operator = cond.get("operator", "in")
        values = cond.get("values") or []
        single_value = cond.get("value")

        if operator == "in":
            return value in values
        elif operator == "not_in":
            return value not in values
        elif operator == "==":
            return value == single_value
        elif operator == "!=":
            return value != single_value
        elif operator == "<":
            return value < single_value
        elif operator == ">":
            return value > single_value
        elif operator == "<=":
            return value <= single_value
        elif operator == ">=":
            return value >= single_value

        return False

    def _validate_pmt(
        self,
        skill_name: str,
        rules: List[GovernanceRule],
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """PMT-specific validation (backward compatible)."""
        results = []
        reasoning = context.get("reasoning", {})
        tp_label = self._normalize_label(reasoning.get("TP_LABEL", "M"), "pmt")
        cp_label = self._normalize_label(reasoning.get("CP_LABEL", "M"), "pmt")

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
                        "cp_label": cp_label
                    }
                ))

        # Built-in: VH threat requires action
        if tp_label == "VH" and skill_name == "do_nothing":
            if not self._has_rule_for(rules, "extreme_threat"):
                results.append(ValidationResult(
                    valid=False,
                    validator_name="ThinkingValidator",
                    errors=["Very High threat perception requires protective action"],
                    warnings=[],
                    metadata={
                        "rule_id": "builtin_extreme_threat_action",
                        "category": "thinking",
                        "subcategory": "pmt",
                        "framework": "pmt",
                        "hallucination_type": "thinking",
                        "tp_label": tp_label
                    }
                ))

        # Built-in: Low TP should not justify extreme measures
        if tp_label in ("VL", "L"):
            extreme_actions = {"relocate", "elevate_house"}
            if skill_name in extreme_actions:
                if not self._has_rule_for(rules, "low_tp_blocks"):
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
                            "blocked_action": skill_name
                        }
                    ))

        return results

    def _validate_utility(
        self,
        skill_name: str,
        rules: List[GovernanceRule],
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """Utility framework validation for government agents."""
        results = []
        reasoning = context.get("reasoning", {})
        budget_util = self._normalize_label(reasoning.get("BUDGET_UTIL", "M"), "utility")
        equity_gap = self._normalize_label(reasoning.get("EQUITY_GAP", "M"), "utility")

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
                        "equity_gap": equity_gap
                    }
                ))

        # Built-in: Low budget utility should not justify expensive policies
        if budget_util == "L":
            expensive_actions = {"increase_subsidy", "launch_campaign"}
            if skill_name in expensive_actions:
                if not self._has_rule_for(rules, "low_budget_blocks"):
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
                            "blocked_action": skill_name
                        }
                    ))

        return results

    def _validate_financial(
        self,
        skill_name: str,
        rules: List[GovernanceRule],
        context: Dict[str, Any]
    ) -> List[ValidationResult]:
        """Financial framework validation for insurance agents."""
        results = []
        reasoning = context.get("reasoning", {})
        risk_appetite = self._normalize_label(reasoning.get("RISK_APPETITE", "M"), "financial")
        solvency = self._normalize_label(reasoning.get("SOLVENCY_IMPACT", "M"), "financial")

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
                        "solvency_impact": solvency
                    }
                ))

        # Built-in: Aggressive risk appetite should not maintain conservative positions
        if risk_appetite == "A":  # Aggressive
            conservative_actions = {"restrict_coverage", "raise_premium"}
            if skill_name in conservative_actions:
                if not self._has_rule_for(rules, "aggressive_conservative"):
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
                            "blocked_action": skill_name
                        }
                    ))

        return results

    def _normalize_label(self, label: Optional[str], framework: str = None) -> str:
        """
        Normalize label to standard format for the given framework.

        Args:
            label: Raw label string
            framework: Framework to use for normalization (defaults to self.framework)

        Returns:
            Normalized label string
        """
        if not label:
            return "M"  # Default to Medium/Moderate
        label = str(label).upper().strip()

        fw = framework or self.framework

        # Framework-specific mappings
        if fw == "pmt":
            mappings = {
                "VERY LOW": "VL", "VERYLOW": "VL", "VERY_LOW": "VL",
                "LOW": "L",
                "MEDIUM": "M", "MED": "M", "MODERATE": "M",
                "HIGH": "H",
                "VERY HIGH": "VH", "VERYHIGH": "VH", "VERY_HIGH": "VH"
            }
        elif fw == "utility":
            mappings = {
                "LOW": "L", "LOW PRIORITY": "L", "LOW_PRIORITY": "L",
                "MEDIUM": "M", "MED": "M", "MEDIUM PRIORITY": "M",
                "HIGH": "H", "HIGH PRIORITY": "H", "HIGH_PRIORITY": "H"
            }
        elif fw == "financial":
            mappings = {
                "CONSERVATIVE": "C", "CONS": "C", "LOW": "C",
                "MODERATE": "M", "MOD": "M", "MEDIUM": "M",
                "AGGRESSIVE": "A", "AGG": "A", "HIGH": "A"
            }
        else:
            # Generic fallback to PMT
            mappings = {
                "VERY LOW": "VL", "LOW": "L", "MEDIUM": "M",
                "HIGH": "H", "VERY HIGH": "VH"
            }

        return mappings.get(label, label)

    def _has_rule_for(self, rules: List[GovernanceRule], rule_id_prefix: str) -> bool:
        """Check if a rule covering this constraint already exists."""
        return any(r.id.startswith(rule_id_prefix) for r in rules if r.category == "thinking")

    def _compare_labels(self, label1: str, label2: str, framework: str = None) -> int:
        """
        Compare two labels for the given framework. Returns -1, 0, or 1.

        Args:
            label1: First label
            label2: Second label
            framework: Framework to use for comparison (defaults to self.framework)

        Returns:
            -1 if label1 < label2, 0 if equal, 1 if label1 > label2
        """
        fw = framework or self.framework
        label_order = FRAMEWORK_LABEL_ORDERS.get(fw, PMT_LABEL_ORDER)
        default_order = len(label_order) // 2  # Default to middle

        order1 = label_order.get(label1, default_order)
        order2 = label_order.get(label2, default_order)

        if order1 < order2:
            return -1
        elif order1 > order2:
            return 1
        return 0

    def get_valid_levels(self, framework: str = None) -> List[str]:
        """
        Get valid rating levels for the given framework.

        Args:
            framework: Framework to get levels for (defaults to self.framework)

        Returns:
            List of valid level strings
        """
        fw = framework or self.framework
        try:
            scale = RatingScaleRegistry.get_by_name(fw)
            return scale.levels
        except Exception:
            # Fallback to hardcoded
            label_order = FRAMEWORK_LABEL_ORDERS.get(fw, PMT_LABEL_ORDER)
            return list(label_order.keys())

    def validate_label_value(self, label: str, framework: str = None) -> bool:
        """
        Validate that a label is valid for the given framework.

        Args:
            label: Label value to validate
            framework: Framework to validate against (defaults to self.framework)

        Returns:
            True if valid, False otherwise
        """
        valid_levels = self.get_valid_levels(framework)
        return label.upper() in [level.upper() for level in valid_levels]
