"""Irrigation ABM — Hung & Yang (2021) water demand adaptation experiment.

Phase 6C-v2 (2026-05-10): registers IrrigationDomainPack at import time
so broker pipeline code can query irrigation behaviour via
``DomainPackRegistry.get_or_default("irrigation")`` without hardcoded
``if domain == "irrigation":`` branches.
"""
from broker.domains.registry import DomainPackRegistry
from examples.irrigation_abm.adapters.irrigation_pack import IrrigationDomainPack

DomainPackRegistry.register("irrigation", IrrigationDomainPack())
