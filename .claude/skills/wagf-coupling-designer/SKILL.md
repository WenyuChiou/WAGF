---
name: wagf-coupling-designer
description: Walk a researcher through designing the LLM↔external-model interface — decision flow IN, observation flow OUT — for a single-agent WAGF domain. Emits a coupling contract, a working mock adapter, and a pattern-specific real-model adapter scaffold so the WAGF side can be built and smoke-tested BEFORE the real model is wired in. Use when the user says "I want to couple my LLM agents to <my simulator>", "help me design the WAGF↔X interface", "scaffold the external model adapter", "draft a coupling contract", "I have a Python / R / CSV-based model and want WAGF to drive it". Sister skill to `model-coupling-contract-checker` (which AUDITS existing contracts; this one DESIGNS new ones).
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

## Scope (v1)

Currently supports **single-agent** WAGF setups and **two coupling
patterns**:

- **Pattern A — File replay**: CSV / NetCDF / pre-computed model
  outputs replayed by year or timestep.
- **Pattern B — Python library**: direct import + function call of an
  in-process Python model.

Three more patterns are documented for awareness but DEFERRED to v2:
C (subprocess CLI), D (REST API), E (long-running co-process). If the
user's model fits C/D/E, surface the deferral and offer pattern B as
a stop-gap (wrap the external call in a Python function).

### Multi-agent coupling: read this first

v1 **scaffolds single-agent couplings only**. Multi-agent
code-emission is correctly deferred (the PhaseOrchestrator /
coordination layer is not yet wired into `ExperimentRunner` — see the
Phase-3/4 gating in the consolidated plan). This is NOT cosmetic: in a
multi-agent coupling the external model returns a per-agent outcome AND
a shared-state update (insurance pool, budget, common-pool resource)
that loops back to every agent. That introduces exposure point **E4
(multi-agent shared-state resolution)** which v1 cannot scaffold and
which is, today, resolved by ad-hoc ordered `env`-dict mutation that is
**not routed through the audit pipeline**.

If the user's target is multi-agent:

1. Still draft the single-agent contract here (E1, E2, E3 and E5 all
   apply per-agent — only E4 is multi-agent-specific — and the
   single-agent contract is the foundation).
2. Explicitly warn the user that E4 is unscaffolded and that
   hand-rolling cross-agent shared-state mutation will silently
   reproduce the dormant-coordination-layer gap.
3. Point them at the full taxonomy:
   `model-coupling-contract-checker/references/coupling_interaction_taxonomy.md`
   (E1–E5, disaster-model worked example, the multi-agent
   amplification column) and at
   `wagf-domain-builder/references/multi_agent_walkthrough.md` (the
   `self.env = env` dual-dict contract + the disaster-coupling worked
   example).
4. Do NOT pretend v1 produced a multi-agent-safe coupling.

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

Ask: "Where does your external model live? Is it (A) a static file of
pre-computed outputs, (B) a Python library you import, (C) a CLI tool
you run as a subprocess, (D) a REST API, or (E) a long-running
co-process?"

Match the answer against
`references/coupling_patterns/README.md`. If C/D/E, explain the v2
deferral and offer pattern B as a stop-gap.

Output: pattern letter (A or B) recorded in the contract draft.

### C1 — Contract drafting (20 min)

Walk the user through filling in the template at
`templates/coupling_contract.md.tmpl`. Use
`references/contract_template.md` for narrative explanation of each
section.

For each section, ask only the questions that section requires —
don't dump the whole template on the user upfront.

After every variable declared, immediately ask the unit. Reference
`references/units_audit_checklist.md` for the 8-10 common unit traps.

For failure modes, force a per-mode answer (timeout / NaN / crash /
out-of-range). Default policy is "fail loudly"; the user must
explicitly opt into "reuse last good output + log warning" — never
silently zero-fill.

Output: `.coupling/contract.md` in the user's domain root.

### C2 — Mock generator (15 min)

Copy `templates/mock_external_model.py.tmpl` into the user's
`lifecycle_hooks.py` (or a new module imported from there).
Substitute the placeholder markers (`<<DOMAIN_NAME>>`,
`<<VAR_RANGES>>`, etc.) using the contract drafted in C1.

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

Output: `lifecycle_hooks.py` with a working `MockExternalModel`.

### C3 — Adapter scaffold (10-30 min, pattern-dependent)

Copy the pattern-specific adapter template:
- Pattern A → `templates/adapter_A_file_replay.py.tmpl`
- Pattern B → `templates/adapter_B_python_library.py.tmpl`

Substitute placeholders with the contract values. The user then
fills the TODO markers in the template (file path / library import /
column names / unpacking logic).

The adapter MUST share the same input/output schema as the mock so
the rest of the WAGF wiring (lifecycle hooks, validators, prompt
context) doesn't change when swapping mock for real. In particular the
real adapter MUST keep emitting the `*_step` stamp the C2 E1 guard
checks — a real model that drops the stamp silently disables the
temporal-sync assertion.

Output: `adapters/external_model_adapter.py` with TODOs marked.

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

The skill itself never edits broker/ or DomainPack code — those are
the user's responsibility.

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
6. **Approve patterns C / D / E in v1.** If the user's model only
   fits C/D/E, surface the deferral, offer Pattern B as a stop-gap
   if the model has Python bindings, and document the request for
   a v2 issue.

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

Templates (file scaffolds the user fills in):

- `templates/coupling_contract.md.tmpl` — the contract template with
  placeholder markers (`<<DOMAIN_NAME>>`, etc.).
- `templates/mock_external_model.py.tmpl` — deterministic Python
  mock that mirrors the contract's input/output schema.
- `templates/adapter_A_file_replay.py.tmpl` — Pattern A adapter
  scaffold (CSV + caching).
- `templates/adapter_B_python_library.py.tmpl` — Pattern B adapter
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

- For input "I have an in-house Python crop-yield model, single
  agent, yearly decisions, model takes fertilizer-pct and returns
  yield-tons-per-ha", produces a complete `.coupling/contract.md`
  with all 7 sections filled, a working
  `MockExternalModel`, and a Pattern-B adapter scaffold.
- For input "I have a SWAT Fortran model", refuses pattern C/D/E
  v1 and offers Pattern B (Python wrapper) as a stop-gap with
  clear caveats.
- For input "Just use defaults, my model returns floats", refuses
  to advance past C1 without unit declarations.

## Future extensions (v2 / v3)

- Patterns C / D / E adapter templates (subprocess, REST,
  co-process)
- FMI / FMU integration for Modelica-world models
- Multi-model coupling (LLM ↔ Model_1 ↔ Model_2)
- Multi-agent variants (deferred until PhaseOrchestrator is wired
  into ExperimentRunner)

Each future pattern adds a single file under
`references/coupling_patterns/` and a single file under `templates/`
— SKILL.md's decision tree extends by adding one row to the
pattern-matching table. No core refactor required.
