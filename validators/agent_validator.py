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


from broker.interfaces.skill_types import ValidationResult
from broker.utils.agent_config import (
    load_agent_config, 
    ValidationRule, 
    CoherenceRule,
    GovernanceAuditor
)
from broker.utils.logging import setup_logger

logger = setup_logger(__name__)

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

            # Map required fields to reasoning keys
            missing = []
            for field in required_fields:
                if field == "decision":
                    # Decision is valid if we have a skill_name extracted
                    if not decision:
                        missing.append(field)
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
                        "constraint": f"required={required_fields}"
                    }
                ))
        except Exception as e:
            # logger.error(f"Error in Tier 0 validation: {e}")
            pass

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
                        "rule": "affordability",
                        "field": "decision",
                        "constraint": "financial_affordability"
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
                        "constraint": str(valid_actions[:4]) + "..."
                    }
                ))
        
        # 2. Dual-Tier Validation (Identity & Thinking)
        # Tier 1: Identity/Condition Validation (Status/Right-to-act)
        # Driven by 'identity_rules' in YAML
        results.extend(self.validate_identity(base_type, agent_id, decision, state))
        
        # Tier 2: Thinking/Cognitive Validation (Reasoning/Coherence)
        # Driven by 'thinking_rules' in YAML
        if reasoning:
            results.extend(self.validate_thinking(base_type, agent_id, decision, state, reasoning))
        
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
                        "constraint": f"min={rule.min_val}"
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
                        "constraint": f"max={rule.max_val}"
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
                            "constraint": f"max_delta={rule.max_delta}"
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

        # DEBUG Task 015-V2: Track elevated state during elevate_house attempts
        if decision == "elevate_house":
            elevated_val = state.get("elevated")
            print(f"[V2-DEBUG] {agent_id} chose elevate_house | elevated={elevated_val} (type={type(elevated_val).__name__ if elevated_val is not None else 'None'}) | rules={len(rules)}")

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

                    rule_msg = f"[Rule: {rule.id}] {rule.message or f'Identity Block: {decision} restricted by {pre}'}"
                    results.append(ValidationResult(
                        valid=(lv == ValidationLevel.WARNING),
                        validator_name=f"AgentValidator:identity_{rule.level.lower()}",
                        errors=[rule_msg] if lv == ValidationLevel.ERROR else [],
                        warnings=[rule_msg] if lv == ValidationLevel.WARNING else [],
                        metadata={
                            "level": lv,
                            "tier": "Tier 1: Identity/Status",
                            "rule": f"identity_{rule.level.lower()}",
                            "rule_id": rule.id,
                            "message": rule.message,
                            "field": "decision",
                            "value": decision,
                            "constraint": f"Identity: {rule.level}",
                            "rules_hit": [rule.id]
                        }
                    ))
        return results

    def validate_thinking(
        self,
        agent_type: str,
        agent_id: str,
        decision: str,
        state: Dict[str, Any],
        reasoning: Dict[str, str]
    ) -> List[ValidationResult]:
        """Tier 2: Thinking/Cognitive validation (Reasoning-based)."""
        rules = self.config.get_thinking_rules(agent_type)
        return self._run_rule_set(agent_id, decision, state, reasoning, rules, "thinking")

    def _run_rule_set(
        self,
        agent_id: str,
        decision: str,
        state: Dict[str, Any],
        reasoning: Dict[str, str],
        rules: List[Any],
        tier_name: str
    ) -> List[ValidationResult]:
        """Generic engine for label-based rules."""
        results = []
        
        def get_label(key):
            """Extract normalized 5-level label (VL/L/M/H/VH) from state or reasoning."""
            if not key: return ""
            # Normalized values are already in state
            # Priority: 1. State, 2. Reasoning
            val = str(state.get(key, reasoning.get(key, ""))).upper().strip()
            # Remove brackets and extract clean label
            label_text = val.split(']')[0].replace("[", "").replace("]", "").strip() if ']' in val else val.strip()
            
            # Load normalization map from shared config if available
            try:
                from broker.utils.agent_config import load_agent_config
                normalization_map = load_agent_config().get_shared("normalization_map", {})
            except:
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
            if rule.conditions:
                if isinstance(rule.conditions, list):
                    matches = []
                    for cond in rule.conditions:
                        if isinstance(cond, dict):
                            construct_name = cond.get("construct")
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
                                except:
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
                
            if is_triggered:
                normalized_decision = decision.lower().strip().replace("_", "")
                blocked_normalized = [b.lower().strip().replace("_", "") for b in rule.blocked_skills]
                
                if normalized_decision in blocked_normalized:
                    lv = ValidationLevel.ERROR if rule.level == "ERROR" else ValidationLevel.WARNING
                    if lv == ValidationLevel.ERROR:
                        self.auditor.log_intervention(rule.id, success=False, is_final=False)

                    rule_msg = f"[Rule: {rule.id}] {rule.message or f'Identity Block: {decision} restricted by {tier_name} rules'}"
                    results.append(ValidationResult(
                        valid=(lv == ValidationLevel.WARNING),
                        validator_name=f"AgentValidator:identity_{rule.level.lower()}",
                        errors=[rule_msg] if lv == ValidationLevel.ERROR else [],
                        warnings=[rule_msg] if lv == ValidationLevel.WARNING else [],
                        metadata={
                            "level": lv,
                            "tier": "Tier 1: Identity/Status",
                            "rule": f"identity_{rule.level.lower()}",
                            "rule_id": rule.id,
                            "message": rule.message,
                            "field": "decision",
                            "value": decision,
                            "constraint": f"Identity: {rule.level}",
                            "rules_hit": [rule.id]
                        }
                    ))
        return results

    def validate_affordability(
        self,
        agent_id: str,
        decision: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Tier 0: Financial affordability check.

        Rules:
        - elevate_house: cost after subsidy <= 3x annual income
        - buy_insurance/buy_contents_insurance: annual premium <= 5% of income
        """
        if not context:
            return True, None

        agent_type = context.get("agent_type")
        if agent_type not in ["household_owner", "household_renter", "household"]:
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
        subsidy_rate = get_number("subsidy_rate", env.get("subsidy_rate", 0.5))
        premium_rate = get_number("premium_rate", env.get("premium_rate", 0.02))
        property_value = get_number("property_value", 0.0)
        if not property_value:
            property_value = get_number("rcv_building", 0.0) + get_number("rcv_contents", 0.0)
        if not property_value:
            property_value = 300000.0

        if decision == "elevate_house":
            cost = 150_000 * (1 - subsidy_rate)
            if cost > income * 3.0:
                return False, (
                    f"AFFORDABILITY: Cannot afford elevation (${cost:,.0f} > 3x income ${income*3:,.0f})"
                )

        if decision in ["buy_insurance", "buy_contents_insurance"]:
            premium = premium_rate * property_value
            if premium > income * 0.05:
                return False, (
                    f"AFFORDABILITY: Premium ${premium:,.0f} exceeds 5% of income ${income*0.05:,.0f}"
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
