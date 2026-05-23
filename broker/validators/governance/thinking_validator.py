"""
Thinking Validator - Multi-framework construct validation and reasoning coherence.

Validates that an agent's chosen action is logically consistent with its
self-reported behavioral appraisals.  Supports multiple psychological
frameworks registered via ``register_framework_metadata()``.

The YAML-driven condition engine (_validate_yaml_rules, _evaluate_conditions,
_evaluate_single_condition) is fully domain-agnostic.  Framework-specific
built-in checks are registered as ``builtin_checks`` and default to
water-domain checks when the water domain pack is loaded.  Pass
``builtin_checks=[]`` to use YAML rules only, or supply domain-specific
checks for new frameworks.

Domain packs register their metadata at import time via
``register_framework_metadata()``.  See ``broker.domains.water`` for a
reference implementation.
"""
from typing import List, Dict, Any, Optional
from broker.interfaces.skill_types import ValidationResult
from broker.interfaces.rating_scales import RatingScaleRegistry, FrameworkType
from broker.governance.rule_types import GovernanceRule
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck


# ──────────────────────────────────────────────────────────────────────
# Framework Metadata Registry
# ──────────────────────────────────────────────────────────────────────
# Domain packs populate these at import time via register_framework_metadata().
# Start empty — no hardcoded domain content.
# ──────────────────────────────────────────────────────────────────────

FRAMEWORK_LABEL_ORDERS: Dict[str, Dict[str, int]] = {}
FRAMEWORK_CONSTRUCTS: Dict[str, dict] = {}
_LABEL_MAPPINGS: Dict[str, Dict[str, str]] = {}

# Default label ordering (5-level VL–VH scale, used when framework is unknown)
_DEFAULT_LABEL_ORDER: Dict[str, int] = {"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4}

# Backward-compatibility aliases
DEFAULT_LABEL_ORDER = _DEFAULT_LABEL_ORDER
PMT_LABEL_ORDER = _DEFAULT_LABEL_ORDER

# Generic fallback label mappings (used when no domain-specific mapping registered)
_GENERIC_LABEL_MAPPINGS: Dict[str, str] = {
    "VERY LOW": "VL", "LOW": "L", "MEDIUM": "M",
    "HIGH": "H", "VERY HIGH": "VH",
}


# ──────────────────────────────────────────────────────────────────────
# Per-framework thinking-check registry (Phase 6K-C 2026-05-22)
# ──────────────────────────────────────────────────────────────────────
# Domain packs register their framework-specific builtin checks here at
# import time (e.g. broker.domains.water registers PMT / Utility /
# Financial checks). ThinkingValidator(framework="pmt") then queries
# this registry for the default builtin_checks list. Empty for an
# unregistered framework — pass builtin_checks=[] (or rely on
# YAML rules) for genuinely-YAML-only domains.
# ──────────────────────────────────────────────────────────────────────

_THINKING_CHECKS_BY_FRAMEWORK: Dict[str, List[BuiltinCheck]] = {}


def register_thinking_checks(framework: str, checks: List[BuiltinCheck]) -> None:
    """Register a list of framework-specific builtin thinking checks.

    Phase 6K-C (2026-05-22): the PMT / Utility / Financial rule bodies
    previously hardcoded in ThinkingValidator._validate_pmt etc.
    relocated to broker.domains.water.thinking_checks; the water
    domain calls this function once at import time per framework.
    Re-registering the same framework REPLACES its check list so
    repeated register() calls (e.g. from test setup) stay
    idempotent.
    """
    _THINKING_CHECKS_BY_FRAMEWORK[framework] = list(checks)


def normalize_label(label: Optional[str], framework: str) -> str:
    """Module-level helper: normalize a free-text label to the
    framework's canonical token (``VL``/``L``/``M``/``H``/``VH`` for
    the default scale, or whatever the framework registered via
    :func:`register_framework_metadata`). Returns ``"M"`` for empty
    input. Phase 6K-C (2026-05-22): extracted from the instance method
    so relocated rule bodies (in broker.domains.water) can call it
    without needing a ThinkingValidator reference.
    """
    if not label:
        return "M"
    label = str(label).upper().strip()
    mappings = _LABEL_MAPPINGS.get(framework, _GENERIC_LABEL_MAPPINGS)
    return mappings.get(label, label)


def has_rule_for(rules: List[GovernanceRule], rule_id_prefix: str) -> bool:
    """Module-level helper: True iff any thinking-category rule's
    ``id`` starts with ``rule_id_prefix``. Phase 6K-C (2026-05-22):
    extracted from the instance method for the same reason as
    :func:`normalize_label`.
    """
    return any(r.id.startswith(rule_id_prefix) for r in rules if r.category == "thinking")


def register_framework_metadata(
    name: str,
    constructs: dict,
    label_order: Dict[str, int],
    label_mappings: Optional[Dict[str, str]] = None,
) -> None:
    """
    Register framework metadata for use by ThinkingValidator.

    Called by domain packs at import time.  For example, the water domain
    pack registers PMT, dual_appraisal, utility, and financial frameworks.

    Args:
        name: Framework identifier (e.g., "pmt", "utility")
        constructs: Dict with "primary", "secondary", "all" keys
        label_order: Ordinal mapping from label strings to ints
        label_mappings: Optional normalization mappings (e.g., "VERY HIGH" -> "VH")
    """
    FRAMEWORK_LABEL_ORDERS[name] = label_order
    FRAMEWORK_CONSTRUCTS[name] = constructs
    if label_mappings:
        _LABEL_MAPPINGS[name] = label_mappings


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
        extreme_actions: Optional[set] = None,
    ):
        """
        Initialize ThinkingValidator with a specific framework.

        Args:
            framework: Psychological framework ("pmt", "utility", "financial")
            builtin_checks: Domain-specific checks.  None = built-in defaults
                (PMT + Utility + Financial).  Pass ``[]`` for YAML-only.
            extreme_actions: Domain-specific actions blocked when threat
                perception is low.  Empty by default (domain-agnostic).
                Configured per domain in ``agent_types.yaml``.

        Raises:
            ValueError: if ``framework`` is non-empty and not registered
                via :func:`register_framework_metadata`. Phase 6C-v3
                (2026-05-10): without registered metadata, label
                comparisons would silently fall back to PMT's VL/L/M/H/VH
                ordinal scale even if the new framework uses a different
                scale — a silent-wrong-answer bug. We now fail loudly.
        """
        self.framework = framework.lower()
        # Phase 6C-v3 strict registration check. PMT / utility / financial
        # ship pre-registered by broker.domains.water; new domains must call
        # register_framework_metadata("<name>", constructs, label_order, ...)
        # before constructing the validator. We allow blank framework=""
        # for YAML-only callers.
        if self.framework and self.framework not in FRAMEWORK_LABEL_ORDERS:
            registered = sorted(FRAMEWORK_LABEL_ORDERS.keys())
            raise ValueError(
                f"ThinkingValidator framework '{self.framework}' is not "
                f"registered. Call broker.validators.governance.thinking_validator"
                f".register_framework_metadata('{self.framework}', constructs, "
                f"label_order, label_mappings) from your domain pack's "
                f"__init__.py before constructing ThinkingValidator(framework="
                f"'{self.framework}'). Otherwise label comparisons will "
                f"silently use the PMT ordinal scale, producing wrong "
                f"validation outcomes. Currently registered: {registered}."
            )
        self._label_order = FRAMEWORK_LABEL_ORDERS.get(self.framework, _DEFAULT_LABEL_ORDER)
        self._constructs = FRAMEWORK_CONSTRUCTS.get(self.framework, {})
        self._extreme_actions = extreme_actions or set()
        super().__init__(builtin_checks=builtin_checks)

    @property
    def category(self) -> str:
        return "thinking"

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Default built-in framework checks for ``self.framework``.

        Phase 6K-C (2026-05-22): defaults now come from the
        ``_THINKING_CHECKS_BY_FRAMEWORK`` registry that domain packs
        populate at import time (see
        :func:`register_thinking_checks`). The PMT / Utility /
        Financial rule bodies that previously lived as
        ``_validate_pmt`` / ``_validate_utility`` / ``_validate_financial``
        instance methods now live in
        ``broker.domains.water.thinking_checks``.

        Returns every registered check across all frameworks (not just
        ``self.framework``) so per-call ``context.get("framework", ...)``
        overrides keep working — each check short-circuits internally
        when the context framework does not match its own. With nothing
        registered the list is empty and callers fall back to YAML
        rules only.
        """
        checks: List[BuiltinCheck] = []
        for fw_checks in _THINKING_CHECKS_BY_FRAMEWORK.values():
            checks.extend(fw_checks)
        return checks

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
        # Phase 6K-C (2026-05-22): inject ``framework`` + ``_extreme_actions``
        # into the context so registered builtin checks (which now live in
        # the domain pack — see broker.domains.water.thinking_checks) can
        # read them without holding a reference to the validator. The
        # relocated free-function checks each hardcode their own framework
        # name as the ``.get("framework", ...)`` fallback, so without this
        # injection a caller that omits ``framework`` from context (legal —
        # the broker context builder always sets it, but unit tests may
        # not) would have every check evaluate past its own short-circuit.
        # A caller-supplied value in context still wins.
        if "framework" not in context:
            context = {**context, "framework": self.framework}
        if self._extreme_actions and "_extreme_actions" not in context:
            context = {**context, "_extreme_actions": self._extreme_actions}

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

    def _normalize_label(self, label: Optional[str], framework: str = None) -> str:
        """Normalize label to standard format for the given framework.

        Phase 6K-C (2026-05-22): thin wrapper around the module-level
        :func:`normalize_label` helper so subclasses and external
        callers that already use the instance method keep working.
        New code should call :func:`normalize_label` directly.
        """
        return normalize_label(label, framework or self.framework)

    def _has_rule_for(self, rules: List[GovernanceRule], rule_id_prefix: str) -> bool:
        """Phase 6K-C (2026-05-22): thin wrapper around the module-level
        :func:`has_rule_for` helper. New code should call the module
        function directly."""
        return has_rule_for(rules, rule_id_prefix)

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
        label_order = FRAMEWORK_LABEL_ORDERS.get(fw, DEFAULT_LABEL_ORDER)
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
            label_order = FRAMEWORK_LABEL_ORDERS.get(fw, DEFAULT_LABEL_ORDER)
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
