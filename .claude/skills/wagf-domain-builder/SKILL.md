---
name: wagf-domain-builder
description: Walk a researcher (PhD, collaborator, lab-mate) through building their first single-agent WAGF domain — from "I have a research question + maybe an external model" to "I have a working WAGF experiment producing audit traces." Conducts a structured S0-S7 interview, invokes `broker.tools.scaffold_domain` at S4, guides 4 surgical edits in S5, and runs `broker.tools.validate_prompt` after every change. Hands off to `wagf-coupling-designer` for any coupling work and to `wagf-experiment-designer` / `abm-reproducibility-checker` once the domain runs green. Use when the user says "I want to build a WAGF model for <my domain>", "help me set up a new domain", "I'm new to WAGF and have a research question", or "scaffold a domain from scratch".
---

# WAGF: Domain Builder

WAGF gives you the framework — DomainPack, validators, lifecycle
hooks, the governance pipeline. But starting a NEW domain from a
blank repo means making ~30 small decisions about skills, cognitive
framework, validators, prompt structure, coupling. This skill
removes that blank-page problem by conducting a structured 7-stage
interview that ends in a working WAGF experiment.

It is the FIRST skill a new domain author should invoke. It sits
upstream of every other WAGF skill — `wagf-quickstart` is for
running the existing reference examples, this skill is for building
a NEW domain. The two never overlap.

## When to Use

Invoke this skill when the user says any of:

- "I want to build a WAGF model for my <domain>."
- "Help me set up a new domain from scratch."
- "I'm new to WAGF and have a research question about <X>."
- "Scaffold a domain for vaccination / energy / crop yield / ..."
- "How do I add my own domain to WAGF?"

Do NOT use this skill for:

- Running the EXISTING flood / irrigation / vaccination_demo
  reference examples → `wagf-quickstart`.
- Designing an experiment on a domain that already works
  → `wagf-experiment-designer`.
- Coupling to an external model when the domain is otherwise built
  → `wagf-coupling-designer` (called BY this skill at S2/S3/S7,
  also valid standalone).
- Auditing finished traces → `llm-agent-audit-trace-analyzer`.

## Scope (v1)

- **Single-agent domains only.** Multi-agent is deferred until
  PhaseOrchestrator is wired into ExperimentRunner. If the user
  describes a multi-agent setup, surface the deferral and offer
  to build the single-agent version first.
- **Cognitive framework**: PMT / Utility / Financial (pre-
  registered), HBM (registered in vaccination_demo as the non-
  water reference), or custom (scaffolded by
  `scaffold_domain --framework custom`).
- **Coupling** is OPTIONAL: if the user has an external model,
  S2 / S3 / S7 are delegated to `wagf-coupling-designer`. If no
  external model, those stages are skipped cleanly.

## Inputs

Before S0, the user must be in a fresh terminal at the WAGF repo
root, with:

- A research question they can articulate in 1-2 sentences.
- Optional: an existing external simulation model.
- A working Ollama install (or equivalent LLM endpoint) — verify
  with `ollama list` before S6.

If the user is unsure whether their environment is ready, defer to
`wagf-quickstart` first.

## Workflow

The skill runs 8 stages (S0-S7). Each stage produces a concrete
artifact. Do not advance to the next stage until the current
stage's artifact exists and is non-empty. See
`references/stage_outputs.md` for the per-stage verify-done table.

### S0 — Domain articulation (5 min)

Ask the questions in `references/domain_articulation_questions.md`
in order. Write the answers to `.research/<domain>_brief.md`. Do
NOT skip questions — every later stage depends on the answers.

Critical branch at Q4: **does the user have an external model?**
- Yes → coupling-required path (S2 / S3 / S7 active).
- No → coupling-skipped path (jump from S1 straight to S4).

Output: `.research/<domain>_brief.md` with all 6-8 questions
answered.

### S1 — Skills design (10 min)

Translate the user's "what decision does the agent make?" answer
into 3-5 WAGF skills. Use
`references/skills_design_patterns.md` to recognize whether their
decision is scaling, categorical, or hierarchical.

Probe for:
- The **default / inaction** option (always include one).
- Mutually exclusive constraints (will inform validator design at S5).
- Rare / extreme actions (will need stronger justification rules).

Output: skills list appended to `<domain>_brief.md`, formatted as
the `--skills` argument for `scaffold_domain`.

### S2 — Coupling contract design (20 min, OPTIONAL)

Skip if the user has no external model. Otherwise hand off to
`wagf-coupling-designer` for stages C0-C1. Wait for the contract
artifact (`.coupling/contract.md`) to exist before returning to S3.

### S3 — Mock external model build (15 min, OPTIONAL)

Skip if no coupling. Otherwise hand off to
`wagf-coupling-designer` C2 — produces a working
`MockExternalModel` in `lifecycle_hooks.py`.

### S4 — scaffold_domain invocation (1 min, automated)

Run the scaffolder with the args derived from S0 / S1:

```bash
python -m broker.tools.scaffold_domain <domain> \
    --output examples/<domain>_demo \
    --skills "<comma-separated from S1>" \
    --framework <pmt|custom>
```

The `--framework custom` decision: if S0 Q5 picked HBM / TPB / a
novel framework, use `custom`. If PMT / Utility / Financial, use
default.

Verify with `python -m broker.tools.validate_prompt examples/<domain>_demo/config/agent_types.yaml`
— must exit 0 clean. If not, halt and surface the diagnostic.

Output: full directory at `examples/<domain>_demo/` with 10-12
scaffolded files.

### S5 — Edit-pass guidance (60-90 min, the longest stage)

Walk the user through 4 surgical edits using
`references/edit_pass_checklist.md`:

1. **Prompt template** (`config/prompts/<agent_type>.txt`) —
   replace generic narrative with domain-specific situation
   description. Keep all broker-filled placeholders intact.
2. **DomainPack** (`adapters/<domain>_pack.py`) — override `name`,
   `reflection_status_text`, `importance_profiles` at minimum;
   optionally `compute_importance`, `classify_emotion`,
   `event_handlers`, `extreme_actions`.
3. **Validators** (`validators/<domain>_validators.py`) — replace
   the placeholder check with 2-3 real physical / personal /
   social / semantic / temporal / behavioural checks. **No
   thinking-level checks here** — those go in YAML rules (the
   Phase 6C-v4 Finding 1 trap).
4. **YAML thinking rules** (`config/agent_types.yaml`, `rules:`
   block) — 1-2 coherence rules at ERROR level. WARNING-level
   rules have ~0% behavior effect on small LLMs (per MEMORY.md);
   use ERROR for actual enforcement.

After EACH edit, automatically run:
```bash
python -m broker.tools.validate_prompt examples/<domain>_demo/config/agent_types.yaml
```

If it doesn't return OK clean, halt the user there. Don't allow
multiple edits to accumulate undetected drift.

Output: 4 edited files + 4 clean validate_prompt runs.

### S6 — Mock smoke run (5 min)

Run the scaffolded `run_experiment.py`:

```bash
python examples/<domain>_demo/run_experiment.py --model gemma3:4b --years 2 --agents 3 --seed 42
```

Verify:
- No `[Adapter:Error]` blocks in stdout (per Phase 6C-v4 cycle 1
  diagnostic).
- Audit CSV at `results/smoke_42/individual_governance_audit.csv`
  has N = years × agents = 6 rows.
- `proposed_skill` values are all from the declared skill list.
- `raw_output` JSON keys match `response_format.fields[].key`.

If smoke fails, walk the user through the Phase 6C-v4 6-BLOCKER
inventory in `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md`.

Output: audit CSV + reflection log + no error blocks.

### S7 — Real-model cutover (30 min, OPTIONAL)

Skip if no coupling. Otherwise hand off to
`wagf-coupling-designer` C3-C4. After that returns, hand off to:
- `model-coupling-contract-checker` for the audit pass.
- `wagf-experiment-designer` for the experiment matrix.
- `abm-reproducibility-checker` before submission.

## Outputs

After full S0-S7 run, the user's repo will have:

```
.research/
└── <domain>_brief.md                          ← S0/S1 answers

examples/<domain>_demo/                        ← S4 scaffolded
├── __init__.py
├── README.md
├── adapters/<domain>_pack.py                  ← S5 edit 2
├── validators/__init__.py
├── validators/<domain>_validators.py          ← S5 edit 3
├── config/
│   ├── skill_registry.yaml
│   ├── agent_types.yaml                       ← S5 edit 4
│   └── prompts/<agent_type>.txt               ← S5 edit 1
├── lifecycle_hooks.py                         ← S3 mock (if coupling)
├── adapters/external_model_adapter.py         ← S7 real (if coupling)
└── run_experiment.py
└── results/smoke_42/                          ← S6 traces
    └── individual_governance_audit.csv

.coupling/
└── contract.md                                ← S2 (if coupling)
```

This is the same shape as `examples/vaccination_demo/` — the user
can compare their output to the reference example at any point.

## Refusal Protocol

The skill MUST refuse to:

1. **Skip S0 questions.** Every later stage depends on the answers.
   Refuse to scaffold without a complete `<domain>_brief.md`.
2. **Pick the cognitive framework for the user.** Surface
   `references/cognitive_framework_chooser.md`, ask which fits.
   If the user is genuinely unsure, suggest PMT as the safest
   default with an explicit note that it can be changed later.
3. **Advance past S5 with stale validate_prompt errors.** Each of
   the 4 edits must end with a clean validate_prompt run.
4. **Build multi-agent.** v1 is single-agent only. If the user's
   domain is multi-agent, surface the deferral and offer to build
   the single-agent skeleton first.
5. **Hand off to `wagf-quickstart` at any point.** That skill is
   for a different lifecycle stage (running existing examples).
   Cross-referencing is fine; routing the user there mid-build
   is wrong.
6. **Bypass the mock smoke (S6) when coupling is present.** The
   mock-first discipline catches WAGF-side bugs that would
   otherwise be masked by external-model variability.

## Bundled resources

References (you read these to guide stages):

- `references/README.md` — one-page index of this skill's references
- `references/domain_articulation_questions.md` — S0 interview script
- `references/skills_design_patterns.md` — S1 patterns + decision tree
- `references/cognitive_framework_chooser.md` — S0 Q5 framework picker
- `references/edit_pass_checklist.md` — S5 detailed walkthrough
- `references/stage_outputs.md` — per-stage verify-done table

## Hand-off rules

| Stage | Hand off to | When control returns |
|---|---|---|
| S2 (coupling, optional) | `wagf-coupling-designer` C0-C1 | After `.coupling/contract.md` exists |
| S3 (mock, optional) | `wagf-coupling-designer` C2 | After MockExternalModel runs in a 1-year smoke |
| S7 (real-model, optional) | `wagf-coupling-designer` C3-C4 | After mock-vs-real divergence smoke is GREEN |
| S7 (post-cutover) | `model-coupling-contract-checker` | After audit verdict (GREEN/YELLOW/RED) |
| S7 (post-audit) | `wagf-experiment-designer` | After experiment matrix is drafted |
| Pre-submission only | `abm-reproducibility-checker` | After reproducibility verdict |

This skill never hands BACK to `wagf-quickstart` (different
lifecycle stage). It never delegates to `llm-agent-audit-trace-
analyzer` directly — trace analysis is post-experiment, owned by
the experiment-designer chain.

## Acceptance criteria

The skill is ready when:

- For input "I want to build a WAGF model of opioid prescription
  decisions; I have an in-house Python epi model with yearly
  cadence", produces a complete `.research/opioid_brief.md`, a
  3-skill skill list, hands off to coupling-designer cleanly,
  invokes scaffold_domain, guides 4 edits, and finishes with a
  green mock smoke run.
- For input "I have a vaccination domain but no external model",
  same outcome but with S2 / S3 / S7 skipped cleanly.
- For input "I want to build a multi-agent flood model", refuses
  multi-agent v1 scope and offers to build the single-agent
  version.
- For input "Just scaffold me an energy domain quickly, skip the
  questions", refuses to skip S0 and explains why each question
  matters.

## Future extensions (v2)

- Multi-agent variant (waits for PhaseOrchestrator → ExperimentRunner
  wiring).
- "Migrate existing ABM to WAGF" entry point — different journey
  shape: start from existing code, not a blank page.
- "Replace cognitive framework" entry point — for users who built
  with PMT and want to switch to HBM later.
- External-model adapter library — first-party adapters for common
  simulators (SWAT, EPI, EnergyPlus, …). Owned by
  `wagf-coupling-designer` future patterns C/D/E.

Each future entry point is its own SKILL.md with shared references;
the v1 surface here does not need refactoring to accommodate them.
