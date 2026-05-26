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

## Scope (v1.1, updated 2026-05-10 per Phase 6E)

- **Single-agent or multi-agent domains.** Multi-agent path validated
  end-to-end by `examples/multi_agent/flood/` (Paper 3 production-grade, env-dict-
  whitelist cross-agent coupling, `with_phase_order` ordering). For
  multi-agent, also read `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md`
  "Building a multi-agent domain" section — covers the dual-dict
  gotcha (Phase 6E Finding #3) the scaffold doesn't auto-handle.
- The scaffolded `run_experiment.py` is a single-agent template. For
  multi-agent, the S5 edit-5 step (ExperimentBuilder wiring) is larger:
  copy from `examples/multi_agent/flood/run_unified_experiment.py` rather than
  the single-agent demo.
- **Cognitive framework**: PMT / Utility / Financial (pre-
  registered), HBM (registered in vaccination_demo as the non-
  water reference), or custom (scaffolded by
  `scaffold_domain --framework custom`). **Phase 6Q-G (2026-05-26)
  registration contract**: auto-discovery in
  `broker/domains/__init__.py` was removed. If your generated domain
  uses PMT / Utility / Financial / cognitive_appraisal (i.e. anything
  registered by `broker.domains.water`), your
  `examples/<domain>/__init__.py` must add `import broker.domains.water`
  before `DomainPackRegistry.register(...)`. Custom frameworks (HBM-
  style) register their own metadata and do NOT need this. See
  `examples/governed_flood/__init__.py` for the canonical pattern.
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

The `--framework` decision: `scaffold_domain` only accepts `pmt` or
`custom`. Pick:
- `--framework pmt` — only if S0 Q5 picked PMT (it is the one
  framework pre-registered for the scaffold path).
- `--framework custom` — for Utility, Financial, HBM, TPB, or any
  novel theory. The scaffold emits a `cognition/` package with
  `register_framework_metadata()` boilerplate that you fill in
  during S5.

If the user picks Utility or Financial expecting "default", use
`--framework custom` and immediately note that the registration
boilerplate is already implemented in `examples/vaccination_demo/
cognition/` (HBM example) and `broker/domains/water/{utility,
financial}.py` (Utility, Financial reference implementations) — they
do NOT need to re-implement these, just register them in the
generated `cognition/__init__.py`.

Verify with `python -m broker.tools.validate_prompt examples/<domain>_demo/config/agent_types.yaml`
— must exit 0 clean. If not, halt and surface the diagnostic.

Output: full directory at `examples/<domain>_demo/` with 10-12
scaffolded files.

### S5 — Edit-pass guidance (60-90 min, the longest stage)

Walk the user through 5 surgical edits using
`references/edit_pass_checklist.md`. Edits 1-4 follow checklist
order; edit 5 is the ExperimentBuilder wiring that turns the
scaffolded `run_experiment.py` STUB into a working smoke entry
point.

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
4. **YAML thinking rules** (`config/agent_types.yaml`,
   `thinking_rules:` block — NOT `rules:`; the broker's
   `get_thinking_rules()` loader at
   `broker/utils/agent_config.py:859` only recognises
   `thinking_rules` or `coherence_rules`. A bare `rules:`
   block is silently dead config — Phase 6N-C 2026-05-23
   finding from the vaccination_demo PoC, which had used the
   wrong key for its entire lifetime.) 1-2 coherence rules at
   ERROR level. WARNING-level rules have ~0% behavior effect
   on small LLMs (per MEMORY.md); use ERROR for actual
   enforcement.
5. **`run_experiment.py` ExperimentBuilder wiring** — the
   scaffolded `run_experiment.py` is intentionally a TODO stub
   (just prints "TODO: replace this stub" and exits). Replace it
   with a working entry point.

   **Single-agent path**: use `examples/vaccination_demo/run_experiment.py`
   as the canonical reference. Key elements: `ExperimentBuilder`
   import, synthetic agent generator OR real-data loader,
   `with_simulation(env)` instantiation, `builder.run()` invocation.
   If coupling (S2/S3) is present, inject the `MockExternalModel` /
   real adapter into the environment object at this step.

   **Multi-agent path**: read `references/multi_agent_walkthrough.md`
   in full before starting edit 5. The wiring is materially
   different — uses `with_lifecycle_hooks(pre_year, post_step,
   post_year)` instead of `with_simulation`, requires a
   `dynamic_whitelist` declared with `TieredContextBuilder`, needs
   `with_phase_order([[t1], [t2], [t3]])` for execution ordering,
   and has the **dual-dict gotcha** (Phase 6E Finding #3 — the
   `self.env = env` aliasing requirement in `pre_year`) that
   silently breaks cross-agent state propagation if missed. The
   canonical reference is `examples/multi_agent/flood/`. The
   walkthrough doc covers all 5 multi-agent-specific additions, the
   gotcha, and a per-symptom BLOCKER table.

   Without this edit, S6 cannot produce an audit CSV — the stub
   just prints TODO and exits.

After EACH edit (1-4), automatically run:
```bash
python -m broker.tools.validate_prompt examples/<domain>_demo/config/agent_types.yaml
```

Edit 5 doesn't need `validate_prompt` (it's Python wiring, not
config). Instead, verify edit 5 by running S6 immediately after.

If `validate_prompt` doesn't return OK clean, halt the user there.
Don't allow multiple edits to accumulate undetected drift.

Output: 5 edited files + 4 clean validate_prompt runs (edits 1-4)
+ a working `run_experiment.py` ready for S6 smoke (edit 5).

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

examples/<domain>_demo/
├── __init__.py                                ← S4 scaffold
├── README.md                                  ← S4 scaffold
├── adapters/<domain>_pack.py                  ← S4 scaffold, edited at S5 edit 2
├── validators/__init__.py                     ← S4 scaffold
├── validators/<domain>_validators.py          ← S4 scaffold, edited at S5 edit 3
├── config/
│   ├── skill_registry.yaml                    ← S4 scaffold
│   ├── agent_types.yaml                       ← S4 scaffold, edited at S5 edit 4
│   └── prompts/<agent_type>.txt               ← S4 scaffold, edited at S5 edit 1
├── run_experiment.py                          ← S4 scaffold (STUB), rewritten at S5 edit 5
├── lifecycle_hooks.py                         ← created at S3 by wagf-coupling-designer C2 (coupling only)
├── adapters/external_model_adapter.py         ← created at S7 by wagf-coupling-designer C3 (coupling only)
└── results/smoke_42/                          ← S6 traces (path follows --output flag)
    └── individual_governance_audit.csv

.coupling/                                     ← coupling only
└── contract.md                                ← created at S2 by wagf-coupling-designer C1
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
4. **Build multi-agent without surfacing the dual-dict gotcha.** v1.1
   supports multi-agent, but the user MUST be directed to the
   `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md` "Building a multi-agent
   domain" section before starting S5 edit-5 (ExperimentBuilder
   wiring). Specifically confirm they understand: (a) the
   `self.env = env` aliasing requirement in `pre_year`, (b) the
   `with_phase_order` ordering, and (c) the env-dict-whitelist
   pattern matches their cross-agent coupling shape. Refuse to
   proceed to S6 smoke without that confirmation — silent failures
   here are the Phase 6E Finding #3 class.
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
- `references/edit_pass_checklist.md` — S5 detailed walkthrough (single-agent path)
- `references/multi_agent_walkthrough.md` — S5 multi-agent path: lifecycle_hooks + dynamic_whitelist + with_phase_order + the dual-dict gotcha. Read in FULL before guiding any multi-agent S5 edit-5 (Phase 6E pre-merge audit P2 → resolved 2026-05-11).
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
- For input "I want to build a multi-agent flood model", surfaces
  the HOW_TO multi-agent section (covers the dual-dict gotcha + env-
  dict-whitelist pattern + `with_phase_order`), points the user at
  `examples/multi_agent/flood/` as the canonical reference, and
  proceeds with S0-S7 — the multi-agent branching expands S5 edit-5
  scope but the rest of the flow is unchanged.
- For input "Just scaffold me an energy domain quickly, skip the
  questions", refuses to skip S0 and explains why each question
  matters.

## Future extensions (v2)

- Tier 2 multi-agent VALIDATED on examples/multi_agent/flood/ (Paper 3 production)
  (2026-05-11 — `--tier2-gossip` mode, 8 individuals, gemma3:1b, all
  10 traces APPROVED, `{neighbor_action_summary}` renders correctly).
  Future v2 work: formalise the Tier 2 onboarding path in this skill's
  S5 stage so users opting into spatial gossip get the InteractionHub
  + SpatialNeighborhoodGraph wiring as part of the normal flow rather
  than reading `references/multi_agent_walkthrough.md` separately.
- "Migrate existing ABM to WAGF" entry point — different journey
  shape: start from existing code, not a blank page.
- "Replace cognitive framework" entry point — for users who built
  with PMT and want to switch to HBM later.
- External-model adapter library — first-party adapters for common
  simulators (SWAT, EPI, EnergyPlus, …). Owned by
  `wagf-coupling-designer` future patterns C/D/E.

Each future entry point is its own SKILL.md with shared references;
the v1 surface here does not need refactoring to accommodate them.
