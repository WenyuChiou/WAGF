"""Continuous quantitative-control coupling (Phase 6V increment 3, 2026-06-10).

The execution path for what the contract could previously only DECLARE
(2026-06-09 architecture review P0-1/P0-2): a hosted solver advanced K
sub-steps per decision period, per-variable sub-step series rolled up by each
VarSpec's declared ``observation_reduce``, and an agent->world write channel
(``ControlSink``) that applies an approved skill's setpoint parameters into
the hosted model.

Division of labour (mirrors the event path):
  * ``run_pipeline``      world->agent: K x solver.update(), collect each
                          observation's series, reduce per declaration.
  * ``commit_world_delta``  agent->world PURE COMMITTER: governance already
                          ran in the retry loop; here the approved setpoints
                          are written into the solver via the sink, once.
  * ``control_hold_policy``  only "constant" is implemented: a committed
                          control persists inside the solver across sub-steps
                          (BMI set_value semantics), so holding constant is
                          the solver's natural behavior. "ramp"/"rate" raise
                          until a real domain needs them — no speculative
                          interpolation engine.

Generic + domain-vocab-free; the solver and variable names are supplied by
the caller under ``examples/<domain>/``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .bmi_source import BmiComponent, _scalar
from .contract import CouplingContract, reduce_series
from .interfaces import ControlSink, Event, InterfaceBundle, WorldDelta


class BmiControlSink:
    """Adapt a BMI component's ``set_value`` verb to the ControlSink Protocol.

    Requires the component to actually expose ``set_value`` (the read-only
    ``BmiComponent`` Protocol deliberately omits it — sources never write)."""

    def __init__(self, bmi: Any):
        if not callable(getattr(bmi, "set_value", None)):
            raise TypeError(
                "BmiControlSink requires a component with a callable set_value "
                "(the BMI write verb); got "
                f"{type(bmi).__name__} without one."
            )
        self._bmi = bmi

    def apply_control(self, name: str, value: float) -> None:
        # BMI set_value takes array-like; single-cell control by convention.
        self._bmi.set_value(name, [float(value)])


@dataclass
class ContinuousBundle(InterfaceBundle):
    """Drive a BMI-conformant solver K sub-steps per decision period.

    ``contract`` supplies the observation VarSpecs (names read directly as
    solver output variables — a domain needing renaming subclasses
    ``run_pipeline``), ``substeps_per_decision`` (K), and the input VarSpecs
    whose names are recognized as committable setpoints.
    ``sink`` defaults to ``BmiControlSink(solver)`` when the solver exposes
    ``set_value``; a domain may inject any ControlSink.
    """

    contract: Optional[CouplingContract] = None
    solver: Optional[BmiComponent] = None
    sink: Optional[ControlSink] = None

    def __post_init__(self) -> None:
        if self.contract is None or self.solver is None:
            raise ValueError("ContinuousBundle requires both contract= and solver=")
        if not isinstance(self.solver, BmiComponent):
            raise TypeError(
                "ContinuousBundle.solver must be BMI-conformant "
                "(update/get_value/get_var_units/get_current_time)"
            )
        k = self.contract.substeps_per_decision
        if k is None:
            raise ValueError(
                "ContinuousBundle requires contract.substeps_per_decision "
                "(K >= 1); declare it instead of relying on an implicit 1 so "
                "the cadence alignment is explicit in the contract."
            )
        self._substeps = int(k)
        if self.sink is None and callable(getattr(self.solver, "set_value", None)):
            self.sink = BmiControlSink(self.solver)

    # ------------------------------------------------------------------
    # world -> agent
    # ------------------------------------------------------------------
    def run_pipeline(
        self,
        base_env: Dict[str, Any],
        events: List[Event],
        operation_order,
        control_hold_policy: str = "constant",
    ) -> Dict[str, Any]:
        if control_hold_policy != "constant":
            raise NotImplementedError(
                f"control_hold_policy={control_hold_policy!r} has no executor yet; "
                "only 'constant' is implemented (committed controls persist in "
                "the solver across sub-steps). Build ramp/rate when a real "
                "domain needs them."
            )
        env: Dict[str, Any] = dict(base_env)
        names = [vs.name for vs in self.contract.observations]
        series: Dict[str, List[float]] = {n: [] for n in names}
        for _ in range(self._substeps):
            self.solver.update()
            for n in names:
                series[n].append(_scalar(self.solver.get_value(n)))
        for vs in self.contract.observations:
            env[vs.name] = reduce_series(series[vs.name], vs.observation_reduce)
        env["_substeps_run"] = self._substeps
        return env

    # ------------------------------------------------------------------
    # agent -> world (PURE COMMITTER — governance ran in the retry loop)
    # ------------------------------------------------------------------
    def commit_world_delta(self, approved_skill: Any) -> WorldDelta:
        params = getattr(approved_skill, "parameters", None) or {}
        declared = {vs.name for vs in self.contract.inputs}
        to_apply = {k: float(v) for k, v in params.items() if k in declared}
        if to_apply and self.sink is None:
            raise ValueError(
                "ContinuousBundle has no ControlSink (solver lacks set_value?) "
                f"but the approved skill carries setpoint(s) {sorted(to_apply)} — "
                "refusing to silently drop an agent-authored control."
            )
        for name, value in to_apply.items():
            self.sink.apply_control(name, value)
        return WorldDelta(
            agent_state_changes={},
            world_changes=dict(to_apply),
            contention_rule="none",
        )

    # ------------------------------------------------------------------
    # provenance (consumed by EnvironmentCouplingAdapter.get_provenance)
    # ------------------------------------------------------------------
    def get_provenance(self) -> Dict[str, Any]:
        name_fn = getattr(self.solver, "get_component_name", None)
        return {
            "bundle_class": type(self).__name__,
            "solver_class": type(self.solver).__name__,
            "solver_component_name": name_fn() if callable(name_fn) else None,
            "substeps_per_decision": self._substeps,
        }


__all__ = ["BmiControlSink", "ContinuousBundle"]
