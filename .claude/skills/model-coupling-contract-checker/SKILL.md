---
name: model-coupling-contract-checker
description: Verify the contract between WAGF/ABM agents and an external model (flood, hydrology, irrigation, seismic, catastrophe) — units, time steps, state mutation direction, feedback-loop double-counting. Use when the user says "check ABM-model coupling", "audit feedback loop", "verify units between WAGF and X model", or asks to confirm an external-model integration is safe.
---

# WAGF: Model Coupling Contract Checker

WAGF couples LLM-driven agents to external physical / catastrophe
models (Lake Mead reservoir, flood-depth grids, seismic damage, etc.).
Bugs in the coupling layer have caused real failures (e.g., the v21
`request`-vs-`diversion` base-asymmetry bug, 2026-03-03). This skill
audits the contract between agent layer and external model.

## When to Use

Load this skill when the user says any of:

- "Check whether my ABM is correctly coupled to this flood model."
- "Audit the external model feedback loop."
- "Verify units and time steps between WAGF and the CAT model."
- "Does this coupling double-count damage?"
- "Validate the ABM ↔ hydrology contract."
- "I want to add an external model — what should I check?"

Do NOT use this skill for:

- Pure ABM debugging unrelated to external model → `debugger`.
- Reproducibility of completed runs → `abm-reproducibility-checker`.
- Designing a new experiment → `wagf-experiment-designer`.

## Inputs

The user must supply ALL of:

1. **ABM state schema** — which fields the agent reads from / writes
   to environment (e.g., `agent.diversion`, `agent.water_right`,
   `env.lake_mead_level`).
2. **External model input schema** — what the external model consumes
   (e.g., demand vector, weather forcing, exposure list).
3. **External model output schema** — what it returns (e.g., delivered
   diversion, flood depth per agent, damage per asset).
4. **Time-step definition** — frequency and alignment (e.g., agent
   yearly decision; reservoir mass balance daily; flood event
   episodic).
5. **State mutation rules** — which side owns which field after each
   step (agent only reads; environment only writes; both write with
   defined order).
6. **Example run output** (optional but recommended) — one round-trip
   trace.

If any of (1)–(5) is missing, ask. Do not guess.

## Workflow

1. **Schema diff**: compare ABM state schema against external model
   input schema. Every external-input field must trace to either an
   agent state field or an environment field. Field type and units
   must match.
2. **Time-step alignment**: verify the external model's time step
   divides into the agent's decision step (e.g., daily reservoir →
   annual agent OK; weekly flood → annual agent requires aggregation
   rule).
3. **Temporal sync + intra-step ordering** (taxonomy E1, E3 — see
   `references/coupling_interaction_taxonomy.md`): enumerate the
   per-step sequence (agent decides → env updates → external runs →
   outcomes propagate → context for next step). Confirm, as a positive
   check (not only a refusal): (a) E1 — the value an agent reads at
   step *t+1* is the model output produced *for step t*, with an
   explicit ordering guarantee, not the `pre_year` `self.env = env`
   aliasing convention alone; (b) E3 — the model-side operation order
   (e.g. `damage → payout → oop → appraisal-input → memory`) is pinned
   and documented, and every consumer (agent prompt, EACH validator,
   audit trace) reads the same vintage of state. A validator reading a
   different vintage than the prompt is an E3 failure even if E1 holds.
4. **Feedback-loop traps** (taxonomy E2, E4, E5):
   - E2 — does damage / cost / exposure get attributed to BOTH the
     agent and the environment ledger (double counting)? One
     consumer-of-record per ledger field.
   - Does an agent's action affect an external-model input that then
     loops back to that same agent's state in the same step (causing
     phantom acceleration)?
   - Are state mutations idempotent under retries? (If the agent
     retries, does the external model run twice?)
   - E4 (multi-agent only) — when N agents feed one model that holds a
     shared resource (insurance pool, budget, aquifer head, reservoir),
     is there a declared, order-independent, **audited**
     conflict-resolution rule? Ad-hoc ordered `env`-dict mutation in
     `lifecycle_hooks.py` is NOT acceptable at >1 agent.
   - E5 — list every validator whose verdict reads a model-produced
     field; confirm that field is guaranteed current (E1) and the
     validator is scoped to the correct agent type (note: builtin
     Python checks are NOT agent-type-scoped today — flag any
     model-feasibility builtin shared across agent types).
5. **Missing / out-of-range handling**: confirm every external-model
   input has documented behaviour for missing values and
   out-of-physical-range values (e.g., negative demand → clip;
   missing flood depth → assume zero or fail loudly?).
6. **Randomness**: confirm both sides share or independently seed
   random number generators in a way that lets the run be reproduced.
7. **Worked-example check** (if provided): walk one trace through the
   round-trip and verify each unit conversion and mutation.
8. **Write report**.

## Outputs

Write under `analysis/coupling/`:

- `coupling_contract_report.md` — structured report with the seven
  sections below.
- `coupling_schema_findings.yml` — machine-readable list of schema
  deltas and severity.

## Output structure contract

`coupling_contract_report.md` MUST have these seven sections in order:

1. `## Scope` — names of the two systems being coupled, their
   versions / commits, the schemas surveyed.
2. `## Verdict` — GREEN / YELLOW / RED with one-sentence rationale.
3. `## Schema findings` — table of (field, ABM type/unit, external
   type/unit, status: OK / mismatch / missing).
4. `## Time-step alignment` — explicit ratio of step durations and
   the aggregation rule when they differ.
5. `## Feedback-loop audit` — for each loop (action → external →
   state → agent), state whether it double-counts, what the
   anti-double-counting guard is, and where it lives in code.
   Explicitly answer the E1–E5 detection questions from
   `references/coupling_interaction_taxonomy.md` (E1 temporal sync,
   E2 double-count, E3 intra-step ordering, E4 multi-agent shared-state
   resolution, E5 validator-depends-on-model-state); mark each
   PASS / FAIL / N-A (single-agent).
6. `## Failure-mode handling` — missing-value and out-of-range
   policies per input field.
7. `## Caveats` — what was NOT checked (e.g., binary external models,
   network-only services, undocumented intermediate caching).

Plus `## Reproducible command list` at the end.

## Refusal Protocol

The skill MUST refuse to:

1. Assume a unit convention. If the schemas don't say `m3` vs `m3/s`
   vs `acre-ft`, ask. The v21 fix would have been caught earlier with
   stricter unit declarations.
2. Treat missing time-step documentation as "annual probably". Ask.
3. Approve a coupling where any external-model output is read by an
   agent in the SAME step that produced it without an explicit
   ordering guarantee.
4. Approve a coupling whose feedback loop has no documented
   anti-double-counting guard.
5. Generate the report from the user's verbal description alone if a
   schema file exists; demand the schema.
6. Approve a >1-agent coupling whose shared-state resolution (insurance
   pool, budget, common-pool resource) is implicit ordered `env`-dict
   mutation with no declared, order-independent, audited rule
   (taxonomy E4).
7. Approve a coupling where a validator's verdict reads a
   model-produced field without (a) a guarantee that the field is
   current (E1 temporal sync) and (b) confirmation the validator is
   scoped to the correct
   agent type (taxonomy E5; builtin Python checks are not
   agent-type-scoped today).

## Bundled resources

- `references/contract_checklist.md` — the full audit checklist,
  YES/NO per field category.
- `references/time_step_alignment.md` — common alignment patterns
  (annual ↔ daily, episodic ↔ continuous, asynchronous events).
- `references/unit_compatibility.md` — common WAGF units and their
  conversion gotchas.
- `references/feedback_loop_traps.md` — catalogued historical
  feedback-loop bugs (v21 base-asymmetry, double-damage in CAT-model
  coupling, etc.) with detection recipes.
- `references/coupling_interaction_taxonomy.md` — the five coupling
  exposure points (E1 temporal sync, E2 double-count, E3 intra-step
  ordering, E4 multi-agent shared-state resolution, E5
  validator-depends-on-model-state), worked end-to-end on a disaster /
  catastrophe model, with the cross-domain skeleton and a
  convention-vs-framework-enforced honesty box. Workflow steps 3–4 and
  Refusal Protocol items 3, 6, 7 derive from this.
- `scripts/contract_diff.py` — diffs two YAML schemas and emits the
  field-level mismatch table.

## Acceptance criteria

The skill is ready when:

- For input "Check the irrigation ABM ↔ Lake Mead reservoir
  coupling", produces a GREEN report with explicit unit + time-step
  declarations and references the v21 fix as a worked example of a
  resolved feedback-loop bug.
- For input "Check this flood-depth CSV ↔ household ABM coupling"
  with no time-step in the user's description, refuses and asks for
  the temporal aggregation rule.
- For input "Verify our new seismic-damage model is hooked up
  correctly" with no schema file supplied, refuses and demands the
  schemas.
