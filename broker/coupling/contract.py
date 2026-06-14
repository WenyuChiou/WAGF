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
from typing import Dict, List, Optional, Sequence, Tuple

# Allowed enum-like string values (kept as strings, not Enums, so a YAML/JSON
# contract can be authored without importing this module).
_CADENCES = ("per_decision", "per_event", "per_solver_step")
_DIRECTIONS = ("world_to_agent", "agent_to_world")
_ON_MISSING = ("fail_loud", "last_good", "quarantine")
_REDUCE = ("mean", "max", "min", "sum", "last")
_DECISION_CADENCES = ("annual", "step")
_SOLVER_CADENCES = ("annual", "event_set", "sub_step")
_HOLD_POLICIES = ("constant", "ramp", "rate")
_VALUE_SOURCES = ("world_deterministic", "proposal")


def reduce_series(values: Sequence[float], how: str) -> float:
    """Apply a declared ``observation_reduce`` to a sub-step series.

    The executor for numerical-correctness check #2's declarations (inc 3,
    2026-06-10): mean storage vs min head vs total spill reduce differently,
    and the roll-up must be the DECLARED one, never an implicit default.
    Empty series fails loud — a coupled variable that produced no sub-step
    values is a wiring bug, not a zero.
    """
    if how not in _REDUCE:
        raise ValueError(f"unknown observation_reduce {how!r}, expected one of {_REDUCE}")
    seq = [float(v) for v in values]
    if not seq:
        raise ValueError("reduce_series: empty sub-step series (no solver values collected)")
    if how == "mean":
        return sum(seq) / len(seq)
    if how == "max":
        return max(seq)
    if how == "min":
        return min(seq)
    if how == "sum":
        return sum(seq)
    return seq[-1]  # "last"


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
    # Execution-sampling guard (inc 3): who AUTHORS this quantity's committed
    # value. "proposal" = the value must come from the approved skill's
    # parameters (an agent-authored setpoint); the adapter raises if the
    # world-side commit diverges from the proposal (a world-side re-sample of
    # an agent-owned value is the execution-sampling bug class).
    # "world_deterministic" (default) = world-side computed, no guard.
    value_source: str = "world_deterministic"
    # B6 R1-fix-2 (build-time guard): mark an input whose committed value is
    # DERIVED world-side (e.g. the bundle computes it in commit_world_delta from
    # another proposal field, like the reservoir deriving release_target from
    # magnitude_pct) rather than authored verbatim by the agent. A derived input
    # is incompatible with value_source="proposal" — __post_init__ rejects that
    # combination at CONSTRUCTION, so the wiring error fails loud at build time
    # instead of as a runtime CouplingViolation in the adapter POST guard.
    # Meaningful only for direction="agent_to_world" inputs. repr=False +
    # compare=False keep it a pure build-time annotation: excluded from the
    # contract provenance sha (repr-based, see adapter.get_provenance) AND from
    # VarSpec __eq__/__hash__, so an existing contract that never sets is_derived
    # hashes and compares exactly as before, and even MARKING an input derived
    # leaves the provenance sha untouched.
    is_derived: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.cadence not in _CADENCES:
            raise ValueError(f"VarSpec[{self.name}]: cadence {self.cadence!r} not in {_CADENCES}")
        if self.direction not in _DIRECTIONS:
            raise ValueError(f"VarSpec[{self.name}]: direction {self.direction!r} not in {_DIRECTIONS}")
        if self.on_missing not in _ON_MISSING:
            raise ValueError(f"VarSpec[{self.name}]: on_missing {self.on_missing!r} not in {_ON_MISSING}")
        if self.on_missing != "fail_loud":
            # Env-layer honesty (2026-06-10 review, archetype-C trap): only
            # fail_loud HAS an executor — adapter._validate_observations punts
            # last_good/quarantine to "the domain pipeline", which nothing
            # implements. A flaky-endpoint author writing last_good would
            # BELIEVE it and still die mid-batch on a timeout. Declared-but-
            # unexecutable vocabulary gets rejected (the Wave-4 slot-honesty
            # rule), not silently accepted. Implement the executor before
            # re-admitting the value.
            raise ValueError(
                f"VarSpec[{self.name}]: on_missing={self.on_missing!r} has NO "
                f"runtime executor yet (only 'fail_loud' is implemented). "
                f"Refusing a policy that would be silently ignored."
            )
        if self.observation_reduce not in _REDUCE:
            raise ValueError(f"VarSpec[{self.name}]: observation_reduce {self.observation_reduce!r} not in {_REDUCE}")
        if self.value_source not in _VALUE_SOURCES:
            raise ValueError(f"VarSpec[{self.name}]: value_source {self.value_source!r} not in {_VALUE_SOURCES}")
        if self.is_derived and self.value_source == "proposal":
            raise ValueError(
                f"VarSpec[{self.name}]: is_derived=True is incompatible with "
                "value_source='proposal'. A derived input is computed world-side "
                "(the bundle derives it in commit_world_delta), so it cannot also "
                "be an agent-authored setpoint -- the adapter POST guard "
                "(execution-sampling) would reject it mid-run. Use "
                "value_source='world_deterministic' for the derive pattern, or "
                "is_derived=False if the proposal authors this key verbatim."
            )
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
    # K solver sub-steps per decision period (inc 3). None = event/annual
    # coupling (one advance per period). ContinuousBundle requires it.
    substeps_per_decision: Optional[int] = None

    def __post_init__(self) -> None:
        if self.decision_cadence not in _DECISION_CADENCES:
            raise ValueError(f"decision_cadence {self.decision_cadence!r} not in {_DECISION_CADENCES}")
        if self.solver_cadence not in _SOLVER_CADENCES:
            raise ValueError(f"solver_cadence {self.solver_cadence!r} not in {_SOLVER_CADENCES}")
        if self.control_hold_policy not in _HOLD_POLICIES:
            raise ValueError(f"control_hold_policy {self.control_hold_policy!r} not in {_HOLD_POLICIES}")
        if self.substeps_per_decision is not None:
            # Coerce to int AT CONSTRUCTION (frozen dataclass -> object.__setattr__):
            # a float K (e.g. 4.7) stored raw would put "4.7" into the provenance
            # sha while ContinuousBundle truncates to 4 — same effective contract,
            # different identity hash (review W1).
            object.__setattr__(self, "substeps_per_decision", int(self.substeps_per_decision))
            if self.substeps_per_decision < 1:
                raise ValueError(f"substeps_per_decision must be >= 1, got {self.substeps_per_decision}")
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


__all__ = ["VarSpec", "CouplingContract", "reduce_series"]
