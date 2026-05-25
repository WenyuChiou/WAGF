"""
Personal Validator - Financial and Cognitive constraints.

Validates:
- Financial affordability (savings vs costs, income limits)
- Cognitive capability (extreme states blocking options)

Domain-specific built-in checks are injected via ``builtin_checks``.
Default is empty (domain-agnostic).  Flood-domain checks live in
``examples/governed_flood/validators/flood_validators.py``.
"""
from typing import List, Optional
from broker.validators.governance.base_validator import BaseValidator, BuiltinCheck


class PersonalValidator(BaseValidator):

    """
    Validates personal constraints: financial affordability and cognitive capability.

    Pass domain-specific ``builtin_checks`` for flood, irrigation, etc.
    Default is empty (YAML rules only).
    """


    # Phase 6O-A-2: financial affordability is the dominant case (cannot-afford = terminal); cognitive sub-cases that are softer are not yet implemented and ride this default until 6O-A-3.
    _DEFAULT_EXPECTED_TERMINAL: bool = True
    _DEFAULT_CONSTRAINT_TYPE: str = "hard"
    def __init__(self, builtin_checks: Optional[List[BuiltinCheck]] = None):
        super().__init__(builtin_checks=builtin_checks)

    def _default_builtin_checks(self) -> List[BuiltinCheck]:
        """Empty — domain checks injected via validate_all(domain=...)."""
        return []

    @property
    def category(self) -> str:
        return "personal"
