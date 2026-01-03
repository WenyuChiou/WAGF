"""
Skill Validators - Governance-level validation for skill proposals.

The validation pipeline operates on skill proposals (NOT actions/tools):
1. Skill Admissibility - Does skill exist? Agent type has permission?
2. Context Feasibility - Current conditions (flood/budget/tenure) met?
3. Institutional Constraints - Once-only, annual limits, exclusivity?
4. Effect Safety - Only modifying allowed state fields?
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from broker.skill_types import SkillProposal, ValidationResult
from broker.skill_registry import SkillRegistry


class SkillValidator(ABC):
    """Base class for skill validators."""
    
    name: str = "BaseSkillValidator"
    
    @abstractmethod
    def validate(self, proposal: SkillProposal, context: Dict[str, Any], 
                 registry: SkillRegistry) -> ValidationResult:
        """Validate a skill proposal."""
        pass


class SkillAdmissibilityValidator(SkillValidator):
    """
    Validates skill admissibility.
    
    Checks:
    - Skill exists in registry
    - Agent type is eligible to use the skill
    """
    
    name = "SkillAdmissibilityValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        
        # Check skill exists
        if not registry.exists(proposal.skill_name):
            errors.append(f"Skill '{proposal.skill_name}' not found in registry")
            return ValidationResult(valid=False, validator_name=self.name, errors=errors)
        
        # Check eligibility
        agent_type = context.get("agent_type", "default")
        eligibility = registry.check_eligibility(proposal.skill_name, agent_type)
        if not eligibility.valid:
            errors.extend(eligibility.errors)
        
        return ValidationResult(
            valid=len(errors) == 0,
            validator_name=self.name,
            errors=errors
        )


class ContextFeasibilityValidator(SkillValidator):
    """
    Validates context feasibility.
    
    Checks if current flood/budget/tenure conditions are met for the skill.
    """
    
    name = "ContextFeasibilityValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        
        # Check preconditions from registry
        agent_state = context.get("agent_state", {})
        precondition_result = registry.check_preconditions(proposal.skill_name, agent_state)
        if not precondition_result.valid:
            errors.extend(precondition_result.errors)
        
        return ValidationResult(
            valid=len(errors) == 0,
            validator_name=self.name,
            errors=errors
        )


class InstitutionalConstraintValidator(SkillValidator):
    """
    Validates institutional constraints.
    
    Checks: once-only rules, annual limits, mutual exclusivity, etc.
    """
    
    name = "InstitutionalConstraintValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        
        skill_def = registry.get(proposal.skill_name)
        if not skill_def:
            return ValidationResult(valid=True, validator_name=self.name)
        
        constraints = skill_def.institutional_constraints
        agent_state = context.get("agent_state", {})
        
        # Check once_only constraint
        if constraints.get("once_only", False):
            # If skill is already used (state already True), cannot use again
            for field in skill_def.allowed_state_changes:
                if agent_state.get(field, False):
                    errors.append(f"Skill '{proposal.skill_name}' is once-only and already used")
                    break
        
        # Check permanent constraint
        if constraints.get("permanent", False) and agent_state.get("relocated", False):
            errors.append("Agent has already permanently relocated")
        
        return ValidationResult(
            valid=len(errors) == 0,
            validator_name=self.name,
            errors=errors
        )


class EffectSafetyValidator(SkillValidator):
    """
    Validates effect safety.
    
    Ensures skills only modify fields they are allowed to change.
    """
    
    name = "EffectSafetyValidator"
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        # Effect safety is enforced at execution time by the simulation engine
        # This validator ensures the skill definition has proper constraints
        
        skill_def = registry.get(proposal.skill_name)
        if not skill_def:
            return ValidationResult(valid=True, validator_name=self.name)
        
        # Validate that allowed_state_changes is properly defined
        warnings = []
        if not skill_def.allowed_state_changes and proposal.skill_name != "do_nothing":
            warnings.append(f"Skill '{proposal.skill_name}' has no defined state changes")
        
        return ValidationResult(
            valid=True,
            validator_name=self.name,
            warnings=warnings
        )


class PMTConsistencyValidator(SkillValidator):
    """
    Validates PMT (Protection Motivation Theory) consistency.
    
    Detects contradictions between reasoning and skill choice.
    """
    
    name = "PMTConsistencyValidator"
    
    HIGH_THREAT_KEYWORDS = ["worried", "concerned", "scared", "at risk", "dangerous", "vulnerable", "threatened"]
    HIGH_EFFICACY_KEYWORDS = ["can protect", "effective", "would help", "prevent damage", "reduce risk"]
    LOW_THREAT_KEYWORDS = ["not worried", "safe", "no risk", "unlikely", "minimal"]
    CANNOT_AFFORD_KEYWORDS = ["cannot afford", "too expensive", "not enough money", "high cost", "financial burden"]
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        errors = []
        
        threat = proposal.reasoning.get("threat", "").lower()
        coping = proposal.reasoning.get("coping", "").lower()
        skill = proposal.skill_name
        flood_status = context.get("flood_status", "")
        
        # Rule 1: High threat + High efficacy + Do Nothing = Inconsistent
        has_high_threat = any(kw in threat for kw in self.HIGH_THREAT_KEYWORDS)
        has_high_efficacy = any(kw in coping for kw in self.HIGH_EFFICACY_KEYWORDS)
        
        if has_high_threat and has_high_efficacy and skill == "do_nothing":
            errors.append("PMT inconsistency: High threat + High efficacy but chose do_nothing")
        
        # Rule 2: Low threat + Relocate = Inconsistent
        has_low_threat = any(kw in threat for kw in self.LOW_THREAT_KEYWORDS)
        if has_low_threat and skill == "relocate":
            errors.append("Claims low threat but chose relocate")
        
        # Rule 3: Flood occurred + Claims safe = Inconsistent
        if "flood occurred" in flood_status.lower():
            if any(kw in threat for kw in ["feel safe", "not worried", "no concern"]):
                errors.append("Flood Response: Claims safe despite flood event this year")
        
        # Rule 4: Cannot afford + Expensive option (Aligned with MCP)
        is_expensive = skill in ["elevate_house", "relocate"]
        if is_expensive and any(kw in coping for kw in self.CANNOT_AFFORD_KEYWORDS):
            errors.append("Claims cannot afford but chose expensive option")
            
        # Rule 5: Already have + Buy again - ALLOWED for annual renewal models
        # if "already have insurance" in coping and skill == "buy_insurance":
        #    errors.append("Claims already has insurance but chose to buy")
        
        return ValidationResult(
            valid=len(errors) == 0,
            validator_name=self.name,
            errors=errors
        )


class UncertaintyValidator(SkillValidator):
    """
    Validates response certainty.
    
    Detects ambiguous or uncertain language in LLM responses that may indicate
    low confidence in the decision. Such responses trigger a retry.
    """
    
    name = "UncertaintyValidator"
    
    # Keywords indicating uncertainty in the response
    UNCERTAIN_KEYWORDS = [
        "maybe", "perhaps", "not sure", "i think", "might",
        "could be", "possibly", "i believe", "uncertain",
        "don't know", "hard to say", "difficult to decide",
        "i'm unsure", "can't decide", "not certain"
    ]
    
    def validate(self, proposal: SkillProposal, context: Dict[str, Any],
                 registry: SkillRegistry) -> ValidationResult:
        raw = proposal.raw_output.lower()
        
        # Check for uncertain keywords
        found_keywords = [kw for kw in self.UNCERTAIN_KEYWORDS if kw in raw]
        
        if found_keywords:
            return ValidationResult(
                valid=False,
                validator_name=self.name,
                errors=[f"Uncertain language detected: {', '.join(found_keywords[:3])}"]
            )
        
        return ValidationResult(valid=True, validator_name=self.name)


def create_default_validators() -> List[SkillValidator]:
    """Create the default set of skill validators."""
    return [
        SkillAdmissibilityValidator(),
        ContextFeasibilityValidator(),
        InstitutionalConstraintValidator(),
        EffectSafetyValidator(),
        PMTConsistencyValidator(),
        # UncertaintyValidator()  # Temporarily disabled - triggers too often on PMT reasoning
    ]
