"""Reservoir continuous-control worked example.

Importing this package registers the reservoir_control physical validators and
DomainPack. Registration is intentionally centralized here, mirroring
examples.cat_model.
"""
from __future__ import annotations

from broker.components.governance.validator_registry import ValidatorRegistry
from broker.domains.registry import DomainPackRegistry

from examples.reservoir_control.ops_validators import RESERVOIR_CONTROL_PHYSICAL_CHECKS
from examples.reservoir_control.reservoir_pack import ReservoirControlDomainPack

ValidatorRegistry.register(
    "reservoir_control",
    "physical",
    list(RESERVOIR_CONTROL_PHYSICAL_CHECKS),
)
DomainPackRegistry.register("reservoir_control", ReservoirControlDomainPack())

__all__ = ["ReservoirControlDomainPack"]
