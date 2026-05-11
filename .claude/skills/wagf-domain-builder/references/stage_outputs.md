# Stage Outputs

Use this table as the gate between stages. Do not advance until the output artifact exists and the verification check is satisfied.

| Stage | Action | Output artifact | How to verify done |
|---|---|---|---|
| S0 | Domain articulation interview | `.research/<domain>_brief.md` | File exists, all 8 questions answered |
| S1 | Skills design | Skill list in `.research/<domain>_brief.md` | 3-5 skill IDs, lowercase snake_case |
| S2 | Coupling contract | `.coupling/contract.md` | Section headers complete, tables filled |
| S3 | Mock external model | `lifecycle_hooks.py` with `MockExternalModel` | Smoke can run without real model |
| S4 | `scaffold_domain` | Full directory in `examples/<domain>_demo/` | `validate_prompt` returns OK clean |
| S5 | Edit pass | Edits to prompt, DomainPack, validators, rules | `validate_prompt` still clean after each edit |
| S6 | Mock smoke run | Audit CSV at `results/smoke_<seed>/` | Audit CSV has `years * agents` rows and no `[Adapter:Error]` blocks |
| S7 | Real-model cutover | Live external model wired up | Mock-vs-real smoke produces qualitatively similar traces |

## Ownership

S0, S1, and S5 are handled by `wagf-domain-builder`.

S2, S3, and S7 are handed off to `.claude/skills/wagf-coupling-designer/SKILL.md` when the user has an external model.

S4 is a single command:

```bash
python -m broker.tools.scaffold_domain <domain> \
  --output examples/<domain>_demo \
  --skills "<comma-separated skill ids>"
```

S6 is a single smoke command (after S5 edit 5 has wired ExperimentBuilder):

```bash
python examples/<domain>_demo/run_experiment.py \
    --model gemma3:4b --years 2 --agents 3 \
    --seed 42 --output results/smoke_42
```

Pass `--seed 42 --output results/smoke_42` explicitly so the audit CSV lands at the path the verify-done check expects. Without these flags, the audit goes to `results/smoke/` (no seed suffix) and the verify-done check fails to find it.

After S7, route to `.claude/skills/model-coupling-contract-checker/SKILL.md` for the coupling audit, then `.claude/skills/wagf-experiment-designer/SKILL.md` for the experiment matrix, and `.claude/skills/abm-reproducibility-checker/SKILL.md` before submission.

If the user has no external model, mark S2, S3, and S7 as skipped in `.research/<domain>_brief.md` and do not create placeholder coupling files.

Record the exact command and output path for S4 and S6 in the brief. Later skills should not have to infer which scaffold or smoke run produced the artifacts.
