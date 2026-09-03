"""
Numeric parameter optimizer for calibration targets.

``broker.domains.water.calibration.calibration_protocol.CalibrationProtocol``
is a diagnostic pilot loop, not an optimizer: it varies only the RNG seed
across iterations and never feeds its own ``AdjustmentRecommendation``
objects back into a simulation's parameters (see that module's docstring,
PR-7 audit finding). This module is the actual search: it takes a
caller-supplied objective function and a bounded parameter space, and
returns the best parameters found under a numeric-evaluation budget.

Scope: NON-PROMPT numeric parameters only
------------------------------------------
``optimize_parameters`` refuses any ``space`` key that looks like a
prompt or template path (contains ``prompt``, ``template``,
``system_message``, or ``persona_text``). This is an **advisory guard
against accidental inclusion**, not a security boundary — it matches on
the key's name, so renaming a key sidesteps it entirely. Its job is to
catch the case where somebody flattens a whole config dict and hands
the result to the search without noticing that prompt paths came along
for the ride. The reason it is worth catching: automatically rewriting
what an agent is *told* is a different, higher-stakes kind of change
than tuning a numeric decision threshold, and WAGF keeps prompt wording
human-reviewed everywhere else in the calibration stack —
``CalibrationProtocol`` only ever *recommends* a prompt change as text
(see its "Human-in-the-loop" design principle); it never applies one.
This optimizer inherits that boundary rather than re-litigating it: it
searches base rates, slopes, cost weights, thresholds — anything that
goes into a decision function as a number — and stops before anything
that goes into a prompt as words.

Two search methods
-------------------
``method="nelder-mead"`` uses ``scipy.optimize.minimize`` when the
``analysis`` extra (``pip install wagf[analysis]``, which pulls in
scipy) is installed. When scipy is not importable, it falls back to a
pure-python coordinate-descent pattern search (Hooke-Jeeves style) —
``OptimizeResult.method`` names which one actually ran, e.g.
``"nelder-mead (scipy)"`` or ``"nelder-mead (pure-python fallback)"``,
so a report never silently claims a search method that did not run.
Whether scipy is available is decided by probing the import on its own,
*before* the search starts, so an ``ImportError`` raised from inside
the caller's objective is never mistaken for "scipy is missing" and
never triggers a silent re-run under the other method.

What a result says about itself
--------------------------------
Every :class:`OptimizeResult` carries the four facts needed to judge
whether the search actually did anything: ``converged`` with a
``termination_reason`` naming *why* it stopped, ``n_evals`` against the
``max_evals`` budget, ``x0`` (the point the search started from), and
``search_moved`` — ``False`` means the best parameters found are the
starting point, i.e. the search never improved on where it began. That
is a legitimate outcome (the start may already be optimal) but it is
never a *calibration*, so the result also carries a ``warning`` string
saying so in plain words.

Non-finite losses are refused. If an objective returns NaN or inf, the
search raises ``ValueError`` at that evaluation instead of carrying the
value into a comparison — NaN loses every ``<`` comparison it takes
part in, so a search that tolerates it silently reports as "best" a
point it never actually measured.

Held-out validation
--------------------
:func:`split_targets` splits a dict of ``{metric_name: target_value}``
into an in-sample set and a held-out set, deterministically under a
seed. Pass a ``held_out_objective`` built from the held-out set to
:func:`optimize_parameters` and the result reports both distances —
the point is not that held-out always improves (it need not, with a
handful of correlated metrics), it is that a calibration report can
say what happened out of sample instead of only in it.

:func:`split_targets` also refuses a split in which a held-out value is
bit-identical to an in-sample value. Two metric names carrying one
number are not two measurements: fitting the in-sample twin hits the
"held-out" one exactly, and the out-of-sample number that comes back is
worthless. Pass ``observed=`` (the metric values the model actually
produces at the starting parameters) to run the same check on the model
side, which is where aliasing usually originates — one estimator
assigned to two metric keys.
"""

from __future__ import annotations

import itertools
import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ObjectiveFn = Callable[[Dict[str, float]], float]
"""(flat_params: Dict[str, float]) -> loss: float

Caller-supplied. Lower is better. Must return a finite float — a NaN or
inf return raises ``ValueError`` at the evaluation site. Typical
choices: a weighted distance between simulated and empirical target
values, or ``1 - EPI`` from a
:class:`~broker.calibration.benchmark_registry.BenchmarkReport` (but
see that module's ``band_distance`` first: a pass rate over a handful
of benchmarks is piecewise constant, so it gives a search nothing to
descend).
"""

_PROMPT_KEY_MARKERS: Tuple[str, ...] = (
    "prompt", "template", "system_message", "persona_text",
)

_NO_MOVE_WARNING = "search never left its starting point"
"""Exact ``OptimizeResult.warning`` text when ``search_moved`` is False."""


def _assert_non_prompt_space(space: Dict[str, Tuple[float, float]]) -> None:
    """Refuse a search space that contains prompt/template-shaped keys.

    An **advisory guard against accidental inclusion** — it matches on
    key names, so it catches "I flattened the whole config and prompt
    paths came along", not a caller who means to search prompt text and
    renames the key. See the module docstring "Scope" section for why
    the accident is worth catching.
    """
    offenders = sorted(
        k for k in space
        if any(marker in k.lower() for marker in _PROMPT_KEY_MARKERS)
    )
    if offenders:
        raise ValueError(
            "optimize_parameters is scoped to non-prompt numeric "
            f"parameters; these space keys look like prompt/template "
            f"paths: {offenders}. Prompt calibration is a human-in-the-"
            f"loop decision (see broker.calibration.optimize module "
            f"docstring) — remove them from `space` and adjust the "
            f"prompt by hand."
        )


def _evaluate(objective: ObjectiveFn, params: Dict[str, float], where: str) -> float:
    """Call ``objective`` and refuse a non-finite result.

    A NaN loss compares False against every bound, so it neither wins
    nor loses a ``loss < best_loss`` test — a search that lets it
    through keeps whatever "best" it held before and then reports that
    point as if it had been measured. inf is the same failure with the
    sign flipped. Both are objective bugs (a division by an empty
    population, a log of zero), so this raises at the evaluation site,
    naming the parameters that produced it, rather than reporting a
    best point the search never stood on.
    """
    loss = float(objective(params))
    if not math.isfinite(loss):
        raise ValueError(
            f"objective returned a non-finite loss ({loss!r}) at {where} "
            f"with params={params}. A non-finite loss cannot be compared, "
            f"so the search would report a best point it never actually "
            f"measured. Fix the objective (guard the empty denominator / "
            f"log of zero / missing metric that produced it) — this "
            f"optimizer will not carry NaN or inf into a comparison."
        )
    return loss


# ---------------------------------------------------------------------------
# Flatten / unflatten helpers
# ---------------------------------------------------------------------------

def flatten_dict(d: Dict[str, Any], sep: str = ".") -> Dict[str, float]:
    """Flatten a nested dict of numbers to ``{"a.b.c": value}``."""
    out: Dict[str, float] = {}

    def _walk(node: Dict[str, Any], prefix: str) -> None:
        for key, value in node.items():
            path = f"{prefix}{sep}{key}" if prefix else str(key)
            if isinstance(value, dict):
                _walk(value, path)
            else:
                out[path] = value

    _walk(d, "")
    return out


def unflatten_dict(flat: Dict[str, float], sep: str = ".") -> Dict[str, Any]:
    """Inverse of :func:`flatten_dict`.

    Raises ``ValueError`` on a key collision — ``{"a": 1, "a.b": 2}``
    asks for ``a`` to be both a number and a dict, and silently
    dropping one of them (which ``setdefault`` alone would do) loses a
    parameter the caller asked to set.
    """
    out: Dict[str, Any] = {}
    for path, value in flat.items():
        parts = path.split(sep)
        node = out
        for depth, part in enumerate(parts[:-1]):
            branch = node.setdefault(part, {})
            if not isinstance(branch, dict):
                prefix = sep.join(parts[:depth + 1])
                raise ValueError(
                    f"cannot unflatten {path!r}: {prefix!r} is already a "
                    f"leaf value ({branch!r}). One of these two keys has "
                    f"to go — a name cannot be both a number and a "
                    f"sub-dict."
                )
            node = branch
        leaf = parts[-1]
        if leaf in node:
            raise ValueError(
                f"cannot unflatten {path!r}: {path!r} collides with an "
                f"already-placed entry ({node[leaf]!r}). Two flat keys "
                f"map to the same slot; rename one."
            )
        node[leaf] = value
    return out


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class OptimizeResult:
    """Outcome of one :func:`optimize_parameters` call.

    ``in_sample_distance`` / ``held_out_distance`` are whatever the
    caller's objective returned — "distance" is the usual case, not a
    guarantee. ``search_moved`` False means ``best_params == x0``: the
    search reports its starting point, which is an answer but not a
    calibration.
    """

    best_params: Dict[str, float]
    best_loss: float
    n_evals: int
    method: str
    converged: bool
    seed: int
    termination_reason: str = ""
    max_evals: Optional[int] = None
    x0: Dict[str, float] = field(default_factory=dict)
    search_moved: bool = True
    in_sample_distance: Optional[float] = None
    held_out_distance: Optional[float] = None
    formula_version: Optional[str] = None

    @property
    def warning(self) -> Optional[str]:
        """Plain-words caveat, or ``None`` when there is nothing to warn about."""
        if not self.search_moved:
            return _NO_MOVE_WARNING
        return None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "best_params": {k: round(v, 6) for k, v in self.best_params.items()},
            "best_loss": round(self.best_loss, 6),
            "n_evals": self.n_evals,
            "max_evals": self.max_evals,
            "method": self.method,
            "converged": self.converged,
            "termination_reason": self.termination_reason,
            "x0": {k: round(v, 6) for k, v in self.x0.items()},
            "search_moved": self.search_moved,
            "seed": self.seed,
            "formula_version": self.formula_version,
            "in_sample_distance": (
                round(self.in_sample_distance, 6)
                if self.in_sample_distance is not None else None
            ),
            "held_out_distance": (
                round(self.held_out_distance, 6)
                if self.held_out_distance is not None else None
            ),
        }
        if self.warning is not None:
            payload["warning"] = self.warning
        return payload


@dataclass
class TargetSplit:
    """Deterministic in-sample / held-out split of a target dict.

    ``held_out_disjoint_check`` reports what :func:`split_targets`
    found, in three shapes:

    * ``"passed"`` — no held-out TARGET value collided with an
      in-sample one, and (when ``observed`` was supplied) the model's
      own values for the two sides were checked and did not collide
      either.
    * ``"passed (target-side collision on <names>, observed-side
      disjoint)"`` — two DIFFERENT metrics happen to publish the same
      target value (e.g. two benchmarks with the same midpoint by
      coincidence, not one estimator under two names); the model's own
      observed values for them were checked and are distinct.
    * ``"not_checked (observed not supplied)"`` — no ``observed`` was
      given, so the side of this check that actually catches aliasing
      (see :func:`split_targets`) never ran. This is never reported as
      ``"passed"``, even when the targets themselves are disjoint: a
      target-side pass says nothing about whether the model's
      estimator is aliased.

    A TARGET-side collision only warns (via ``logging``) — it is not
    proof of aliasing. An OBSERVED-side collision, when checked, still
    raises ``ValueError`` and no ``TargetSplit`` is constructed; see
    :func:`_assert_values_disjoint`.
    """

    in_sample: Dict[str, float]
    held_out: Dict[str, float]
    holdout_fraction: float
    seed: int
    held_out_disjoint_check: str = "passed"
    disjoint_check_used_observed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "in_sample": dict(self.in_sample),
            "held_out": dict(self.held_out),
            "holdout_fraction": self.holdout_fraction,
            "seed": self.seed,
            "held_out_disjoint_check": self.held_out_disjoint_check,
            "disjoint_check_used_observed": self.disjoint_check_used_observed,
        }


def _value_collisions(
    in_sample: Dict[str, float],
    held_out: Dict[str, float],
) -> List[Tuple[str, str, float]]:
    """Every ``(held_key, in_key, value)`` where a held-out value is
    bit-identical to an in-sample value. No raising — just the scan.

    Shared by both checks :func:`split_targets` runs: the TARGET-side
    one (advisory — two different metrics can coincidentally publish
    the same number) and the OBSERVED-side one via
    :func:`_assert_values_disjoint` (fatal — the model producing the
    same number for two different metric names is an aliased
    estimator, not a coincidence).
    """
    collisions: List[Tuple[str, str, float]] = []
    for held_key, held_value in sorted(held_out.items()):
        for in_key, in_value in sorted(in_sample.items()):
            if held_value == in_value:
                collisions.append((held_key, in_key, held_value))
    return collisions


def _assert_values_disjoint(
    in_sample: Dict[str, float],
    held_out: Dict[str, float],
    side: str,
) -> None:
    """Refuse a split where a held-out value equals an in-sample value.

    Bit-identical, not "close": two metric names carrying one number
    are one measurement wearing two labels. Fitting the in-sample label
    lands exactly on the "held-out" one, so the out-of-sample number
    that comes back measures nothing. The usual cause is an aliased
    estimator — one computation assigned to two metric keys — which is
    why this check is worth running on the model's own output
    (``observed``) as well as on the targets.

    Only the caller decides which side this fires for. ``side="target"``
    is no longer used to *raise* (see :func:`split_targets` — a
    target-side collision is common and often innocent, so it only
    warns); this function still raises unconditionally whenever it is
    called, which is why ``split_targets`` only calls it for
    ``side="observed"``.
    """
    collisions = _value_collisions(in_sample, held_out)
    if collisions:
        lines = [
            f"{held_key}={value!r} (held out) == {in_key}={value!r} (in sample)"
            for held_key, in_key, value in collisions
        ]
        raise ValueError(
            f"held-out/in-sample {side} values are not disjoint:\n  "
            + "\n  ".join(lines)
            + "\nA held-out metric whose value is bit-identical to an "
              "in-sample metric is not held out: fitting the in-sample "
              "twin hits it exactly, so the reported out-of-sample "
              "number is meaningless. Check for an aliased estimator "
              "(one computation assigned to two metric names), or drop "
              "one of the two metrics from the split."
        )


def split_targets(
    targets: Dict[str, float],
    holdout_fraction: float = 0.2,
    seed: int = 42,
    observed: Optional[Dict[str, float]] = None,
) -> TargetSplit:
    """Split a ``{metric_name: target_value}`` dict deterministically.

    Parameters
    ----------
    targets : dict
        Metric name -> empirical target value (e.g. a benchmark
        midpoint). Split at the metric-name level, not per-observation
        — WAGF calibration targets are population-level rates, not
        rows of data.
    holdout_fraction : float
        Fraction of metric names to hold out. At least 1 metric is held
        out whenever 2 or more are available; at least 1 stays
        in-sample.
    seed : int
        Shuffle seed. Same ``targets`` + same ``seed`` always produce
        the same split.
    observed : dict, optional
        The values the model actually produces for these metrics (at
        the starting parameters, say). When given, the identical-value
        check runs on these too, and — unlike the target-side check —
        a collision here RAISES: model-side aliasing (one estimator,
        two metric names) is the common case and does not show up in
        the targets at all. Omitting ``observed`` means that check
        never runs; ``held_out_disjoint_check`` on the result says so
        (``"not_checked (observed not supplied)"``) rather than
        reporting a "passed" that only ever looked at the targets.

    Raises
    ------
    ValueError
        If any held-out value is bit-identical to an in-sample value in
        ``observed``. See :func:`_assert_values_disjoint`. A collision
        in ``targets`` alone does NOT raise — two different metrics can
        legitimately publish the same value by coincidence (e.g. two
        FLOOD_BENCHMARKS entries that both happen to have midpoint
        0.275); it is logged as a warning and recorded on the result
        instead. See :class:`TargetSplit`.
    """
    if not 0.0 <= holdout_fraction < 1.0:
        raise ValueError(f"holdout_fraction must be in [0, 1); got {holdout_fraction}")

    keys = sorted(targets)  # deterministic order before shuffling
    rng = random.Random(seed)
    shuffled = keys[:]
    rng.shuffle(shuffled)

    n = len(shuffled)
    n_holdout = round(n * holdout_fraction)
    if n >= 2:
        n_holdout = max(1, min(n_holdout, n - 1))
    else:
        n_holdout = 0

    holdout_keys = set(shuffled[:n_holdout])
    in_sample = {k: v for k, v in targets.items() if k not in holdout_keys}
    held_out = {k: v for k, v in targets.items() if k in holdout_keys}

    disjoint_check = "passed"
    if held_out:
        target_collisions = _value_collisions(in_sample, held_out)
        if target_collisions:
            colliding_names = sorted({
                name for held_key, in_key, _ in target_collisions
                for name in (held_key, in_key)
            })
            logger.warning(
                "held-out/in-sample TARGET values collide on %s (the "
                "published numbers coincide) but this is only checked "
                "on the targets, not on what the model actually "
                "produces for them — different metrics can share a "
                "published midpoint by coincidence (e.g. two "
                "benchmarks that both happen to be 0.275). Pass "
                "observed= to check the side that actually catches an "
                "aliased estimator.",
                colliding_names,
            )

        if observed is not None:
            obs_in = {k: v for k, v in observed.items() if k in in_sample}
            obs_held = {k: v for k, v in observed.items() if k in held_out}
            if obs_in and obs_held:
                _assert_values_disjoint(obs_in, obs_held, side="observed")
            if target_collisions:
                disjoint_check = (
                    f"passed (target-side collision on "
                    f"{', '.join(colliding_names)}, observed-side disjoint)"
                )
            # else: no target collision and the observed check above
            # did not raise -> stays "passed".
        else:
            disjoint_check = "not_checked (observed not supplied)"

    return TargetSplit(
        in_sample=in_sample, held_out=held_out,
        holdout_fraction=holdout_fraction, seed=seed,
        held_out_disjoint_check=disjoint_check,
        disjoint_check_used_observed=observed is not None,
    )


# ---------------------------------------------------------------------------
# Search methods
# ---------------------------------------------------------------------------

@dataclass
class _SearchOutcome:
    """What one search method reports back to :func:`optimize_parameters`."""

    best_params: Dict[str, float]
    best_loss: float
    n_evals: int
    converged: bool
    termination_reason: str
    x0: Dict[str, float]


def _grid_search(
    objective: ObjectiveFn,
    space: Dict[str, Tuple[float, float]],
    max_evals: int,
) -> _SearchOutcome:
    """Evenly discretise each dimension and evaluate the cartesian product,
    capped at ``max_evals``. Deterministic — no RNG involved.

    ``converged`` means the *full* grid was enumerated. Being stopped by
    ``max_evals`` partway through is not convergence: ``itertools.product``
    varies the last dimension fastest, so a truncated run may never have
    changed the leading dimensions at all — the termination reason names
    which ones.
    """
    names = list(space)
    n_dims = max(len(names), 1)
    # Choose a per-dimension level count so the full grid stays <= max_evals.
    levels = max(2, int(round(max_evals ** (1.0 / n_dims))))
    axes: List[List[float]] = []
    for name in names:
        lo, hi = space[name]
        if levels == 1:
            axes.append([(lo + hi) / 2.0])
        else:
            step = (hi - lo) / (levels - 1)
            axes.append([lo + i * step for i in range(levels)])

    total_points = 1
    for axis in axes:
        total_points *= len(axis)

    x0 = {name: axis[0] for name, axis in zip(names, axes)}
    seen: Dict[str, set] = {name: set() for name in names}

    best_params: Optional[Dict[str, float]] = None
    best_loss = float("inf")
    n_evals = 0
    truncated = False
    for combo in itertools.product(*axes):
        if n_evals >= max_evals:
            truncated = True
            break
        params = dict(zip(names, combo))
        loss = _evaluate(objective, params, f"grid evaluation #{n_evals + 1}")
        n_evals += 1
        for name, value in params.items():
            seen[name].add(value)
        if loss < best_loss:
            best_loss = loss
            best_params = params

    if best_params is None:
        # space was empty — evaluate the empty point once so callers get
        # a well-formed result instead of a crash.
        best_params = {}
        best_loss = _evaluate(objective, best_params, "grid evaluation of the empty space")
        n_evals = 1
        return _SearchOutcome(
            best_params, best_loss, n_evals, True,
            "empty space: one evaluation, nothing to enumerate", {},
        )

    if truncated:
        untried = [
            name for name, axis in zip(names, axes)
            if len(seen[name]) < len(axis)
        ]
        reason = (
            f"max_evals before full grid: {n_evals}/{total_points} grid "
            f"points evaluated"
        )
        if untried:
            reason += f"; dimensions never fully varied: {sorted(untried)}"
        return _SearchOutcome(best_params, best_loss, n_evals, False, reason, x0)

    return _SearchOutcome(
        best_params, best_loss, n_evals, True,
        f"full grid enumerated ({n_evals}/{total_points} points)", x0,
    )


def _coordinate_descent_fallback(
    objective: ObjectiveFn,
    space: Dict[str, Tuple[float, float]],
    max_evals: int,
    seed: int,
) -> _SearchOutcome:
    """Pure-python Hooke-Jeeves-style pattern search — used for
    ``method="nelder-mead"`` when scipy is not importable.

    ``converged`` means the step size shrank below ``1e-3`` of each
    dimension's range, i.e. the search stopped because it stopped
    improving. Running out of ``max_evals`` with a live step size is
    not convergence.
    """
    names = list(space)
    rng = random.Random(seed)
    x0 = {n: (lo + hi) / 2.0 for n, (lo, hi) in space.items()}
    current = dict(x0)
    best_loss = _evaluate(objective, current, "coordinate-descent start point")
    n_evals = 1
    step_frac = 0.25  # fraction of each dimension's range, shrinks over time
    min_step_frac = 1e-3

    while n_evals < max_evals and step_frac > min_step_frac:
        improved = False
        order = names[:]
        rng.shuffle(order)
        for name in order:
            if n_evals >= max_evals:
                break
            lo, hi = space[name]
            step = step_frac * (hi - lo)
            for sign in (+1.0, -1.0):
                if n_evals >= max_evals:
                    break
                trial = dict(current)
                trial[name] = min(max(current[name] + sign * step, lo), hi)
                loss = _evaluate(
                    objective, trial,
                    f"coordinate-descent evaluation #{n_evals + 1} "
                    f"(dimension {name!r})",
                )
                n_evals += 1
                if loss < best_loss:
                    best_loss = loss
                    current = trial
                    improved = True
        if not improved:
            step_frac *= 0.5

    converged = step_frac <= min_step_frac
    if converged:
        reason = (
            f"step size shrank to {step_frac:.2e} of each dimension's range "
            f"(<= {min_step_frac:g}): no further local improvement"
        )
    else:
        reason = (
            f"max_evals exhausted ({n_evals}/{max_evals}) with step size "
            f"still at {step_frac:.2e} of each dimension's range — the "
            f"search was still moving when the budget ran out"
        )
    return _SearchOutcome(current, best_loss, n_evals, converged, reason, x0)


def _nelder_mead_scipy(
    objective: ObjectiveFn,
    space: Dict[str, Tuple[float, float]],
    max_evals: int,
    seed: int,
) -> _SearchOutcome:
    import numpy as np
    from scipy.optimize import minimize

    names = list(space)
    lows = [space[n][0] for n in names]
    highs = [space[n][1] for n in names]
    x0 = [(lo + hi) / 2.0 for lo, hi in zip(lows, highs)]

    # Explicit initial simplex, sized as 10% of each dimension's bound
    # range. scipy's default simplex step is 0.00025 for any coordinate
    # that starts at (or very near) zero — and x0 is the bounds
    # midpoint here, which is exactly zero for any symmetric range —
    # producing a near-degenerate simplex that stalls convergence for
    # many evaluations before it expands enough to matter. Sizing off
    # the range instead of the coordinate value sidesteps that
    # regardless of where x0 sits.
    n = len(names)
    simplex = [list(x0)]
    for i in range(n):
        vertex = list(x0)
        span = highs[i] - lows[i]
        step = span * 0.1 if span > 0 else 0.1
        moved = min(max(vertex[i] + step, lows[i]), highs[i])
        if moved == vertex[i]:  # clipped to the same point at an upper bound
            moved = min(max(vertex[i] - step, lows[i]), highs[i])
        vertex[i] = moved
        simplex.append(vertex)

    count = {"n": 0}

    def _wrapped(x: "np.ndarray") -> float:
        # No clipping here: `bounds=` below makes scipy keep every
        # trial point inside the box itself. Clipping in the wrapper
        # instead would hand scipy a loss measured at a *different*
        # point than the one it asked about, which quietly flattens the
        # objective along every bound.
        params = dict(zip(names, (float(v) for v in x)))
        count["n"] += 1
        return _evaluate(objective, params, f"scipy Nelder-Mead evaluation #{count['n']}")

    result = minimize(
        _wrapped, x0=np.array(x0, dtype=float), method="Nelder-Mead",
        bounds=list(zip(lows, highs)),
        options={
            "maxfev": max_evals, "xatol": 1e-4, "fatol": 1e-6,
            "initial_simplex": np.array(simplex, dtype=float),
        },
    )
    best_params = dict(zip(names, (float(v) for v in result.x)))
    return _SearchOutcome(
        best_params=best_params,
        best_loss=float(result.fun),
        n_evals=count["n"],
        converged=bool(result.success),
        termination_reason=str(result.message),
        x0=dict(zip(names, x0)),
    )


def _scipy_available() -> bool:
    """Probe scipy/numpy on their own, before any objective runs.

    Deliberately separate from the search call. Wrapping the search in
    ``except ImportError`` would relabel an ``ImportError`` raised
    *inside the caller's objective* as "scipy is not available" and
    silently re-run the whole search under a different method — the
    report would then name a method that did not produce its numbers.
    """
    try:
        import numpy  # noqa: F401
        import scipy.optimize  # noqa: F401
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def optimize_parameters(
    objective: ObjectiveFn,
    space: Dict[str, Tuple[float, float]],
    method: str = "nelder-mead",
    max_evals: int = 50,
    seed: int = 42,
    held_out_objective: Optional[ObjectiveFn] = None,
    formula_version: Optional[str] = None,
) -> OptimizeResult:
    """Search ``space`` for the parameters minimising ``objective``.

    Parameters
    ----------
    objective : callable
        ``(flat_params: Dict[str, float]) -> float``. Lower is better,
        and must be finite — a NaN or inf return raises ``ValueError``
        at the evaluation site rather than being carried into a
        comparison.
    space : dict
        Flat ``{param_name: (low, high)}``. Numeric-only — a key that
        looks like a prompt/template path raises ``ValueError`` (an
        advisory guard; see module docstring). Use :func:`flatten_dict`
        first if your parameters are nested.
    method : "nelder-mead" or "grid"
        ``"nelder-mead"`` uses scipy when available, else a
        pure-python coordinate-descent fallback (both named in the
        result). ``"grid"`` is always pure python.
    max_evals : int
        Cap on objective evaluations. Recorded on the result next to
        ``n_evals`` so a reader can see whether the budget bound the
        search.
    seed : int
        Determinism for the fallback search's step ordering. Grid
        search and scipy's Nelder-Mead are themselves deterministic
        given ``x0``/the grid, but ``seed`` is still recorded on the
        result for reproducibility.
    held_out_objective : callable, optional
        If given, evaluated once on the best in-sample parameters
        after the search converges. Its value is reported as
        ``held_out_distance`` — never used to select parameters.
    formula_version : str, optional
        Recorded verbatim on the result. Supply it whenever the
        objective is derived from a plausibility formula (EPI and
        friends) that has more than one implementation, so the number
        is never read detached from the formula that produced it.

    Returns
    -------
    OptimizeResult
        Including ``converged`` + ``termination_reason``, ``x0``, and
        ``search_moved`` — check the last one before describing the
        result as a calibration.
    """
    _assert_non_prompt_space(space)
    if method not in ("nelder-mead", "grid"):
        raise ValueError(f"method must be 'nelder-mead' or 'grid'; got {method!r}")
    if max_evals < 1:
        raise ValueError(f"max_evals must be >= 1; got {max_evals}")

    if not space:
        loss = _evaluate(objective, {}, "evaluation of the empty space")
        result = OptimizeResult(
            best_params={}, best_loss=loss, n_evals=1,
            method=f"{method} (empty space)", converged=True, seed=seed,
            termination_reason="empty space: nothing to search",
            max_evals=max_evals, x0={}, search_moved=False,
            in_sample_distance=loss, formula_version=formula_version,
        )
        if held_out_objective is not None:
            result.held_out_distance = _evaluate(
                held_out_objective, {}, "held-out evaluation of the empty space",
            )
        return result

    if method == "grid":
        outcome = _grid_search(objective, space, max_evals)
        method_name = "grid"
    elif _scipy_available():
        outcome = _nelder_mead_scipy(objective, space, max_evals, seed)
        method_name = "nelder-mead (scipy)"
    else:
        logger.info(
            "scipy/numpy not importable; falling back to pure-python "
            "coordinate descent for method='nelder-mead'"
        )
        outcome = _coordinate_descent_fallback(objective, space, max_evals, seed)
        method_name = "nelder-mead (pure-python fallback)"

    search_moved = (
        set(outcome.best_params) != set(outcome.x0)
        or any(outcome.best_params[k] != outcome.x0[k] for k in outcome.x0)
    )

    result = OptimizeResult(
        best_params=outcome.best_params, best_loss=outcome.best_loss,
        n_evals=outcome.n_evals, method=method_name,
        converged=outcome.converged,
        termination_reason=outcome.termination_reason,
        max_evals=max_evals, x0=outcome.x0, search_moved=search_moved,
        seed=seed, in_sample_distance=outcome.best_loss,
        formula_version=formula_version,
    )
    if not search_moved:
        logger.warning(
            "%s: %s (best_params == x0 = %s, best_loss=%s) — the reported "
            "parameters are the ones the search started from",
            method_name, _NO_MOVE_WARNING, outcome.x0, outcome.best_loss,
        )
    if held_out_objective is not None:
        result.held_out_distance = _evaluate(
            held_out_objective, outcome.best_params,
            "held-out evaluation at the best in-sample parameters",
        )
    return result
