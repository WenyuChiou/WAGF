"""
Exp3 Validators - PMT Construct Validation

Validates household decisions based on PMT construct consistency:
- R1: HIGH TP + HIGH CP → Should NOT do_nothing
- R2: LOW TP → do_nothing is acceptable
- R3: FULL PA → Should NOT elevate again
- R4: Renter → Cannot elevate_house
- R5: LOW CP + HIGH cost action → Warning (may not afford)

Separate from audit - validator checks logical consistency,
audit records all decisions regardless of validation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from examples.exp3_multi_agent.parsers import HouseholdOutput


@dataclass
class ValidationResult:
    """Result of validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rule_checks: Dict[str, bool] = field(default_factory=dict)


class HouseholdValidator:
    """
    Validates household agent decisions for PMT consistency.
    
    Rules based on PMT literature:
    - Threat Appraisal alone should not lead to extreme actions
    - Coping Appraisal is needed for protective behavior
    - Construct levels should be internally consistent with decision
    """
    
    def validate(
        self, 
        output: HouseholdOutput, 
        agent_state: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate a household decision.
        
        Args:
            output: Parsed LLM output with constructs and decision
            agent_state: Current agent state
            
        Returns:
            ValidationResult with errors, warnings, and rule checks
        """
        errors = []
        warnings = []
        rule_checks = {}
        
        # R1: HIGH TP + HIGH CP → Should NOT do_nothing
        rule_checks["R1_high_tp_cp_action"] = self._check_r1(output, errors, warnings)
        
        # R2: LOW TP → do_nothing is acceptable (no warning)
        rule_checks["R2_low_tp_ok"] = self._check_r2(output, warnings)
        
        # R3: FULL PA → Should NOT elevate again
        rule_checks["R3_no_redundant_action"] = self._check_r3(output, agent_state, errors)
        
        # R4: Renter → Cannot elevate_house
        rule_checks["R4_renter_constraint"] = self._check_r4(output, errors)
        
        # R5: LOW CP + HIGH cost action → Warning
        rule_checks["R5_affordability"] = self._check_r5(output, warnings)
        
        # R6: Already relocated → Cannot take any action
        rule_checks["R6_relocated_constraint"] = self._check_r6(output, agent_state, errors)
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            rule_checks=rule_checks
        )
    
    def _check_r1(self, output: HouseholdOutput, errors: List, warnings: List) -> bool:
        """R1: HIGH TP + HIGH CP → Should NOT do_nothing"""
        if output.tp_level == "HIGH" and output.cp_level == "HIGH":
            if output.decision_skill == "do_nothing":
                warnings.append(
                    "R1: HIGH threat + HIGH coping but chose do_nothing - "
                    "possible irrational behavior"
                )
                return False
        return True
    
    def _check_r2(self, output: HouseholdOutput, warnings: List) -> bool:
        """R2: LOW TP → do_nothing is acceptable"""
        if output.tp_level == "LOW" and output.decision_skill != "do_nothing":
            # Not an error, but notable
            warnings.append(
                "R2: LOW threat but took protective action - "
                "precautionary behavior (acceptable)"
            )
        return True
    
    def _check_r3(self, output: HouseholdOutput, state: Dict, errors: List) -> bool:
        """R3: FULL PA or already elevated → Should NOT elevate again"""
        if output.decision_skill == "elevate_house":
            if state.get("elevated", False):
                errors.append("R3: Cannot elevate - house already elevated")
                return False
            if output.pa_level == "FULL":
                errors.append("R3: PA=FULL indicates full protection - elevation unnecessary")
                return False
        return True
    
    def _check_r4(self, output: HouseholdOutput, errors: List) -> bool:
        """R4: Renter → Cannot elevate_house"""
        if output.tenure == "Renter" and output.decision_skill == "elevate_house":
            errors.append("R4: Renters cannot elevate property they don't own")
            return False
        return True
    
    def _check_r5(self, output: HouseholdOutput, warnings: List) -> bool:
        """R5: LOW CP + HIGH cost action → Warning"""
        high_cost_actions = ["elevate_house", "relocate"]
        if output.cp_level == "LOW" and output.decision_skill in high_cost_actions:
            warnings.append(
                f"R5: LOW coping perception but chose {output.decision_skill} - "
                "may face affordability issues"
            )
            return False
        return True
    
    def _check_r6(self, output: HouseholdOutput, state: Dict, errors: List) -> bool:
        """R6: Already relocated → Cannot take any action"""
        if state.get("relocated", False) and output.decision_skill != "do_nothing":
            errors.append("R6: Already relocated - cannot take further flood actions")
            return False
        return True


class InstitutionalValidator:
    """
    Validates institutional agent (Insurance/Government) decisions.
    """
    
    def validate_insurance(self, decision: str, loss_ratio: float) -> ValidationResult:
        """
        Validate insurance decision consistency.
        
        Rules:
        - Loss ratio > 1.0 → Should RAISE premium
        - Loss ratio < 0.5 → Can LOWER premium
        """
        warnings = []
        
        if loss_ratio > 1.0 and decision == "LOWER":
            warnings.append("Insurance: Loss ratio > 1 but lowering premium - risky")
        
        if loss_ratio < 0.3 and decision == "RAISE":
            warnings.append("Insurance: Very low loss ratio but raising - may lose customers")
        
        return ValidationResult(valid=True, warnings=warnings)
    
    def validate_government(
        self, 
        decision: str, 
        budget_remaining_pct: float,
        mg_adoption: float
    ) -> ValidationResult:
        """
        Validate government decision consistency.
        
        Rules:
        - Low budget → Should not INCREASE subsidy
        - Low MG adoption + budget available → Consider prioritizing MG
        """
        warnings = []
        
        if budget_remaining_pct < 0.2 and decision == "INCREASE":
            warnings.append("Government: Less than 20% budget but increasing subsidy")
        
        if mg_adoption < 0.2 and budget_remaining_pct > 0.5:
            warnings.append("Government: Low MG adoption with ample budget - consider MG priority")
        
        return ValidationResult(valid=True, warnings=warnings)
