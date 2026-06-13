"""Reservoir multi-dimensional control worked example (Phase 6W-B7).

Importing this package registers the multi-dim DomainPack AND the generic
ParameterBoundsValidator (built from the pack's per-skill VarSpec param_specs) in the
physical validator slot — the same ValidatorRegistry channel dead_pool_violation uses.

This is the FIRST real call-site of DomainPack.param_specs(): its dormancy ends here
(the DORMANT_HOOKS entry for param_specs is removed in this commit). Demonstrates the
B1-B6 multi-dimensional-action chain end-to-end: a domain declares 3 bounded numeric
setpoints, the LLM proposes them, ParameterBoundsValidator bounds-checks each with
reject-and-retry, and the approved setpoints commit to the hosted solver.
"""
from __future__ import annotations

from broker.components.governance.validator_registry import ValidatorRegistry
from broker.coupling.param_validator import make_parameter_bounds_validator
from broker.domains.registry import DomainPackRegistry

from examples.reservoir_control_multidim.reservoir_multidim_pack import (
    ReservoirMultidimDomainPack,
)

_PACK = ReservoirMultidimDomainPack()
DomainPackRegistry.register("reservoir_control_multidim", _PACK)
ValidatorRegistry.register(
    "reservoir_control_multidim",
    "physical",
    [make_parameter_bounds_validator(_PACK.param_specs())],
)

__all__ = ["ReservoirMultidimDomainPack"]
