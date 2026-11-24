"""Projection check: ask the hosted model "what would happen if we did this?"
before a proposal runs, and refuse the proposal when a declared feasibility
bound would be breached (``CouplingContract.feasibility``).

Where the answer comes from (chosen once, when the check is built):

1. ``project``  the model's own ``project(inputs, context, substeps)`` method, if
   it has one. It returns ``{name: [value per sub-step]}`` for every model name
   the bounds read. The model is trusted to leave its own state, RNG and files
   alone while answering.
2. ``copy``  a deep copy of a Python solver, stepped one decision period on the
   copy. The bundle's ``apply_forecast(copy, context)`` feeds the copy the
   forecast the agent saw (not the true next inflow, which the agent could not
   know). The live solver is never touched.
3. Anything else is a BUILD error (never a silent skip): the contract declares
   bounds but the model has no ``project()`` and cannot be deep-copied.

What is judged: ``must_hold`` is evaluated at EVERY projected sub-step on the
model's values and on ``requested_<input>`` (the value the proposal asks for,
before any clamp). A bound should be written on the value before clamping (a
model that clamps storage at zero reports 0.0 for a request that wanted
-3.0), which is why a model publishes it through ``get_value``.

Isolation while projecting (both sources): the global ``random`` and the legacy
``numpy.random`` states are saved and restored. On the copy source only, a
process-wide audit hook (installed the first time a copy is projected; a no-op
when no projection is running on the thread) stops the run with
``ProjectionSideEffect`` when the copy opens a file for writing, removes,
renames or links one, changes its permissions or times, makes or removes a
directory, truncates a file, runs ``shutil.rmtree``, or starts or signals a
process. The run stops even when the model's own code catches that exception.
The process-wide parts (the RNG restore, no bytecode cache, the paused garbage
collector) are why a run that declares feasibility bounds must use
``workers=1``: the builder refuses ``workers>1`` for it.

LIMITS of the copy source. The guard sees only what Python's audit events
report, and the copy is only as separate as ``copy.deepcopy`` makes it. NOT
seen or not protected: writes made by native code (C, Fortran, ``sqlite3``);
``os.write`` to a file that was already open; log records sent to an existing
logging handler (``deepcopy`` of a logger returns the same logger, so a copy
that logs appends to the live log); threads or processes the copy starts by
means without an audit event (e.g. ``_posixsubprocess.fork_exec``, which
``multiprocessing`` uses on POSIX); network traffic; changes to ``os.environ``
or the working directory; and state the copy shares with the live model
(generators from ``numpy.random.default_rng()`` kept at module level, class
attributes, objects whose ``__deepcopy__`` returns ``self``, native handles);
and finalizers: pausing the garbage collector does not stop an object freed by
its last reference going away, and the copy itself is freed after the guard is
off, so a ``__del__`` that writes a file is not seen. A model that does any of
these needs a ``project()`` method.

Errors raised here while a proposal is validated (a value that cannot be read,
a zero divisor, a side effect) are ``ProjectionCheckError`` (a
``CouplingViolation``). The experiment runner re-raises them so the run stops
instead of filing one more ABORTED row.
"""
from __future__ import annotations

import contextlib
import copy
import gc
import logging
import math
import os
import random
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from broker.governance.expression_condition import (
    ExpressionEvaluationError,
    compile_expression_condition,
    evaluate_expression_condition,
)
from broker.interfaces.skill_types import ApprovedSkill, ValidationResult

from .adapter import CouplingViolation
from .bmi_source import _scalar
from .continuous import BmiControlSink, ContinuousBundle

logger = logging.getLogger(__name__)

REQUESTED_PREFIX = "requested_"


class ProjectionCheckError(CouplingViolation):
    """The projection check could not judge a proposal; the run stops."""


class ProjectionSideEffect(ProjectionCheckError):
    """A projection copy tried to change something outside itself."""


# ----------------------------------------------------------------------
# Guard against side effects on a copy (one process-wide audit hook)
# ----------------------------------------------------------------------
_state = threading.local()
_hook_lock = threading.Lock()
_hook_installed = False

_WRITE_OPEN_FLAGS = (
    os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
)
_BLOCKED_EVENTS = frozenset({
    "os.remove", "os.rename", "os.replace", "os.mkdir", "os.rmdir",
    "os.truncate", "os.symlink", "os.link", "os.chmod", "os.chown", "os.utime",
    "shutil.rmtree", "subprocess.Popen", "os.system", "os.exec", "os.spawn",
    "os.posix_spawn", "os.startfile", "os.fork", "os.forkpty", "os.kill",
    "os.killpg", "_winapi.CreateProcess",
})
_HOW_TO_FIX = (
    "A projection must not change anything outside the copy. Give the model a "
    "project() method, or turn the copy's file output off in the bundle's "
    "apply_forecast(model_copy, context)."
)


def _describe(arg: Any) -> str:
    try:
        return repr(os.fsdecode(arg)) if isinstance(arg, (str, bytes, os.PathLike)) else repr(arg)
    except Exception:  # noqa: BLE001 - only used to build a message
        return "<unprintable>"


def _block(message: str) -> None:
    # Remember the first block on this thread, so the run still stops when the
    # model's own code catches the exception (see _guarding_copy).
    if getattr(_state, "blocked", None) is None:
        _state.blocked = message
    raise ProjectionSideEffect(message)


def _audit_hook(event: str, args: Tuple[Any, ...]) -> None:
    if not getattr(_state, "projecting", False):
        return  # the common case: cheap and silent
    if event == "open":
        path = args[0] if args else None
        if isinstance(path, int):
            return  # an existing file descriptor, not a new file
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else None
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and bool(flags & _WRITE_OPEN_FLAGS)
        )
        if not writing:
            return
        _block(
            f"a projection copy tried to open {_describe(path)} for writing "
            f"(mode {mode!r}). " + _HOW_TO_FIX
        )
    if event in _BLOCKED_EVENTS:
        what = ", ".join(_describe(a) for a in args[:2])
        _block(f"a projection copy triggered {event}({what}). " + _HOW_TO_FIX)


def _install_hook() -> None:
    global _hook_installed
    if _hook_installed:
        return
    with _hook_lock:
        if not _hook_installed:
            sys.addaudithook(_audit_hook)
            _hook_installed = True


@contextlib.contextmanager
def _guarding_copy():
    """Turn the side-effect guard on for this thread. A blocked side effect
    stops the run even when the model's own code caught the exception.

    While it is on, the import system writes no bytecode cache (a first-time
    import inside the copy would otherwise make ``__pycache__`` and trip the
    guard), and the cyclic garbage collector is paused (a finalizer of some
    unrelated object, e.g. a temporary directory's cleanup, would otherwise run
    on this thread and be blamed on the copy). Both are process-wide, which is
    why the builder requires ``workers=1`` with feasibility bounds.
    """
    _install_hook()
    previous = getattr(_state, "projecting", False)
    previous_blocked = getattr(_state, "blocked", None)
    previous_bytecode = sys.dont_write_bytecode
    gc_was_on = gc.isenabled()
    _state.projecting = True
    _state.blocked = None
    sys.dont_write_bytecode = True
    gc.disable()
    try:
        yield
        blocked = _state.blocked
    except ProjectionSideEffect:
        raise
    except Exception as exc:
        # The model caught the blocked side effect and then failed some other
        # way: report the side effect, which is the cause.
        if _state.blocked is not None:
            raise ProjectionSideEffect(_state.blocked) from exc
        raise
    finally:
        _state.projecting = previous
        _state.blocked = previous_blocked
        sys.dont_write_bytecode = previous_bytecode
        if gc_was_on:
            gc.enable()
    if blocked is not None:
        raise ProjectionSideEffect(blocked)


@contextlib.contextmanager
def _rng_restored():
    """Leave the global ``random`` and ``numpy.random`` states as they were."""
    py_state = random.getstate()
    try:
        import numpy as np
    except ImportError:  # pragma: no cover - numpy is a dependency of the framework
        np = None
    np_state = np.random.get_state() if np is not None else None
    try:
        yield
    finally:
        random.setstate(py_state)
        if np is not None:
            np.random.set_state(np_state)


# ----------------------------------------------------------------------
# Results
# ----------------------------------------------------------------------
@dataclass
class Breach:
    """One bound that a projection does not meet."""

    bound: str
    substep: int
    substeps: int
    source: str
    projected: Dict[str, float]
    requested: Dict[str, float]
    skill: str
    text: str


def _fmt(values: Mapping[str, float]) -> str:
    return ", ".join(f"{k}={v:.6g}" for k, v in values.items()) or "(nothing)"


class ProjectionCheck:
    """A custom validator ``(proposal, context, registry) -> [ValidationResult]``
    built from the coupling adapter (its contract and its bundle).

    Build errors (a bound that reads a name nothing provides, a model that
    cannot be projected) raise ``ValueError`` here, before the run starts; a
    side effect of the build-time trial copy raises ``ProjectionSideEffect``.
    """

    def __init__(self, adapter: Any) -> None:
        self.contract = adapter.contract
        self.bundle = adapter.sources
        bounds = tuple(self.contract.feasibility)
        if not bounds:
            raise ValueError("ProjectionCheck needs a contract that declares feasibility bounds")
        self._bounds = bounds
        self._compiled = {
            b.name: compile_expression_condition(
                b.must_hold, where=f"FeasibilityBound[{b.name}]"
            )
            for b in bounds
        }
        self._substeps = int(self.contract.substeps_per_decision or 1)
        self.projections_run = 0

        input_names = {vs.name for vs in self.contract.inputs}
        model_names: List[str] = []
        for b in bounds:
            for name in self._compiled[b.name].names:
                if name.startswith(REQUESTED_PREFIX):
                    base = name[len(REQUESTED_PREFIX):]
                    if base not in input_names:
                        raise ValueError(
                            f"FeasibilityBound[{b.name}]: {name!r} names no declared input "
                            f"{base!r}; inputs are {sorted(input_names)}."
                        )
                elif name not in model_names:
                    model_names.append(name)
        self._model_names = tuple(model_names)
        self.source = self._select_source()

    # ------------------------------------------------------------------
    # build time
    # ------------------------------------------------------------------
    def _select_source(self) -> str:
        if not callable(getattr(self.bundle, "inputs_for_skill", None)):
            raise ValueError(
                "contract declares feasibility bounds but the bundle "
                f"{type(self.bundle).__name__} has no inputs_for_skill(approved_skill), "
                "so the setpoints a proposal asks for cannot be worked out before it runs."
            )
        solver = getattr(self.bundle, "solver", None)
        if solver is not None and callable(getattr(solver, "project", None)):
            return "project"
        cannot = (
            "contract declares feasibility bounds but the model has no project() and "
            "cannot be deep-copied; give it project() or remove the bounds"
        )
        if solver is None or not isinstance(self.bundle, ContinuousBundle):
            raise ValueError(f"{cannot} (the bundle {type(self.bundle).__name__} hosts no solver).")
        sink = getattr(self.bundle, "sink", None)
        # Exactly the default sink: the copy is driven by a plain
        # BmiControlSink, so a subclass that changes apply_control would be
        # projected with different controls than the live model gets. Every
        # subclass is refused on purpose (one that does not override cannot be
        # told apart cheaply); do not relax this to isinstance.
        if self.contract.inputs and type(sink) is not BmiControlSink:
            raise ValueError(
                "contract declares feasibility bounds and the model is projected on a copy, "
                f"which takes its setpoints through set_value; but the bundle's sink is "
                f"{type(sink).__name__}, so the copy would not get them the way the live "
                "model does. Give the model project(), or use the default sink."
            )
        # The trial copy runs under the same isolation as a projection.
        with _rng_restored(), _guarding_copy():
            try:
                trial = copy.deepcopy(solver)
            except Exception as exc:  # noqa: BLE001 - any failure to copy is a build error
                raise ValueError(
                    f"{cannot}. Deep copy of {type(solver).__name__} failed: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            overridden = type(self.bundle).apply_forecast is not ContinuousBundle.apply_forecast
            if not overridden and not getattr(self.bundle, "projection_has_no_forcing", False):
                raise ValueError(
                    f"contract declares feasibility bounds and the model is projected on a copy, "
                    f"but {type(self.bundle).__name__} does not implement "
                    "apply_forecast(model_copy, context), so the copy would not see the forecast "
                    "the agent saw. Implement it, or set projection_has_no_forcing = True on the "
                    "bundle if the model has no outside forcing."
                )
            for b in self._bounds:
                for name in self._compiled[b.name].names:
                    if name.startswith(REQUESTED_PREFIX):
                        continue
                    try:
                        _scalar(trial.get_value(name))
                    except Exception as exc:  # noqa: BLE001
                        raise ValueError(
                            f"FeasibilityBound[{b.name}]: the model does not answer {name!r} "
                            f"through get_value ({type(exc).__name__}: {exc}). Use a name the "
                            "model publishes, or requested_<input> for a declared input."
                        ) from exc
        return "copy"

    # ------------------------------------------------------------------
    # validator entry point
    # ------------------------------------------------------------------
    def __call__(self, proposal: Any, context: Any, registry: Any = None) -> List[ValidationResult]:
        if proposal is None:
            return []
        skill = getattr(proposal, "skill_name", None)
        if not any(b.applies_to(skill) for b in self._bounds):
            return []
        from broker.core.skill_broker_engine import parameters_from_proposal

        breaches = self.check_skill(
            skill, parameters_from_proposal(proposal), context,
            getattr(proposal, "agent_id", None), stop_at_first=True,
        )
        return [
            ValidationResult(
                valid=False,
                validator_name=b.bound,
                errors=[b.text],
                metadata={
                    "category": "physical",
                    "rule_id": b.bound,
                    "grounding": "world",
                    "deterministic": True,
                    "source": b.source,
                    "substep": b.substep,
                    "projected": dict(b.projected),
                    "requested": dict(b.requested),
                },
            )
            for b in breaches
        ]

    # ------------------------------------------------------------------
    # the what-if run
    # ------------------------------------------------------------------
    def check_skill(
        self,
        skill_name: str,
        parameters: Dict[str, Any],
        context: Any,
        agent_id: Optional[str] = None,
        *,
        stop_at_first: bool = True,
    ) -> List[Breach]:
        """Project ``skill_name`` with ``parameters`` and return the breaches.

        ``stop_at_first`` stops at the first sub-step where any bound is
        breached (the validator path). Otherwise the whole period is run and
        each bound's first breach is reported (the default-after-retries mark).
        """
        bounds = [b for b in self._bounds if b.applies_to(skill_name)]
        if not bounds:
            return []
        approved = ApprovedSkill(
            skill_name=skill_name,
            agent_id=str(agent_id or ""),
            approval_status="PROPOSED",
            parameters=dict(parameters or {}),
        )
        try:
            inputs = {k: float(v) for k, v in self.bundle.inputs_for_skill(approved).items()}
        except ProjectionCheckError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProjectionCheckError(
                f"projection of {skill_name!r}: could not work out the setpoints the "
                f"proposal asks for ({type(exc).__name__}: {exc})"
            ) from exc
        requested = {REQUESTED_PREFIX + k: v for k, v in inputs.items()}
        needed = [n for n in self._model_names if any(
            n in self._compiled[b.name].names for b in bounds)]
        found: Dict[str, Breach] = {}

        def on_substep(k: int, model_values: Dict[str, float]) -> bool:
            values = {**model_values, **requested}
            hit = False
            for b in bounds:
                if b.name in found:
                    continue
                compiled = self._compiled[b.name]
                try:
                    outcome = evaluate_expression_condition(compiled, {}, {"env_state": values})
                except ExpressionEvaluationError as exc:
                    raise ProjectionCheckError(
                        f"feasibility bound {b.name!r} on {skill_name!r}, sub-step {k}: {exc}"
                    ) from exc
                if not outcome.readable:
                    raise ProjectionCheckError(
                        f"feasibility bound {b.name!r} on {skill_name!r}, sub-step {k}: cannot "
                        f"be judged (missing {list(outcome.missing)}, unusable "
                        f"{[n for n, _ in outcome.unusable]}). A bound may read "
                        f"requested_<input> of an input this skill sets, or a name the model "
                        "answers; never an assumed value."
                    )
                if not outcome.matched:
                    projected = {n: values[n] for n in compiled.names if n in model_values}
                    found[b.name] = Breach(
                        bound=b.name, substep=k, substeps=self._substeps,
                        source=self.source, projected=projected, requested=dict(inputs),
                        skill=skill_name,
                        text=(
                            f"{skill_name} (requested {_fmt(inputs)}) breaks {b.name}: "
                            f"{b.must_hold} does not hold; the model projects "
                            f"{_fmt(projected)} at sub-step {k} of {self._substeps} "
                            f"({self.source} projection)."
                        ),
                    )
                    hit = True
            return hit and stop_at_first

        self.projections_run += 1
        with _rng_restored():
            if self.source == "project":
                self._run_project(inputs, context, needed, on_substep)
            else:
                self._run_copy(inputs, context, needed, on_substep)
        return sorted(found.values(), key=lambda br: (br.substep, br.bound))

    def _run_project(
        self, inputs: Dict[str, float], context: Any, needed: List[str],
        on_substep: Callable[[int, Dict[str, float]], bool],
    ) -> None:
        solver = self.bundle.solver
        try:
            result = solver.project(dict(inputs), context, self._substeps)
            if not isinstance(result, Mapping):
                raise ProjectionCheckError(
                    f"project() returned {type(result).__name__}, expected "
                    "{name: [value per sub-step]}"
                )
            missing = [n for n in needed if n not in result]
            if missing:
                raise ProjectionCheckError(
                    f"project() did not return {missing}, which the feasibility bounds read "
                    f"(it returned {sorted(result)})"
                )
            series = {n: [float(v) for v in result[n]] for n in needed}
        except ProjectionCheckError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProjectionCheckError(
                f"the model's project() failed ({type(exc).__name__}: {exc})"
            ) from exc
        wrong = {n: len(v) for n, v in series.items() if len(v) != self._substeps}
        if wrong:
            raise ProjectionCheckError(
                f"project() must return one value per sub-step ({self._substeps}) for "
                f"each name the bounds read; got lengths {wrong}"
            )
        for k in range(self._substeps if series else 1):
            if on_substep(k + 1, {n: series[n][k] for n in needed}):
                return

    def _run_copy(
        self, inputs: Dict[str, float], context: Any, needed: List[str],
        on_substep: Callable[[int, Dict[str, float]], bool],
    ) -> None:
        bundle = self.bundle
        try:
            with _guarding_copy():
                model = copy.deepcopy(bundle.solver)
                if type(bundle).apply_forecast is not ContinuousBundle.apply_forecast:
                    bundle.apply_forecast(model, context)
                if inputs:
                    sink = BmiControlSink(model)
                    for name, value in inputs.items():
                        sink.apply_control(name, value)
                for k in range(1, self._substeps + 1):
                    model.update()
                    values = {n: _scalar(model.get_value(n)) for n in needed}
                    if on_substep(k, values):
                        return
        except ProjectionCheckError:
            raise
        except Exception as exc:  # noqa: BLE001 - a projection that fails must stop the run
            raise ProjectionCheckError(
                f"the what-if run on a copy of {type(bundle.solver).__name__} failed "
                f"({type(exc).__name__}: {exc})"
            ) from exc

    def describe(self) -> Dict[str, Any]:
        """Facts for the run's provenance."""
        return {
            "source": self.source,
            "substeps": self._substeps,
            "model_names_read": list(self._model_names),
            "projections_run": self.projections_run,
        }


__all__ = [
    "Breach",
    "ProjectionCheck",
    "ProjectionCheckError",
    "ProjectionSideEffect",
]
