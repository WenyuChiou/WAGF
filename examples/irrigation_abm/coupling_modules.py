"""Irrigation environment coupling modules (v0.6 coupling-layer wiring).

Concrete implementations of the generic ``broker.coupling`` interfaces for
the irrigation ABM's continuous water-system state (Colorado River Basin
mass balance, ``examples/irrigation_abm/irrigation_env.py``). All
irrigation vocabulary lives HERE under ``examples/`` (never in
``broker/coupling/``, per the genericity invariant,
``broker/tests/test_framework_invariants.py``).

  IrrigationBundle                    -> broker.coupling.InterfaceBundle
      wraps ``IrrigationEnvironment``'s year-advance
      (``advance_year()``) and demand commit (``execute_skill()``).
  build_irrigation_coupling_contract(env) -> broker.coupling.CouplingContract
      the boundary VarSpecs (see table below); takes the already-
      initialised environment so bounds are DERIVED from the loaded
      config/agents, not typed-in guesses.

INVARIANT (read before touching this file): with the v0.6 coupling layer
ON (``global_config.coupling.enable: true``, or the ``--coupling`` CLI
flag in ``run_experiment.py`` / ``run_ungoverned_experiment.py``),
``simulation_log.csv`` is BYTE-IDENTICAL to the contract-OFF run at the
same model/seed/years/agents, and every PRE-EXISTING governance-audit-CSV
column keeps the exact same values row-for-row (at ``workers=1``; row
ORDER at ``workers>1`` is independently non-deterministic under BOTH
coupling on and off, a pre-existing ThreadPoolExecutor-completion-order
property unrelated to coupling - see
``examples/irrigation_abm/tests/test_coupling.py::
test_coupling_off_vs_on_byte_identical_workers_4`` and the README's
"Workers and the v0.6 coupling layer" section). The audit CSV gains
EXACTLY two new columns, ``world_request`` and ``world_contention_rule``,
because ``EnvironmentCouplingAdapter.execute_skill`` (``broker/coupling/
adapter.py``) always reports a ``WorldDelta`` through
``action_context.world_delta``, and ``broker/components/analytics/
audit.py``'s KEY-GATED row builder flattens any present ``world_changes``
into ``world_<key>`` columns unconditionally for every coupled domain
(see ``broker/tests/test_audit_schema_golden.py::
test_world_delta_adds_only_key_gated_world_columns`` and
``broker/tests/test_continuous_coupling.py::
test_frozen_shaped_trace_gains_no_world_columns``: a FROZEN/uncoupled
trace gains zero columns, by design; a coupled one is EXPECTED to gain
its declared ``world_changes`` keys plus ``world_contention_rule``). This
is shared, generic ``broker.coupling`` behaviour, not something
``IrrigationBundle`` can or should suppress - verify the two CSVs with
``broker.tools.compare_audit_csv.compare(..., drop_columns=
("world_request", "world_contention_rule"))`` for the audit CSV and a
plain ``compare()`` for ``simulation_log.csv``.

FAILURE MODE (read before assuming every ``CouplingViolation`` behaves the
same way): an OBSERVATION-side violation, raised inside
``EnvironmentCouplingAdapter.advance_step()`` (a corrupted or missing
world-state reading, before any agent decides), propagates out of
``ExperimentRunner.run()``'s main loop uncaught and ABORTS THE WHOLE RUN.
A COMMIT-side violation, raised inside ``execute_skill()`` while
processing one agent's approved step, is caught by the per-agent handler
(``ExperimentRunner._run_agents_sequential`` /
``_run_agents_parallel``), recorded as one ``ABORTED`` audit row via
``_write_aborted_trace``, and the run continues with the next agent/year.

``IrrigationBundle`` holds its half of the byte-identity invariant by
being a PURE PASS-THROUGH / PURE COMMITTER wrapper - it never
re-implements or re-derives irrigation physics:

  * ``run_pipeline`` returns the wrapped environment's own
    ``advance_year()`` dict UNCHANGED (``dict(base_env)``, no key added,
    renamed, or dropped). ``EnvironmentCouplingAdapter._advance_real()``
    already called ``advance_year()`` on the real engine before handing us
    ``base_env``; returning it verbatim is what keeps the per-year env
    dict, and therefore every prompt built from
    ``context_builder.build(env_context=env)``
    (``broker/core/experiment_runner.py``), byte-identical to the
    uncoupled path.
  * ``commit_world_delta`` forwards the already-governed
    ``approved_skill`` straight to ``IrrigationEnvironment.execute_skill()``,
    the SAME method ``broker/core/skill_broker_engine.py`` calls directly
    on the uncoupled path, and reshapes its ``ExecutionResult`` into a
    ``WorldDelta`` without recomputing anything. Governance itself already
    ran in the retry loop; this is a pure committer (E2: applies the delta
    exactly once) plus a fail-loud guard against a genuinely failed commit
    (see its docstring).

WORKERS (AR-3, ``broker/INVARIANTS.md`` "Accepted risks"): the generic
builder warns that ``workers>1`` with coupling enabled is UNSUPPORTED
because "phase-internal parallel steps can interleave bundle mutations."
That risk does not materialise for THIS bundle: the commit path
(``IrrigationEnvironment.execute_skill``) writes only to a per-agent-keyed
dict entry (``self._agents[agent_id]``, never shared across agents) using
a generator derived fresh per ``(seed, year, agent, skill)`` call
(``_decision_rng``, no shared mutable RNG stream), and
``EnvironmentCouplingAdapter`` mutates its own state (``self._period``)
only inside ``advance_step()``, which the runner calls once per year on
the main thread BEFORE the parallel agent phase begins, never inside
``execute_skill()``. ``IrrigationBundle`` itself holds no mutable state of
its own. Empirically confirmed at ``workers=4`` (see the test named
above); the generic AR-3 warning is still emitted (accurate for the
general case) and is not suppressed.

SCOPE (read this before assuming the contract below covers all irrigation
physical state): this bundle enforces the boundary
``EnvironmentCouplingAdapter`` owns, ``advance_step()`` /
``execute_skill()``, which is the FLAT per-period environment dict
(``IrrigationEnvironment._global``: year, total_available_water,
drought_index, total_basin_demand) plus the committed per-agent demand
request. It is deliberately narrower than the physical state an agent's
PROMPT reads: Lake Mead elevation, curtailment ratio, water_right,
precipitation, shortage tier and the rest of the fifteen
``get_agent_context()`` fields cross a DIFFERENT boundary, a per-agent
accessor reading three separate dicts (``self._agents[id]`` /
``self._basins[basin]`` / ``self._global``) lazily per call, not the one
flat dict ``advance_step()`` produces, and are already governed by the
SEPARATE, pre-existing ``examples.irrigation_abm.irrigation_coupling``
contract + ``guard_agent_context_sources``, gated by its own flag
(``global_config.coupling.context_contract``, PR-9 coupling-retrofit,
F1). See that module's docstring for why it is not a plain
``EnvironmentCouplingAdapter`` wrap either; the same reasoning applies
here in reverse: an ``EnvironmentCouplingAdapter`` contract cannot declare
an observation absent from the ``advance_step()`` env dict without the
adapter raising ``CouplingViolation`` on every period (fail-loud has no
"not applicable here" escape hatch). The two flags compose independently;
a paper run may set one, both, or neither, and one is not a substitute for
the other's coverage. Both flags' keys DO appear together in
``run_integrity.json`` when both are on:
``EnvironmentCouplingAdapter.__getattr__`` (``broker/coupling/adapter.py``)
forwards ``get_coupling_retrofit_metadata`` to the wrapped real engine
when it defines one, so wrapping ``IrrigationEnvironment`` in this
adapter does not make its own context-contract reporting vanish.

VarSpec table (name / direction / unit / bounds / source symbol). Bounds
are COMPUTED at contract-construction time from ``env``, not typed-in
literals; the formulas (with the values they produce for a representative
run) are:

  Observations (world_to_agent, checked every ``advance_step()`` against
  the dict this bundle's ``run_pipeline`` returns):
    year                   | world_to_agent | calendar_year | [1900, 2200]                                            | IrrigationEnvironment._global["year"] (advance_year)
    total_available_water  | world_to_agent | acre_ft       | [0.7 * S, S], S = config.upper_basin_allocation + config.lower_basin_allocation (e.g. [10.5e6, 15e6] at the default 7.5e6 + 7.5e6) | IrrigationEnvironment._global["total_available_water"]; bound is BY CONSTRUCTION from advance_year()'s own `variability = 1.0 - drought_index * 0.3` with drought_index in [0, 1]
    drought_index          | world_to_agent | ratio_decimal | [0.0, 1.0]                                              | IrrigationEnvironment._compute_drought_index (advance_year)
    total_basin_demand     | world_to_agent | acre_ft       | [0.0, sum(water_right over env.agent_ids)]              | IrrigationEnvironment._global["total_basin_demand"]

  Inputs (agent_to_world, checked around ``commit_world_delta``):
    request                | agent_to_world | acre_ft       | [0.0, max(water_right over env.agent_ids)]              | IrrigationEnvironment.execute_skill -> state_changes["request"]
                              (world-computed from the agent's chosen skill
                              plus code-sampled magnitude, not a raw number
                              the LLM authors verbatim; ``is_derived=True``,
                              default ``value_source="world_deterministic"``)

See ``examples/irrigation_abm/tests/test_coupling.py::
test_contract_bounds_against_faf1bb12_corpus`` for these bounds checked
against the ``strict_42yr_gemma3_4b_faf1bb12_seed42`` real-CRSS corpus
(78 agents, 42 years) when that corpus is present locally.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from broker.coupling import (
    CouplingContract,
    CouplingViolation,
    Event,
    InterfaceBundle,
    VarSpec,
    WorldDelta,
)

from examples.irrigation_abm.irrigation_env import IrrigationEnvironment


def build_irrigation_coupling_contract(env: IrrigationEnvironment) -> CouplingContract:
    """The v0.6 coupling contract for ``IrrigationEnvironment``'s
    ``advance_step()`` / ``execute_skill()`` boundary.

    ``env`` must already be initialised (``initialize_synthetic`` /
    ``initialize_from_profiles`` / ``initialize_from_csv``): the
    ``total_available_water`` bound is derived from ``env.config``'s
    allocation constants, and the ``total_basin_demand`` / ``request``
    bounds are derived from the water_right values of the agents actually
    loaded into ``env`` (a real 78-agent CRSS run and a 5-agent synthetic
    smoke test have genuinely different physical ceilings; a single typed
    constant cannot be correct for both). See the module docstring's
    VarSpec table for the full name/unit/bounds/source list and the
    "SCOPE" section for what this contract deliberately does NOT cover.
    """
    cfg = env.config
    # advance_year()'s own formula: variability = 1.0 - drought_index * 0.3,
    # and drought_index is clamped to [0, 1] by _compute_drought_index, so
    # variability is always in [0.7, 1.0] - the BY-CONSTRUCTION bounds
    # below, not typed-in guesses.
    max_total_available_water = cfg.upper_basin_allocation + cfg.lower_basin_allocation
    min_total_available_water = max_total_available_water * 0.7

    water_rights = [
        float(env.get_agent_state(aid).get("water_right", 0.0))
        for aid in env.agent_ids
    ]
    if not water_rights or max(water_rights) <= 0.0:
        raise ValueError(
            "build_irrigation_coupling_contract requires an env whose "
            "agents are already initialised (initialize_synthetic / "
            "initialize_from_profiles / initialize_from_csv) - no positive "
            "water_right was found to derive the request / "
            "total_basin_demand bounds from."
        )
    max_water_right = max(water_rights)
    sum_water_right = sum(water_rights)

    return CouplingContract(
        observations=(
            VarSpec("year", int, "calendar_year", lo=1900, hi=2200),
            VarSpec(
                "total_available_water", float, "acre_ft",
                lo=min_total_available_water, hi=max_total_available_water,
            ),
            VarSpec("drought_index", float, "ratio_decimal", lo=0.0, hi=1.0),
            VarSpec("total_basin_demand", float, "acre_ft", lo=0.0, hi=sum_water_right),
        ),
        inputs=(
            VarSpec(
                "request", float, "acre_ft",
                lo=0.0, hi=max_water_right,
                direction="agent_to_world",
                is_derived=True,
            ),
        ),
        decision_cadence="annual",
        solver_cadence="annual",
        operation_order=("advance_physics", "commit_demand"),
    )


class IrrigationBundle(InterfaceBundle):
    """Wraps ``IrrigationEnvironment``'s year-advance and demand-commit
    behind the generic ``broker.coupling`` boundary.

    No discrete events (``event_src=None``): irrigation's water-system
    state is continuous/annual, not event-drawn, so
    ``EnvironmentCouplingAdapter.advance_step()`` treats every period as
    zero events - irrelevant here since ``run_pipeline`` ignores its
    ``events`` argument entirely (there is nothing event-shaped to fold
    in). See the module docstring for the byte-identity invariant, the
    workers note, and the scope this bundle does and does not cover.
    """

    def __init__(self, env: IrrigationEnvironment):
        super().__init__(event_src=None)
        self.env = env

    def run_pipeline(
        self,
        base_env: Dict[str, Any],
        events: List[Event],
        operation_order: Tuple[str, ...],
        control_hold_policy: str = "constant",
    ) -> Dict[str, Any]:
        """PURE PASS-THROUGH. ``base_env`` IS
        ``IrrigationEnvironment.advance_year()``'s own return value;
        ``EnvironmentCouplingAdapter._advance_real()`` already called it on
        the wrapped engine before this runs. Returning a shallow copy
        UNCHANGED (no field added, renamed, or dropped) is what keeps a
        coupled run's env dict, and every prompt built from it, byte-
        identical to the uncoupled path. No physics is re-run here.
        """
        return dict(base_env)

    def commit_world_delta(self, approved_skill: Any) -> WorldDelta:
        """PURE COMMITTER (E2: applies the already-governed delta exactly
        once). Forwards ``approved_skill`` straight to
        ``IrrigationEnvironment.execute_skill()``, the SAME call the
        uncoupled path makes directly via
        ``broker/core/skill_broker_engine.py``, and reshapes its
        ``ExecutionResult`` into a ``WorldDelta`` without recomputing
        anything.

        Fails loud (``CouplingViolation``) instead of silently reporting
        success when the underlying commit itself reports failure (unknown
        agent / unknown skill): ``EnvironmentCouplingAdapter.execute_skill``
        always returns ``success=True`` in its own ``ExecutionResult``
        regardless of what this method returns, so a swallowed failure here
        would otherwise vanish silently rather than surface as the
        audit-visible ABORTED path a direct (uncoupled) call would produce.
        This is a COMMIT-side violation (see the module docstring's
        "FAILURE MODE" section): it is caught per-agent by
        ``ExperimentRunner`` and recorded as one ABORTED audit row; the run
        continues. Never fires in a well-formed run (skill names always
        come from the registered ``IRRIGATION_SKILLS``, agent ids always
        match the initialised profiles), so it cannot affect the
        byte-identity invariant for a correct run.
        """
        result = self.env.execute_skill(approved_skill)
        if not result.success:
            raise CouplingViolation(
                "IrrigationEnvironment.execute_skill failed for "
                f"agent={getattr(approved_skill, 'agent_id', '?')!r} "
                f"skill={getattr(approved_skill, 'skill_name', '?')!r}: "
                f"{result.error}"
            )
        state_changes = dict(result.state_changes or {})
        world_changes: Dict[str, Any] = {}
        if "request" in state_changes:
            world_changes["request"] = state_changes["request"]
        return WorldDelta(
            agent_state_changes=state_changes,
            world_changes=world_changes,
            contention_rule="none",
        )

    def get_provenance(self) -> Dict[str, Any]:
        """World-side parameters for the reproducibility manifest
        (``ExperimentRunner._collect_reproducibility_metadata`` ->
        ``reproducibility_manifest.json``'s ``coupling_provenance``),
        mirroring ``CatBundle.get_provenance``'s role for this bundle."""
        cfg = self.env.config
        return {
            "bundle_class": type(self).__name__,
            "n_agents": len(self.env.agent_ids),
            "sim_start_year": cfg.sim_start_year,
            "sim_end_year": cfg.sim_end_year,
            "seed": cfg.seed,
        }


__all__ = ["IrrigationBundle", "build_irrigation_coupling_contract"]
