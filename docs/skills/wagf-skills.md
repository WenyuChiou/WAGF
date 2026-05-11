# WAGF Skills Index

Researcher-facing AI skills bundled with the Water Agent Governance
Framework (WAGF). Each skill orchestrates existing production
analysis scripts; none reimplements WAGF logic.

## Quick chooser

| If you want to … | Load skill |
|---|---|
| **Build a new domain from scratch** — I have a research question + maybe an external model | `wagf-domain-builder` |
| **Design the coupling** between WAGF agents and my external simulator | `wagf-coupling-designer` |
| **Onboard** — first time using the EXISTING reference examples (flood / irrigation / vaccination) | `wagf-quickstart` |
| **Plan** a new experiment matrix from a research question on a working domain | `wagf-experiment-designer` |
| **Analyse** existing audit traces into paper-ready metrics | `llm-agent-audit-trace-analyzer` |
| **Verify** the contract between agents and an external model (audit existing coupling) | `model-coupling-contract-checker` |
| **Audit** an experiment folder before submission | `abm-reproducibility-checker` |

### Lifecycle map

```
[blank repo + research question]
        ↓
   wagf-domain-builder (S0-S7)     ← builds the domain
   ├─ S2/S3/S7: hands off to
   │   wagf-coupling-designer (C0-C4) ← designs the external-model interface
   │            └─ C4: hands off to
   │                model-coupling-contract-checker  ← audits the coupling
   │
   └─ S7: hands off to
       wagf-experiment-designer    ← plans the experiment matrix
                  ↓
             [run experiment]
                  ↓
       llm-agent-audit-trace-analyzer ← analyses the traces
                  ↓
       abm-reproducibility-checker    ← pre-submission audit
```

`wagf-quickstart` is a separate path for users running the EXISTING reference
examples (not building a new domain).

For paper writing, Zotero, citations, generic coding delegation, or
literature review, use the user-level skills (`academic-writing-skills`,
`research-hub`, `verify-references`, `codex-delegate`,
`gemini-delegate`). WAGF skills do NOT duplicate those.

## Skill 0: `wagf-quickstart` (entry point)

**Trigger phrases**: "I just cloned WAGF", "set up WAGF", "first WAGF
run", "I'm new to this", "where do I start with WAGF", or opening a
Claude Code session in a freshly-cloned WAGF repo without a clear
task.

**Inputs**: none (the skill prompts the user as it walks the four
phases).

**Outputs**: `.wagf-quickstart-status.json` (resume-state file);
hands off artefacts to the lifecycle skills.

**Workflow**: 4 phases:
1. Environment check (~3 min) via
   `.claude/skills/wagf-quickstart/scripts/check_env.py`.
2. Smoke test (~5 min) via `examples/quickstart/0[12]_*.py`.
3. First experiment (~30 min) — hand off to
   `wagf-experiment-designer` with sensible defaults.
4. First analysis (~5 min after run) — hand off to
   `llm-agent-audit-trace-analyzer`.

**Refusal protocol**: refuses to skip phases, pretend env is fine when
`check_env.py` says no, or auto-fill the user's research question.

## Skill 1: `wagf-experiment-designer`

**Trigger phrases**: "design an experiment", "plan an ablation",
"compare strict vs disabled", "set up cross-model evaluation".

**Inputs**: research question, hypothesis, domain (flood / irrigation
/ multi-agent flood), candidate Ollama model tags, governance
conditions, seed budget, time horizon, agent count, metric set.

**Outputs**: `.research/wagf_experiment_matrix.yml`,
`.research/metrics_plan.md`, `.research/run_plan.md`.

**Reuses**: matrix template from `.research/`, metric catalogue from
`examples/<domain>/analysis/compute_*.py`, governance modes from
`examples/<domain>/agent_types.yaml`.

**Refusal protocol**: refuses to invent model tags, governance modes,
or metrics; refuses to mix domains in one matrix; refuses to plan
n<3 paired-t without an explicit "exploratory" flag.

## Skill 2: `llm-agent-audit-trace-analyzer`

**Trigger phrases**: "analyze these traces", "compute governance
metrics", "summarize rejection and retry outcomes", "give me an
IBR/EHE table".

**Inputs**: a run dir or results-tree root containing
`household_governance_audit.csv` + `raw/*.jsonl`.

**Outputs**: `analysis/governance_metrics.csv`,
`governance_summary.md`, `rejection_taxonomy.csv`,
`retry_outcomes.csv`, `model_condition_comparison.md`.

**Reuses (do NOT reimplement)**: `compute_ibr_components`,
`shannon_entropy`, `compute_temporal_diagnostics.py`,
`compute_retry_compliance.py`, `detect_audit_sentinels_in_csv`.

**Refusal protocol**: refuses to invent metric formulas; refuses to
pool seeds across code commits without flagging; refuses to drop
sentinel-flagged columns silently.

## Skill 3: `model-coupling-contract-checker`

**Trigger phrases**: "check ABM-model coupling", "audit feedback
loop", "verify units between WAGF and X model", "does this coupling
double-count damage?".

**Inputs**: ABM state schema, external model input/output schemas,
time-step definition, state mutation rules, optional example trace.

**Outputs**: `analysis/coupling/coupling_contract_report.md`,
`analysis/coupling/coupling_schema_findings.yml`.

**Reuses**: `examples/multi_agent/flood/orchestration/lifecycle_hooks.py`
for canonical hook signatures; `examples/irrigation_abm/irrigation_env.py:585-595`
as the v21 worked-example of a resolved feedback-loop bug.

**Refusal protocol**: refuses to assume unit conventions or time-step
ratios; refuses to approve a coupling with read-after-write within
step; demands schemas (does not work from verbal description alone
when schema files exist).

## Skill 4: `abm-reproducibility-checker`

**Trigger phrases**: "audit reproducibility", "prepare for
submission", "check this experiment folder", "verify seed X was
generated by the code we cite".

**Inputs**: results-tree root with
`reproducibility_manifest.json` files OR a paper Methods section +
figure script paths.

**Outputs**: `analysis/reproducibility/reproducibility_report.md`,
`artifact_inventory.yml`, `missing_repro_steps.md`.

**Reuses**: `_collect_reproducibility_metadata` schema,
`detect_audit_sentinels_in_csv`, `git log --follow` cross-reference
pattern.

**Refusal protocol**: refuses to declare GREEN without successful
manifest + git-blame cross-reference; refuses to treat unmasked
sentinels as benign unless on `broker/INVARIANTS.md` Invariant 4
reserved list; refuses to GREEN if `pytest broker/ tests/` fails.

## Skill 5: `wagf-domain-builder` (Phase 6D, 2026-05-10)

**Trigger phrases**: "I want to build a WAGF model for <my domain>",
"help me set up a new domain", "I'm new to WAGF and have a research
question about X", "scaffold a domain from scratch".

**Inputs**: research question (1-2 sentences), optional external
model identity, working LLM endpoint.

**Outputs**: `.research/<domain>_brief.md`, full directory at
`examples/<domain>_demo/`, edited prompt / DomainPack / validators /
YAML rules, audit CSV from mock smoke at `results/smoke_<seed>/`.

**Reuses**: `broker.tools.scaffold_domain` (cycle 4),
`broker.tools.validate_prompt` (cycle 3); hands off to
`wagf-coupling-designer` for S2/S3/S7 stages if coupling is needed;
hands off to `wagf-experiment-designer` after S7.

**Refusal protocol**: refuses to skip S0 interview questions, pick
the cognitive framework for the user, advance past S5 with stale
validate_prompt errors, build multi-agent (v1 single-agent only),
or bypass the mock smoke (S6) when coupling is present.

## Skill 6: `wagf-coupling-designer` (Phase 6D, 2026-05-10)

**Trigger phrases**: "I want to couple my WAGF agents to <my
simulator>", "help me design the WAGF↔X interface", "draft a
coupling contract", "scaffold the external model adapter",
"I have a Python / R / CSV-based model and want WAGF to drive it".

**Inputs**: domain name, external model identity (name + language /
runtime), decision variables, output variables, cadence, reset
semantics.

**Outputs**: `.coupling/contract.md` (7 required sections),
`lifecycle_hooks.py` with `MockExternalModel`,
`adapters/external_model_adapter.py` (pattern-specific).

**Reuses**: pattern A (CSV replay) and pattern B (Python library)
templates from `references/coupling_patterns/`; pairs with
`model-coupling-contract-checker` (this skill DRAFTS the contract;
that skill AUDITS it).

**Refusal protocol**: refuses to guess units, skip failure-mode
questions, advance past C1 without a complete contract, bypass the
mock smoke before real-model cutover, or claim mock fidelity
matches real model.

**v1 scope**: patterns A + B only (~80% of PhD use cases).
C (subprocess) / D (REST) / E (co-process) deferred to v2.

## Why these specific seven

WAGF now has 7 skills covering the full lifecycle from blank repo
to submitted paper:

| Skill | Lifecycle slot |
|---|---|
| `wagf-domain-builder` | NEW: from blank to working domain |
| `wagf-coupling-designer` | NEW: from working domain to coupled simulator |
| `wagf-quickstart` | Onboarding on EXISTING reference examples |
| `wagf-experiment-designer` | Plan the experiment matrix |
| `model-coupling-contract-checker` | Audit coupling (sister of designer) |
| `llm-agent-audit-trace-analyzer` | Post-run trace analysis |
| `abm-reproducibility-checker` | Pre-submission gate |

Adding more risks duplicating user-level skills
(`academic-writing-skills`, `research-hub`). Each existing skill
owns a distinct lifecycle slot — there is no functional overlap.

## Composing the five skills (typical flow)

0. **Onboard** with `wagf-quickstart` (first time only) → environment
   check + smoke test + handoff to step 1.
1. **Plan** with `wagf-experiment-designer` →
   `.research/wagf_experiment_matrix.yml`.
2. **Run** the experiment via the bat in
   `.research/run_plan.md` (no skill — this is just bash / Ollama).
3. **Verify coupling** mid-run with `model-coupling-contract-checker`
   if a new external model was added.
4. **Analyse** completed runs with
   `llm-agent-audit-trace-analyzer` →
   `analysis/governance_summary.md`.
5. **Audit** for submission with `abm-reproducibility-checker` →
   `analysis/reproducibility/reproducibility_report.md`.
6. **Hand off** the four output bundles plus the paper draft to
   `academic-writing-skills` for the actual writing.

## Anti-hallucination guardrails (cross-cutting)

Every WAGF skill must:

- Refuse to invent metric formulas, model tags, or domain
  assumptions.
- Cite the exact production file:line for every formula it uses.
- Surface ambiguity as a `caveats` section in every output report.
- Cross-reference manifest `git_commit` against trace timestamps
  before claiming reproducibility.
- Mark unknowns as `TODO` rather than auto-filling.

## See also

- `.ai/wagf_skills_brief_2026-04-25.md` — the original Codex brief
  that motivated these four skills.
- `.ai/wagf_audit_summary_2026-04-24.md` — the 2026-04-24 audit
  that produced the failure-pattern catalogue used by
  `abm-reproducibility-checker`.
- `broker/INVARIANTS.md` — the framework invariants every skill
  cross-references.
