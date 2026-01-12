"""
Multi-Agent Validation Rules

Validates household decisions based on:
1. Tenure constraints (Owner vs Renter)
2. State constraints (already elevated, relocated)
3. PMT consistency (5 constructs)

References:
- PMT: Rogers (1983), Grothmann & Reusswig (2006)
- Flood adaptation: Bubeck et al. (2012), Bamberg et al. (2017)
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of validation check."""
    valid: bool
    errors: List[str]
    warnings: List[str]
    blocked_skill: Optional[str] = None
    suggested_skill: Optional[str] = None


class MultiAgentValidator:
    """
    Validator for multi-agent household decisions.
    
    Rules:
    - R1: Renters cannot buyout (only owners can participate in buyout program)
    - R2: Renters cannot elevate (they don't own the structure)
    - R3: Owners cannot relocate (they can only buyout)
    - R4: Cannot elevate twice (already elevated)
    - R5: Already relocated agents cannot make decisions
    - R6: HIGH TP + HIGH CP → should NOT do_nothing
    - R7: LOW CP → should NOT choose expensive options (elevate, relocate)
    """
    
    OWNER_SKILLS = {"buy_insurance", "elevate_house", "buyout_program", "do_nothing"}
    RENTER_SKILLS = {"buy_contents_insurance", "relocate", "do_nothing"}
    EXPENSIVE_SKILLS = {"elevate_house", "buyout_program", "relocate"}
    
    def validate(
        self,
        decision: str,
        agent_state: Dict[str, Any],
        constructs: Optional[Dict[str, str]] = None
    ) -> ValidationResult:
        """
        Validate a household decision.
        
        Args:
            decision: Proposed skill/action
            agent_state: Current agent state dict
            constructs: Optional PMT constructs (TP, CP, SP, SC, PA)
            
        Returns:
            ValidationResult with errors/warnings
        """
        errors = []
        warnings = []
        
        tenure = agent_state.get("tenure", "Owner")
        elevated = agent_state.get("elevated", False)
        relocated = agent_state.get("relocated", False)
        mg = agent_state.get("mg", False)
        
        # R5: Already relocated - no decisions allowed
        if relocated:
            if decision != "already_relocated":
                errors.append("Agent has already relocated and cannot make further decisions")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        # R1: Renters cannot buyout
        if tenure == "Renter" and decision == "buyout_program":
            errors.append("Renters cannot participate in buyout program (Owner-only action)")
        
        # R2: Renters cannot elevate
        if tenure == "Renter" and decision == "elevate_house":
            errors.append("Renters cannot elevate house (they don't own the structure)")
        
        # R3: Owners cannot relocate (must use buyout)
        if tenure == "Owner" and decision == "relocate":
            errors.append("Owners cannot relocate directly (use buyout_program instead)")
        
        # R4: Cannot elevate twice
        if elevated and decision == "elevate_house":
            errors.append("House is already elevated (cannot elevate twice)")
        
        # Tenure-based skill validation
        if tenure == "Owner" and decision not in self.OWNER_SKILLS:
            if decision == "buy_contents_insurance":
                warnings.append("Owner using buy_contents_insurance (should use buy_insurance)")
            elif decision not in {"already_relocated"}:
                errors.append(f"Invalid skill '{decision}' for Owner")
        
        if tenure == "Renter" and decision not in self.RENTER_SKILLS:
            if decision == "buy_insurance":
                # Accept but note it's contents-only for renters
                pass
            elif decision not in {"already_relocated"}:
                errors.append(f"Invalid skill '{decision}' for Renter")
        
        # PMT Consistency Rules (if constructs provided)
        if constructs:
            tp = constructs.get("TP", "MODERATE").upper()
            cp = constructs.get("CP", "MODERATE").upper()
            
            # R6: HIGH TP + HIGH CP → should act
            if tp == "HIGH" and cp == "HIGH" and decision == "do_nothing":
                warnings.append("HIGH Threat + HIGH Coping but chose do_nothing (inconsistent)")
            
            # R7: LOW CP → expensive actions blocked
            if cp == "LOW" and decision in self.EXPENSIVE_SKILLS:
                errors.append(f"LOW Coping but chose expensive action '{decision}'")
            
            # Additional soft checks
            if tp == "LOW" and decision in {"relocate", "buyout_program"}:
                warnings.append("LOW Threat but chose extreme action (possible overreaction)")
        
        valid = len(errors) == 0
        
        return ValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            blocked_skill=decision if not valid else None,
            suggested_skill="do_nothing" if not valid else None
        )
    
    def get_valid_skills(self, tenure: str, elevated: bool = False) -> List[str]:
        """Get list of valid skills for an agent based on tenure and state."""
        if tenure == "Owner":
            skills = list(self.OWNER_SKILLS)
            if elevated:
                skills.remove("elevate_house")
        else:
            skills = list(self.RENTER_SKILLS)
        return skills


# =============================================================================
# INSTITUTIONAL VALIDATORS (Future)
# =============================================================================

class GovernmentValidator:
    """Validator for State Government (FEMA partner) decisions."""
    
    def validate(self, decision: str, state: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []
        
        subsidy_rate = state.get("subsidy_rate", 0.5)
        budget_remaining = state.get("budget_remaining", 0)
        
        # Cannot increase subsidy if budget depleted
        if decision == "increase_subsidy" and budget_remaining < 10000:
            errors.append("Cannot increase subsidy with depleted budget")
        
        # Cannot increase subsidy above 95%
        if decision == "increase_subsidy" and subsidy_rate >= 0.95:
            warnings.append("Subsidy rate already at maximum (95%)")
        
        # Cannot decrease subsidy below 20%
        if decision == "decrease_subsidy" and subsidy_rate <= 0.20:
            warnings.append("Subsidy rate already at minimum (20%)")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


class InsuranceValidator:
    """Validator for Insurance (NFIP/FEMA) decisions."""
    
    def validate(self, decision: str, state: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []
        
        premium_rate = state.get("premium_rate", 0.05)
        loss_ratio = state.get("loss_ratio", 0.5)
        
        # Cannot lower premium if loss ratio > 100%
        if decision == "lower_premium" and loss_ratio > 1.0:
            errors.append("Cannot lower premium when loss ratio exceeds 100%")
        
        # Cannot raise premium above 15%
        if decision == "raise_premium" and premium_rate >= 0.15:
            warnings.append("Premium rate at regulatory maximum (15%)")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    validator = MultiAgentValidator()
    
    # Test cases
    tests = [
        # (decision, agent_state, constructs, expected_valid)
        ("buy_insurance", {"tenure": "Owner", "elevated": False}, None, True),
        ("elevate_house", {"tenure": "Renter", "elevated": False}, None, False),
        ("buyout_program", {"tenure": "Renter", "elevated": False}, None, False),
        ("relocate", {"tenure": "Owner", "elevated": False}, None, False),
        ("elevate_house", {"tenure": "Owner", "elevated": True}, None, False),
        ("do_nothing", {"tenure": "Owner"}, {"TP": "HIGH", "CP": "HIGH"}, True),  # Valid but warning
        ("elevate_house", {"tenure": "Owner"}, {"TP": "HIGH", "CP": "LOW"}, False),
    ]
    
    print("=== Multi-Agent Validator Tests ===\n")
    for decision, state, constructs, expected in tests:
        result = validator.validate(decision, state, constructs)
        status = "PASS" if result.valid == expected else "FAIL"
        print(f"[{status}] {decision} | tenure={state.get('tenure')} elevated={state.get('elevated', False)}")
        if result.errors:
            print(f"  Errors: {result.errors}")
        if result.warnings:
            print(f"  Warnings: {result.warnings}")
        print()
