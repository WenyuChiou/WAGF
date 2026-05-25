"""
Semantic Grounding Validator — validates reasoning against ground truth.

Prevents hallucinations where agent reasoning contradicts the simulation state:
- Hallucinated Social Proof: agent cites neighbor influence when isolated
- Temporal Grounding: agent references events that didn't occur
- State Consistency: agent reasoning contradicts its known state variables

Domain-specific built-in checks are injected via ``builtin_checks``.
Default is empty (domain-agnostic).  Flood-domain checks live in
``examples/governed_flood/validators/flood_validators.py``.
"""
from typing import List, Optional

from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck


class SemanticGroundingValidator(BaseValidator):

    """
    Validates that agent reasoning is grounded in the simulation state.

    Prevents hallucinations where the agent's reasoning text contradicts
    observable ground truth (social context, event history, agent state).

    Pass domain-specific ``builtin_checks`` for flood, irrigation, etc.
    Default is empty (YAML rules only).
    """


    # Phase 6O-A-2: semantic / grounding checks log inconsistency but never block — the model can always rephrase to ground its reasoning.
    _DEFAULT_EXPECTED_TERMINAL: bool = False
    _DEFAULT_CONSTRAINT_TYPE: str = "diagnostic"
    def __init__(self, builtin_checks: Optional[List[BuiltinCheck]] = None):
        super().__init__(builtin_checks=builtin_checks)

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Empty — domain checks injected via validate_all(domain=...)."""
        return []

    @property
    def category(self) -> str:
        return "semantic"
