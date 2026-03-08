"""
Water-domain validator bundle adapters.

This module isolates water-specific builtin validator wiring from the generic
governance entrypoint so `broker.validators.governance` does not import
example packages directly.
"""

from typing import List, Optional

from broker.validators.governance.base_validator import BuiltinCheck
from broker.validators.governance.personal_validator import PersonalValidator
from broker.validators.governance.social_validator import SocialValidator
from broker.validators.governance.thinking_validator import ThinkingValidator
from broker.validators.governance.physical_validator import PhysicalValidator
from broker.validators.governance.semantic_validator import SemanticGroundingValidator


def _empty_validators() -> list:
    no_builtins: List[BuiltinCheck] = []
    return [
        PersonalValidator(builtin_checks=no_builtins),
        PhysicalValidator(builtin_checks=no_builtins),
        ThinkingValidator(builtin_checks=no_builtins),
        SocialValidator(builtin_checks=no_builtins),
        SemanticGroundingValidator(builtin_checks=no_builtins),
    ]


def build_domain_validators(domain: Optional[str]) -> list:
    """Return builtin validator instances for a water-domain name."""
    resolved = (domain or "").strip().lower() or None

    if resolved == "irrigation":
        from examples.irrigation_abm.validators.irrigation_validators import (
            IRRIGATION_PHYSICAL_CHECKS,
            IRRIGATION_SOCIAL_CHECKS,
        )

        return [
            PersonalValidator(builtin_checks=[]),
            PhysicalValidator(builtin_checks=list(IRRIGATION_PHYSICAL_CHECKS)),
            ThinkingValidator(builtin_checks=[]),
            SocialValidator(builtin_checks=list(IRRIGATION_SOCIAL_CHECKS)),
            SemanticGroundingValidator(builtin_checks=[]),
        ]

    if resolved == "flood":
        from examples.governed_flood.validators.flood_validators import (
            FLOOD_PHYSICAL_CHECKS,
            FLOOD_PERSONAL_CHECKS,
            FLOOD_SOCIAL_CHECKS,
            FLOOD_SEMANTIC_CHECKS,
        )

        return [
            PersonalValidator(builtin_checks=list(FLOOD_PERSONAL_CHECKS)),
            PhysicalValidator(builtin_checks=list(FLOOD_PHYSICAL_CHECKS)),
            ThinkingValidator(extreme_actions={"relocate", "elevate_house"}),
            SocialValidator(builtin_checks=list(FLOOD_SOCIAL_CHECKS)),
            SemanticGroundingValidator(builtin_checks=list(FLOOD_SEMANTIC_CHECKS)),
        ]

    return _empty_validators()
