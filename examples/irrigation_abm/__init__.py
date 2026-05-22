"""Irrigation ABM — Hung & Yang (2021) water demand adaptation experiment.

Phase 6C-v2 (2026-05-10): registers IrrigationDomainPack at import time
so broker pipeline code can query irrigation behaviour via
``DomainPackRegistry.get_or_default("irrigation")`` without hardcoded
``if domain == "irrigation":`` branches.

Phase 6J-D (2026-05-22): also imports ``.validators`` on package
import so the irrigation builtin checks register without
``broker/domains/water/validator_bundles.py`` reverse-importing from
``examples/`` (the prior lazy ``_ensure_irrigation_registered``
fallback was removed).
"""
from broker.domains.registry import DomainPackRegistry
from examples.irrigation_abm.adapters.irrigation_pack import IrrigationDomainPack

DomainPackRegistry.register("irrigation", IrrigationDomainPack())

# Register the irrigation builtin validator checks. Guarded so a
# transient import failure cannot mask the DomainPack registration.
try:
    from examples.irrigation_abm import validators  # noqa: F401
except ImportError:
    pass
