"""
Generic Agent Validator

Label-based validation - one validator for all agent types.
Rules are configured per agent_type label, not per file.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class ValidationLevel(Enum):
    ERROR = "ERROR"      # Must fix, decision rejected
    WARNING = "WARNING"  # Log but allow


@dataclass
class ValidationResult:
    valid: bool
    level: ValidationLevel
    rule: str
    message: str
    agent_id: str
    field: Optional[str] = None
    value: Optional[float] = None
    constraint: Optional[str] = None


from broker.agent_config import load_agent_config, ValidationRule, CoherenceRule

class AgentValidator:
    """
    Generic validator for any agent type.
    
    Uses agent_type label to lookup validation rules from agent_types.yaml.
    """
    
    def __init__(self, config_path: str = None):
        self.config = load_agent_config(config_path)
        self.errors: List[ValidationResult] = []
        self.warnings: List[ValidationResult] = []
    
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
            decision = proposal.skill_name
            state = context.get('state', {})
            # Normalized values are already in state
            # Reasoning might be in proposal
            reasoning = getattr(proposal, 'reasoning', {})
            
            return self._validate_internal(agent_type, agent_id, decision, state, None, reasoning)
            
        return self._validate_internal(*args, **kwargs)

    def _validate_internal(
        self,
        agent_type: str,
        agent_id: str,
        decision: str,
        state: Dict[str, Any],
        prev_state: Dict[str, Any] = None,
        reasoning: Dict[str, str] = None
    ) -> List[ValidationResult]:
        """
        Validate agent decision based on agent_type rules.
        """
        results = []
        
        if agent_type.startswith("household"):
            base_type = "household"
        else:
            base_type = agent_type
            
        # 1. Validate decision is in allowed values
        valid_actions = self.config.get_valid_actions(base_type)
        if valid_actions:
            normalized = decision.lower().replace("_", "").replace(" ", "")
            valid_normalized = [v.lower().replace("_", "").replace(" ", "") for v in valid_actions]
            if normalized not in valid_normalized:
                results.append(ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    rule="valid_decisions",
                    message=f"Invalid decision '{decision}' for {agent_type}",
                    agent_id=agent_id,
                    field="decision",
                    constraint=str(valid_actions[:4]) + "..."
                ))
        
        # 2. Validate PMT Coherence (Household only)
        if base_type == "household" and reasoning:
            # HARNDENING: Merge hardcoded default rules for household
            default_results = self.validate_default_household_rules(agent_id, decision, reasoning)
            results.extend(default_results)
            
            # YAML-based rules
            results.extend(self.validate_pmt_coherence(agent_id, state, reasoning))
            results.extend(self.validate_action_blocking(agent_id, decision, state, reasoning))
        
        # 3. Validate rate/param bounds
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
                    valid=False,
                    level=lv,
                    rule=rule_name,
                    message=rule.message or f"{param} {value:.2f} below min {rule.min_val:.2f}",
                    agent_id=agent_id,
                    field=param,
                    value=value,
                    constraint=f"min={rule.min_val}"
                ))
            
            if rule.max_val is not None and value > rule.max_val:
                results.append(ValidationResult(
                    valid=False,
                    level=lv,
                    rule=rule_name,
                    message=rule.message or f"{param} {value:.2f} above max {rule.max_val:.2f}",
                    agent_id=agent_id,
                    field=param,
                    value=value,
                    constraint=f"max={rule.max_val}"
                ))
            
            # Delta check
            if rule.max_delta is not None and prev_state and param in prev_state:
                delta = abs(value - prev_state[param])
                if delta > rule.max_delta:
                    results.append(ValidationResult(
                        valid=False,
                        level=lv,
                        rule=rule_name,
                        message=rule.message or f"{param} change {delta:.2%} exceeds max {rule.max_delta:.0%}",
                        agent_id=agent_id,
                        field=param,
                        value=delta,
                        constraint=f"max_delta={rule.max_delta}"
                    ))
        
        self._categorize_results(results)
        return results
        
        self._categorize_results(results)
        return results

    def validate_default_household_rules(
        self,
        agent_id: str,
        decision: str,
        reasoning: Dict[str, str]
    ) -> List[ValidationResult]:
        """
        Hardcoded default consistency rules for household agents.
        Ensures safety rails if YAML config is missing.
        """
        results = []
        
        # Helper to safely get label (H/M/L)
        def get_label(key):
            val = reasoning.get(key, "").upper()
            label_text = val.split(']')[0].replace("[", "").replace("]", "").strip() if ']' in val else val.strip()
            return label_text[:1] if label_text else ""

        tp_label = get_label("TP_LABEL")
        cp_label = get_label("CP_LABEL")
        normalized_decision = decision.lower().strip().replace("_", "")

        # 1. Enforce Urgency: High Threat must not result in Do Nothing
        if tp_label == "H" and normalized_decision == "donothing":
            results.append(ValidationResult(
                valid=False,
                level=ValidationLevel.ERROR,
                rule="default_urgency",
                message=f"BLOCK! Model said TP=High but chose 'do_nothing' (Forbidden by default).",
                agent_id=agent_id,
                field="decision",
                value=decision,
                constraint="Blocked when TP is High"
            ))

        # 2. Enforce Coping Alignment: Low Coping blocks expensive actions
        if cp_label == "L" and normalized_decision in ["elevatehouse", "relocate"]:
            results.append(ValidationResult(
                valid=False,
                level=ValidationLevel.ERROR,
                rule="default_coping_block",
                message=f"BLOCK! Model said CP=Low but chose '{decision}' (Forbidden by default).",
                agent_id=agent_id,
                field="decision",
                value=decision,
                constraint="Blocked when CP is Low"
            ))

        return results

    def validate_pmt_coherence(
        self,
        agent_id: str,
        state: Dict[str, Any],
        reasoning: Dict[str, str]
    ) -> List[ValidationResult]:
        """
        Validate logical coherence between Agent State and LLM PMT Labels.
        Uses rules from agent_types.yaml.
        """
        results = []
        rules = self.config.get_coherence_rules("household")
        
        # Helper to safely get label (handles brackets like [H])
        def get_label(key):
            val = reasoning.get(key, reasoning.get(f"EVAL_{key}", "")).upper()
            label = val.split(']')[0].replace("[", "").replace("]", "").strip() if ']' in val else val.strip()
            return label[:1] # Just take the first char (L, M, H) unless it's NONE/PARTIAL/FULL

        for rule in rules:
            label = get_label(rule.construct)
            if not label: continue
            
            # Get current value for comparison
            current_val = 0.0
            if rule.state_field:
                current_val = state.get(rule.state_field, 0.5)
            elif rule.state_fields:
                vals = [state.get(f, 0.5) for f in rule.state_fields]
                if rule.aggregation == "average":
                    current_val = sum(vals) / len(vals)
                elif rule.aggregation == "any_true":
                    current_val = 1.0 if any(v > 0.5 for v in vals) else 0.0
            
            # Check coherence
            is_coherent = True
            if current_val >= rule.threshold:
                if rule.expected_levels and label not in rule.expected_levels:
                    # Special case for L/M/H vs NONE/PARTIAL/FULL
                    is_coherent = False
            
            if not is_coherent:
                results.append(ValidationResult(
                    valid=False,
                    level=ValidationLevel.WARNING,
                    rule=f"pmt_coherence_{rule.construct.lower()}",
                    message=rule.message or f"Coherence issue with {rule.construct}",
                    agent_id=agent_id,
                    field=rule.construct,
                    value=label,
                    constraint=f"Expected {rule.expected_levels} when state >= {rule.threshold}"
                ))
            
        return results

    def validate_action_blocking(
        self,
        agent_id: str,
        decision: str,
        state: Dict[str, Any],
        reasoning: Dict[str, str]
    ) -> List[ValidationResult]:
        """
        Validate decision based on Model's Qualitative Labels (H/M/L).
        Ignores numerical state thresholds. STRICTLY checks:
        If Label IN [TriggerValues] AND Decision IN [BlockedSkills] -> ERROR.
        """
        results = []
        rules = self.config.get_coherence_rules("household")
        
        # Helper to safely get label (H/M/L)
        def get_label(key):
            # Try keys like 'TP', 'EVAL_TP', 'Threat Appraisal'
            val = reasoning.get(key, reasoning.get(f"EVAL_{key}", "")).upper()
            # Handle "[High]" or "High"
            # Split by ']' to handle "[High]..."
            label_text = val.split(']')[0].replace("[", "").replace("]", "").strip() if ']' in val else val.strip()
            # Return first char 'H', 'M', 'L' if exists
            return label_text[:1] if label_text else ""

        for rule in rules:
            if not rule.blocked_skills:
                continue
            
            # 1. Get Model's Evaluation (Label)
            label = get_label(rule.construct)
            if not label: 
                continue # Model didn't output a label, skip blocking check
            
            # 2. Check Trigger (Is Label in the 'High' set?)
            # YAML 'when_above' is used as 'trigger_labels' here
            # Logic: If rule.when_above=["H"], and label="H", then TRIGGER.
            is_triggered = False
            if rule.when_above and any(label.startswith(t[:1]) for t in rule.when_above):
                is_triggered = True
                
            if is_triggered:
                # 3. Check Blocked Actions
                normalized_decision = decision.lower().strip()
                if normalized_decision in rule.blocked_skills:
                    results.append(ValidationResult(
                        valid=False,
                        level=ValidationLevel.ERROR, # Strictly Block
                        rule=f"action_blocking_{rule.construct.lower()}",
                        message=f"BLOCK! Model said {rule.construct}={label} but chose '{decision}' (Forbidden).",
                        agent_id=agent_id,
                        field="decision",
                        value=decision,
                        constraint=f"Blocked when {rule.construct} is {label}"
                    ))
                    
        return results
    
    def validate_response_format(
        self,
        agent_id: str,
        response: str,
        required_fields: List[str] = None
    ) -> List[ValidationResult]:
        """Validate LLM response has required fields."""
        results = []
        required = required_fields or ["INTERPRET:", "DECIDE:"]
        
        for field in required:
            if field not in response:
                results.append(ValidationResult(
                    valid=False,
                    level=ValidationLevel.ERROR,
                    rule="response_format",
                    message=f"Missing '{field}' in response",
                    agent_id=agent_id,
                    field="response",
                    constraint=f"required: {required}"
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
                valid=False,
                level=ValidationLevel.WARNING,
                rule="adjustment_bounds",
                message=f"Adjustment {adjustment:.1%} outside [{min_adj:.0%}, {max_adj:.0%}]",
                agent_id=agent_id,
                field="adjustment",
                value=adjustment,
                constraint=f"[{min_adj}, {max_adj}]"
            ))
        self._categorize_results(results)
        return results
    
    def _categorize_results(self, results: List[ValidationResult]):
        """Sort results into errors and warnings."""
        for r in results:
            if r.level == ValidationLevel.ERROR:
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
            "errors": [{"rule": e.rule, "message": e.message} for e in self.errors],
            "warnings": [{"rule": w.rule, "message": w.message} for w in self.warnings]
        }
    
    def reset(self):
        """Clear accumulated results."""
        self.errors = []
        self.warnings = []


# Backward compatibility alias
InstitutionalValidator = AgentValidator
