"""Multi-agent vaccination demo — Phase 6E target.

Import order:
  1. cognition: triggers HBM framework metadata registration via
     vaccination_demo's existing cognition package
  2. validators: registers physical checks under domain "vaccination_ma"
  3. DomainPackRegistry.register("vaccination_ma", VaccinationMADomainPack())
"""
# 1. Register HBM framework (reused from single-agent vaccination_demo)
from examples.vaccination_ma_demo import cognition  # noqa: F401  side-effect

# 2. Register validators
from examples.vaccination_ma_demo import validators  # noqa: F401  side-effect

# 3. Register DomainPack
try:
    from broker.domains.registry import DomainPackRegistry
    from examples.vaccination_ma_demo.adapters.vaccination_ma_pack import (
        VaccinationMADomainPack,
    )
    DomainPackRegistry.register("vaccination_ma", VaccinationMADomainPack())
except ImportError:
    pass
