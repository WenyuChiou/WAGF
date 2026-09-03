# Calibration: what exists, two EPI formulas, and how to search parameters

## What this is, in one paragraph

WAGF has always had machinery for comparing a simulation's aggregate
behaviour against empirical benchmarks and reporting a single
plausibility number, EPI (Empirical Plausibility Index) — "what
fraction of the benchmarks we checked landed inside the empirically
plausible range, weighted by how much each one matters." What it did
NOT have, until PR-7, was anything that *searched* for parameters that
raise that number. This guide covers both halves: the benchmark
comparison machinery (`broker/calibration/`) and the numeric optimizer
built on top of it (`broker/calibration/optimize.py`).

## Where the code lives now

| Path | What's there | Water-domain content |
|---|---|---|
| `broker/calibration/benchmark_registry.py` | `Benchmark`, `BenchmarkRegistry`, EPI comparison, `band_distance` / `midpoint_distance` | None — benchmark definitions are 100% caller-supplied |
| `broker/calibration/calibration_protocol.py` | `CalibrationProtocol` — a 3-stage pilot/sensitivity/full diagnostic loop | None |
| `broker/calibration/directional_validator.py` | `DirectionalValidator`, `chi_squared_test`, `mann_whitney_u` | None |
| `broker/calibration/optimize.py` | `optimize_parameters`, `split_targets` — new in PR-7 | None |
| `broker/calibration/benchmark_diff.py` | `diff_benchmark_tables` — lists where two benchmark tables disagree | None |
| `broker/domains/water/calibration/{benchmark_registry,calibration_protocol,directional_validator}.py` | Deprecated re-export shims (`DeprecationWarning` on import) | N/A — same objects as above |
| `broker/domains/water/calibration/{micro_validator,distribution_matcher,temporal_coherence,psychometric_*,validation_router,cv_runner,conservatism_diagnostic}.py` | Everything else in the C&V framework — stayed put | Real: PMT label scales, flood action-name defaults, `posthoc_keywords` imports (see below) |

Why the split landed where it did: `benchmark_registry.py`,
`calibration_protocol.py`, and `directional_validator.py` had zero
water tokens in them before this PR — every "flood" or "insurance"
mention was a docstring example, not a hardcoded default. Everything
else in the old `broker/domains/water/calibration/` package has a real
coupling: `micro_validator.py` imports `TA_KEYWORDS` / `CA_KEYWORDS`
from `broker.domains.water.posthoc_keywords`; `conservatism_diagnostic.py`
hardcodes flood action-name sets (`STRONG_ACTIONS`,
`PROTECTIVE_ACTIONS`); `validation_router.py` and `temporal_coherence.py`
carry the PMT 5-level ordinal scale as a real default, not an example.
Moving those would either drag water-domain code into a "generic"
namespace or need a larger surgical split than this PR's scope — they
stay put, and `broker/tests/test_framework_invariants.py::TestDomainGenericity`
enforces the boundary by scanning every non-water, non-test subtree of
`broker/` for a fixed list of domain tokens.

## Two EPI formulas — read this before reporting a number

Two implementations compute something called "EPI" from the same kind
of input (observed rate -> benchmark range -> weighted pass rate), and
they do not agree:

| | `broker.calibration.benchmark_registry.BenchmarkRegistry.compare` (`legacy_epi_v1`) | `validation.metrics.l2_macro.compute_l2_metrics` (paper3 — **the one that actually produced every published number**) |
|---|---|---|
| Range check | Tolerance-expanded: `[low*(1-tol), high*(1+tol)]`, `tol=0.3` default | Hard: `[low, high]`, no expansion |
| Observed value | Used as-is | Rounded to 4 decimal places first |
| Where it lives | `broker/calibration/` (generic, caller supplies benchmarks) | `examples/multi_agent/flood/paper3/analysis/validation/` (flood-specific, hardcoded `EMPIRICAL_BENCHMARKS`) |
| Benchmark constants | `examples/multi_agent/flood/paper3/analysis/empirical_benchmarks.FLOOD_BENCHMARKS` | `validation.benchmarks.flood.EMPIRICAL_BENCHMARKS` |

Both formulas now stamp their output. `BenchmarkReport.formula_version`
is `"legacy_epi_v1"`; `L2Metrics.formula_version` (paper3) is
`"paper3_l2_hard_range_v1"` and rides through `asdict()` into
`validation_report.json` and `l2_macro_metrics.json`, so a saved
artifact says which formula produced its number instead of leaving it
to be inferred from the file's path.

## The two benchmark TABLES also disagree — on six ranges

Separate from the formula, and worse: **the two benchmark constant sets
give different ranges for the same metric.** Even with the formula
fixed, the two paths are not interoperable, because they are not
checking against the same claim.

| Metric | `FLOOD_BENCHMARKS` (registry side) | `EMPIRICAL_BENCHMARKS` (paper3 side) |
|---|---|---|
| `insurance_rate` / `insurance_rate_sfha` | [0.30, 0.50] | [0.30, 0.60] |
| `insurance_rate_all` | [0.15, 0.40] | [0.15, 0.55] |
| `elevation_rate` | [0.03, 0.12] | [0.10, 0.35] |
| `buyout_rate` | [0.02, 0.15] | [0.05, 0.25] |
| `mg_adaptation_gap` | [0.10, 0.30] | [0.05, 0.30] |
| `insurance_lapse_rate` | [0.05, 0.15] | [0.15, 0.30] |
| `do_nothing_rate_postflood` | [0.35, 0.65] | [0.35, 0.65] — agree |
| `rl_uninsured_rate` / `renter_uninsured_rate` | [0.15, 0.40] | [0.15, 0.40] — agree |

Two of those rows are also **name** mismatches: `insurance_rate` vs
`insurance_rate_sfha`, and `rl_uninsured_rate` vs
`renter_uninsured_rate`. Without an explicit alias declaring them
synonyms, a comparison sees four separate metrics, two per table, and
the range disagreement on the first pair stays invisible entirely.

Gaps like `elevation_rate` are not rounding: [0.03, 0.12] and
[0.10, 0.35] barely overlap, so the same simulated elevation rate can
be "plausible" against one table and "implausibly low" against the
other.

**This PR does not reconcile them.** Which range is right is a
judgement about the literature and belongs to a human. What it does is
make the disagreement enumerable so it cannot go quiet:

- `broker/calibration/benchmark_diff.py` — `diff_benchmark_tables(left,
  right, aliases=...)` returns every range disagreement, weight
  disagreement, and unmatched name, and renders them as a markdown
  table. It has no opinion about which names are synonyms; the caller
  declares that, because it is domain knowledge.
- `broker/tests/test_calibration_pr7.py::TestBenchmarkTablesDisagree`
  pins the table above. Change either constant set and that test fails
  with the new diff printed, rather than the disagreement silently
  shifting.
- Every `calibration_result.json` records `benchmark_source` (the
  module path of the table used) plus per-metric `rate_low`,
  `rate_high`, `weight` and `tolerance`, and the parametric script
  prints the table it used on stdout.

Anyone quoting "EPI = 0.7" without saying which formula produced it and
which benchmark table it used has not said anything checkable.

### The difference, computed on a shared fixture

Same 5 metrics, same observed values, same `(range, weight)`
definitions (pulled from `EMPIRICAL_BENCHMARKS` for both, so this
table isolates the *formula* difference — not the separate
benchmark-constant disagreement above):

| Metric | Observed | Range | Weight | Hard-range pass? | Tolerance-expanded pass? |
|---|---|---|---|---|---|
| `insurance_rate_all` | 0.42 | [0.15, 0.55] | 0.8 | yes | yes |
| `elevation_rate` | 0.07 | [0.10, 0.35] | 1.0 | **no** | **yes** (band widens to [0.07, 0.455]) |
| `buyout_rate` | 0.03 | [0.05, 0.25] | 0.8 | no | no |
| `do_nothing_rate_postflood` | 0.55 | [0.35, 0.65] | 1.5 | yes | yes |
| `mg_adaptation_gap` | 0.12 | [0.05, 0.30] | 2.0 | yes | yes |

- `compute_l2_metrics` (hard range, paper3): **EPI = 0.7049** (3/5 pass, weighted)
- `BenchmarkRegistry.compare` (tolerance-expanded, `legacy_epi_v1`): **EPI = 0.8689** (4/5 pass, weighted)

`elevation_rate = 0.07` is the swing metric: it sits exactly on the
tolerance-expanded lower bound (`0.10 * (1 - 0.3) = 0.07`) but outside
the hard range, so the same observation counts as a pass under one
formula and a fail under the other. This is not a rounding artifact —
0.164 of EPI is a real disagreement. Pinned by
`broker/tests/test_calibration_pr7.py::TestTwoEpiFormulas`; re-derive
it with `examples/multi_agent/flood/paper3/analysis` and
`broker/calibration/benchmark_registry.py` on the path (see the test
for the exact fixture construction) if this ever needs to be checked
again.

### What to do about it

- **Reporting a Paper 3 number**: use `compute_l2_metrics` — it is the
  formula that ran. Cite `formula_version` if you print the generic
  registry's output anywhere near it.
- **New domain, new benchmarks**: use `broker.calibration.benchmark_registry.BenchmarkRegistry`
  directly. Its `BenchmarkReport.formula_version` field is always
  `"legacy_epi_v1"` — carry it alongside any EPI number your domain
  reports, so a reader six months later can tell which formula
  produced it without re-deriving this table.
- **Do not** average, difference, or otherwise combine an EPI number
  from one formula with one from the other. They are not the same
  measurement.

## `CalibrationProtocol` is not an optimizer

`broker.calibration.calibration_protocol.CalibrationProtocol` runs a
3-stage pilot / sensitivity / full loop, but its pilot stage
(`_run_pilot`) varies only the RNG seed across iterations — it
generates `AdjustmentRecommendation` objects (human-readable text: "the
simulated X is below range, consider adjusting Y") but never feeds
them back into `simulate_fn`'s `config_overrides`. Nothing in it
searches parameter space; it is a diagnostic loop that tells a human
what changed and leaves the next move to them, by design (see its
"Human-in-the-loop" principle). `CalibrationProtocol`,
`DirectionalValidator`, `SwapTest`, and `DirectionalTest` all have zero
production call sites as of this PR — grep the repo for
`CalibrationProtocol(` outside `tests/` and `calibration_hooks.py`'s
docstring usage example and you will find none. `chi_squared_test` from
`directional_validator.py` is the one symbol with a live call site
(`examples/multi_agent/flood/paper3/analysis/persona_sensitivity.py`
and `prompt_sensitivity.py`).

Two of its defaults deserve naming, because both used to describe one
flood experiment while sitting in generic code:

- `CalibrationConfig.framework` was `"pmt"`. A run in any other domain
  reported `framework: pmt` in its metadata and looked like a
  deliberate choice. It is now `Optional[str] = None` — written through
  to the report as `None`, the honest "nobody said" — and any path that
  needs the name calls `config.require_framework(purpose)`, which
  raises instead of guessing.
- `FullConfig` still defaults to `n_agents=400, n_years=13, n_seeds=10`,
  which are the Paper 3 multi-agent flood run's dimensions, not neutral
  values. They are kept because
  `tests/test_calibration_protocol.py::test_full_config_defaults` pins
  400 and 10, and silently redefining what an existing test asserts is
  worse than an honest docstring. A new domain should pass its own
  numbers rather than inherit these.

## The optimizer: `broker.calibration.optimize`

`optimize_parameters(objective, space, method="nelder-mead"|"grid",
max_evals, seed) -> OptimizeResult` — a numeric search over a flat
`{param_name: value}` dict.

- **`objective`**: `Dict[str, float] -> float`, lower is better, and
  must be finite — a NaN or inf return raises `ValueError` at the
  evaluation site (a NaN loses every `<` comparison, so a search that
  tolerates one reports a "best" point it never measured, with
  `converged: true` and a bare `NaN` in the JSON). **Do not pass
  `1 - EPI`** — see "Choosing an objective" below.
- **`space`**: `Dict[str, (low, high)]`. **Numeric-only** — a key
  containing `prompt`, `template`, `system_message`, or `persona_text`
  raises `ValueError`. This is an *advisory guard against accidental
  inclusion*, not a security boundary: it matches on the key's name, so
  renaming a key sidesteps it. It catches the real case — somebody
  flattens a whole config dict and prompt paths come along unnoticed.
  Worth catching because automatically rewriting what an agent is
  *told* is a different, higher-stakes change than tuning a decision
  threshold, and prompt calibration stays human-reviewed everywhere
  else in this stack (`CalibrationProtocol` only ever recommends prompt
  text, never applies it — see above). If a domain's calibration
  surface legitimately mixes prompt and non-prompt parameters, split
  them: search the numbers here, hand-edit the words.
- **`method`**: `"nelder-mead"` uses `scipy.optimize.minimize` when the
  `analysis` extra is installed, else a pure-python coordinate-descent
  (Hooke-Jeeves) fallback — `OptimizeResult.method` always names which
  one actually ran (`"nelder-mead (scipy)"` vs `"nelder-mead
  (pure-python fallback)"`), so a report never silently claims a search
  method that did not execute. `"grid"` is always pure python.
- **Held-out validation**: `split_targets(targets, holdout_fraction,
  seed) -> TargetSplit` splits a `{metric_name: target_value}` dict
  deterministically (metric-name-level, not per-row — WAGF calibration
  targets are population rates, not observations). Pass a
  `held_out_objective` built from the held-out half to
  `optimize_parameters`, and `OptimizeResult` reports both
  `in_sample_distance` and `held_out_distance` — the point is not that
  held-out always improves (with a handful of correlated metrics it
  need not), it is that a calibration report can say what happened out
  of sample instead of only in it.

  `split_targets` **refuses** a split in which a held-out value is
  bit-identical to an in-sample value. Two metric names carrying one
  number are one measurement wearing two labels: fitting the in-sample
  twin lands exactly on the "held-out" one, so the out-of-sample figure
  measures nothing. Pass `observed=` (the values the model produces at
  the starting parameters) to run the same check on the model side,
  which is where aliasing usually starts — one estimator assigned to
  two metric keys. Every `TargetSplit` records
  `held_out_disjoint_check: "passed"` and whether the observed side was
  checked.

### Reading a result: did the search actually do anything?

`OptimizeResult` carries four facts that together decide whether a
number is a calibration or a no-op, all serialised by `to_dict()`:

| Field | Why it is there |
|---|---|
| `converged` + `termination_reason` | `converged` used to be `n_evals <= max_evals`, which is true by construction. It now means what it says: for `grid`, the full grid was enumerated (and if not, the reason names the dimensions the budget never varied); for the pure-python fallback, the step size shrank below `1e-3` of each range; for scipy, `result.success` with scipy's own message. |
| `n_evals` / `max_evals` | Whether the budget bound the search. |
| `x0` | Where the search started (the bounds midpoint for Nelder-Mead and its fallback; the first grid corner for `grid`). |
| `search_moved` + `warning` | `False` means `best_params == x0`: the reported parameters are the ones the search began with. Legitimate (the start may already be optimal) but never a calibration, so `warning` says `"search never left its starting point"` in the JSON and the CLI prints it. |

### Choosing an objective: EPI is a pass rate

`plausibility_score` (EPI) counts how many benchmarks landed inside
their band, weighted. Over four or five benchmarks it can take four or
five values, so `1 - EPI` is a staircase — flat almost everywhere, with
no information about which way to move a parameter until some metric
crosses a bound. A search handed it returns wherever it started, and
the report says "distance 0.615 → 0.0" as if something happened. That
is exactly what the first version of the parametric example did.

`BenchmarkReport` provides two continuous quantities instead:

| Quantity | Per metric | Use it for |
|---|---|---|
| `band_distance` | How far *outside* the tolerance-widened band, in band widths. `0.0` inside. | **Reporting.** It says by how much a failing metric failed. Not a search objective: flat across the whole band interior, so a search that reaches the band stops learning. |
| `midpoint_distance` | Distance from the centre of the *published* range, in half-ranges. `1.0` on a published bound. Tolerance-independent. | **Searching.** A gradient everywhere. |

One caveat on `midpoint_distance`, and it matters: a benchmark states a
**range**, so every point inside that range is equally supported by its
source. Driving this number toward zero picks the most central of the
acceptable points — a tie-break that makes the search well-posed. It is
not evidence that the centre is more correct than a point near a bound.
Report `band_distance` and the pass rate for the plausibility claim.

### CLI

```
python -m broker.tools.calibrate \
    --objective-module examples.my_domain.calib:objective \
    --space '{"base_rates.owner": [0.0, 1.0]}' \
    --formula-version legacy_epi_v1 \
    --method nelder-mead --max-evals 50 --out results/calibration/
```

Thin wrapper — imports the objective(s) you name, parses `--space`
(inline JSON or a path to a JSON file), runs the search, writes
`optimize_result.json`. See `broker/tools/calibrate.py`'s docstring for
the full flag list.

**Naming the formula.** Because two implementations here compute an
"EPI" and disagree, the CLI refuses to write a result whose objective
is plausibility-derived but unnamed. The contract:

- an objective module exports `FORMULA_VERSION = "..."` and the CLI
  reads it — this is the intended path (see
  `examples/multi_agent/flood/parametric/calibrate_parametric.py`);
- `--formula-version` overrides it from the command line;
- "plausibility-derived" is detected explicitly: the module sets
  `EPI_DERIVED = True`, or its namespace holds a name imported from
  `broker.calibration.benchmark_registry`. An objective with no
  benchmark machinery in it — a plain distance to targets — needs no
  version and is written as usual.

### The first workload: the parametric flood decider

`examples/multi_agent/flood/parametric/calibrate_parametric.py` is a
complete, runnable, no-LLM example: it searches
`parametric_decider.PARAMETRIC_CALIBRATION["base_rates"]` (four
numbers) against `paper3.analysis.empirical_benchmarks.FLOOD_BENCHMARKS`,
using a closed-form aggregate-rate estimator (`aggregate_rates`) in
place of a full multi-year ABM run — deliberately a fast smoke-level
demonstration of the optimizer + held-out machinery, not a
recalibration of the real Paper 3 decider (which has per-agent TP/CP
dynamics this simplified surface does not model). Run it:

```
python examples/multi_agent/flood/parametric/calibrate_parametric.py --out <dir>
```

A real run (seed 42, default 400-evaluation budget,
`nelder-mead (scipy)`, 0.05 s), on the three in-sample metrics
`buyout_rate` / `elevation_rate` / `insurance_rate_all` with
`insurance_rate` held out:

| | before | after |
|---|---|---|
| in-sample midpoint distance (the objective) | 1.0370 | 0.3215 |
| held-out midpoint distance | 2.2988 | 1.5762 |
| in-sample band distance | 0.0116 | 0.0 |
| held-out band distance | 0.0906 | 0.0 |
| in-sample EPI pass rate | 0.3846 | 1.0 (3/3) |
| held-out EPI pass rate | 0.0 | 1.0 (1/1) |

`insurance_rate` (the held-out metric) finishes at 0.2424 — below its
own published lower bound of 0.30, and inside the widened band
`[0.21, 0.65]` only because `tolerance=0.3` stretches it that far. Read
"held-out EPI pass rate 0.0 → 1.0" as true under widening, not as the
observed rate having landed inside the literature's own range.

`converged: true`, `search_moved: true`, 253 of 400 evaluations used.
The four base rates come out at 0.391 / 0.062 / 0.160 / 0.599 — the
zone×tenure structure survives, in the sense that the four numbers stay
distinct. Their *ordering* does not survive: the search puts
non-flood-prone renters (0.599) well above flood-prone renters (0.062),
which is behaviourally backwards. Three aggregate in-sample metrics do
not identify four base rates, so a wide set of combinations satisfies
the bands equally well and the search returns one of them. Read the
result as "these bands are satisfiable", not as an estimate of the
four rates.

Two findings worth carrying, both visible only because the result now
reports enough to see them:

- **The band distance cannot be the objective here.** With
  `band_distance` as the loss the search reports `search_moved: false`:
  the starting point (the bounds midpoint, 0.4505 on all four
  parameters) already sits inside every widened band, so the loss is
  0.0 there and no move can improve it. The midpoint distance is used
  instead, for exactly that reason.
- **Held-out shows overfitting when the budget is raised.** At a
  40-evaluation budget the search stops early with in-sample 0.491 and
  held-out **0.397**; run to convergence at 253 evaluations, in-sample
  improves to 0.321 while held-out gets **worse**, 1.576. Fitting three
  aggregate rates harder moves the fourth away. That is what the
  held-out number is for.

### How to read `calibration_result.json`

| Field | Meaning |
|---|---|
| `params_before` / `params_after` / `x0` | The numeric surface as shipped, at the search's best point, and at the point the search started from |
| `search_moved` | `false` means `params_after == x0` — the search returned its starting point. A `warning` field appears alongside it |
| `converged` / `termination_reason` / `n_evals` / `max_evals` | Whether the search finished, why it stopped, and whether the budget bound it |
| `objective` | `kind`, a plain-words `definition`, the `tolerance`, and what a `0.0` does and does not claim |
| `benchmark_source` | Module path of the benchmark table used — the two tables in this repo disagree on six ranges (see above) |
| `in_sample_metrics` / `held_out_metrics` | Which benchmark metrics were searched against vs. held out (from `split_targets`) |
| `held_out_disjoint_check` / `disjoint_check_used_observed` | That no held-out value duplicates an in-sample one, and whether the model's own outputs were checked too |
| `in_sample_midpoint_distance_before` / `_after` | The objective the search minimised, on the in-sample metrics |
| `held_out_midpoint_distance_before` / `_after` | The same quantity on metrics the search never saw — `null` if no held-out objective was given |
| `in_sample_band_distance_*` / `held_out_band_distance_*` | The plausibility statement: how far outside the widened band, in band widths. `0.0` = inside |
| `epi_pass_rate_in_sample_*` / `epi_pass_rate_held_out_*` | The weighted pass rate. Reported, never optimised against |
| `n_benchmarks_evaluated_*` / `n_within_range_*` | The counts behind those pass rates |
| `benchmarks` | Per metric: published range, weight, tolerance, widened band, observed before/after, both distances before/after, and pass/fail |
| `formula_version` | Which EPI convention the bands and pass rate use (always check before comparing to another report) |
| `method` | Which search actually ran, e.g. `"nelder-mead (scipy)"` |

## Known aliasing this PR did NOT fix

`examples/multi_agent/flood/paper3/analysis/calibration_hooks.py:87`
sets `rates["insurance_rate_all"] = rates["insurance_rate"]` on the
real-ABM metric path — the flood-prone-only rate and the all-zone rate
emitted as one number under two names. The equivalent bug in
`parametric/parametric_decider.py` is fixed (the prone-only rate is now
accumulated over flood-prone households only); `calibration_hooks.py`
is out of this PR's scope and still aliases them.

Consequence, in plain terms: on the real-ABM path those two metrics
**cannot be used as an in-sample / held-out pair**, and their two EPI
contributions are one measurement double-counted with different
weights. `split_targets(..., observed=...)` will now refuse such a
split outright if you pass it the observed rates, which is the
intended way to notice.

## Refusal protocol

This machinery will not:

- Report an EPI number without a `formula_version` attached — and the
  CLI refuses to *write* a result whose objective is
  plausibility-derived but unnamed.
- Search a parameter whose name looks like a prompt or template path —
  `optimize_parameters` raises `ValueError` rather than silently
  including it. (Advisory: it matches names, so it catches accidents,
  not intent.)
- Claim a search method it did not run — `OptimizeResult.method` always
  names the actual execution path (scipy vs. pure-python fallback), and
  scipy availability is probed separately from the search so an
  `ImportError` from inside your objective is never relabelled "scipy
  is missing".
- Report a non-finite best: a NaN or inf loss raises `ValueError` at
  the evaluation that produced it.
- Call a search converged because it stayed inside its budget —
  `converged` names a real stopping condition, and
  `termination_reason` says which.
- Describe a search that never moved as a calibration —
  `search_moved: false` carries a `warning` field and a printed
  warning.
- Hold out a metric that duplicates an in-sample one — `split_targets`
  raises rather than reporting a meaningless out-of-sample number.
- Claim out-of-sample validation without a number: `held_out_distance`
  is `None` unless a `held_out_objective` was supplied and evaluated.
