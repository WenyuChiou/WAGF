"""
Physical Validator - State preconditions and action immutability.

Validates:
- State preconditions (already completed irreversible actions)
- Role restrictions (cannot modify property without ownership)
- Action immutability (irreversible decisions)

Domain-specific built-in checks are injected via ``builtin_checks``.
Default is empty (domain-agnostic).  Flood-domain checks live in
``examples/governed_flood/validators/flood_validators.py``.

Design note — insurance renewal:
    ``buy_insurance`` is deliberately NOT checked for "already insured".
    Insurance is an annual renewable action (expires each year if not
    renewed).  Unlike elevation and relocation (irreversible one-time
    actions), insurance renewal is expected rational behavior.  See
    ``ResearchSimulation.execute_skill()`` for annual expiry logic.
"""
from typing import List, Optional
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck


class PhysicalValidator(BaseValidator):
    """
    Validates physical state: preconditions and immutable states.

    Pass domain-specific ``builtin_checks`` for flood, irrigation, etc.
    Default is empty (YAML rules only).
    """

    def __init__(self, builtin_checks: Optional[List[BuiltinCheck]] = None):
        super().__init__(builtin_checks=builtin_checks)

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Empty — domain checks injected via validate_all(domain=...)."""
        return []

    @property
    def category(self) -> str:
        return "physical"
