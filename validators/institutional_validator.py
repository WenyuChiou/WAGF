"""
Institutional Agent Validator

Validates institutional agent decisions against defined rules.
Each agent type has specific validation constraints.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
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


class InstitutionalValidator:
    """
    Validates institutional agent decisions.
    
    Validation Rules by Agent Type:
    
    Insurance:
    - Premium rate bounds: 0.02 ≤ rate ≤ 0.15
    - Max change: ±15% per year
    - Solvency floor: > 0
    - Valid decisions: RAISE, LOWER, MAINTAIN
    
    Government:
    - Subsidy bounds: 0.2 ≤ rate ≤ 0.95
    - Max change: ±15% per year
    - Emergency reserve: budget_used ≤ 0.9
    - MG priority: favor MG if adoption gap
    """
    
    # Rule definitions
    INSURANCE_RULES = {
        "rate_bounds": {
            "param": "premium_rate",
            "min": 0.02,
            "max": 0.15,
            "level": ValidationLevel.ERROR
        },
        "max_change": {
            "param": "premium_rate",
            "max_delta": 0.15,
            "level": ValidationLevel.WARNING
        },
        "solvency_floor": {
            "param": "solvency",
            "min": 0.0,
            "level": ValidationLevel.ERROR
        },
        "valid_decision": {
            "values": ["RAISE", "LOWER", "MAINTAIN", "raise_premium", "lower_premium", "maintain_premium"],
            "level": ValidationLevel.ERROR
        }
    }
    
    GOVERNMENT_RULES = {
        "subsidy_bounds": {
            "param": "subsidy_rate",
            "min": 0.20,
            "max": 0.95,
            "level": ValidationLevel.ERROR
        },
        "max_change": {
            "param": "subsidy_rate",
            "max_delta": 0.15,
            "level": ValidationLevel.WARNING
        },
        "emergency_reserve": {
            "param": "budget_used",
            "max": 0.90,
            "level": ValidationLevel.WARNING
        },
        "valid_decision": {
            "values": ["INCREASE", "DECREASE", "MAINTAIN", "OUTREACH", 
                      "increase_subsidy", "decrease_subsidy", "maintain_subsidy", "target_mg_outreach"],
            "level": ValidationLevel.ERROR
        }
    }
    
    def __init__(self):
        self.errors: List[ValidationResult] = []
        self.warnings: List[ValidationResult] = []
    
    def validate_insurance(
        self,
        agent_id: str,
        decision: str,
        premium_rate: float,
        prev_premium_rate: float,
        solvency: float
    ) -> List[ValidationResult]:
        """Validate insurance agent decision."""
        results = []
        
        # 1. Rate bounds
        rule = self.INSURANCE_RULES["rate_bounds"]
        if not (rule["min"] <= premium_rate <= rule["max"]):
            results.append(ValidationResult(
                valid=False,
                level=rule["level"],
                rule="rate_bounds",
                message=f"Premium rate {premium_rate:.2%} outside bounds [{rule['min']:.0%}, {rule['max']:.0%}]",
                agent_id=agent_id,
                field="premium_rate",
                value=premium_rate,
                constraint=f"[{rule['min']}, {rule['max']}]"
            ))
        
        # 2. Max change
        rule = self.INSURANCE_RULES["max_change"]
        delta = abs(premium_rate - prev_premium_rate)
        if delta > rule["max_delta"]:
            results.append(ValidationResult(
                valid=False,
                level=rule["level"],
                rule="max_change",
                message=f"Premium change {delta:.1%} exceeds max {rule['max_delta']:.0%}",
                agent_id=agent_id,
                field="premium_rate",
                value=delta,
                constraint=f"max_delta={rule['max_delta']}"
            ))
        
        # 3. Solvency floor
        rule = self.INSURANCE_RULES["solvency_floor"]
        if solvency <= rule["min"]:
            results.append(ValidationResult(
                valid=False,
                level=rule["level"],
                rule="solvency_floor",
                message=f"Solvency {solvency:.2f} at or below floor {rule['min']}",
                agent_id=agent_id,
                field="solvency",
                value=solvency,
                constraint=f"min={rule['min']}"
            ))
        
        # 4. Valid decision
        rule = self.INSURANCE_RULES["valid_decision"]
        if decision.lower().replace("_", "") not in [v.lower().replace("_", "") for v in rule["values"]]:
            results.append(ValidationResult(
                valid=False,
                level=rule["level"],
                rule="valid_decision",
                message=f"Invalid decision '{decision}'",
                agent_id=agent_id,
                field="decision",
                value=None,
                constraint=str(rule["values"])
            ))
        
        self._categorize_results(results)
        return results
    
    def validate_government(
        self,
        agent_id: str,
        decision: str,
        subsidy_rate: float,
        prev_subsidy_rate: float,
        budget_used: float,
        mg_adoption: float = 0.0,
        nmg_adoption: float = 0.0
    ) -> List[ValidationResult]:
        """Validate government agent decision."""
        results = []
        
        # 1. Subsidy bounds
        rule = self.GOVERNMENT_RULES["subsidy_bounds"]
        if not (rule["min"] <= subsidy_rate <= rule["max"]):
            results.append(ValidationResult(
                valid=False,
                level=rule["level"],
                rule="subsidy_bounds",
                message=f"Subsidy rate {subsidy_rate:.0%} outside bounds [{rule['min']:.0%}, {rule['max']:.0%}]",
                agent_id=agent_id,
                field="subsidy_rate",
                value=subsidy_rate,
                constraint=f"[{rule['min']}, {rule['max']}]"
            ))
        
        # 2. Max change
        rule = self.GOVERNMENT_RULES["max_change"]
        delta = abs(subsidy_rate - prev_subsidy_rate)
        if delta > rule["max_delta"]:
            results.append(ValidationResult(
                valid=False,
                level=rule["level"],
                rule="max_change",
                message=f"Subsidy change {delta:.1%} exceeds max {rule['max_delta']:.0%}",
                agent_id=agent_id,
                field="subsidy_rate",
                value=delta,
                constraint=f"max_delta={rule['max_delta']}"
            ))
        
        # 3. Emergency reserve
        rule = self.GOVERNMENT_RULES["emergency_reserve"]
        if budget_used > rule["max"]:
            results.append(ValidationResult(
                valid=False,
                level=rule["level"],
                rule="emergency_reserve",
                message=f"Budget used {budget_used:.0%} exceeds {rule['max']:.0%} (no emergency reserve)",
                agent_id=agent_id,
                field="budget_used",
                value=budget_used,
                constraint=f"max={rule['max']}"
            ))
        
        # 4. Valid decision
        rule = self.GOVERNMENT_RULES["valid_decision"]
        if decision.lower().replace("_", "") not in [v.lower().replace("_", "") for v in rule["values"]]:
            results.append(ValidationResult(
                valid=False,
                level=rule["level"],
                rule="valid_decision",
                message=f"Invalid decision '{decision}'",
                agent_id=agent_id,
                field="decision",
                value=None,
                constraint=str(rule["values"])
            ))
        
        # 5. MG priority check (soft warning)
        if mg_adoption < nmg_adoption and decision in ["DECREASE", "decrease_subsidy"]:
            results.append(ValidationResult(
                valid=True,  # Soft warning, not rejection
                level=ValidationLevel.WARNING,
                rule="mg_priority",
                message=f"Decreasing subsidy while MG adoption ({mg_adoption:.0%}) < NMG ({nmg_adoption:.0%})",
                agent_id=agent_id,
                field="equity_gap",
                value=nmg_adoption - mg_adoption,
                constraint="MG priority policy"
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
