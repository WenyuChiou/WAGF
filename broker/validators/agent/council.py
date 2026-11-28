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
    def __init__(
        self,
        validators: List[Any],
        consensus_mode: str = "MAJORITY",
        weights: Optional[List[float]] = None,
        quorum_threshold: float = 0.5,
    ):
        # The MAJORITY-mode quorum was a
        # hardcoded ``>= 0.5`` literal inside ``validate``; extracted to
        # a constructor kwarg so a domain that wants a super-majority
        # (2/3 ≈ 0.667) or qualified-majority can declare it via
        # ``governance.population.quorum_threshold`` in YAML / via
        # ``DomainPack.population_governance_policy()``. Default 0.5
        # preserves prior behaviour byte-for-byte.
        self.validators = validators
        self.consensus_mode = consensus_mode
        self.weights = weights or [1.0] * len(validators)
        self.quorum_threshold = quorum_threshold
        self.errors = []
        self.warnings = []

    def validate(self, proposal, context, registry) -> List[ValidationResult]:
        """Validate using multiple sub-validators once and aggregate results."""
        self.errors = []
        self.warnings = []

        if not self.validators:
            return []

        per_validator: List[List[ValidationResult]] = []
        all_results: List[ValidationResult] = []
        for validator in self.validators:
            res = validator.validate(proposal, context, registry)
            group = res if isinstance(res, list) else [res]
            per_validator.append(group)
            all_results.extend(group)

        if self.consensus_mode == "UNANIMOUS":
            return all_results

        if self.consensus_mode == "MAJORITY":
            total_votes = len(self.validators)
            passed_votes = sum(
                1 for group in per_validator if all(r.valid for r in group)
            )
            if (passed_votes / total_votes) >= self.quorum_threshold:
                return [r for r in all_results if r.valid]
            return [r for r in all_results if not r.valid]

        return all_results

    def reset(self):
        for v in self.validators:
            if hasattr(v, 'reset'): v.reset()
