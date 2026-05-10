"""
Vaccination decision-making ABM — WAGF non-water reference example.

Import order matters here:
  1. ``cognition``: registers HBM framework metadata so
     ``ThinkingValidator(framework="hbm")`` won't raise (Phase 6C-v3 Group H).
  2. ``validators``: registers vaccination check functions with
     ``ValidatorRegistry``.
  3. ``DomainPackRegistry.register("vaccination", VaccinationDomainPack())``:
     wires the broker's pluggable behaviours (reflection, emotion, events,
     mg_barrier) to this domain.
"""
# 1. Register HBM framework metadata (must happen before any
#    ThinkingValidator is constructed for "vaccination").
from examples.vaccination_demo import cognition  # noqa: F401 -- side-effect

# 2. Register validator checks (so ValidatorRegistry has the entries
#    by the time broker.validators.governance.validate_all is called).
from examples.vaccination_demo import validators  # noqa: F401 -- side-effect

# 3. Register the DomainPack.
try:
    from broker.domains.registry import DomainPackRegistry
    from examples.vaccination_demo.adapters.vaccination_pack import (
        VaccinationDomainPack,
    )
    DomainPackRegistry.register("vaccination", VaccinationDomainPack())
except ImportError:
    # Allow partial bring-up (e.g., docs-only environments) without
    # broker.domains available.
    pass
