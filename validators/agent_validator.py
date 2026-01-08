"""
Generic Agent Validator

Label-based validation - one validator for all agent types.
Rules are configured per agent_type label, not per file.

Features:
- Configurable retry count and behavior
- Validation audit logging
- Multi-agent support via agent_type routing
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime
import json


class ValidationLevel(Enum):
    ERROR = "ERROR"      # Must fix, triggers retry
    WARNING = "WARNING"  # Log but may allow (configurable)


class ValidationOutcome(Enum):
    APPROVED = "APPROVED"           # First-pass valid
    RETRY_SUCCESS = "RETRY_SUCCESS" # Valid after retry
    REJECTED = "REJECTED"           # Invalid after max retries
    UNCERTAIN = "UNCERTAIN"         # Warnings but allowed


@dataclass
class ValidationResult:
    valid: bool
    level: ValidationLevel
    rule: str
    message: str
    agent_id: str
    field: Optional[str] = None
    value: Optional[Any] = None
    constraint: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "level": self.level.value,
            "rule": self.rule,
            "message": self.message,
            "agent_id": self.agent_id,
            "field": self.field,
            "value": self.value,
            "constraint": self.constraint
        }


@dataclass
class ValidatorConfig:
    """Configuration for validator behavior."""
    max_retries: int = 2              # Max retry attempts
    retry_on_warning: bool = False    # Whether warnings trigger retry
    audit_enabled: bool = True        # Enable validation audit logging
    audit_path: Optional[str] = None  # Path for audit log file
    strict_mode: bool = False         # Reject on any warning


@dataclass
class ValidationAuditEntry:
    """Single validation audit entry."""
    timestamp: str
    agent_id: str
    agent_type: str
    decision: str
    attempt: int
    results: List[Dict]
    outcome: str
    retry_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "decision": self.decision,
            "attempt": self.attempt,
            "results": self.results,
            "outcome": self.outcome,
            "retry_errors": self.retry_errors
        }


class ValidationAudit:
    """Tracks validation history for analysis."""
    
    def __init__(self, enabled: bool = True, path: Optional[str] = None):
        self.enabled = enabled
        self.path = path
        self.entries: List[ValidationAuditEntry] = []
        self.stats = {
            "total": 0,
            "approved": 0,
            "retry_success": 0,
            "rejected": 0,
            "uncertain": 0,
            "by_agent_type": {},
            "by_rule": {}
        }
    
    def log(self, entry: ValidationAuditEntry) -> None:
        """Log a validation entry."""
        if not self.enabled:
            return
        
        self.entries.append(entry)
        self.stats["total"] += 1
        self.stats[entry.outcome.lower()] = self.stats.get(entry.outcome.lower(), 0) + 1
        
        # Track by agent type
        at = entry.agent_type
        if at not in self.stats["by_agent_type"]:
            self.stats["by_agent_type"][at] = {"total": 0, "rejected": 0}
        self.stats["by_agent_type"][at]["total"] += 1
        if entry.outcome == "REJECTED":
            self.stats["by_agent_type"][at]["rejected"] += 1
        
        # Track by rule
        for r in entry.results:
            rule = r.get("rule", "unknown")
            if rule not in self.stats["by_rule"]:
                self.stats["by_rule"][rule] = {"triggered": 0}
            if not r.get("valid", True):
                self.stats["by_rule"][rule]["triggered"] += 1
        
        # Write to file if path specified
        if self.path:
            with open(self.path, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get validation statistics summary."""
        return {
            **self.stats,
            "approval_rate": (self.stats["approved"] + self.stats["retry_success"]) / max(1, self.stats["total"]) * 100,
            "retry_rate": self.stats["retry_success"] / max(1, self.stats["total"]) * 100,
            "rejection_rate": self.stats["rejected"] / max(1, self.stats["total"]) * 100
        }


from broker.agent_config import load_agent_config, ValidationRule, CoherenceRule

class AgentValidator:
    """
    Generic validator for any agent type.
    
    Features:
    - Configurable retry behavior via ValidatorConfig
    - Validation audit logging via ValidationAudit
    - Multi-agent support via agent_type routing
    
    Usage:
        config = ValidatorConfig(max_retries=3, audit_enabled=True)
        validator = AgentValidator(config_path="agent_types.yaml", validator_config=config)
        
        results = validator.validate(agent_type, agent_id, decision, state, reasoning)
        # Check validator.audit.get_summary() for stats
    """
    
    def __init__(self, config_path: str = None, validator_config: ValidatorConfig = None):
        self.config = load_agent_config(config_path)
        self.validator_config = validator_config or ValidatorConfig()
        self.audit = ValidationAudit(
            enabled=self.validator_config.audit_enabled,
            path=self.validator_config.audit_path
        )
        self.errors: List[ValidationResult] = []
        self.warnings: List[ValidationResult] = []
    
    def validate(
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
        
        Args:
            agent_type: Type label (e.g., "insurance", "government", "household")
            agent_id: Agent identifier
            decision: Decision string
            state: Current agent state
            prev_state: Previous state (for delta checks)
            reasoning: Optional reasoning dictionary (contains PMT labels)
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
        
        # 2. Validate PMT Coherence (if coherence_rules defined for this type)
        if reasoning:
            results.extend(self.validate_pmt_coherence(base_type, agent_id, decision, state, reasoning))
        
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

    def validate_pmt_coherence(
        self,
        agent_type: str,
        agent_id: str,
        decision: str,
        state: Dict[str, Any],
        reasoning: Dict[str, str]
    ) -> List[ValidationResult]:
        """
        Validate logical coherence between Agent State/Decision and LLM PMT Labels.
        Uses rules from agent_types.yaml.
        """
        results = []
        rules = self.config.get_coherence_rules(agent_type)
        
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
            
            # Check coherence: if label matches expected AND decision is in blocked_skills
            is_coherent = True
            decision_lower = decision.lower().replace("_", "")
            
            if rule.expected_levels and label in rule.expected_levels:
                # Label matches the "flagged" level, now check if decision is blocked
                if rule.blocked_skills:
                    blocked_normalized = [s.lower().replace("_", "") for s in rule.blocked_skills]
                    if decision_lower in blocked_normalized:
                        is_coherent = False
            
            if not is_coherent:
                results.append(ValidationResult(
                    valid=False,
                    level=ValidationLevel.WARNING,
                    rule=f"pmt_coherence_{rule.construct.lower()}",
                    message=rule.message or f"Incoherent: {rule.construct}={label} but chose {decision}",
                    agent_id=agent_id,
                    field=rule.construct,
                    value=label,
                    constraint=f"Blocked skills: {rule.blocked_skills} when {rule.construct} in {rule.expected_levels}"
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
