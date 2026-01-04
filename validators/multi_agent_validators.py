"""
Multi-Agent Validators for Experiment 3.

Validators organized by agent type:
1. Household: ConstructConsistencyValidator, MGSubsidyConsistencyValidator
2. Government: GovernmentBudgetValidator
3. Insurance: InsurancePolicyValidator

Literature Support:
- ConstructConsistencyValidator: Grothmann 2006, Bamberg 2017, Weyrich 2020, PADM
- See docs/validator_design_readme.md for full citations
"""

from typing import Dict, Any, List
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from broker.skill_types import SkillProposal, ValidationResult
from broker.skill_registry import SkillRegistry
from validators.skill_validators import (
    SkillValidator, 
    SkillAdmissibilityValidator,
    ContextFeasibilityValidator,
    InstitutionalConstraintValidator,
    EffectSafetyValidator
)


# ============================================================================
# HOUSEHOLD VALIDATORS
# ============================================================================

class AgentTypeAdmissibilityValidator(SkillAdmissibilityValidator):
    """
    Extended admissibility for multi-agent types.
    
    Checks skill ↔ agent type (Owner/Renter) compatibility.
    """
    
    name = "AgentTypeAdmissibilityValidator"
    
    # Skills only available to owners
    OWNER_ONLY_SKILLS = ["elevate_house", "buyout_program"]
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        # First run base admissibility
        base_result = super().validate(proposal, context, registry)
        if not base_result.valid:
            return base_result
        
        errors = []
        agent_type = context.get("agent_type", "")
        
        # Renter cannot use owner-only skills
        if "renter" in agent_type.lower():
            if proposal.skill_name in self.OWNER_ONLY_SKILLS:
                errors.append(f"Renter cannot use owner-only skill: {proposal.skill_name}")
        
        return ValidationResult(
            valid=len(errors) == 0, 
            validator_name=self.name, 
            errors=errors
        )


class ConstructConsistencyValidator(SkillValidator):
    """
    Validate consistency between constructs (TP/CP/SP) and decision.
    
    Uses explicit construct levels (LOW/MODERATE/HIGH) from LLM output
    instead of keyword matching like PMTConsistencyValidator.
    
    Literature Support:
    - R1: Grothmann & Reusswig (2006) - HIGH TP + HIGH CP → protection motivation
    - R2: Bamberg et al. (2017) Meta-analysis - CP is strongest predictor
    - R3: Rogers (1983) PMT - TP necessary for extreme response
    - R4: PADM (Lindell & Perry, 2012) - Stakeholder perception matters
    """
    
    name = "ConstructConsistencyValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        warnings = []
        
        # Get parsed construct levels from LLM output
        tp = context.get("parsed_tp_level", "MODERATE").upper()  # LOW/MODERATE/HIGH
        cp = context.get("parsed_cp_level", "MODERATE").upper()
        sp = context.get("parsed_sp_level", "MODERATE").upper()
        skill = proposal.skill_name
        
        expensive_actions = ["elevate_house", "relocate", "buyout_program"]
        extreme_actions = ["relocate", "buyout_program"]
        
        # === ERROR RULES (Trigger retry) ===
        
        # R1: HIGH TP + HIGH CP + do_nothing = inconsistent
        # Citation: Grothmann & Reusswig (2006) - this combination should lead to action
        if tp == "HIGH" and cp == "HIGH" and skill == "do_nothing":
            errors.append("R1: HIGH TP + HIGH CP should motivate action [Grothmann 2006]")
        
        # R2: LOW CP + expensive action = inconsistent
        # Citation: Bamberg et al. (2017) - CP is strongest predictor; LOW CP = cannot afford
        if cp == "LOW" and skill in expensive_actions:
            errors.append("R2: LOW CP cannot afford expensive action [Bamberg 2017]")
        
        # R3: LOW TP + extreme action = overreaction
        # Citation: Rogers (1983) PMT - threat appraisal necessary for extreme response
        if tp == "LOW" and skill in extreme_actions:
            errors.append("R3: LOW TP does not justify extreme action [Rogers 1983]")
        
        # R4: LOW SP + LOW TP + buy_insurance = irrational
        # Citation: PADM - no threat + distrust = no motivation
        if sp == "LOW" and tp == "LOW" and skill == "buy_insurance":
            errors.append("R4: LOW SP + LOW TP makes insurance purchase irrational [PADM]")
        
        # === WARNING RULES (Log only) ===
        
        # R5: LOW SP + buy_insurance (with threat) = unusual but possible
        # Citation: Trust literature - fear may override distrust
        if sp == "LOW" and tp in ["MODERATE", "HIGH"] and skill == "buy_insurance":
            warnings.append("R5: LOW SP but chose insurance - fear overrides distrust?")
        
        # === VALID NON-PROTECTIVE PATH ===
        # HIGH TP + LOW CP + do_nothing is VALID (fatalism/denial)
        # Citation: Grothmann & Reusswig (2006) - non-protective responses documented
        
        return ValidationResult(
            valid=len(errors) == 0, 
            validator_name=self.name, 
            errors=errors, 
            warnings=warnings
        )


class MGSubsidyConsistencyValidator(SkillValidator):
    """
    Validate MG subsidy logic consistency.
    
    Ensures Marginalized Group agents properly account for available subsidies.
    """
    
    name = "MGSubsidyConsistencyValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        warnings = []
        
        is_mg = context.get("is_MG", False)
        subsidy_rate = context.get("subsidy_rate", 0)
        skill = proposal.skill_name
        cp_explanation = context.get("parsed_cp_explanation", "").lower()
        
        # MG has subsidy but claims "cannot afford" + chose do_nothing
        if is_mg and subsidy_rate > 0.3:
            if "cannot afford" in cp_explanation and skill == "do_nothing":
                warnings.append("MG has >30% subsidy available but claims cannot afford")
        
        # NMG incorrectly references subsidy
        if not is_mg:
            sp_explanation = context.get("parsed_sp_explanation", "").lower()
            if "subsidy" in sp_explanation and "may qualify" not in sp_explanation:
                warnings.append("NMG references MG-specific subsidy")
        
        return ValidationResult(
            valid=len(errors) == 0, 
            validator_name=self.name, 
            errors=errors,
            warnings=warnings
        )


# ============================================================================
# GOVERNMENT VALIDATORS
# ============================================================================

class GovernmentBudgetValidator(SkillValidator):
    """
    Validate Government agent budget consistency.
    
    Ensures budget decisions are fiscally rational.
    """
    
    name = "GovernmentBudgetValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        warnings = []
        
        budget_remaining = context.get("budget_remaining", 1)
        budget_total = context.get("budget_total", 1)
        adoption_rate = context.get("mg_adoption_rate", 0.5)
        skill = proposal.skill_name
        
        budget_ratio = budget_remaining / max(budget_total, 1)
        
        # R1: Budget nearly exhausted + increase_subsidy = fiscally irresponsible
        if budget_ratio < 0.20 and skill == "increase_subsidy":
            errors.append("R1: Budget <20% but chose increase_subsidy - unsustainable")
        
        # R2: Low adoption + maintain_subsidy = may need adjustment
        if adoption_rate < 0.3 and skill == "maintain_subsidy":
            warnings.append("R2: Low adoption (<30%) but maintaining subsidy - consider increase")
        
        # R3: High adoption + increase_subsidy = may be unnecessary
        if adoption_rate > 0.7 and skill == "increase_subsidy":
            warnings.append("R3: High adoption (>70%) - subsidy increase may be unnecessary")
        
        return ValidationResult(
            valid=len(errors) == 0, 
            validator_name=self.name, 
            errors=errors,
            warnings=warnings
        )


# ============================================================================
# INSURANCE VALIDATORS
# ============================================================================

class InsurancePolicyValidator(SkillValidator):
    """
    Validate Insurance agent decision logic.
    
    Ensures premium decisions align with loss ratio.
    """
    
    name = "InsurancePolicyValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        warnings = []
        
        loss_ratio = context.get("loss_ratio", 0.5)
        take_up_rate = context.get("take_up_rate", 0.5)
        skill = proposal.skill_name
        
        # R1: High loss ratio + lower_premium = unsustainable
        if loss_ratio > 0.80 and skill == "lower_premium":
            errors.append("R1: High loss ratio (>80%) but chose lower_premium - unsustainable")
        
        # R2: Low loss ratio + raise_premium = may lose customers
        if loss_ratio < 0.30 and skill == "raise_premium":
            warnings.append("R2: Low loss ratio (<30%) but raising premium - may lose customers")
        
        # R3: Low take-up + raise_premium = counterproductive
        if take_up_rate < 0.3 and skill == "raise_premium":
            warnings.append("R3: Low take-up (<30%) + raise_premium may reduce adoption further")
        
        return ValidationResult(
            valid=len(errors) == 0, 
            validator_name=self.name, 
            errors=errors,
            warnings=warnings
        )


# ============================================================================
# VALIDATOR FACTORY
# ============================================================================

def create_validators_for_agent(agent_type: str) -> List[SkillValidator]:
    """
    Create appropriate validator pipeline based on agent type.
    
    Args:
        agent_type: One of 'household_owner', 'household_renter', 
                    'insurance', 'government'
    
    Returns:
        List of validators for the agent type
    """
    
    if agent_type in ["household_owner", "household_renter", "MG_Owner", "MG_Renter", 
                       "NMG_Owner", "NMG_Renter"]:
        return [
            AgentTypeAdmissibilityValidator(),
            ContextFeasibilityValidator(),
            InstitutionalConstraintValidator(),
            EffectSafetyValidator(),
            ConstructConsistencyValidator(),
            MGSubsidyConsistencyValidator(),
        ]
    elif agent_type == "insurance":
        return [
            SkillAdmissibilityValidator(),
            InsurancePolicyValidator(),
        ]
    elif agent_type == "government":
        return [
            SkillAdmissibilityValidator(),
            GovernmentBudgetValidator(),
        ]
    else:
        # Default: basic admissibility only
        return [SkillAdmissibilityValidator()]
