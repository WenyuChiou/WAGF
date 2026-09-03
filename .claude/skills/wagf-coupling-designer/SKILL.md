---
name: wagf-coupling-designer
description: Walk a researcher through designing the LLM-external-model interface for a WAGF domain using the v0.6 coupling layer. Use when the user says "I want to couple my LLM agents to <my simulator>", "help me design the WAGF interface", "scaffold the external model adapter", "draft a coupling contract", or "I have a Python / R / CSV / service model and want WAGF to drive it".
---

# WAGF: Coupling Designer

A WAGF agent that doesn't talk to anything is just an LLM chat. The
moment you bolt an external simulator on (hydrology, epi model, crop
yield, energy market, traffic, custom Python ABM), the interface
between the LLM-driven decision layer and the simulator becomes the
single biggest source of subtle bugs — unit mismatches, cadence
misalignment, silent NaN propagation, double-counted feedback.

This skill is the DESIGN-time counterpart to
`model-coupling-contract-checker`. The checker audits an existing
coupling for the seven known traps; this skill walks the researcher
through DRAFTING the contract before any code is written, then emits
templates that survive contact with the real model.

It is the back-end for `wagf-domain-builder` stages S2 / S3 / S7, but
also works standalone for users adding coupling to an existing WAGF
setup or swapping one external model for another.

**v0.6 design target**: do not hand-roll a private adapter contract.
Design into `broker.coupling.CouplingContract` + `VarSpec`. Units,
range, direction, type, cadence vocabulary, missing-value policy, and
double-count declarations are enforced at construction/runtime by the
coupling layer; the skill's job is to make the research semantics
explicit enough that those checks are meaningful.

## When to Use

Invoke this skill when the user says any of:

- "I want to couple my WAGF agents to <name of simulator>."
- "Help me design the WAGF ↔ <my model> interface."
- "Draft a coupling contract for <my domain>."
- "Scaffold the external model adapter for <my domain>."
- "I have a Python / R / CSV-based model — how do I wire it in?"
- "Swap the existing external model for a new one."

Do NOT use this skill for:

- Auditing an EXISTING coupling → `model-coupling-contract-checker`.
- Building a WAGF domain from scratch (no external model)
  → `wagf-domain-builder` (which may CALL this skill at S2/S3/S7).
- Debugging a coupling-related runtime error → `debugger`.
- Designing an experiment matrix on top of working coupling
  → `wagf-experiment-designer`.

## Scope (v0.6)

Start from `docs/COUPLING_CONNECTORS.md`, not from a blank adapter.
Pick one connector archetype and copy the matching worked example as
the starting skeleton:

- **A — BMI/CSDMS solver**: `BmiEventSource` for event-style coupling,
  or `ContinuousBundle` for K-sub-step control. Copy
  `examples/cat_model/` for the event path or
  `examples/reservoir_control/` for continuous control.
- **B — File replay**: copy the file-replay source pattern in
  `examples/cat_model/coupling_modules.py` and attach file provenance.
- **C — Service model**: SUBPROCESS is READY — copy
  `broker.coupling.SubprocessModelConnector`
  (`broker/coupling/subprocess_source.py`) and the worked example at
  `examples/coupling_examples/archetype_c_subprocess/` (JSON-on-stdin /
  JSON-on-stdout, one call per period, validates the reply against the
  contract, refuses a non-zero exit). REST is still DEFERRED (v2 — no
  first-party domain needs one yet; implement the EventSource surface
  around your HTTP client following the same shape if you need it before
  then). Either transport: `VarSpec.on_missing` only accepts `fail_loud`;
  retries/caches must live inside the source.
- **D — Another ABM / period-end exchange**: copy
  `examples/cat_model/run_cat_ma.py`. Accumulate intents during the
  period, settle shared state once at period end, and project the
  settlement into the next period.

Wire the result through
`ExperimentBuilder.with_coupling(contract, bundle, domain=...)`. The
feature must remain default-OFF through the two-layer flag:
`global_config.coupling.enable` in YAML first, then the DomainPack's
`coupling_enabled_default()` fallback.

### Multi-agent coupling: read this first

v0.6 has a worked multi-agent period-end pattern in
`examples/cat_model/run_cat_ma.py`; copy it rather than improvising
ordered `env` mutation. A multi-agent coupling returns per-agent
outcomes AND a shared-state update (insurance pool, budget,
common-pool resource) that loops back to every agent. That is exposure
point **E4 (multi-agent shared-state resolution)** and it requires an
order-independent, audited resolver.

If the user's target is multi-agent:

1. Draft the per-agent `VarSpec` observations/inputs first. E1, E2,
   E3 and E5 still apply per-agent; E4 adds the shared-state rule.
2. Copy the period-end settlement shape from
   `examples/cat_model/run_cat_ma.py` when shared state can be lagged
   to the next period.
3. Point them at the full taxonomy:
   `model-coupling-contract-checker/references/coupling_interaction_taxonomy.md`
   (E1–E5, disaster-model worked example, the multi-agent
   amplification column) and at
   `wagf-domain-builder/references/multi_agent_walkthrough.md` (the
   `self.env = env` dual-dict contract + the disaster-coupling worked
   example).
4. Do NOT pretend this skill made a same-period multi-agent loop safe.
5. Do NOT claim same-period feedback is supported by default. If the
   research question needs within-period reaction loops, flag it as a
   different framework regime.

## Inputs

Before C1 (contract drafting), the user must answer:

1. **Domain name** (lowercase snake_case; e.g. `crop_yield`).
2. **External model identity** — name and language/runtime (e.g.
   "SWAT in Fortran", "in-house Python ABM", "scikit-learn surrogate",
   "historical streamflow CSV").
3. **Decision variable(s)** the LLM controls per agent step.
4. **Output variable(s)** the model produces that feed back into the
   LLM context.
5. **Cadence** — LLM decision frequency (yearly typical) and model
   frequency (daily / monthly / per-decision / continuous).
6. **Reset semantics** — does the model carry state between agents /
   seeds, or is each call independent?

If any of (1)–(5) is missing, ask. Do not guess units, do not guess
cadence. Silent guesses are the v21 bug pattern.

## Workflow

The skill runs 5 stages. Each stage produces a concrete artifact;
verify the artifact exists before moving to the next stage.

### C0 — Pattern recognition (5 min)

Ask: "Which connector archetype in `docs/COUPLING_CONNECTORS.md` is
closest: (A) BMI/CSDMS solver, (B) file replay, (C) service model, or
(D) another ABM / period-end exchange?"

Record the chosen archetype and the copied skeleton path:
`examples/cat_model/`, `examples/cat_model/run_cat_ma.py`, or
`examples/reservoir_control/`. If none fits, stop and write down the
missing interface rather than inventing a fifth pattern.

Output: connector archetype and starting skeleton recorded in the
contract draft.

### C1 — Contract drafting (20 min)

Walk the user through filling in the template at
`templates/coupling_contract.md.tmpl`. Use
`references/contract_template.md` for narrative explanation of each
section, then translate the variable tables into `CouplingContract`
and `VarSpec` declarations in code.

For each section, ask only the questions that section requires —
don't dump the whole template on the user upfront.

For every variable, collect `name`, Python type, unit, physical range
(`lo`/`hi` where meaningful), direction (`world_to_agent` vs
`agent_to_world`), cadence, and whether it is the consumer of record.
Reference `references/units_audit_checklist.md` for the 8-10 common
unit traps.

For failure modes, force a per-mode answer (timeout / NaN / crash /
out-of-range). In v0.6 `VarSpec.on_missing` accepts ONLY
`"fail_loud"` — declaring `"last_good"` or `"quarantine"` RAISES at
construction (no runtime executor exists; the contract refuses
policies it cannot honour). Any reuse-last-good or retry behaviour
must be implemented INSIDE the user's source/bundle, where it is
visible and testable — never silently zero-fill.

Output: `.coupling/contract.md` in the user's domain root plus a
draft `_build_contract() -> CouplingContract` skeleton.

### C2 — Mock generator (15 min)

Copy the closest v0.6 worked example first. Use
`examples/cat_model/run_cat.py` for single-agent event coupling,
`examples/cat_model/run_cat_ma.py` for period-end multi-agent
settlement, or `examples/reservoir_control/run_reservoir_ops.py` for
continuous control / `ContinuousBundle`. Only use
`templates/mock_external_model.py.tmpl` when no shipped skeleton is
close enough.

The mock must:
- Accept the same INPUT keys the contract declares.
- Return the same OUTPUT keys.
- Generate values in plausible ranges (from contract).
- Be deterministic given a seed.

**Also emit the E1 temporal-sync assertion stub** (taxonomy E1 —
`model-coupling-contract-checker/references/coupling_interaction_taxonomy.md`).
The agent at step *t+1* must read the model outputs produced *for step
t*; today this rests on the `pre_year` `self.env = env` aliasing
convention with no framework guard (framework-enforced in Gate-3,
post-Paper-1b). Until then, paste this guard into the lifecycle hook so
a sync regression fails loudly instead of silently mis-training agents:

```python
# E1 temporal-sync guard (paste into pre_year, AFTER env.update + the
# `self.env = env` aliasing line). Replace OUTPUT_KEY/STAMP with a
# field the external model writes each step and the step it stamped.
def _assert_model_outputs_current(self, year):
    out = self.env.get("OUTPUT_KEY")
    stamped = self.env.get("OUTPUT_KEY_step")  # model writes this
    assert out is not None, (
        f"E1: model output OUTPUT_KEY missing at year {year} "
        f"(env-sync ordering bug — see coupling_interaction_taxonomy E1)"
    )
    assert stamped == year - 1 or stamped == year, (
        f"E1: agent at year {year} sees OUTPUT_KEY stamped for "
        f"step {stamped}, not the just-produced step "
        f"(stale-env / Paper-3 dual-dict class bug)"
    )
```

The mock's returned payload must include the `*_step` stamp so this
guard is exercisable from the very first smoke run.

Verify by running a 1-agent, 1-year smoke through WAGF that calls
the mock — no real model yet. The smoke is the dev-loop unblocker:
the user can iterate on prompts and validators while the real model
is still being wired in.

Output: a runner/bundle skeleton with scripted mock behavior and a
1-agent or minimum-agent smoke that exercises the coupling layer.

### C3 — Adapter scaffold (10-30 min, pattern-dependent)

Implement the connector chosen in C0 behind the v0.6 bundle/source
surface. For archetype A/B/D, start by copying the matching shipped
example named in C0. For a service model, keep the retry/cache policy
inside the source and let `CouplingViolation` surface unrecoverable
failures loudly.

The adapter MUST share the same input/output schema as the mock so
the rest of the WAGF wiring (lifecycle hooks, validators, prompt
context) doesn't change when swapping mock for real. In particular the
real adapter MUST keep emitting the `*_step` stamp the C2 E1 guard
checks — a real model that drops the stamp silently disables the
temporal-sync assertion.

Output: an InterfaceBundle/source implementation plus
`ExperimentBuilder.with_coupling(contract, bundle, domain=...)` wiring
guarded by `global_config.coupling.enable` /
`coupling_enabled_default()`.

### C4 — Loop validation + hand-off (10 min)

1. Run a 1-agent, 1-year smoke through WAGF using the REAL adapter
   (mock-vs-real divergence test).
2. Hand off to `model-coupling-contract-checker` for the audit pass
   — pass it the `.coupling/contract.md` from C1 and the adapter
   from C3.
3. Hand off to `wagf-experiment-designer` for the seeds × conditions
   matrix once coupling is GREEN.
4. (Pre-submission only) Hand off to `abm-reproducibility-checker`.

Output: GREEN coupling, ready for full experiment.

## Outputs

The user's domain repo will gain:

```
<user_domain_root>/
├── .coupling/
│   └── contract.md                  ← from C1
├── lifecycle_hooks.py               ← MockExternalModel from C2
└── adapters/
    └── external_model_adapter.py    ← from C3 (with TODOs)
```

The skill itself never edits `broker/`. DomainPack edits are limited
to explicit coupling defaults such as `coupling_enabled_default()`.

## Output structure contract

`.coupling/contract.md` MUST have these sections in this order (matching
`templates/coupling_contract.md.tmpl` exactly):

1. Title — `# Coupling contract: <domain> ↔ <external model>`
2. `## Scope` — domain, external model identity, lifecycle owner
3. `## Cadence` — agent step, model step, sync points
4. `## Inputs (agent -> model)` — table: variable / type / unit /
   range / mapping from skill_id
5. `## Input mapping notes` — narrative on how skill_id maps to input
   values, including any non-linear mapping logic
6. `## Outputs (model -> agent context)` — table: variable / type /
   unit / template placeholder / producer code path
7. `## Output visibility notes` — which outputs are surfaced to the
   LLM vs kept internal for diagnostics
8. `## Failure modes` — per-mode planned response (timeout, NaN,
   crash, missing-input, out-of-range)
9. `## Units audit checklist` — per-variable check, ticked or
   unchecked
10. `## Mock fidelity` — what the mock preserves vs the real model
11. `## Adapter scaffold` — which pattern (A-E) is used, which file
    holds the adapter
12. `## Smoke test` — the 1-agent, 1-year command used to verify the
    contract round-trip
13. `## Handoff to checker` — when to invoke
    `model-coupling-contract-checker` and what input it expects

Sections 2-13 map 1:1 to the template's `##` headers. The audit-time
sister skill `model-coupling-contract-checker` reads sections 1, 4, 6,
8, 9 directly during its schema diff pass; the other sections are
narrative for human readers and do not change the audit verdict.

## Refusal Protocol

The skill MUST refuse to:

1. **Guess units.** If the user says "8%", ask whether they mean 0.08
   (decimal) or 8 (whole percent). The v21 bug was a unit
   ambiguity that wasn't surfaced; this skill exists to prevent
   the next one.
2. **Skip the failure-mode questions.** "What happens if the model
   returns NaN?" must have an explicit answer before C3 starts.
   Default policy is fail-loudly; opt-out is intentional, never
   silent.
3. **Advance past C1 without a complete contract.** If any section
   in `.coupling/contract.md` is empty, stay in C1.
4. **Advance past C3 without running the mock smoke.** Mock-first is
   the design discipline; the user MUST see the WAGF pipeline run
   green with mock data before the real model is wired in.
5. **Pretend mock fidelity matches real-model fidelity.** Always
   state explicitly what the mock preserves (ranges, structure,
   determinism) and what it does NOT (true dynamics, real spatial /
   temporal autocorrelation, agent-action sensitivity).
6. **Invent a connector archetype.** If A/B/C/D in
   `docs/COUPLING_CONNECTORS.md` do not fit, stop and document the
   missing interface instead of writing an unreviewed pattern.
7. **Bypass the default-OFF flag.** Coupling must be enabled by
   `global_config.coupling.enable: true` or, absent that key, by an
   intentional `coupling_enabled_default()` override.

## Bundled resources

References (narrative / decision content):

- `references/coupling_patterns/README.md` — summary table of all 5
  patterns and when each fits.
- `references/coupling_patterns/A_file_replay.md` — full pattern doc
  for CSV / NetCDF replay.
- `references/coupling_patterns/B_python_library.md` — full pattern
  doc for in-process Python.
- `references/contract_template.md` — narrative explanation of each
  contract section, with worked examples from the WAGF reference
  domains.
- `references/units_audit_checklist.md` — 8-10 common unit traps
  with detection and fix recipes.
- `references/failure_mode_playbook.md` — planned responses to
  timeout, NaN, crash, missing-input, out-of-range failure modes.

Fallback templates (use only when no v0.6 worked example is close
enough):

- `templates/coupling_contract.md.tmpl` — the contract template with
  placeholder markers (`<<DOMAIN_NAME>>`, etc.).
- `templates/mock_external_model.py.tmpl` — deterministic Python
  mock that mirrors the contract's input/output schema.
- `templates/adapter_A_file_replay.py.tmpl` — legacy file-replay adapter
  scaffold (CSV + caching).
- `templates/adapter_B_python_library.py.tmpl` — legacy Python-library adapter
  scaffold (import + invoke).

## Hand-off rules

| When | Hand off to |
|---|---|
| Called from `wagf-domain-builder` at S2 (contract draft) | Stay in this skill through C1, return artifact + control |
| Called from `wagf-domain-builder` at S3 (mock build) | Stay through C2, return |
| Called from `wagf-domain-builder` at S7 (real-model cutover) | Stay through C3-C4, then hand off to checker + designer |
| Standalone, contract complete | Hand off to `model-coupling-contract-checker` at C4 for audit |
| Coupling GREEN, ready for experiment | Hand off to `wagf-experiment-designer` |
| Pre-submission | Hand off to `abm-reproducibility-checker` |

Do NOT hand off to `wagf-quickstart` (that's a different lifecycle
stage). Do NOT hand off to `llm-agent-audit-trace-analyzer` from C4 —
trace analysis is post-experiment, this skill stops before that.

## Acceptance criteria

The skill is ready when:

- For input "I have an in-house Python crop-yield model, yearly
  decisions, model takes fertilizer-pct and returns
  yield-tons-per-ha", produces a complete `.coupling/contract.md`,
  a `_build_contract() -> CouplingContract` skeleton with `VarSpec`
  declarations, and `ExperimentBuilder.with_coupling(...)` wiring.
- For input "I have a subprocess/CLI model", selects archetype C, points
  the user at `SubprocessModelConnector` + the
  `archetype_c_subprocess` worked example, keeps retry/cache logic
  inside the source, uses `VarSpec.on_missing="fail_loud"`, and documents
  provenance.
- For input "I have a REST/service model", selects archetype C, states
  plainly that REST is deferred to v2 (no first-party domain needs one
  yet) and that the subprocess connector's shape is the template to
  follow when one is needed sooner.
- For input "Just use defaults, my model returns floats", refuses
  to advance past C1 without unit declarations.

## Future extensions (v2 / v3)

- REST/HTTP archetype-C transport (subprocess is READY as of PR-9; no
  first-party domain has needed REST yet — implement it by following
  `subprocess_source.py`'s shape, transport swapped, when one does).
- Additional worked examples for connector archetypes that do not yet
  have first-party domains.
- FMI / FMU integration for Modelica-world models
- Multi-model coupling (LLM ↔ Model_1 ↔ Model_2)
- Same-period multi-agent feedback loops, if a real research domain
  needs them.

Each future pattern adds a single file under
`references/coupling_patterns/` and a single file under `templates/`
— SKILL.md's decision tree extends by adding one row to the
pattern-matching table. No core refactor required.
