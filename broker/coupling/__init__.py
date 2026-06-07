"""Generic environment-coupling layer (Phase 6V, 2026-06-06).

A domain-agnostic interface for coupling WAGF's governed LLM-agent decision
layer to heterogeneous external simulators through a *verified* contract —
units, decision-cadence vs solver-cadence alignment, state-mutation direction,
and feedback-loop double-counting safety.

This subtree carries ZERO domain vocabulary so the framework genericity
invariant (``broker/tests/test_framework_invariants.py::TestDomainGenericity``)
stays green. All domain-specific couplings (e.g. an external-simulator adapter)
live under ``examples/<domain>/`` and compose these generic pieces.

Import-inert: nothing here registers a side effect at import time, and a domain
imports it only inside its coupling-enabled code path, so a flag-OFF run never
loads this module (preserving paper-3 byte-identity).

Public API:
    VarSpec, CouplingContract        -- the typed, unit-bearing contract
    EventSource, ExposureUpdater,    -- the composable simulator interfaces
        VulnerabilityModel, FinancialLedger, InterfaceBundle
    Event, MdrDraw, Settlement, WorldDelta  -- interface value types
    EnvironmentCouplingAdapter       -- wraps a sim engine behind the contract
    resolve_coupling_enabled         -- two-layer feature-flag resolver
"""
from __future__ import annotations

from .contract import CouplingContract, VarSpec
from .flag import resolve_coupling_enabled
from .interfaces import (
    Event,
    EventSource,
    ExposureUpdater,
    FinancialLedger,
    InterfaceBundle,
    MdrDraw,
    Settlement,
    VulnerabilityModel,
    WorldDelta,
)
from .adapter import CouplingViolation, EnvironmentCouplingAdapter

__all__ = [
    "CouplingViolation",
    "VarSpec",
    "CouplingContract",
    "Event",
    "MdrDraw",
    "Settlement",
    "WorldDelta",
    "EventSource",
    "ExposureUpdater",
    "VulnerabilityModel",
    "FinancialLedger",
    "InterfaceBundle",
    "EnvironmentCouplingAdapter",
    "resolve_coupling_enabled",
]
