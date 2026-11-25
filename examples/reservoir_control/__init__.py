"""Reservoir continuous-control worked example.

Importing this package registers the reservoir_control physical validators and
DomainPack. Registration is intentionally centralized here, mirroring
examples.cat_model.
"""
from __future__ import annotations

from broker.components.governance.validator_registry import ValidatorRegistry
from broker.domains.registry import DomainPackRegistry

from examples.reservoir_control.reservoir_pack import ReservoirControlDomainPack

# Dead-pool and overflow limits are declared on the coupling contract and in
# YAML expression rules, so no Python physical check is registered here.
ValidatorRegistry.register("reservoir_control", "physical", [])
DomainPackRegistry.register("reservoir_control", ReservoirControlDomainPack())

__all__ = ["ReservoirControlDomainPack"]
