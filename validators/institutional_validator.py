"""
Institutional Agent Validator (Deprecated)

This module is now an alias for the generic AgentValidator.
All specific validation rules are now defined in agent_types.yaml.
"""
from typing import Dict, List, Any
from .agent_validator import AgentValidator, ValidationResult, ValidationLevel

# Usage: InstitutionalValidator() -> AgentValidator()
class InstitutionalValidator(AgentValidator):
    """
    Deprecated alias for AgentValidator.
    Please use AgentValidator directly.
    """
    def __init__(self, config_path: str = None):
        super().__init__(config_path)
    
    # Forward legacy method calls to generic validate() if needed,
    # but the framework call sites should be updated to use .validate()
    # For now, we assume the caller uses .validate() or we add shims.

    def validate_insurance(self, agent_id: str, decision: str, premium_rate: float, prev_premium_rate: float, solvency: float) -> List[ValidationResult]:
        """Shim for legacy validate_insurance call."""
        # Map args to state dict
        state = {
            "premium_rate": premium_rate,
            "solvency": solvency
        }
        prev_state = {
            "premium_rate": prev_premium_rate
        }
        # Call generic validate
        return self.validate(
            agent_type="insurance",
            agent_id=agent_id,
            decision=decision,
            state=state,
            prev_state=prev_state
        )

    def validate_government(self, agent_id: str, decision: str, subsidy_rate: float, prev_subsidy_rate: float, budget_used: float, mg_adoption: float = 0.0, nmg_adoption: float = 0.0) -> List[ValidationResult]:
        """Shim for legacy validate_government call."""
        state = {
            "subsidy_rate": subsidy_rate,
            "budget_used": budget_used,
            "mg_adoption": mg_adoption,
            "nmg_adoption": nmg_adoption
        }
        prev_state = {
            "subsidy_rate": prev_subsidy_rate
        }
        return self.validate(
            agent_type="government",
            agent_id=agent_id,
            decision=decision,
            state=state,
            prev_state=prev_state
        )
