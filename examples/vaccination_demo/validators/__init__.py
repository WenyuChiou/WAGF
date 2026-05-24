"""Vaccination validators — registers checks with ValidatorRegistry at import.

NOTE on slot policy (Phase 6C-v3 discovery):
``ValidatorRegistry`` validates that ``slot`` is one of
``{physical, personal, social, semantic, temporal, behavioural}``.
``thinking`` is NOT a registered slot — thinking-validator checks come
from YAML rules in ``agent_types.yaml`` under the ``thinking_rules:``
key (NOT ``rules:`` — the loader at
``broker/utils/agent_config.py:859`` only recognises
``thinking_rules`` or ``coherence_rules``). Consumed by
``ThinkingValidator._validate_yaml_rules`` rather than by
``ValidatorRegistry``.  This module therefore only registers physical
checks; HBM coherence rules live in ``config/agent_types.yaml``.
"""
from examples.vaccination_demo.validators.vaccination_validators import (
    VACCINATION_PHYSICAL_CHECKS,
)

try:
    from broker.components.governance.validator_registry import ValidatorRegistry

    ValidatorRegistry.register("vaccination", "physical", list(VACCINATION_PHYSICAL_CHECKS))
except ImportError:
    pass
