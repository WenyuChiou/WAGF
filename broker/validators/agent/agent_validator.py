"""
Generic Agent Validator

Label-based validation - one validator for all agent types.
Rules are configured per agent_type label, not per file.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class ValidationLevel(Enum):
    ERROR = "ERROR"      # Must fix, decision rejected
    WARNING = "WARNING"  # Log but allow


from broker.interfaces.skill_types import IDENTITY_TIER, ValidationResult
from broker.utils.agent_config import (
    load_agent_config,
    ValidationRule,
    CoherenceRule,
    GovernanceAuditor,
    world_condition_target,
)
from broker.utils.logging import setup_logger

logger = setup_logger(__name__)

# PR-6: sentinel for "this world variable was not found anywhere in the
# validation context". A plain ``None`` cannot be the sentinel — a domain may
# legitimately store ``None`` in state, and treating that as "absent" would make
# a rule silently not fire on exactly the rows where the world state is unknown.
_MISSING = object()


def _lookup_world_variable(name, scope, state, full_context):
    """Resolve a world variable, returning ``_MISSING`` when it is not present.

    Lookup order for ``scope: auto`` is env_state -> agent state -> flattened
    context, and it is DOCUMENTED rather than incidental. The broker builds its
    validation context as ``{"env_state": env, **agent_state, **env}``, so a name
    carried by both planes resolves to the env copy and the agent's own value is
    unreachable — the key-collision trap. ``scope: state`` / ``scope: env`` name
    the plane explicitly and are the recommended form for any new rule.
    """
    ctx = full_context if isinstance(full_context, dict) else {}
    env = ctx.get("env_state")
    env = env if isinstance(env, dict) else {}
    social = ctx.get("social_context")
    social = social if isinstance(social, dict) else {}
    st = state if isinstance(state, dict) else {}

    if scope == "env":
        planes = (env,)
    elif scope == "state":
        planes = (st,)
    elif scope == "social":
        planes = (social,)
    elif scope == "context":
        planes = (ctx,)
    else:  # auto
        planes = (env, st, ctx)

    for plane in planes:
        if name in plane:
            return plane[name]
    return _MISSING


def _coerce_pair(actual, target):
    """Best-effort numeric coercion for a comparison, else the originals.

    YAML gives ``0.4`` as a float and a simulator may hand back ``"0.4"``; a
    string/float comparison would raise TypeError inside a validator and take
    the whole run down, so the fallback is the uncoerced pair rather than an
    exception.
    """
    try:
        return float(actual), float(target)
    except (TypeError, ValueError):
        return actual, target


def _evaluate_world_condition(cond, name, scope, state, full_context):
    """Evaluate one world-state condition. Returns ``(matched, readable)``.

    Fails CLOSED in the direction that matters: a rule whose world antecedent
    cannot be read does not block. The alternative — treating an unreadable
    variable as satisfied — would block actions on evidence nobody has.

    ``readable`` is the second half of that contract and the reason this is a
    tuple rather than a bool (P1-a). "Did not fire because the world says no"
    and "did not fire because the variable was never published" are the same
    row otherwise — and the second one means the grounded rule was decorative
    for that decision. The caller turns a False here into an audited
    ``world_variable_missing`` WARNING and a run-integrity tally.
    """
    actual = _lookup_world_variable(name, scope, state, full_context)
    if actual is _MISSING:
        return False, False

    operator = str(cond.get("operator", "==")).strip()
    values = cond.get("values")
    values = list(values) if isinstance(values, (list, tuple)) else []
    target = cond.get("value", values[0] if values else None)

    if operator == "in":
        return actual in values, True
    if operator == "not_in":
        return actual not in values, True
    if operator == "is_true":
        # Identity against the singleton, deliberately: `1 == True` and
        # `numpy.True_ == True` are both True under `==`, so an `is_true` rule
        # written to read a flag would start matching a magnitude of 1. See the
        # strictness note beside WORLD_CONDITION_SCOPES in agent_config.py.
        return actual is True, True
    if operator == "is_false":
        return actual is False, True
    if operator in ("==", "!="):
        # A bool is compared only against a bool. Python would happily coerce
        # `1.0 == True` to True, so without this a rule written to read a flag
        # would start matching a magnitude that happens to equal 1 — and the
        # audit row would show the rule firing with nothing to explain why.
        both_bool = isinstance(actual, bool) and isinstance(target, bool)
        either_bool = isinstance(actual, bool) or isinstance(target, bool)
        if either_bool and not both_bool:
            return (operator == "!="), True
        if both_bool:
            same = actual is target
        else:
            a, t = _coerce_pair(actual, target)
            same = a == t
        return (same if operator == "==" else not same), True

    a, t = _coerce_pair(actual, target)
    try:
        if operator == ">":
            return a > t, True
        if operator == "<":
            return a < t, True
        if operator == ">=":
            return a >= t, True
        if operator == "<=":
            return a <= t, True
    except TypeError:
        return False, True
    logger.warning(
        "[AgentValidator] world condition on %r uses unknown operator %r; "
        "treated as NOT matched. Valid: in, not_in, ==, !=, <, >, <=, >=, "
        "is_true, is_false.", name, operator,
    )
    return False, True


def _affordability_constraints_from_domain_pack():
    """Per-decision affordability cost models from the first registered
    DomainPack with non-empty ``affordability_constraints()`` — mirrors
    the perception / reflection pack-scan. Empty dict when none (the
    affordability check is then a no-op). Phase 6H Item 6."""
    try:
        from broker.domains.registry import DomainPackRegistry
    except ImportError:
        return {}
    for name in DomainPackRegistry.domains():
        pack = DomainPackRegistry.get(name)
        if pack is None:
            continue
        constraints = pack.affordability_constraints() or {}
        if constraints:
            return constraints
    return {}


class AgentValidator:
    """
    Generic validator for any agent type.
    
    Uses agent_type label to lookup validation rules from agent_types.yaml.
    """
    
    def __init__(self, config_path: str = None, enable_financial_constraints: bool = False):
        self.config = load_agent_config(config_path)
        self.errors: List[ValidationResult] = []
        self.warnings: List[ValidationResult] = []
        self.auditor = GovernanceAuditor()
        self.enable_financial_constraints = enable_financial_constraints
        # PR-6: resolved ONCE, and coerced to a real bool rather than stored raw
        # — tests build this validator with stand-in config objects whose getters
        # return truthy mocks, and a mock would silently switch the flag on and
        # move every label comparison in the suite.
        _fa = getattr(self.config, "get_validators_framework_aware_labels", None)
        _fa_value = _fa() if callable(_fa) else False
        self.framework_aware_labels = _fa_value if isinstance(_fa_value, bool) else False
        # global_config.governance.rule_id_prefix (default True = the shipped
        # "[Rule: <id>] " prefix on every identity/thinking message). Coerced
        # the same way as framework_aware_labels: a stand-in config whose
        # getter returns a mock keeps the shipped prefix.
        _rp = getattr(self.config, "get_governance_rule_id_prefix", None)
        _rp_value = _rp() if callable(_rp) else True
        self.rule_id_prefix = _rp_value if isinstance(_rp_value, bool) else True

    def _rule_message(self, rule_id: str, body: str) -> str:
        """A rule's message as rendered into results and retry prompts: the
        ``[Rule: <id>] `` prefix (unless ``rule_id_prefix`` is off) + body."""
        prefix = f"[Rule: {rule_id}] " if getattr(self, "rule_id_prefix", True) else ""
        return prefix + body
    
    def validate(self, *args, **kwargs) -> List[ValidationResult]:
        """
        Generic entry point supporting both signatures:
        1. validate(proposal, context, registry) - used by SkillBrokerEngine
        2. validate(agent_type, agent_id, decision, state, ...) - legacy/direct
        """
        # Check for generic signature (proposal object as first arg)
        if len(args) >= 2 and hasattr(args[0], 'skill_name'):
            proposal = args[0]
            context = args[1]
            
            agent_type = context.get('agent_type', 'household')
            agent_id = getattr(proposal, 'agent_id', context.get('agent_id', 'unknown'))
            alias_map = self.config.get_action_alias_map(agent_type)
            decision = proposal.skill_name
            if alias_map:
                decision = alias_map.get(decision.lower(), decision)

            # Task 015 fix: Support both 'state' and 'agent_state' keys
            # The broker passes context as 'agent_state', but legacy code may use 'state'
            # The context structure from build_tiered_context is:
            #   {"personal": {...}, "state": {...}, "local": {...}, ...}
            # But governed_broker wraps it as:
            #   {"agent_state": <context>, "agent_type": ...}
            # So we need to unwrap it properly.
            state = context.get('state', {})
            if not state:
                agent_state = context.get('agent_state', {})
                if isinstance(agent_state, dict):
                    # agent_state is the full context, get state or personal from it
                    state = agent_state.get('state', agent_state.get('personal', agent_state))
            reasoning = getattr(proposal, 'reasoning', {})
            parse_layer = getattr(proposal, 'parse_layer', "")
            
            return self._validate_internal(
                agent_type,
                agent_id,
                decision,
                state,
                None,
                reasoning,
                parse_layer,
                full_validation_context=context
            )

            
        return self._validate_internal(*args, **kwargs)

    def _validate_internal(
        self,
        agent_type: str,
        agent_id: str,
        decision: str,
        state: Dict[str, Any],
        prev_state: Dict[str, Any] = None,
        reasoning: Dict[str, str] = None,
        parse_layer: str = "",
        full_validation_context: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResult]:

        """
        Validate agent decision based on agent_type rules.
        """
        results = []
        
        base_type = self.config.get_base_type(agent_type)

        # 0. Validate Response Format (Tier 0)
        # Check if required fields from YAML are present in reasoning
        try:
            from broker.components.response_format import ResponseFormatBuilder
            shared_config = {"response_format": self.config._config.get("shared", {}).get("response_format", {})}
            agent_config = self.config.get(base_type)
            rfb = ResponseFormatBuilder(agent_config, shared_config)
            required_fields = rfb.get_required_fields()
            field_types = rfb.get_field_types()

            # Map required fields to reasoning keys
            missing = []
            for field in required_fields:
                if field == "decision":
                    # Decision is valid if we have a skill_name extracted
                    if not decision:
                        missing.append(field)
                    continue

                # Text fields are free-text output, not structured construct keys
                if field_types.get(field, "text") == "text":
                    continue

                if field not in reasoning:
                    # Also check for construct mapping (e.g. TP_LABEL)
                    mapping = rfb.get_construct_mapping()
                    construct = mapping.get(field)
                    if construct and construct not in reasoning:
                        missing.append(field)
                    elif not construct:
                        missing.append(field)

            if missing:
                results.append(ValidationResult(
                    valid=False,
                    validator_name="AgentValidator:format",
                    errors=[f"Response missing required fields: {', '.join(missing)}"],
                    metadata={
                        "level": ValidationLevel.ERROR,
                        "rule": "format",
                        "field": "json_structure",
                        "constraint": f"required={required_fields}",
                        # Phase 6O-A-2: format violations are hard schema breaches.
                        "expected_terminal": True,
                        "constraint_type": "hard",
                        # DELIBERATELY no "rule_id" (2026-06-10): this result
                        # fires on EVERY row of the frozen mock baselines
                        # (mock output lacks the PMT appraisal fields), so the
                        # audit CSV's failed_rules column shows "Unknown" for
                        # it BY FREEZE — adding a rule_id here flips every
                        # frozen-baseline row and breaks mock byte-identity
                        # re-verification. Name it ("format_required_fields")
                        # at the next AUDIT_SCHEMA_VERSION bump, never before.
                        # See docs/AUDIT_SCHEMA.md "failed_rules" entry.
                    }
                ))
        except Exception as e:
            # This wraps the ENTIRE Tier-0 response-format block -- the check that emits the
            # AgentValidator:format ERROR with constraint_type=hard. If it raises, Tier 0
            # produces zero results and a decision missing every required construct field is
            # APPROVED, executed, and written to the audit CSV as a clean row. The logger
            # call was commented out, so at no log level did anything appear.
            #
            # It has never fired: 137,592 corpus rows contain zero APPROVED rows with an
            # empty construct label (checked 2026-08-06). But two triggers are visible in
            # this function -- `reasoning: Dict[str, str] = None` at the signature reaching
            # `if field not in reasoning`, and `self.config.get(base_type)` for an
            # agent_type absent from config -- so it is latent, not impossible.
            #
            # `pass` is kept deliberately rather than re-raising. Raising here would turn a
            # format-check failure into a run-ending crash mid-experiment, and the failure
            # direction of THAT is worse: an operator loses ten hours to a defect in a check
            # rather than to a defect in the science. Making it visible is the fix; making it
            # fatal is a different decision and not one to take silently.
            #
            # THE GAP THIS LOGGER DOES NOT CLOSE, and it is the reason not to stop here.
            # The decision is still written to the audit CSV indistinguishable from a
            # format-checked one. A later reader of the corpus has no way to act on the
            # instruction in the message below, because the corpus carries no marker -- only
            # this log line does, in a file nobody greps. The real fix is a column saying the
            # row was not format-checked, which the note ~20 lines above correctly forbids
            # before the next AUDIT_SCHEMA_VERSION bump. **Add it at that bump.** Until then
            # the hole is visible rather than closed, and anyone reading this should not
            # mistake a logger for a repair.
            logger.error(
                "[AgentValidator] Tier-0 response-format validation raised and was "
                "swallowed for agent_type=%r agent_id=%r: %s. This decision was NOT "
                "format-checked; treat its row as unvalidated.",
                agent_type, agent_id, e, exc_info=True,
            )

        # 0.1. Validate Financial Affordability (Tier 0.1)
        if self.enable_financial_constraints and full_validation_context:
            is_affordable, affordability_reason = self.validate_affordability(
                agent_id, decision, full_validation_context
            )
            if not is_affordable:
                results.append(ValidationResult(
                    valid=False,
                    validator_name="AgentValidator:affordability",
                    errors=[affordability_reason],
                    metadata={
                        "level": ValidationLevel.ERROR,
                        "rules_hit": ["affordability"],
                        "field": "decision",
                        "constraint": "financial_affordability",
                        "deterministic": True,
                        # Phase 6O-A-2: cannot-afford is hard / terminal —
                        # economic infeasibility, model cannot recover.
                        "expected_terminal": True,
                        "constraint_type": "hard",
                    }
                ))

        # 1. Validate decision is in allowed values
        valid_actions = self.config.get_valid_actions(base_type)

        if valid_actions:
            normalized = decision.lower().replace("_", "").replace(" ", "")
            valid_normalized = [v.lower().replace("_", "").replace(" ", "") for v in valid_actions]
            if normalized not in valid_normalized:
                results.append(ValidationResult(
                    valid=False,
                    validator_name="AgentValidator:valid_decisions",
                    errors=[f"Invalid decision '{decision}' for {agent_type}"],
                    metadata={
                        "level": ValidationLevel.ERROR,
                        "rule": "valid_decisions",
                        "field": "decision",
                        "constraint": str(valid_actions[:4]) + "...",
                        # Phase 6O-A-2: skill not in agent eligibility list is hard.
                        "expected_terminal": True,
                        "constraint_type": "hard",
                    }
                ))
        
        # 2. Dual-Tier Validation (Identity & Thinking)
        # Tier 1: Identity/Condition Validation (Status/Right-to-act)
        # Driven by 'identity_rules' in YAML
        results.extend(self.validate_identity(base_type, agent_id, decision, state))
        
        # Tier 2: Thinking/Cognitive Validation (Reasoning/Coherence)
        # Driven by 'thinking_rules' in YAML
        if reasoning:
            results.extend(self.validate_thinking(
                base_type, agent_id, decision, state, reasoning,
                full_context=full_validation_context,
            ))
        
        # 3. Numeric Attribute Bounds (Legacy/Structural)
        # Driven by 'validation_rules' in YAML
        rules = self.config.get_validation_rules(base_type)
        for rule_name, rule in rules.items():
            param = rule.param
            if not param or param not in state:
                continue
            
            value = state[param]
            lv = ValidationLevel.ERROR if rule.level == "ERROR" else ValidationLevel.WARNING
            
            # Min/Max bounds
            if rule.min_val is not None and value < rule.min_val:
                results.append(ValidationResult(
                    valid=(lv == ValidationLevel.WARNING),
                    validator_name=f"AgentValidator:{rule_name}",
                    errors=[rule.message or f"{param} {value:.2f} below min {rule.min_val:.2f}"] if lv == ValidationLevel.ERROR else [],
                    warnings=[rule.message or f"{param} {value:.2f} below min {rule.min_val:.2f}"] if lv == ValidationLevel.WARNING else [],
                    metadata={
                        "level": lv,
                        "rule": rule_name,
                        "field": param,
                        "value": value,
                        "constraint": f"min={rule.min_val}",
                        # Phase 6O-A-2: out-of-bounds = hard for ERROR,
                        # diagnostic-only for WARNING.
                        "expected_terminal": lv == ValidationLevel.ERROR,
                        "constraint_type": "hard" if lv == ValidationLevel.ERROR else "diagnostic",
                    }
                ))
            
            if rule.max_val is not None and value > rule.max_val:
                results.append(ValidationResult(
                    valid=(lv == ValidationLevel.WARNING),
                    validator_name=f"AgentValidator:{rule_name}",
                    errors=[rule.message or f"{param} {value:.2f} above max {rule.max_val:.2f}"] if lv == ValidationLevel.ERROR else [],
                    warnings=[rule.message or f"{param} {value:.2f} above max {rule.max_val:.2f}"] if lv == ValidationLevel.WARNING else [],
                    metadata={
                        "level": lv,
                        "rule": rule_name,
                        "field": param,
                        "value": value,
                        "constraint": f"max={rule.max_val}",
                        # Phase 6O-A-2: out-of-bounds = hard for ERROR,
                        # diagnostic-only for WARNING.
                        "expected_terminal": lv == ValidationLevel.ERROR,
                        "constraint_type": "hard" if lv == ValidationLevel.ERROR else "diagnostic",
                    }
                ))
            
            # Delta check
            if rule.max_delta is not None and prev_state and param in prev_state:
                delta = abs(value - prev_state[param])
                if delta > rule.max_delta:
                    results.append(ValidationResult(
                        valid=(lv == ValidationLevel.WARNING),
                        validator_name=f"AgentValidator:{rule_name}",
                        errors=[rule.message or f"{param} change {delta:.2%} exceeds max {rule.max_delta:.0%}"] if lv == ValidationLevel.ERROR else [],
                        warnings=[rule.message or f"{param} change {delta:.2%} exceeds max {rule.max_delta:.0%}"] if lv == ValidationLevel.WARNING else [],
                        metadata={
                            "level": lv,
                            "rule": rule_name,
                            "field": param,
                            "value": delta,
                            "constraint": f"max_delta={rule.max_delta}",
                            # Phase 6O-A-2: delta-over-limit = hard for ERROR,
                            # diagnostic-only for WARNING.
                            "expected_terminal": lv == ValidationLevel.ERROR,
                            "constraint_type": "hard" if lv == ValidationLevel.ERROR else "diagnostic",
                        }
                    ))
        
        self._categorize_results(results)
        return results

    # validate_default_household_rules was removed in favor of YAML coherence_rules

    def validate_identity(
        self,
        agent_type: str,
        agent_id: str,
        decision: str,
        state: Dict[str, Any]
    ) -> List[ValidationResult]:
        """Tier 1: Identity/Condition validation (Status-based)."""
        results = []
        rules = self.config.get_identity_rules(agent_type)

        for rule in rules:
            if not rule.blocked_skills: continue
            
            # Check precondition in state
            pre = rule.metadata.get("precondition")
            is_triggered = False
            if pre:
                if state.get(pre) is True:
                    is_triggered = True
            
            if is_triggered:
                normalized_decision = decision.lower().strip().replace("_", "")
                blocked_normalized = [b.lower().strip().replace("_", "") for b in rule.blocked_skills]
                
                if normalized_decision in blocked_normalized:
                    lv = ValidationLevel.ERROR if rule.level == "ERROR" else ValidationLevel.WARNING
                    if lv == ValidationLevel.ERROR:
                        self.auditor.log_intervention(rule.id, success=False, is_final=False)
                    else:
                        self.auditor.log_warning(rule.id)

                    rule_msg = self._rule_message(
                        rule.id,
                        rule.message or f'Identity Block: {decision} restricted by {pre}',
                    )
                    results.append(ValidationResult(
                        valid=(lv == ValidationLevel.WARNING),
                        validator_name=f"AgentValidator:identity_{rule.level.lower()}",
                        errors=[rule_msg] if lv == ValidationLevel.ERROR else [],
                        warnings=[rule_msg] if lv == ValidationLevel.WARNING else [],
                        metadata={
                            "level": lv,
                            "tier": IDENTITY_TIER,
                            "rule": f"identity_{rule.level.lower()}",
                            "rule_id": rule.id,
                            "message": rule.message,
                            "field": "decision",
                            "value": decision,
                            "constraint": f"Identity: {rule.level}",
                            "rules_hit": [rule.id],
                            # Phase 6O-A-2: identity = agent-type eligibility
                            # (hard when ERROR); WARNING rules are diagnostic.
                            "expected_terminal": lv == ValidationLevel.ERROR,
                            "constraint_type": "hard" if lv == ValidationLevel.ERROR else "diagnostic",
                            # P1-f: identity rules are precondition tests on
                            # world state the model cannot author (this
                            # irreversible action has already been taken), so
                            # they are world-grounded and always were. Without
                            # this stamp
                            # `_safe_rules_by_grounding` applied its default and
                            # filed every identity block under `rules_self_report`
                            # — a paper counting self-report blocks would have
                            # counted physical constraints among them.
                            "grounding": getattr(rule, "grounding", "self_report"),
                        }
                    ))
        return results

    def validate_thinking(
        self,
        agent_type: str,
        agent_id: str,
        decision: str,
        state: Dict[str, Any],
        reasoning: Dict[str, str],
        full_context: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationResult]:
        """Tier 2: Thinking/Cognitive validation (Reasoning-based).

        ``full_context`` is the broker's validation context. It carries the
        world planes (``env_state``, ``social_context``) that the agent's own
        ``state`` dict does not, and world-grounded rules need them. Optional
        and default-``None`` so every existing direct caller keeps working —
        with it absent, a world condition simply finds nothing and does not fire.
        """
        rules = self.config.get_thinking_rules(agent_type)
        return self._run_rule_set(
            agent_id, decision, state, reasoning, rules, "thinking",
            agent_type=agent_type, full_context=full_context,
        )

    def _run_rule_set(
        self,
        agent_id: str,
        decision: str,
        state: Dict[str, Any],
        reasoning: Dict[str, str],
        rules: List[Any],
        tier_name: str,
        agent_type: str = "",
        full_context: Optional[Dict[str, Any]] = None,
    ) -> List[ValidationResult]:
        """Generic engine for label-based rules."""
        results = []
        framework_aware = bool(getattr(self, "framework_aware_labels", False))
        framework = ""
        fw_mappings: Dict[str, str] = {}
        fw_alphabet: Dict[str, int] = {}
        if framework_aware:
            framework, fw_mappings, fw_alphabet = self._resolve_framework_alphabet(agent_type)
        # Constructs a rule asked about and the model did not report. Collected,
        # not fabricated: under the flag these become audited WARNING findings
        # instead of a silently-invented middle value.
        missing_constructs: List[str] = []
        # P1-a: world variables a rule asked about and the environment did not
        # publish, as ordered (rule_id, variable) pairs. Same reasoning as
        # `missing_constructs`, applied to the other plane: a grounded rule whose
        # antecedent is unreadable does not fire, and a non-firing grounded rule
        # is indistinguishable in the audit trail from a rule that was evaluated
        # and found nothing wrong. Collected UNCONDITIONALLY (no flag): a world
        # condition is only reachable at all in a profile that declares one, and
        # no frozen profile does, so this cannot move a published byte.
        missing_world_vars: List[tuple] = []
        # Per-pass grounded-rule census, for the run-integrity tally below.
        world_rules_total = 0
        world_rules_unreadable = 0

        def get_label(key):
            """Extract normalized 5-level label (VL/L/M/H/VH) from state or reasoning."""
            if not key: return ""
            if framework_aware:
                raw = state.get(key, reasoning.get(key, ""))
                if raw is None or str(raw).strip() == "":
                    if key not in missing_constructs:
                        missing_constructs.append(key)
                    return ""
                return self._normalize_framework_label(
                    str(raw), fw_mappings, fw_alphabet,
                )
            # Normalized values are already in state
            # Priority: 1. State, 2. Reasoning
            val = str(state.get(key, reasoning.get(key, ""))).upper().strip()
            # Remove brackets and extract clean label
            label_text = val.split(']')[0].replace("[", "").replace("]", "").strip() if ']' in val else val.strip()
            
            # Load normalization map from shared config if available
            try:
                normalization_map = self.config.get_shared("normalization_map", {})
            except (ImportError, AttributeError, KeyError):
                normalization_map = {}
                
            # Fallback to standard 5-level if nothing in config
            if not normalization_map:
                normalization_map = {
                    "VERY LOW": "VL", "VERYLOW": "VL", "VERY_LOW": "VL",
                    "LOW": "L",
                    "MEDIUM": "M", "MED": "M", "MODERATE": "M", "MOD": "M",
                    "HIGH": "H",
                    "VERY HIGH": "VH", "VERYHIGH": "VH", "VERY_HIGH": "VH"
                }
            
            return normalization_map.get(label_text, label_text[:2] if len(label_text) >= 2 else label_text)

        def label_matches(actual_label: str, expected_values: list) -> bool:
            """Check if actual_label matches any of the expected values (5-level aware)."""
            if not actual_label: return False
            if framework_aware:
                # The EXPECTED side must go through the same alphabet as the
                # actual side. Normalising only the actual value is how a
                # framework whose YAML writes `values: ["AGGRESSIVE"]` ends up
                # comparing "A" against "AGGRESSIVE" and never matching.
                return actual_label in {
                    self._normalize_framework_label(str(v), fw_mappings, fw_alphabet)
                    for v in expected_values
                }
            normalized_expected = []
            for v in expected_values:
                v_upper = v.upper().strip()
                if v_upper in ["VL", "VERY LOW", "VERYLOW", "VERY_LOW"]: normalized_expected.append("VL")
                elif v_upper in ["L", "LOW"]: normalized_expected.append("L")
                elif v_upper in ["M", "MED", "MEDIUM", "MODERATE", "MOD"]: normalized_expected.append("M")
                elif v_upper in ["H", "HIGH"]: normalized_expected.append("H")
                elif v_upper in ["VH", "VERY HIGH", "VERYHIGH", "VERY_HIGH"]: normalized_expected.append("VH")
                else: normalized_expected.append(v_upper)
            return actual_label in normalized_expected

        for rule in rules:
            if not rule.blocked_skills: continue
            
            is_triggered = False
            _rule_has_world_condition = False
            _rule_world_unreadable = False
            if rule.conditions:
                if isinstance(rule.conditions, list):
                    matches = []
                    for cond in rule.conditions:
                        if isinstance(cond, dict):
                            # PR-6: WORLD-STATE condition. Checked first and
                            # `continue`d, so a construct condition takes the
                            # identical path it always took — that equality is
                            # what keeps every frozen self-report baseline
                            # byte-for-byte unchanged.
                            _var, _scope = world_condition_target(cond)
                            if _var:
                                _rule_has_world_condition = True
                                _matched, _readable = _evaluate_world_condition(
                                    cond, _var, _scope, state, full_context,
                                )
                                matches.append(_matched)
                                if not _readable:
                                    _rule_world_unreadable = True
                                    _pair = (str(rule.id), str(_var))
                                    if _pair not in missing_world_vars:
                                        missing_world_vars.append(_pair)
                                continue
                            # Phase 6N-E (2026-05-24): accept both the
                            # canonical short shape `construct: X` (used
                            # by irrigation, governed_flood, MA flood)
                            # AND the verbose `RuleCondition`-flavoured
                            # shape `field: X` (which L3-1C's
                            # vaccination_demo copy-pasted from
                            # broker/governance/rule_types.py). Without
                            # this fallback, any YAML written in the
                            # verbose shape produced silently-dead
                            # rules — `cond.get("construct")` returned
                            # None, `get_label(None)` returned "", and
                            # the rule never fired.
                            construct_name = cond.get("construct") or cond.get("field")
                            if "operator" in cond and "value" in cond:
                                # Numeric Comparison (for Finance/Generic)
                                actual_val = state.get(construct_name, reasoning.get(construct_name, 0.0))
                                try:
                                    op = cond.get("operator")
                                    target = float(cond.get("value"))
                                    val = float(actual_val)
                                    if op == ">": matches.append(val > target)
                                    elif op == "<": matches.append(val < target)
                                    elif op == ">=": matches.append(val >= target)
                                    elif op == "<=": matches.append(val <= target)
                                    elif op == "==": matches.append(val == target)
                                    else: matches.append(False)
                                except (ValueError, TypeError):
                                    matches.append(False)
                            else:
                                # Categorical/Label Comparison (for Flood/PMT) - 5-level aware
                                actual = get_label(construct_name)
                                matches.append(label_matches(actual, cond.get("values", [])))
                        else:
                            matches.append(False)
                    is_triggered = all(matches) if matches else False
                elif isinstance(rule.conditions, str):
                    # Robust evaluation of string expressions if needed
                    # Note: Avoid hard-coded experiment hacks here.
                    is_triggered = False
            elif rule.construct:
                label = get_label(rule.construct)
                if label and rule.expected_levels:
                    is_triggered = label_matches(label, rule.expected_levels)

            if _rule_has_world_condition:
                world_rules_total += 1
                if _rule_world_unreadable:
                    world_rules_unreadable += 1

            if is_triggered:
                normalized_decision = decision.lower().strip().replace("_", "")
                blocked_normalized = [b.lower().strip().replace("_", "") for b in rule.blocked_skills]
                
                if normalized_decision in blocked_normalized:
                    lv = ValidationLevel.ERROR if rule.level == "ERROR" else ValidationLevel.WARNING
                    if lv == ValidationLevel.ERROR:
                        self.auditor.log_intervention(rule.id, success=False, is_final=False)
                    else:
                        self.auditor.log_warning(rule.id)

                    rule_msg = self._rule_message(
                        rule.id,
                        rule.message or f'{tier_name.capitalize()} Block: {decision} restricted by {tier_name} rules',
                    )
                    # Optional YAML `suggestion:` (AgentTypeConfig.
                    # get_thinking_rules), read by build_intervention_reports
                    # as the retry prompt's "Suggestion:" line. No key at all
                    # for a rule without one, so its metadata is unchanged.
                    _rule_meta = getattr(rule, "metadata", None) or {}
                    _suggestion_meta = (
                        {"suggestion": _rule_meta["suggestion"]}
                        if _rule_meta.get("suggestion") else {}
                    )
                    results.append(ValidationResult(
                        valid=(lv == ValidationLevel.WARNING),
                        validator_name=f"AgentValidator:{tier_name}_{rule.level.lower()}",
                        errors=[rule_msg] if lv == ValidationLevel.ERROR else [],
                        warnings=[rule_msg] if lv == ValidationLevel.WARNING else [],
                        metadata={
                            "level": lv,
                            "tier": f"Tier 2: {tier_name.capitalize()}",
                            "rule": f"{tier_name}_{rule.level.lower()}",
                            "rule_id": rule.id,
                            "message": rule.message,
                            "field": "decision",
                            "value": decision,
                            "constraint": f"Identity: {rule.level}",
                            "rules_hit": [rule.id],
                            # Phase 6O-A-2: thinking rules detect coherence
                            # violations; model can re-reason so never terminal.
                            "expected_terminal": False,
                            "constraint_type": "diagnostic" if lv == ValidationLevel.WARNING else "soft",
                            # PR-6: does this rule's antecedent read the world or
                            # the model's own labels? Recorded per FIRING, not
                            # per rule definition, so the audit row can say which
                            # of the rules that actually blocked a decision were
                            # world-grounded. Additive metadata only — no
                            # existing consumer reads this key, so flag-OFF rows
                            # are unchanged.
                            "grounding": getattr(rule, "grounding", "self_report"),
                            **_suggestion_meta,
                        }
                    ))

        # PR-6: one audited finding per construct a rule asked about and the
        # model did not report. Only under the flag — legacy behaviour is that
        # `get_label` returns "" and the rule quietly does not fire, which is
        # the right ENFORCEMENT decision and the wrong AUDIT one: the row is
        # indistinguishable from a row where the rule was evaluated and passed.
        for construct_name in missing_constructs:
            message = (
                f"[Rule: construct_missing] Construct '{construct_name}' was not "
                f"reported, so rules conditioned on it did not fire. No middle "
                f"value was assumed."
            )
            results.append(ValidationResult(
                valid=True,
                validator_name=f"AgentValidator:{tier_name}_construct_missing",
                errors=[],
                warnings=[message],
                metadata={
                    "level": ValidationLevel.WARNING,
                    "tier": f"Tier 2: {tier_name.capitalize()}",
                    "rule": "construct_missing",
                    "rule_id": "construct_missing",
                    "rules_hit": ["construct_missing"],
                    "field": construct_name,
                    "framework": framework,
                    "constraint": "construct_present",
                    "expected_terminal": False,
                    "constraint_type": "diagnostic",
                    "grounding": "self_report",
                },
            ))

        # P1-a: one audited finding per (rule, world variable) the environment
        # did not publish. `grounding="world"` on purpose, so the row's
        # `rules_world_grounded` cell names the rule that COULD NOT be evaluated
        # alongside the ones that fired — a grounded profile whose variable was
        # never published otherwise produces a row identical to a clean one.
        _pass_unevaluable = bool(
            world_rules_total and world_rules_unreadable == world_rules_total)
        for rule_id, var_name in missing_world_vars:
            message = (
                f"[Rule: world_variable_missing] Rule '{rule_id}' reads world "
                f"variable '{var_name}', which the environment did not publish "
                f"for this decision, so the rule did not fire. No value was "
                f"assumed."
            )
            results.append(ValidationResult(
                valid=True,
                validator_name=f"AgentValidator:{tier_name}_world_variable_missing",
                errors=[],
                warnings=[message],
                metadata={
                    "level": ValidationLevel.WARNING,
                    "tier": f"Tier 2: {tier_name.capitalize()}",
                    "rule": "world_variable_missing",
                    "rule_id": "world_variable_missing",
                    "rules_hit": ["world_variable_missing"],
                    "field": var_name,
                    "source_rule_id": rule_id,
                    "constraint": "world_variable_published",
                    "expected_terminal": False,
                    "constraint_type": "diagnostic",
                    "grounding": "world",
                    # The per-pass census, carried on the finding so the audit
                    # row can tally "every grounded rule was unevaluable here"
                    # once per ROW rather than once per validation pass.
                    "world_rules_total": world_rules_total,
                    "world_rules_unreadable": world_rules_unreadable,
                    "world_rules_unevaluable_pass": _pass_unevaluable,
                },
            ))
        return results

    # ------------------------------------------------------------------
    # PR-6: framework-aware label resolution (flag-gated)
    # ------------------------------------------------------------------
    def _resolve_framework_alphabet(self, agent_type: str):
        """Return ``(framework, label_mappings, label_order)`` for an agent type.

        Reads the SAME registry the ThinkingValidator reads
        (``register_framework_metadata``), so a framework registered once is
        enforced everywhere rather than only where it happened to be wired.
        An UNREGISTERED framework name falls back to empty dicts, which makes
        :meth:`_normalize_framework_label` behave like the legacy five-level
        path minus the two-character truncation (both sides of a comparison pass
        through unchanged, so literal labels still match) — but it is logged
        once, because it means the framework's own alphabet is not being applied.

        A framework that cannot be RESOLVED AT ALL raises. The old
        ``except Exception: framework = ""`` swallowed a broken config accessor
        and silently ran every label rule against the generic alphabet: rules
        written for a registered framework's labels then matched nothing, and a
        rule that never fires leaves the same audit trail as a rule that is never
        violated. This flag is opt-in and off for every frozen corpus, so failing
        loudly here costs a reproduction nothing and buys the run its own
        correctness.
        """
        framework = ""
        try:
            getter = getattr(self.config, "get_framework_for_agent_type", None)
            if callable(getter) and agent_type:
                framework = str(getter(agent_type) or "").strip().lower()
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"validators.framework_aware_labels is ON but the framework for "
                f"agent_type {agent_type!r} could not be resolved "
                f"({type(exc).__name__}: {exc}). Refusing to fall back to the "
                f"generic alphabet: every rule written against this framework's "
                f"labels would silently never fire, and the audit trail of a "
                f"rule that never fires is identical to one that was never "
                f"violated. Fix the config's psychological_framework declaration, "
                f"or turn the flag off."
            ) from exc
        try:
            from broker.validators.governance.thinking_validator import (
                FRAMEWORK_LABEL_ORDERS, _LABEL_MAPPINGS,
            )
        except ImportError:  # pragma: no cover - defensive
            return framework, {}, {}
        if framework and framework not in FRAMEWORK_LABEL_ORDERS:
            warned = self.__dict__.setdefault("_warned_unregistered_frameworks", set())
            if framework not in warned:
                warned.add(framework)
                logger.warning(
                    "[AgentValidator] validators.framework_aware_labels is ON and "
                    "agent_type %r declares framework %r, which is NOT registered "
                    "(registered: %s). Labels will be compared literally on both "
                    "sides instead of through that framework's alphabet, so a "
                    "rule written with the framework's short codes will not match "
                    "a model that answered in long form. Call "
                    "register_framework_metadata(%r, ...) from the domain pack.",
                    agent_type, framework, sorted(FRAMEWORK_LABEL_ORDERS.keys()),
                    framework,
                )
        return (
            framework,
            dict(_LABEL_MAPPINGS.get(framework, {}) or {}),
            dict(FRAMEWORK_LABEL_ORDERS.get(framework, {}) or {}),
        )

    def _normalize_framework_label(self, raw: str, mappings: Dict[str, str],
                                   alphabet: Dict[str, int]) -> str:
        """Normalise one label against a framework's registered alphabet.

        Deliberately does NOT truncate to two characters. That truncation is the
        F2 defect: it turns ``AGGRESSIVE`` into ``"AG"``, which is in no
        framework's alphabet, so every ``financial`` rule silently never fires.
        An unrecognised label is returned whole instead, where a comparison can
        fail visibly rather than fail as a near-miss.
        """
        text = str(raw).upper().strip()
        if "]" in text:
            text = text.split("]")[0].replace("[", "").replace("]", "").strip()
        if text in alphabet:
            return text
        if text in mappings:
            return mappings[text]
        try:
            shared_map = self.config.get_shared("normalization_map", {}) or {}
        except (ImportError, AttributeError, KeyError):
            shared_map = {}
        if text in shared_map:
            return shared_map[text]
        return text

    def validate_affordability(
        self,
        agent_id: str,
        decision: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Tier 0: financial affordability check (domain-neutral).

        A decision is affordable iff
            base_cost * (1 - subsidy_rate) <= income * income_multiplier

        The per-decision cost model comes from the active DomainPack's
        ``affordability_constraints()``; a decision the domain does not
        list is unconstrained. No decision names are hardcoded here
        (Phase 6H Item 6). ``subsidy_rate`` is read from agent/env state,
        falling back to the spec's ``default_subsidy_rate``.
        """
        if not context:
            return True, None

        spec = _affordability_constraints_from_domain_pack().get(decision)
        if not spec:
            return True, None

        agent_state = context.get("agent_state", {})
        state = {}
        if isinstance(agent_state, dict):
            state = agent_state.get("state") or agent_state.get("personal") or {}
        if not isinstance(state, dict):
            state = {}

        fixed = state.get("fixed_attributes", {})
        if not isinstance(fixed, dict):
            fixed = {}

        env = context.get("env_state", {})
        if not isinstance(env, dict):
            env = {}

        def get_number(key: str, default: float) -> float:
            val = state.get(key, fixed.get(key, default))
            try:
                return float(val)
            except (TypeError, ValueError):
                return float(default)

        income = get_number("income", 50000)
        subsidy_rate = get_number(
            "subsidy_rate",
            env.get("subsidy_rate", float(spec.get("default_subsidy_rate", 0.0))),
        )
        base_cost = float(spec.get("base_cost", 0.0))
        # Fallback 1.0 (cost <= 100% income) is domain-neutral; the
        # flood spec always supplies an explicit multiplier.
        income_multiplier = float(spec.get("income_multiplier", 1.0))

        cost = base_cost * (1.0 - subsidy_rate)
        threshold = income * income_multiplier
        if cost > threshold:
            return False, (
                f"AFFORDABILITY: Cannot afford '{decision}' "
                f"(${cost:,.0f} > {income_multiplier:g}x income ${threshold:,.0f})"
            )
        return True, None
    
    def validate_response_format(
        self,
        agent_id: str,
        response: str,
        required_fields: List[str] = None
    ) -> List[ValidationResult]:
        """Validate LLM response has required fields."""
        results = []
        required = required_fields or ["decision", "reasoning"]
        
        for field in required:
            if field not in response:
                results.append(ValidationResult(
                    valid=False,
                    validator_name="AgentValidator:response_format",
                    errors=[f"Missing '{field}' in response"],
                    metadata={
                        "level": ValidationLevel.ERROR,
                        "rule": "format",
                        "field": "json_structure",
                        "constraint": f"required: {required}"
                    }
                ))
        
        self._categorize_results(results)
        return results
    
    def validate_adjustment(
        self,
        agent_id: str,
        adjustment: float,
        min_adj: float = 0.0,
        max_adj: float = 0.15
    ) -> List[ValidationResult]:
        """Validate adjustment is within bounds."""
        results = []
        if not (min_adj <= adjustment <= max_adj):
            results.append(ValidationResult(
                valid=True, # WARNING
                validator_name="AgentValidator:adjustment_bounds",
                errors=[],
                warnings=[f"Adjustment {adjustment:.1%} outside [{min_adj:.0%}, {max_adj:.0%}]"],
                metadata={
                    "level": ValidationLevel.WARNING,
                    "rule": "adjustment_bounds",
                    "field": "adjustment",
                    "value": adjustment,
                    "constraint": f"[{min_adj}, {max_adj}]"
                }
            ))
        self._categorize_results(results)
        return results
    
    def _categorize_results(self, results: List[ValidationResult]):
        """Sort results into errors and warnings."""
        for r in results:
            if not r.valid and r.errors:
                self.errors.append(r)
            else:
                self.warnings.append(r)
    
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    def summary(self) -> Dict:
        """Return validation summary."""
        return {
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "errors": [{"rule": e.metadata.get("rule"), "message": str(e.errors)} for e in self.errors],
            "warnings": [{"rule": w.metadata.get("rule", "warning"), "message": str(w.warnings)} for w in self.warnings]
        }
    
    def reset(self):
        """Clear accumulated results."""
        self.errors = []
        self.warnings = []


# Backward compatibility alias
InstitutionalValidator = AgentValidator
