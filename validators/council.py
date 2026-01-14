from typing import List, Dict, Any, Optional
from broker.interfaces.skill_types import ValidationResult

class CouncilValidator:
    """
    Agent Council Validator (Phase 28).
    
    Orchestrates multiple validators (Institutional Agents or Rules) 
    to achieve consensus on a proposal.
    
    Modes:
    - UNANIMOUS: All validators must return valid=True.
    - MAJORITY: More than half of validators must return valid=True.
    """
    def __init__(self, validators: List[Any], consensus_mode: str = "MAJORITY", weights: Optional[List[float]] = None):
        self.validators = validators
        self.consensus_mode = consensus_mode
        self.weights = weights or [1.0] * len(validators)
        self.errors = []
        self.warnings = []

    def validate(self, proposal, context, registry) -> List[ValidationResult]:
        """Validate using multiple sub-validators and aggregate results."""
        self.errors = []
        self.warnings = []
        
        all_results = []
        for validator in self.validators:
            res = validator.validate(proposal, context, registry)
            if isinstance(res, list):
                all_results.extend(res)
            else:
                all_results.append(res)
        
        # Determine consensus
        if self.consensus_mode == "UNANIMOUS":
            return all_results
        
        elif self.consensus_mode == "MAJORITY":
            # For each distinct rule/type of validation, if majority fail, then it's an error.
            # But the SkillBrokerEngine treats any ValidationResult with valid=False as a block.
            # So CouncilValidator must return a SINGLE (or reduced) set of ValidationResults
            # that represent the council's decision.
            
            valid_votes = 0
            total_votes = len(self.validators)
            
            # Count valid validators (a validator is valid if all its results are valid)
            # This is a bit simplified.
            for validator in self.validators:
                # We need to re-run or inspect results per validator.
                # Since we flattened all_results, we lost the per-validator grouping.
                pass
            
            # Alternative: Run and check each
            validator_votes = []
            for validator in self.validators:
                res = validator.validate(proposal, context, registry)
                is_ok = True
                if isinstance(res, list):
                    if any(not r.valid for r in res): is_ok = False
                elif not res.valid:
                    is_ok = False
                validator_votes.append(is_ok)
            
            passed_votes = sum(1 for v in validator_votes if v)
            if (passed_votes / total_votes) >= 0.5:
                # Council approves, even if some validators failed
                # Return empty list or only warnings
                return [r for r in all_results if r.valid]
            else:
                # Council rejects
                # Return all errors
                return [r for r in all_results if not r.valid]
        
        return all_results

    def reset(self):
        for v in self.validators:
            if hasattr(v, 'reset'): v.reset()
