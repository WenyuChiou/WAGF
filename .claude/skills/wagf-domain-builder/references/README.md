# WAGF Domain Builder References

These references support `wagf-domain-builder`, the first-domain-build workflow for a researcher turning a research question into a runnable single-agent OR multi-agent WAGF domain. They keep the main `SKILL.md` short while carrying the S0/S1/S5 detail needed to scaffold, edit, validate, and smoke-test a new domain.

Use them with `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md`; do not duplicate that guide during execution. The guide is the canonical schema reference, while these files tell the skill what to ask, how to choose patterns, and where to stop.

## Files

| File | Use |
|---|---|
| `domain_articulation_questions.md` | S0 interview script for domain, decision, cadence, coupling, framework, scope, and baseline. |
| `skills_design_patterns.md` | S1 patterns for translating a domain decision into 3-5 WAGF skill IDs. |
| `cognitive_framework_chooser.md` | S0 Q5 chooser for PMT, Utility, Financial, HBM, TPB, or custom frameworks. |
| `edit_pass_checklist.md` | S5 surgical edit checklist (single-agent path) for prompt, DomainPack, validators, YAML rules, and ExperimentBuilder wiring. |
| `multi_agent_walkthrough.md` | S5 multi-agent path — lifecycle_hooks env-dict-whitelist writes, `with_phase_order` execution ordering, dual-dict gotcha (Phase 6E Finding #3), Tier 1 (broadcast) and Tier 2 (spatial gossip) variants. Read in full before any multi-agent edit-5. |
| `stage_outputs.md` | One-page S0-S7 output table with verify-done checks. |
| `README.md` | This index and routing map. |

## Stage Flow

S0 domain articulation -> S1 skills design -> S2 coupling contract, optional -> S3 mock external model, optional -> S4 scaffold_domain -> S5 edit pass -> S6 mock smoke run -> S7 real-model cutover, optional.

S0, S1, and S5 are the work of `wagf-domain-builder`.

S2, S3, and S7 are hand-offs when an external model is involved.

S4 and S6 are short tool invocations with verification gates.

## Hand-Off Skills

- `.claude/skills/wagf-coupling-designer/SKILL.md` designs new external-model contracts, mocks, and adapters for S2/S3/S7.
- `.claude/skills/model-coupling-contract-checker/SKILL.md` audits the real coupling after S7 cutover.
- `.claude/skills/wagf-experiment-designer/SKILL.md` turns the working domain into a reproducible experiment matrix.
- `.claude/skills/abm-reproducibility-checker/SKILL.md` performs the pre-submission reproducibility sweep.

Do not route a first-domain-build user to `.claude/skills/wagf-quickstart/SKILL.md` mid-build. `wagf-quickstart` is for running existing examples, not authoring a new domain.

## Tools Invoked

- `broker.tools.scaffold_domain`: writes the initial domain skeleton under `examples/<domain>_demo/`.
- `broker.tools.validate_prompt`: checks prompt/YAML alignment after S4 and after every S5 edit.

## Reference Domains

- `examples/vaccination_demo/`: first non-water single-agent reference, HBM-based.
- `examples/vaccination_ma_demo/`: multi-agent reference, 3 agent types (health_authority + community_org + individual), env-dict-whitelist coupling; supports `--tier2-gossip` for spatial neighbor observability.
- `examples/irrigation_abm/`: scaling-action water-demand reference (single-agent).
- `examples/governed_flood/`: flood adaptation reference with categorical protective actions (single-agent).
- `examples/multi_agent/flood/`: Paper 3 multi-agent flood (4 agent types: government, insurance, household_owner, household_renter); production-scale reference.
