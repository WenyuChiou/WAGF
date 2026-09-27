"""Irrigation env <-> agent physical-state guard (PR-9 coupling-retrofit, F1).

Audit finding F1: ``IrrigationEnvironment.get_agent_context()`` (the ONLY
place per-agent physical state crosses into the LLM prompt) reads every
field with a silent default —
``basin.get("precipitation", 0)``, ``basin.get("lake_mead_level", 0)``,
``agent.get("water_right", 0)``, and twelve more (fifteen in all; the full
list is ``IRRIGATION_CONTEXT_FIELD_SOURCES`` below) — bypassing the coupling
layer's ``VarSpec(on_missing="fail_loud")`` discipline entirely. A missing
field does not raise; it becomes a plausible-looking zero, and nothing
downstream can tell the difference between "the reservoir really is at
0 ft" and "the reservoir's state was never set."

This module declares a ``CouplingContract`` naming every field
``get_agent_context()`` reads with a default, and a guard function that
checks PRESENCE in the underlying source dicts (not the defaulted output)
before any default is applied — raising ``CouplingViolation`` (naming the
field) when a value is genuinely absent, exactly what
``VarSpec(on_missing="fail_loud")`` exists to do.

WHAT IS AND IS NOT ENFORCED HERE (review W3 — stated precisely because the
coupling layer advertises FOUR numerical-correctness checks and this path
runs two of them; a paper must not attribute all four to irrigation):

* At CONSTRUCTION, when ``build_irrigation_agent_context_contract()`` runs:
  ``CouplingContract.__post_init__`` enforces check #3 (direction — every
  observation must be ``world_to_agent``) and check #4 (double-count — at
  most one ``consumer_of_record`` per quantity), and ``VarSpec.__post_init__``
  enforces that a numeric variable declares a non-empty unit and that
  ``lo <= hi``.
* At RUNTIME under the flag, per ``get_agent_context()`` call:
  PRESENCE (``on_missing="fail_loud"``), then, for a present value,
  ``VarSpec.range_violation`` — finite (no NaN/±inf), inside ``[lo, hi]``,
  and of the declared dtype. That is ALL.
* NOT called on this path at any time: ``CouplingContract.check_units()``
  and ``check_cadence()``. Nothing here verifies a UNIT CONVERSION — the
  contract records that ``precipitation`` is mm and ``lake_mead_level`` is
  ft, and a wrong-unit value inside the declared range passes silently.
  Cadence is likewise declared (``annual``/``annual``) and never re-checked
  at runtime.

Why this is NOT a plain ``EnvironmentCouplingAdapter`` wrap: the adapter's
``_validate_observations`` checks ONE flat env dict produced by
``advance_step()``. ``get_agent_context(agent_id)`` is a SEPARATE, per-agent
accessor that reads from three different dicts (``self._agents[agent_id]``,
``self._basins[basin_key]``, ``self._global``) lazily, per call — a shape
the adapter's single-dict model does not fit. This module reuses the exact
same primitives the adapter is built from (``VarSpec.range_violation``,
``VarSpec.on_missing``, ``CouplingViolation``) at the ACTUAL handoff point,
rather than forcing a mismatched wrap.

Gated by ``global_config.coupling.context_contract`` (default OFF, see
``AgentTypeConfig.get_coupling_context_contract``). With the flag OFF,
``IrrigationEnvironment`` is byte-identical to pre-PR-9 behaviour: this
module is imported (no import-time side effect) but the guard is never
called.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from broker.coupling.adapter import CouplingViolation
from broker.coupling.contract import CouplingContract, VarSpec

# varspec name -> (source dict, raw key read from that dict). "source" is
# one of "agent" / "basin" / "global", matching the three dicts
# get_agent_context() reads from. Kept as an explicit table (not inferred
# from the VarSpec name) so a future rename on either side fails a test
# instead of silently mismatching.
IRRIGATION_CONTEXT_FIELD_SOURCES: Dict[str, Tuple[str, str]] = {
    "current_diversion": ("agent", "diversion"),
    "current_request": ("agent", "request"),
    "water_right": ("agent", "water_right"),
    "curtailment_ratio": ("agent", "curtailment_ratio"),
    "at_allocation_cap": ("agent", "at_allocation_cap"),
    "has_efficient_system": ("agent", "has_efficient_system"),
    "below_minimum_utilisation": ("agent", "below_minimum_utilisation"),
    "cluster": ("agent", "cluster"),
    "basin": ("agent", "basin"),
    "precipitation": ("basin", "precipitation"),
    "lake_mead_level": ("basin", "lake_mead_level"),
    "preceding_factor": ("basin", "preceding_factor"),
    "drought_index": ("global", "drought_index"),
    "total_available_water": ("global", "total_available_water"),
    "total_basin_demand": ("global", "total_basin_demand"),
    # Supply-side redesign (2026-09-25): settlement outputs and the two
    # reservoir signals the prompt now reads.
    "delivery_ratio": ("agent", "delivery_ratio"),
    "gap_reason": ("agent", "gap_reason"),
    "basin_request_over_target": ("global", "basin_request_over_target"),
    "natural_flow_maf": ("global", "natural_flow_maf"),
    "powell_storage_maf": ("global", "powell_storage_maf"),
}


def build_irrigation_agent_context_contract() -> CouplingContract:
    """The full contract for ``get_agent_context()``'s physical-state
    handoff: every field the method currently defaults to 0/False/"unknown"
    on a silent miss, declared ``world_to_agent`` with
    ``on_missing="fail_loud"`` (the ``VarSpec`` default — no other policy
    has a runtime executor, see ``broker/coupling/contract.py``)."""
    return CouplingContract(
        observations=(
            VarSpec("current_diversion", float, "acre_ft", lo=0.0, cadence="per_decision"),
            VarSpec("current_request", float, "acre_ft", lo=0.0, cadence="per_decision"),
            VarSpec("water_right", float, "acre_ft", lo=0.0, cadence="per_decision"),
            VarSpec("curtailment_ratio", float, "ratio_decimal", lo=0.0, hi=1.0, cadence="per_decision"),
            VarSpec("at_allocation_cap", bool, "", cadence="per_decision"),
            VarSpec("has_efficient_system", bool, "", cadence="per_decision"),
            VarSpec("below_minimum_utilisation", bool, "", cadence="per_decision"),
            VarSpec("cluster", str, "", cadence="per_decision"),
            VarSpec("basin", str, "", cadence="per_decision"),
            VarSpec("precipitation", float, "mm", lo=0.0, cadence="per_decision"),
            VarSpec("lake_mead_level", float, "ft", lo=800.0, hi=1300.0, cadence="per_decision"),
            VarSpec("preceding_factor", int, "flag", lo=0, hi=1, cadence="per_decision"),
            VarSpec("drought_index", float, "ratio_decimal", lo=0.0, hi=1.0, cadence="per_decision"),
            VarSpec("total_available_water", float, "acre_ft", lo=0.0, cadence="per_decision"),
            VarSpec("total_basin_demand", float, "acre_ft", lo=0.0, cadence="per_decision"),
            VarSpec("delivery_ratio", float, "ratio_decimal", lo=0.0, hi=1.0, cadence="per_decision"),
            VarSpec("gap_reason", str, "", cadence="per_decision"),
            VarSpec("basin_request_over_target", float, "ratio_decimal", lo=0.0, cadence="per_decision"),
            VarSpec("natural_flow_maf", float, "maf", lo=0.0, cadence="per_decision"),
            VarSpec("powell_storage_maf", float, "maf", lo=0.0, cadence="per_decision"),
        ),
        decision_cadence="annual",
        solver_cadence="annual",
    )


# Keys ``get_agent_context()`` returns that the contract deliberately does
# NOT cover, and why (review P2: "the contract covers 20 of 24 context keys"
# is only checkable if the other 4 are written down somewhere the manifest
# can quote). None of them is read from a source dict with a silent default,
# which is what this contract guards:
#   agent_id             -- the caller's own argument, echoed back; never
#                          looked up.
#   year                 -- ``self._current_year``, a plain attribute set in
#                          __init__ and incremented by advance_year; cannot
#                          be "missing".
#   shortage_tier        -- computed by ``_compute_shortage_tier()`` from
#                          lake_mead_level, which IS covered; guarding the
#                          derived value as well would double-report one
#                          underlying fact.
#   powell_dead_pool_maf -- ``self.config.powell_dead_pool_maf``, a
#                          ``WaterSystemConfig`` field validated at
#                          construction (``__post_init__``); never read from
#                          ``self._agents`` / ``self._basins`` / ``self._global``
#                          with a silent default, so it carries none of the F1
#                          risk this contract exists to guard.
IRRIGATION_CONTEXT_UNCOVERED_KEYS: Tuple[str, ...] = (
    "agent_id", "shortage_tier", "year", "powell_dead_pool_maf",
)


def irrigation_contract_field_names() -> List[str]:
    """Sorted field list for provenance reporting (run_integrity.json)."""
    return sorted(IRRIGATION_CONTEXT_FIELD_SOURCES.keys())


def irrigation_contract_field_checks() -> Dict[str, str]:
    """Per-field statement of WHICH check the guard actually applies
    (review P1-c), for ``run_integrity.json``.

    Five of the fifteen fields are declared ``bool`` or ``str``. Before the
    PR-9 review, ``VarSpec.range_violation`` returned ``None`` immediately for
    any non-numeric dtype, so those five got PRESENCE checking and nothing
    else while the manifest listed them beside the numeric ones as though all
    fifteen were equally guarded. The dtype checks in ``range_violation`` now
    give them a real check — but a different one — and the manifest says which
    each field got rather than leaving a reader to infer it:

    * ``presence+range`` — numeric (``int``/``float``): present, finite,
      inside the declared ``[lo, hi]``, and of numeric type.
    * ``presence+type``  — ``bool``/``str``: present, and of the declared
      type (a ``str`` field must additionally be non-empty). There is no
      range to check.

    Neither label implies any unit conversion was verified; nothing on this
    path checks units (see this module's docstring).
    """
    contract = build_irrigation_agent_context_contract()
    checks: Dict[str, str] = {}
    for vs in contract.observations:
        checks[vs.name] = "presence+range" if vs.dtype in (int, float) else "presence+type"
    return dict(sorted(checks.items()))


# Basin-scoped fields — a REAL finding surfaced by building this guard
# (PR-9 verification run, not a hypothetical): ``precipitation`` is written
# ONLY onto ``self._basins["upper_basin"]`` and ``lake_mead_level`` ONLY
# onto ``self._basins["lower_basin"]`` (irrigation_env.py's
# ``advance_year`` / ``__init__``) — a deliberate per-basin telemetry
# split matching the domain (Powell inflow tracks Upper Basin winter
# precipitation; Lower Basin curtailment risk tracks Mead elevation), NOT
# a bug. A naive "every observation required for every agent" contract
# raised ``CouplingViolation: lake_mead_level missing`` for EVERY
# upper-basin agent on the very first --model mock smoke run — a false
# alarm on a legitimate design choice, not a real gap. This table encodes
# that scoping so the guard matches the field to the basin it actually
# applies to, the same gate ``irrigation_personas.build_water_situation_text``
# already uses (``if basin == "upper_basin": use precip else: use mead``).
#
# The residual risk this does NOT close: for an upper-basin agent,
# ``get_agent_context()`` still returns ``lake_mead_level=0`` (silently —
# the field is simply not applicable, and the guard now skips it rather
# than validating it). That is fine for the one consumer that exists today
# (it never reads the inapplicable field), but a FUTURE consumer that reads
# ``ctx["lake_mead_level"]`` without the same basin gate would silently see
# a plausible-looking 0 instead of "not applicable" — this table is the
# one place that fact is now written down; a validator/prompt author
# should grep it before trusting either field.
_BASIN_SCOPED_FIELDS: Dict[str, str] = {
    "precipitation": "upper_basin",
    "lake_mead_level": "lower_basin",
}

# Every basin name the table above knows how to scope. Review P1-d: the
# scoping rule "skip this field unless the agent is in ITS basin" silently
# skips BOTH scoped fields for any basin name that is in neither branch —
# so an agent whose ``basin`` is a typo, or a basin a future config adds,
# quietly loses the only two environment signals the guard was built to
# protect, and the run reports a clean guard. An unrecognised basin is
# therefore a violation in its own right, naming the basin.
_SCOPED_BASINS = frozenset(_BASIN_SCOPED_FIELDS.values())


def guard_agent_context_sources(
    contract: CouplingContract,
    *,
    agent: Dict[str, Any],
    basin_key: str,
    basin: Dict[str, Any],
    global_state: Dict[str, Any],
) -> None:
    """Raise ``CouplingViolation`` naming every declared observation whose
    backing key is ACTUALLY ABSENT (or ``None``) in its source dict, or
    whose present value violates the VarSpec's declared range or dtype —
    checked BEFORE ``get_agent_context()`` applies any ``.get(key, default)``
    fallback. A field listed in ``_BASIN_SCOPED_FIELDS`` is only checked
    for the basin it applies to (see that table's docstring for why this
    is a real design property, not a loophole); a ``basin_key`` that is in
    NEITHER branch of that table is itself reported as a violation naming
    the basin, so the scoping rule can never quietly turn into a blanket
    exemption. No-op (returns normally)
    when every applicable field is present and in-range, so a
    fully-populated agent/basin/global state produces IDENTICAL output
    whether this guard ran or not (F1 remediation: the guard adds a
    fail-loud floor, it does not change a single value on the happy path).
    """
    sources = {"agent": agent, "basin": basin, "global": global_state}
    problems: List[str] = []
    if basin_key not in _SCOPED_BASINS:
        # P1-d: not "skip both scoped fields and report clean" — say so.
        problems.append(
            f"basin={basin_key!r} not in the basin-scoping table "
            f"(known: {sorted(_SCOPED_BASINS)}); the basin-scoped field(s) "
            f"{sorted(_BASIN_SCOPED_FIELDS)} cannot be checked for it"
        )
    for vs in contract.observations:
        required_basin = _BASIN_SCOPED_FIELDS.get(vs.name)
        if required_basin is not None and basin_key != required_basin:
            continue  # not applicable to this agent's basin (see table docstring)
        source_name, raw_key = IRRIGATION_CONTEXT_FIELD_SOURCES[vs.name]
        src = sources[source_name]
        if raw_key not in src or src[raw_key] is None:
            if vs.on_missing == "fail_loud":
                problems.append(f"{vs.name}: missing (on_missing=fail_loud)")
            continue
        rv = vs.range_violation(src[raw_key])
        if rv:
            problems.append(rv)
    if problems:
        raise CouplingViolation(f"observation contract violations: {problems}")


__all__ = [
    "IRRIGATION_CONTEXT_FIELD_SOURCES",
    "IRRIGATION_CONTEXT_UNCOVERED_KEYS",
    "build_irrigation_agent_context_contract",
    "irrigation_contract_field_names",
    "irrigation_contract_field_checks",
    "guard_agent_context_sources",
    "CouplingViolation",
]
