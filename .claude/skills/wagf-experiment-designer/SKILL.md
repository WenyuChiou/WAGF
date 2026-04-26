---
name: wagf-experiment-designer
description: Turn a WAGF research question into a reproducible experiment matrix (model × governance × seed × metric × artefact path). Use when the user says "design an experiment", "plan an ablation", "compare strict vs disabled", "set up cross-model evaluation", or wants a runnable matrix written to .research/.
---

# WAGF: Experiment Designer

Convert a research question into a reproducible experiment matrix that
the WAGF runner can execute. The skill produces three artefacts:

- `.research/wagf_experiment_matrix.yml` — the (model × governance ×
  seed × …) cross-product to run.
- `.research/metrics_plan.md` — the metric-to-artefact mapping that
  the analyzer skill will read.
- `.research/run_plan.md` — runnable bat / shell commands derived from
  the matrix, with idempotent skip-checks.

## When to Use

Load this skill when the user says:

- "Design an experiment to test whether governance reduces hallucinated actions."
- "Compare strict vs relaxed governance across models."
- "Plan a cross-model WAGF ablation."
- "I want to test [hypothesis] — set up the experiment matrix."
- "Lay out runs for [model list] × [seeds]."

Do NOT use this skill for:

- Analysing existing audit traces → `llm-agent-audit-trace-analyzer`.
- Reproducibility audit of completed runs → `abm-reproducibility-checker`.
- Generic project planning → `project-planner`.

## Inputs

The skill needs answers to ALL of:

1. **Research question** — one-sentence claim or comparison.
2. **Hypothesis** — what direction of effect is expected, with sign.
3. **Domain** — flood (single_agent), irrigation (irrigation_abm),
   or multi_agent_flood. If unsure, ask. Do not guess.
4. **Candidate models** — exact Ollama tags (e.g., `gemma3:4b`,
   `gemma4:e4b`, `ministral-3:8b`). Refuse to invent unavailable
   models; check via `ollama list` if unsure.
5. **Governance conditions** — list from
   `examples/<domain>/agent_types.yaml`'s `governance_profile` keys.
   Common values: `strict`, `disabled`, `relaxed`, plus any ablation
   variant present in the domain config.
6. **Seed budget** — integer count; default 5 (paper convention) but
   ask for confirmation. Specify which seeds (typically 42–46).
7. **Time horizon** — number of simulation years (flood: 10;
   irrigation: 42; user override OK).
8. **Agent count** — flood: 100; irrigation: 78 (CRSS); MA flood: 400.
9. **Metric set** — drawn from `references/metrics_catalog.md`. Refuse
   to invent metrics not in the catalogue.

If any input is missing, ask. Do not assume.

## Workflow

1. **Clarify**: confirm all 9 inputs above; if missing, ask.
2. **Build matrix**: cross-product of (model × condition × seed) with
   shared time horizon and agent count. Each row = one run.
3. **Map metrics → artefacts**: each metric in the user's set must
   point to (a) the canonical analysis script (per
   `references/metrics_catalog.md`), and (b) the expected output path
   (e.g., `analysis/<metric>_summary.md`).
4. **Write run plan**: one bat / shell command per matrix row, with
   `if exist <output>/simulation_log.csv` skip-check for idempotent
   resume. Reference an existing per-domain bat as template (e.g.,
   `examples/irrigation_abm/run_gemma4_e2b_batch.bat`).
5. **Write the three artefacts**.

## Outputs (mandatory artefacts)

### `.research/wagf_experiment_matrix.yml`

```yaml
research_question: "<one-sentence>"
hypothesis: "<directional claim>"
domain: flood | irrigation | multi_agent_flood
agent_count: <int>
time_horizon_years: <int>

models:
  - tag: gemma4:e4b
    governance:
      - strict
      - disabled
    seeds: [42, 43, 44, 45, 46]

  - tag: gemma3:4b
    governance:
      - strict
      - disabled
    seeds: [42, 43, 44, 45, 46]

metrics:
  - name: ibr
    canonical_script: examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py
    formula_ref: references/metrics_catalog.md#ibr
    output_artefact: analysis/governance_metrics.csv
  - name: ehe
    canonical_script: examples/irrigation_abm/analysis/nw_bootstrap_ci.py:shannon_entropy
    formula_ref: references/metrics_catalog.md#ehe
    output_artefact: analysis/governance_metrics.csv

statistical_comparisons:
  - name: governed_vs_disabled_per_model
    test: paired_t
    metric: ibr
    df_per_model: 4   # n_seeds - 1
```

### `.research/metrics_plan.md`

Free-form markdown with one section per metric:

```markdown
## IBR (Irrational Behaviour Rate)
- Definition: <restate from metrics_catalog.md>
- Canonical script: <path>
- Input data path: <path glob>
- Output: <path>
- Statistical comparison: paired t (governed vs disabled, n=5 seeds)
- Acceptance: ΔIBR with 95% CI excludes 0 → governance effect confirmed
```

### `.research/run_plan.md`

Runnable command list with idempotency:

```bash
# Phase 1: gemma4:e4b governed
for seed in 42 43 44 45 46; do
    if [ -f "examples/single_agent/results/JOH_FINAL_v2/gemma4_e4b/Group_C/Run_${seed}/simulation_log.csv" ]; then
        echo "skip: gemma4:e4b governed seed=${seed}"
    else
        python examples/single_agent/run_flood.py \
            --model gemma4:e4b --seed ${seed} \
            --governance-mode strict \
            --output examples/single_agent/results/JOH_FINAL_v2/gemma4_e4b/Group_C/Run_${seed} \
            --num-ctx 8192 --num-predict 1536 \
            > .../seed${seed}.stdout.log 2>&1
    fi
done
```

## Refusal Protocol

The skill MUST refuse to:

1. Invent model tags. If user gives "Gemma" or "Claude" without a
   specific Ollama tag, ask. Do not guess.
2. Invent metrics. Ask the user to choose from
   `references/metrics_catalog.md` or to specify a new formula
   (out-of-scope; must be implemented as a new analysis script first).
3. Invent governance modes. Read available modes from the domain's
   `agent_types.yaml`; ask if the requested mode is not configured.
4. Run with seed budget < 3 unless the user explicitly states the
   experiment is exploratory. Below n=3 paired-t is unreliable; flag.
5. Mix domains in one matrix. Each matrix is single-domain by default;
   cross-domain comparison requires a separate matrix per domain plus
   a comparison plan.

## Output structure contract

`metrics_plan.md` MUST have one section per metric with these fields
in order: Definition, Canonical script, Input data path, Output,
Statistical comparison, Acceptance.

`run_plan.md` MUST have one command per matrix row with idempotent
skip-check (no command may overwrite an existing `simulation_log.csv`
without explicit user opt-in).

`wagf_experiment_matrix.yml` MUST validate against the
`research_question + hypothesis + domain + models[] + metrics[]`
schema (top-level keys mandatory).

## Bundled resources

- `references/matrix_template.md` — copy-paste-ready
  `wagf_experiment_matrix.yml` skeleton with annotated comments.
- `references/metrics_catalog.md` — every metric the WAGF analyser can
  produce, with file:line refs to the canonical implementation.
- `references/governance_modes.md` — the available governance modes
  per domain, derived from each `agent_types.yaml`.
- `references/anti_overclaim.md` — refusal patterns and clarification
  prompts to avoid scope-creep.

## Acceptance criteria

The skill is ready when:

- For input "Plan a cross-model WAGF flood ablation across Gemma-3 4B,
  Gemma-4 e4b, Ministral 8B with 5 seeds", produces a valid
  `wagf_experiment_matrix.yml` with 3 models × 2 conditions × 5 seeds
  = 30 rows, plus `metrics_plan.md` with IBR + EHE + retry-rate, plus
  `run_plan.md` with skip-checks pointing to `JOH_FINAL_v2/`.
- For input "Compare governed vs ungoverned" without specifying
  models, the skill asks rather than guessing.
- For input "Test the WAGF Coherence Index across drought scenarios",
  the skill refuses ("metric not in catalogue") and asks user to pick
  from the catalogue or define a new metric.
