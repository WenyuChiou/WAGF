"""The coupling contract — typed, unit-bearing specification of the
agent <-> external-simulator interface, with four numerical-correctness checks.

Generic + domain-vocab-free. The four checks operationalise the coupling
discipline that adopted standards (BMI 2.0 / OpenMI 2.0 / FMI) provide for
pure numerical models, but here carried across the LLM <-> simulator boundary:

  #1 units      -- each exchanged variable declares a unit + dtype + range;
                   structurally validated (range coherence, unit present).
  #2 cadence    -- the solver cadence must align with the decision cadence;
                   when they differ, a per-variable reduction must be declared.
  #3 direction  -- each variable is either world_to_agent (observation) or
                   agent_to_world (input); the contract says which side may write.
  #4 double-count -- exactly one ``consumer_of_record`` per ledger quantity;
                   declaring a quantity with >1 consumer is the classic
                   mass-balance double-count bug and is rejected at construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Allowed enum-like string values (kept as strings, not Enums, so a YAML/JSON
# contract can be authored without importing this module).
_CADENCES = ("per_decision", "per_event", "per_solver_step")
_DIRECTIONS = ("world_to_agent", "agent_to_world")
_ON_MISSING = ("fail_loud", "last_good", "quarantine")
_REDUCE = ("mean", "max", "min", "sum", "last")
_DECISION_CADENCES = ("annual", "step")
_SOLVER_CADENCES = ("annual", "event_set", "sub_step")
_HOLD_POLICIES = ("constant", "ramp", "rate")


@dataclass(frozen=True)
class VarSpec:
    """One exchanged variable on the coupling boundary."""

    name: str
    dtype: type  # int | float | bool | str
    unit: str  # "m", "ft", "USD_2020", "ratio_decimal", "" for categorical/bool
    lo: Optional[float] = None  # inclusive numeric range (None = unbounded)
    hi: Optional[float] = None
    cadence: str = "per_decision"
    direction: str = "world_to_agent"
    # E2: exactly one True per ledger quantity (same ``name``); others are
    # diagnostic-only. Defaulting True means an accidental duplicate is caught.
    consumer_of_record: bool = True
    on_missing: str = "fail_loud"  # never silent-zero
    # Per-quantity sub-step -> period reduction (used when cadences differ):
    # mean storage vs min head vs total spill reduce differently.
    observation_reduce: str = "last"

    def __post_init__(self) -> None:
        if self.cadence not in _CADENCES:
            raise ValueError(f"VarSpec[{self.name}]: cadence {self.cadence!r} not in {_CADENCES}")
        if self.direction not in _DIRECTIONS:
            raise ValueError(f"VarSpec[{self.name}]: direction {self.direction!r} not in {_DIRECTIONS}")
        if self.on_missing not in _ON_MISSING:
            raise ValueError(f"VarSpec[{self.name}]: on_missing {self.on_missing!r} not in {_ON_MISSING}")
        if self.observation_reduce not in _REDUCE:
            raise ValueError(f"VarSpec[{self.name}]: observation_reduce {self.observation_reduce!r} not in {_REDUCE}")
        if self.dtype in (int, float):
            if not self.unit:
                raise ValueError(f"VarSpec[{self.name}]: numeric variable must declare a non-empty unit")
            if self.lo is not None and self.hi is not None and self.lo > self.hi:
                raise ValueError(f"VarSpec[{self.name}]: lo {self.lo} > hi {self.hi}")

    # --- numerical-correctness check #1: units / dtype / range ---
    def range_violation(self, value: object) -> Optional[str]:
        """Return a message if ``value`` violates dtype/range, else None."""
        if value is None:
            return None  # missing-handling is the adapter's on_missing job
        if self.dtype in (int, float):
            try:
                num = float(value)
            except (TypeError, ValueError):
                return f"{self.name}={value!r} not coercible to {self.dtype.__name__} ({self.unit})"
            if self.lo is not None and num < self.lo:
                return f"{self.name}={num} below lo={self.lo} ({self.unit})"
            if self.hi is not None and num > self.hi:
                return f"{self.name}={num} above hi={self.hi} ({self.unit})"
        return None


@dataclass(frozen=True)
class CouplingContract:
    """The full agent <-> simulator contract for one domain."""

    observations: Tuple[VarSpec, ...] = field(default_factory=tuple)  # world_to_agent
    inputs: Tuple[VarSpec, ...] = field(default_factory=tuple)  # agent_to_world
    decision_cadence: str = "annual"  # "annual" | "step"
    solver_cadence: str = "annual"  # "annual" | "event_set" | "sub_step"
    operation_order: Tuple[str, ...] = field(default_factory=tuple)  # E3 pinned pipeline order
    control_hold_policy: str = "constant"  # how an agent control is held across K sub-steps

    def __post_init__(self) -> None:
        if self.decision_cadence not in _DECISION_CADENCES:
            raise ValueError(f"decision_cadence {self.decision_cadence!r} not in {_DECISION_CADENCES}")
        if self.solver_cadence not in _SOLVER_CADENCES:
            raise ValueError(f"solver_cadence {self.solver_cadence!r} not in {_SOLVER_CADENCES}")
        if self.control_hold_policy not in _HOLD_POLICIES:
            raise ValueError(f"control_hold_policy {self.control_hold_policy!r} not in {_HOLD_POLICIES}")
        for vs in self.observations:
            if vs.direction != "world_to_agent":
                raise ValueError(f"observation {vs.name!r} must be world_to_agent, got {vs.direction}")
        for vs in self.inputs:
            if vs.direction != "agent_to_world":
                raise ValueError(f"input {vs.name!r} must be agent_to_world, got {vs.direction}")
        # numerical-correctness check #4 (E2): fail-fast on a double-counted ledger.
        dupes = {k: c for k, c in self.ledger_consumers().items() if c > 1}
        if dupes:
            raise ValueError(
                "CouplingContract double-count risk: quantity/ies declared with "
                f">1 consumer_of_record (mass-balance double-count bug): {dupes}. Mark all but "
                "one of each duplicate as consumer_of_record=False (diagnostic-only)."
            )

    # --- numerical-correctness check #1 ---
    def check_units(self) -> List[str]:
        """Structural unit/dtype/range coherence over all VarSpecs. Defense-in-depth
        re-check: ``VarSpec.__post_init__`` already raises on these at construction,
        so for a correctly-built contract this returns []. Kept for adapter-time
        validation of contracts assembled by other means (e.g. loaded from YAML/JSON)."""
        problems: List[str] = []
        for vs in (*self.observations, *self.inputs):
            if vs.dtype in (int, float) and not vs.unit:
                problems.append(f"{vs.name}: numeric variable missing unit")
            if vs.lo is not None and vs.hi is not None and vs.lo > vs.hi:
                problems.append(f"{vs.name}: lo {vs.lo} > hi {vs.hi}")
        return problems

    # --- numerical-correctness check #2 ---
    def check_cadence(self) -> List[str]:
        """The solver cadence must align with the decision cadence; when they
        differ, sub-period variables must declare a reduction (not the implicit
        'last') so the sub-step -> period roll-up is explicit, not accidental."""
        problems: List[str] = []
        cadences_differ = (
            (self.decision_cadence == "annual" and self.solver_cadence != "annual")
            or (self.decision_cadence == "step" and self.solver_cadence == "sub_step")
        )
        if cadences_differ:
            for vs in self.observations:
                if vs.cadence in ("per_event", "per_solver_step") and vs.observation_reduce == "last":
                    problems.append(
                        f"{vs.name}: cadence {vs.cadence} under solver={self.solver_cadence}/"
                        f"decision={self.decision_cadence} must declare an explicit "
                        f"observation_reduce (got implicit 'last')"
                    )
        return problems

    # --- numerical-correctness check #3 ---
    def check_direction(self, key: str) -> Optional[str]:
        """Which side may WRITE ``key``: 'world' (observation) or 'agent'
        (input). None if the key is not in the contract."""
        for vs in self.observations:
            if vs.name == key:
                return "world"
        for vs in self.inputs:
            if vs.name == key:
                return "agent"
        return None

    # --- numerical-correctness check #4 (helper) ---
    def ledger_consumers(self) -> Dict[str, int]:
        """Map each variable name -> count of VarSpecs claiming
        consumer_of_record. Exactly one is required per ledger quantity;
        ``__post_init__`` raises on any count > 1."""
        counts: Dict[str, int] = {}
        for vs in (*self.observations, *self.inputs):
            if vs.consumer_of_record:
                counts[vs.name] = counts.get(vs.name, 0) + 1
        return counts

    def observation_specs(self) -> Dict[str, VarSpec]:
        return {vs.name: vs for vs in self.observations}

    def input_specs(self) -> Dict[str, VarSpec]:
        return {vs.name: vs for vs in self.inputs}


__all__ = ["VarSpec", "CouplingContract"]
