"""vaccination_ma validator registration.

Reuses the recent-dose physical check from the single-agent vaccination_demo
for the `individual` agent type. health_authority and community_org have no
physical checks in v1 — their YAML rules block (currently empty) is the
right extension point if cross-agent coherence rules are added later.
"""
from examples.vaccination_demo.validators.vaccination_validators import (
    VACCINATION_PHYSICAL_CHECKS,
)

try:
    from broker.components.governance.validator_registry import ValidatorRegistry

    # Register under the multi-agent domain key so YAML's
    # `global_config.governance.domain: vaccination_ma` lookup resolves.
    ValidatorRegistry.register(
        "vaccination_ma", "physical", list(VACCINATION_PHYSICAL_CHECKS)
    )
except ImportError:
    pass
